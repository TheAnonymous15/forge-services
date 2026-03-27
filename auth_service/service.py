# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Core Logic
===========================================
Core authentication and authorization business logic.
"""
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import jwt
from werkzeug.security import generate_password_hash, check_password_hash

from .config import config
from .models import (
    User, EmailVerificationToken, PasswordResetToken,
    TwoFactorDevice, LoginHistory, UserSession, BlacklistedToken,
    get_session
)

logger = logging.getLogger('auth_service')


class AuthError(Exception):
    """Authentication/authorization error."""

    def __init__(self, message: str, code: str = 'auth_error', status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ValidationError(Exception):
    """Input validation error."""

    def __init__(self, message: str, field: str = None, status_code: int = 422):
        self.message = message
        self.field = field
        self.status_code = status_code
        super().__init__(message)


class AuthService:
    """
    Central Authentication & Authorization Service.

    This is the main service class that handles all auth operations.
    """

    # =========================================================================
    # TOKEN GENERATION
    # =========================================================================

    @staticmethod
    def _generate_access_token(user: User) -> str:
        """Generate JWT access token."""
        now = datetime.utcnow()
        payload = {
            'sub': user.id,
            'email': user.email,
            'role': user.role,
            'is_verified': user.is_verified,
            'type': 'access',
            'iat': now,
            'exp': now + config.JWT_ACCESS_TOKEN_EXPIRES,
            'jti': secrets.token_hex(16)
        }
        return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)

    @staticmethod
    def _generate_refresh_token(user: User, session: UserSession = None) -> str:
        """Generate JWT refresh token."""
        now = datetime.utcnow()
        jti = secrets.token_hex(16)

        payload = {
            'sub': user.id,
            'type': 'refresh',
            'iat': now,
            'exp': now + config.JWT_REFRESH_TOKEN_EXPIRES,
            'jti': jti
        }

        return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM), jti

    @staticmethod
    def _decode_token(token: str) -> Dict[str, Any]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(
                token,
                config.JWT_SECRET_KEY,
                algorithms=[config.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthError("Token has expired", code='token_expired', status_code=401)
        except jwt.InvalidTokenError as e:
            raise AuthError("Invalid token", code='invalid_token', status_code=401)

    # =========================================================================
    # PASSWORD VALIDATION
    # =========================================================================

    @staticmethod
    def _validate_password(password: str) -> None:
        """Validate password strength."""
        if len(password) < config.MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters",
                field='password'
            )

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)

        if not (has_upper and has_lower and has_digit):
            raise ValidationError(
                "Password must contain uppercase, lowercase, and numeric characters",
                field='password'
            )

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    @classmethod
    def register(
        cls,
        email: str,
        password: str,
        first_name: str = '',
        last_name: str = '',
        phone_number: str = '',
        role: str = 'talent',
        consent_privacy: bool = False,
        consent_terms: bool = False,
        consent_marketing: bool = False,
        ip_address: str = None,
        user_agent: str = ''
    ) -> Dict[str, Any]:
        """
        Register a new user.

        Returns dict with success, user data, and verification token.
        """
        db = get_session()

        try:
            # Validate email
            email = email.lower().strip()
            if not email:
                raise ValidationError("Email is required", field='email')

            # Check if email exists
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                raise ValidationError("An account with this email already exists", field='email')

            # Validate password
            cls._validate_password(password)

            # Validate role
            if role not in User.ROLES:
                raise ValidationError(f"Invalid role. Must be one of: {', '.join(User.ROLES)}", field='role')

            # Validate consent
            if not consent_privacy or not consent_terms:
                raise ValidationError("You must accept the privacy policy and terms of service")

            # Create user
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                role=role,
                consent_privacy=consent_privacy,
                consent_terms=consent_terms,
                consent_marketing=consent_marketing,
                consented_at=datetime.utcnow()
            )
            user.set_password(password)

            db.add(user)
            db.flush()  # Get user ID

            # Create verification token
            verification_token = EmailVerificationToken.create_token(
                user.id,
                expires_hours=config.VERIFICATION_TOKEN_HOURS
            )
            db.add(verification_token)

            db.commit()

            logger.info(f"User registered: {email} (role: {role}, ip: {ip_address})")

            return {
                'success': True,
                'message': 'Registration successful. Please verify your email.',
                'user': user.to_dict(),
                'verification_token': verification_token.token
            }

        except (ValidationError, AuthError):
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Registration failed for {email}: {e}")
            raise AuthError(f"Registration failed: {str(e)}", status_code=500)
        finally:
            db.close()

    # =========================================================================
    # LOGIN
    # =========================================================================

    @classmethod
    def login(
        cls,
        email: str,
        password: str,
        ip_address: str = None,
        user_agent: str = '',
        otp_code: str = None
    ) -> Dict[str, Any]:
        """
        Authenticate user and return tokens.
        """
        db = get_session()

        try:
            email = email.lower().strip()

            if not email or not password:
                cls._log_login(db, email=email, status=LoginHistory.STATUS_FAILED,
                              ip_address=ip_address, user_agent=user_agent,
                              failure_reason='Missing credentials')
                raise AuthError("Email and password are required", code='missing_credentials')

            # Find user
            user = db.query(User).filter(User.email == email).first()
            if not user:
                cls._log_login(db, email=email, status=LoginHistory.STATUS_FAILED,
                              ip_address=ip_address, user_agent=user_agent,
                              failure_reason='User not found')
                raise AuthError("Invalid email or password", code='invalid_credentials', status_code=401)

            # Check if locked
            if user.is_locked:
                remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
                cls._log_login(db, email=email, user_id=user.id, status=LoginHistory.STATUS_LOCKED,
                              ip_address=ip_address, user_agent=user_agent,
                              failure_reason='Account locked')
                raise AuthError(
                    f"Account is locked. Try again in {remaining} minutes.",
                    code='account_locked',
                    status_code=403
                )

            # Check if active
            if not user.is_active:
                cls._log_login(db, email=email, user_id=user.id, status=LoginHistory.STATUS_FAILED,
                              ip_address=ip_address, user_agent=user_agent,
                              failure_reason='Account inactive')
                raise AuthError("Account is deactivated", code='account_inactive', status_code=403)

            # Verify password
            if not user.check_password(password):
                user.increment_failed_login()
                db.commit()

                cls._log_login(db, email=email, user_id=user.id, status=LoginHistory.STATUS_FAILED,
                              ip_address=ip_address, user_agent=user_agent,
                              failure_reason='Invalid password')

                attempts_remaining = config.MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
                if attempts_remaining <= 0:
                    raise AuthError(
                        f"Account locked. Try again in {config.LOCKOUT_DURATION_MINUTES} minutes.",
                        code='account_locked',
                        status_code=403
                    )
                raise AuthError(
                    f"Invalid email or password. {attempts_remaining} attempts remaining.",
                    code='invalid_credentials',
                    status_code=401
                )

            # Check 2FA
            if user.is_2fa_enabled:
                if not otp_code:
                    cls._log_login(db, email=email, user_id=user.id, status=LoginHistory.STATUS_REQUIRES_2FA,
                                  ip_address=ip_address, user_agent=user_agent)
                    return {
                        'success': False,
                        'requires_2fa': True,
                        'message': 'Please enter your 2FA code'
                    }

                if not cls._verify_2fa(db, user, otp_code):
                    cls._log_login(db, email=email, user_id=user.id, status=LoginHistory.STATUS_FAILED,
                                  ip_address=ip_address, user_agent=user_agent,
                                  failure_reason='Invalid 2FA code')
                    raise AuthError("Invalid 2FA code", code='invalid_2fa', status_code=401)

            # Success - reset failed attempts
            user.reset_failed_login()
            user.last_login = datetime.utcnow()

            # Generate tokens
            access_token = cls._generate_access_token(user)
            refresh_token, jti = cls._generate_refresh_token(user)

            # Create session
            session = UserSession(
                user_id=user.id,
                refresh_token_jti=jti,
                device_info=user_agent[:500] if user_agent else '',
                ip_address=ip_address,
                expires_at=datetime.utcnow() + config.JWT_REFRESH_TOKEN_EXPIRES
            )
            db.add(session)

            # Log success
            cls._log_login(db, email=email, user_id=user.id, status=LoginHistory.STATUS_SUCCESS,
                          ip_address=ip_address, user_agent=user_agent)

            db.commit()

            logger.info(f"User logged in: {email} (ip: {ip_address})")

            result = {
                'success': True,
                'message': 'Login successful',
                'tokens': {
                    'access': access_token,
                    'refresh': refresh_token
                },
                'user': user.to_dict()
            }

            if not user.is_verified:
                result['warning'] = 'Please verify your email address'
                result['requires_verification'] = True

            return result

        except (ValidationError, AuthError):
            raise
        except Exception as e:
            logger.error(f"Login failed for {email}: {e}")
            raise AuthError(f"Login failed: {str(e)}", status_code=500)
        finally:
            db.close()

    # =========================================================================
    # LOGOUT
    # =========================================================================

    @classmethod
    def logout(cls, refresh_token: str) -> Dict[str, Any]:
        """Logout by blacklisting refresh token."""
        db = get_session()

        try:
            if refresh_token:
                payload = cls._decode_token(refresh_token)
                jti = payload.get('jti')
                user_id = payload.get('sub')
                exp = datetime.utcfromtimestamp(payload.get('exp'))

                # Blacklist token
                blacklisted = BlacklistedToken(
                    jti=jti,
                    token_type='refresh',
                    user_id=user_id,
                    expires_at=exp
                )
                db.add(blacklisted)

                # Revoke session
                session = db.query(UserSession).filter(
                    UserSession.refresh_token_jti == jti
                ).first()
                if session:
                    session.is_revoked = True

                db.commit()

                logger.info(f"User logged out (user_id: {user_id})")

            return {'success': True, 'message': 'Logout successful'}

        except AuthError:
            # Token already invalid, still count as logout
            return {'success': True, 'message': 'Logout successful'}
        except Exception as e:
            db.rollback()
            logger.error(f"Logout error: {e}")
            return {'success': True, 'message': 'Logout successful'}
        finally:
            db.close()

    # =========================================================================
    # TOKEN REFRESH
    # =========================================================================

    @classmethod
    def refresh_tokens(cls, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        db = get_session()

        try:
            payload = cls._decode_token(refresh_token)

            if payload.get('type') != 'refresh':
                raise AuthError("Invalid token type", code='invalid_token', status_code=401)

            jti = payload.get('jti')
            user_id = payload.get('sub')

            # Check if blacklisted
            blacklisted = db.query(BlacklistedToken).filter(
                BlacklistedToken.jti == jti
            ).first()
            if blacklisted:
                raise AuthError("Token has been revoked", code='token_revoked', status_code=401)

            # Check session
            session = db.query(UserSession).filter(
                UserSession.refresh_token_jti == jti
            ).first()
            if session and (session.is_revoked or not session.is_valid):
                raise AuthError("Session has been revoked", code='session_revoked', status_code=401)

            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                raise AuthError("User not found or inactive", code='user_inactive', status_code=401)

            # Generate new access token
            access_token = cls._generate_access_token(user)

            # Update session last active
            if session:
                session.last_active = datetime.utcnow()
                db.commit()

            return {
                'success': True,
                'access': access_token
            }

        except AuthError:
            raise
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise AuthError("Token refresh failed", status_code=500)
        finally:
            db.close()

    # =========================================================================
    # TOKEN VALIDATION
    # =========================================================================

    @classmethod
    def validate_token(cls, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """
        Validate a token and return user info.

        This endpoint is called by other services to validate tokens.
        """
        db = get_session()

        try:
            payload = cls._decode_token(token)

            if payload.get('type') != token_type:
                raise AuthError(f"Expected {token_type} token", code='invalid_token_type', status_code=401)

            jti = payload.get('jti')

            # Check if blacklisted
            blacklisted = db.query(BlacklistedToken).filter(
                BlacklistedToken.jti == jti
            ).first()
            if blacklisted:
                raise AuthError("Token has been revoked", code='token_revoked', status_code=401)

            user_id = payload.get('sub')
            user = db.query(User).filter(User.id == user_id).first()

            if not user:
                raise AuthError("User not found", code='user_not_found', status_code=401)

            if not user.is_active:
                raise AuthError("User is inactive", code='user_inactive', status_code=403)

            return {
                'valid': True,
                'user_id': user.id,
                'email': user.email,
                'role': user.role,
                'is_verified': user.is_verified,
                'permissions': cls.get_user_permissions(user)
            }

        except AuthError:
            raise
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            raise AuthError("Token validation failed", status_code=500)
        finally:
            db.close()

    # =========================================================================
    # EMAIL VERIFICATION
    # =========================================================================

    @classmethod
    def verify_email(cls, token: str) -> Dict[str, Any]:
        """Verify email using verification token."""
        db = get_session()

        try:
            token_obj = db.query(EmailVerificationToken).filter(
                EmailVerificationToken.token == token
            ).first()

            if not token_obj:
                raise AuthError("Invalid verification token", code='invalid_token')

            if not token_obj.is_valid:
                raise AuthError("Verification token has expired", code='token_expired')

            user = token_obj.user
            user.is_verified = True
            token_obj.use()

            db.commit()

            logger.info(f"Email verified: {user.email}")

            return {
                'success': True,
                'message': 'Email verified successfully',
                'user': user.to_dict()
            }

        except AuthError:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Email verification failed: {e}")
            raise AuthError("Verification failed", status_code=500)
        finally:
            db.close()

    @classmethod
    def resend_verification(cls, email: str) -> Dict[str, Any]:
        """Resend verification email."""
        db = get_session()

        try:
            email = email.lower().strip()
            user = db.query(User).filter(User.email == email).first()

            if not user:
                # Don't reveal if email exists
                return {
                    'success': True,
                    'message': 'If an account exists, a verification link has been sent.'
                }

            if user.is_verified:
                return {
                    'success': True,
                    'message': 'Email is already verified'
                }

            # Invalidate old tokens
            db.query(EmailVerificationToken).filter(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None)
            ).update({'used_at': datetime.utcnow()})

            # Create new token
            token = EmailVerificationToken.create_token(
                user.id,
                expires_hours=config.VERIFICATION_TOKEN_HOURS
            )
            db.add(token)
            db.commit()

            return {
                'success': True,
                'message': 'Verification email sent',
                'token': token.token  # In production, send via email
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Resend verification failed: {e}")
            raise AuthError("Failed to resend verification", status_code=500)
        finally:
            db.close()

    # =========================================================================
    # PASSWORD MANAGEMENT
    # =========================================================================

    @classmethod
    def forgot_password(cls, email: str, ip_address: str = None) -> Dict[str, Any]:
        """Initiate password reset."""
        db = get_session()

        try:
            email = email.lower().strip()
            user = db.query(User).filter(User.email == email).first()

            if not user:
                return {
                    'success': True,
                    'message': 'If an account exists, a password reset link has been sent.'
                }

            # Invalidate old tokens
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None)
            ).update({'used_at': datetime.utcnow()})

            # Create new token
            token = PasswordResetToken.create_token(
                user.id,
                ip_address=ip_address,
                expires_hours=config.PASSWORD_RESET_TOKEN_HOURS
            )
            db.add(token)
            db.commit()

            logger.info(f"Password reset requested: {email}")

            return {
                'success': True,
                'message': 'If an account exists, a password reset link has been sent.',
                'token': token.token  # In production, send via email
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Forgot password failed: {e}")
            raise AuthError("Failed to initiate password reset", status_code=500)
        finally:
            db.close()

    @classmethod
    def reset_password(cls, token: str, new_password: str) -> Dict[str, Any]:
        """Reset password using token."""
        db = get_session()

        try:
            token_obj = db.query(PasswordResetToken).filter(
                PasswordResetToken.token == token
            ).first()

            if not token_obj:
                raise AuthError("Invalid password reset token", code='invalid_token')

            if not token_obj.is_valid:
                raise AuthError("Password reset token has expired", code='token_expired')

            cls._validate_password(new_password)

            user = token_obj.user
            user.set_password(new_password)
            user.failed_login_attempts = 0
            user.locked_until = None
            token_obj.use()

            # Revoke all sessions (force re-login)
            db.query(UserSession).filter(
                UserSession.user_id == user.id
            ).update({'is_revoked': True})

            db.commit()

            logger.info(f"Password reset completed: {user.email}")

            return {
                'success': True,
                'message': 'Password reset successful. Please login with your new password.'
            }

        except (ValidationError, AuthError):
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Password reset failed: {e}")
            raise AuthError("Password reset failed", status_code=500)
        finally:
            db.close()

    @classmethod
    def change_password(
        cls,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> Dict[str, Any]:
        """Change password for authenticated user."""
        db = get_session()

        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise AuthError("User not found", status_code=404)

            if not user.check_password(current_password):
                raise AuthError("Current password is incorrect", code='invalid_password')

            cls._validate_password(new_password)

            if current_password == new_password:
                raise ValidationError("New password must be different from current password")

            user.set_password(new_password)
            db.commit()

            logger.info(f"Password changed: {user.email}")

            return {
                'success': True,
                'message': 'Password changed successfully'
            }

        except (ValidationError, AuthError):
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Password change failed: {e}")
            raise AuthError("Password change failed", status_code=500)
        finally:
            db.close()

    # =========================================================================
    # AUTHORIZATION
    # =========================================================================

    @classmethod
    def get_user_permissions(cls, user: User) -> List[str]:
        """Get user permissions based on role."""
        if user.role == User.ROLE_ADMIN or user.is_superuser:
            return ['*']

        role_permissions = {
            User.ROLE_TALENT: [
                'profile:read', 'profile:write',
                'applications:read', 'applications:write',
                'matches:read',
                'media:upload'
            ],
            User.ROLE_EMPLOYER: [
                'profile:read', 'profile:write',
                'jobs:read', 'jobs:write',
                'candidates:read',
                'applications:read',
                'org:read'
            ],
            User.ROLE_ORG_ADMIN: [
                'profile:read', 'profile:write',
                'jobs:read', 'jobs:write',
                'candidates:read',
                'applications:read',
                'org:read', 'org:write',
                'org:users:manage',
                'analytics:org:read'
            ],
            User.ROLE_STAFF: [
                'profiles:read:all',
                'applications:read:all',
                'analytics:read',
                'content:manage'
            ],
        }

        return role_permissions.get(user.role, [])

    @classmethod
    def check_permission(cls, user_id: str, permission: str) -> bool:
        """Check if user has a specific permission."""
        db = get_session()

        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            permissions = cls.get_user_permissions(user)
            return '*' in permissions or permission in permissions

        finally:
            db.close()

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _log_login(
        db,
        email: str,
        status: str,
        user_id: str = None,
        ip_address: str = None,
        user_agent: str = '',
        failure_reason: str = ''
    ):
        """Log login attempt."""
        try:
            log = LoginHistory(
                user_id=user_id,
                email=email,
                status=status,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else '',
                failure_reason=failure_reason
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log login attempt: {e}")

    @staticmethod
    def _verify_2fa(db, user: User, code: str) -> bool:
        """Verify 2FA code."""
        try:
            import pyotp

            device = db.query(TwoFactorDevice).filter(
                TwoFactorDevice.user_id == user.id,
                TwoFactorDevice.is_active == True
            ).first()

            if not device:
                return False

            # Try TOTP
            totp = pyotp.TOTP(device.secret_key)
            if totp.verify(code, valid_window=1):
                return True

            # Try backup codes
            for i, hashed_code in enumerate(device.backup_codes):
                if check_password_hash(hashed_code, code.upper()):
                    device.backup_codes.pop(i)
                    db.commit()
                    logger.info(f"Backup code used for: {user.email}")
                    return True

            return False

        except ImportError:
            logger.warning("pyotp not installed, 2FA disabled")
            return False
        except Exception as e:
            logger.error(f"2FA verification error: {e}")
            return False

