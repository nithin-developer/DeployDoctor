from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Request, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from config.settings import get_settings
from services.auth_service import auth_service
from schemas.auth import (
    LoginRequest,
    TwoFAVerifyRequest,
    TwoFAEnableRequest,
    UpdateAccountRequest,
    ChangePasswordRequest,
    TokenResponse,
    TwoFARequiredResponse,
    TwoFASetupResponse,
    UserResponse,
    MessageResponse,
    ErrorResponse
)
from models.users import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get the current authenticated user."""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = auth_header.split(" ", 1)[1]
    payload = auth_service.decode_token(token, "access")
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    try:
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await auth_service.get_user_by_id(db, user_id)
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not active")
    
    return user


def set_refresh_cookie(response: Response, refresh_token: str, expires: datetime):
    """Set the refresh token cookie."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        expires=expires,
        path="/api/auth"
    )


@router.post("/login", response_model=TokenResponse | TwoFARequiredResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password."""
    email = request.email.strip().lower()
    
    user = await auth_service.get_user_by_email(db, email)
    
    if not user or not auth_service.verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="user_inactive")
    
    # 2FA check
    if user.is_2fa_enabled:
        twofa_token = auth_service.create_2fa_token(user)
        return TwoFARequiredResponse(twofa_required=True, twofa_token=twofa_token)
    
    # Generate tokens
    access_token = auth_service.create_access_token(user)
    refresh_token, jti, expires_at = auth_service.create_refresh_token(user)
    
    # Store refresh token
    await auth_service.store_refresh_token(db, user.id, jti, expires_at)
    
    # Set refresh cookie
    set_refresh_cookie(response, refresh_token, expires_at)
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=str(user.id),
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            is_2fa_enabled=user.is_2fa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    )


@router.post("/verify-2fa", response_model=TokenResponse)
async def verify_2fa(
    request: TwoFAVerifyRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Verify 2FA code and complete login."""
    payload = auth_service.decode_token(request.twofa_token, "2fa")
    
    if not payload:
        raise HTTPException(status_code=401, detail="invalid_twofa_token")
    
    try:
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="invalid_twofa_token")
    
    user = await auth_service.get_user_by_id(db, user_id)
    
    if not user or not user.is_2fa_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="2fa_not_setup")
    
    if not auth_service.verify_totp(user.totp_secret, request.code):
        raise HTTPException(status_code=401, detail="invalid_code")
    
    # Generate tokens
    access_token = auth_service.create_access_token(user)
    refresh_token, jti, expires_at = auth_service.create_refresh_token(user)
    
    # Store refresh token
    await auth_service.store_refresh_token(db, user.id, jti, expires_at)
    
    # Set refresh cookie
    set_refresh_cookie(response, refresh_token, expires_at)
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=str(user.id),
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            is_2fa_enabled=user.is_2fa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: Annotated[str | None, Cookie()] = None
):
    """Refresh the access token."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="missing_refresh_cookie")
    
    payload = auth_service.decode_token(refresh_token, "refresh")
    
    if not payload:
        raise HTTPException(status_code=401, detail="invalid_refresh_token")
    
    try:
        user_id = UUID(payload["sub"])
        jti = payload["jti"]
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="invalid_refresh_token")
    
    # Verify token exists and is valid
    stored_token = await auth_service.get_refresh_token(db, jti, user_id)
    
    if not stored_token or not stored_token.is_valid():
        raise HTTPException(status_code=401, detail="refresh_revoked")
    
    user = await auth_service.get_user_by_id(db, user_id)
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user_inactive")
    
    # Revoke old token
    await auth_service.revoke_refresh_token(db, jti)
    
    # Generate new tokens
    access_token = auth_service.create_access_token(user)
    new_refresh_token, new_jti, expires_at = auth_service.create_refresh_token(user)
    
    # Store new refresh token
    await auth_service.store_refresh_token(db, user.id, new_jti, expires_at)
    
    # Set new refresh cookie
    set_refresh_cookie(response, new_refresh_token, expires_at)
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=str(user.id),
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            is_2fa_enabled=user.is_2fa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: Annotated[str | None, Cookie()] = None
):
    """Logout and revoke refresh token."""
    # Clear cookie
    response.delete_cookie(key="refresh_token", path="/api/auth")
    
    if refresh_token:
        payload = auth_service.decode_token(refresh_token, "refresh")
        if payload and "jti" in payload:
            await auth_service.revoke_refresh_token(db, payload["jti"])
    
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=str(current_user.id),
        full_name=current_user.full_name,
        email=current_user.email,
        is_active=current_user.is_active,
        is_2fa_enabled=current_user.is_2fa_enabled,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


@router.post("/setup-2fa", response_model=TwoFASetupResponse)
async def setup_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate TOTP secret and QR code for 2FA setup."""
    secret = auth_service.generate_totp_secret()
    uri = auth_service.get_totp_uri(secret, current_user.email)
    
    current_user.totp_secret = secret
    await db.commit()
    
    return TwoFASetupResponse(secret=secret, qr_code_uri=uri)


@router.post("/enable-2fa", response_model=MessageResponse)
async def enable_2fa(
    request: TwoFAEnableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Enable 2FA after verifying TOTP token."""
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA setup not initiated")
    
    if not auth_service.verify_totp(current_user.totp_secret, request.token):
        raise HTTPException(status_code=400, detail="Invalid TOTP token")
    
    current_user.is_2fa_enabled = True
    await db.commit()
    
    return MessageResponse(message="2FA has been successfully enabled")


@router.post("/disable-2fa", response_model=MessageResponse)
async def disable_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disable 2FA for the current user."""
    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    await db.commit()
    
    return MessageResponse(message="2FA has been disabled")


@router.put("/update-account", response_model=UserResponse)
async def update_account(
    request: UpdateAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update account information."""
    if request.full_name is not None:
        current_user.full_name = request.full_name
    
    await db.commit()
    await db.refresh(current_user)
    
    return UserResponse(
        id=str(current_user.id),
        full_name=current_user.full_name,
        email=current_user.email,
        is_active=current_user.is_active,
        is_2fa_enabled=current_user.is_2fa_enabled,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change user password."""
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    if not auth_service.verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    current_user.hashed_password = auth_service.hash_password(request.new_password)
    await db.commit()
    
    return MessageResponse(message="Password changed successfully")
