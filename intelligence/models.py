# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Intelligence Models (MVP1)
==============================================
Talent Intelligence & Skill Extraction subsystem.
Manages AI/ML-derived insights: skill graphs, talent scores, CV parsing results.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class SkillTaxonomy(models.Model):
    """
    Master list of skills with categorisation and metadata.
    Shared by profiles, intelligence, and matching subsystems.
    """

    class Category(models.TextChoices):
        TECHNICAL    = 'technical',    _('Technical')
        CREATIVE     = 'creative',     _('Creative')
        BUSINESS     = 'business',     _('Business')
        LEADERSHIP   = 'leadership',   _('Leadership')
        COMMUNICATION= 'communication',_('Communication')
        ANALYTICAL   = 'analytical',   _('Analytical')
        TRADES       = 'trades',       _('Trades & Crafts')
        AGRICULTURE  = 'agriculture',  _('Agriculture')
        HEALTH       = 'health',       _('Health & Medical')
        EDUCATION    = 'education',    _('Education & Training')
        ARTS         = 'arts',         _('Arts & Culture')
        SPORTS       = 'sports',       _('Sports & Athletics')
        OTHER        = 'other',        _('Other')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=100, unique=True, db_index=True)
    slug         = models.SlugField(max_length=120, unique=True)
    category     = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    description  = models.TextField(blank=True)
    aliases      = models.JSONField(default=list, blank=True, help_text='Alternative names for this skill')
    parent       = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children'
    )
    is_active    = models.BooleanField(default=True)
    usage_count  = models.PositiveIntegerField(default=0, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label  = 'intelligence'
        db_table   = 'intelligence_skill_taxonomy'
        ordering   = ['name']
        verbose_name        = _('Skill')
        verbose_name_plural = _('Skills')

    def __str__(self):
        return f"{self.name} ({self.category})"


class CVParseResult(models.Model):
    """
    Result of AI-powered CV / resume text extraction.
    Each Document can have one parse result.
    """

    class Status(models.TextChoices):
        PENDING    = 'pending',    _('Pending')
        PROCESSING = 'processing', _('Processing')
        DONE       = 'done',       _('Done')
        FAILED     = 'failed',     _('Failed')

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cv_parses'
    )
    # FK to media.Document — stored as string to avoid cross-app dependency issues
    document_id    = models.UUIDField(db_index=True)
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    # Extracted structured data
    raw_text       = models.TextField(blank=True)
    parsed_data    = models.JSONField(default=dict, blank=True)   # full structured output
    extracted_skills   = models.JSONField(default=list, blank=True)
    extracted_education = models.JSONField(default=list, blank=True)
    extracted_experience = models.JSONField(default=list, blank=True)
    contact_info   = models.JSONField(default=dict, blank=True)

    # Confidence scores
    overall_confidence = models.FloatField(default=0.0)
    error_message  = models.TextField(blank=True)

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'intelligence'
        db_table  = 'intelligence_cv_parse_results'
        ordering  = ['-created_at']

    def __str__(self):
        return f"CV parse for user {self.user_id} [{self.status}]"


class TalentScore(models.Model):
    """
    Composite score for a talent profile, computed by the intelligence engine.
    Scores are recalculated on profile update (via Celery task).
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='talent_score'
    )

    # Individual dimension scores (0.0 – 100.0)
    profile_completeness = models.FloatField(default=0.0)
    skill_depth          = models.FloatField(default=0.0)
    experience_score     = models.FloatField(default=0.0)
    education_score      = models.FloatField(default=0.0)
    portfolio_score      = models.FloatField(default=0.0)
    activity_score       = models.FloatField(default=0.0)

    # Composite overall score
    overall_score    = models.FloatField(default=0.0, db_index=True)
    percentile_rank  = models.FloatField(default=0.0)   # vs all platform users

    # Breakdown for dashboard display
    breakdown        = models.JSONField(default=dict, blank=True)

    computed_at      = models.DateTimeField(auto_now=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'intelligence'
        db_table  = 'intelligence_talent_scores'
        ordering  = ['-overall_score']

    def __str__(self):
        return f"Score {self.overall_score:.1f} for user {self.user_id}"


class SkillExtraction(models.Model):
    """
    Skills extracted from a specific document or profile text block.
    Linked to SkillTaxonomy entries where possible.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skill_extractions'
    )
    source_type     = models.CharField(max_length=50, default='cv')  # cv, profile, bio
    source_id       = models.UUIDField(null=True, blank=True, db_index=True)

    skill_name      = models.CharField(max_length=100)
    skill_taxonomy  = models.ForeignKey(
        SkillTaxonomy, on_delete=models.SET_NULL, null=True, blank=True, related_name='extractions'
    )
    confidence      = models.FloatField(default=0.0)
    context_snippet = models.TextField(blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'intelligence'
        db_table  = 'intelligence_skill_extractions'
        ordering  = ['-confidence']
        indexes   = [
            models.Index(fields=['user', 'skill_name']),
        ]

    def __str__(self):
        return f"{self.skill_name} ({self.confidence:.0%}) for user {self.user_id}"


class IntelligenceInsight(models.Model):
    """
    AI-generated insights for a user: career path recommendations,
    skill gap analysis, market demand analysis.
    """

    class InsightType(models.TextChoices):
        SKILL_GAP       = 'skill_gap',      _('Skill Gap Analysis')
        CAREER_PATH     = 'career_path',    _('Career Path Suggestion')
        MARKET_DEMAND   = 'market_demand',  _('Market Demand Alert')
        PROFILE_TIP     = 'profile_tip',    _('Profile Improvement Tip')
        SALARY_BENCHMARK = 'salary',        _('Salary Benchmark')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='insights'
    )
    insight_type = models.CharField(max_length=30, choices=InsightType.choices)
    title        = models.CharField(max_length=200)
    body         = models.TextField()
    data         = models.JSONField(default=dict, blank=True)
    is_read      = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    relevance_score = models.FloatField(default=0.0)
    expires_at   = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'intelligence'
        db_table  = 'intelligence_insights'
        ordering  = ['-relevance_score', '-created_at']

    def __str__(self):
        return f"{self.insight_type}: {self.title} → {self.user_id}"
