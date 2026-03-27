# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Administration Models (MVP1)
================================================
Platform governance: staff roles, feature flags, audit trails, support tickets.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class StaffRole(models.Model):
    """
    Fine-grained role definition for platform staff beyond Django's built-in groups.
    """

    class Scope(models.TextChoices):
        PLATFORM  = 'platform',  _('Platform-Wide')
        TALENT    = 'talent',    _('Talent Operations')
        EMPLOYER  = 'employer',  _('Employer Operations')
        CONTENT   = 'content',   _('Content & Blog')
        ANALYTICS = 'analytics', _('Analytics & Reporting')
        TECHNICAL = 'technical', _('Technical / DevOps')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    scope       = models.CharField(max_length=20, choices=Scope.choices, default=Scope.PLATFORM)
    permissions = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'administration'
        db_table  = 'admin_staff_roles'
        ordering  = ['name']

    def __str__(self):
        return f"{self.name} ({self.scope})"


class StaffRoleAssignment(models.Model):
    """Assigns a StaffRole to a platform user."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_roles'
    )
    role       = models.ForeignKey(StaffRole, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='staff_role_grants'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'administration'
        db_table  = 'admin_role_assignments'
        unique_together = [['user', 'role']]

    def __str__(self):
        return f"{self.user} → {self.role}"


class FeatureFlag(models.Model):
    """
    Runtime feature flags — toggle platform features without redeploying.
    """

    class Rollout(models.TextChoices):
        ALL          = 'all',          _('All Users')
        STAFF_ONLY   = 'staff',        _('Staff Only')
        BETA_USERS   = 'beta',         _('Beta Users')
        PERCENTAGE   = 'percentage',   _('Percentage Rollout')
        OFF          = 'off',          _('Disabled')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key          = models.CharField(max_length=100, unique=True, db_index=True)
    display_name = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    is_enabled   = models.BooleanField(default=False, db_index=True)
    rollout      = models.CharField(max_length=15, choices=Rollout.choices, default=Rollout.OFF)
    rollout_pct  = models.PositiveSmallIntegerField(default=0)  # 0–100 for PERCENTAGE rollout
    metadata     = models.JSONField(default=dict, blank=True)
    created_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'administration'
        db_table  = 'admin_feature_flags'
        ordering  = ['key']

    def __str__(self):
        status = 'ON' if self.is_enabled else 'OFF'
        return f"{self.key} [{status} / {self.rollout}]"


class AdminAuditLog(models.Model):
    """
    Immutable audit trail for administrative actions (complements django-auditlog).
    Stores who did what to which object, with full diff.
    """

    class Action(models.TextChoices):
        CREATE    = 'create',   _('Created')
        UPDATE    = 'update',   _('Updated')
        DELETE    = 'delete',   _('Deleted')
        LOGIN     = 'login',    _('Login')
        LOGOUT    = 'logout',   _('Logout')
        EXPORT    = 'export',   _('Data Exported')
        OVERRIDE  = 'override', _('Manual Override')
        FLAG_CHANGE = 'flag',   _('Feature Flag Changed')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='admin_audit_logs'
    )
    action       = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    object_type  = models.CharField(max_length=100, blank=True)
    object_id    = models.CharField(max_length=100, blank=True)
    object_repr  = models.CharField(max_length=500, blank=True)
    changes      = models.JSONField(default=dict, blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.TextField(blank=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'administration'
        db_table  = 'admin_audit_logs'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]

    def __str__(self):
        return f"{self.actor} {self.action} {self.object_type}:{self.object_id}"


class SupportTicket(models.Model):
    """
    User-submitted support ticket.
    """

    class Priority(models.TextChoices):
        LOW      = 'low',      _('Low')
        MEDIUM   = 'medium',   _('Medium')
        HIGH     = 'high',     _('High')
        CRITICAL = 'critical', _('Critical')

    class Status(models.TextChoices):
        OPEN        = 'open',        _('Open')
        IN_PROGRESS = 'in_progress', _('In Progress')
        WAITING     = 'waiting',     _('Waiting on User')
        RESOLVED    = 'resolved',    _('Resolved')
        CLOSED      = 'closed',      _('Closed')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=20, unique=True, db_index=True)
    submitter    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets'
    )
    assigned_to  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tickets'
    )
    subject      = models.CharField(max_length=255)
    description  = models.TextField()
    priority     = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status       = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN, db_index=True)
    category     = models.CharField(max_length=50, blank=True)
    tags         = models.JSONField(default=list, blank=True)

    resolved_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'administration'
        db_table  = 'admin_support_tickets'
        ordering  = ['-created_at']

    def __str__(self):
        return f"[{self.ticket_number}] {self.subject} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            import random, string
            self.ticket_number = 'FF-' + ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)
