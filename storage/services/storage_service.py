# -*- coding: utf-8 -*-
"""
Storage Service - Core Implementation
======================================
Centralized, secure file storage for the entire ForgeForth platform.

Features:
- Categorized file organization (profiles/avatars, applications/resumes, etc.)
- Unique UUID-based naming (never trust uploaded filenames)
- Signed URL access (never expose direct paths)
- Access level enforcement (public, private, restricted, org_members)
- Async processing support via Celery
- CDN compatibility
- File versioning
- Garbage collection for orphan files
- Full audit logging
"""
import hashlib
import hmac
import logging
import os
import secrets
import uuid
from base64 import urlsafe_b64encode, urlsafe_b64decode
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, BinaryIO, Union

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.files.uploadedfile import UploadedFile

from ..models import (
    StoredFile, SignedURL, StorageQuota, StorageAccessLog,
    ProcessingJob, OrphanFile, FileCategory, AccessLevel
)

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================

# Storage root (should be outside web root!)
STORAGE_ROOT = getattr(settings, 'SECURE_STORAGE_ROOT', settings.BASE_DIR / 'secure_storage')

# Maximum file size (50MB default)
MAX_FILE_SIZE = getattr(settings, 'STORAGE_MAX_FILE_SIZE', 50 * 1024 * 1024)

# Default URL expiry
DEFAULT_URL_EXPIRY_HOURS = getattr(settings, 'STORAGE_URL_EXPIRY_HOURS', 24 * 7)

# Signing key
SIGNING_KEY = getattr(settings, 'STORAGE_SIGNING_KEY', None) or settings.SECRET_KEY

# Encryption key (optional)
ENCRYPTION_KEY = getattr(settings, 'STORAGE_ENCRYPTION_KEY', None)

# Async threshold - files larger than this go to background processing
ASYNC_THRESHOLD = 5 * 1024 * 1024  # 5MB


# ============================================================
# File Type Detection
# ============================================================

MIME_TO_EXTENSION = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'image/svg+xml': 'svg',
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'text/plain': 'txt',
    'video/mp4': 'mp4',
    'video/webm': 'webm',
    'audio/mpeg': 'mp3',
    'audio/wav': 'wav',
    'audio/ogg': 'ogg',
}

CATEGORY_ACCESS_DEFAULTS = {
    FileCategory.AVATAR: AccessLevel.PUBLIC,
    FileCategory.COVER_IMAGE: AccessLevel.PUBLIC,
    FileCategory.RESUME: AccessLevel.PRIVATE,
    FileCategory.COVER_LETTER: AccessLevel.PRIVATE,
    FileCategory.PORTFOLIO: AccessLevel.AUTHENTICATED,
    FileCategory.CERTIFICATE: AccessLevel.PRIVATE,
    FileCategory.ORG_LOGO: AccessLevel.PUBLIC,
    FileCategory.ORG_BANNER: AccessLevel.PUBLIC,
    FileCategory.ORG_DOCUMENT: AccessLevel.ORG_MEMBERS,
    FileCategory.MESSAGE_ATTACHMENT: AccessLevel.RESTRICTED,
    FileCategory.EMAIL_ATTACHMENT: AccessLevel.RESTRICTED,
    FileCategory.BLOG_IMAGE: AccessLevel.PUBLIC,
    FileCategory.BLOG_ATTACHMENT: AccessLevel.PUBLIC,
    FileCategory.GALLERY_IMAGE: AccessLevel.PUBLIC,
    FileCategory.CV_UPLOAD: AccessLevel.INTERNAL,
    FileCategory.SKILL_EVIDENCE: AccessLevel.PRIVATE,
    FileCategory.PROCESSED_IMAGE: AccessLevel.PRIVATE,
    FileCategory.PROCESSED_DOCUMENT: AccessLevel.PRIVATE,
    FileCategory.TEMP: AccessLevel.PRIVATE,
    FileCategory.OTHER: AccessLevel.PRIVATE,
}


def detect_mime_type(data: bytes) -> str:
    """Detect MIME type from file content (magic bytes)."""
    signatures = {
        b'\x89PNG\r\n\x1a\n': 'image/png',
        b'\xff\xd8\xff': 'image/jpeg',
        b'GIF87a': 'image/gif',
        b'GIF89a': 'image/gif',
        b'RIFF': 'image/webp',  # Needs further check
        b'%PDF': 'application/pdf',
        b'PK\x03\x04': 'application/zip',  # Could be docx, xlsx, etc.
        b'\x00\x00\x00\x18ftypmp4': 'video/mp4',
        b'\x00\x00\x00\x1cftyp': 'video/mp4',
        b'\x1aE\xdf\xa3': 'video/webm',
        b'ID3': 'audio/mpeg',
        b'\xff\xfb': 'audio/mpeg',
        b'OggS': 'audio/ogg',
    }

    for sig, mime in signatures.items():
        if data[:len(sig)] == sig:
            if sig == b'RIFF' and b'WEBP' in data[:12]:
                return 'image/webp'
            return mime

    # Check for text
    try:
        data[:1024].decode('utf-8')
        return 'text/plain'
    except:
        pass

    return 'application/octet-stream'


def generate_file_id() -> str:
    """Generate a short unique file ID."""
    return secrets.token_urlsafe(12)[:16]


def generate_storage_path(category: str, file_id: str, extension: str) -> str:
    """
    Generate storage path with date-based organization.
    Format: category/YYYY/MM/file_id.ext
    """
    now = timezone.now()
    return f"{category}/{now.year}/{now.month:02d}/{file_id}.{extension}"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for display (not for storage)."""
    # Remove path components
    filename = os.path.basename(filename)
    # Remove dangerous characters
    dangerous = ['..', '/', '\\', '\0', '<', '>', ':', '"', '|', '?', '*']
    for char in dangerous:
        filename = filename.replace(char, '_')
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename or 'unnamed'


# ============================================================
# URL Signing
# ============================================================

class URLSigner:
    """Signs and verifies file access tokens."""

    def __init__(self, key: bytes = None):
        self.key = key or SIGNING_KEY.encode() if isinstance(SIGNING_KEY, str) else SIGNING_KEY or b'default-key'

    def sign(self, file_id: str, expires_at: datetime, extra_data: dict = None) -> str:
        """Create a signed token for file access."""
        # Create token data
        expires_ts = int(expires_at.timestamp())
        data = f"{file_id}:{expires_ts}"
        if extra_data:
            import json
            data += f":{urlsafe_b64encode(json.dumps(extra_data).encode()).decode()}"

        # Sign
        signature = hmac.new(
            self.key,
            data.encode(),
            hashlib.sha256
        ).digest()

        # Combine: data + signature
        token = urlsafe_b64encode(data.encode() + b':' + signature).decode()
        return token

    def verify(self, token: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Verify a signed token.
        Returns: (is_valid, file_id, error_message)
        """
        try:
            decoded = urlsafe_b64decode(token.encode())
            parts = decoded.rsplit(b':', 1)
            if len(parts) != 2:
                return False, None, "Invalid token format"

            data, signature = parts

            # Verify signature
            expected_sig = hmac.new(
                self.key,
                data,
                hashlib.sha256
            ).digest()

            if not hmac.compare_digest(signature, expected_sig):
                return False, None, "Invalid signature"

            # Parse data
            data_parts = data.decode().split(':')
            file_id = data_parts[0]
            expires_ts = int(data_parts[1])

            # Check expiration
            if datetime.fromtimestamp(expires_ts, tz=timezone.utc) < timezone.now():
                return False, file_id, "Token expired"

            return True, file_id, None

        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return False, None, "Invalid token"


# ============================================================
# Storage Backend
# ============================================================

class FileStorageBackend:
    """
    Low-level file storage operations.
    Handles actual reading/writing to filesystem.
    """

    def __init__(self, root: Path = None):
        self.root = Path(root or STORAGE_ROOT)
        self._ensure_root()

    def _ensure_root(self):
        """Ensure storage root exists with secure permissions."""
        if not self.root.exists():
            self.root.mkdir(parents=True, mode=0o700)
            logger.info(f"Created storage root: {self.root}")

    def _get_path(self, storage_path: str) -> Path:
        """Get full filesystem path."""
        return self.root / storage_path

    def store(self, storage_path: str, data: bytes) -> bool:
        """Store data to path."""
        try:
            full_path = self._get_path(storage_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write with secure permissions
            full_path.write_bytes(data)
            os.chmod(full_path, 0o600)

            return True
        except Exception as e:
            logger.error(f"Failed to store file at {storage_path}: {e}")
            return False

    def retrieve(self, storage_path: str) -> Optional[bytes]:
        """Retrieve data from path."""
        try:
            full_path = self._get_path(storage_path)
            if not full_path.exists():
                return None
            return full_path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to retrieve file at {storage_path}: {e}")
            return None

    def delete(self, storage_path: str) -> bool:
        """Delete file at path."""
        try:
            full_path = self._get_path(storage_path)
            if full_path.exists():
                full_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete file at {storage_path}: {e}")
            return False

    def exists(self, storage_path: str) -> bool:
        """Check if file exists."""
        return self._get_path(storage_path).exists()

    def get_size(self, storage_path: str) -> int:
        """Get file size."""
        full_path = self._get_path(storage_path)
        return full_path.stat().st_size if full_path.exists() else 0

    def list_all_files(self) -> List[str]:
        """List all files in storage (for garbage collection)."""
        files = []
        for path in self.root.rglob('*'):
            if path.is_file():
                files.append(str(path.relative_to(self.root)))
        return files


# ============================================================
# Main Storage Service
# ============================================================

class SecureStorageService:
    """
    Main storage service for the ForgeForth platform.

    This is the ONLY interface for file storage across all subsystems.

    Usage:
        service = SecureStorageService()

        # Store a file
        result = service.store(
            data=file_bytes,
            filename="resume.pdf",
            category=FileCategory.RESUME,
            owner_id="user_123",
        )

        # Generate signed URL
        url = service.get_signed_url(result['file_id'])

        # Retrieve with token
        result = service.retrieve_with_token(token)
    """

    def __init__(self):
        self.backend = FileStorageBackend()
        self.signer = URLSigner()
        self.logger = logger

    # --------------------------------------------------
    # Store Operations
    # --------------------------------------------------

    def store(
        self,
        data: Union[bytes, BinaryIO, UploadedFile],
        filename: str,
        category: str = FileCategory.OTHER,
        owner_id: str = None,
        owner_type: str = 'user',
        organization_id: str = None,
        access_level: str = None,
        mime_type: str = None,
        related_entity_type: str = None,
        related_entity_id: str = None,
        metadata: dict = None,
        tags: list = None,
        description: str = '',
        expires_in_hours: int = None,
        process_async: bool = None,
        request_context: dict = None,
    ) -> Dict[str, Any]:
        """
        Store a file securely.

        Args:
            data: File content (bytes, file-like object, or Django UploadedFile)
            filename: Original filename (will be sanitized)
            category: File category (from FileCategory enum)
            owner_id: User/Org ID who owns the file
            owner_type: 'user' or 'organization'
            organization_id: Organization ID (for org_members access)
            access_level: Override default access level for category
            mime_type: MIME type (auto-detected if not provided)
            related_entity_type: Related model name (e.g., 'profile', 'application')
            related_entity_id: Related model ID
            metadata: Additional metadata dict
            tags: List of tags
            description: File description
            expires_in_hours: Auto-expire after N hours
            process_async: Force async processing (default: auto based on size)
            request_context: Request info for audit logging

        Returns:
            Dict with success, file_id, signed_url, etc.
        """
        request_context = request_context or {}

        try:
            # Read data
            if hasattr(data, 'read'):
                if hasattr(data, 'seek'):
                    data.seek(0)
                content = data.read()
            else:
                content = data

            original_size = len(content)

            # Validate size
            if original_size > MAX_FILE_SIZE:
                return {
                    'success': False,
                    'error': f'File too large: {original_size} bytes (max: {MAX_FILE_SIZE})'
                }

            # Check quota
            if owner_id:
                can_store, quota_error = self._check_quota(owner_id, owner_type, original_size)
                if not can_store:
                    return {'success': False, 'error': quota_error}

            # Detect MIME type
            if not mime_type:
                mime_type = detect_mime_type(content)

            # Get extension
            extension = MIME_TO_EXTENSION.get(mime_type, '')
            if not extension:
                # Try from filename
                _, ext = os.path.splitext(filename)
                extension = ext.lstrip('.').lower() or 'bin'

            # Generate IDs and paths
            file_id = generate_file_id()
            storage_path = generate_storage_path(category, file_id, extension)

            # Sanitize filename
            safe_filename = sanitize_filename(filename)

            # Calculate checksums
            checksum_original = hashlib.sha256(content).hexdigest()

            # Determine access level
            if access_level is None:
                access_level = CATEGORY_ACCESS_DEFAULTS.get(category, AccessLevel.PRIVATE)

            # Determine media type
            media_type = self._get_media_type(mime_type)

            # Should process async?
            if process_async is None:
                process_async = original_size > ASYNC_THRESHOLD

            # Store the file
            stored = self.backend.store(storage_path, content)
            if not stored:
                return {'success': False, 'error': 'Failed to store file'}

            stored_size = self.backend.get_size(storage_path)
            checksum_stored = checksum_original  # Same if not encrypted

            # Calculate expiration
            expires_at = None
            if expires_in_hours:
                expires_at = timezone.now() + timedelta(hours=expires_in_hours)

            # Create database record
            with transaction.atomic():
                stored_file = StoredFile.objects.create(
                    file_id=file_id,
                    filename=safe_filename,
                    original_filename=filename,
                    extension=extension,
                    mime_type=mime_type,
                    category=category,
                    storage_path=storage_path,
                    original_size=original_size,
                    stored_size=stored_size,
                    checksum_sha256=checksum_original,
                    checksum_stored=checksum_stored,
                    is_encrypted=False,  # TODO: Add encryption
                    access_level=access_level,
                    owner_id=owner_id,
                    owner_type=owner_type,
                    organization_id=organization_id,
                    related_entity_type=related_entity_type,
                    related_entity_id=related_entity_id,
                    media_type=media_type,
                    metadata=metadata or {},
                    tags=tags or [],
                    description=description,
                    expires_at=expires_at,
                    status='active',
                )

                # Update quota
                if owner_id:
                    self._update_quota(owner_id, owner_type, original_size, add=True)

                # Log access
                self._log_access(
                    operation='upload',
                    file_id=file_id,
                    file_category=category,
                    success=True,
                    user_id=owner_id,
                    request_context=request_context,
                    details={'size': original_size, 'mime_type': mime_type}
                )

            # Queue async processing if needed
            if process_async and media_type in ['image', 'document', 'video', 'audio']:
                self._queue_processing(stored_file, f'process_{media_type}')

            # Generate signed URL
            signed_url, url_expires_at = self._generate_signed_url(file_id)

            return {
                'success': True,
                'file_id': file_id,
                'storage_path': storage_path,
                'signed_url': signed_url,
                'url_expires_at': url_expires_at.isoformat(),
                'stored_file': {
                    'id': str(stored_file.id),
                    'file_id': file_id,
                    'filename': safe_filename,
                    'mime_type': mime_type,
                    'size': original_size,
                    'category': category,
                    'access_level': access_level,
                    'media_type': media_type,
                }
            }

        except Exception as e:
            self.logger.error(f"Storage error: {e}", exc_info=True)
            self._log_access(
                operation='upload',
                file_id='unknown',
                success=False,
                error_message=str(e),
                user_id=owner_id,
                request_context=request_context,
            )
            return {'success': False, 'error': str(e)}

    # --------------------------------------------------
    # Retrieve Operations
    # --------------------------------------------------

    def retrieve_with_token(
        self,
        token: str,
        request_context: dict = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a file using a signed token.
        This is the PRIMARY way to access files.
        """
        request_context = request_context or {}
        ip_address = request_context.get('ip_address')

        # Verify token
        is_valid, file_id, error = self.signer.verify(token)

        if not is_valid:
            self._log_access(
                operation='view',
                file_id=file_id or 'unknown',
                success=False,
                error_message=error,
                request_context=request_context,
            )
            return {'success': False, 'error': error or 'Invalid token'}

        try:
            # Get file record
            stored_file = StoredFile.objects.get(file_id=file_id, status='active')

            # Check SignedURL record if exists
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            try:
                signed_url = SignedURL.objects.get(token_hash=token_hash)
                if not signed_url.is_valid:
                    return {'success': False, 'error': 'URL no longer valid'}
                if not signed_url.use(ip_address):
                    return {'success': False, 'error': 'IP address not allowed'}
            except SignedURL.DoesNotExist:
                pass  # Token-only access (no SignedURL record)

            # Read file
            content = self.backend.retrieve(stored_file.storage_path)
            if content is None:
                return {'success': False, 'error': 'File not found on disk'}

            # Update access tracking
            stored_file.mark_accessed()

            # Log access
            self._log_access(
                operation='view',
                file_id=file_id,
                file_category=stored_file.category,
                success=True,
                request_context=request_context,
            )

            return {
                'success': True,
                'content': content,
                'file_info': {
                    'file_id': file_id,
                    'filename': stored_file.filename,
                    'mime_type': stored_file.mime_type,
                    'size': stored_file.original_size,
                }
            }

        except StoredFile.DoesNotExist:
            self._log_access(
                operation='view',
                file_id=file_id,
                success=False,
                error_message='File not found',
                request_context=request_context,
            )
            return {'success': False, 'error': 'File not found'}

        except Exception as e:
            self.logger.error(f"Retrieve error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata (no content)."""
        try:
            sf = StoredFile.objects.get(file_id=file_id)
            return {
                'file_id': sf.file_id,
                'filename': sf.filename,
                'original_filename': sf.original_filename,
                'mime_type': sf.mime_type,
                'size': sf.original_size,
                'category': sf.category,
                'access_level': sf.access_level,
                'media_type': sf.media_type,
                'owner_id': sf.owner_id,
                'owner_type': sf.owner_type,
                'organization_id': sf.organization_id,
                'related_entity_type': sf.related_entity_type,
                'related_entity_id': sf.related_entity_id,
                'version': sf.version,
                'is_latest_version': sf.is_latest_version,
                'status': sf.status,
                'created_at': sf.created_at.isoformat(),
                'access_count': sf.access_count,
                'download_count': sf.download_count,
                'metadata': sf.metadata,
                'tags': sf.tags,
            }
        except StoredFile.DoesNotExist:
            return None

    # --------------------------------------------------
    # URL Generation
    # --------------------------------------------------

    def get_signed_url(
        self,
        file_id: str,
        expires_in_hours: int = None,
        max_uses: int = 0,
        allowed_ips: List[str] = None,
        created_by_id: str = None,
    ) -> Optional[str]:
        """
        Generate a signed URL for file access.

        Args:
            file_id: File ID
            expires_in_hours: URL validity period
            max_uses: Max times URL can be used (0 = unlimited)
            allowed_ips: List of allowed IP addresses
            created_by_id: User who created this URL

        Returns:
            Signed URL token or None if file not found
        """
        try:
            stored_file = StoredFile.objects.get(file_id=file_id, status='active')
        except StoredFile.DoesNotExist:
            return None

        expires_in_hours = expires_in_hours or DEFAULT_URL_EXPIRY_HOURS
        expires_at = timezone.now() + timedelta(hours=expires_in_hours)

        # Generate token
        token = self.signer.sign(file_id, expires_at)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Store in database
        SignedURL.objects.create(
            file=stored_file,
            token_hash=token_hash,
            expires_at=expires_at,
            max_uses=max_uses,
            allowed_ips=allowed_ips or [],
            created_by_id=created_by_id,
        )

        return token

    def _generate_signed_url(self, file_id: str) -> Tuple[str, datetime]:
        """Internal method to generate URL without creating SignedURL record."""
        expires_at = timezone.now() + timedelta(hours=DEFAULT_URL_EXPIRY_HOURS)
        token = self.signer.sign(file_id, expires_at)
        return token, expires_at

    def build_public_url(self, token: str, base_url: str = None) -> str:
        """Build full public URL for file access."""
        base = base_url or getattr(settings, 'SITE_URL', '')
        return f"{base}/storage/file/{token}/"

    # --------------------------------------------------
    # Delete Operations
    # --------------------------------------------------

    def delete(
        self,
        file_id: str,
        user_id: str = None,
        hard_delete: bool = False,
        request_context: dict = None,
    ) -> bool:
        """
        Delete a file.

        Args:
            file_id: File ID
            user_id: User performing deletion
            hard_delete: If True, also removes from disk
            request_context: Request info for audit
        """
        request_context = request_context or {}

        try:
            stored_file = StoredFile.objects.get(file_id=file_id)

            if hard_delete:
                # Delete from disk
                self.backend.delete(stored_file.storage_path)

                # Update quota
                if stored_file.owner_id:
                    self._update_quota(
                        stored_file.owner_id,
                        stored_file.owner_type,
                        stored_file.original_size,
                        add=False
                    )

                # Delete record
                stored_file.delete()
            else:
                # Soft delete
                stored_file.mark_deleted()

            # Revoke all signed URLs
            SignedURL.objects.filter(file_id=stored_file.id).update(
                is_revoked=True,
                revoked_at=timezone.now(),
                revoked_by_id=user_id,
            )

            # Log
            self._log_access(
                operation='delete',
                file_id=file_id,
                file_category=stored_file.category,
                success=True,
                user_id=user_id,
                request_context=request_context,
                details={'hard_delete': hard_delete}
            )

            return True

        except StoredFile.DoesNotExist:
            return False
        except Exception as e:
            self.logger.error(f"Delete error: {e}", exc_info=True)
            return False

    # --------------------------------------------------
    # Versioning
    # --------------------------------------------------

    def store_new_version(
        self,
        parent_file_id: str,
        data: Union[bytes, BinaryIO],
        filename: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Store a new version of an existing file.
        """
        try:
            parent = StoredFile.objects.get(file_id=parent_file_id, status='active')
        except StoredFile.DoesNotExist:
            return {'success': False, 'error': 'Parent file not found'}

        # Get next version number
        new_version = parent.create_new_version()

        # Store with parent reference
        result = self.store(
            data=data,
            filename=filename or parent.original_filename,
            category=parent.category,
            owner_id=parent.owner_id,
            owner_type=parent.owner_type,
            organization_id=parent.organization_id,
            access_level=parent.access_level,
            related_entity_type=parent.related_entity_type,
            related_entity_id=parent.related_entity_id,
            **kwargs
        )

        if result['success']:
            # Update new file with version info
            StoredFile.objects.filter(file_id=result['file_id']).update(
                version=new_version,
                parent_file_id=parent.id,
                is_latest_version=True,
            )
            result['version'] = new_version
            result['parent_file_id'] = parent_file_id

        return result

    def get_file_versions(self, file_id: str) -> List[Dict[str, Any]]:
        """Get all versions of a file."""
        try:
            # Get the file
            sf = StoredFile.objects.get(file_id=file_id)

            # Find root (earliest version)
            root = sf
            while root.parent_file:
                root = root.parent_file

            # Get all versions from root
            versions = [root]
            versions.extend(list(root.versions.all().order_by('version')))

            return [
                {
                    'file_id': v.file_id,
                    'version': v.version,
                    'is_latest': v.is_latest_version,
                    'created_at': v.created_at.isoformat(),
                    'size': v.original_size,
                }
                for v in versions
            ]
        except StoredFile.DoesNotExist:
            return []

    # --------------------------------------------------
    # Garbage Collection
    # --------------------------------------------------

    def find_orphan_files(self) -> List[str]:
        """
        Find files on disk that don't have database records.
        Returns list of storage paths.
        """
        # Get all paths from disk
        disk_files = set(self.backend.list_all_files())

        # Get all paths from database
        db_paths = set(
            StoredFile.objects.exclude(status='deleted').values_list('storage_path', flat=True)
        )

        # Find orphans
        orphans = disk_files - db_paths

        # Record them
        for path in orphans:
            size = self.backend.get_size(path)
            OrphanFile.objects.get_or_create(
                storage_path=path,
                defaults={'file_size': size}
            )

        return list(orphans)

    def cleanup_orphans(self, older_than_days: int = 7) -> int:
        """
        Delete orphan files older than specified days.
        Returns count of deleted files.
        """
        cutoff = timezone.now() - timedelta(days=older_than_days)
        orphans = OrphanFile.objects.filter(
            status='detected',
            detected_at__lt=cutoff
        )

        count = 0
        for orphan in orphans:
            if self.backend.delete(orphan.storage_path):
                orphan.status = 'deleted'
                orphan.resolved_at = timezone.now()
                orphan.save()
                count += 1

        return count

    def cleanup_expired(self) -> int:
        """Delete files past their expiration date."""
        expired = StoredFile.objects.filter(
            status='active',
            expires_at__lt=timezone.now()
        )

        count = 0
        for sf in expired:
            if self.delete(sf.file_id, hard_delete=True):
                count += 1

        return count

    # --------------------------------------------------
    # Statistics
    # --------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        from django.db.models import Count, Sum

        files = StoredFile.objects.filter(status='active')
        total_count = files.count()

        # Aggregate by category
        by_category = dict(
            files.values('category').annotate(
                count=Count('id'),
                total_size=Sum('original_size')
            ).values_list('category', 'count')
        )

        # Aggregate by media type
        by_media_type = dict(
            files.values('media_type').annotate(
                count=Count('id')
            ).values_list('media_type', 'count')
        )

        # Total size
        total_size = files.aggregate(total=Sum('original_size'))['total'] or 0

        return {
            'total_files': total_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'by_category': by_category,
            'by_media_type': by_media_type,
            'orphan_count': OrphanFile.objects.filter(status='detected').count(),
            'processing_queue': ProcessingJob.objects.filter(
                status__in=['pending', 'queued', 'processing']
            ).count(),
        }

    # --------------------------------------------------
    # Private Helpers
    # --------------------------------------------------

    def _get_media_type(self, mime_type: str) -> str:
        """Determine media type from MIME type."""
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type in ['application/pdf', 'application/msword',
                           'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                           'text/plain']:
            return 'document'
        return 'other'

    def _check_quota(self, owner_id: str, owner_type: str, size: int) -> Tuple[bool, Optional[str]]:
        """Check if owner has quota for the file."""
        quota, _ = StorageQuota.objects.get_or_create(
            owner_id=owner_id,
            owner_type=owner_type,
        )
        return quota.can_store(size)

    def _update_quota(self, owner_id: str, owner_type: str, size: int, add: bool):
        """Update quota usage."""
        try:
            quota = StorageQuota.objects.get(owner_id=owner_id, owner_type=owner_type)
            if add:
                quota.add_file(size)
            else:
                quota.remove_file(size)
        except StorageQuota.DoesNotExist:
            pass

    def _queue_processing(self, stored_file: StoredFile, job_type: str):
        """Queue a background processing job."""
        ProcessingJob.objects.create(
            file=stored_file,
            job_type=job_type,
            status='pending',
        )

        # TODO: Trigger Celery task
        # from storage.tasks import process_file
        # process_file.delay(str(stored_file.id), job_type)

    def _log_access(
        self,
        operation: str,
        file_id: str,
        file_category: str = '',
        success: bool = True,
        error_message: str = '',
        user_id: str = None,
        request_context: dict = None,
        details: dict = None,
    ):
        """Log a storage access."""
        request_context = request_context or {}
        StorageAccessLog.objects.create(
            operation=operation,
            file_id=file_id,
            file_category=file_category,
            success=success,
            error_message=error_message,
            user_id=user_id,
            ip_address=request_context.get('ip_address'),
            user_agent=request_context.get('user_agent', ''),
            request_id=request_context.get('request_id', ''),
            service_name=request_context.get('service_name', ''),
            details=details or {},
        )


# ============================================================
# Singleton Instance
# ============================================================

_storage_service = None


def get_storage_service() -> SecureStorageService:
    """Get the singleton storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = SecureStorageService()
    return _storage_service


# ============================================================
# Convenience Functions
# ============================================================

def store_file(
    data: Union[bytes, BinaryIO],
    filename: str,
    category: str = FileCategory.OTHER,
    owner_id: str = None,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to store a file."""
    return get_storage_service().store(
        data=data,
        filename=filename,
        category=category,
        owner_id=owner_id,
        **kwargs
    )


def retrieve_file(token: str, request_context: dict = None) -> Dict[str, Any]:
    """Convenience function to retrieve a file."""
    return get_storage_service().retrieve_with_token(token, request_context)


def delete_file(file_id: str, **kwargs) -> bool:
    """Convenience function to delete a file."""
    return get_storage_service().delete(file_id, **kwargs)


def get_signed_url(file_id: str, **kwargs) -> Optional[str]:
    """Convenience function to get a signed URL."""
    return get_storage_service().get_signed_url(file_id, **kwargs)


def store_avatar(data: bytes, user_id: str, **kwargs) -> Dict[str, Any]:
    """Store a profile avatar."""
    return store_file(
        data=data,
        filename='avatar.png',
        category=FileCategory.AVATAR,
        owner_id=user_id,
        owner_type='user',
        access_level=AccessLevel.PUBLIC,
        **kwargs
    )


def store_resume(data: bytes, user_id: str, filename: str, **kwargs) -> Dict[str, Any]:
    """Store a resume/CV."""
    return store_file(
        data=data,
        filename=filename,
        category=FileCategory.RESUME,
        owner_id=user_id,
        owner_type='user',
        access_level=AccessLevel.PRIVATE,
        **kwargs
    )


def store_org_logo(data: bytes, org_id: str, **kwargs) -> Dict[str, Any]:
    """Store an organization logo."""
    return store_file(
        data=data,
        filename='logo.png',
        category=FileCategory.ORG_LOGO,
        owner_id=org_id,
        owner_type='organization',
        organization_id=org_id,
        access_level=AccessLevel.PUBLIC,
        **kwargs
    )


def store_blog_image(data: bytes, filename: str, blog_post_id: str = None, **kwargs) -> Dict[str, Any]:
    """Store a blog image."""
    return store_file(
        data=data,
        filename=filename,
        category=FileCategory.BLOG_IMAGE,
        owner_type='system',
        related_entity_type='blog_post',
        related_entity_id=blog_post_id,
        access_level=AccessLevel.PUBLIC,
        **kwargs
    )

