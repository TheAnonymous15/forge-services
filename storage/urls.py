# -*- coding: utf-8 -*-
"""
Storage Subsystem - URL Configuration
======================================
All file access is via signed URLs.
Direct path access is NOT allowed.

Public Endpoints:
    /storage/file/{token}/          - Serve file via signed URL

API Endpoints (auth required):
    /storage/api/upload/            - Upload file
    /storage/api/file/{file_id}/    - Get file info
    /storage/api/file/{file_id}/delete/      - Delete file
    /storage/api/file/{file_id}/signed-url/  - Generate signed URL

Admin Endpoints:
    /storage/api/stats/             - Storage statistics
    /storage/api/files/             - List all files
    /storage/api/orphans/           - List orphan files
    /storage/api/orphans/cleanup/   - Cleanup orphan files
"""
from django.urls import path
from . import views

app_name = 'storage'

urlpatterns = [
    # ----------------------------------------
    # Public: File access via signed URL
    # ----------------------------------------
    path('file/<str:token>/', views.serve_file, name='serve_file'),

    # ----------------------------------------
    # API: Authenticated endpoints
    # ----------------------------------------
    path('api/upload/', views.api_upload, name='api_upload'),
    path('api/file/<str:file_id>/', views.api_file_info, name='api_file_info'),
    path('api/file/<str:file_id>/delete/', views.api_delete_file, name='api_delete_file'),
    path('api/file/<str:file_id>/signed-url/', views.api_generate_signed_url, name='api_signed_url'),

    # ----------------------------------------
    # Admin: Staff-only endpoints
    # ----------------------------------------
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/files/', views.api_list_files, name='api_list_files'),
    path('api/orphans/', views.api_orphan_files, name='api_orphan_files'),
    path('api/orphans/cleanup/', views.api_cleanup_orphans, name='api_cleanup_orphans'),
]



