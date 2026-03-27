# -*- coding: utf-8 -*-
"""
Storage Subsystem - Django Signals
"""
from django.db.models.signals import post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_delete, sender='storage.StoredFile')
def delete_file_from_storage(sender, instance, **kwargs):
    """
    When a StoredFile record is deleted, also delete the actual file.
    """
    from storage.services import get_storage_service

    try:
        storage = get_storage_service()
        storage.backend.delete(instance.file_id)
        logger.info(f"Deleted file from storage: {instance.file_id}")
    except Exception as e:
        logger.error(f"Failed to delete file from storage: {instance.file_id} - {e}")

