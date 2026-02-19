from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


# ============ AUTH SCHEMAS ============

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Password is required')
        return v


class TwoFAVerifyRequest(BaseModel):
    twofa_token: str
    code: str

    @field_validator('code')
    @classmethod
    def code_valid(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) != 6 or not v.isdigit():
            raise ValueError('Code must be 6 digits')
        return v


class TwoFAEnableRequest(BaseModel):
    token: str


class UpdateAccountRequest(BaseModel):
    full_name: Optional[str] = None

    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Full name must be at least 2 characters')
        if len(v) > 100:
            raise ValueError('Full name must not exceed 100 characters')
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError('New password must be at least 6 characters')
        return v


# ============ RESPONSE SCHEMAS ============

class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    is_active: bool
    is_2fa_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse


class TwoFARequiredResponse(BaseModel):
    twofa_required: bool = True
    twofa_token: str


class TwoFASetupResponse(BaseModel):
    secret: str
    qr_code_uri: str


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
