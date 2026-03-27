# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Profiles Models (MVP1)
==========================================
Talent profiles, education, work experience, skills, and certifications.
"""
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
import uuid


# =============================================================================
# ENUMS / CHOICES
# =============================================================================

class Gender(models.TextChoices):
    MALE = 'male', _('Male')
    FEMALE = 'female', _('Female')
    OTHER = 'other', _('Other')
    PREFER_NOT_TO_SAY = 'prefer_not_to_say', _('Prefer not to say')


class EmploymentStatus(models.TextChoices):
    EMPLOYED = 'employed', _('Currently Employed')
    UNEMPLOYED = 'unemployed', _('Unemployed')
    STUDENT = 'student', _('Student')
    FREELANCE = 'freelance', _('Freelancer')
    SELF_EMPLOYED = 'self_employed', _('Self-Employed')


class Availability(models.TextChoices):
    IMMEDIATE = 'immediate', _('Immediately Available')
    TWO_WEEKS = '2_weeks', _('Available in 2 Weeks')
    ONE_MONTH = '1_month', _('Available in 1 Month')
    THREE_MONTHS = '3_months', _('Available in 3 Months')
    NOT_AVAILABLE = 'not_available', _('Not Currently Available')


class RemotePreference(models.TextChoices):
    ONSITE = 'onsite', _('On-site Only')
    REMOTE = 'remote', _('Remote Only')
    HYBRID = 'hybrid', _('Hybrid')
    FLEXIBLE = 'flexible', _('Flexible')


class SalaryPeriod(models.TextChoices):
    HOURLY = 'hourly', _('Hourly')
    DAILY = 'daily', _('Daily')
    WEEKLY = 'weekly', _('Weekly')
    MONTHLY = 'monthly', _('Monthly')
    ANNUALLY = 'annually', _('Annually')


class EducationLevel(models.TextChoices):
    HIGH_SCHOOL = 'high_school', _('High School')
    CERTIFICATE = 'certificate', _('Certificate')
    DIPLOMA = 'diploma', _('Diploma')
    BACHELORS = 'bachelors', _('Bachelor\'s Degree')
    MASTERS = 'masters', _('Master\'s Degree')
    DOCTORATE = 'doctorate', _('Doctorate')
    OTHER = 'other', _('Other')


class SkillLevel(models.TextChoices):
    BEGINNER = 'beginner', _('Beginner')
    INTERMEDIATE = 'intermediate', _('Intermediate')
    ADVANCED = 'advanced', _('Advanced')
    EXPERT = 'expert', _('Expert')


class EmploymentType(models.TextChoices):
    FULL_TIME = 'full_time', _('Full-time')
    PART_TIME = 'part_time', _('Part-time')
    CONTRACT = 'contract', _('Contract')
    INTERNSHIP = 'internship', _('Internship')
    FREELANCE = 'freelance', _('Freelance')
    VOLUNTEER = 'volunteer', _('Volunteer')


# =============================================================================
# TALENT PROFILE
# =============================================================================

class TalentProfile(models.Model):
    """
    Extended profile for talent users.
    One-to-one relationship with User.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='talent_profile'
    )

    # Personal Information
    headline = models.CharField(max_length=200, blank=True, help_text=_('e.g., Senior Software Engineer'))
    bio = models.TextField(max_length=2000, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True)
    nationality = models.CharField(max_length=100, blank=True)

    # Avatar/Photo
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    # Contact Information (additional)
    phone_number = models.CharField(max_length=20, blank=True)
    phone_secondary = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)

    # Location
    country = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Work Preferences
    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.UNEMPLOYED
    )
    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.IMMEDIATE
    )
    available_from = models.DateField(null=True, blank=True)
    willing_to_relocate = models.BooleanField(default=False)
    preferred_locations = models.JSONField(default=list, blank=True)
    remote_preference = models.CharField(
        max_length=20,
        choices=RemotePreference.choices,
        default=RemotePreference.FLEXIBLE
    )

    # Compensation
    expected_salary_min = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    expected_salary_max = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    salary_currency = models.CharField(max_length=3, default='ZAR')
    salary_period = models.CharField(
        max_length=20,
        choices=SalaryPeriod.choices,
        default=SalaryPeriod.MONTHLY
    )

    # Opportunity Interests
    interested_in_jobs = models.BooleanField(default=True)
    interested_in_internships = models.BooleanField(default=False)
    interested_in_volunteer = models.BooleanField(default=False)
    interested_in_skillup = models.BooleanField(default=False)

    # Profile Meta
    completeness_score = models.IntegerField(default=0)
    is_public = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profiles_talent'
        verbose_name = _('Talent Profile')
        verbose_name_plural = _('Talent Profiles')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - {self.headline or 'No headline'}"

    def calculate_completeness(self):
        """Calculate profile completeness percentage."""
        fields_weight = {
            'headline': 10,
            'bio': 10,
            'avatar': 10,
            'phone_number': 5,
            'country': 5,
            'city': 5,
            'employment_status': 5,
            'availability': 5,
        }
        score = 0
        for field, weight in fields_weight.items():
            value = getattr(self, field, None)
            if value:
                score += weight

        # Check related models
        if self.education.exists():
            score += 15
        if self.work_experience.exists():
            score += 15
        if self.skills.exists():
            score += 15

        self.completeness_score = min(score, 100)
        return self.completeness_score


# =============================================================================
# EDUCATION
# =============================================================================

class Education(models.Model):
    """Educational background for talents."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        TalentProfile,
        on_delete=models.CASCADE,
        related_name='education'
    )

    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=255, blank=True)
    level = models.CharField(
        max_length=20,
        choices=EducationLevel.choices,
        default=EducationLevel.BACHELORS
    )
    field_of_study = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    grade = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    activities = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profiles_education'
        verbose_name = _('Education')
        verbose_name_plural = _('Education')
        ordering = ['-end_date', '-start_date']

    def __str__(self):
        return f"{self.degree or self.level} at {self.institution}"


# =============================================================================
# WORK EXPERIENCE
# =============================================================================

class WorkExperience(models.Model):
    """Work history for talents."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        TalentProfile,
        on_delete=models.CASCADE,
        related_name='work_experience'
    )

    company = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME
    )
    location = models.CharField(max_length=255, blank=True)
    is_remote = models.BooleanField(default=False)

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    description = models.TextField(blank=True)
    responsibilities = models.JSONField(default=list, blank=True)
    achievements = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profiles_work_experience'
        verbose_name = _('Work Experience')
        verbose_name_plural = _('Work Experiences')
        ordering = ['-end_date', '-start_date']

    def __str__(self):
        return f"{self.title} at {self.company}"

    @property
    def duration_months(self):
        """Calculate duration in months."""
        from datetime import date
        end = self.end_date or date.today()
        return (end.year - self.start_date.year) * 12 + (end.month - self.start_date.month)


# =============================================================================
# SKILLS
# =============================================================================

class Skill(models.Model):
    """Skills catalog - can be reused across profiles."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'profiles_skills'
        verbose_name = _('Skill')
        verbose_name_plural = _('Skills')
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TalentSkill(models.Model):
    """Many-to-many relationship between talents and skills."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        TalentProfile,
        on_delete=models.CASCADE,
        related_name='skills'
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='talents'
    )
    level = models.CharField(
        max_length=20,
        choices=SkillLevel.choices,
        default=SkillLevel.INTERMEDIATE
    )
    years_of_experience = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profiles_talent_skills'
        verbose_name = _('Talent Skill')
        verbose_name_plural = _('Talent Skills')
        unique_together = ['profile', 'skill']
        ordering = ['-is_primary', '-years_of_experience']

    def __str__(self):
        return f"{self.profile.user.full_name} - {self.skill.name} ({self.level})"


# =============================================================================
# CERTIFICATIONS
# =============================================================================

class Certification(models.Model):
    """Professional certifications and credentials."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        TalentProfile,
        on_delete=models.CASCADE,
        related_name='certifications'
    )

    name = models.CharField(max_length=255)
    issuing_organization = models.CharField(max_length=255)
    credential_id = models.CharField(max_length=255, blank=True)
    credential_url = models.URLField(blank=True)

    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    does_not_expire = models.BooleanField(default=False)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profiles_certifications'
        verbose_name = _('Certification')
        verbose_name_plural = _('Certifications')
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.name} - {self.issuing_organization}"

    @property
    def is_valid(self):
        """Check if certification is still valid."""
        if self.does_not_expire:
            return True
        if not self.expiry_date:
            return True
        from datetime import date
        return self.expiry_date >= date.today()


# =============================================================================
# LANGUAGES
# =============================================================================

class LanguageProficiency(models.TextChoices):
    ELEMENTARY = 'elementary', _('Elementary')
    LIMITED_WORKING = 'limited_working', _('Limited Working')
    PROFESSIONAL_WORKING = 'professional_working', _('Professional Working')
    FULL_PROFESSIONAL = 'full_professional', _('Full Professional')
    NATIVE = 'native', _('Native or Bilingual')


class TalentLanguage(models.Model):
    """Languages spoken by talents."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        TalentProfile,
        on_delete=models.CASCADE,
        related_name='languages'
    )

    language = models.CharField(max_length=100)
    proficiency = models.CharField(
        max_length=30,
        choices=LanguageProficiency.choices,
        default=LanguageProficiency.PROFESSIONAL_WORKING
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'profiles_languages'
        verbose_name = _('Language')
        verbose_name_plural = _('Languages')
        unique_together = ['profile', 'language']

    def __str__(self):
        return f"{self.language} ({self.proficiency})"


# =============================================================================
# SIGNALS
# =============================================================================

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_talent_profile(sender, instance, created, **kwargs):
    """Auto-create TalentProfile when a talent user is created."""
    if created and instance.role == 'talent':
        TalentProfile.objects.get_or_create(user=instance)

