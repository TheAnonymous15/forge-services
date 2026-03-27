# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Applications Models (MVP1)
===============================================
Application tracking, workflow stages, and related entities.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


# =============================================================================
# ENUMS / CHOICES
# =============================================================================

class ApplicationStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    SUBMITTED = 'submitted', _('Submitted')
    UNDER_REVIEW = 'under_review', _('Under Review')
    SHORTLISTED = 'shortlisted', _('Shortlisted')
    INTERVIEW = 'interview', _('Interview Stage')
    ASSESSMENT = 'assessment', _('Assessment Stage')
    OFFER = 'offer', _('Offer Extended')
    ACCEPTED = 'accepted', _('Accepted')
    REJECTED = 'rejected', _('Rejected')
    WITHDRAWN = 'withdrawn', _('Withdrawn')


class InterviewType(models.TextChoices):
    PHONE = 'phone', _('Phone Screen')
    VIDEO = 'video', _('Video Interview')
    ONSITE = 'onsite', _('On-site Interview')
    TECHNICAL = 'technical', _('Technical Interview')
    PANEL = 'panel', _('Panel Interview')
    FINAL = 'final', _('Final Interview')


class InterviewStatus(models.TextChoices):
    SCHEDULED = 'scheduled', _('Scheduled')
    CONFIRMED = 'confirmed', _('Confirmed')
    COMPLETED = 'completed', _('Completed')
    CANCELLED = 'cancelled', _('Cancelled')
    RESCHEDULED = 'rescheduled', _('Rescheduled')
    NO_SHOW = 'no_show', _('No Show')


# =============================================================================
# APPLICATION
# =============================================================================

class Application(models.Model):
    """
    Job application from a talent to an opportunity.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relations (using ForeignKey for single database)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    opportunity = models.ForeignKey(
        'organizations.Opportunity',
        on_delete=models.CASCADE,
        related_name='applications'
    )

    # Application content
    cover_letter = models.TextField(blank=True)
    resume = models.FileField(upload_to='resumes/', null=True, blank=True)
    portfolio_url = models.URLField(blank=True)

    # Answers to application questions (JSON)
    answers = models.JSONField(default=dict, blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.DRAFT
    )

    # Scoring & notes (for employers)
    score = models.PositiveIntegerField(null=True, blank=True, help_text=_('0-100'))
    internal_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # Matching
    match_score = models.PositiveIntegerField(null=True, blank=True, help_text=_('AI-computed match score'))

    # Flags
    is_starred = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications'
    )

    class Meta:
        db_table = 'applications_applications'
        verbose_name = _('Application')
        verbose_name_plural = _('Applications')
        ordering = ['-created_at']
        unique_together = ['applicant', 'opportunity']

    def __str__(self):
        return f"{self.applicant.email} -> {self.opportunity.title}"

    @property
    def can_withdraw(self):
        """Check if application can be withdrawn."""
        return self.status in [
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.UNDER_REVIEW,
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.INTERVIEW,
        ]

    @property
    def is_active(self):
        """Check if application is in active state."""
        return self.status not in [
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.ACCEPTED,
        ]


# =============================================================================
# APPLICATION STATUS HISTORY
# =============================================================================

class ApplicationStatusHistory(models.Model):
    """Track application status changes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='status_history'
    )

    from_status = models.CharField(max_length=20, choices=ApplicationStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=ApplicationStatus.choices)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'applications_status_history'
        verbose_name = _('Application Status History')
        verbose_name_plural = _('Application Status Histories')
        ordering = ['-created_at']


# =============================================================================
# INTERVIEW
# =============================================================================

class Interview(models.Model):
    """Interview scheduled for an application."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='interviews'
    )

    # Interview details
    interview_type = models.CharField(
        max_length=20,
        choices=InterviewType.choices,
        default=InterviewType.VIDEO
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Scheduling
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    timezone = models.CharField(max_length=50, default='Africa/Johannesburg')

    # Location/Link
    location = models.CharField(max_length=255, blank=True)
    meeting_link = models.URLField(blank=True)
    meeting_password = models.CharField(max_length=50, blank=True)

    # Interviewers
    interviewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conducted_interviews',
        blank=True
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=InterviewStatus.choices,
        default=InterviewStatus.SCHEDULED
    )

    # Feedback
    feedback = models.TextField(blank=True)
    rating = models.PositiveIntegerField(null=True, blank=True, help_text=_('1-5'))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_interviews'
    )

    class Meta:
        db_table = 'applications_interviews'
        verbose_name = _('Interview')
        verbose_name_plural = _('Interviews')
        ordering = ['scheduled_at']

    def __str__(self):
        return f"{self.title} - {self.application.applicant.email}"


# =============================================================================
# APPLICATION NOTE
# =============================================================================

class ApplicationNote(models.Model):
    """Notes added to an application by reviewers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='notes'
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    content = models.TextField()
    is_private = models.BooleanField(default=True, help_text=_('Private notes are only visible to org members'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'applications_notes'
        verbose_name = _('Application Note')
        verbose_name_plural = _('Application Notes')
        ordering = ['-created_at']


# =============================================================================
# SAVED OPPORTUNITY (Wishlist/Bookmarks)
# =============================================================================

class SavedOpportunity(models.Model):
    """Opportunities saved/bookmarked by users."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_opportunities'
    )
    opportunity = models.ForeignKey(
        'organizations.Opportunity',
        on_delete=models.CASCADE,
        related_name='saved_by'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'applications_saved_opportunities'
        verbose_name = _('Saved Opportunity')
        verbose_name_plural = _('Saved Opportunities')
        unique_together = ['user', 'opportunity']
        ordering = ['-created_at']

