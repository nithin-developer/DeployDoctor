"""Authentication schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ============ Request Schemas ============

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Registration request schema."""
    full_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class TwoFAVerifyRequest(BaseModel):
    """2FA verification request schema."""
    twofa_token: str
    code: str = Field(..., min_length=6, max_length=6)


class TwoFAEnableRequest(BaseModel):
    """2FA enable request schema."""
    token: str = Field(..., min_length=6, max_length=6)


class UpdateAccountRequest(BaseModel):
    """Update account request schema."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


# ============ Response Schemas ============

class UserResponse(BaseModel):
    """User response schema."""
    id: str
    full_name: str
    email: str
    is_active: bool = True
    is_2fa_enabled: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Token response schema (successful login)."""
    access_token: str
    user: UserResponse


class TwoFARequiredResponse(BaseModel):
    """Response when 2FA is required."""
    twofa_required: bool = True
    twofa_token: str


class TwoFASetupResponse(BaseModel):
    """2FA setup response with secret and QR code URI."""
    secret: str
    qr_code_uri: str


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
