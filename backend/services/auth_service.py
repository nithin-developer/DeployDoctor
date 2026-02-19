import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from uuid import UUID

import jwt
import pyotp
from passlib.context import CryptContext
from werkzeug.security import check_password_hash as werkzeug_check_password
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.settings import get_settings
from models.users import User, RefreshToken

settings = get_settings()

# Password hashing - bcrypt for new passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self):
        self.jwt_secret = settings.JWT_SECRET
        self.access_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
    
    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        Supports both bcrypt (new) and werkzeug pbkdf2 (legacy) formats.
        """
        # Check if it's a werkzeug hash (starts with pbkdf2: or scrypt:)
        if hashed_password.startswith(("pbkdf2:", "scrypt:")):
            return werkzeug_check_password(hashed_password, plain_password)
        
        # Otherwise use passlib/bcrypt
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False
    
    def create_access_token(self, user: User) -> str:
        """Create an access token for a user."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.access_expire_minutes)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
    
    def create_refresh_token(self, user: User) -> Tuple[str, str, datetime]:
        """
        Create a refresh token for a user.
        
        Returns:
            Tuple of (token, jti, expires_at)
        """
        now = datetime.now(timezone.utc)
        jti = secrets.token_hex(16)
        expires_at = now + timedelta(days=self.refresh_expire_days)
        
        payload = {
            "sub": str(user.id),
            "type": "refresh",
            "jti": jti,
            "iat": now,
            "exp": expires_at
        }
        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        return token, jti, expires_at
    
    def create_2fa_token(self, user: User) -> str:
        """Create a temporary 2FA token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "type": "2fa",
            "iat": now,
            "exp": now + timedelta(minutes=5)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
    
    def decode_token(self, token: str, expected_type: str = "access") -> Optional[dict]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token string
            expected_type: Expected token type (access, refresh, 2fa)
            
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            if payload.get("type") != expected_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email."""
        result = await db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Get a user by ID."""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def store_refresh_token(
        self,
        db: AsyncSession,
        user_id: UUID,
        jti: str,
        expires_at: datetime
    ) -> RefreshToken:
        """Store a refresh token in the database."""
        refresh_token = RefreshToken(
            user_id=user_id,
            token_id=jti,
            expires_at=expires_at
        )
        db.add(refresh_token)
        await db.commit()
        return refresh_token
    
    async def get_refresh_token(
        self,
        db: AsyncSession,
        jti: str,
        user_id: UUID
    ) -> Optional[RefreshToken]:
        """Get a refresh token from the database."""
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_id == jti,
                RefreshToken.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
    
    async def revoke_refresh_token(
        self,
        db: AsyncSession,
        jti: str
    ) -> None:
        """Revoke a refresh token."""
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_id == jti)
        )
        token = result.scalar_one_or_none()
        if token:
            token.revoked = True
            await db.commit()
    
    def generate_totp_secret(self) -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()
    
    def get_totp_uri(self, secret: str, email: str, issuer: str = "DevOps Agent") -> str:
        """Get the TOTP provisioning URI for QR code generation."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer)
    
    def verify_totp(self, secret: str, code: str) -> bool:
        """Verify a TOTP code."""
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)


# Singleton instance
auth_service = AuthService()
