# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Matching Models (MVP1)
==========================================
Matching & Recommendation Engine.
Computes compatibility between talent profiles and opportunities.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class MatchScore(models.Model):
    """
    Pre-computed match between a talent (user) and an opportunity.
    Recalculated asynchronously when either side is updated.
    """

    class Status(models.TextChoices):
        PENDING    = 'pending',    _('Pending')
        COMPUTED   = 'computed',   _('Computed')
        EXPIRED    = 'expired',    _('Expired')

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='match_scores'
    )
    # FK stored as UUID to avoid cross-app hard dependency
    opportunity_id      = models.UUIDField(db_index=True)
    opportunity_type    = models.CharField(max_length=30, default='job')  # job, internship, volunteer

    status              = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Dimension scores (0.0 – 100.0)
    skill_match         = models.FloatField(default=0.0)
    experience_match    = models.FloatField(default=0.0)
    education_match     = models.FloatField(default=0.0)
    location_match      = models.FloatField(default=0.0)
    salary_match        = models.FloatField(default=0.0)
    culture_match       = models.FloatField(default=0.0)

    # Overall composite
    overall_score       = models.FloatField(default=0.0, db_index=True)
    confidence          = models.FloatField(default=0.0)

    # Algorithm metadata
    algorithm_version   = models.CharField(max_length=20, default='v1')
    score_breakdown     = models.JSONField(default=dict, blank=True)
    matched_skills      = models.JSONField(default=list, blank=True)
    missing_skills      = models.JSONField(default=list, blank=True)

    computed_at         = models.DateTimeField(null=True, blank=True)
    expires_at          = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'matching'
        db_table  = 'matching_scores'
        unique_together = [['user', 'opportunity_id']]
        ordering  = ['-overall_score']
        indexes   = [
            models.Index(fields=['user', 'overall_score']),
            models.Index(fields=['opportunity_id', 'overall_score']),
        ]

    def __str__(self):
        return f"Match {self.overall_score:.1f} — user {self.user_id} x opp {self.opportunity_id}"


class Recommendation(models.Model):
    """
    Surfaced recommendation shown to a user (talent or employer).
    References a MatchScore or an externally-computed suggestion.
    """

    class RecType(models.TextChoices):
        OPPORTUNITY   = 'opportunity',  _('Opportunity')
        TALENT        = 'talent',       _('Talent Profile')
        SKILL         = 'skill',        _('Skill to Learn')
        CONNECTION    = 'connection',   _('Suggested Connection')

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recommendations'
    )
    rec_type        = models.CharField(max_length=20, choices=RecType.choices)
    target_id       = models.UUIDField(db_index=True)
    match_score     = models.ForeignKey(
        MatchScore, on_delete=models.SET_NULL, null=True, blank=True, related_name='recommendations'
    )

    rank            = models.PositiveSmallIntegerField(default=0)
    relevance_score = models.FloatField(default=0.0, db_index=True)
    reason          = models.CharField(max_length=255, blank=True)
    metadata        = models.JSONField(default=dict, blank=True)

    # Interaction tracking
    is_viewed       = models.BooleanField(default=False)
    is_clicked      = models.BooleanField(default=False)
    is_dismissed    = models.BooleanField(default=False)
    is_saved        = models.BooleanField(default=False)

    created_at      = models.DateTimeField(auto_now_add=True)
    expires_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'matching'
        db_table  = 'matching_recommendations'
        ordering  = ['rank', '-relevance_score']

    def __str__(self):
        return f"{self.rec_type} rec for user {self.user_id} (score {self.relevance_score:.1f})"


class SearchIndex(models.Model):
    """
    Denormalised, search-optimised snapshot of a talent profile.
    Rebuilt by Celery on every significant profile update.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='search_index'
    )

    # Searchable text fields
    headline        = models.TextField(blank=True)
    bio_text        = models.TextField(blank=True)
    skills_text     = models.TextField(blank=True)   # flattened skill names
    experience_text = models.TextField(blank=True)
    education_text  = models.TextField(blank=True)

    # Structured filters
    skills_json     = models.JSONField(default=list, blank=True)
    location        = models.CharField(max_length=100, blank=True)
    country         = models.CharField(max_length=50, blank=True, db_index=True)
    availability    = models.CharField(max_length=30, blank=True)
    employment_types = models.JSONField(default=list, blank=True)
    salary_min      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default='ZAR')

    overall_score   = models.FloatField(default=0.0, db_index=True)
    is_searchable   = models.BooleanField(default=True, db_index=True)

    indexed_at      = models.DateTimeField(auto_now=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'matching'
        db_table  = 'matching_search_index'
        ordering  = ['-overall_score']

    def __str__(self):
        return f"Search index for user {self.user_id}"
