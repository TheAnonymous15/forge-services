# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organizations Models (MVP1)
================================================
Organization profiles, opportunities, and related entities.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


# =============================================================================
# ENUMS / CHOICES
# =============================================================================

class OrganizationType(models.TextChoices):
    COMPANY = 'company', _('Company')
    STARTUP = 'startup', _('Startup')
    NGO = 'ngo', _('NGO / Non-Profit')
    GOVERNMENT = 'government', _('Government')
    EDUCATIONAL = 'educational', _('Educational Institution')
    RECRUITMENT = 'recruitment', _('Recruitment Agency')
    OTHER = 'other', _('Other')


class OrganizationSize(models.TextChoices):
    SOLO = '1', _('1 employee')
    MICRO = '2-10', _('2-10 employees')
    SMALL = '11-50', _('11-50 employees')
    MEDIUM = '51-200', _('51-200 employees')
    LARGE = '201-500', _('201-500 employees')
    ENTERPRISE = '501-1000', _('501-1000 employees')
    CORPORATE = '1001+', _('1001+ employees')


class OrganizationStatus(models.TextChoices):
    PENDING = 'pending', _('Pending Verification')
    VERIFIED = 'verified', _('Verified')
    SUSPENDED = 'suspended', _('Suspended')
    REJECTED = 'rejected', _('Rejected')


class MemberRole(models.TextChoices):
    OWNER = 'owner', _('Owner')
    ADMIN = 'admin', _('Administrator')
    RECRUITER = 'recruiter', _('Recruiter')
    HIRING_MANAGER = 'hiring_manager', _('Hiring Manager')
    VIEWER = 'viewer', _('Viewer')


class OpportunityType(models.TextChoices):
    FULL_TIME = 'full_time', _('Full-time')
    PART_TIME = 'part_time', _('Part-time')
    CONTRACT = 'contract', _('Contract')
    INTERNSHIP = 'internship', _('Internship')
    VOLUNTEER = 'volunteer', _('Volunteer')
    FREELANCE = 'freelance', _('Freelance')
    SKILLUP = 'skillup', _('SkillUp Program')


class OpportunityStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    OPEN = 'open', _('Open')
    PAUSED = 'paused', _('Paused')
    CLOSED = 'closed', _('Closed')
    FILLED = 'filled', _('Filled')
    CANCELLED = 'cancelled', _('Cancelled')


class ExperienceLevel(models.TextChoices):
    ENTRY = 'entry', _('Entry Level')
    JUNIOR = 'junior', _('Junior')
    MID = 'mid', _('Mid-Level')
    SENIOR = 'senior', _('Senior')
    LEAD = 'lead', _('Lead')
    EXECUTIVE = 'executive', _('Executive')


class RemotePolicy(models.TextChoices):
    ONSITE = 'onsite', _('On-site')
    REMOTE = 'remote', _('Remote')
    HYBRID = 'hybrid', _('Hybrid')


# =============================================================================
# INDUSTRY
# =============================================================================

class Industry(models.Model):
    """Industry categories."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # Icon class/name
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organizations_industries'
        verbose_name = _('Industry')
        verbose_name_plural = _('Industries')
        ordering = ['name']

    def __str__(self):
        return self.name


# =============================================================================
# ORGANIZATION
# =============================================================================

class Organization(models.Model):
    """Organization/Company profile."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic Info
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    tagline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    # Classification
    org_type = models.CharField(
        max_length=20,
        choices=OrganizationType.choices,
        default=OrganizationType.COMPANY
    )
    industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organizations'
    )
    size = models.CharField(
        max_length=20,
        choices=OrganizationSize.choices,
        default=OrganizationSize.SMALL
    )
    founded_year = models.PositiveIntegerField(null=True, blank=True)

    # Branding
    logo = models.ImageField(upload_to='org_logos/', null=True, blank=True)
    cover_image = models.ImageField(upload_to='org_covers/', null=True, blank=True)
    brand_color = models.CharField(max_length=7, default='#0EA5E9')  # Hex color

    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)

    # Social Links
    linkedin_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)

    # Location (HQ)
    country = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Status & Verification
    status = models.CharField(
        max_length=20,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.PENDING
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)

    # Settings
    is_hiring = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    # Stats
    total_opportunities = models.PositiveIntegerField(default=0)
    total_hires = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations_organizations'
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


# =============================================================================
# ORGANIZATION MEMBERS
# =============================================================================

class OrganizationMember(models.Model):
    """Users who belong to an organization."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=MemberRole.choices,
        default=MemberRole.VIEWER
    )
    title = models.CharField(max_length=100, blank=True)  # Job title within org

    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations_members'
        verbose_name = _('Organization Member')
        verbose_name_plural = _('Organization Members')
        unique_together = ['organization', 'user']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} @ {self.organization.name} ({self.role})"


# =============================================================================
# OPPORTUNITY
# =============================================================================

class Opportunity(models.Model):
    """Job/Internship/Volunteer opportunity posted by organizations."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='opportunities'
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='posted_opportunities'
    )

    # Basic Info
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300, unique=True)
    description = models.TextField()
    summary = models.CharField(max_length=500, blank=True)

    # Classification
    opportunity_type = models.CharField(
        max_length=20,
        choices=OpportunityType.choices,
        default=OpportunityType.FULL_TIME
    )
    experience_level = models.CharField(
        max_length=20,
        choices=ExperienceLevel.choices,
        default=ExperienceLevel.MID
    )
    category = models.CharField(max_length=100, blank=True)  # e.g., Engineering, Marketing

    # Location
    location = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    remote_policy = models.CharField(
        max_length=20,
        choices=RemotePolicy.choices,
        default=RemotePolicy.ONSITE
    )

    # Requirements
    requirements = models.TextField(blank=True)
    responsibilities = models.TextField(blank=True)
    qualifications = models.TextField(blank=True)
    required_skills = models.JSONField(default=list, blank=True)
    preferred_skills = models.JSONField(default=list, blank=True)
    min_experience_years = models.PositiveIntegerField(default=0)

    # Compensation
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default='ZAR')
    salary_period = models.CharField(max_length=20, default='monthly')
    hide_salary = models.BooleanField(default=False)
    benefits = models.JSONField(default=list, blank=True)

    # Status & Dates
    status = models.CharField(
        max_length=20,
        choices=OpportunityStatus.choices,
        default=OpportunityStatus.DRAFT
    )
    published_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)

    # Settings
    is_featured = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False)
    positions_available = models.PositiveIntegerField(default=1)
    external_apply_url = models.URLField(blank=True)

    # Stats
    views_count = models.PositiveIntegerField(default=0)
    applications_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations_opportunities'
        verbose_name = _('Opportunity')
        verbose_name_plural = _('Opportunities')
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['opportunity_type']),
            models.Index(fields=['country', 'city']),
        ]

    def __str__(self):
        return f"{self.title} at {self.organization.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            from django.utils import timezone
            base_slug = slugify(f"{self.title}-{self.organization.name}")
            slug = base_slug
            counter = 1
            while Opportunity.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        from django.utils import timezone
        if self.status != OpportunityStatus.OPEN:
            return False
        if self.deadline and self.deadline < timezone.now():
            return False
        return True

    @property
    def salary_display(self):
        if self.hide_salary:
            return "Competitive"
        if self.salary_min and self.salary_max:
            return f"{self.salary_currency} {self.salary_min:,.0f} - {self.salary_max:,.0f}"
        if self.salary_min:
            return f"From {self.salary_currency} {self.salary_min:,.0f}"
        return "Not specified"


# =============================================================================
# ORGANIZATION LOCATIONS (Multiple offices)
# =============================================================================

class OrganizationLocation(models.Model):
    """Additional office locations for organizations."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='locations'
    )

    name = models.CharField(max_length=100)  # e.g., "Cape Town Office"
    country = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    is_headquarters = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organizations_locations'
        verbose_name = _('Organization Location')
        verbose_name_plural = _('Organization Locations')

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

