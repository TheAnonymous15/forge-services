# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Accounts Models (MVP1)
==========================================
User authentication, verification tokens, and related security models.
"""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid
import secrets


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        TALENT = "talent", _("Talent")
        EMPLOYER = "employer", _("Employer")
        ORG_ADMIN = "org_admin", _("Organization Admin")
        STAFF = "staff", _("Staff")
        ADMIN = "admin", _("Admin")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TALENT)

    # Status flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_2fa_enabled = models.BooleanField(default=False)

    # Consent tracking
    consent_privacy = models.BooleanField(default=False)
    consent_terms = models.BooleanField(default=False)
    consent_marketing = models.BooleanField(default=False)
    consented_at = models.DateTimeField(null=True, blank=True)

    # Settings
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    timezone = models.CharField(max_length=50, default='Africa/Johannesburg')
    language = models.CharField(max_length=10, default='en')

    # Security
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_password_change = models.DateTimeField(null=True, blank=True)

    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_users"
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_talent(self):
        return self.role == self.Role.TALENT

    @property
    def is_employer(self):
        return self.role in [self.Role.EMPLOYER, self.Role.ORG_ADMIN]

    @property
    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def increment_failed_login(self):
        """Increment failed login attempts and lock if threshold reached."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=['failed_login_attempts', 'locked_until'])

    def reset_failed_login(self):
        """Reset failed login attempts after successful login."""
        if self.failed_login_attempts > 0 or self.locked_until:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=['failed_login_attempts', 'locked_until'])


# =============================================================================
# EMAIL VERIFICATION TOKEN
# =============================================================================

class EmailVerificationToken(models.Model):
    """Token for email verification."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='verification_tokens'
    )
    token = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_email_verification_tokens"
        verbose_name = _("Email Verification Token")
        verbose_name_plural = _("Email Verification Tokens")

    def __str__(self):
        return f"Verification token for {self.user.email}"

    @classmethod
    def create_token(cls, user, expires_hours=24):
        """Create a new verification token for user."""
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timezone.timedelta(hours=expires_hours)
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )

    @property
    def is_valid(self):
        """Check if token is still valid."""
        return self.used_at is None and self.expires_at > timezone.now()

    def use(self):
        """Mark token as used."""
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])


# =============================================================================
# PASSWORD RESET TOKEN
# =============================================================================

class PasswordResetToken(models.Model):
    """Token for password reset."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "accounts_password_reset_tokens"
        verbose_name = _("Password Reset Token")
        verbose_name_plural = _("Password Reset Tokens")

    def __str__(self):
        return f"Password reset token for {self.user.email}"

    @classmethod
    def create_token(cls, user, ip_address=None, expires_hours=1):
        """Create a new password reset token."""
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timezone.timedelta(hours=expires_hours)
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address
        )

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def use(self):
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])


# =============================================================================
# TWO-FACTOR AUTHENTICATION
# =============================================================================

class TwoFactorDevice(models.Model):
    """TOTP device for two-factor authentication."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='two_factor_device'
    )
    secret_key = models.CharField(max_length=32)
    is_active = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list)  # Hashed backup codes

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_two_factor_devices"
        verbose_name = _("Two-Factor Device")
        verbose_name_plural = _("Two-Factor Devices")

    def __str__(self):
        return f"2FA device for {self.user.email}"


# =============================================================================
# LOGIN HISTORY / AUDIT
# =============================================================================

class LoginHistory(models.Model):
    """Track user login attempts."""

    class Status(models.TextChoices):
        SUCCESS = 'success', _('Success')
        FAILED = 'failed', _('Failed')
        LOCKED = 'locked', _('Account Locked')
        REQUIRES_2FA = '2fa', _('Requires 2FA')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_history',
        null=True,
        blank=True
    )
    email = models.EmailField()  # Store even if user doesn't exist
    status = models.CharField(max_length=20, choices=Status.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_login_history"
        verbose_name = _("Login History")
        verbose_name_plural = _("Login History")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        return f"{self.email} - {self.status} at {self.created_at}"
