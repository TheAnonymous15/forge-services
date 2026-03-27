# -*- coding: utf-8 -*-
"""
Storage Subsystem
=================
Centralized, secure file storage for the entire ForgeForth platform.

This is the ONLY subsystem that handles file storage.
All other subsystems MUST use this service for file operations.

Features:
---------
- Categorized file organization (profiles/avatars, applications/resumes, etc.)
- Unique UUID-based file naming (never trust uploaded filenames)
- Signed URL access (never expose direct paths)
- Access level enforcement (public, private, restricted, org_members)
- Async processing support via Celery
- CDN compatibility
- File versioning
- Quota management
- Garbage collection for orphan files
- Full audit logging

Usage:
------
    from storage.services import store_file, FileCategory

    # Store a file
    result = store_file(
        data=file_bytes,
        filename="resume.pdf",
        category=FileCategory.RESUME,
        owner_id="user_123",
    )

    # Get signed URL
    from storage.services import get_signed_url
    token = get_signed_url(result['file_id'])

    # Build full URL
    url = f"/storage/file/{token}/"

File Categories:
----------------
    - profiles/avatars
    - profiles/cover_images
    - applications/resumes
    - applications/cover_letters
    - applications/portfolios
    - applications/certificates
    - organizations/logos
    - organizations/banners
    - organizations/documents
    - communications/attachments
    - communications/email_attachments
    - website/blog_images
    - website/gallery
    - intelligence/cv_uploads
    - media/processed/images
    - media/processed/documents
"""

default_app_config = 'storage.apps.StorageConfig'

