# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Communications Models (MVP1)
================================================
Notifications, in-app messages, email logs, and broadcast announcements.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class Notification(models.Model):
    """
    In-app notification for a user.
    Supports multiple channels: in_app, email, sms, push.
    """

    class Channel(models.TextChoices):
        IN_APP = 'in_app', _('In-App')
        EMAIL  = 'email',  _('Email')
        SMS    = 'sms',    _('SMS')
        PUSH   = 'push',   _('Push Notification')

    class NotifType(models.TextChoices):
        MATCH_FOUND      = 'match_found',      _('New Match Found')
        APPLICATION_UPDATE = 'app_update',     _('Application Status Update')
        MESSAGE_RECEIVED = 'message',          _('New Message')
        PROFILE_VIEW     = 'profile_view',     _('Profile Viewed')
        INSIGHT_NEW      = 'insight',          _('New Insight Available')
        SYSTEM           = 'system',           _('System Notification')
        WELCOME          = 'welcome',          _('Welcome')
        VERIFICATION     = 'verification',     _('Account Verification')
        REMINDER         = 'reminder',         _('Reminder')
        ANNOUNCEMENT     = 'announcement',     _('Announcement')

    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending')
        SENT      = 'sent',      _('Sent')
        DELIVERED = 'delivered', _('Delivered')
        READ      = 'read',      _('Read')
        FAILED    = 'failed',    _('Failed')

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    channel        = models.CharField(max_length=10, choices=Channel.choices, default=Channel.IN_APP)
    notif_type     = models.CharField(max_length=30, choices=NotifType.choices)
    status         = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True)

    title          = models.CharField(max_length=200)
    body           = models.TextField()
    action_url     = models.CharField(max_length=512, blank=True)
    data           = models.JSONField(default=dict, blank=True)

    # Reference to related object (generic)
    ref_type       = models.CharField(max_length=50, blank=True)
    ref_id         = models.UUIDField(null=True, blank=True)

    is_read        = models.BooleanField(default=False, db_index=True)
    read_at        = models.DateTimeField(null=True, blank=True)
    sent_at        = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'communications'
        db_table  = 'comms_notifications'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', 'channel', 'status']),
        ]

    def __str__(self):
        return f"[{self.channel}] {self.notif_type} → {self.recipient_id}"


class EmailLog(models.Model):
    """
    Audit log for every outbound email sent by the platform.
    """

    class Status(models.TextChoices):
        QUEUED    = 'queued',    _('Queued')
        SENT      = 'sent',      _('Sent')
        DELIVERED = 'delivered', _('Delivered')
        OPENED    = 'opened',    _('Opened')
        CLICKED   = 'clicked',   _('Clicked')
        BOUNCED   = 'bounced',   _('Bounced')
        FAILED    = 'failed',    _('Failed')
        SPAM      = 'spam',      _('Marked as Spam')

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='email_logs'
    )
    to_email      = models.EmailField(db_index=True)
    from_email    = models.EmailField()
    subject       = models.CharField(max_length=500)
    template_name = models.CharField(max_length=100, blank=True)
    status        = models.CharField(max_length=15, choices=Status.choices, default=Status.QUEUED, db_index=True)

    # Provider tracking (SendGrid, etc.)
    provider_message_id = models.CharField(max_length=255, blank=True)
    provider_response   = models.JSONField(default=dict, blank=True)

    sent_at       = models.DateTimeField(null=True, blank=True)
    opened_at     = models.DateTimeField(null=True, blank=True)
    clicked_at    = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'communications'
        db_table  = 'comms_email_logs'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Email '{self.subject}' → {self.to_email} [{self.status}]"


class Message(models.Model):
    """
    Direct in-platform message between two users (talent <-> employer).
    """

    class Status(models.TextChoices):
        SENT     = 'sent',     _('Sent')
        DELIVERED= 'delivered',_('Delivered')
        READ     = 'read',     _('Read')
        DELETED  = 'deleted',  _('Deleted')

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages'
    )
    recipient  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages'
    )
    thread_id  = models.UUIDField(db_index=True)   # Groups messages into conversations

    body       = models.TextField()
    status     = models.CharField(max_length=15, choices=Status.choices, default=Status.SENT)
    is_read    = models.BooleanField(default=False)
    read_at    = models.DateTimeField(null=True, blank=True)

    # Attachments stored as media file IDs
    attachments = models.JSONField(default=list, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'communications'
        db_table  = 'comms_messages'
        ordering  = ['thread_id', 'created_at']
        indexes   = [
            models.Index(fields=['thread_id', 'created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"Message from {self.sender_id} to {self.recipient_id} in thread {self.thread_id}"


class Announcement(models.Model):
    """
    Platform-wide or targeted announcements (news, outages, features).
    """

    class AudienceType(models.TextChoices):
        ALL       = 'all',      _('All Users')
        TALENT    = 'talent',   _('Talent Only')
        EMPLOYERS = 'employer', _('Employers Only')
        STAFF     = 'staff',    _('Staff Only')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title       = models.CharField(max_length=255)
    body        = models.TextField()
    audience    = models.CharField(max_length=20, choices=AudienceType.choices, default=AudienceType.ALL)
    is_active   = models.BooleanField(default=True, db_index=True)
    is_pinned   = models.BooleanField(default=False)
    action_url  = models.CharField(max_length=512, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at  = models.DateTimeField(null=True, blank=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'communications'
        db_table  = 'comms_announcements'
        ordering  = ['-is_pinned', '-published_at']

    def __str__(self):
        return f"{self.title} ({self.audience})"
