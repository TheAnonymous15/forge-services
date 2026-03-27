# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Media Processing Services
==============================================
Intelligent media router with specialized pipelines for:
- Images (sanitization, compression, WebP conversion)
- Documents (PDF/DOCX text extraction, sanitization)
- Video (compression, thumbnail generation, format conversion)
- Audio (compression, format conversion, metadata stripping)

Usage:
    # Simple processing
    from media.services import process_media
    result = process_media(file_bytes)

    # Process and store securely
    from media.services import process_and_store
    result = process_and_store(
        file_bytes,
        filename="document.pdf",
        owner_id="user_123"
    )
    # Returns: {success, file_id, signed_url, processing_info}
"""
from .router import MediaRouter, MediaType, process_media, process_and_store
from .image_processor import ImageProcessor
from .document_processor import DocumentProcessor
from .video_processor import VideoProcessor
from .audio_processor import AudioProcessor
from .base import BaseProcessor, ProcessingResult

__all__ = [
    'MediaRouter',
    'MediaType',
    'process_media',
    'process_and_store',
    'ImageProcessor',
    'DocumentProcessor',
    'VideoProcessor',
    'AudioProcessor',
    'BaseProcessor',
    'ProcessingResult',
]

