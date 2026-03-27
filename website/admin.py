from django.contrib import admin
from .models import PartnerRegistration, TalentWaitlist, ContactMessage


@admin.register(PartnerRegistration)
class PartnerRegistrationAdmin(admin.ModelAdmin):
    list_display = ['organization_name', 'full_name', 'email', 'industry', 'country', 'is_contacted', 'created_at']
    list_filter = ['industry', 'is_contacted', 'created_at', 'country']
    search_fields = ['organization_name', 'first_name', 'last_name', 'email', 'country']
    readonly_fields = ['ip_address', 'user_agent', 'created_at']
    list_editable = ['is_contacted']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    fieldsets = (
        ('Organization', {
            'fields': ('organization_name', 'industry', 'company_size', 'country')
        }),
        ('Contact Person', {
            'fields': ('first_name', 'last_name', 'job_title', 'email', 'phone')
        }),
        ('Interest', {
            'fields': ('interest_types', 'message')
        }),
        ('Status & Notes', {
            'fields': ('is_contacted', 'notes')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TalentWaitlist)
class TalentWaitlistAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'country', 'is_contacted', 'created_at']
    list_filter = ['is_contacted', 'created_at', 'country']
    search_fields = ['full_name', 'email', 'country']
    readonly_fields = ['ip_address', 'user_agent', 'created_at']
    list_editable = ['is_contacted']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    fieldsets = (
        ('Personal Info', {
            'fields': ('full_name', 'email', 'phone', 'country')
        }),
        ('Opportunities', {
            'fields': ('opportunity_types',)
        }),
        ('Skills & Fields', {
            'fields': ('skills', 'skills_other', 'preferred_fields', 'fields_other')
        }),
        ('Status & Notes', {
            'fields': ('is_contacted', 'notes')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'is_read', 'is_replied', 'created_at']
    list_filter = ['is_read', 'is_replied', 'created_at']
    search_fields = ['full_name', 'email', 'message']
    readonly_fields = ['ip_address', 'user_agent', 'created_at']
    list_editable = ['is_read', 'is_replied']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    fieldsets = (
        ('Contact Info', {
            'fields': ('full_name', 'email', 'phone', 'country')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Status', {
            'fields': ('is_read', 'is_replied')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )
