# -*- coding: utf-8 -*-
"""
Base processor classes and shared utilities for media processing.
"""
import hashlib
import io
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, BinaryIO, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class MediaType(Enum):
    """Supported media types."""
    IMAGE = 'image'
    DOCUMENT = 'document'
    VIDEO = 'video'
    AUDIO = 'audio'
    UNKNOWN = 'unknown'


class ProcessingStatus(Enum):
    """Processing job status."""
    SUCCESS = 'success'
    FAILED = 'failed'
    QUARANTINED = 'quarantined'
    PARTIAL = 'partial'  # Some processing succeeded, some failed


@dataclass
class ProcessingResult:
    """Result of a media processing operation."""
    success: bool
    content: Optional[bytes] = None
    media_type: MediaType = MediaType.UNKNOWN
    mime_type: str = ''
    extension: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    threats_sanitized: List[str] = field(default_factory=list)
    checksum_sha256: str = ''
    original_size: int = 0
    processed_size: int = 0
    thumbnail: Optional[bytes] = None
    extracted_text: str = ''

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.processed_size and self.original_size:
            return round(self.original_size / self.processed_size, 2)
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'media_type': self.media_type.value,
            'mime_type': self.mime_type,
            'extension': self.extension,
            'metadata': self.metadata,
            'error': self.error,
            'warnings': self.warnings,
            'threats_sanitized': self.threats_sanitized,
            'checksum_sha256': self.checksum_sha256,
            'original_size': self.original_size,
            'processed_size': self.processed_size,
            'compression_ratio': self.compression_ratio,
            'has_thumbnail': self.thumbnail is not None,
            'has_extracted_text': bool(self.extracted_text),
        }


# Dangerous patterns to scan for in all file types
DANGEROUS_PATTERNS = [
    b'<script',
    b'<SCRIPT',
    b'<?php',
    b'<%',
    b'<!DOCTYPE html',
    b'<html',
    b'#!/bin/',
    b'#!/usr/',
    b'javascript:',
    b'onload=',
    b'onerror=',
    b'onclick=',
    b'eval(',
    b'document.cookie',
    b'window.location',
    b'exec(',
    b'system(',
    b'passthru(',
    b'shell_exec(',
    b'`',  # Backtick command execution
]

# Binary executable signatures
EXECUTABLE_SIGNATURES = [
    b'MZ',           # Windows PE
    b'\x7fELF',      # Linux ELF
    b'\xfe\xed\xfa\xce',  # Mach-O 32-bit
    b'\xfe\xed\xfa\xcf',  # Mach-O 64-bit
    b'\xca\xfe\xba\xbe',  # Mach-O Universal
    b'PK\x03\x04',   # ZIP (could be JAR, APK, etc.)
    b'\x00asm',      # WebAssembly
]


class BaseProcessor(ABC):
    """Base class for all media processors."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def process(self, data: bytes, **options) -> ProcessingResult:
        """Process the media file. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def can_process(self, mime_type: str) -> bool:
        """Check if this processor can handle the given MIME type."""
        pass

    @staticmethod
    def calculate_checksum(data: bytes) -> str:
        """Calculate SHA-256 checksum of data."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def generate_filename(extension: str = '') -> str:
        """Generate a unique filename."""
        unique_id = uuid.uuid4().hex[:16]
        if extension:
            extension = extension.lstrip('.')
            return f"{unique_id}.{extension}"
        return unique_id

    def scan_for_threats(self, data: bytes) -> List[str]:
        """
        Scan data for dangerous patterns.
        Returns list of detected threats (for logging/sanitization).
        """
        threats = []

        # Only scan first 1MB and last 100KB
        scan_regions = [
            ('header', data[:min(len(data), 1024 * 1024)]),
            ('footer', data[-min(len(data), 100 * 1024):] if len(data) > 100 * 1024 else b''),
        ]

        for region_name, region in scan_regions:
            if not region:
                continue

            # Check for dangerous patterns
            for pattern in DANGEROUS_PATTERNS:
                if pattern in region:
                    threat = f"Dangerous pattern '{pattern[:20].decode('utf-8', errors='replace')}' in {region_name}"
                    if threat not in threats:
                        threats.append(threat)

            # Check for executable signatures (only at start)
            if region_name == 'header':
                for sig in EXECUTABLE_SIGNATURES:
                    if region.startswith(sig):
                        threats.append(f"Executable signature detected: {sig[:8]}")
                        break

        return threats

    def read_file_data(self, input_data: Union[bytes, BinaryIO]) -> bytes:
        """Read bytes from file-like object or return bytes directly."""
        if hasattr(input_data, 'read'):
            input_data.seek(0)
            data = input_data.read()
            if hasattr(input_data, 'seek'):
                input_data.seek(0)
            return data
        return input_data


def detect_mime_type(data: bytes) -> str:
    """
    Detect MIME type from file content using magic bytes.
    Falls back to basic detection if python-magic is not available.
    """
    try:
        import magic
        mime = magic.Magic(mime=True)
        return mime.from_buffer(data)
    except ImportError:
        # Fallback to basic magic byte detection
        return _detect_mime_basic(data)
    except Exception as e:
        logger.warning(f"Magic detection failed: {e}, using basic detection")
        return _detect_mime_basic(data)


def _detect_mime_basic(data: bytes) -> str:
    """Basic MIME type detection using magic bytes."""
    if not data:
        return 'application/octet-stream'

    # Images
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return 'image/gif'
    if data.startswith(b'RIFF') and b'WEBP' in data[:12]:
        return 'image/webp'
    if data.startswith(b'BM'):
        return 'image/bmp'
    if b'<svg' in data[:1000].lower():
        return 'image/svg+xml'

    # Documents
    if data.startswith(b'%PDF'):
        return 'application/pdf'
    if data.startswith(b'PK\x03\x04'):
        # Could be DOCX, XLSX, ODT, etc.
        if b'word/' in data[:2000]:
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if b'xl/' in data[:2000]:
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return 'application/zip'
    if data.startswith(b'\xd0\xcf\x11\xe0'):
        return 'application/msword'  # Old .doc format

    # Video
    if data.startswith(b'\x00\x00\x00') and b'ftyp' in data[:12]:
        return 'video/mp4'
    if data.startswith(b'\x1a\x45\xdf\xa3'):
        return 'video/webm'
    if data.startswith(b'RIFF') and b'AVI ' in data[:12]:
        return 'video/avi'
    if data.startswith(b'\x00\x00\x01\xba') or data.startswith(b'\x00\x00\x01\xb3'):
        return 'video/mpeg'

    # Audio
    if data.startswith(b'ID3') or data.startswith(b'\xff\xfb') or data.startswith(b'\xff\xfa'):
        return 'audio/mpeg'
    if data.startswith(b'RIFF') and b'WAVE' in data[:12]:
        return 'audio/wav'
    if data.startswith(b'OggS'):
        return 'audio/ogg'
    if data.startswith(b'fLaC'):
        return 'audio/flac'

    # Text/HTML
    if data[:100].strip().startswith(b'<!DOCTYPE') or data[:100].strip().startswith(b'<html'):
        return 'text/html'
    if data[:100].strip().startswith(b'<?xml'):
        return 'application/xml'

    # Default
    return 'application/octet-stream'


def get_media_type_from_mime(mime_type: str) -> MediaType:
    """Determine MediaType from MIME type string."""
    if not mime_type:
        return MediaType.UNKNOWN

    mime_lower = mime_type.lower()

    if mime_lower.startswith('image/'):
        return MediaType.IMAGE
    if mime_lower.startswith('video/'):
        return MediaType.VIDEO
    if mime_lower.startswith('audio/'):
        return MediaType.AUDIO

    # Documents
    document_mimes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument',
        'application/vnd.oasis.opendocument',
        'text/plain',
        'text/rtf',
        'application/rtf',
    ]
    for doc_mime in document_mimes:
        if mime_lower.startswith(doc_mime):
            return MediaType.DOCUMENT

    return MediaType.UNKNOWN


def get_extension_from_mime(mime_type: str) -> str:
    """Get file extension from MIME type."""
    mime_to_ext = {
        # Images
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
        'image/bmp': 'bmp',
        'image/svg+xml': 'svg',
        # Documents
        'application/pdf': 'pdf',
        'application/msword': 'doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'text/plain': 'txt',
        # Video
        'video/mp4': 'mp4',
        'video/webm': 'webm',
        'video/avi': 'avi',
        'video/mpeg': 'mpeg',
        'video/quicktime': 'mov',
        # Audio
        'audio/mpeg': 'mp3',
        'audio/wav': 'wav',
        'audio/ogg': 'ogg',
        'audio/flac': 'flac',
        'audio/aac': 'aac',
    }
    return mime_to_ext.get(mime_type.lower(), '')

