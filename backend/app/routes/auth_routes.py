# pyre-ignore-all-errors
"""
Authentication API routes.
Handles user registration, login, face verification, and profile access.
"""

import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from bson import ObjectId

from app.config.database import get_database
from app.models.user import (
    UserRegisterRequest,
    UserLoginRequest,
    FaceVerifyRequest,
    RegisterResponse,
    AuthTokenResponse,
    FaceVerificationResponse,
    StandardResponse,
)
from app.services.auth_service import AuthService
from app.middleware.auth_middleware import get_current_user, security

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ──────────────────────────────────────────────
#  POST /api/auth/register
# ──────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(request: UserRegisterRequest, db=Depends(get_database)):
    """
    Register a new user with face recognition.

    Requires:
    - Full name, email, phone, password
    - 4 face images (front, left, right, up/down) as base64 strings
    - Liveness detection is performed automatically
    """
    auth_service = AuthService(db)

    success, message, user_id = await auth_service.register_user(
        name=request.name,
        email=request.email,
        phone=request.phone,
        password=request.password,
        face_images=request.face_images,
        location=request.location.model_dump() if request.location else None,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    logger.info(f"New user registered: {user_id}")
    return RegisterResponse(status=True, message=message, user_id=user_id)


# ──────────────────────────────────────────────
#  POST /api/auth/login
# ──────────────────────────────────────────────

@router.post("/login", response_model=AuthTokenResponse)
async def login_user(request: UserLoginRequest, db=Depends(get_database)):
    """
    Login with email and password.

    Returns JWT tokens but face verification is still required.
    Client must call /api/auth/verify-face next.
    """
    auth_service = AuthService(db)

    success, message, token_data = await auth_service.login_with_password(
        email=request.email,
        password=request.password,
        location=request.location.model_dump() if request.location else None,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )

    logger.info(f"User logged in (password verified): {token_data['user_id']}")
    return AuthTokenResponse(**token_data)


# ──────────────────────────────────────────────
#  POST /api/auth/verify-face
# ──────────────────────────────────────────────

@router.post("/verify-face", response_model=FaceVerificationResponse)
async def verify_face(
    request: FaceVerifyRequest,
    db=Depends(get_database),
):
    """
    Verify a user's face against stored embeddings.

    Called after password login or as standalone face login.
    Captures a live face image and compares it with stored embeddings.
    """
    auth_service = AuthService(db)

    is_verified, message, confidence = await auth_service.verify_face(
        user_id=request.user_id,
        face_image=request.face_image,
    )

    if is_verified:
        logger.info(f"Face verified for user: {request.user_id}")
        # Send login success email after face verification
        try:
            from app.utils.email_service import send_login_success_email
            user_data = await auth_service.get_user_by_id(request.user_id)
            if user_data:
                login_addr = user_data.get("last_login_address") or user_data.get("registered_address")
                login_loc = user_data.get("registered_location")
                await send_login_success_email(
                    name=user_data.get("name", ""),
                    email=user_data.get("email", ""),
                    address=login_addr, coords=login_loc,
                )
        except Exception as mail_err:
            logger.warning(f"Login success email failed: {mail_err}")
    else:
        logger.warning(f"Face verification failed for user: {request.user_id}")
        # Send login failed email for face mismatch
        try:
            from app.utils.email_service import send_login_failed_email
            user_data = await auth_service.get_user_by_id(request.user_id)
            if user_data:
                await send_login_failed_email(
                    email=user_data.get("email", ""),
                    reason="Face verification failed — face did not match registered data",
                    address=user_data.get("registered_address"),
                    coords=user_data.get("registered_location"),
                )
        except Exception:
            pass

    return FaceVerificationResponse(
        status=is_verified,
        message=message,
        confidence=confidence,
    )


# ──────────────────────────────────────────────
#  POST /api/auth/face-login
# ──────────────────────────────────────────────

@router.post("/face-login")
async def face_login(request: FaceVerifyRequest, db=Depends(get_database)):
    """
    Login using face recognition only.
    Searches all users and matches the face embedding.
    Enforces location check against registered location.
    """
    from app.services.face_recognition import face_service
    from app.utils.encryption import decrypt_embeddings
    from app.services.auth_service import haversine_distance, LOCATION_RADIUS_M
    from bson import ObjectId

    # Extract embedding from the provided face image (strict quality checks + full-face validation)
    live_embedding, reason = face_service.extract_embedding_with_reason(request.face_image, strict=True)
    if live_embedding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    # If user_id is provided, verify against that specific user
    if request.user_id:
        auth_service = AuthService(db)

        # Resolve the identifier (could be email or ObjectId)
        resolved_id = await auth_service.resolve_user_id(request.user_id)
        if not resolved_id:
            raise HTTPException(status_code=404, detail="User not found")

        # ── Location check for face-login ──
        user_doc = await db.users.find_one({"_id": ObjectId(resolved_id)})
        if user_doc:
            reg_loc = user_doc.get("registered_location")
            login_loc = request.location.model_dump() if request.location else None

            if reg_loc and login_loc:
                dist = haversine_distance(
                    reg_loc["latitude"], reg_loc["longitude"],
                    login_loc["latitude"], login_loc["longitude"],
                )
                if dist > LOCATION_RADIUS_M:
                    from app.utils.geocoding import reverse_geocode

                    # Use STORED registered address from DB
                    stored_reg_addr = user_doc.get("registered_address") or {}
                    reg_area = ", ".join(filter(None, [
                        stored_reg_addr.get("road"),
                        stored_reg_addr.get("area"),
                        stored_reg_addr.get("suburb"),
                        stored_reg_addr.get("city"),
                        stored_reg_addr.get("state"),
                    ]))
                    if not reg_area:
                        reg_area = stored_reg_addr.get("display_name") or f"({reg_loc['latitude']:.6f}, {reg_loc['longitude']:.6f})"

                    # Geocode ONLY current location fresh
                    cur_address = await reverse_geocode(login_loc["latitude"], login_loc["longitude"])
                    cur_area = ", ".join(filter(None, [
                        cur_address.get("road"),
                        cur_address.get("area"),
                        cur_address.get("suburb"),
                        cur_address.get("city"),
                        cur_address.get("state"),
                    ]))
                    if not cur_area:
                        cur_area = cur_address.get("display_name") or f"({login_loc['latitude']:.6f}, {login_loc['longitude']:.6f})"

                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"LOGIN FAILED — Location mismatch! "
                            f"You are {dist:.0f}m away from your registered location. "
                            f"Max allowed: {LOCATION_RADIUS_M}m. "
                            f"RegisteredArea: {reg_area}. "
                            f"CurrentArea: {cur_area}. "
                            f"You can only login from your registered location. "
                            f"To login from this new location, you must register a new account first."
                        ),
                    )
            elif reg_loc and not login_loc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Location is required for login. Please enable GPS/location services.",
                )

        is_verified, message, confidence = await auth_service.verify_face(
            user_id=resolved_id,
            face_image=request.face_image,
        )

        if not is_verified:
            # Send face-login failure email
            try:
                from app.utils.email_service import send_login_failed_email
                await send_login_failed_email(
                    email=user.get("email", "") if user else "",
                    reason="Face verification failed — face did not match",
                    address=user_doc.get("registered_address") if user_doc else None,
                    coords=login_loc,
                )
            except Exception:
                pass
            return FaceVerificationResponse(status=False, message=message, confidence=confidence)

        user = await auth_service.get_user_by_id(resolved_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        access_token = AuthService.create_access_token(resolved_id, user["email"])
        refresh_token = AuthService.create_refresh_token(resolved_id)

        # Record login session for face-login users
        login_loc = request.location.model_dump() if request.location else None
        await auth_service._record_login(resolved_id, login_loc)

        # Send login success email
        try:
            from app.utils.email_service import send_login_success_email
            from app.utils.geocoding import reverse_geocode as _geocode
            login_addr = await _geocode(login_loc["latitude"], login_loc["longitude"]) if login_loc else None
            await send_login_success_email(
                name=user.get("name", ""), email=user.get("email", ""),
                address=login_addr, coords=login_loc,
            )
        except Exception:
            pass

        return {
            "status": True,
            "message": "Face Verified",
            "confidence": confidence,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": resolved_id,
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="User ID is required for face login",
    )


# ──────────────────────────────────────────────
#  GET /api/auth/profile
# ──────────────────────────────────────────────

@router.get("/profile", response_model=StandardResponse)
async def get_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_database),
):
    """
    Get the authenticated user's profile.
    Requires a valid JWT access token.
    """
    payload = await get_current_user(credentials)
    user_id = payload.get("sub")

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return StandardResponse(status=True, message="Profile retrieved", data=user)


# ──────────────────────────────────────────────
#  PUT /api/auth/update-face
# ──────────────────────────────────────────────

class UpdateFaceRequest(BaseModel):
    """Schema for updating face data."""
    face_images: List[str] = Field(
        ...,
        min_length=4, max_length=4,
        description="4 base64-encoded face images: [front, left, right, up/down]"
    )


@router.put("/update-face", response_model=StandardResponse)
async def update_face_data(
    request: UpdateFaceRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_database),
):
    """
    Add or update face data for an authenticated user.
    Useful when user registered without face data or wants to re-enroll.
    Requires a valid JWT access token.
    """
    from app.services.face_recognition import face_service
    from app.utils.encryption import encrypt_embeddings
    from datetime import datetime

    payload = await get_current_user(credentials)
    user_id = payload.get("sub")

    # Perform liveness check
    logger.info(f"Performing liveness check for face update (user: {user_id})")
    is_live, liveness_msg = face_service.perform_liveness_check(request.face_images)
    if not is_live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Liveness verification failed: {liveness_msg}",
        )

    # Extract embeddings
    logger.info("Extracting face embeddings for update...")
    embeddings, errors = face_service.extract_multiple_embeddings(request.face_images)

    if errors:
        logger.warning(f"Some face images failed during update: {'; '.join(errors)}")

    if len(embeddings) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract enough face embeddings. Ensure your face is well-lit and clearly visible.",
        )

    # Encrypt and store
    encrypted_embeddings = encrypt_embeddings(embeddings)

    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "face_embedding": encrypted_embeddings,
                "liveness_verified": True,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"Face data updated for user: {user_id} ({len(embeddings)} embeddings)")
    return StandardResponse(
        status=True,
        message=f"Face data updated successfully ({len(embeddings)} views enrolled)",
    )


# ──────────────────────────────────────────────
#  GET /api/auth/health
# ──────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Face Auth API"}


# ──────────────────────────────────────────────
#  POST /api/auth/logout
# ──────────────────────────────────────────────

@router.post("/logout", response_model=StandardResponse)
async def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_database),
):
    """Record logout time for the authenticated user."""
    payload = await get_current_user(credentials)
    user_id = payload.get("sub")

    auth_service = AuthService(db)
    await auth_service.record_logout(user_id)

    logger.info(f"User logged out: {user_id}")
    return StandardResponse(status=True, message="Logged out successfully")


# ──────────────────────────────────────────────
#  POST /api/auth/geocode
# ──────────────────────────────────────────────

class GeocodeRequest(BaseModel):
    latitude: float
    longitude: float


@router.post("/geocode")
async def geocode_location(request: GeocodeRequest):
    """Reverse-geocode a lat/lng to a human-readable address."""
    from app.utils.geocoding import reverse_geocode
    result = await reverse_geocode(request.latitude, request.longitude)
    return {"status": True, "data": result}

