# -*- coding: utf-8 -*-
"""
Audio Processor
===============
Processes audio files:
- Validates audio structure
- Compresses/transcodes to web-friendly formats (MP3/OGG)
- Strips metadata (ID3 tags, comments, embedded images)
- Enforces duration and size limits
"""
import io
import logging
import subprocess
import tempfile
import os
from typing import Optional

from .base import BaseProcessor, ProcessingResult, MediaType

logger = logging.getLogger(__name__)

# Constants
MAX_DURATION = 1800  # 30 minutes
MAX_OUTPUT_SIZE = 50 * 1024 * 1024  # 50MB
DEFAULT_BITRATE = '128k'


class AudioProcessor(BaseProcessor):
    """
    Processes audio with focus on:
    1. Format validation and security
    2. Compression to web-friendly format
    3. Metadata stripping for privacy

    Can use ffmpeg (preferred) or pydub+mutagen as fallback.
    """

    SUPPORTED_MIMES = [
        'audio/mpeg',
        'audio/mp3',
        'audio/wav',
        'audio/wave',
        'audio/x-wav',
        'audio/ogg',
        'audio/flac',
        'audio/aac',
        'audio/x-m4a',
        'audio/mp4',
    ]

    def __init__(self):
        super().__init__()
        self._ffmpeg_available = None
        self._pydub_available = None

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

    def _check_pydub(self) -> bool:
        """Check if pydub is available."""
        if self._pydub_available is not None:
            return self._pydub_available

        try:
            from pydub import AudioSegment
            self._pydub_available = True
        except ImportError:
            self._pydub_available = False

        return self._pydub_available

    def process(self, data: bytes, **options) -> ProcessingResult:
        """
        Process an audio file.

        Options:
            max_duration: Maximum duration in seconds (default 1800)
            max_size: Maximum output size in bytes (default 50MB)
            bitrate: Target bitrate (default '128k')
            output_format: Output format 'mp3' or 'ogg' (default 'mp3')
        """
        max_duration = options.get('max_duration', MAX_DURATION)
        max_size = options.get('max_size', MAX_OUTPUT_SIZE)
        bitrate = options.get('bitrate', DEFAULT_BITRATE)
        output_format = options.get('output_format', 'mp3')

        original_size = len(data)
        threats = []
        warnings = []

        try:
            # Scan for embedded threats
            threats = self.scan_for_threats(data)
            if threats:
                self.logger.warning(f"Audio threats detected: {threats}")

            # Try ffmpeg first (more reliable)
            if self._check_ffmpeg():
                return self._process_with_ffmpeg(
                    data, max_duration, max_size, bitrate, output_format, threats
                )

            # Fallback to pydub
            if self._check_pydub():
                return self._process_with_pydub(
                    data, max_duration, max_size, bitrate, output_format, threats
                )

            return ProcessingResult(
                success=False,
                media_type=MediaType.AUDIO,
                original_size=original_size,
                error="No audio processing backend available (need ffmpeg or pydub)",
            )

        except Exception as e:
            self.logger.error(f"Audio processing error: {e}", exc_info=True)
            return ProcessingResult(
                success=False,
                media_type=MediaType.AUDIO,
                original_size=original_size,
                error=f"Processing failed: {str(e)}",
            )

    def _process_with_ffmpeg(
        self, data: bytes, max_duration: int, max_size: int,
        bitrate: str, output_format: str, threats: list
    ) -> ProcessingResult:
        """Process audio using ffmpeg."""
        original_size = len(data)
        warnings = []

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix='.audio', delete=False) as tmp_in:
            tmp_in.write(data)
            tmp_in_path = tmp_in.name

        try:
            # Get audio info
            info = self._get_audio_info(tmp_in_path)
            if not info['success']:
                return ProcessingResult(
                    success=False,
                    media_type=MediaType.AUDIO,
                    original_size=original_size,
                    error=info.get('error', 'Failed to read audio info'),
                )

            duration = info.get('duration', 0)

            # Validate duration
            if duration > max_duration:
                return ProcessingResult(
                    success=False,
                    media_type=MediaType.AUDIO,
                    original_size=original_size,
                    error=f"Audio too long: {duration:.0f}s exceeds {max_duration}s limit",
                )

            # Transcode
            with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as tmp_out:
                tmp_out_path = tmp_out.name

            success = self._transcode_audio(tmp_in_path, tmp_out_path, bitrate, output_format)

            if not success:
                return ProcessingResult(
                    success=False,
                    media_type=MediaType.AUDIO,
                    original_size=original_size,
                    error="Audio transcoding failed",
                )

            # Read processed audio
            with open(tmp_out_path, 'rb') as f:
                processed_data = f.read()

            os.unlink(tmp_out_path)

            # Check size
            if len(processed_data) > max_size:
                warnings.append(f"Output size ({len(processed_data)}) exceeds target")

            checksum = self.calculate_checksum(processed_data)

            return ProcessingResult(
                success=True,
                content=processed_data,
                media_type=MediaType.AUDIO,
                mime_type='audio/mpeg' if output_format == 'mp3' else 'audio/ogg',
                extension=output_format,
                metadata={
                    'duration': duration,
                    'bitrate': bitrate,
                    'format': output_format,
                    'sample_rate': info.get('sample_rate', 0),
                    'channels': info.get('channels', 0),
                },
                threats_sanitized=threats,
                warnings=warnings,
                checksum_sha256=checksum,
                original_size=original_size,
                processed_size=len(processed_data),
            )

        finally:
            if os.path.exists(tmp_in_path):
                os.unlink(tmp_in_path)

    def _process_with_pydub(
        self, data: bytes, max_duration: int, max_size: int,
        bitrate: str, output_format: str, threats: list
    ) -> ProcessingResult:
        """Process audio using pydub (fallback)."""
        from pydub import AudioSegment

        original_size = len(data)
        warnings = []

        try:
            # Load audio
            audio = AudioSegment.from_file(io.BytesIO(data))

            duration = len(audio) / 1000  # milliseconds to seconds

            # Validate duration
            if duration > max_duration:
                return ProcessingResult(
                    success=False,
                    media_type=MediaType.AUDIO,
                    original_size=original_size,
                    error=f"Audio too long: {duration:.0f}s exceeds {max_duration}s limit",
                )

            # Export with specified format and bitrate
            buffer = io.BytesIO()

            # Parse bitrate (e.g., '128k' -> 128)
            bitrate_int = int(bitrate.replace('k', '').replace('K', ''))

            audio.export(
                buffer,
                format=output_format,
                bitrate=f"{bitrate_int}k",
                tags={}  # Clear all tags
            )

            processed_data = buffer.getvalue()

            # Strip any remaining metadata with mutagen
            processed_data = self._strip_metadata(processed_data, output_format)

            checksum = self.calculate_checksum(processed_data)

            return ProcessingResult(
                success=True,
                content=processed_data,
                media_type=MediaType.AUDIO,
                mime_type='audio/mpeg' if output_format == 'mp3' else 'audio/ogg',
                extension=output_format,
                metadata={
                    'duration': duration,
                    'bitrate': bitrate,
                    'format': output_format,
                    'sample_rate': audio.frame_rate,
                    'channels': audio.channels,
                },
                threats_sanitized=threats,
                warnings=warnings,
                checksum_sha256=checksum,
                original_size=original_size,
                processed_size=len(processed_data),
            )

        except Exception as e:
            return ProcessingResult(
                success=False,
                media_type=MediaType.AUDIO,
                original_size=original_size,
                error=f"Pydub processing failed: {str(e)}",
            )

    def _get_audio_info(self, path: str) -> dict:
        """Get audio metadata using ffprobe."""
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

            duration = float(data.get('format', {}).get('duration', 0))

            sample_rate = channels = 0
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    sample_rate = int(stream.get('sample_rate', 0))
                    channels = stream.get('channels', 0)
                    break

            return {
                'success': True,
                'duration': duration,
                'sample_rate': sample_rate,
                'channels': channels,
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _transcode_audio(
        self, input_path: str, output_path: str, bitrate: str, format: str
    ) -> bool:
        """Transcode audio to clean format."""
        try:
            codec = 'libmp3lame' if format == 'mp3' else 'libvorbis'

            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:a', codec,
                '-b:a', bitrate,
                '-map_metadata', '-1',  # Strip all metadata
                '-fflags', '+bitexact',
                '-y',
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)
            return result.returncode == 0

        except Exception as e:
            self.logger.error(f"Transcode failed: {e}")
            return False

    def _strip_metadata(self, data: bytes, format: str) -> bytes:
        """Strip metadata using mutagen if available."""
        try:
            import mutagen
            from mutagen.mp3 import MP3
            from mutagen.oggvorbis import OggVorbis

            buffer = io.BytesIO(data)

            if format == 'mp3':
                audio = MP3(buffer)
            elif format == 'ogg':
                audio = OggVorbis(buffer)
            else:
                return data

            # Delete all tags
            audio.delete()

            # Write back
            output = io.BytesIO()
            audio.save(output)
            return output.getvalue()

        except Exception:
            # If mutagen fails, return original (ffmpeg already stripped metadata)
            return data

