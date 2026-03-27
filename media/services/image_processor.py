# -*- coding: utf-8 -*-
"""
Image Processor - Security-First Pipeline
==========================================
STRICT REQUIREMENTS:
1. Security scan - detect embedded code/malicious content
2. Sanitization - clean the image by re-encoding pixels ONLY
3. WebP compression - MUST output WebP, MUST be < 1MB

Pipeline: Input → Security Scan → Sanitization → WebP Compression → Output
"""
import io
import logging
from typing import Optional, Tuple, List

from .base import BaseProcessor, ProcessingResult, MediaType

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS - Strict requirements
# ═══════════════════════════════════════════════════════════════════════════════
MAX_OUTPUT_SIZE = 1 * 1024 * 1024   # 1MB - STRICT LIMIT, NO EXCEPTIONS
MIN_QUALITY = 85                     # MINIMUM quality - NEVER go below 85%
TARGET_QUALITY = 98                  # Starting quality for compression (high)
MAX_DIMENSION = 4096                 # Maximum pixels per side
MIN_DIMENSION = 10                   # Minimum pixels per side
THUMBNAIL_SIZE = (300, 300)

# Strategy: Minimum size + Maximum quality
# - Start at 95% quality
# - Reduce to 85% minimum (never lower)
# - If still too large at 85%, RESIZE image instead
# - This ensures smallest file with highest possible quality (85%+)

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY PATTERNS - Malicious content detection
# ═══════════════════════════════════════════════════════════════════════════════
DANGEROUS_BYTE_PATTERNS = [
    # Script injection
    b'<script',
    b'<SCRIPT',
    b'javascript:',
    b'vbscript:',
    b'onload=',
    b'onerror=',
    b'onclick=',
    b'onmouseover=',
    b'onfocus=',
    b'onblur=',

    # PHP/ASP code
    b'<?php',
    b'<?=',
    b'<%',
    b'%>',
    b'<asp:',

    # Shell commands
    b'#!/bin/',
    b'#!/usr/',
    b'exec(',
    b'system(',
    b'passthru(',
    b'shell_exec(',
    b'eval(',
    b'`',  # Backtick execution

    # HTML injection
    b'<!DOCTYPE',
    b'<html',
    b'<body',
    b'<iframe',
    b'<embed',
    b'<object',
    b'<applet',
    b'<form',
    b'<input',

    # JavaScript globals
    b'document.cookie',
    b'document.write',
    b'document.location',
    b'window.location',
    b'XMLHttpRequest',
    b'ActiveXObject',

    # SQL injection attempts
    b'UNION SELECT',
    b'union select',
    b'DROP TABLE',
    b'drop table',
    b'INSERT INTO',
    b'DELETE FROM',

    # Other dangerous
    b'data:text/html',
    b'data:application',
]

# Executable file signatures (should NEVER appear in images)
EXECUTABLE_SIGNATURES = [
    (b'MZ', 'Windows PE executable'),
    (b'\x7fELF', 'Linux ELF binary'),
    (b'\xfe\xed\xfa\xce', 'Mach-O 32-bit'),
    (b'\xfe\xed\xfa\xcf', 'Mach-O 64-bit'),
    (b'\xca\xfe\xba\xbe', 'Mach-O Universal'),
    (b'PK\x03\x04', 'ZIP/JAR/APK archive'),
    (b'\x00asm', 'WebAssembly'),
    (b'Rar!', 'RAR archive'),
    (b'\x1f\x8b', 'GZIP compressed'),
]

# EXIF tags that can contain malicious data
DANGEROUS_EXIF_FIELDS = [
    'XPComment',
    'UserComment',
    'ImageDescription',
    'Copyright',
    'Artist',
    'Software',
    'Make',
    'Model',
]


class ImageSanitizer:
    """
    Step 1 & 2: Security scanning and sanitization.
    Detects threats and removes them via pixel re-encoding.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ImageSanitizer")

    def scan_threats(self, data: bytes) -> List[str]:
        """
        Scan image data for embedded malicious content.
        Returns list of detected threats.
        """
        threats = []

        # Scan entire file for dangerous patterns
        data_lower = data.lower()

        for pattern in DANGEROUS_BYTE_PATTERNS:
            pattern_lower = pattern.lower() if isinstance(pattern, bytes) else pattern
            if pattern_lower in data_lower:
                # Get context around the match
                try:
                    idx = data_lower.index(pattern_lower)
                    context = data[max(0, idx-10):min(len(data), idx+30)]
                    threat_desc = f"Dangerous pattern: {pattern[:30]!r}"
                except:
                    threat_desc = f"Dangerous pattern: {pattern[:30]!r}"

                if threat_desc not in threats:
                    threats.append(threat_desc)

        # Check for executable signatures at start of file
        for sig, description in EXECUTABLE_SIGNATURES:
            if data.startswith(sig):
                threats.append(f"Executable signature: {description}")
                break

        # Check for polyglot files (valid image + hidden content)
        # Look for suspicious patterns after image data
        if len(data) > 1024:
            tail = data[-2048:]  # Last 2KB
            for pattern in DANGEROUS_BYTE_PATTERNS[:15]:  # Most dangerous patterns
                if pattern.lower() in tail.lower():
                    threats.append(f"Suspicious content in file tail: {pattern[:20]!r}")
                    break

        return threats

    def sanitize(self, img):
        """
        Sanitize image by re-encoding pixels ONLY.
        This removes ALL embedded data:
        - EXIF metadata
        - GPS coordinates
        - Camera info
        - Embedded thumbnails
        - Comments
        - ICC profiles (rebuilt from scratch)
        - Any malicious payload

        The resulting image contains ONLY pixel data.
        """
        from PIL import Image

        # Extract raw pixel data
        pixel_data = list(img.getdata())

        # Create brand new image with ONLY pixels
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(pixel_data)

        # Normalize color mode
        if clean_img.mode in ('RGBA', 'LA', 'PA', 'P'):
            # Handle transparency
            if clean_img.mode == 'P':
                clean_img = clean_img.convert('RGBA')
            if 'A' in clean_img.mode:
                # Keep alpha channel
                clean_img = clean_img.convert('RGBA')
            else:
                clean_img = clean_img.convert('RGB')
        elif clean_img.mode not in ('RGB', 'L'):
            clean_img = clean_img.convert('RGB')

        self.logger.debug(f"Sanitized image: {img.size}, mode {img.mode} → {clean_img.mode}")

        return clean_img


class ImageCompressor:
    """
    Step 3: WebP compression with STRICT 1MB limit.
    Will resize image if necessary to meet size requirement.
    """

    def __init__(self, max_size: int = MAX_OUTPUT_SIZE):
        self.max_size = max_size
        self.logger = logging.getLogger(f"{__name__}.ImageCompressor")

    def compress_to_webp(
        self,
        img,
        target_quality: int = TARGET_QUALITY,
        min_quality: int = MIN_QUALITY,
    ) -> Tuple[Optional[bytes], dict]:
        """
        Compress image to WebP format.
        GUARANTEED to be under max_size or returns None.

        Returns:
            Tuple of (compressed_bytes, metadata_dict)
            Returns (None, {error: ...}) if cannot compress to target size
        """
        from PIL import Image

        original_size = img.size
        current_img = img
        has_alpha = img.mode == 'RGBA'
        quality = target_quality
        resized = False
        final_size = original_size

        # Strategy 1: Reduce quality (small steps for maximum quality)
        while quality >= min_quality:
            data = self._encode_webp(current_img, quality, has_alpha)

            if len(data) <= self.max_size:
                return data, {
                    'quality': quality,
                    'original_size': original_size,
                    'final_size': final_size,
                    'resized': resized,
                    'compression_ratio': round(len(data) / (original_size[0] * original_size[1] * 3), 4),
                }

            quality -= 2  # Small steps (2%) to find optimal quality

        # Strategy 2: Progressive resize while keeping quality at minimum (85%+)
        # Resize image instead of reducing quality below 85%
        for scale in [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]:
            new_width = max(MIN_DIMENSION, int(original_size[0] * scale))
            new_height = max(MIN_DIMENSION, int(original_size[1] * scale))

            if new_width < MIN_DIMENSION or new_height < MIN_DIMENSION:
                break

            # High-quality resize
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Try quality range on resized image (starting high, minimum 85%)
            for q in range(target_quality, min_quality - 1, -2):
                data = self._encode_webp(resized_img, q, has_alpha)

                if len(data) <= self.max_size:
                    return data, {
                        'quality': q,
                        'original_size': original_size,
                        'final_size': (new_width, new_height),
                        'resized': True,
                        'scale_factor': scale,
                        'compression_ratio': round(len(data) / (new_width * new_height * 3), 4),
                    }

        # Failed to compress to target size
        self.logger.error(f"Cannot compress {original_size} image to under {self.max_size} bytes")
        return None, {'error': f'Cannot compress to under {self.max_size // 1024}KB'}

    def _encode_webp(self, img, quality: int, has_alpha: bool) -> bytes:
        """Encode image to WebP bytes."""
        buffer = io.BytesIO()

        if has_alpha:
            img.save(buffer, format='WEBP', quality=quality, method=6, lossless=False)
        else:
            rgb_img = img.convert('RGB') if img.mode != 'RGB' else img
            rgb_img.save(buffer, format='WEBP', quality=quality, method=6, lossless=False)

        return buffer.getvalue()


class ImageProcessor(BaseProcessor):
    """
    Complete Image Processing Pipeline
    ===================================

    STRICT REQUIREMENTS:
    1. Input: Any supported image format (JPEG, PNG, GIF, WebP, BMP)
    2. Security scan: Detect embedded malicious content
    3. Sanitization: Remove ALL metadata, re-encode pixels only
    4. Output: WebP format, MUST be < 1MB

    Pipeline:
    ┌──────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────┐
    │  Input   │ → │ Scan & Log  │ → │  Sanitize    │ → │  WebP < 1MB │
    │  Image   │    │  Threats    │    │  (pixels)   │    │  (strict)   │
    └──────────┘    └─────────────┘    └──────────────┘    └────────────┘

    Usage:
        processor = ImageProcessor()
        result = processor.process(image_bytes)

        if result.success:
            webp_data = result.content  # Guaranteed WebP < 1MB
            threats = result.threats_sanitized  # List of detected threats
    """

    SUPPORTED_MIMES = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'image/bmp',
        'image/tiff',
    ]

    def __init__(self, max_output_size: int = MAX_OUTPUT_SIZE):
        super().__init__()
        self.max_output_size = max_output_size
        self.sanitizer = ImageSanitizer()
        self.compressor = ImageCompressor(max_size=max_output_size)

    def can_process(self, mime_type: str) -> bool:
        """Check if this processor can handle the given MIME type."""
        return mime_type.lower() in self.SUPPORTED_MIMES

    def process(self, data: bytes, **options) -> ProcessingResult:
        """
        Process an image through the security-first pipeline.

        Args:
            data: Raw image bytes
            **options:
                max_size: Max output size in bytes (default 1MB - STRICT)
                quality: Target quality 0-100 (default 92)
                generate_thumbnail: Generate thumbnail (default True)
                thumbnail_size: Tuple (width, height) for thumbnail

        Returns:
            ProcessingResult with:
                - success: True if processing completed
                - content: WebP bytes (GUARANTEED < 1MB if success=True)
                - threats_sanitized: List of detected threats that were removed
                - error: Error message if failed
        """
        try:
            from PIL import Image, ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
        except ImportError:
            return ProcessingResult(
                success=False,
                media_type=MediaType.IMAGE,
                original_size=len(data),
                error="Pillow library not installed. Run: pip install Pillow",
            )

        # Parse options
        max_size = options.get('max_size', self.max_output_size)
        quality = options.get('quality', TARGET_QUALITY)
        gen_thumbnail = options.get('generate_thumbnail', True)
        thumb_size = options.get('thumbnail_size', THUMBNAIL_SIZE)

        original_size = len(data)
        warnings = []

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: SECURITY SCAN
        # ═══════════════════════════════════════════════════════════════════
        self.logger.info(f"[STEP 1/4] Security scan for {original_size} bytes")
        threats = self.sanitizer.scan_threats(data)

        if threats:
            self.logger.warning(f"THREATS DETECTED ({len(threats)}): {threats}")
            # Continue processing - threats will be removed via sanitization

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: VALIDATE & LOAD IMAGE
        # ═══════════════════════════════════════════════════════════════════
        self.logger.info("[STEP 2/4] Validating and loading image")
        try:
            img = Image.open(io.BytesIO(data))
            img.load()  # Force full decode to catch bombs/corruption
        except Exception as e:
            return ProcessingResult(
                success=False,
                media_type=MediaType.IMAGE,
                original_size=original_size,
                error=f"Invalid or corrupted image: {str(e)}",
                threats_sanitized=threats,
            )

        # Validate dimensions
        width, height = img.size

        if width < MIN_DIMENSION or height < MIN_DIMENSION:
            return ProcessingResult(
                success=False,
                media_type=MediaType.IMAGE,
                original_size=original_size,
                error=f"Image too small: {width}x{height} (minimum {MIN_DIMENSION}x{MIN_DIMENSION})",
            )

        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            return ProcessingResult(
                success=False,
                media_type=MediaType.IMAGE,
                original_size=original_size,
                error=f"Image too large: {width}x{height} (maximum {MAX_DIMENSION}x{MAX_DIMENSION})",
            )

        # Check for suspicious aspect ratios
        aspect = max(width, height) / max(min(width, height), 1)
        if aspect > 20:
            warnings.append(f"Unusual aspect ratio: {aspect:.1f}:1")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: SANITIZATION (RE-ENCODE PIXELS ONLY)
        # ═══════════════════════════════════════════════════════════════════
        self.logger.info("[STEP 3/4] Sanitizing image (re-encoding pixels)")
        clean_img = self.sanitizer.sanitize(img)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: COMPRESS TO WEBP (STRICT < 1MB)
        # ═══════════════════════════════════════════════════════════════════
        self.logger.info(f"[STEP 4/4] Compressing to WebP (max {max_size // 1024}KB)")

        compressed_data, compress_meta = self.compressor.compress_to_webp(
            clean_img,
            target_quality=quality,
            min_quality=MIN_QUALITY,
        )

        if compressed_data is None:
            return ProcessingResult(
                success=False,
                media_type=MediaType.IMAGE,
                original_size=original_size,
                error=compress_meta.get('error', 'Compression failed'),
                threats_sanitized=threats,
            )

        # VERIFY size limit (paranoid check)
        if len(compressed_data) > max_size:
            return ProcessingResult(
                success=False,
                media_type=MediaType.IMAGE,
                original_size=original_size,
                error=f"INTERNAL ERROR: Output {len(compressed_data)} exceeds {max_size} limit",
                threats_sanitized=threats,
            )

        if compress_meta.get('resized'):
            warnings.append(
                f"Image resized from {compress_meta['original_size']} to {compress_meta['final_size']}"
            )

        # ═══════════════════════════════════════════════════════════════════
        # OPTIONAL: GENERATE THUMBNAIL
        # ═══════════════════════════════════════════════════════════════════
        thumbnail_data = None
        if gen_thumbnail:
            thumbnail_data = self._generate_thumbnail(clean_img, thumb_size)

        # ═══════════════════════════════════════════════════════════════════
        # BUILD RESULT
        # ═══════════════════════════════════════════════════════════════════
        checksum = self.calculate_checksum(compressed_data)

        self.logger.info(
            f"SUCCESS: {original_size} → {len(compressed_data)} bytes "
            f"({compress_meta.get('quality', '?')}% quality, "
            f"{len(threats)} threats sanitized)"
        )

        return ProcessingResult(
            success=True,
            content=compressed_data,
            media_type=MediaType.IMAGE,
            mime_type='image/webp',
            extension='webp',
            metadata={
                'original_dimensions': (width, height),
                'final_dimensions': compress_meta.get('final_size', (width, height)),
                'quality': compress_meta.get('quality', quality),
                'format': 'webp',
                'has_alpha': clean_img.mode == 'RGBA',
                'resized': compress_meta.get('resized', False),
            },
            threats_sanitized=threats,
            warnings=warnings,
            checksum_sha256=checksum,
            original_size=original_size,
            processed_size=len(compressed_data),
            thumbnail=thumbnail_data,
        )

    def _generate_thumbnail(self, img, size: Tuple[int, int]) -> Optional[bytes]:
        """Generate a WebP thumbnail."""
        try:
            from PIL import Image

            thumb = img.copy()
            thumb.thumbnail(size, Image.Resampling.LANCZOS)

            # Ensure RGB/RGBA
            if thumb.mode not in ('RGB', 'RGBA'):
                thumb = thumb.convert('RGB')

            buffer = io.BytesIO()
            thumb.save(buffer, format='WEBP', quality=80, method=6)
            return buffer.getvalue()

        except Exception as e:
            self.logger.warning(f"Thumbnail generation failed: {e}")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def process_image(data: bytes, **options) -> ProcessingResult:
    """
    Convenience function to process an image.

    Args:
        data: Raw image bytes
        **options: Processing options (see ImageProcessor.process)

    Returns:
        ProcessingResult with WebP output guaranteed < 1MB
    """
    processor = ImageProcessor()
    return processor.process(data, **options)


def sanitize_and_compress(data: bytes, max_size: int = MAX_OUTPUT_SIZE) -> ProcessingResult:
    """
    Quick sanitize and compress to WebP.

    Args:
        data: Raw image bytes
        max_size: Maximum output size (default 1MB)

    Returns:
        ProcessingResult
    """
    processor = ImageProcessor(max_output_size=max_size)
    return processor.process(data, generate_thumbnail=False)

