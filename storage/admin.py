# -*- coding: utf-8 -*-
"""
Storage Admin Configuration
"""
from django.contrib import admin
from .models import StoredFile, SignedURL, StorageQuota, StorageAccessLog, ProcessingJob, OrphanFile


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    list_display = ['file_id', 'filename', 'category', 'mime_type', 'size_mb', 'owner_id', 'status', 'created_at']
    list_filter = ['category', 'status', 'access_level', 'media_type', 'is_processed']
    search_fields = ['file_id', 'filename', 'original_filename', 'owner_id']
    readonly_fields = ['id', 'file_id', 'checksum_sha256', 'checksum_stored', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Identification', {
            'fields': ('id', 'file_id', 'filename', 'original_filename', 'extension')
        }),
        ('Storage', {
            'fields': ('category', 'storage_path', 'mime_type', 'media_type')
        }),
        ('Size & Checksums', {
            'fields': ('original_size', 'stored_size', 'checksum_sha256', 'checksum_stored')
        }),
        ('Access Control', {
            'fields': ('access_level', 'owner_id', 'owner_type', 'organization_id')
        }),
        ('Related Entity', {
            'fields': ('related_entity_type', 'related_entity_id')
        }),
        ('Processing', {
            'fields': ('is_processed', 'processing_info', 'threats_detected')
        }),
        ('Versioning', {
            'fields': ('version', 'parent_file', 'is_latest_version')
        }),
        ('Status & Lifecycle', {
            'fields': ('status', 'expires_at', 'is_encrypted')
        }),
        ('Metadata', {
            'fields': ('metadata', 'tags', 'description')
        }),
        ('Tracking', {
            'fields': ('access_count', 'download_count', 'last_accessed_at', 'cdn_url')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at')
        }),
    )


@admin.register(SignedURL)
class SignedURLAdmin(admin.ModelAdmin):
    list_display = ['id', 'file', 'expires_at', 'max_uses', 'use_count', 'is_revoked', 'created_at']
    list_filter = ['is_revoked', 'created_at']
    search_fields = ['file__file_id', 'token_hash']
    readonly_fields = ['id', 'token_hash', 'created_at', 'last_used_at']


@admin.register(StorageQuota)
class StorageQuotaAdmin(admin.ModelAdmin):
    list_display = ['owner_id', 'owner_type', 'usage_percentage', 'used_storage', 'total_quota', 'current_files']
    list_filter = ['owner_type']
    search_fields = ['owner_id']

    def usage_percentage(self, obj):
        return f"{obj.usage_percentage}%"
    usage_percentage.short_description = 'Usage'


@admin.register(StorageAccessLog)
class StorageAccessLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'operation', 'file_id', 'success', 'user_id', 'ip_address']
    list_filter = ['operation', 'success', 'timestamp']
    search_fields = ['file_id', 'user_id', 'ip_address']
    readonly_fields = ['id', 'timestamp']
    ordering = ['-timestamp']


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'job_type', 'file', 'status', 'progress_percent', 'attempts', 'created_at']
    list_filter = ['status', 'job_type', 'created_at']
    search_fields = ['file__file_id', 'celery_task_id']
    readonly_fields = ['id', 'created_at', 'started_at', 'completed_at']


@admin.register(OrphanFile)
class OrphanFileAdmin(admin.ModelAdmin):
    list_display = ['storage_path', 'file_size', 'status', 'detected_at', 'resolved_at']
    list_filter = ['status', 'detected_at']
    search_fields = ['storage_path']
    readonly_fields = ['id', 'detected_at']

