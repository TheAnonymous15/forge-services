# -*- coding: utf-8 -*-
"""
ForgeForth Africa — Orchestration Event Bus
============================================
The central nervous system of the data orchestration layer.

Flow:
  1. A subsystem model is saved / deleted  (Django signal fires)
  2. signal_handlers.py calls EventBus.publish(event)
  3. EventBus persists the event to SyncEventLog (immediate, synchronous)
  4. EventBus dispatches a Celery task  (async, off the request thread)
  5. Celery task calls EventBus.process(event)  → serialise → write to central_db mirror
  6. On failure → retry with exponential back-off → Dead Letter Queue after MAX_RETRIES

Security:
  - Every payload is serialised via the model's own serializer (no raw __dict__ leakage)
  - Sensitive fields (passwords, tokens) are stripped before storage
  - All writes to central_db are done inside a transaction

"""
import logging
import uuid
from typing import Any, Dict, Optional, Type

from django.apps import apps
from django.db import transaction, connections
from django.utils import timezone

logger = logging.getLogger("forgeforth.orchestration")

# ── Constants ────────────────────────────────────────────────────────────────
MAX_RETRIES   = 5
RETRY_DELAYS  = [10, 30, 120, 600, 1800]   # seconds  (exponential-ish)

# Subsystem apps whose changes we track
TRACKED_APPS = {
    "accounts", "profiles", "organizations", "applications",
    "media", "intelligence", "matching", "communications",
    "analytics", "administration", "security",
}

# Fields that must never be stored in the central sync log or mirror tables
SENSITIVE_FIELDS = {
    "password", "hashed_password", "token", "access_token", "refresh_token",
    "secret", "api_key", "private_key", "ssn", "national_id_number",
    "bank_account", "credit_card",
}


# ── Payload Sanitiser ────────────────────────────────────────────────────────

def sanitise_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields from a payload dict (top-level only)."""
    return {k: v for k, v in data.items() if k.lower() not in SENSITIVE_FIELDS}


# ── Model → dict serialisers ─────────────────────────────────────────────────

def serialise_instance(instance) -> Dict[str, Any]:
    """
    Convert a model instance to a JSON-safe dict for event payload storage.
    Uses the model's own DRF serializer if available, else falls back to
    a safe field-by-field extraction.
    """
    try:
        # Attempt to import the app's serializer
        app_label = instance._meta.app_label
        model_name = instance.__class__.__name__
        serializer_module = __import__(
            f"{app_label}.serializers", fromlist=[""]
        )
        # Look for a serializer named e.g. "UserSerializer", "ProfileSerializer"
        serializer_class = getattr(serializer_module, f"{model_name}Serializer", None)
        if serializer_class:
            data = serializer_class(instance).data
            return sanitise_payload(dict(data))
    except (ImportError, AttributeError):
        pass

    # Fallback: safe field extraction
    data: Dict[str, Any] = {}
    for field in instance._meta.get_fields():
        if not hasattr(field, "attname"):
            continue
        value = getattr(instance, field.attname, None)
        # Convert non-JSON-serialisable types
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif hasattr(value, "__str__") and not isinstance(value, (str, int, float, bool, type(None), list, dict)):
            value = str(value)
        data[field.attname] = value

    return sanitise_payload(data)


# ── Event Bus ────────────────────────────────────────────────────────────────

class EventBus:
    """
    Static event bus — no state, fully thread-safe.
    """

    @staticmethod
    def publish(
        instance,
        operation: str,         # "create" | "update" | "delete"
        using: str = "default",
    ) -> Optional["SyncEventLog"]:  # noqa: F821
        """
        Persist the event to SyncEventLog and enqueue the Celery sync task.
        Returns the SyncEventLog instance or None on error.
        """
        from orchestration.models import SyncEventLog  # local import avoids circular

        app_label  = instance._meta.app_label
        model_name = instance.__class__.__name__
        instance_id = str(instance.pk)

        if app_label not in TRACKED_APPS:
            return None

        payload = serialise_instance(instance)

        try:
            # Determine which DB to write the event log to.
            # In single-DB mode this is "default"; in multi-DB it is "central_db".
            from django.conf import settings as django_settings
            event_db = "default" if getattr(django_settings, "USE_SINGLE_DATABASE", True) else "central_db"

            with transaction.atomic(using=event_db):
                event = SyncEventLog.objects.using(event_db).create(
                    app_label   = app_label,
                    model_name  = model_name,
                    instance_id = instance_id,
                    operation   = operation,
                    payload     = payload,
                    status      = SyncEventLog.Status.PENDING,
                )

            # Dispatch the async task (fire-and-forget from request thread)
            EventBus._dispatch_task(str(event.id))
            return event

        except Exception as exc:
            logger.exception(
                "EventBus.publish failed for %s.%s:%s — %s",
                app_label, model_name, instance_id, exc
            )
            return None

    @staticmethod
    def _dispatch_task(event_id: str) -> None:
        """Fire the Celery sync task, catching import errors gracefully."""
        try:
            from orchestration.tasks import sync_event_to_central  # noqa
            sync_event_to_central.apply_async(
                args=[event_id],
                countdown=1,        # 1-second grace period
                retry=False,        # Celery retries handled inside the task
            )
        except Exception as exc:
            logger.warning("Could not dispatch Celery task for event %s: %s", event_id, exc)

    @staticmethod
    def process(event_id: str) -> bool:
        """
        Called from within the Celery task.
        Writes the event payload to the correct central mirror model.
        Returns True on success.
        """
        from orchestration.models import SyncEventLog, DeadLetterEvent
        from orchestration.registry import MIRROR_REGISTRY

        from django.conf import settings as django_settings
        event_db = "default" if getattr(django_settings, "USE_SINGLE_DATABASE", True) else "central_db"

        try:
            event = SyncEventLog.objects.using(event_db).get(id=event_id)
        except SyncEventLog.DoesNotExist:
            logger.error("EventBus.process: event %s not found", event_id)
            return False

        try:
            event.status = SyncEventLog.Status.RETRYING if event.retry_count > 0 else SyncEventLog.Status.PENDING
            event.save(using=event_db, update_fields=["status"])

            handler_fn = MIRROR_REGISTRY.get(f"{event.app_label}.{event.model_name}")
            if handler_fn is None:
                # No mirror handler → mark success (we don't need to mirror everything)
                event.status = SyncEventLog.Status.SUCCESS
                event.synced_at = timezone.now()
                event.save(using=event_db, update_fields=["status", "synced_at"])
                return True

            with transaction.atomic(using=event_db):
                handler_fn(event.operation, event.payload)

            event.status = SyncEventLog.Status.SUCCESS
            event.synced_at = timezone.now()
            event.save(using=event_db, update_fields=["status", "synced_at"])
            logger.info(
                "Synced %s.%s:%s (%s)",
                event.app_label, event.model_name, event.instance_id, event.operation
            )
            return True

        except Exception as exc:
            event.retry_count += 1
            event.error_message = str(exc)

            if event.retry_count >= MAX_RETRIES:
                event.status = SyncEventLog.Status.DEAD
                event.save(using=event_db, update_fields=["status", "retry_count", "error_message"])
                # Move to Dead Letter Queue
                DeadLetterEvent.objects.using(event_db).create(
                    original_event = event.id,
                    app_label      = event.app_label,
                    model_name     = event.model_name,
                    instance_id    = event.instance_id,
                    operation      = event.operation,
                    payload        = event.payload,
                    last_error     = str(exc),
                    retry_count    = event.retry_count,
                )
                logger.error(
                    "Event %s moved to DLQ after %d retries: %s",
                    event_id, event.retry_count, exc
                )
            else:
                event.status = SyncEventLog.Status.FAILED
                event.save(using=event_db, update_fields=["status", "retry_count", "error_message"])
                logger.warning(
                    "Event %s failed (attempt %d/%d): %s",
                    event_id, event.retry_count, MAX_RETRIES, exc
                )
            return False

