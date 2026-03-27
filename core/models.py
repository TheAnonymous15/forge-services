# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Core Models
================================
Shared, cross-cutting models used across multiple subsystems.
These are NOT tied to a single business domain.
Includes: platform configuration, onboarding states, country/region data.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class Country(models.Model):
    """
    Master list of countries with ISO codes, currency, and phone prefix.
    Seeded once via a data migration.
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=100, unique=True)
    iso2         = models.CharField(max_length=2, unique=True, db_index=True)
    iso3         = models.CharField(max_length=3, unique=True, db_index=True)
    phone_prefix = models.CharField(max_length=10, blank=True)
    currency     = models.CharField(max_length=3, blank=True)
    region       = models.CharField(max_length=50, blank=True)   # e.g. East Africa
    sub_region   = models.CharField(max_length=50, blank=True)
    flag_emoji   = models.CharField(max_length=10, blank=True)
    is_active    = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'
        db_table  = 'core_countries'
        ordering  = ['name']
        verbose_name        = _('Country')
        verbose_name_plural = _('Countries')

    def __str__(self):
        return f"{self.flag_emoji} {self.name} ({self.iso2})"


class Industry(models.Model):
    """
    Master list of industry categories for profiles and organisations.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=50, blank=True)    # e.g. FontAwesome class
    parent      = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_industries'
    )
    is_active   = models.BooleanField(default=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = 'core'
        db_table  = 'core_industries'
        ordering  = ['sort_order', 'name']
        verbose_name        = _('Industry')
        verbose_name_plural = _('Industries')

    def __str__(self):
        return self.name


class Language(models.Model):
    """
    Languages supported by the platform for UI translation.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    native_name = models.CharField(max_length=100, blank=True)
    code        = models.CharField(max_length=10, unique=True, db_index=True)   # BCP 47
    flag_emoji  = models.CharField(max_length=10, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    is_rtl      = models.BooleanField(default=False)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = 'core'
        db_table  = 'core_languages'
        ordering  = ['sort_order', 'name']

    def __str__(self):
        return f"{self.flag_emoji} {self.name} ({self.code})"


class OnboardingState(models.Model):
    """
    Tracks a user's onboarding progress step by step.
    """

    class Step(models.TextChoices):
        REGISTERED          = 'registered',         _('Registered')
        EMAIL_VERIFIED      = 'email_verified',     _('Email Verified')
        PROFILE_CREATED     = 'profile_created',    _('Profile Created')
        PHOTO_UPLOADED      = 'photo_uploaded',     _('Photo Uploaded')
        CV_UPLOADED         = 'cv_uploaded',        _('CV Uploaded')
        SKILLS_ADDED        = 'skills_added',       _('Skills Added')
        PREFERENCES_SET     = 'preferences_set',    _('Preferences Set')
        FIRST_MATCH         = 'first_match',        _('First Match Received')
        ONBOARDING_COMPLETE = 'complete',           _('Onboarding Complete')

    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                  = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='onboarding_state'
    )
    current_step          = models.CharField(max_length=30, choices=Step.choices, default=Step.REGISTERED)
    completed_steps       = models.JSONField(default=list, blank=True)
    completion_percentage = models.PositiveSmallIntegerField(default=0)
    is_complete           = models.BooleanField(default=False, db_index=True)
    completed_at          = models.DateTimeField(null=True, blank=True)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table  = 'core_onboarding_states'
        ordering  = ['-updated_at']

    def __str__(self):
        return f"Onboarding for {self.user} — {self.current_step} ({self.completion_percentage}%)"

    def mark_step_complete(self, step: str):
        """Record a completed step and recalculate percentage."""
        from django.utils import timezone
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.current_step = step
        total = len(self.Step.values)
        self.completion_percentage = int(len(self.completed_steps) / total * 100)
        if step == self.Step.ONBOARDING_COMPLETE or self.completion_percentage >= 100:
            self.is_complete = True
            self.completed_at = timezone.now()
        self.save()


class PlatformSetting(models.Model):
    """
    Key-value store for cross-subsystem runtime settings accessible to all apps.
    Not to be confused with devops.SystemConfig which is infrastructure-focused.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key         = models.CharField(max_length=150, unique=True, db_index=True)
    value       = models.TextField()
    value_type  = models.CharField(
        max_length=10, default='str',
        choices=[('str', 'String'), ('int', 'Integer'), ('bool', 'Boolean'), ('json', 'JSON')]
    )
    description = models.TextField(blank=True)
    is_public   = models.BooleanField(default=False)   # expose to frontend via API
    updated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table  = 'core_platform_settings'
        ordering  = ['key']

    def __str__(self):
        return f"{self.key} = {self.value[:50]}"

    @classmethod
    def get(cls, key, default=None):
        """Convenience method to fetch a setting value."""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

