# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Security Models (MVP1)
==========================================
Security & Compliance Layer.
API keys, rate limit violations, POPIA consent records, security events.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid
import secrets


class APIKey(models.Model):
    """
    API key for machine-to-machine access (partner integrations, mobile app).
    """

    class Status(models.TextChoices):
        ACTIVE   = 'active',   _('Active')
        REVOKED  = 'revoked',  _('Revoked')
        EXPIRED  = 'expired',  _('Expired')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys'
    )
    name         = models.CharField(max_length=100, help_text='Descriptive name for this key')
    key_prefix   = models.CharField(max_length=10, db_index=True)   # First 8 chars — shown in UI
    key_hash     = models.CharField(max_length=128, unique=True)     # SHA-256 of the full key
    status       = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    scopes       = models.JSONField(default=list, blank=True)        # e.g. ['read:profiles', 'write:applications']
    allowed_ips  = models.JSONField(default=list, blank=True)        # IP allowlist (empty = any)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    revoked_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'security'
        db_table  = 'security_api_keys'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…) [{self.status}]"

    @classmethod
    def generate(cls, owner, name, scopes=None, expires_days=None):
        """Generate a new API key and return (instance, raw_key)."""
        import hashlib
        from django.utils import timezone
        raw_key = secrets.token_urlsafe(40)
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        expires_at = (timezone.now() + timezone.timedelta(days=expires_days)) if expires_days else None
        instance = cls.objects.create(
            owner=owner,
            name=name,
            key_prefix=raw_key[:8],
            key_hash=hashed,
            scopes=scopes or [],
            expires_at=expires_at,
        )
        return instance, raw_key


class SecurityEvent(models.Model):
    """
    Security-related events: brute-force attempts, suspicious activity, policy violations.
    """

    class Severity(models.TextChoices):
        INFO     = 'info',     _('Info')
        LOW      = 'low',      _('Low')
        MEDIUM   = 'medium',   _('Medium')
        HIGH     = 'high',     _('High')
        CRITICAL = 'critical', _('Critical')

    class EventType(models.TextChoices):
        BRUTE_FORCE      = 'brute_force',      _('Brute-Force Login Attempt')
        ACCOUNT_LOCKED   = 'account_locked',   _('Account Locked')
        SUSPICIOUS_IP    = 'suspicious_ip',    _('Suspicious IP Activity')
        TOKEN_ABUSE      = 'token_abuse',      _('Token / API Key Abuse')
        CSRF_VIOLATION   = 'csrf',             _('CSRF Violation')
        XSS_ATTEMPT      = 'xss',              _('XSS Attempt')
        SQL_INJECTION    = 'sqli',             _('SQL Injection Attempt')
        RATE_LIMIT       = 'rate_limit',       _('Rate Limit Exceeded')
        DATA_EXPORT      = 'data_export',      _('Bulk Data Export')
        PRIVILEGE_ESCALATION = 'priv_esc',     _('Privilege Escalation Attempt')
        UNUSUAL_ACCESS   = 'unusual_access',   _('Unusual Access Pattern')
        OTHER            = 'other',            _('Other')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='security_events'
    )
    event_type   = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    severity     = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM, db_index=True)
    description  = models.TextField()
    ip_address   = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent   = models.TextField(blank=True)
    request_path = models.CharField(max_length=512, blank=True)
    extra_data   = models.JSONField(default=dict, blank=True)
    is_resolved  = models.BooleanField(default=False, db_index=True)
    resolved_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_security_events'
    )
    resolved_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'security'
        db_table  = 'security_events'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['event_type', 'severity', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.event_type} at {self.created_at}"


class ConsentRecord(models.Model):
    """
    POPIA / GDPR consent record — immutable append-only log.
    Records every consent grant or withdrawal per user per purpose.
    """

    class Purpose(models.TextChoices):
        PRIVACY_POLICY     = 'privacy_policy',     _('Privacy Policy')
        TERMS_OF_SERVICE   = 'terms_of_service',   _('Terms of Service')
        COOKIE_POLICY      = 'cookie_policy',      _('Cookie Policy')
        MARKETING_EMAIL    = 'marketing_email',     _('Marketing Emails')
        DATA_PROCESSING    = 'data_processing',    _('Data Processing')
        DATA_SHARING       = 'data_sharing',       _('Data Sharing with Partners')
        PROFILING          = 'profiling',          _('AI Profiling & Matching')
        ANALYTICS          = 'analytics',          _('Analytics & Usage Tracking')

    class Action(models.TextChoices):
        GRANTED   = 'granted',   _('Consent Granted')
        WITHDRAWN = 'withdrawn', _('Consent Withdrawn')
        UPDATED   = 'updated',   _('Consent Updated')

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='consent_records'
    )
    purpose       = models.CharField(max_length=30, choices=Purpose.choices, db_index=True)
    action        = models.CharField(max_length=15, choices=Action.choices)
    version       = models.CharField(max_length=20, default='1.0')   # policy version

    # Context at time of consent
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    user_agent    = models.TextField(blank=True)
    source        = models.CharField(max_length=100, blank=True)      # registration, settings, etc.
    raw_request   = models.JSONField(default=dict, blank=True)        # full request metadata

    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'security'
        db_table  = 'security_consent_records'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['user', 'purpose', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user} {self.action} {self.purpose} (v{self.version})"


class BlockedIP(models.Model):
    """
    IP addresses blocked from accessing the platform.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address  = models.GenericIPAddressField(unique=True, db_index=True)
    reason      = models.CharField(max_length=255)
    is_active   = models.BooleanField(default=True, db_index=True)
    blocked_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    expires_at  = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'security'
        db_table  = 'security_blocked_ips'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.ip_address} blocked: {self.reason}"
