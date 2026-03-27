# -*- coding: utf-8 -*-
"""
Orchestration Models
====================
Central DB models that mirror each subsystem's data.
Also holds the event log (audit trail of every sync operation)
and the dead letter queue (failed events for manual review).
"""
from django.db import models
from django.utils import timezone
import uuid


# ─────────────────────────────────────────────────────────────────────────────
# EVENT LOG  — every sync attempt is recorded here (central DB)
# ─────────────────────────────────────────────────────────────────────────────

class SyncEventLog(models.Model):
    """Audit trail of every event-driven sync attempt."""

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        SUCCESS   = 'success',   'Success'
        FAILED    = 'failed',    'Failed'
        RETRYING  = 'retrying',  'Retrying'
        DEAD      = 'dead',      'Dead (exhausted retries)'

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_label       = models.CharField(max_length=64, db_index=True)
    model_name      = models.CharField(max_length=128, db_index=True)
    instance_id     = models.CharField(max_length=255, db_index=True)
    operation       = models.CharField(max_length=16)   # create | update | delete
    status          = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    retry_count     = models.PositiveSmallIntegerField(default=0)
    payload         = models.JSONField(default=dict)
    error_message   = models.TextField(blank=True)
    celery_task_id  = models.CharField(max_length=255, blank=True)
    created_at      = models.DateTimeField(default=timezone.now, db_index=True)
    synced_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label    = 'orchestration'
        db_table     = 'orch_sync_event_log'
        ordering     = ['-created_at']
        indexes      = [
            models.Index(fields=['app_label', 'model_name', 'status']),
            models.Index(fields=['status', 'retry_count']),
        ]

    def __str__(self):
        return f"[{self.status}] {self.app_label}.{self.model_name}:{self.instance_id} ({self.operation})"


class DeadLetterEvent(models.Model):
    """
    Events that exhausted all retries.
    Stored for manual review / replay.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_event  = models.UUIDField(db_index=True)          # FK-like reference to SyncEventLog.id
    app_label       = models.CharField(max_length=64)
    model_name      = models.CharField(max_length=128)
    instance_id     = models.CharField(max_length=255)
    operation       = models.CharField(max_length=16)
    payload         = models.JSONField(default=dict)
    last_error      = models.TextField()
    retry_count     = models.PositiveSmallIntegerField(default=0)
    created_at      = models.DateTimeField(default=timezone.now)
    resolved        = models.BooleanField(default=False)
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolved_by     = models.CharField(max_length=255, blank=True)
    notes           = models.TextField(blank=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'orch_dead_letter'
        ordering  = ['-created_at']

    def __str__(self):
        return f"[DLQ] {self.app_label}.{self.model_name}:{self.instance_id}"


# ─────────────────────────────────────────────────────────────────────────────
# CENTRAL MIRROR MODELS  — one per subsystem, stored in central_db
# These are read-only snapshots for analytics, intelligence, matching etc.
# ─────────────────────────────────────────────────────────────────────────────

class CentralUser(models.Model):
    """Mirror of accounts.User → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    email           = models.EmailField(db_index=True)
    first_name      = models.CharField(max_length=150, blank=True)
    last_name       = models.CharField(max_length=150, blank=True)
    role            = models.CharField(max_length=20)
    is_active       = models.BooleanField(default=True)
    is_verified     = models.BooleanField(default=False)
    date_joined     = models.DateTimeField(null=True)
    last_login      = models.DateTimeField(null=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_users'

    def __str__(self):
        return f"{self.email} ({self.role})"


class CentralProfile(models.Model):
    """Mirror of profiles.TalentProfile → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    user_id         = models.UUIDField(db_index=True)
    headline        = models.CharField(max_length=255, blank=True)
    bio             = models.TextField(blank=True)
    country         = models.CharField(max_length=100, blank=True)
    city            = models.CharField(max_length=100, blank=True)
    skills          = models.JSONField(default=list)
    experience_years= models.PositiveSmallIntegerField(default=0)
    availability    = models.CharField(max_length=32, blank=True)
    employment_status = models.CharField(max_length=32, blank=True)
    is_public       = models.BooleanField(default=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_profiles'

    def __str__(self):
        return f"Profile:{self.user_id}"


class CentralOrganization(models.Model):
    """Mirror of organizations.Organization → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    owner_id        = models.UUIDField(db_index=True)
    name            = models.CharField(max_length=255, db_index=True)
    org_type        = models.CharField(max_length=32, blank=True)
    industry        = models.CharField(max_length=100, blank=True)
    country         = models.CharField(max_length=100, blank=True)
    city            = models.CharField(max_length=100, blank=True)
    size            = models.CharField(max_length=20, blank=True)
    status          = models.CharField(max_length=20, blank=True)
    is_verified     = models.BooleanField(default=False)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_organizations'

    def __str__(self):
        return self.name


class CentralOpportunity(models.Model):
    """Mirror of organizations.Opportunity → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    organization_id = models.UUIDField(db_index=True)
    title           = models.CharField(max_length=255, db_index=True)
    opp_type        = models.CharField(max_length=32, blank=True)
    location        = models.CharField(max_length=255, blank=True)
    is_remote       = models.BooleanField(default=False)
    required_skills = models.JSONField(default=list)
    status          = models.CharField(max_length=20, blank=True)
    deadline        = models.DateTimeField(null=True)
    created_at      = models.DateTimeField(null=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_opportunities'

    def __str__(self):
        return self.title


class CentralApplication(models.Model):
    """Mirror of applications.Application → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    applicant_id    = models.UUIDField(db_index=True)
    opportunity_id  = models.UUIDField(db_index=True)
    organization_id = models.UUIDField(db_index=True)
    status          = models.CharField(max_length=32, db_index=True)
    applied_at      = models.DateTimeField(null=True)
    updated_at      = models.DateTimeField(null=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_applications'

    def __str__(self):
        return f"App:{self.applicant_id}→{self.opportunity_id}"


class CentralSkill(models.Model):
    """Unified skill registry built from all profile skills → central DB."""
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=255, unique=True, db_index=True)
    category    = models.CharField(max_length=100, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_skills'

    def __str__(self):
        return self.name


class FullSyncReport(models.Model):
    """Record of every nightly full-sync run."""
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    started_at      = models.DateTimeField(default=timezone.now)
    completed_at    = models.DateTimeField(null=True)
    status          = models.CharField(max_length=20, default='running')
    total_synced    = models.PositiveIntegerField(default=0)
    total_failed    = models.PositiveIntegerField(default=0)
    details         = models.JSONField(default=dict)
    error_message   = models.TextField(blank=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'orch_full_sync_reports'
        ordering  = ['-started_at']

    def __str__(self):
        return f"FullSync {self.started_at:%Y-%m-%d %H:%M} [{self.status}]"


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA SUBSYSTEM MIRROR
# ─────────────────────────────────────────────────────────────────────────────

class CentralMediaFile(models.Model):
    """Mirror of media.MediaFile → central DB."""
    id          = models.UUIDField(primary_key=True, editable=False)
    owner_id    = models.UUIDField(db_index=True)
    file_type   = models.CharField(max_length=50, blank=True)
    mime_type   = models.CharField(max_length=100, blank=True)
    file_size   = models.PositiveBigIntegerField(default=0)
    status      = models.CharField(max_length=32, blank=True)
    is_public   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(null=True)
    synced_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_media_files'

    def __str__(self):
        return f"Media:{self.id} ({self.file_type})"


class CentralDocument(models.Model):
    """Mirror of media.Document → central DB."""
    id           = models.UUIDField(primary_key=True, editable=False)
    owner_id     = models.UUIDField(db_index=True)
    doc_type     = models.CharField(max_length=50, blank=True)
    is_verified  = models.BooleanField(default=False)
    created_at   = models.DateTimeField(null=True)
    synced_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_documents'

    def __str__(self):
        return f"Document:{self.id} ({self.doc_type})"


# ─────────────────────────────────────────────────────────────────────────────
# INTELLIGENCE SUBSYSTEM MIRROR
# ─────────────────────────────────────────────────────────────────────────────

class CentralTalentScore(models.Model):
    """Mirror of intelligence.TalentScore → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    profile_id      = models.UUIDField(db_index=True)
    overall_score   = models.FloatField(default=0.0)
    skill_score     = models.FloatField(default=0.0)
    experience_score= models.FloatField(default=0.0)
    education_score = models.FloatField(default=0.0)
    completeness    = models.FloatField(default=0.0)
    computed_at     = models.DateTimeField(null=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_talent_scores'

    def __str__(self):
        return f"Score:{self.profile_id} ({self.overall_score})"


class CentralSkillExtraction(models.Model):
    """Mirror of intelligence.SkillExtraction → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    profile_id      = models.UUIDField(db_index=True)
    extracted_skills= models.JSONField(default=list)
    confidence      = models.FloatField(default=0.0)
    source          = models.CharField(max_length=32, blank=True)
    created_at      = models.DateTimeField(null=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_skill_extractions'

    def __str__(self):
        return f"SkillExtraction:{self.profile_id}"


# ─────────────────────────────────────────────────────────────────────────────
# MATCHING SUBSYSTEM MIRROR
# ─────────────────────────────────────────────────────────────────────────────

class CentralMatchScore(models.Model):
    """Mirror of matching.MatchScore → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    profile_id      = models.UUIDField(db_index=True)
    opportunity_id  = models.UUIDField(db_index=True)
    score           = models.FloatField(default=0.0)
    match_factors   = models.JSONField(default=dict)
    is_recommended  = models.BooleanField(default=False)
    computed_at     = models.DateTimeField(null=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_match_scores'
        indexes   = [models.Index(fields=['profile_id', 'opportunity_id'])]

    def __str__(self):
        return f"Match:{self.profile_id}→{self.opportunity_id} ({self.score:.2f})"


# ─────────────────────────────────────────────────────────────────────────────
# COMMUNICATIONS SUBSYSTEM MIRROR
# ─────────────────────────────────────────────────────────────────────────────

class CentralNotification(models.Model):
    """Mirror of communications.Notification → central DB."""
    id          = models.UUIDField(primary_key=True, editable=False)
    recipient_id= models.UUIDField(db_index=True)
    notif_type  = models.CharField(max_length=64, blank=True)
    channel     = models.CharField(max_length=32, blank=True)
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(null=True)
    synced_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_notifications'

    def __str__(self):
        return f"Notification:{self.recipient_id} ({self.notif_type})"


class CentralMessage(models.Model):
    """Mirror of communications.Message → central DB."""
    id          = models.UUIDField(primary_key=True, editable=False)
    sender_id   = models.UUIDField(db_index=True)
    recipient_id= models.UUIDField(db_index=True)
    thread_id   = models.UUIDField(null=True, db_index=True)
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(null=True)
    synced_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_messages'

    def __str__(self):
        return f"Message:{self.sender_id}→{self.recipient_id}"


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS SUBSYSTEM MIRROR
# ─────────────────────────────────────────────────────────────────────────────

class CentralAnalyticsEvent(models.Model):
    """Mirror of analytics.UserEvent → central DB."""
    id          = models.UUIDField(primary_key=True, editable=False)
    user_id     = models.UUIDField(null=True, db_index=True)
    event_name  = models.CharField(max_length=128, db_index=True)
    event_data  = models.JSONField(default=dict)
    session_id  = models.CharField(max_length=128, blank=True)
    created_at  = models.DateTimeField(null=True, db_index=True)
    synced_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_analytics_events'
        indexes   = [models.Index(fields=['event_name', 'created_at'])]

    def __str__(self):
        return f"Event:{self.event_name} ({self.created_at})"


class CentralMetricSnapshot(models.Model):
    """Mirror of analytics.PlatformMetricSnapshot → central DB."""
    id              = models.UUIDField(primary_key=True, editable=False)
    metric_name     = models.CharField(max_length=128, db_index=True)
    metric_value    = models.FloatField(default=0.0)
    period          = models.CharField(max_length=16, blank=True)
    recorded_at     = models.DateTimeField(null=True, db_index=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_metric_snapshots'

    def __str__(self):
        return f"Metric:{self.metric_name}={self.metric_value}"


# ─────────────────────────────────────────────────────────────────────────────
# ADMINISTRATION SUBSYSTEM MIRROR
# ─────────────────────────────────────────────────────────────────────────────

class CentralAdminAuditLog(models.Model):
    """Mirror of administration.AdminAuditLog → central DB."""
    id          = models.UUIDField(primary_key=True, editable=False)
    actor_id    = models.UUIDField(db_index=True)
    action      = models.CharField(max_length=128, db_index=True)
    target_type = models.CharField(max_length=128, blank=True)
    target_id   = models.CharField(max_length=255, blank=True)
    details     = models.JSONField(default=dict)
    ip_address  = models.GenericIPAddressField(null=True)
    created_at  = models.DateTimeField(null=True, db_index=True)
    synced_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_admin_audit_logs'

    def __str__(self):
        return f"AdminAudit:{self.actor_id} {self.action}"


class CentralFeatureFlag(models.Model):
    """Mirror of administration.FeatureFlag → central DB."""
    id          = models.UUIDField(primary_key=True, editable=False)
    name        = models.CharField(max_length=128, unique=True, db_index=True)
    is_enabled  = models.BooleanField(default=False)
    rollout_pct = models.PositiveSmallIntegerField(default=0)
    updated_at  = models.DateTimeField(null=True)
    synced_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_feature_flags'

    def __str__(self):
        return f"FeatureFlag:{self.name} ({'ON' if self.is_enabled else 'OFF'})"


# ─────────────────────────────────────────────────────────────────────────────
# SECURITY SUBSYSTEM MIRROR
# ─────────────────────────────────────────────────────────────────────────────

class CentralSecurityEvent(models.Model):
    """Mirror of security.SecurityEvent → central DB."""
    id          = models.UUIDField(primary_key=True, editable=False)
    user_id     = models.UUIDField(null=True, db_index=True)
    event_type  = models.CharField(max_length=64, db_index=True)
    severity    = models.CharField(max_length=16, blank=True)
    ip_address  = models.GenericIPAddressField(null=True)
    details     = models.JSONField(default=dict)
    resolved    = models.BooleanField(default=False)
    created_at  = models.DateTimeField(null=True, db_index=True)
    synced_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_security_events'
        indexes   = [models.Index(fields=['event_type', 'severity', 'created_at'])]

    def __str__(self):
        return f"SecEvent:{self.event_type} [{self.severity}]"


class CentralConsentRecord(models.Model):
    """Mirror of security.ConsentRecord → central DB. Required for POPIA compliance."""
    id              = models.UUIDField(primary_key=True, editable=False)
    user_id         = models.UUIDField(db_index=True)
    consent_type    = models.CharField(max_length=64, db_index=True)
    is_granted      = models.BooleanField(default=False)
    ip_address      = models.GenericIPAddressField(null=True)
    granted_at      = models.DateTimeField(null=True)
    revoked_at      = models.DateTimeField(null=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orchestration'
        db_table  = 'central_consent_records'
        indexes   = [models.Index(fields=['user_id', 'consent_type'])]

    def __str__(self):
        return f"Consent:{self.user_id} {self.consent_type} ({'Y' if self.is_granted else 'N'})"



