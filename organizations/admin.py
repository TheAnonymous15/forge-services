# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organizations Admin (MVP1)
===============================================
Admin configuration for organizations and opportunities.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Industry, Organization, OrganizationMember,
    Opportunity, OrganizationLocation
)


class OrganizationMemberInline(admin.TabularInline):
    model = OrganizationMember
    extra = 0


class OrganizationLocationInline(admin.TabularInline):
    model = OrganizationLocation
    extra = 0


class OpportunityInline(admin.TabularInline):
    model = Opportunity
    extra = 0
    fields = ['title', 'opportunity_type', 'status', 'published_at']
    readonly_fields = ['title', 'published_at']
    show_change_link = True


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'org_type', 'industry', 'size', 'status', 'is_hiring', 'created_at']
    list_filter = ['org_type', 'size', 'status', 'is_hiring', 'is_public']
    search_fields = ['name', 'email', 'city', 'country']
    readonly_fields = ['id', 'total_opportunities', 'total_hires', 'verified_at', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        (None, {'fields': ('name', 'slug', 'tagline', 'description')}),
        (_('Classification'), {'fields': ('org_type', 'industry', 'size', 'founded_year')}),
        (_('Branding'), {'fields': ('logo', 'cover_image', 'brand_color')}),
        (_('Contact'), {'fields': ('email', 'phone', 'website')}),
        (_('Social'), {'fields': ('linkedin_url', 'twitter_url', 'facebook_url', 'instagram_url')}),
        (_('Location'), {'fields': ('country', 'state_province', 'city', 'address', 'postal_code')}),
        (_('Status'), {'fields': ('status', 'verified_at', 'verification_notes', 'is_hiring', 'is_public')}),
        (_('Stats'), {'fields': ('total_opportunities', 'total_hires')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )

    inlines = [OrganizationMemberInline, OrganizationLocationInline]


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'title', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active']
    search_fields = ['user__email', 'organization__name', 'title']


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ['title', 'organization', 'opportunity_type', 'experience_level', 'status', 'is_featured', 'published_at']
    list_filter = ['opportunity_type', 'experience_level', 'status', 'remote_policy', 'is_featured', 'is_urgent']
    search_fields = ['title', 'organization__name', 'location', 'city', 'country']
    readonly_fields = ['id', 'views_count', 'applications_count', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'

    fieldsets = (
        (None, {'fields': ('organization', 'posted_by', 'title', 'slug', 'summary', 'description')}),
        (_('Classification'), {'fields': ('opportunity_type', 'experience_level', 'category')}),
        (_('Location'), {'fields': ('location', 'country', 'city', 'remote_policy')}),
        (_('Requirements'), {'fields': ('requirements', 'responsibilities', 'qualifications', 'required_skills', 'preferred_skills', 'min_experience_years')}),
        (_('Compensation'), {'fields': ('salary_min', 'salary_max', 'salary_currency', 'salary_period', 'hide_salary', 'benefits')}),
        (_('Status'), {'fields': ('status', 'published_at', 'deadline', 'start_date')}),
        (_('Settings'), {'fields': ('is_featured', 'is_urgent', 'positions_available', 'external_apply_url')}),
        (_('Stats'), {'fields': ('views_count', 'applications_count')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(OrganizationLocation)
class OrganizationLocationAdmin(admin.ModelAdmin):
    list_display = ['organization', 'name', 'city', 'country', 'is_headquarters']
    list_filter = ['is_headquarters', 'country']
    search_fields = ['organization__name', 'name', 'city']
