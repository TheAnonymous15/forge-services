# -*- coding: utf-8 -*-
"""
Storage Tasks - Background Processing
======================================
Celery tasks for async file processing.

Processing Pipeline:
1. User uploads file
2. File is stored immediately
3. Processing job is queued
4. Worker processes file in background
5. File record is updated with processing results
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def process_file(self, file_id: str, job_type: str):
    """
    Process a file in the background.

    Args:
        file_id: UUID of the StoredFile
        job_type: Type of processing (process_image, process_document, etc.)
    """
    from storage.models import StoredFile, ProcessingJob
    from storage.services import get_storage_service

    logger.info(f"Processing {job_type} for file {file_id}")

    try:
        stored_file = StoredFile.objects.get(id=file_id)
        job = ProcessingJob.objects.filter(file=stored_file, job_type=job_type).first()

        if job:
            job.start()
            job.celery_task_id = self.request.id
            job.save(update_fields=['celery_task_id'])

        # Get file content
        service = get_storage_service()
        content = service.backend.retrieve(stored_file.storage_path)

        if content is None:
            raise Exception("File not found on disk")

        # Route to appropriate processor
        result = {}

        if job_type == 'process_image':
            result = _process_image(stored_file, content, job)
        elif job_type == 'process_document':
            result = _process_document(stored_file, content, job)
        elif job_type == 'process_video':
            result = _process_video(stored_file, content, job)
        elif job_type == 'process_audio':
            result = _process_audio(stored_file, content, job)
        elif job_type == 'generate_thumbnail':
            result = _generate_thumbnail(stored_file, content, job)
        elif job_type == 'extract_text':
            result = _extract_text(stored_file, content, job)
        elif job_type == 'scan_threats':
            result = _scan_threats(stored_file, content, job)
        else:
            raise Exception(f"Unknown job type: {job_type}")

        # Update file record
        stored_file.is_processed = True
        stored_file.processing_info = result
        stored_file.save(update_fields=['is_processed', 'processing_info', 'updated_at'])

        if job:
            job.complete(result)

        logger.info(f"Completed {job_type} for file {file_id}")
        return result

    except Exception as e:
        logger.error(f"Failed {job_type} for file {file_id}: {e}", exc_info=True)

        if job:
            job.fail(str(e))

        raise


def _process_image(stored_file, content: bytes, job=None) -> dict:
    """Process an image file."""
    from media.services import ImageProcessor

    if job:
        job.update_progress(10, "Initializing image processor")

    processor = ImageProcessor()

    if job:
        job.update_progress(30, "Processing image")

    result = processor.process(content)

    if not result.success:
        raise Exception(result.error or "Image processing failed")

    if job:
        job.update_progress(70, "Saving processed image")

    # If image was compressed, update the stored file
    if result.content and len(result.content) < len(content):
        from storage.services import get_storage_service
        service = get_storage_service()

        # Store processed version
        service.backend.store(stored_file.storage_path, result.content)

        # Update size
        stored_file.stored_size = len(result.content)
        stored_file.save(update_fields=['stored_size'])

    if job:
        job.update_progress(90, "Finalizing")

    return {
        'original_size': result.original_size,
        'final_size': result.final_size,
        'compression_ratio': result.compression_ratio,
        'format': result.output_format,
        'threats_detected': result.threats_detected or [],
    }


def _process_document(stored_file, content: bytes, job=None) -> dict:
    """Process a document file."""
    from media.services import DocumentProcessor

    if job:
        job.update_progress(10, "Initializing document processor")

    processor = DocumentProcessor()

    if job:
        job.update_progress(30, "Processing document")

    result = processor.process(content)

    if not result.success:
        raise Exception(result.error or "Document processing failed")

    if job:
        job.update_progress(90, "Finalizing")

    return {
        'original_size': result.original_size,
        'final_size': result.final_size,
        'page_count': result.metadata.get('page_count'),
        'text_extracted': bool(result.metadata.get('text')),
        'threats_detected': result.threats_detected or [],
    }


def _process_video(stored_file, content: bytes, job=None) -> dict:
    """Process a video file."""
    from media.services import VideoProcessor

    if job:
        job.update_progress(10, "Initializing video processor")

    processor = VideoProcessor()

    if job:
        job.update_progress(20, "Processing video (this may take a while)")

    result = processor.process(content)

    if not result.success:
        raise Exception(result.error or "Video processing failed")

    return {
        'original_size': result.original_size,
        'final_size': result.final_size,
        'duration': result.metadata.get('duration'),
        'resolution': result.metadata.get('resolution'),
        'thumbnail_generated': bool(result.metadata.get('thumbnail')),
    }


def _process_audio(stored_file, content: bytes, job=None) -> dict:
    """Process an audio file."""
    from media.services import AudioProcessor

    if job:
        job.update_progress(10, "Initializing audio processor")

    processor = AudioProcessor()

    if job:
        job.update_progress(30, "Processing audio")

    result = processor.process(content)

    if not result.success:
        raise Exception(result.error or "Audio processing failed")

    return {
        'original_size': result.original_size,
        'final_size': result.final_size,
        'duration': result.metadata.get('duration'),
        'bitrate': result.metadata.get('bitrate'),
    }


def _generate_thumbnail(stored_file, content: bytes, job=None) -> dict:
    """Generate thumbnail for image/video."""
    # Implementation depends on file type
    return {'thumbnail_generated': False}


def _extract_text(stored_file, content: bytes, job=None) -> dict:
    """Extract text from document."""
    from media.services import DocumentProcessor

    processor = DocumentProcessor()
    result = processor.process(content, extract_text=True)

    text = result.metadata.get('text', '') if result.success else ''

    return {
        'text_extracted': bool(text),
        'character_count': len(text),
    }


def _scan_threats(stored_file, content: bytes, job=None) -> dict:
    """Scan file for threats."""
    # This would integrate with antivirus/threat detection
    # For now, basic signature scanning
    threats = []

    # Check for dangerous patterns
    dangerous_patterns = [
        b'<%', b'%>', b'<script', b'javascript:',
        b'<?php', b'eval(', b'exec(',
    ]

    for pattern in dangerous_patterns:
        if pattern in content.lower():
            threats.append(f"Suspicious pattern: {pattern}")

    return {
        'scanned': True,
        'threats_found': len(threats),
        'threats': threats,
    }


# ============================================================
# Cleanup Tasks
# ============================================================

@shared_task
def cleanup_expired_files():
    """Delete expired files. Run daily."""
    from storage.services import get_storage_service

    service = get_storage_service()
    count = service.cleanup_expired()

    logger.info(f"Cleaned up {count} expired files")
    return count


@shared_task
def cleanup_orphan_files():
    """Find and cleanup orphan files. Run weekly."""
    from storage.services import get_storage_service

    service = get_storage_service()

    # Find orphans
    orphans = service.find_orphan_files()
    logger.info(f"Found {len(orphans)} orphan files")

    # Cleanup orphans older than 7 days
    deleted = service.cleanup_orphans(older_than_days=7)
    logger.info(f"Deleted {deleted} orphan files")

    return {'found': len(orphans), 'deleted': deleted}


@shared_task
def cleanup_revoked_urls():
    """Cleanup old revoked signed URLs. Run daily."""
    from storage.models import SignedURL

    cutoff = timezone.now() - timezone.timedelta(days=30)
    deleted, _ = SignedURL.objects.filter(
        is_revoked=True,
        revoked_at__lt=cutoff
    ).delete()

    logger.info(f"Deleted {deleted} old revoked URLs")
    return deleted


@shared_task
def generate_storage_report():
    """Generate storage usage report. Run weekly."""
    from storage.services import get_storage_service
    from storage.models import StorageQuota

    service = get_storage_service()
    stats = service.get_stats()

    # Check for users near quota
    near_quota = StorageQuota.objects.filter(
        used_storage__gte=models.F('total_quota') * 0.9
    ).count()

    report = {
        **stats,
        'users_near_quota': near_quota,
        'generated_at': timezone.now().isoformat(),
    }

    logger.info(f"Storage report: {stats['total_files']} files, {stats['total_size_mb']}MB")

    return report


# ============================================================
# Processing Queue Management
# ============================================================

@shared_task
def process_pending_jobs():
    """Process pending jobs in queue. Run every minute."""
    from storage.models import ProcessingJob

    pending = ProcessingJob.objects.filter(
        status='pending'
    ).order_by('priority', 'created_at')[:10]

    for job in pending:
        job.status = 'queued'
        job.save(update_fields=['status'])

        process_file.delay(str(job.file_id), job.job_type)

    return len(pending)


@shared_task
def retry_failed_jobs():
    """Retry failed jobs that haven't exceeded max attempts. Run hourly."""
    from storage.models import ProcessingJob

    failed = ProcessingJob.objects.filter(
        status='failed',
        attempts__lt=models.F('max_attempts')
    )

    count = 0
    for job in failed:
        job.status = 'pending'
        job.save(update_fields=['status'])
        count += 1

    logger.info(f"Queued {count} failed jobs for retry")
    return count

