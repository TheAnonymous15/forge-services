# -*- coding: utf-8 -*-
"""
Storage Subsystem - Database Models
====================================
Centralized file storage for the entire ForgeForth platform.
NO OTHER SUBSYSTEM should handle file storage - all goes through here.

File Categories:
- profiles/avatars/
- profiles/cover_images/
- applications/resumes/
- applications/cover_letters/
- applications/portfolios/
- organizations/logos/
- organizations/banners/
- organizations/documents/
- communications/attachments/
- website/blog_images/
- intelligence/cv_uploads/
- media/processed/
"""
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings


class FileCategory(models.TextChoices):
    """Predefined file categories for organization."""
    # Profile files
    AVATAR = 'profiles/avatars', 'Profile Avatar'
    COVER_IMAGE = 'profiles/cover_images', 'Profile Cover Image'

    # Application files
    RESUME = 'applications/resumes', 'Resume/CV'
    COVER_LETTER = 'applications/cover_letters', 'Cover Letter'
    PORTFOLIO = 'applications/portfolios', 'Portfolio Item'
    CERTIFICATE = 'applications/certificates', 'Certificate'

    # Organization files
    ORG_LOGO = 'organizations/logos', 'Organization Logo'
    ORG_BANNER = 'organizations/banners', 'Organization Banner'
    ORG_DOCUMENT = 'organizations/documents', 'Organization Document'

    # Communication files
    MESSAGE_ATTACHMENT = 'communications/attachments', 'Message Attachment'
    EMAIL_ATTACHMENT = 'communications/email_attachments', 'Email Attachment'

    # Website files
    BLOG_IMAGE = 'website/blog_images', 'Blog Image'
    BLOG_ATTACHMENT = 'website/blog_attachments', 'Blog Attachment'
    GALLERY_IMAGE = 'website/gallery', 'Gallery Image'

    # Intelligence files
    CV_UPLOAD = 'intelligence/cv_uploads', 'CV for Processing'
    SKILL_EVIDENCE = 'intelligence/skill_evidence', 'Skill Evidence'

    # Media processing
    PROCESSED_IMAGE = 'media/processed/images', 'Processed Image'
    PROCESSED_DOCUMENT = 'media/processed/documents', 'Processed Document'
    PROCESSED_VIDEO = 'media/processed/videos', 'Processed Video'
    PROCESSED_AUDIO = 'media/processed/audio', 'Processed Audio'

    # Temporary/misc
    TEMP = 'temp', 'Temporary File'
    OTHER = 'other', 'Other'


class AccessLevel(models.TextChoices):
    """File access levels for permission control."""
    PUBLIC = 'public', 'Public - Anyone can access'
    AUTHENTICATED = 'authenticated', 'Authenticated - Logged in users only'
    PRIVATE = 'private', 'Private - Owner only'
    RESTRICTED = 'restricted', 'Restricted - Specific users/roles'
    ORG_MEMBERS = 'org_members', 'Organization Members Only'
    INTERNAL = 'internal', 'Internal - System use only'


class StoredFile(models.Model):
    """
    Central file storage record.
    ALL files in the platform are tracked here.
    """
    # Primary identifier (never expose auto-increment ID)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Unique file ID for URLs (shorter than UUID)
    file_id = models.CharField(max_length=32, unique=True, db_index=True)

    # File information
    filename = models.CharField(max_length=255, help_text="Sanitized display filename")
    original_filename = models.CharField(max_length=255, help_text="Original uploaded filename")
    extension = models.CharField(max_length=20, blank=True)
    mime_type = models.CharField(max_length=100)

    # Category and organization
    category = models.CharField(
        max_length=50,
        choices=FileCategory.choices,
        default=FileCategory.OTHER,
        db_index=True
    )

    # Storage path (relative to storage root)
    # Format: category/YYYY/MM/file_id.ext
    storage_path = models.CharField(max_length=500, unique=True)

    # Size tracking
    original_size = models.BigIntegerField(help_text="Original file size in bytes")
    stored_size = models.BigIntegerField(help_text="Size after processing/encryption")

    # Checksums for integrity
    checksum_sha256 = models.CharField(max_length=64, help_text="SHA-256 of original content")
    checksum_stored = models.CharField(max_length=64, help_text="SHA-256 of stored content")

    # Security
    is_encrypted = models.BooleanField(default=True)
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PRIVATE,
        db_index=True
    )

    # Ownership
    owner_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    owner_type = models.CharField(
        max_length=20,
        choices=[
            ('user', 'User'),
            ('organization', 'Organization'),
            ('system', 'System'),
        ],
        blank=True,
        null=True
    )

    # Organization scope (for org_members access level)
    organization_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    # Related entity (e.g., profile_id, application_id, blog_post_id)
    related_entity_type = models.CharField(max_length=50, blank=True, null=True)
    related_entity_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    # Processing info
    media_type = models.CharField(
        max_length=20,
        choices=[
            ('image', 'Image'),
            ('document', 'Document'),
            ('video', 'Video'),
            ('audio', 'Audio'),
            ('other', 'Other'),
        ],
        default='other'
    )
    is_processed = models.BooleanField(default=False)
    processing_info = models.JSONField(default=dict, blank=True)
    threats_detected = models.JSONField(default=list, blank=True)

    # Versioning
    version = models.PositiveIntegerField(default=1)
    parent_file = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versions'
    )
    is_latest_version = models.BooleanField(default=True)

    # CDN support
    cdn_url = models.URLField(max_length=500, blank=True, null=True)
    cdn_invalidated_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('uploading', 'Uploading'),
            ('processing', 'Processing'),
            ('active', 'Active'),
            ('archived', 'Archived'),
            ('deleted', 'Deleted'),
            ('quarantined', 'Quarantined'),
        ],
        default='active',
        db_index=True
    )

    # Lifecycle
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Access tracking
    access_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'storage_files'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['owner_id', 'category']),
            models.Index(fields=['related_entity_type', 'related_entity_id']),
            models.Index(fields=['organization_id', 'status']),
            models.Index(fields=['expires_at', 'status']),
        ]

    def __str__(self):
        return f"{self.file_id}: {self.filename}"

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_public(self):
        return self.access_level == AccessLevel.PUBLIC

    @property
    def size_mb(self):
        return round(self.original_size / (1024 * 1024), 2)

    def mark_accessed(self):
        """Update access tracking."""
        self.access_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=['access_count', 'last_accessed_at'])

    def mark_downloaded(self):
        """Update download tracking."""
        self.download_count += 1
        self.mark_accessed()
        self.save(update_fields=['download_count'])

    def mark_deleted(self):
        """Soft delete the file."""
        self.status = 'deleted'
        self.deleted_at = timezone.now()
        self.save(update_fields=['status', 'deleted_at', 'updated_at'])

    def archive(self):
        """Archive the file."""
        self.status = 'archived'
        self.save(update_fields=['status', 'updated_at'])

    def quarantine(self, reason: str = None):
        """Quarantine file (security threat detected)."""
        self.status = 'quarantined'
        if reason:
            self.metadata['quarantine_reason'] = reason
            self.metadata['quarantined_at'] = timezone.now().isoformat()
        self.save(update_fields=['status', 'metadata', 'updated_at'])

    def create_new_version(self):
        """Mark this as parent and prepare for new version."""
        self.is_latest_version = False
        self.save(update_fields=['is_latest_version'])
        return self.version + 1

    def can_access(self, user=None, organization_id=None) -> bool:
        """Check if user can access this file."""
        if self.status != 'active':
            return False

        if self.is_expired:
            return False

        if self.access_level == AccessLevel.PUBLIC:
            return True

        if user is None:
            return False

        if self.access_level == AccessLevel.AUTHENTICATED:
            return user.is_authenticated

        if self.access_level == AccessLevel.PRIVATE:
            return str(user.id) == self.owner_id

        if self.access_level == AccessLevel.ORG_MEMBERS:
            return organization_id and organization_id == self.organization_id

        if self.access_level == AccessLevel.RESTRICTED:
            # Check allowed_users in metadata
            allowed = self.metadata.get('allowed_users', [])
            return str(user.id) in allowed

        if self.access_level == AccessLevel.INTERNAL:
            return getattr(user, 'is_staff', False)

        return False


class SignedURL(models.Model):
    """
    Tracks signed URLs for secure file access.
    Supports expiration, usage limits, and IP restrictions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    file = models.ForeignKey(StoredFile, on_delete=models.CASCADE, related_name='signed_urls')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)

    # Expiration
    expires_at = models.DateTimeField(db_index=True)

    # Usage limits
    max_uses = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    use_count = models.PositiveIntegerField(default=0)

    # IP restrictions
    allowed_ips = models.JSONField(default=list, blank=True)

    # Access type
    allow_download = models.BooleanField(default=True)

    # Revocation
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by_id = models.CharField(max_length=100, null=True, blank=True)

    # Tracking
    created_by_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'storage_signed_urls'
        ordering = ['-created_at']

    def __str__(self):
        return f"SignedURL for {self.file.file_id}"

    @property
    def is_valid(self) -> bool:
        """Check if URL is still valid."""
        if self.is_revoked:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.max_uses > 0 and self.use_count >= self.max_uses:
            return False
        return True

    def use(self, ip_address: str = None) -> bool:
        """
        Record a use of this URL.
        Returns False if IP not allowed.
        """
        # Check IP restrictions
        if self.allowed_ips and ip_address:
            if ip_address not in self.allowed_ips:
                return False

        self.use_count += 1
        self.last_used_at = timezone.now()
        if ip_address:
            self.last_used_ip = ip_address
        self.save(update_fields=['use_count', 'last_used_at', 'last_used_ip'])
        return True

    def revoke(self, user_id: str = None):
        """Revoke this signed URL."""
        self.is_revoked = True
        self.revoked_at = timezone.now()
        if user_id:
            self.revoked_by_id = user_id
        self.save(update_fields=['is_revoked', 'revoked_at', 'revoked_by_id'])


class StorageQuota(models.Model):
    """
    Storage quota tracking per user/organization.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner_id = models.CharField(max_length=100, db_index=True)
    owner_type = models.CharField(
        max_length=20,
        choices=[('user', 'User'), ('organization', 'Organization')]
    )

    # Quota limits
    total_quota = models.BigIntegerField(
        default=1024 * 1024 * 1024,  # 1GB default
        help_text="Total storage quota in bytes"
    )
    used_storage = models.BigIntegerField(default=0)

    # File limits
    max_files = models.PositiveIntegerField(default=10000)
    current_files = models.PositiveIntegerField(default=0)

    # Category-specific limits (optional)
    category_limits = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'storage_quotas'
        unique_together = ['owner_id', 'owner_type']

    def __str__(self):
        return f"Quota for {self.owner_type}:{self.owner_id}"

    @property
    def usage_percentage(self) -> int:
        if self.total_quota == 0:
            return 100
        return int((self.used_storage / self.total_quota) * 100)

    @property
    def available_storage(self) -> int:
        return max(0, self.total_quota - self.used_storage)

    def can_store(self, size: int) -> tuple:
        """
        Check if file of given size can be stored.
        Returns (can_store: bool, error_message: str or None)
        """
        if self.used_storage + size > self.total_quota:
            return False, f"Storage quota exceeded. Available: {self.available_storage} bytes"
        if self.current_files >= self.max_files:
            return False, f"File count limit reached ({self.max_files})"
        return True, None

    def add_file(self, size: int):
        """Record a new file added."""
        self.used_storage += size
        self.current_files += 1
        self.save(update_fields=['used_storage', 'current_files', 'updated_at'])

    def remove_file(self, size: int):
        """Record a file removed."""
        self.used_storage = max(0, self.used_storage - size)
        self.current_files = max(0, self.current_files - 1)
        self.save(update_fields=['used_storage', 'current_files', 'updated_at'])


class StorageAccessLog(models.Model):
    """
    Audit log for all storage operations.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Operation details
    operation = models.CharField(
        max_length=20,
        choices=[
            ('upload', 'Upload'),
            ('download', 'Download'),
            ('view', 'View'),
            ('delete', 'Delete'),
            ('update', 'Update'),
            ('share', 'Share'),
            ('revoke', 'Revoke Access'),
        ],
        db_index=True
    )

    # File reference
    file_id = models.CharField(max_length=32, db_index=True)
    file_category = models.CharField(max_length=50, blank=True)

    # Result
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    # Actor
    user_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=100, blank=True)
    service_name = models.CharField(max_length=50, blank=True)

    # Additional details
    details = models.JSONField(default=dict, blank=True)

    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'storage_access_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['file_id', 'operation']),
            models.Index(fields=['user_id', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.operation} on {self.file_id} at {self.timestamp}"


class ProcessingJob(models.Model):
    """
    Background processing job for files.
    Used for async processing of large files.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Job details
    job_type = models.CharField(
        max_length=30,
        choices=[
            ('process_image', 'Process Image'),
            ('process_document', 'Process Document'),
            ('process_video', 'Process Video'),
            ('process_audio', 'Process Audio'),
            ('generate_thumbnail', 'Generate Thumbnail'),
            ('extract_text', 'Extract Text'),
            ('scan_threats', 'Scan for Threats'),
            ('compress', 'Compress'),
            ('convert_format', 'Convert Format'),
        ]
    )

    # File reference
    file = models.ForeignKey(
        StoredFile,
        on_delete=models.CASCADE,
        related_name='processing_jobs'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('queued', 'Queued'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        db_index=True
    )

    # Celery task info
    celery_task_id = models.CharField(max_length=100, blank=True, null=True)

    # Progress
    progress_percent = models.PositiveIntegerField(default=0)
    progress_message = models.CharField(max_length=255, blank=True)

    # Results
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    # Retry info
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Priority
    priority = models.PositiveIntegerField(default=5, help_text="1=highest, 10=lowest")

    class Meta:
        db_table = 'storage_processing_jobs'
        ordering = ['priority', 'created_at']

    def __str__(self):
        return f"{self.job_type} for {self.file.file_id}"

    def start(self):
        """Mark job as started."""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.attempts += 1
        self.save(update_fields=['status', 'started_at', 'attempts'])

    def complete(self, result: dict = None):
        """Mark job as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percent = 100
        if result:
            self.result = result
        self.save(update_fields=['status', 'completed_at', 'progress_percent', 'result'])

    def fail(self, error: str):
        """Mark job as failed."""
        if self.attempts >= self.max_attempts:
            self.status = 'failed'
        else:
            self.status = 'pending'  # Will be retried
        self.error_message = error
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])

    def update_progress(self, percent: int, message: str = ''):
        """Update job progress."""
        self.progress_percent = min(99, percent)  # Never 100 until complete
        self.progress_message = message
        self.save(update_fields=['progress_percent', 'progress_message'])


class OrphanFile(models.Model):
    """
    Tracks orphan files detected during garbage collection.
    Files that exist in storage but not in database.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    storage_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(default=0)

    detected_at = models.DateTimeField(auto_now_add=True)

    # Resolution
    status = models.CharField(
        max_length=20,
        choices=[
            ('detected', 'Detected'),
            ('reviewed', 'Reviewed'),
            ('deleted', 'Deleted'),
            ('restored', 'Restored'),
            ('ignored', 'Ignored'),
        ],
        default='detected'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_id = models.CharField(max_length=100, null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'storage_orphan_files'
        ordering = ['-detected_at']

    def __str__(self):
        return f"Orphan: {self.storage_path}"

