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
from app.config.email import send_auth_email, fire_and_forget_email

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
                    await send_auth_email(email, "register", "failure")
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
                "role": "admin" if email == "admin@example.com" else "user",
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
            fire_and_forget_email(email, "register", "success")
            return True, msg, user_id

        except Exception as e:
            logger.error(f"Registration failed: {e}")
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
                fire_and_forget_email(email, "login", "failure")
                return False, "Invalid email or password", None

            if not self.verify_password(password, user["password_hash"]):
                fire_and_forget_email(email, "login", "failure")
                return False, "Invalid email or password", None

            # ── Location check ──
            reg_loc = user.get("registered_location")
            if reg_loc and location:
                dist = haversine_distance(
                    reg_loc["latitude"], reg_loc["longitude"],
                    location["latitude"], location["longitude"],
                )
                logger.info(f"Location distance: {dist:.0f}m (limit: {LOCATION_RADIUS_M}m)")
                if dist > LOCATION_RADIUS_M:
                    reg_addr = await reverse_geocode(reg_loc["latitude"], reg_loc["longitude"])
                    curr_addr = await reverse_geocode(location["latitude"], location["longitude"])
                    
                    def format_addr(addr_doc, lat, lng):
                        if not addr_doc or "fallback" in addr_doc:
                            return f"{lat:.6f}, {lng:.6f}"
                        parts = [
                            addr_doc.get("road"),
                            addr_doc.get("suburb") or addr_doc.get("area"),
                            addr_doc.get("city"),
                            addr_doc.get("state"),
                            addr_doc.get("country"),
                            addr_doc.get("pincode")
                        ]
                        valid_parts = [p for p in parts if p is not None and str(p).strip()]
                        return ", ".join(valid_parts) if valid_parts else addr_doc.get("display_name", f"{lat:.6f}, {lng:.6f}")

                    email_reg_str = format_addr(reg_addr, reg_loc['latitude'], reg_loc['longitude'])
                    email_curr_str = format_addr(curr_addr, location['latitude'], location['longitude'])
                    
                    reg_display = f"({reg_loc['latitude']:.6f}, {reg_loc['longitude']:.6f}) - {reg_addr.get('display_name', 'Location')}"
                    curr_display = f"({location['latitude']:.6f}, {location['longitude']:.6f}) - {curr_addr.get('display_name', 'Location')}"
                    fire_and_forget_email(
                        email, "login", "location_mismatch",
                        reg_display=email_reg_str,
                        curr_display=email_curr_str
                    )
                    return (
                        False,
                        f"LOGIN FAILED — Location mismatch! "
                        f"You are {dist:.0f}m away from your registered location. "
                        f"Max allowed: {LOCATION_RADIUS_M}m. "
                        f"Registered: {reg_display}. "
                        f"Current: {curr_display}. "
                        f"You can only login from your registered location. "
                        f"To login from this new location, you must register a new account first.",
                        None,
                    )
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
                # Don't send login success email yet — face verification still pending
                return True, "Password verified. Face verification required.", token_data
            else:
                logger.info(f"Password + location OK for user: {user_id} — no face data, login complete")
                fire_and_forget_email(email, "login", "success")
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
                # face_embeddings is excluded by projection, so use liveness_verified flag
                user["has_face_data"] = user.get("liveness_verified", False)

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
        # Step 1: Record logout in the database
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
            logger.warning(f"Failed to record logout session: {e}")

        # Step 2: Send logout notification email (always attempted, even if step 1 fails)
        try:
            user_doc = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)}, {"email": 1}
            )
            if user_doc and user_doc.get("email"):
                logger.info(f"Sending logout email to {user_doc['email']}")
                fire_and_forget_email(user_doc["email"], "login", "logout")
            else:
                logger.warning(f"Cannot send logout email — user {user_id} not found or has no email")
        except Exception as e:
            logger.error(f"Failed to send logout email for user {user_id}: {e}")
