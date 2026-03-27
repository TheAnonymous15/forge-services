# -*- coding: utf-8 -*-
"""
Intelligent Media Router
========================
Automatically detects media type and routes to the appropriate processor.
Handles async processing via Celery for large files.
"""
import logging
from typing import Any, Dict, Optional, Union, BinaryIO

from .base import (
    BaseProcessor,
    ProcessingResult,
    MediaType,
    detect_mime_type,
    get_media_type_from_mime,
)

logger = logging.getLogger(__name__)

# Size thresholds for async processing (in bytes)
ASYNC_THRESHOLD_IMAGE = 5 * 1024 * 1024      # 5MB
ASYNC_THRESHOLD_DOCUMENT = 10 * 1024 * 1024   # 10MB
ASYNC_THRESHOLD_VIDEO = 10 * 1024 * 1024      # 10MB
ASYNC_THRESHOLD_AUDIO = 10 * 1024 * 1024      # 10MB

# Maximum file sizes (in bytes)
MAX_SIZE_IMAGE = 50 * 1024 * 1024       # 50MB
MAX_SIZE_DOCUMENT = 100 * 1024 * 1024   # 100MB
MAX_SIZE_VIDEO = 500 * 1024 * 1024      # 500MB
MAX_SIZE_AUDIO = 100 * 1024 * 1024      # 100MB


class MediaRouter:
    """
    Intelligent media processor that:
    1. Detects the media type from file content (not extension)
    2. Routes to the appropriate specialized processor
    3. Decides sync vs async processing based on file size
    4. Returns a unified ProcessingResult

    Usage:
        router = MediaRouter()
        result = router.process(file_data)

        # Or with options
        result = router.process(file_data,
            max_image_size=1024*1024,
            extract_text=True,
            generate_thumbnail=True
        )

        # Check if should process async
        if router.should_process_async(file_data):
            task = router.process_async.delay(file_data)
    """

    def __init__(self):
        self.logger = logger
        self._processors: Dict[MediaType, BaseProcessor] = {}
        self._initialize_processors()

    def _initialize_processors(self):
        """Lazy-load processors to avoid import errors if dependencies missing."""
        pass  # Processors loaded on demand

    def _get_processor(self, media_type: MediaType) -> Optional[BaseProcessor]:
        """Get or create processor for the given media type."""
        if media_type in self._processors:
            return self._processors[media_type]

        try:
            if media_type == MediaType.IMAGE:
                from .image_processor import ImageProcessor
                self._processors[media_type] = ImageProcessor()
            elif media_type == MediaType.DOCUMENT:
                from .document_processor import DocumentProcessor
                self._processors[media_type] = DocumentProcessor()
            elif media_type == MediaType.VIDEO:
                from .video_processor import VideoProcessor
                self._processors[media_type] = VideoProcessor()
            elif media_type == MediaType.AUDIO:
                from .audio_processor import AudioProcessor
                self._processors[media_type] = AudioProcessor()
            else:
                return None

            return self._processors.get(media_type)
        except ImportError as e:
            self.logger.error(f"Failed to load processor for {media_type}: {e}")
            return None

    def detect_type(self, data: bytes) -> tuple[MediaType, str]:
        """
        Detect media type and MIME type from file content.

        Returns:
            Tuple of (MediaType, mime_type_string)
        """
        mime_type = detect_mime_type(data)
        media_type = get_media_type_from_mime(mime_type)
        return media_type, mime_type

    def get_max_size(self, media_type: MediaType) -> int:
        """Get maximum allowed file size for a media type."""
        return {
            MediaType.IMAGE: MAX_SIZE_IMAGE,
            MediaType.DOCUMENT: MAX_SIZE_DOCUMENT,
            MediaType.VIDEO: MAX_SIZE_VIDEO,
            MediaType.AUDIO: MAX_SIZE_AUDIO,
        }.get(media_type, MAX_SIZE_DOCUMENT)

    def get_async_threshold(self, media_type: MediaType) -> int:
        """Get the file size threshold for async processing."""
        return {
            MediaType.IMAGE: ASYNC_THRESHOLD_IMAGE,
            MediaType.DOCUMENT: ASYNC_THRESHOLD_DOCUMENT,
            MediaType.VIDEO: ASYNC_THRESHOLD_VIDEO,
            MediaType.AUDIO: ASYNC_THRESHOLD_AUDIO,
        }.get(media_type, ASYNC_THRESHOLD_DOCUMENT)

    def should_process_async(self, data: bytes) -> bool:
        """
        Determine if the file should be processed asynchronously.

        Args:
            data: File content as bytes

        Returns:
            True if file should be processed via Celery task
        """
        media_type, _ = self.detect_type(data)
        threshold = self.get_async_threshold(media_type)
        return len(data) > threshold

    def validate_size(self, data: bytes, media_type: MediaType) -> Optional[str]:
        """
        Validate file size against limits.

        Returns:
            Error message if too large, None if OK
        """
        max_size = self.get_max_size(media_type)
        if len(data) > max_size:
            size_mb = len(data) / (1024 * 1024)
            max_mb = max_size / (1024 * 1024)
            return f"File too large: {size_mb:.1f}MB exceeds {max_mb:.0f}MB limit for {media_type.value}"
        return None

    def process(
        self,
        input_data: Union[bytes, BinaryIO],
        **options
    ) -> ProcessingResult:
        """
        Process a media file through the appropriate pipeline.

        Args:
            input_data: Raw bytes or file-like object
            **options: Processor-specific options:
                - max_image_size: Max output size for images (default 1MB)
                - image_quality: Target quality for images (default 92)
                - extract_text: Extract text from documents (default True)
                - generate_thumbnail: Generate thumbnail (default True)
                - video_max_duration: Max video duration in seconds
                - audio_bitrate: Target audio bitrate

        Returns:
            ProcessingResult with processed content and metadata
        """
        try:
            # Read data if file-like object
            if hasattr(input_data, 'read'):
                input_data.seek(0)
                data = input_data.read()
                if hasattr(input_data, 'seek'):
                    input_data.seek(0)
            else:
                data = input_data

            original_size = len(data)

            # Detect type
            media_type, mime_type = self.detect_type(data)
            self.logger.info(f"Detected media type: {media_type.value} ({mime_type}), size: {original_size} bytes")

            # Validate size
            size_error = self.validate_size(data, media_type)
            if size_error:
                return ProcessingResult(
                    success=False,
                    media_type=media_type,
                    mime_type=mime_type,
                    original_size=original_size,
                    error=size_error,
                )

            # Get processor
            processor = self._get_processor(media_type)
            if not processor:
                return ProcessingResult(
                    success=False,
                    media_type=media_type,
                    mime_type=mime_type,
                    original_size=original_size,
                    error=f"No processor available for {media_type.value} ({mime_type})",
                )

            # Process
            self.logger.info(f"Processing {media_type.value} with {processor.__class__.__name__}")
            result = processor.process(data, **options)

            # Ensure media type is set
            result.media_type = media_type
            result.original_size = original_size

            return result

        except Exception as e:
            self.logger.error(f"Media processing failed: {e}", exc_info=True)
            return ProcessingResult(
                success=False,
                error=f"Processing failed: {str(e)}",
            )

    def process_uploaded_file(self, uploaded_file, **options) -> ProcessingResult:
        """
        Process a Django UploadedFile.

        Args:
            uploaded_file: Django UploadedFile from request.FILES
            **options: Processor-specific options

        Returns:
            ProcessingResult with original filename in metadata
        """
        try:
            uploaded_file.seek(0)
            data = uploaded_file.read()
            uploaded_file.seek(0)

            result = self.process(data, **options)

            # Add original filename to metadata
            if result.metadata is None:
                result.metadata = {}
            result.metadata['original_filename'] = getattr(uploaded_file, 'name', 'unknown')

            return result

        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Failed to read uploaded file: {str(e)}",
            )

    def get_supported_types(self) -> Dict[MediaType, list]:
        """Get list of supported MIME types per media type."""
        return {
            MediaType.IMAGE: [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp',
            ],
            MediaType.DOCUMENT: [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
            ],
            MediaType.VIDEO: [
                'video/mp4', 'video/webm', 'video/avi', 'video/mpeg', 'video/quicktime',
            ],
            MediaType.AUDIO: [
                'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/flac', 'audio/aac',
            ],
        }


# Convenience function
def process_media(input_data: Union[bytes, BinaryIO], **options) -> ProcessingResult:
    """
    Convenience function to process media without creating a router instance.

    Args:
        input_data: Raw bytes or file-like object
        **options: Processor-specific options

    Returns:
        ProcessingResult
    """
    router = MediaRouter()
    return router.process(input_data, **options)


def process_and_store(
    input_data: Union[bytes, BinaryIO],
    filename: str,
    owner_id: Optional[str] = None,
    owner_type: str = 'user',
    metadata: Optional[Dict[str, Any]] = None,
    request_context: Optional[Dict[str, Any]] = None,
    **options
) -> Dict[str, Any]:
    """
    Process media and store in secure storage.

    This is the MAIN entry point for file uploads:
    1. Detect media type
    2. Process through appropriate pipeline (sanitize, compress, etc.)
    3. Store in secure encrypted storage
    4. Return signed URL for access

    Args:
        input_data: Raw bytes or file-like object
        filename: Original filename
        owner_id: User/Organization ID who owns the file
        owner_type: 'user' or 'organization'
        metadata: Additional metadata to store
        request_context: Request info (ip_address, user_agent, etc.) for audit
        **options: Processor-specific options

    Returns:
        Dict with:
        - success: bool
        - file_id: str (if success)
        - signed_url: str (if success)
        - error: str (if failed)
        - processing_info: dict (processing metadata)
    """
    # Import here to avoid circular imports
    from storage.services import store_file

    router = MediaRouter()

    # Process the media
    result = router.process(input_data, **options)

    if not result.success:
        return {
            'success': False,
            'error': result.error or 'Processing failed',
            'processing_info': {
                'media_type': result.media_type.value if result.media_type else None,
                'threats': result.threats_detected,
            }
        }

    # Prepare metadata
    store_metadata = metadata or {}
    store_metadata['original_filename'] = filename
    store_metadata['processing'] = result.metadata or {}

    # Determine output filename
    output_filename = filename
    if result.output_format:
        # Change extension if format changed (e.g., jpg -> webp)
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        output_filename = f"{base_name}.{result.output_format}"

    # Store in secure storage
    storage_result = store_file(
        data=result.content or input_data,  # Use processed content, or original if none
        filename=output_filename,
        mime_type=result.output_mime_type or result.mime_type or 'application/octet-stream',
        owner_id=owner_id,
        owner_type=owner_type,
        metadata=store_metadata,
        media_type=result.media_type.value if result.media_type else 'other',
        processing_info={
            'compression_ratio': result.compression_ratio,
            'original_size': result.original_size,
            'final_size': result.final_size,
            'format_converted': result.output_format is not None,
        },
        threats_detected=result.threats_detected or [],
        request_context=request_context,
    )

    if not storage_result['success']:
        return {
            'success': False,
            'error': storage_result.get('error', 'Storage failed'),
            'processing_info': result.metadata,
        }

    return {
        'success': True,
        'file_id': storage_result['file_id'],
        'signed_url': storage_result['signed_url'],
        'url_expires_at': storage_result['url_expires_at'],
        'processing_info': {
            'media_type': result.media_type.value if result.media_type else None,
            'original_size': result.original_size,
            'final_size': result.final_size,
            'compression_ratio': result.compression_ratio,
            'format': result.output_format,
            'threats_detected': result.threats_detected,
        },
        'file_info': storage_result.get('stored_file', {}),
    }

