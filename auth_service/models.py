# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Database Models
================================================
Database models for the authentication microservice.
These mirror the accounts app models but are self-contained.
"""
import uuid
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text,
    ForeignKey, Index, JSON, create_engine
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

from .config import config

Base = declarative_base()


class User(Base):
    """User model for authentication."""

    __tablename__ = 'auth_users'

    # Roles
    ROLE_TALENT = 'talent'
    ROLE_EMPLOYER = 'employer'
    ROLE_ORG_ADMIN = 'org_admin'
    ROLE_STAFF = 'staff'
    ROLE_ADMIN = 'admin'

    ROLES = [ROLE_TALENT, ROLE_EMPLOYER, ROLE_ORG_ADMIN, ROLE_STAFF, ROLE_ADMIN]

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    first_name = Column(String(150), default='')
    last_name = Column(String(150), default='')
    phone_number = Column(String(20), default='')

    role = Column(String(20), default=ROLE_TALENT, index=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_staff = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    is_2fa_enabled = Column(Boolean, default=False)

    # Consent
    consent_privacy = Column(Boolean, default=False)
    consent_terms = Column(Boolean, default=False)
    consent_marketing = Column(Boolean, default=False)
    consented_at = Column(DateTime, nullable=True)

    # Settings
    email_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=False)
    timezone = Column(String(50), default='Africa/Johannesburg')
    language = Column(String(10), default='en')

    # Security
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_password_change = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    verification_tokens = relationship('EmailVerificationToken', back_populates='user', cascade='all, delete-orphan')
    password_reset_tokens = relationship('PasswordResetToken', back_populates='user', cascade='all, delete-orphan')
    two_factor_device = relationship('TwoFactorDevice', back_populates='user', uselist=False, cascade='all, delete-orphan')
    login_history = relationship('LoginHistory', back_populates='user', cascade='all, delete-orphan')
    sessions = relationship('UserSession', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password: str):
        """Hash and set the password."""
        self.password_hash = generate_password_hash(password)
        self.last_password_change = datetime.utcnow()

    def check_password(self, password: str) -> bool:
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_locked(self) -> bool:
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def increment_failed_login(self):
        """Increment failed login attempts."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= config.MAX_LOGIN_ATTEMPTS:
            self.locked_until = datetime.utcnow() + timedelta(minutes=config.LOCKOUT_DURATION_MINUTES)

    def reset_failed_login(self):
        """Reset failed login counter."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone_number': self.phone_number,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'is_2fa_enabled': self.is_2fa_enabled,
            'timezone': self.timezone,
            'language': self.language,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }

        if include_sensitive:
            data.update({
                'is_staff': self.is_staff,
                'is_superuser': self.is_superuser,
                'failed_login_attempts': self.failed_login_attempts,
                'is_locked': self.is_locked,
            })

        return data


class EmailVerificationToken(Base):
    """Email verification token model."""

    __tablename__ = 'auth_email_verification_tokens'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('auth_users.id', ondelete='CASCADE'), nullable=False)
    token = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship('User', back_populates='verification_tokens')

    @classmethod
    def create_token(cls, user_id: str, expires_hours: int = 24) -> 'EmailVerificationToken':
        """Create a new verification token."""
        return cls(
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours)
        )

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.utcnow()

    def use(self):
        """Mark token as used."""
        self.used_at = datetime.utcnow()


class PasswordResetToken(Base):
    """Password reset token model."""

    __tablename__ = 'auth_password_reset_tokens'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('auth_users.id', ondelete='CASCADE'), nullable=False)
    token = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)

    user = relationship('User', back_populates='password_reset_tokens')

    @classmethod
    def create_token(cls, user_id: str, ip_address: str = None, expires_hours: int = 1) -> 'PasswordResetToken':
        """Create a new password reset token."""
        return cls(
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
            ip_address=ip_address
        )

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.utcnow()

    def use(self):
        self.used_at = datetime.utcnow()


class TwoFactorDevice(Base):
    """Two-factor authentication device."""

    __tablename__ = 'auth_two_factor_devices'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('auth_users.id', ondelete='CASCADE'), unique=True, nullable=False)
    secret_key = Column(String(32), nullable=False)
    is_active = Column(Boolean, default=False)
    backup_codes = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    user = relationship('User', back_populates='two_factor_device')


class LoginHistory(Base):
    """Login attempt history for audit."""

    __tablename__ = 'auth_login_history'

    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_LOCKED = 'locked'
    STATUS_REQUIRES_2FA = '2fa'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('auth_users.id', ondelete='SET NULL'), nullable=True)
    email = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, default='')
    failure_reason = Column(String(255), default='')
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship('User', back_populates='login_history')

    __table_args__ = (
        Index('ix_login_history_user_created', 'user_id', 'created_at'),
        Index('ix_login_history_ip_created', 'ip_address', 'created_at'),
    )


class UserSession(Base):
    """Active user sessions (for session management)."""

    __tablename__ = 'auth_user_sessions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('auth_users.id', ondelete='CASCADE'), nullable=False, index=True)
    refresh_token_jti = Column(String(255), unique=True, nullable=False, index=True)  # JWT ID
    device_info = Column(Text, default='')
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)

    user = relationship('User', back_populates='sessions')

    @property
    def is_valid(self) -> bool:
        return not self.is_revoked and self.expires_at > datetime.utcnow()


class BlacklistedToken(Base):
    """Blacklisted JWT tokens."""

    __tablename__ = 'auth_blacklisted_tokens'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    jti = Column(String(255), unique=True, nullable=False, index=True)  # JWT ID
    token_type = Column(String(20), default='refresh')  # 'access' or 'refresh'
    user_id = Column(String(36), nullable=True)
    blacklisted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # Keep until token would have expired anyway


# Database setup
def get_engine():
    """Create database engine."""
    db_url = config.DATABASE_URL

    # Handle SQLite specially
    if db_url.startswith('sqlite'):
        return create_engine(db_url, connect_args={'check_same_thread': False})

    return create_engine(db_url, pool_pre_ping=True, pool_size=10, max_overflow=20)


def init_db():
    """Initialize database tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session():
    """Get database session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

