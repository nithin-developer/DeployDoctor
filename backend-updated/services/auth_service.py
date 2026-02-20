"""Authentication service for handling JWT tokens, 2FA, and user management."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

import bcrypt
import jwt
import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from models.users import User, RefreshToken

settings = get_settings()


class AuthService:
    """Service class for authentication operations."""

    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.algorithm = "HS256"
        self.access_token_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        self.twofa_token_expire = timedelta(minutes=5)

    # ============ Password Methods ============

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False

    # ============ JWT Token Methods ============

    def create_access_token(self, user: User) -> str:
        """Create an access token for a user."""
        expires = datetime.now(timezone.utc) + self.access_token_expire
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "type": "access",
            "exp": expires,
            "iat": datetime.now(timezone.utc)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user: User) -> Tuple[str, str, datetime]:
        """
        Create a refresh token for a user.
        
        Returns:
            Tuple of (token, jti, expires_at)
        """
        jti = secrets.token_hex(32)
        expires = datetime.now(timezone.utc) + self.refresh_token_expire
        payload = {
            "sub": str(user.id),
            "type": "refresh",
            "jti": jti,
            "exp": expires,
            "iat": datetime.now(timezone.utc)
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, jti, expires

    def create_2fa_token(self, user: User) -> str:
        """Create a temporary 2FA verification token."""
        expires = datetime.now(timezone.utc) + self.twofa_token_expire
        payload = {
            "sub": str(user.id),
            "type": "2fa",
            "exp": expires,
            "iat": datetime.now(timezone.utc)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str, expected_type: str) -> Optional[dict]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: The JWT token string
            expected_type: Expected token type ("access", "refresh", "2fa")
            
        Returns:
            Token payload dict or None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != expected_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # ============ User Database Methods ============

    async def get_user_by_id(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Get a user by their ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by their email."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_user(
        self,
        db: AsyncSession,
        full_name: str,
        email: str,
        password: str
    ) -> User:
        """Create a new user."""
        user = User(
            full_name=full_name,
            email=email.lower(),
            hashed_password=self.hash_password(password)
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    # ============ Refresh Token Database Methods ============

    async def store_refresh_token(
        self,
        db: AsyncSession,
        user_id: UUID,
        jti: str,
        expires_at: datetime
    ) -> RefreshToken:
        """Store a refresh token in the database."""
        token = RefreshToken(
            user_id=user_id,
            token_id=jti,
            expires_at=expires_at
        )
        db.add(token)
        await db.commit()
        return token

    async def get_refresh_token(
        self,
        db: AsyncSession,
        jti: str,
        user_id: UUID
    ) -> Optional[RefreshToken]:
        """Get a refresh token by jti and user_id."""
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_id == jti,
                RefreshToken.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, db: AsyncSession, jti: str) -> bool:
        """Revoke a refresh token by its jti."""
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_id == jti)
        )
        token = result.scalar_one_or_none()
        if token:
            token.revoked = True
            await db.commit()
            return True
        return False

    async def revoke_all_user_tokens(self, db: AsyncSession, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user."""
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False
            )
        )
        tokens = result.scalars().all()
        count = 0
        for token in tokens:
            token.revoked = True
            count += 1
        if count > 0:
            await db.commit()
        return count

    # ============ TOTP (2FA) Methods ============

    def generate_totp_secret(self) -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()

    def get_totp_uri(self, secret: str, email: str) -> str:
        """Get the TOTP provisioning URI for QR code generation."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=settings.APP_NAME)

    def verify_totp(self, secret: str, token: str) -> bool:
        """Verify a TOTP token against the secret."""
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=1)
        except Exception:
            return False


# Singleton instance
auth_service = AuthService()
