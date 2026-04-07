# pyre-ignore-all-errors
"""
Authentication service handling user registration, login, and token management.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
import jwt  # type: ignore[import-untyped]
from bson import ObjectId

from app.config.settings import get_settings
from app.models.user import UserDocument
from app.services.face_recognition import face_service
from app.utils.encryption import encrypt_embeddings, decrypt_embeddings
from app.utils.geocoding import reverse_geocode
from app.utils.email_service import (
    send_registration_success_email,
    send_registration_failed_email,
    send_login_success_email,
    send_login_failed_email,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Maximum distance (in metres) between registered and login locations
LOCATION_RADIUS_M = 100  # 100 m — strict geofencing


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two GPS points (in metres).
    Uses the Haversine formula.
    """
    R = 6_371_000  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class AuthService:
    """Service handling authentication operations."""

    def __init__(self, db):
        self.db = db
        self.users_collection = db["users"]

    # ──────────────────────────────────────────────
    #  User Lookup Helpers
    # ──────────────────────────────────────────────

    async def resolve_user_id(self, identifier: str) -> Optional[str]:
        """
        Resolve a user identifier (ObjectId string OR email) to an ObjectId string.
        Returns the ObjectId string if found, else None.
        """
        # If it looks like a valid ObjectId, use it directly
        if ObjectId.is_valid(identifier):
            user = await self.users_collection.find_one({"_id": ObjectId(identifier)}, {"_id": 1})
            if user:
                return str(user["_id"])

        # Otherwise, try to find the user by email
        user = await self.users_collection.find_one({"email": identifier.strip().lower()}, {"_id": 1})
        if user:
            return str(user["_id"])

        return None

    # ──────────────────────────────────────────────
    #  Password Utilities
    # ──────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its bcrypt hash."""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    # ──────────────────────────────────────────────
    #  JWT Token Utilities
    # ──────────────────────────────────────────────

    @staticmethod
    def create_access_token(user_id: str, email: str) -> str:
        """Generate a JWT access token."""
        payload = {
            "sub": user_id,
            "email": email,
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Generate a JWT refresh token."""
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    # ──────────────────────────────────────────────
    #  User Registration
    # ──────────────────────────────────────────────

    async def register_user(
        self,
        name: str,
        email: str,
        phone: str,
        password: str,
        face_images: list,
        location: Optional[dict] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Register a new user, optionally with face recognition.

        If face_images is empty (no camera available), the user is registered
        with password-only authentication.  Face data can be added later.

        Args:
            name: Full name.
            email: Email address.
            phone: Phone number.
            password: Plain-text password.
            face_images: List of base64-encoded face images (can be empty).

        Returns:
            Tuple of (success, message, user_id or None).
        """
        try:
            # Check for existing user
            existing = await self.users_collection.find_one(
                {"$or": [{"email": email}, {"phone": phone}]}
            )
            if existing:
                if existing.get("email") == email:
                    return False, "Email already registered", None
                return False, "Phone number already registered", None

            # Hash password
            password_hash = self.hash_password(password)

            encrypted_embeddings = []
            liveness_verified = False
            has_face_data = len(face_images) >= 4

            if has_face_data:
                # Perform liveness detection
                logger.info("Performing liveness detection...")
                is_live, liveness_msg = face_service.perform_liveness_check(face_images)
                if not is_live:
                    return False, f"Liveness verification failed: {liveness_msg}", None

                # Extract face embeddings from all 4 directions
                logger.info("Extracting face embeddings...")
                embeddings, errors = face_service.extract_multiple_embeddings(face_images)

                if errors:
                    logger.warning(f"Some face images failed: {'; '.join(errors)}")

                if len(embeddings) < 2:
                    return False, "Could not extract enough face embeddings. Please ensure your face is well-lit and clearly visible.", None

                # Encrypt embeddings before storage
                encrypted_embeddings = encrypt_embeddings(embeddings)
                liveness_verified = True
            else:
                logger.info("Registering user without face data (no camera available)")

            # Reverse-geocode the registered location
            registered_address = None
            if location:
                registered_address = await reverse_geocode(
                    location["latitude"], location["longitude"]
                )

            # Create user document
            user_doc = {
                "name": name,
                "email": email,
                "phone": phone,
                "password_hash": password_hash,
                "face_embeddings": encrypted_embeddings,
                "registered_location": location,
                "registered_address": registered_address,
                "liveness_verified": liveness_verified,
                "login_sessions": [],
                "last_login_at": None,
                "last_logout_at": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result = await self.users_collection.insert_one(user_doc)
            user_id = str(result.inserted_id)

            msg = "Registration successful"
            if not has_face_data:
                msg += " (without face data — you can add it later)"

            logger.info(f"User registered successfully: {user_id} (face_data={has_face_data})")

            # Send registration success email (fire-and-forget)
            try:
                await send_registration_success_email(
                    name=name, email=email,
                    address=registered_address, coords=location,
                )
            except Exception as mail_err:
                logger.warning(f"Registration email failed: {mail_err}")

            return True, msg, user_id

        except Exception as e:
            logger.error(f"Registration failed: {e}")

            # Send registration failure email (fire-and-forget)
            try:
                await send_registration_failed_email(
                    email=email, reason=str(e), coords=location,
                )
            except Exception:
                pass

            return False, f"Registration failed: {str(e)}", None

    # ──────────────────────────────────────────────
    #  User Login (Email + Password)
    # ──────────────────────────────────────────────

    async def login_with_password(
        self, email: str, password: str, location: Optional[dict] = None
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Authenticate user with email and password.
        Validates GPS location against registered location.

        Returns:
            Tuple of (success, message, token_data or None).
        """
        try:
            user = await self.users_collection.find_one({"email": email})

            if not user:
                return False, "Invalid email or password", None

            if not self.verify_password(password, user["password_hash"]):
                # Send failed login email for wrong password
                try:
                    cur_addr = await reverse_geocode(location["latitude"], location["longitude"]) if location else None
                    await send_login_failed_email(
                        email=email, reason="Invalid password",
                        address=cur_addr, coords=location,
                    )
                except Exception:
                    pass
                return False, "Invalid email or password", None

            # ── Location check ──
            reg_loc = user.get("registered_location")

            # Backfill: if user has location but no stored address, geocode and save it now
            if reg_loc and not user.get("registered_address"):
                try:
                    backfill_addr = await reverse_geocode(reg_loc["latitude"], reg_loc["longitude"])
                    await self.users_collection.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"registered_address": backfill_addr}},
                    )
                    user["registered_address"] = backfill_addr
                    logger.info(f"Backfilled registered_address for user {user['_id']}")
                except Exception as e:
                    logger.warning(f"Failed to backfill registered_address: {e}")

            if reg_loc and location:
                dist = haversine_distance(
                    reg_loc["latitude"], reg_loc["longitude"],
                    location["latitude"], location["longitude"],
                )
                logger.info(f"Location distance: {dist:.0f}m (limit: {LOCATION_RADIUS_M}m)")
                if dist > LOCATION_RADIUS_M:
                    # Use the STORED registered address from MongoDB (geocoded once at registration)
                    stored_reg_addr = user.get("registered_address") or {}
                    reg_area = ", ".join(filter(None, [
                        stored_reg_addr.get("road"),
                        stored_reg_addr.get("area"),
                        stored_reg_addr.get("suburb"),
                        stored_reg_addr.get("city"),
                        stored_reg_addr.get("state"),
                    ]))
                    # Fallback: use display_name or coordinates
                    if not reg_area:
                        reg_area = stored_reg_addr.get("display_name") or f"({reg_loc['latitude']:.6f}, {reg_loc['longitude']:.6f})"

                    # Reverse-geocode ONLY the current location (fresh GPS)
                    cur_address = await reverse_geocode(location["latitude"], location["longitude"])
                    cur_area = ", ".join(filter(None, [
                        cur_address.get("road"),
                        cur_address.get("area"),
                        cur_address.get("suburb"),
                        cur_address.get("city"),
                        cur_address.get("state"),
                    ]))
                    if not cur_area:
                        cur_area = cur_address.get("display_name") or f"({location['latitude']:.6f}, {location['longitude']:.6f})"

                    mismatch_msg = (
                        f"LOGIN FAILED — Location mismatch! "
                        f"You are {dist:.0f}m away from your registered location. "
                        f"Max allowed: {LOCATION_RADIUS_M}m. "
                        f"RegisteredArea: {reg_area}. "
                        f"CurrentArea: {cur_area}. "
                        f"You can only login from your registered location. "
                        f"To login from this new location, you must register a new account first."
                    )

                    # Send location mismatch email
                    try:
                        await send_login_failed_email(
                            email=email,
                            reason=f"Location mismatch — {dist:.0f}m away from registered location",
                            address=cur_address, coords=location,
                        )
                    except Exception:
                        pass

                    return False, mismatch_msg, None
            elif reg_loc and not location:
                return (
                    False,
                    "Location is required for login. Please enable GPS/location services.",
                    None,
                )
            # If no registered location, skip the check (backward compat)

            user_id = str(user["_id"])

            # Generate tokens
            access_token = self.create_access_token(user_id, email)
            refresh_token = self.create_refresh_token(user_id)
            has_face_data = bool(user.get("face_embeddings"))
            requires_face = has_face_data

            token_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "requires_face_verification": requires_face,
                "user_id": user_id,
            }

            # Record login session for ALL users at password login time
            await self._record_login(user_id, location)

            if requires_face:
                logger.info(f"Password + location OK for user: {user_id} — face verification required")
                # Email will be sent after face verification completes (in routes)
                return True, "Password verified. Face verification required.", token_data
            else:
                logger.info(f"Password + location OK for user: {user_id} — no face data, login complete")
                # Send login success email for password-only users
                try:
                    login_addr = await reverse_geocode(location["latitude"], location["longitude"]) if location else None
                    await send_login_success_email(
                        name=user.get("name", ""), email=email,
                        address=login_addr, coords=location,
                    )
                except Exception:
                    pass
                return True, "Login successful.", token_data

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False, f"Login failed: {str(e)}", None

    # ──────────────────────────────────────────────
    #  Face Verification
    # ──────────────────────────────────────────────

    async def verify_face(
        self, user_id: str, face_image: str
    ) -> Tuple[bool, str, Optional[float]]:
        """
        Verify a user's face against their stored embeddings.

        Args:
            user_id: User ID (ObjectId string or email) to verify against.
            face_image: Base64-encoded face image.

        Returns:
            Tuple of (is_verified, message, confidence_score).
        """
        try:
            # Resolve identifier (email or ObjectId) to actual ObjectId
            resolved_id = await self.resolve_user_id(user_id)
            if not resolved_id:
                return False, "User not found", None
            user = await self.users_collection.find_one({"_id": ObjectId(resolved_id)})

            if not user:
                return False, "User not found", None

            if not user.get("face_embeddings"):
                return False, "No face data registered for this user", None

            # Extract embedding from live image (strict quality checks + full-face validation)
            live_embedding, reason = face_service.extract_embedding_with_reason(face_image, strict=True)
            if live_embedding is None:
                return False, reason, None

            # Decrypt stored embeddings
            stored_embeddings = decrypt_embeddings(user["face_embeddings"])

            # Compare embeddings
            is_match, score = face_service.compare_embeddings(live_embedding, stored_embeddings)

            if is_match:
                logger.info(f"Face verified for user {user_id} with score {score}")
                return True, "Face Verified", score
            else:
                logger.warning(f"Face verification failed for user {user_id}, score: {score}")
                return False, "Face Not Recognized", score

        except Exception as e:
            logger.error(f"Face verification error: {e}")
            return False, f"Verification failed: {str(e)}", None

    # ──────────────────────────────────────────────
    #  Get User by ID
    # ──────────────────────────────────────────────

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """Retrieve user data by ID or email (excluding sensitive fields)."""
        try:
            resolved_id = await self.resolve_user_id(user_id)
            if not resolved_id:
                return None
            user = await self.users_collection.find_one(
                {"_id": ObjectId(resolved_id)},
                {
                    "password_hash": 0,
                    "face_embeddings": 0,
                },
            )
            if user:
                user["_id"] = str(user["_id"])
                # Add a flag telling the frontend whether face data exists
                face_emb = user.pop("face_embedding", None)
                user["has_face_data"] = bool(face_emb)

                # Ensure session tracking fields exist (for users registered before this feature)
                user.setdefault("last_login_at", None)
                user.setdefault("last_logout_at", None)
                user.setdefault("login_sessions", [])
                user.setdefault("registered_address", None)
                user.setdefault("last_login_address", None)

                # Convert datetime to ISO strings for JSON serialisation
                for key in ["created_at", "updated_at", "last_login_at", "last_logout_at"]:
                    if isinstance(user.get(key), datetime):
                        user[key] = user[key].isoformat()
                # Convert login_sessions datetimes
                for session in user.get("login_sessions", []):
                    for k in ["login_at", "logout_at"]:
                        if isinstance(session.get(k), datetime):
                            session[k] = session[k].isoformat()
            return user
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None

    # ──────────────────────────────────────────────
    #  Login/Logout Session Tracking
    # ──────────────────────────────────────────────

    async def _record_login(self, user_id: str, location: Optional[dict] = None):
        """Record login time, location, and reverse-geocoded address in the user document."""
        try:
            now = datetime.utcnow()
            login_address = None
            if location:
                login_address = await reverse_geocode(
                    location["latitude"], location["longitude"]
                )

            session_entry = {
                "login_at": now,
                "logout_at": None,
                "location": location,
                "address": login_address,
            }

            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "last_login_at": now,
                        "last_login_location": location,
                        "last_login_address": login_address,
                    },
                    "$push": {
                        "login_sessions": {
                            "$each": [session_entry],
                            "$slice": -20,  # keep last 20 sessions
                        }
                    },
                },
            )
            logger.info(f"Login session recorded for user: {user_id}")
        except Exception as e:
            logger.warning(f"Failed to record login session: {e}")

    async def record_login_for_face_verified(self, user_id: str):
        """Called after face verification completes to record the login session."""
        # Get stored login location from the last password login attempt
        try:
            user = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)},
                {"registered_location": 1}
            )
            location = user.get("registered_location") if user else None
            await self._record_login(user_id, location)
        except Exception as e:
            logger.warning(f"Failed to record face-verified login: {e}")

    async def record_logout(self, user_id: str):
        """Record logout time for the user's most recent session."""
        try:
            now = datetime.utcnow()
            # Update the last session's logout_at
            user = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)},
                {"login_sessions": 1},
            )
            if user and user.get("login_sessions"):
                sessions = user["login_sessions"]
                sessions[-1]["logout_at"] = now
                await self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$set": {
                            "last_logout_at": now,
                            "login_sessions": sessions,
                        }
                    },
                )
            else:
                await self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"last_logout_at": now}},
                )
            logger.info(f"Logout recorded for user: {user_id}")
        except Exception as e:
            logger.warning(f"Failed to record logout: {e}")
