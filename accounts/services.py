# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Central Authentication & Authorization Service
===================================================================
A centralized service handling all authentication and authorization concerns:
- User registration (talent, employer, admin)
- Login/logout with JWT tokens
- Email verification
- Password management (forgot, reset, change)
- Two-factor authentication
- Session management
- Role-based access control
- Login auditing

All authentication flows pass through this service.
"""
import secrets
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import (
    User, EmailVerificationToken, PasswordResetToken,
    TwoFactorDevice, LoginHistory
)

logger = logging.getLogger('forgeforth.auth')


class AuthenticationError(Exception):
    """Base exception for authentication errors."""
    def __init__(self, message: str, code: str = 'auth_error'):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(Exception):
    """Validation error for input data."""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


class AuthService:
    """
    Central Authentication & Authorization Service

    This service is the single source of truth for all authentication
    and authorization operations in ForgeForth Africa.

    Usage:
        from accounts.services import AuthService

        # Register a new user
        result = AuthService.register(
            email='user@example.com',
            password='SecureP@ss123',
            first_name='John',
            last_name='Doe',
            role='talent'
        )

        # Login
        result = AuthService.login(
            email='user@example.com',
            password='SecureP@ss123',
            ip_address='127.0.0.1'
        )
    """

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    VERIFICATION_TOKEN_HOURS = 24
    PASSWORD_RESET_TOKEN_HOURS = 1
    MIN_PASSWORD_LENGTH = 8

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    @classmethod
    @transaction.atomic
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
        send_verification: bool = True,
        ip_address: str = None,
        user_agent: str = ''
    ) -> Dict[str, Any]:
        """
        Register a new user account.

        Args:
            email: User's email address
            password: User's password (will be validated and hashed)
            first_name: User's first name
            last_name: User's last name
            phone_number: User's phone number
            role: User role ('talent', 'employer', 'org_admin', 'staff', 'admin')
            consent_privacy: Privacy policy consent
            consent_terms: Terms of service consent
            consent_marketing: Marketing communications consent
            send_verification: Whether to send verification email
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit

        Returns:
            Dict with 'success', 'user', 'message', and optionally 'verification_token'

        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If registration fails
        """
        # Validate email
        email = email.lower().strip()
        if not email:
            raise ValidationError("Email is required", field='email')

        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists", field='email')

        # Validate password
        cls._validate_password(password)

        # Validate role
        valid_roles = [choice[0] for choice in User.Role.choices]
        if role not in valid_roles:
            raise ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}", field='role')

        # Validate consent
        if not consent_privacy or not consent_terms:
            raise ValidationError("You must accept the privacy policy and terms of service")

        try:
            # Create user
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                role=role,
                consent_privacy=consent_privacy,
                consent_terms=consent_terms,
                consent_marketing=consent_marketing,
                consented_at=timezone.now()
            )

            result = {
                'success': True,
                'user': user,
                'message': 'Registration successful. Please verify your email.'
            }

            # Create and send verification token
            if send_verification:
                token = EmailVerificationToken.create_token(user, expires_hours=cls.VERIFICATION_TOKEN_HOURS)
                result['verification_token'] = token.token

                # Send verification email (async in production)
                try:
                    cls._send_verification_email(user, token.token)
                except Exception as e:
                    logger.warning(f"Failed to send verification email to {email}: {e}")

            logger.info(f"New user registered: {email} (role: {role}, ip: {ip_address})")

            return result

        except Exception as e:
            logger.error(f"Registration failed for {email}: {e}")
            raise AuthenticationError(f"Registration failed: {str(e)}")

    # =========================================================================
    # LOGIN / LOGOUT
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
        Authenticate user and generate JWT tokens.

        Args:
            email: User's email address
            password: User's password
            ip_address: Client IP for audit logging
            user_agent: Client user agent for audit
            otp_code: 2FA code if enabled

        Returns:
            Dict with 'success', 'tokens' (access, refresh), 'user', and optional flags

        Raises:
            AuthenticationError: If authentication fails
        """
        email = email.lower().strip()

        if not email or not password:
            cls._log_login_attempt(email=email, status=LoginHistory.Status.FAILED,
                                   ip_address=ip_address, user_agent=user_agent,
                                   failure_reason='Missing credentials')
            raise AuthenticationError("Email and password are required", code='missing_credentials')

        # Find user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            cls._log_login_attempt(email=email, status=LoginHistory.Status.FAILED,
                                   ip_address=ip_address, user_agent=user_agent,
                                   failure_reason='User not found')
            raise AuthenticationError("Invalid email or password", code='invalid_credentials')

        # Check if account is locked
        if user.is_locked:
            cls._log_login_attempt(user=user, email=email, status=LoginHistory.Status.LOCKED,
                                   ip_address=ip_address, user_agent=user_agent,
                                   failure_reason='Account locked')
            remaining = (user.locked_until - timezone.now()).seconds // 60
            raise AuthenticationError(
                f"Account is locked. Try again in {remaining} minutes.",
                code='account_locked'
            )

        # Check if account is active
        if not user.is_active:
            cls._log_login_attempt(user=user, email=email, status=LoginHistory.Status.FAILED,
                                   ip_address=ip_address, user_agent=user_agent,
                                   failure_reason='Account inactive')
            raise AuthenticationError("Account is deactivated", code='account_inactive')

        # Verify password
        if not user.check_password(password):
            user.increment_failed_login()
            cls._log_login_attempt(user=user, email=email, status=LoginHistory.Status.FAILED,
                                   ip_address=ip_address, user_agent=user_agent,
                                   failure_reason='Invalid password')

            attempts_remaining = cls.MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
            if attempts_remaining <= 0:
                raise AuthenticationError(
                    f"Account locked due to too many failed attempts. Try again in {cls.LOCKOUT_DURATION_MINUTES} minutes.",
                    code='account_locked'
                )
            raise AuthenticationError(
                f"Invalid email or password. {attempts_remaining} attempts remaining.",
                code='invalid_credentials'
            )

        # Check 2FA if enabled
        if user.is_2fa_enabled:
            if not otp_code:
                cls._log_login_attempt(user=user, email=email, status=LoginHistory.Status.REQUIRES_2FA,
                                       ip_address=ip_address, user_agent=user_agent)
                return {
                    'success': False,
                    'requires_2fa': True,
                    'message': 'Please enter your 2FA code'
                }

            # Verify 2FA code
            if not cls._verify_2fa_code(user, otp_code):
                cls._log_login_attempt(user=user, email=email, status=LoginHistory.Status.FAILED,
                                       ip_address=ip_address, user_agent=user_agent,
                                       failure_reason='Invalid 2FA code')
                raise AuthenticationError("Invalid 2FA code", code='invalid_2fa')

        # Successful login
        user.reset_failed_login()
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Generate tokens
        tokens = cls._generate_tokens(user)

        # Log successful login
        cls._log_login_attempt(user=user, email=email, status=LoginHistory.Status.SUCCESS,
                               ip_address=ip_address, user_agent=user_agent)

        logger.info(f"User logged in: {email} (role: {user.role}, ip: {ip_address})")

        result = {
            'success': True,
            'tokens': tokens,
            'user': user,
            'message': 'Login successful'
        }

        # Add warning if email not verified
        if not user.is_verified:
            result['warning'] = 'Please verify your email address'
            result['requires_verification'] = True

        return result

    @classmethod
    def logout(cls, refresh_token: str, user: User = None) -> Dict[str, Any]:
        """
        Logout user by blacklisting their refresh token.

        Args:
            refresh_token: The refresh token to blacklist
            user: Optional user object for logging

        Returns:
            Dict with 'success' and 'message'
        """
        try:
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            if user:
                logger.info(f"User logged out: {user.email}")

            return {
                'success': True,
                'message': 'Logout successful'
            }
        except TokenError:
            # Token already blacklisted or invalid
            return {
                'success': True,
                'message': 'Logout successful'
            }

    @classmethod
    def refresh_token(cls, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            Dict with new 'access' token

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            token = RefreshToken(refresh_token)
            return {
                'success': True,
                'access': str(token.access_token)
            }
        except TokenError as e:
            raise AuthenticationError("Invalid or expired refresh token", code='invalid_token')

    # =========================================================================
    # EMAIL VERIFICATION
    # =========================================================================

    @classmethod
    def verify_email(cls, token: str) -> Dict[str, Any]:
        """
        Verify user email address using verification token.

        Args:
            token: The verification token

        Returns:
            Dict with 'success', 'user', and 'message'

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            token_obj = EmailVerificationToken.objects.get(token=token)
        except EmailVerificationToken.DoesNotExist:
            raise AuthenticationError("Invalid verification token", code='invalid_token')

        if not token_obj.is_valid:
            raise AuthenticationError("Verification token has expired", code='token_expired')

        user = token_obj.user
        user.is_verified = True
        user.save(update_fields=['is_verified'])

        token_obj.use()

        logger.info(f"Email verified: {user.email}")

        return {
            'success': True,
            'user': user,
            'message': 'Email verified successfully'
        }

    @classmethod
    def resend_verification(cls, email: str) -> Dict[str, Any]:
        """
        Resend verification email.

        Args:
            email: User's email address

        Returns:
            Dict with 'success' and 'message'
        """
        email = email.lower().strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists
            return {
                'success': True,
                'message': 'If an account exists with this email, a verification link has been sent.'
            }

        if user.is_verified:
            return {
                'success': True,
                'message': 'Email is already verified'
            }

        # Invalidate old tokens
        EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )

        # Create new token
        token = EmailVerificationToken.create_token(user, expires_hours=cls.VERIFICATION_TOKEN_HOURS)

        try:
            cls._send_verification_email(user, token.token)
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")

        return {
            'success': True,
            'message': 'Verification email sent'
        }

    # =========================================================================
    # PASSWORD MANAGEMENT
    # =========================================================================

    @classmethod
    def forgot_password(cls, email: str, ip_address: str = None) -> Dict[str, Any]:
        """
        Initiate password reset process.

        Args:
            email: User's email address
            ip_address: Client IP for security

        Returns:
            Dict with 'success' and 'message'
        """
        email = email.lower().strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists
            return {
                'success': True,
                'message': 'If an account exists with this email, a password reset link has been sent.'
            }

        # Invalidate old tokens
        PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )

        # Create new token
        token = PasswordResetToken.create_token(
            user,
            ip_address=ip_address,
            expires_hours=cls.PASSWORD_RESET_TOKEN_HOURS
        )

        try:
            cls._send_password_reset_email(user, token.token)
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")

        logger.info(f"Password reset requested for: {email}")

        return {
            'success': True,
            'message': 'If an account exists with this email, a password reset link has been sent.'
        }

    @classmethod
    def reset_password(cls, token: str, new_password: str) -> Dict[str, Any]:
        """
        Reset password using reset token.

        Args:
            token: The password reset token
            new_password: The new password

        Returns:
            Dict with 'success' and 'message'

        Raises:
            AuthenticationError: If token is invalid
            ValidationError: If password is invalid
        """
        try:
            token_obj = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            raise AuthenticationError("Invalid password reset token", code='invalid_token')

        if not token_obj.is_valid:
            raise AuthenticationError("Password reset token has expired", code='token_expired')

        # Validate new password
        cls._validate_password(new_password)

        user = token_obj.user
        user.set_password(new_password)
        user.last_password_change = timezone.now()
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=['password', 'last_password_change', 'failed_login_attempts', 'locked_until'])

        token_obj.use()

        # Invalidate all refresh tokens (force re-login)
        # Note: This requires token blacklisting to be enabled

        logger.info(f"Password reset completed for: {user.email}")

        return {
            'success': True,
            'message': 'Password reset successful. Please login with your new password.'
        }

    @classmethod
    def change_password(
        cls,
        user: User,
        current_password: str,
        new_password: str
    ) -> Dict[str, Any]:
        """
        Change password for authenticated user.

        Args:
            user: The authenticated user
            current_password: Current password
            new_password: New password

        Returns:
            Dict with 'success' and 'message'

        Raises:
            AuthenticationError: If current password is wrong
            ValidationError: If new password is invalid
        """
        if not user.check_password(current_password):
            raise AuthenticationError("Current password is incorrect", code='invalid_password')

        cls._validate_password(new_password)

        if current_password == new_password:
            raise ValidationError("New password must be different from current password")

        user.set_password(new_password)
        user.last_password_change = timezone.now()
        user.save(update_fields=['password', 'last_password_change'])

        logger.info(f"Password changed for: {user.email}")

        return {
            'success': True,
            'message': 'Password changed successfully'
        }

    # =========================================================================
    # TWO-FACTOR AUTHENTICATION
    # =========================================================================

    @classmethod
    def setup_2fa(cls, user: User) -> Dict[str, Any]:
        """
        Initialize 2FA setup for user.

        Returns:
            Dict with 'secret_key', 'qr_code_url', and 'backup_codes'
        """
        import pyotp
        import base64

        # Generate secret key
        secret = pyotp.random_base32()

        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        hashed_backups = [make_password(code) for code in backup_codes]

        # Create or update 2FA device
        device, created = TwoFactorDevice.objects.update_or_create(
            user=user,
            defaults={
                'secret_key': secret,
                'is_active': False,
                'backup_codes': hashed_backups
            }
        )

        # Generate provisioning URI for QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name='ForgeForth Africa'
        )

        return {
            'success': True,
            'secret_key': secret,
            'provisioning_uri': provisioning_uri,
            'backup_codes': backup_codes  # Show only once
        }

    @classmethod
    def confirm_2fa(cls, user: User, otp_code: str) -> Dict[str, Any]:
        """
        Confirm and activate 2FA setup.

        Args:
            user: The user enabling 2FA
            otp_code: The OTP code to verify

        Returns:
            Dict with 'success' and 'message'
        """
        try:
            device = TwoFactorDevice.objects.get(user=user)
        except TwoFactorDevice.DoesNotExist:
            raise AuthenticationError("2FA not set up. Please initiate setup first.", code='2fa_not_setup')

        if not cls._verify_2fa_code(user, otp_code):
            raise AuthenticationError("Invalid OTP code", code='invalid_otp')

        device.is_active = True
        device.confirmed_at = timezone.now()
        device.save(update_fields=['is_active', 'confirmed_at'])

        user.is_2fa_enabled = True
        user.save(update_fields=['is_2fa_enabled'])

        logger.info(f"2FA enabled for: {user.email}")

        return {
            'success': True,
            'message': 'Two-factor authentication enabled successfully'
        }

    @classmethod
    def disable_2fa(cls, user: User, password: str) -> Dict[str, Any]:
        """
        Disable 2FA for user.

        Args:
            user: The user
            password: User's password for confirmation

        Returns:
            Dict with 'success' and 'message'
        """
        if not user.check_password(password):
            raise AuthenticationError("Invalid password", code='invalid_password')

        TwoFactorDevice.objects.filter(user=user).delete()

        user.is_2fa_enabled = False
        user.save(update_fields=['is_2fa_enabled'])

        logger.info(f"2FA disabled for: {user.email}")

        return {
            'success': True,
            'message': 'Two-factor authentication disabled'
        }

    # =========================================================================
    # AUTHORIZATION HELPERS
    # =========================================================================

    @classmethod
    def check_permission(cls, user: User, permission: str) -> bool:
        """
        Check if user has a specific permission.

        Args:
            user: The user to check
            permission: Permission string (e.g., 'can_edit_profile')

        Returns:
            True if user has permission, False otherwise
        """
        # Admin has all permissions
        if user.role == User.Role.ADMIN or user.is_superuser:
            return True

        # Define role-based permissions
        role_permissions = {
            User.Role.TALENT: [
                'view_own_profile', 'edit_own_profile', 'apply_to_jobs',
                'view_applications', 'view_matches', 'upload_media'
            ],
            User.Role.EMPLOYER: [
                'view_own_profile', 'edit_own_profile', 'post_jobs',
                'view_candidates', 'view_applications', 'manage_org'
            ],
            User.Role.ORG_ADMIN: [
                'view_own_profile', 'edit_own_profile', 'post_jobs',
                'view_candidates', 'view_applications', 'manage_org',
                'manage_org_users', 'view_org_analytics'
            ],
            User.Role.STAFF: [
                'view_all_profiles', 'view_all_applications',
                'view_analytics', 'manage_content'
            ],
        }

        return permission in role_permissions.get(user.role, [])

    @classmethod
    def get_user_permissions(cls, user: User) -> list:
        """Get all permissions for a user based on their role."""
        if user.role == User.Role.ADMIN or user.is_superuser:
            return ['*']  # All permissions

        role_permissions = {
            User.Role.TALENT: [
                'view_own_profile', 'edit_own_profile', 'apply_to_jobs',
                'view_applications', 'view_matches', 'upload_media'
            ],
            User.Role.EMPLOYER: [
                'view_own_profile', 'edit_own_profile', 'post_jobs',
                'view_candidates', 'view_applications', 'manage_org'
            ],
            User.Role.ORG_ADMIN: [
                'view_own_profile', 'edit_own_profile', 'post_jobs',
                'view_candidates', 'view_applications', 'manage_org',
                'manage_org_users', 'view_org_analytics'
            ],
            User.Role.STAFF: [
                'view_all_profiles', 'view_all_applications',
                'view_analytics', 'manage_content'
            ],
        }

        return role_permissions.get(user.role, [])

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    @classmethod
    def _validate_password(cls, password: str) -> None:
        """Validate password strength."""
        if len(password) < cls.MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"Password must be at least {cls.MIN_PASSWORD_LENGTH} characters",
                field='password'
            )

        # Check for at least one uppercase, lowercase, digit
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)

        if not (has_upper and has_lower and has_digit):
            raise ValidationError(
                "Password must contain uppercase, lowercase, and numeric characters",
                field='password'
            )

    @classmethod
    def _generate_tokens(cls, user: User) -> Dict[str, str]:
        """Generate JWT tokens for user."""
        refresh = RefreshToken.for_user(user)

        # Add custom claims
        refresh['role'] = user.role
        refresh['email'] = user.email
        refresh['is_verified'] = user.is_verified

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }

    @classmethod
    def _verify_2fa_code(cls, user: User, code: str) -> bool:
        """Verify 2FA OTP code or backup code."""
        try:
            device = TwoFactorDevice.objects.get(user=user, is_active=True)
        except TwoFactorDevice.DoesNotExist:
            return False

        import pyotp

        # Try TOTP first
        totp = pyotp.TOTP(device.secret_key)
        if totp.verify(code, valid_window=1):
            return True

        # Try backup codes
        for i, hashed_code in enumerate(device.backup_codes):
            if check_password(code.upper(), hashed_code):
                # Remove used backup code
                device.backup_codes.pop(i)
                device.save(update_fields=['backup_codes'])
                logger.info(f"Backup code used for: {user.email}")
                return True

        return False

    @classmethod
    def _log_login_attempt(
        cls,
        email: str,
        status: str,
        ip_address: str = None,
        user_agent: str = '',
        user: User = None,
        failure_reason: str = ''
    ) -> None:
        """Log login attempt for audit."""
        LoginHistory.objects.create(
            user=user,
            email=email,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else '',
            failure_reason=failure_reason
        )

    @classmethod
    def _send_verification_email(cls, user: User, token: str) -> None:
        """Send verification email to user."""
        try:
            from communications.services import EmailService
            EmailService.send_verification_email(user, token)
        except ImportError:
            logger.warning("EmailService not available, skipping verification email")

    @classmethod
    def _send_password_reset_email(cls, user: User, token: str) -> None:
        """Send password reset email to user."""
        try:
            from communications.services import EmailService
            EmailService.send_password_reset_email(user, token)
        except ImportError:
            logger.warning("EmailService not available, skipping password reset email")


# =============================================================================
# DECORATORS FOR VIEW PROTECTION
# =============================================================================

def require_role(*roles):
    """
    Decorator to require specific user roles.

    Usage:
        @require_role('admin', 'staff')
        def admin_view(request):
            ...
    """
    def decorator(view_func):
        from functools import wraps

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.http import JsonResponse
                return JsonResponse({'error': 'Authentication required'}, status=401)

            if request.user.role not in roles and not request.user.is_superuser:
                from django.http import JsonResponse
                return JsonResponse({'error': 'Permission denied'}, status=403)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def require_permission(permission):
    """
    Decorator to require specific permission.

    Usage:
        @require_permission('manage_org')
        def org_settings_view(request):
            ...
    """
    def decorator(view_func):
        from functools import wraps

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.http import JsonResponse
                return JsonResponse({'error': 'Authentication required'}, status=401)

            if not AuthService.check_permission(request.user, permission):
                from django.http import JsonResponse
                return JsonResponse({'error': 'Permission denied'}, status=403)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def require_verified_email(view_func):
    """
    Decorator to require verified email.

    Usage:
        @require_verified_email
        def sensitive_view(request):
            ...
    """
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'Authentication required'}, status=401)

        if not request.user.is_verified:
            from django.http import JsonResponse
            return JsonResponse({'error': 'Email verification required'}, status=403)

        return view_func(request, *args, **kwargs)

    return wrapper

