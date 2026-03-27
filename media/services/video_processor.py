# -*- coding: utf-8 -*-
"""
Video Processor
===============
Processes video files:
- Validates video structure and codec
- Compresses/transcodes to web-friendly formats (MP4/WebM)
- Extracts thumbnail frames
- Strips metadata for privacy
- Enforces duration and size limits
"""
import io
import logging
import subprocess
import tempfile
import os
from typing import Optional, Tuple

from .base import BaseProcessor, ProcessingResult, MediaType

logger = logging.getLogger(__name__)

# Constants
MAX_DURATION = 600  # 10 minutes
MAX_OUTPUT_SIZE = 100 * 1024 * 1024  # 100MB
DEFAULT_BITRATE = '2M'
THUMBNAIL_TIME = 1  # Second to capture thumbnail


class VideoProcessor(BaseProcessor):
    """
    Processes videos with focus on:
    1. Format validation and security
    2. Compression to web-friendly format
    3. Thumbnail extraction
    4. Metadata stripping

    Note: Requires ffmpeg to be installed on the server.
    """

    SUPPORTED_MIMES = [
        'video/mp4',
        'video/webm',
        'video/avi',
        'video/mpeg',
        'video/quicktime',
        'video/x-msvideo',
        'video/x-matroska',
    ]

    def __init__(self):
        super().__init__()
        self._ffmpeg_available = None

    def can_process(self, mime_type: str) -> bool:
        return mime_type.lower() in self.SUPPORTED_MIMES

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        if self._ffmpeg_available is not None:
            return self._ffmpeg_available

        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            self._ffmpeg_available = result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            self._ffmpeg_available = False

        return self._ffmpeg_available

    def process(self, data: bytes, **options) -> ProcessingResult:
        """
        Process a video file.

        Options:
            max_duration: Maximum duration in seconds (default 600)
            max_size: Maximum output size in bytes (default 100MB)
            bitrate: Target bitrate (default '2M')
            generate_thumbnail: Whether to generate thumbnail (default True)
            output_format: Output format 'mp4' or 'webm' (default 'mp4')
        """
        if not self._check_ffmpeg():
            return ProcessingResult(
                success=False,
                media_type=MediaType.VIDEO,
                original_size=len(data),
                error="ffmpeg not available on server",
            )

        max_duration = options.get('max_duration', MAX_DURATION)
        max_size = options.get('max_size', MAX_OUTPUT_SIZE)
        bitrate = options.get('bitrate', DEFAULT_BITRATE)
        gen_thumbnail = options.get('generate_thumbnail', True)
        output_format = options.get('output_format', 'mp4')

        original_size = len(data)
        threats = []
        warnings = []
        thumbnail_data = None

        try:
            # Scan for embedded threats
            threats = self.scan_for_threats(data)
            if threats:
                self.logger.warning(f"Video threats detected: {threats}")

            # Write to temp file for ffmpeg processing
            with tempfile.NamedTemporaryFile(suffix='.video', delete=False) as tmp_in:
                tmp_in.write(data)
                tmp_in_path = tmp_in.name

            try:
                # Get video info
                info = self._get_video_info(tmp_in_path)
                if not info['success']:
                    return ProcessingResult(
                        success=False,
                        media_type=MediaType.VIDEO,
                        original_size=original_size,
                        error=info.get('error', 'Failed to read video info'),
                    )

                duration = info.get('duration', 0)
                width = info.get('width', 0)
                height = info.get('height', 0)

                # Validate duration
                if duration > max_duration:
                    return ProcessingResult(
                        success=False,
                        media_type=MediaType.VIDEO,
                        original_size=original_size,
                        error=f"Video too long: {duration:.0f}s exceeds {max_duration}s limit",
                    )

                # Generate thumbnail
                if gen_thumbnail:
                    thumbnail_data = self._generate_thumbnail(tmp_in_path, min(THUMBNAIL_TIME, duration/2))

                # Transcode to clean format (strips metadata, re-encodes)
                with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as tmp_out:
                    tmp_out_path = tmp_out.name

                success = self._transcode_video(
                    tmp_in_path, tmp_out_path, bitrate, output_format
                )

                if not success:
                    return ProcessingResult(
                        success=False,
                        media_type=MediaType.VIDEO,
                        original_size=original_size,
                        error="Video transcoding failed",
                    )

                # Read processed video
                with open(tmp_out_path, 'rb') as f:
                    processed_data = f.read()

                # Clean up output temp file
                os.unlink(tmp_out_path)

                # Check size
                if len(processed_data) > max_size:
                    warnings.append(f"Output size ({len(processed_data)}) exceeds target, consider lower bitrate")

                checksum = self.calculate_checksum(processed_data)

                return ProcessingResult(
                    success=True,
                    content=processed_data,
                    media_type=MediaType.VIDEO,
                    mime_type=f'video/{output_format}',
                    extension=output_format,
                    metadata={
                        'duration': duration,
                        'width': width,
                        'height': height,
                        'bitrate': bitrate,
                        'format': output_format,
                    },
                    threats_sanitized=threats,
                    warnings=warnings,
                    checksum_sha256=checksum,
                    original_size=original_size,
                    processed_size=len(processed_data),
                    thumbnail=thumbnail_data,
                )

            finally:
                # Clean up input temp file
                if os.path.exists(tmp_in_path):
                    os.unlink(tmp_in_path)

        except Exception as e:
            self.logger.error(f"Video processing error: {e}", exc_info=True)
            return ProcessingResult(
                success=False,
                media_type=MediaType.VIDEO,
                original_size=original_size,
                error=f"Processing failed: {str(e)}",
            )

    def _get_video_info(self, path: str) -> dict:
        """Get video metadata using ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)

            if result.returncode != 0:
                return {'success': False, 'error': 'ffprobe failed'}

            import json
            data = json.loads(result.stdout)

            # Extract info
            duration = float(data.get('format', {}).get('duration', 0))

            width = height = 0
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    break

            return {
                'success': True,
                'duration': duration,
                'width': width,
                'height': height,
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _transcode_video(
        self, input_path: str, output_path: str, bitrate: str, format: str
    ) -> bool:
        """Transcode video to clean format."""
        try:
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', 'libx264' if format == 'mp4' else 'libvpx-vp9',
                '-c:a', 'aac' if format == 'mp4' else 'libopus',
                '-b:v', bitrate,
                '-map_metadata', '-1',  # Strip all metadata
                '-fflags', '+bitexact',  # Reproducible output
                '-movflags', '+faststart' if format == 'mp4' else '',
                '-y',  # Overwrite
                output_path
            ]
            # Remove empty args
            cmd = [c for c in cmd if c]

            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0

        except Exception as e:
            self.logger.error(f"Transcode failed: {e}")
            return False

    def _generate_thumbnail(self, path: str, time_sec: float) -> Optional[bytes]:
        """Generate thumbnail from video frame."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            cmd = [
                'ffmpeg',
                '-ss', str(time_sec),
                '-i', path,
                '-vframes', '1',
                '-vf', 'scale=300:-1',
                '-y',
                tmp_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=30)

            if result.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, 'rb') as f:
                    data = f.read()
                os.unlink(tmp_path)

                # Convert to WebP
                from PIL import Image
                img = Image.open(io.BytesIO(data))
                buffer = io.BytesIO()
                img.save(buffer, format='WEBP', quality=80)
                return buffer.getvalue()

            return None

        except Exception as e:
            self.logger.warning(f"Thumbnail generation failed: {e}")
            return None

