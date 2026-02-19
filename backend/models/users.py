import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from config.database import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, index=True, nullable=False)
    hashed_password = db.Column(db.String(255), nullable=False)
    totp_secret = db.Column(db.String(32), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.id})>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "full_name": self.full_name,
            "email": self.email,
            "is_active": self.is_active,
            "is_2fa_enabled": self.is_2fa_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_id = db.Column(db.String(64), unique=True, nullable=False, index=True)  # jti
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    revoked = db.Column(db.Boolean, default=False, index=True)

    def is_valid(self):
        from datetime import datetime, timezone
        return (not self.revoked) and (self.expires_at > datetime.now(timezone.utc))
