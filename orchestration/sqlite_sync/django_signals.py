# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Django Signals Integration
===============================================
Integrates Django model signals with the SQLite sync system.

This provides an additional layer of event capture beyond SQLite triggers,
catching changes made through the Django ORM.
"""
import json
import logging
from typing import Any

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import SyncEvent, SyncEventStore

logger = logging.getLogger("forgeforth.orchestration.sqlite_sync.signals")

# Lazy import to avoid circular imports
_store = None


def get_store() -> SyncEventStore:
    """Get the event store singleton."""
    global _store
    if _store is None:
        _store = SyncEventStore()
    return _store


def model_to_dict(instance) -> dict:
    """Convert a Django model instance to a dictionary."""
    data = {}

    for field in instance._meta.fields:
        value = getattr(instance, field.name, None)

        # Handle special types
        if hasattr(value, 'isoformat'):  # datetime/date
            value = value.isoformat()
        elif hasattr(value, 'pk'):  # ForeignKey
            value = str(value.pk) if value else None
        elif isinstance(value, bytes):
            value = None  # Skip binary fields

        data[field.name] = value

    return data


def get_subsystem_for_model(instance) -> str:
    """Determine which subsystem a model belongs to."""
    app_label = instance._meta.app_label
    return app_label


def create_sync_event(instance, operation: str):
    """Create a sync event for a model change."""
    try:
        store = get_store()

        event = SyncEvent(
            subsystem=get_subsystem_for_model(instance),
            table_name=instance._meta.db_table,
            operation=operation,
            row_id=str(instance.pk),
            data=model_to_dict(instance),
        )

        store.add_event(event)
        logger.debug(f"Created sync event: {operation} on {instance._meta.db_table}")

    except Exception as e:
        logger.error(f"Failed to create sync event: {e}")


# Track which models we've connected signals to
_connected_models = set()


def connect_model_signals(model_class):
    """Connect sync signals to a model class."""
    if model_class in _connected_models:
        return

    model_key = f"{model_class._meta.app_label}.{model_class._meta.model_name}"

    @receiver(post_save, sender=model_class)
    def handle_save(sender, instance, created, **kwargs):
        operation = 'insert' if created else 'update'
        create_sync_event(instance, operation)

    @receiver(post_delete, sender=model_class)
    def handle_delete(sender, instance, **kwargs):
        create_sync_event(instance, 'delete')

    _connected_models.add(model_class)
    logger.debug(f"Connected signals for {model_key}")


def connect_all_models():
    """Connect signals for all relevant models."""
    from django.apps import apps

    # Models to track
    tracked_apps = [
        'accounts',
        'profiles',
        'organizations',
        'applications',
        'media',
        'intelligence',
        'matching',
        'communications',
        'analytics',
        'administration',
        'security',
    ]

    for app_label in tracked_apps:
        try:
            app_config = apps.get_app_config(app_label)
            for model in app_config.get_models():
                connect_model_signals(model)
        except LookupError:
            logger.debug(f"App not found: {app_label}")
        except Exception as e:
            logger.error(f"Error connecting signals for {app_label}: {e}")

