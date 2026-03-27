# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Accounts Admin (MVP1)
==========================================
Admin configuration for user and authentication models.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, EmailVerificationToken, PasswordResetToken, TwoFactorDevice, LoginHistory


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for custom User model."""
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_verified', 'is_active', 'date_joined']
    list_filter = ['role', 'is_verified', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name', 'phone_number', 'avatar')}),
        (_('Role & Status'), {'fields': ('role', 'is_verified', 'is_active', 'is_staff', 'is_superuser')}),
        (_('Permissions'), {'fields': ('groups', 'user_permissions')}),
        (_('Settings'), {'fields': ('email_notifications', 'sms_notifications', 'timezone', 'language')}),
        (_('Security'), {'fields': ('is_2fa_enabled', 'failed_login_attempts', 'locked_until')}),
        (_('Consent'), {'fields': ('consent_privacy', 'consent_terms', 'consent_marketing', 'consented_at')}),
        (_('Important Dates'), {'fields': ('last_login', 'date_joined', 'last_password_change')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'role'),
        }),
    )

    readonly_fields = ['date_joined', 'last_login', 'last_password_change', 'consented_at']


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'token', 'created_at', 'expires_at', 'used_at']
    list_filter = ['created_at', 'used_at']
    search_fields = ['user__email', 'token']
    readonly_fields = ['token', 'created_at']


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'token', 'ip_address', 'created_at', 'expires_at', 'used_at']
    list_filter = ['created_at', 'used_at']
    search_fields = ['user__email', 'token', 'ip_address']
    readonly_fields = ['token', 'created_at']


@admin.register(TwoFactorDevice)
class TwoFactorDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_active', 'created_at', 'confirmed_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['secret_key', 'created_at']


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['email', 'status', 'ip_address', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['email', 'ip_address']
    readonly_fields = ['user', 'email', 'status', 'ip_address', 'user_agent', 'failure_reason', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
