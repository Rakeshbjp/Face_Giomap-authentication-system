"""
Authentication API routes.
Handles user registration, login, face verification, and profile access.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

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
    else:
        logger.warning(f"Face verification failed for user: {request.user_id}")

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
    """
    from app.services.face_recognition import face_service
    from app.utils.encryption import decrypt_embeddings
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

        is_verified, message, confidence = await auth_service.verify_face(
            user_id=resolved_id,
            face_image=request.face_image,
        )

        if not is_verified:
            return FaceVerificationResponse(status=False, message=message, confidence=confidence)

        user = await auth_service.get_user_by_id(resolved_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        access_token = AuthService.create_access_token(resolved_id, user["email"])
        refresh_token = AuthService.create_refresh_token(resolved_id)

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
#  GET /api/auth/health
# ──────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Face Auth API"}
