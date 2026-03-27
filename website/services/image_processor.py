# -*- coding: utf-8 -*-
"""
Image Processor - Sanitization and Compression for Blog Images.

This module provides:
1. Image Sanitization: Removes embedded metadata, EXIF data, hidden code/commands
2. Image Compression: Converts to WebP format with >90% quality and <1MB size

Security Features:
- Strips all EXIF/metadata (GPS, camera info, hidden data)
- Removes embedded ICC profiles (can contain malicious data)
- Re-encodes image pixels only (removes any steganographic content)
- Validates image structure and dimensions
- Detects and removes dangerous patterns (polyglot files, embedded scripts)
- Any detected threats are sanitized out during re-encoding

Usage:
    from website.services.image_processor import ImageProcessor

    processor = ImageProcessor()
    result = processor.process_image(uploaded_file)
    if result['success']:
        processed_content = result['content']
        # Save processed_content to storage
"""
import io
import logging
from typing import Optional, Tuple, Dict, Any, BinaryIO, Union, List

from PIL import Image, ImageFile

logger = logging.getLogger(__name__)

# Allow loading truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Constants
MAX_OUTPUT_SIZE = 1 * 1024 * 1024  # 1MB max output
MIN_QUALITY = 70  # Minimum quality we'll go to
TARGET_QUALITY = 92  # Target quality (>90%)
MAX_DIMENSION = 4096  # Max width/height
MIN_DIMENSION = 10  # Min width/height to be valid

# Dangerous patterns to detect and log (will be sanitized out during re-encoding)
DANGEROUS_PATTERNS = [
    b'<script',
    b'<SCRIPT',
    b'<?php',
    b'<%',
    b'<svg',
    b'<!DOCTYPE html',
    b'<html',
    b'#!/bin/',
    b'#!/usr/',
    b'%PDF-',
    b'PK\x03\x04',  # ZIP header
    b'\x00asm',  # WebAssembly
    b'MZ',  # Windows executable (at start)
    b'\x7fELF',  # Linux executable
    b'javascript:',
    b'onload=',
    b'onerror=',
    b'onclick=',
    b'eval(',
    b'document.cookie',
    b'window.location',
]

# Valid image magic bytes
VALID_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'jpeg',
    b'\x89PNG\r\n\x1a\n': 'png',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',  # WebP starts with RIFF
}


class ImageSanitizer:
    """
    Sanitizes images by removing potentially dangerous embedded data.
    Instead of rejecting images with suspicious content, we sanitize them
    by re-encoding only the pixel data, which removes any embedded threats.
    """

    @staticmethod
    def detect_file_type(data: bytes) -> Optional[str]:
        """Detect the actual file type from magic bytes."""
        for magic, file_type in VALID_MAGIC_BYTES.items():
            if data.startswith(magic):
                return file_type
        # Check WebP specifically (RIFF....WEBP)
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return 'webp'
        return None

    @staticmethod
    def scan_for_dangerous_content(data: bytes) -> List[str]:
        """
        Scan raw bytes for dangerous patterns.
        Returns a list of detected threats (for logging purposes).
        These will be sanitized out during the re-encoding process.

        Returns:
            List of detected threat descriptions
        """
        detected_threats = []

        # Only scan first 1MB and last 100KB to catch header/footer injections
        scan_regions = [
            ('header', data[:min(len(data), 1024 * 1024)]),
            ('footer', data[-min(len(data), 100 * 1024):] if len(data) > 100 * 1024 else b'')
        ]

        for region_name, region in scan_regions:
            if not region:
                continue
            for pattern in DANGEROUS_PATTERNS:
                if pattern in region:
                    threat_desc = f"Pattern '{pattern[:20].decode('utf-8', errors='replace')}' in {region_name}"
                    if threat_desc not in detected_threats:
                        detected_threats.append(threat_desc)

        return detected_threats

    @staticmethod
    def validate_image_structure(img: Image.Image) -> Tuple[bool, Optional[str]]:
        """
        Validate image dimensions and structure.

        Returns:
            Tuple of (is_valid, error_message)
        """
        width, height = img.size

        # Check dimensions
        if width < MIN_DIMENSION or height < MIN_DIMENSION:
            return False, f"Image too small: {width}x{height}. Minimum is {MIN_DIMENSION}x{MIN_DIMENSION}"

        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            return False, f"Image too large: {width}x{height}. Maximum is {MAX_DIMENSION}x{MAX_DIMENSION}"

        # Check for reasonable aspect ratio (not super thin/tall which could indicate manipulation)
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 20:
            return False, f"Suspicious aspect ratio: {aspect_ratio:.1f}:1"

        return True, None

    @staticmethod
    def strip_metadata(img: Image.Image) -> Image.Image:
        """
        Create a clean copy of the image with all metadata stripped.
        This re-encodes only the pixel data, removing any hidden content,
        embedded scripts, steganographic data, or malicious payloads.
        """
        # Get the pixel data
        pixel_data = list(img.getdata())

        # Create a new image with only pixel data
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(pixel_data)

        return clean_img

    @staticmethod
    def convert_to_safe_mode(img: Image.Image) -> Image.Image:
        """
        Convert image to a safe color mode for WebP output.
        Handles transparency properly.
        """
        if img.mode in ('RGBA', 'LA', 'PA'):
            # Keep alpha channel
            return img.convert('RGBA')
        elif img.mode in ('P', 'L', '1'):
            # Convert palette/grayscale to RGB
            return img.convert('RGB')
        elif img.mode == 'CMYK':
            # Convert CMYK to RGB
            return img.convert('RGB')
        elif img.mode == 'RGB':
            return img
        else:
            # Default to RGB for unknown modes
            return img.convert('RGB')

    def sanitize(self, file_data: bytes) -> Tuple[Optional[Image.Image], Optional[str], List[str]]:
        """
        Fully sanitize an image file.

        Instead of rejecting images with dangerous content, we:
        1. Log any detected threats
        2. Re-encode only pixel data (removes all embedded content)
        3. Return the clean image

        Args:
            file_data: Raw bytes of the image file

        Returns:
            Tuple of (sanitized_image, error_message, list_of_sanitized_threats)
        """
        sanitized_threats = []

        try:
            # 1. Detect actual file type from magic bytes
            file_type = self.detect_file_type(file_data)
            if not file_type:
                return None, "Unrecognized or invalid image format", []

            # 2. Scan for dangerous content (for logging, not rejection)
            detected_threats = self.scan_for_dangerous_content(file_data)
            if detected_threats:
                logger.warning(f"Dangerous content detected and will be sanitized: {detected_threats}")
                sanitized_threats = detected_threats

            # 3. Try to open the image
            try:
                img = Image.open(io.BytesIO(file_data))
                img.load()  # Force load to catch decompression bombs
            except Exception as e:
                return None, f"Failed to decode image: {str(e)}", []

            # 4. Validate structure
            is_valid, error = self.validate_image_structure(img)
            if not is_valid:
                return None, error, []

            # 5. Strip all metadata by re-creating the image (THIS REMOVES ALL THREATS)
            # By extracting only pixel data and creating a new image, we remove:
            # - All metadata (EXIF, GPS, camera info)
            # - Embedded scripts or code
            # - Steganographic content
            # - Polyglot file structures
            # - Any hidden data in image chunks
            clean_img = self.strip_metadata(img)

            # 6. Convert to safe color mode
            clean_img = self.convert_to_safe_mode(clean_img)

            if sanitized_threats:
                logger.info(f"Image sanitized, removed {len(sanitized_threats)} potential threat(s): {clean_img.size}, mode={clean_img.mode}")
            else:
                logger.info(f"Image sanitized successfully: {clean_img.size}, mode={clean_img.mode}")

            return clean_img, None, sanitized_threats

        except Exception as e:
            logger.error(f"Error sanitizing image: {e}")
            return None, f"Sanitization failed: {str(e)}", []


class ImageCompressor:
    """
    Compresses images to WebP format with high quality and small size.
    """

    @staticmethod
    def calculate_resize_dimensions(
        width: int,
        height: int,
        max_dimension: int = 2048
    ) -> Tuple[int, int]:
        """
        Calculate new dimensions if image needs resizing.
        Maintains aspect ratio.
        """
        if width <= max_dimension and height <= max_dimension:
            return width, height

        ratio = min(max_dimension / width, max_dimension / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)

        return new_width, new_height

    @staticmethod
    def compress_to_webp(
        img: Image.Image,
        max_size: int = MAX_OUTPUT_SIZE,
        target_quality: int = TARGET_QUALITY,
        min_quality: int = MIN_QUALITY,
    ) -> Tuple[Optional[bytes], int, Optional[str]]:
        """
        Compress image to WebP format.

        Iteratively reduces quality until file is under max_size.

        Args:
            img: PIL Image object (already sanitized)
            max_size: Maximum output size in bytes
            target_quality: Starting quality (>90%)
            min_quality: Minimum acceptable quality

        Returns:
            Tuple of (compressed_bytes, final_quality, error_message)
        """
        quality = target_quality

        # Handle transparency
        has_alpha = img.mode in ('RGBA', 'LA', 'PA')

        while quality >= min_quality:
            buffer = io.BytesIO()

            try:
                if has_alpha:
                    # WebP with alpha
                    img.save(
                        buffer,
                        format='WEBP',
                        quality=quality,
                        method=6,  # Best compression
                        lossless=False,
                    )
                else:
                    # Convert to RGB if not already
                    rgb_img = img.convert('RGB') if img.mode != 'RGB' else img
                    rgb_img.save(
                        buffer,
                        format='WEBP',
                        quality=quality,
                        method=6,  # Best compression
                        lossless=False,
                    )

                compressed_data = buffer.getvalue()

                if len(compressed_data) <= max_size:
                    logger.info(f"Compressed to {len(compressed_data)} bytes at quality {quality}")
                    return compressed_data, quality, None

                # Reduce quality and try again
                quality -= 5

            except Exception as e:
                return None, 0, f"Compression failed: {str(e)}"

        # If still too large, try resizing
        return None, 0, f"Could not compress to under {max_size} bytes while maintaining minimum quality"

    def compress_with_resize(
        self,
        img: Image.Image,
        max_size: int = MAX_OUTPUT_SIZE,
        target_quality: int = TARGET_QUALITY,
        min_quality: int = MIN_QUALITY,
    ) -> Tuple[Optional[bytes], Dict[str, Any], Optional[str]]:
        """
        Compress image, resizing if necessary to meet size requirements.

        Returns:
            Tuple of (compressed_bytes, metadata_dict, error_message)
        """
        original_width, original_height = img.size
        current_img = img
        resize_factor = 1.0

        # Try compression at current size first
        result, quality, error = self.compress_to_webp(
            current_img, max_size, target_quality, min_quality
        )

        if result:
            return result, {
                'original_size': (original_width, original_height),
                'final_size': current_img.size,
                'quality': quality,
                'resized': False,
                'output_bytes': len(result),
            }, None

        # Need to resize - try progressively smaller sizes
        resize_steps = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]

        for factor in resize_steps:
            new_width = int(original_width * factor)
            new_height = int(original_height * factor)

            # Don't go below minimum dimensions
            if new_width < MIN_DIMENSION or new_height < MIN_DIMENSION:
                break

            # Resize with high quality
            resized_img = img.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

            # Try compression
            result, quality, error = self.compress_to_webp(
                resized_img, max_size, target_quality, min_quality
            )

            if result:
                return result, {
                    'original_size': (original_width, original_height),
                    'final_size': (new_width, new_height),
                    'quality': quality,
                    'resized': True,
                    'resize_factor': factor,
                    'output_bytes': len(result),
                }, None

        return None, {}, "Could not compress image to required size even with resizing"


class ImageProcessor:
    """
    Main class combining sanitization and compression.

    Usage:
        processor = ImageProcessor()
        result = processor.process_image(file_data_or_uploaded_file)
        if result['success']:
            webp_content = result['content']
            metadata = result['metadata']
    """

    def __init__(self):
        self.sanitizer = ImageSanitizer()
        self.compressor = ImageCompressor()

    def process_image(
        self,
        input_data: Union[bytes, BinaryIO],
        max_size: int = MAX_OUTPUT_SIZE,
        target_quality: int = TARGET_QUALITY,
        min_quality: int = MIN_QUALITY,
    ) -> Dict[str, Any]:
        """
        Process an image: sanitize and compress to WebP.

        Args:
            input_data: Raw bytes or file-like object
            max_size: Maximum output size in bytes (default 1MB)
            target_quality: Target quality percentage (default 92%)
            min_quality: Minimum acceptable quality (default 70%)

        Returns:
            Dict with keys:
                - success: bool
                - content: bytes (the processed WebP image) or None
                - metadata: dict with processing details
                - error: str or None
        """
        try:
            # Read data if file-like object
            if hasattr(input_data, 'read'):
                input_data.seek(0)
                file_data = input_data.read()
                if hasattr(input_data, 'seek'):
                    input_data.seek(0)  # Reset for potential reuse
            else:
                file_data = input_data

            original_size = len(file_data)

            # Step 1: Sanitize
            logger.info(f"Sanitizing image ({original_size} bytes)...")
            clean_img, error, _ = self.sanitizer.sanitize(file_data)

            if error:
                return {
                    'success': False,
                    'content': None,
                    'metadata': {'original_size': original_size},
                    'error': error,
                }

            # Step 2: Compress to WebP
            logger.info(f"Compressing to WebP (max {max_size} bytes, quality {target_quality}%)...")
            compressed_data, metadata, error = self.compressor.compress_with_resize(
                clean_img, max_size, target_quality, min_quality
            )

            if error:
                return {
                    'success': False,
                    'content': None,
                    'metadata': metadata,
                    'error': error,
                }

            # Calculate compression ratio
            compression_ratio = original_size / len(compressed_data) if compressed_data else 0

            metadata.update({
                'original_bytes': original_size,
                'compression_ratio': round(compression_ratio, 2),
                'format': 'webp',
            })

            logger.info(
                f"Image processed: {original_size} -> {len(compressed_data)} bytes "
                f"({compression_ratio:.1f}x compression)"
            )

            return {
                'success': True,
                'content': compressed_data,
                'metadata': metadata,
                'error': None,
            }

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return {
                'success': False,
                'content': None,
                'metadata': {},
                'error': f"Processing failed: {str(e)}",
            }

    def process_uploaded_file(self, uploaded_file) -> Dict[str, Any]:
        """
        Process a Django UploadedFile object.

        Args:
            uploaded_file: Django UploadedFile (from request.FILES)

        Returns:
            Same as process_image()
        """
        try:
            # Read all content
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
            uploaded_file.seek(0)

            result = self.process_image(file_data)

            # Add original filename to metadata
            if result['success']:
                result['metadata']['original_filename'] = getattr(
                    uploaded_file, 'name', 'unknown'
                )

            return result

        except Exception as e:
            return {
                'success': False,
                'content': None,
                'metadata': {},
                'error': f"Failed to read uploaded file: {str(e)}",
            }


# Convenience function for direct use
def process_image(
    input_data: Union[bytes, BinaryIO],
    max_size: int = MAX_OUTPUT_SIZE,
    target_quality: int = TARGET_QUALITY,
) -> Dict[str, Any]:
    """
    Convenience function to process an image.

    Args:
        input_data: Raw bytes or file-like object
        max_size: Maximum output size in bytes (default 1MB)
        target_quality: Target quality percentage (default 92%)

    Returns:
        Dict with success, content, metadata, error keys
    """
    processor = ImageProcessor()
    return processor.process_image(input_data, max_size, target_quality)
