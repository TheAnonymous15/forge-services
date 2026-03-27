# -*- coding: utf-8 -*-
"""
Media Processing Celery Tasks
=============================
Async tasks for processing large media files.
"""
import logging
from typing import Dict, Any, Optional
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def process_media_async(
    self,
    media_file_id: str,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Async task to process a MediaFile.

    Args:
        media_file_id: UUID of the MediaFile record
        options: Processing options dict

    Returns:
        Dict with processing result summary
    """
    from media.models import MediaFile, ProcessingJob
    from media.services import MediaRouter
    from django.core.files.base import ContentFile
    from django.conf import settings
    import os

    options = options or {}

    try:
        # Get the MediaFile record
        media_file = MediaFile.objects.get(id=media_file_id)

        # Update status
        media_file.status = MediaFile.Status.PROCESSING
        media_file.save(update_fields=['status'])

        # Create processing job record
        job = ProcessingJob.objects.create(
            media_file=media_file,
            job_type=ProcessingJob.JobType.SANITISE,
            status=ProcessingJob.Status.RUNNING,
            celery_task=self.request.id,
            started_at=timezone.now(),
        )

        # Read the file
        file_path = os.path.join(settings.MEDIA_ROOT, media_file.file_path)
        with open(file_path, 'rb') as f:
            data = f.read()

        # Process
        router = MediaRouter()
        result = router.process(data, **options)

        # Update records based on result
        if result.success:
            # Save processed file
            if result.content:
                processed_filename = f"processed_{media_file.stored_filename}"
                if result.extension:
                    base_name = os.path.splitext(processed_filename)[0]
                    processed_filename = f"{base_name}.{result.extension}"

                processed_path = os.path.join(
                    os.path.dirname(media_file.file_path),
                    processed_filename
                )

                full_path = os.path.join(settings.MEDIA_ROOT, processed_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                with open(full_path, 'wb') as f:
                    f.write(result.content)

                media_file.processed_path = processed_path

            # Save thumbnail if present
            if result.thumbnail:
                thumb_filename = f"thumb_{media_file.stored_filename}.webp"
                thumb_path = os.path.join(
                    os.path.dirname(media_file.file_path),
                    'thumbnails',
                    thumb_filename
                )

                full_thumb_path = os.path.join(settings.MEDIA_ROOT, thumb_path)
                os.makedirs(os.path.dirname(full_thumb_path), exist_ok=True)

                with open(full_thumb_path, 'wb') as f:
                    f.write(result.thumbnail)

                media_file.thumbnail_path = thumb_path

            # Update MediaFile
            media_file.status = MediaFile.Status.READY
            media_file.is_sanitised = True
            media_file.checksum_sha256 = result.checksum_sha256
            media_file.mime_type = result.mime_type or media_file.mime_type
            media_file.metadata = result.metadata or {}

            if result.threats_sanitized:
                media_file.threat_detected = True
                media_file.threat_detail = '\n'.join(result.threats_sanitized)

            media_file.save()

            # Update job
            job.status = ProcessingJob.Status.DONE
            job.result = result.to_dict()
            job.finished_at = timezone.now()
            job.save()

            # If document, save extracted text
            if result.extracted_text:
                from media.models import Document
                Document.objects.update_or_create(
                    media_file=media_file,
                    defaults={
                        'owner': media_file.owner,
                        'extracted_text': result.extracted_text,
                        'pages': result.metadata.get('pages', 0),
                    }
                )

            logger.info(f"Successfully processed MediaFile {media_file_id}")
            return {
                'success': True,
                'media_file_id': str(media_file_id),
                'processed_size': result.processed_size,
                'compression_ratio': result.compression_ratio,
            }

        else:
            # Processing failed
            media_file.status = MediaFile.Status.FAILED
            media_file.save(update_fields=['status'])

            job.status = ProcessingJob.Status.FAILED
            job.error = result.error or 'Unknown error'
            job.finished_at = timezone.now()
            job.save()

            logger.error(f"Failed to process MediaFile {media_file_id}: {result.error}")
            return {
                'success': False,
                'media_file_id': str(media_file_id),
                'error': result.error,
            }

    except MediaFile.DoesNotExist:
        logger.error(f"MediaFile {media_file_id} not found")
        return {
            'success': False,
            'media_file_id': str(media_file_id),
            'error': 'MediaFile not found',
        }
    except Exception as e:
        logger.error(f"Error processing MediaFile {media_file_id}: {e}", exc_info=True)

        # Update status if we have the record
        try:
            media_file = MediaFile.objects.get(id=media_file_id)
            media_file.status = MediaFile.Status.FAILED
            media_file.save(update_fields=['status'])
        except:
            pass

        raise  # Re-raise for Celery retry


@shared_task
def cleanup_old_processing_jobs(days: int = 30):
    """
    Clean up old processing job records.

    Args:
        days: Delete jobs older than this many days
    """
    from media.models import ProcessingJob
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)

    deleted, _ = ProcessingJob.objects.filter(
        created_at__lt=cutoff,
        status__in=[ProcessingJob.Status.DONE, ProcessingJob.Status.FAILED]
    ).delete()

    logger.info(f"Deleted {deleted} old processing jobs")
    return {'deleted': deleted}


@shared_task
def reprocess_failed_media(limit: int = 100):
    """
    Retry processing for failed media files.

    Args:
        limit: Maximum number of files to retry
    """
    from media.models import MediaFile

    failed_files = MediaFile.objects.filter(
        status=MediaFile.Status.FAILED
    )[:limit]

    queued = 0
    for media_file in failed_files:
        process_media_async.delay(str(media_file.id))
        queued += 1

    logger.info(f"Queued {queued} failed media files for reprocessing")
    return {'queued': queued}

