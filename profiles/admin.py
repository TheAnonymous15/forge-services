# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Profiles Admin (MVP1)
==========================================
Admin configuration for talent profiles.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    TalentProfile, Education, WorkExperience,
    Skill, TalentSkill, Certification, TalentLanguage
)


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0


class WorkExperienceInline(admin.TabularInline):
    model = WorkExperience
    extra = 0


class TalentSkillInline(admin.TabularInline):
    model = TalentSkill
    extra = 0


class CertificationInline(admin.TabularInline):
    model = Certification
    extra = 0


class TalentLanguageInline(admin.TabularInline):
    model = TalentLanguage
    extra = 0


@admin.register(TalentProfile)
class TalentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'headline', 'country', 'city', 'employment_status', 'availability', 'completeness_score', 'is_public']
    list_filter = ['employment_status', 'availability', 'remote_preference', 'is_public', 'is_searchable', 'country']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'headline', 'city']
    readonly_fields = ['id', 'completeness_score', 'views_count', 'created_at', 'updated_at']

    fieldsets = (
        (None, {'fields': ('user', 'headline', 'bio', 'avatar')}),
        (_('Personal'), {'fields': ('date_of_birth', 'gender', 'nationality')}),
        (_('Contact'), {'fields': ('phone_number', 'phone_secondary', 'website', 'linkedin_url', 'github_url', 'portfolio_url')}),
        (_('Location'), {'fields': ('country', 'state_province', 'city', 'address', 'postal_code')}),
        (_('Work Preferences'), {'fields': ('employment_status', 'availability', 'available_from', 'willing_to_relocate', 'preferred_locations', 'remote_preference')}),
        (_('Compensation'), {'fields': ('expected_salary_min', 'expected_salary_max', 'salary_currency', 'salary_period')}),
        (_('Interests'), {'fields': ('interested_in_jobs', 'interested_in_internships', 'interested_in_volunteer', 'interested_in_skillup')}),
        (_('Settings'), {'fields': ('is_public', 'is_searchable')}),
        (_('Stats'), {'fields': ('completeness_score', 'views_count')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )

    inlines = [EducationInline, WorkExperienceInline, TalentSkillInline, CertificationInline, TalentLanguageInline]


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ['profile', 'institution', 'degree', 'level', 'field_of_study', 'start_date', 'end_date']
    list_filter = ['level', 'is_current']
    search_fields = ['profile__user__email', 'institution', 'degree', 'field_of_study']


@admin.register(WorkExperience)
class WorkExperienceAdmin(admin.ModelAdmin):
    list_display = ['profile', 'company', 'title', 'employment_type', 'start_date', 'end_date', 'is_current']
    list_filter = ['employment_type', 'is_current', 'is_remote']
    search_fields = ['profile__user__email', 'company', 'title']


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'is_verified']
    list_filter = ['is_verified', 'category']
    search_fields = ['name', 'category']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(TalentSkill)
class TalentSkillAdmin(admin.ModelAdmin):
    list_display = ['profile', 'skill', 'level', 'years_of_experience', 'is_primary']
    list_filter = ['level', 'is_primary']
    search_fields = ['profile__user__email', 'skill__name']


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ['profile', 'name', 'issuing_organization', 'issue_date', 'expiry_date', 'does_not_expire']
    list_filter = ['does_not_expire', 'issue_date']
    search_fields = ['profile__user__email', 'name', 'issuing_organization']


@admin.register(TalentLanguage)
class TalentLanguageAdmin(admin.ModelAdmin):
    list_display = ['profile', 'language', 'proficiency']
    list_filter = ['proficiency']
    search_fields = ['profile__user__email', 'language']
