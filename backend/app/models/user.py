# pyre-ignore-all-errors
"""
Pydantic models for User entity.
Handles request validation, response serialization, and DB schema.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator
import re


# ──────────────────────────────────────────────
#  Shared Sub-Models
# ──────────────────────────────────────────────

class LocationData(BaseModel):
    """GPS coordinates."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")


# ──────────────────────────────────────────────
#  Request Models
# ──────────────────────────────────────────────

# Professions that grant admin-level access to the Admin Control Panel
ADMIN_PROFESSIONS = [
    "HR",
    "Manager",
    "Team Leader",
    "Senior Manager",
    "CEO",
    "Managing Director",
    "Director",
    "CTO",
    "CFO",
    "COO",
    "Vice President",
]

# All available profession choices for the registration form
ALL_PROFESSIONS = [
    "Employee",
    "HR",
    "Manager",
    "Team Leader",
    "Senior Manager",
    "CEO",
    "Managing Director",
    "Director",
    "CTO",
    "CFO",
    "COO",
    "Vice President",
]


class UserRegisterRequest(BaseModel):
    """Schema for user registration request."""
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the user")
    email: EmailStr = Field(..., description="Unique email address")
    phone: str = Field(..., min_length=10, max_length=15, description="Unique phone number")
    password: str = Field(..., min_length=8, max_length=128, description="Strong password")
    face_images: List[str] = Field(
        default_factory=list,
        max_length=4,
        description="Base64-encoded face images: [front, left, right, up/down]. Empty if no camera."
    )
    location: Optional[LocationData] = Field(
        default=None,
        description="GPS coordinates at time of registration. Used for location-locked login."
    )
    designation: str = Field(..., min_length=2, max_length=100, description="Employee designation")
    profession: str = Field(..., description="Profession/role in the company (e.g., Employee, HR, Manager, CEO)")
    joining_date: str = Field(..., description="Date of joining (YYYY-MM-DD)")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?\d{10,15}$", cleaned):
            raise ValueError("Invalid phone number format")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce strong password policy."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

class CompanySettings(BaseModel):
    """Schema for global company settings."""
    hours_per_day: float = Field(default=8.0, gt=0, le=24, description="Global working hours per day")
    hours_per_week: float = Field(default=40.0, gt=0, description="Global working hours per week")
    hours_per_month: float = Field(default=160.0, gt=0, description="Global working hours per month")
    hours_per_year: float = Field(default=1920.0, gt=0, description="Global working hours per year")
    weekly_off: str = Field(default="Sunday", description="Day(s) off each week (e.g., 'Sunday')")

class CheckUserRequest(BaseModel):
    """Schema to check if a user exists by email or phone."""
    email: EmailStr = Field(..., description="Unique email address")
    phone: str = Field(..., min_length=10, max_length=15, description="Unique phone number")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?\d{10,15}$", cleaned):
            raise ValueError("Invalid phone number format")
        return cleaned


class UserLoginRequest(BaseModel):
    """Schema for email + password login."""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")
    location: Optional[LocationData] = Field(
        default=None,
        description="Current GPS coordinates. Compared against registered location."
    )


class FaceVerifyRequest(BaseModel):
    """Schema for face verification request."""
    user_id: str = Field(..., description="User ID to verify against")
    face_image: str = Field(..., description="Base64-encoded face image for verification")
    challenge_frame: Optional[str] = Field(
        default=None,
        description="Second base64 frame captured ~400ms after face_image for temporal liveness detection."
    )
    location: Optional[LocationData] = Field(
        default=None,
        description="Current GPS coordinates for location verification during face login."
    )


# ──────────────────────────────────────────────
#  Response Models
# ──────────────────────────────────────────────

class UserResponse(BaseModel):
    """Schema for user data in API responses."""
    id: str = Field(..., alias="_id")
    name: str
    email: str
    phone: str
    role: str = "user"
    profession: Optional[str] = None
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    joining_date: Optional[str] = None
    hours_per_day: Optional[float] = None
    weekly_off: Optional[str] = None
    registered_location: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class AuthTokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    requires_face_verification: bool = True
    user_id: str


class FaceVerificationResponse(BaseModel):
    """Schema for face verification result."""
    status: bool
    message: str
    confidence: Optional[float] = None


class RegisterResponse(BaseModel):
    """Schema for registration response."""
    status: bool
    message: str
    user_id: Optional[str] = None


class StandardResponse(BaseModel):
    """Generic API response wrapper."""
    status: bool
    message: str
    data: Optional[dict] = None


# ──────────────────────────────────────────────
#  Database Document Model
# ──────────────────────────────────────────────

class UserDocument(BaseModel):
    """Schema representing a user document in MongoDB."""
    name: str
    email: str
    phone: str
    password_hash: str
    face_embeddings: List[List[float]] = Field(
        default_factory=list,
        description="Array of face embedding vectors (encrypted)"
    )
    role: str = Field(
        default="user",
        description="User role, either 'admin' or 'user'."
    )
    registered_location: Optional[dict] = Field(
        default=None,
        description="GPS location at registration time: {latitude, longitude}"
    )
    employee_id: Optional[str] = Field(default=None, description="Auto-generated unique employee ID")
    designation: Optional[str] = Field(default=None, description="Employee job designation")
    profession: Optional[str] = Field(default=None, description="Profession/role in the company")
    joining_date: Optional[str] = Field(default=None, description="Initial employment date")
    hours_per_day: Optional[float] = Field(default=None, description="Mandatory daily work hours")
    weekly_off: Optional[str] = Field(default=None, description="Assigned days off")
    liveness_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
