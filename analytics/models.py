# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Analytics Models (MVP1)
===========================================
Analytics & Reporting subsystem.
Tracks platform usage, talent funnel, employer activity, and KPIs.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class PageView(models.Model):
    """
    Single page/endpoint visit. Anonymous-friendly (user can be null).
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='page_views'
    )
    session_id  = models.CharField(max_length=64, blank=True, db_index=True)
    path        = models.CharField(max_length=512, db_index=True)
    method      = models.CharField(max_length=10, default='GET')
    status_code = models.PositiveSmallIntegerField(default=200)
    referrer    = models.CharField(max_length=512, blank=True)
    user_agent  = models.TextField(blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    country     = models.CharField(max_length=50, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)   # response time in ms
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'analytics'
        db_table  = 'analytics_page_views'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.method} {self.path} [{self.status_code}]"


class UserEvent(models.Model):
    """
    Structured user interaction event (profile view, application click, etc.).
    Used for funnel analysis and personalisation.
    """

    class EventType(models.TextChoices):
        PROFILE_VIEW        = 'profile_view',       _('Profile Viewed')
        PROFILE_UPDATE      = 'profile_update',     _('Profile Updated')
        CV_UPLOAD           = 'cv_upload',          _('CV Uploaded')
        SEARCH              = 'search',             _('Talent/Job Search')
        OPPORTUNITY_VIEW    = 'opp_view',           _('Opportunity Viewed')
        OPPORTUNITY_APPLY   = 'opp_apply',          _('Application Submitted')
        MESSAGE_SENT        = 'message_sent',       _('Message Sent')
        MATCH_ACCEPTED      = 'match_accepted',     _('Match Accepted')
        MATCH_REJECTED      = 'match_rejected',     _('Match Rejected')
        LOGIN               = 'login',              _('Login')
        LOGOUT              = 'logout',             _('Logout')
        SIGNUP              = 'signup',             _('Registration')
        ONBOARDING_STEP     = 'onboarding',         _('Onboarding Step Completed')
        WAITLIST_JOIN       = 'waitlist',           _('Joined Waitlist')
        PARTNER_REGISTER    = 'partner_register',   _('Partner Registration')
        BLOG_VIEW           = 'blog_view',          _('Blog Article Viewed')
        NOTIFICATION_READ   = 'notif_read',         _('Notification Read')
        CUSTOM              = 'custom',             _('Custom Event')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='user_events'
    )
    session_id  = models.CharField(max_length=64, blank=True, db_index=True)
    event_type  = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    event_name  = models.CharField(max_length=100, blank=True)   # custom name for CUSTOM type
    properties  = models.JSONField(default=dict, blank=True)

    # Context
    ref_type    = models.CharField(max_length=50, blank=True)    # model name
    ref_id      = models.UUIDField(null=True, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    country     = models.CharField(max_length=50, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'analytics'
        db_table  = 'analytics_user_events'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} by user {self.user_id} at {self.created_at}"


class PlatformMetricSnapshot(models.Model):
    """
    Hourly/daily snapshot of key platform metrics.
    Pre-aggregated for fast dashboard rendering.
    """

    class Granularity(models.TextChoices):
        HOURLY  = 'hourly',  _('Hourly')
        DAILY   = 'daily',   _('Daily')
        WEEKLY  = 'weekly',  _('Weekly')
        MONTHLY = 'monthly', _('Monthly')

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    granularity     = models.CharField(max_length=10, choices=Granularity.choices, db_index=True)
    period_start    = models.DateTimeField(db_index=True)

    # User metrics
    total_users         = models.PositiveIntegerField(default=0)
    new_users           = models.PositiveIntegerField(default=0)
    active_users        = models.PositiveIntegerField(default=0)
    talent_count        = models.PositiveIntegerField(default=0)
    employer_count      = models.PositiveIntegerField(default=0)

    # Activity metrics
    total_page_views    = models.PositiveIntegerField(default=0)
    total_events        = models.PositiveIntegerField(default=0)
    applications_submitted = models.PositiveIntegerField(default=0)
    matches_computed    = models.PositiveIntegerField(default=0)
    messages_sent       = models.PositiveIntegerField(default=0)
    cv_uploads          = models.PositiveIntegerField(default=0)

    # Conversion
    waitlist_joins      = models.PositiveIntegerField(default=0)
    partner_registrations = models.PositiveIntegerField(default=0)

    # Geographic breakdown (top 5 countries as JSON)
    top_countries       = models.JSONField(default=list, blank=True)

    # Raw data for custom analysis
    extra               = models.JSONField(default=dict, blank=True)

    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'analytics'
        db_table  = 'analytics_metric_snapshots'
        unique_together = [['granularity', 'period_start']]
        ordering  = ['-period_start']

    def __str__(self):
        return f"{self.granularity} snapshot @ {self.period_start}"


class Report(models.Model):
    """
    On-demand or scheduled analytics report.
    """

    class ReportType(models.TextChoices):
        TALENT_FUNNEL    = 'talent_funnel',   _('Talent Funnel')
        EMPLOYER_ACTIVITY= 'employer_activity',_('Employer Activity')
        MATCH_QUALITY    = 'match_quality',   _('Match Quality')
        PLATFORM_HEALTH  = 'platform_health', _('Platform Health')
        CUSTOM           = 'custom',          _('Custom Report')

    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending')
        RUNNING   = 'running',   _('Running')
        DONE      = 'done',      _('Done')
        FAILED    = 'failed',    _('Failed')

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_type   = models.CharField(max_length=30, choices=ReportType.choices)
    title         = models.CharField(max_length=255)
    status        = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    parameters    = models.JSONField(default=dict, blank=True)
    result_data   = models.JSONField(default=dict, blank=True)
    file_path     = models.CharField(max_length=512, blank=True)   # for exported PDF/CSV

    requested_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    started_at    = models.DateTimeField(null=True, blank=True)
    finished_at   = models.DateTimeField(null=True, blank=True)
    error         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'analytics'
        db_table  = 'analytics_reports'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.report_type}: {self.title} [{self.status}]"
