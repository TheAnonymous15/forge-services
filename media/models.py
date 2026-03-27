# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Media Models (MVP1)
=======================================
Secure media ingestion, processing, and storage.
Covers profile documents, CVs, portfolio files, and organisation media.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class MediaFile(models.Model):
    """
    Central record for every uploaded file.
    The actual bytes live on disk / S3; this table tracks metadata and status.
    """

    class FileType(models.TextChoices):
        CV            = 'cv',            _('CV / Resume')
        COVER_LETTER  = 'cover_letter',  _('Cover Letter')
        CERTIFICATE   = 'certificate',   _('Certificate')
        PORTFOLIO     = 'portfolio',     _('Portfolio Item')
        PROFILE_PHOTO = 'profile_photo', _('Profile Photo')
        ORG_LOGO      = 'org_logo',      _('Organisation Logo')
        ORG_BANNER    = 'org_banner',    _('Organisation Banner')
        BLOG_IMAGE    = 'blog_image',    _('Blog Image')
        OTHER         = 'other',         _('Other')

    class Status(models.TextChoices):
        PENDING    = 'pending',    _('Pending Processing')
        PROCESSING = 'processing', _('Processing')
        READY      = 'ready',      _('Ready')
        FAILED     = 'failed',     _('Processing Failed')
        QUARANTINE = 'quarantine', _('Quarantined (Security Risk)')
        DELETED    = 'deleted',    _('Deleted')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='media_files',
    )
    file_type    = models.CharField(max_length=20, choices=FileType.choices, default=FileType.OTHER)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    # Storage
    original_filename  = models.CharField(max_length=255)
    stored_filename    = models.CharField(max_length=255, unique=True)   # UUID-based safe name
    file_path          = models.CharField(max_length=512)                # relative path from MEDIA_ROOT
    file_size          = models.PositiveBigIntegerField(default=0)       # bytes
    mime_type          = models.CharField(max_length=100, blank=True)
    extension          = models.CharField(max_length=20, blank=True)

    # Processed output (e.g. WebP conversion, thumbnail)
    processed_path     = models.CharField(max_length=512, blank=True)
    thumbnail_path     = models.CharField(max_length=512, blank=True)

    # Security
    checksum_sha256    = models.CharField(max_length=64, blank=True)
    is_sanitised       = models.BooleanField(default=False)
    threat_detected    = models.BooleanField(default=False)
    threat_detail      = models.TextField(blank=True)

    # Metadata
    metadata           = models.JSONField(default=dict, blank=True)
    is_public          = models.BooleanField(default=False)

    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        app_label   = 'media'
        db_table    = 'media_files'
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['owner', 'file_type']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.file_type}: {self.original_filename} [{self.status}]"

    @property
    def url(self):
        from django.conf import settings as s
        if self.processed_path:
            return f"{s.MEDIA_URL}{self.processed_path}"
        return f"{s.MEDIA_URL}{self.file_path}"

    @property
    def is_image(self):
        return self.mime_type.startswith('image/') if self.mime_type else False

    @property
    def size_kb(self):
        return round(self.file_size / 1024, 1)


class Document(models.Model):
    """
    A processed document (CV, certificate, etc.) linked to a talent profile.
    Extends MediaFile with document-specific metadata.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media_file  = models.OneToOneField(
        MediaFile, on_delete=models.CASCADE, related_name='document'
    )
    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title       = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    is_primary  = models.BooleanField(default=False)   # Primary CV flag

    # Extracted text for full-text search
    extracted_text = models.TextField(blank=True)
    pages          = models.PositiveSmallIntegerField(default=0)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'media'
        db_table  = 'media_documents'
        ordering  = ['-is_primary', '-created_at']

    def __str__(self):
        return f"{self.title or self.media_file.original_filename} ({self.owner})"


class ProcessingJob(models.Model):
    """
    Async processing job for a MediaFile (virus scan, compression, OCR, etc.).
    """

    class JobType(models.TextChoices):
        SANITISE   = 'sanitise',   _('Security Sanitisation')
        COMPRESS   = 'compress',   _('Image Compression')
        THUMBNAIL  = 'thumbnail',  _('Thumbnail Generation')
        OCR        = 'ocr',        _('Text Extraction (OCR)')
        VIRUS_SCAN = 'virus_scan', _('Virus / Malware Scan')

    class Status(models.TextChoices):
        QUEUED     = 'queued',     _('Queued')
        RUNNING    = 'running',    _('Running')
        DONE       = 'done',       _('Done')
        FAILED     = 'failed',     _('Failed')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media_file  = models.ForeignKey(MediaFile, on_delete=models.CASCADE, related_name='jobs')
    job_type    = models.CharField(max_length=20, choices=JobType.choices)
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    celery_task = models.CharField(max_length=255, blank=True)
    result      = models.JSONField(default=dict, blank=True)
    error       = models.TextField(blank=True)
    started_at  = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'media'
        db_table  = 'media_processing_jobs'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.job_type} → {self.media_file} [{self.status}]"
