# -*- coding: utf-8 -*-
"""
Storage Services
================
Centralized file storage for the entire ForgeForth platform.

ALL file storage across subsystems goes through this service.
No other subsystem should handle file storage directly.

Usage Examples:
---------------

# Store a file
from storage.services import store_file, FileCategory

result = store_file(
    data=file_bytes,
    filename="resume.pdf",
    category=FileCategory.RESUME,
    owner_id="user_123",
)
print(result['signed_url'])

# Retrieve a file
from storage.services import retrieve_file

result = retrieve_file(token)
content = result['content']

# Get signed URL
from storage.services import get_signed_url

url_token = get_signed_url(file_id, expires_in_hours=24)

# Helper functions for common operations
from storage.services import store_avatar, store_resume, store_org_logo

result = store_avatar(image_bytes, user_id="user_123")
result = store_resume(pdf_bytes, user_id="user_123", filename="cv.pdf")
result = store_org_logo(logo_bytes, org_id="org_456")

# Get full service instance
from storage.services import get_storage_service

service = get_storage_service()
stats = service.get_stats()
orphans = service.find_orphan_files()
"""

from .storage_service import (
    # Main service
    SecureStorageService,
    get_storage_service,

    # Convenience functions
    store_file,
    retrieve_file,
    delete_file,
    get_signed_url,

    # Helper functions for common operations
    store_avatar,
    store_resume,
    store_org_logo,
    store_blog_image,

    # URL Signer
    URLSigner,

    # Backend
    FileStorageBackend,

    # Utility functions
    detect_mime_type,
    generate_file_id,
    generate_storage_path,
    sanitize_filename,
)

# Re-export models for convenience
from storage.models import (
    StoredFile,
    SignedURL,
    StorageQuota,
    StorageAccessLog,
    ProcessingJob,
    OrphanFile,
    FileCategory,
    AccessLevel,
)

__all__ = [
    # Service
    'SecureStorageService',
    'get_storage_service',

    # Main functions
    'store_file',
    'retrieve_file',
    'delete_file',
    'get_signed_url',

    # Helper functions
    'store_avatar',
    'store_resume',
    'store_org_logo',
    'store_blog_image',

    # Models
    'StoredFile',
    'SignedURL',
    'StorageQuota',
    'StorageAccessLog',
    'ProcessingJob',
    'OrphanFile',
    'FileCategory',
    'AccessLevel',

    # Utilities
    'URLSigner',
    'FileStorageBackend',
    'detect_mime_type',
    'generate_file_id',
    'generate_storage_path',
    'sanitize_filename',
]

