# -*- coding: utf-8 -*-
"""
ForgeForth Africa — Orchestration Celery Tasks
================================================
All async work for the data orchestration layer lives here.

Tasks:
  sync_event_to_central   — process a single SyncEventLog event
  retry_failed_events     — periodic: re-queue FAILED events
  full_sync_subsystem     — on-demand: bulk sync one subsystem to central_db
  nightly_full_sync       — scheduled: full sync of all subsystems nightly
  requeue_dead_letter     — admin tool: replay a dead-letter event
"""
import logging
from celery import shared_task
from django.utils import timezone

from orchestration.event_bus import EventBus, MAX_RETRIES, RETRY_DELAYS

logger = logging.getLogger("forgeforth.orchestration.tasks")


# ── 1. Single event sync ─────────────────────────────────────────────────────

@shared_task(
    bind=True,
    name="orchestration.sync_event_to_central",
    max_retries=MAX_RETRIES,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_event_to_central(self, event_id: str) -> dict:
    """
    Process a single event: read SyncEventLog → write central mirror.
    Retries with exponential back-off on failure.
    """
    try:
        success = EventBus.process(event_id)
        if success:
            return {"status": "ok", "event_id": event_id}

        # EventBus.process already incremented retry_count and set status.
        # Re-raise so Celery also tracks the retry.
        raise RuntimeError(f"EventBus.process returned False for event {event_id}")

    except Exception as exc:
        retry_number = self.request.retries
        if retry_number < MAX_RETRIES:
            delay = RETRY_DELAYS[min(retry_number, len(RETRY_DELAYS) - 1)]
            logger.warning(
                "sync_event_to_central retry %d/%d for event %s in %ds",
                retry_number + 1, MAX_RETRIES, event_id, delay
            )
            raise self.retry(exc=exc, countdown=delay)

        logger.error("sync_event_to_central exhausted retries for event %s", event_id)
        return {"status": "dead", "event_id": event_id}


# ── 2. Retry failed events (periodic) ────────────────────────────────────────

@shared_task(name="orchestration.retry_failed_events")
def retry_failed_events() -> dict:
    """
    Re-queue all FAILED events that have not yet exhausted MAX_RETRIES.
    Run every 5 minutes via Celery Beat.
    """
    from orchestration.models import SyncEventLog
    from django.conf import settings as s
    db = "default" if getattr(s, "USE_SINGLE_DATABASE", True) else "central_db"

    failed_qs = SyncEventLog.objects.using(db).filter(
        status=SyncEventLog.Status.FAILED,
        retry_count__lt=MAX_RETRIES,
    ).order_by("created_at")[:200]   # cap to 200 per run

    count = 0
    for event in failed_qs:
        sync_event_to_central.apply_async(args=[str(event.id)], countdown=2)
        count += 1

    logger.info("retry_failed_events: re-queued %d events", count)
    return {"requeued": count}


# ── 3. Full sync of a single subsystem ───────────────────────────────────────

@shared_task(name="orchestration.full_sync_subsystem")
def full_sync_subsystem(app_label: str, model_name: str) -> dict:
    """
    Iterate every instance of a model and publish a synthetic 'update' event.
    Useful after deploying to sync existing data that pre-dates the event bus.
    """
    from django.apps import apps
    from orchestration.models import FullSyncReport
    from django.conf import settings as s
    db = "default" if getattr(s, "USE_SINGLE_DATABASE", True) else "central_db"

    report = FullSyncReport.objects.using(db).create()
    synced = 0
    failed = 0

    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        report.status = "error"
        report.error_message = f"Model {app_label}.{model_name} not found"
        report.completed_at = timezone.now()
        report.save(using=db)
        return {"status": "error", "message": report.error_message}

    try:
        using = _db_for_app(app_label)
        qs = model.objects.using(using).iterator(chunk_size=500)
        for instance in qs:
            try:
                EventBus.publish(instance, operation="update")
                synced += 1
            except Exception as exc:
                logger.warning("full_sync: failed on %s:%s — %s", model_name, instance.pk, exc)
                failed += 1

        report.status = "done"
        report.total_synced = synced
        report.total_failed = failed
        report.completed_at = timezone.now()
        report.details = {"app_label": app_label, "model_name": model_name}
        report.save(using=db)
        logger.info("full_sync_subsystem %s.%s: synced=%d failed=%d", app_label, model_name, synced, failed)
        return {"status": "done", "synced": synced, "failed": failed}

    except Exception as exc:
        report.status = "error"
        report.error_message = str(exc)
        report.total_synced = synced
        report.total_failed = failed
        report.completed_at = timezone.now()
        report.save(using=db)
        logger.exception("full_sync_subsystem crashed: %s", exc)
        return {"status": "error", "message": str(exc)}


def _db_for_app(app_label: str) -> str:
    """Return the DB alias for a given app, respecting USE_SINGLE_DATABASE."""
    from django.conf import settings as s
    if getattr(s, "USE_SINGLE_DATABASE", True):
        return "default"
    router_map = {
        "accounts": "accounts_db",
        "profiles": "profiles_db",
        "organizations": "organizations_db",
        "applications": "applications_db",
        "communications": "communications_db",
        "analytics": "analytics_db",
        "media": "media_db",
        "intelligence": "intelligence_db",
        "matching": "intelligence_db",
        "administration": "administration_db",
    }
    return router_map.get(app_label, "default")


# ── 4. Nightly full sync of ALL subsystems ────────────────────────────────────

@shared_task(name="orchestration.nightly_full_sync")
def nightly_full_sync() -> dict:
    """
    Scheduled nightly task: sync every tracked model to central_db.
    Add to Celery Beat schedule (see settings.py CELERY_BEAT_SCHEDULE).
    """
    from orchestration.registry import MIRROR_REGISTRY

    results = {}
    for key in MIRROR_REGISTRY:
        app_label, model_name = key.split(".")
        job = full_sync_subsystem.apply_async(args=[app_label, model_name])
        results[key] = job.id

    logger.info("nightly_full_sync dispatched %d subsystem sync jobs", len(results))
    return {"dispatched": len(results), "jobs": results}


# ── 5. Replay a dead-letter event ────────────────────────────────────────────

@shared_task(name="orchestration.requeue_dead_letter")
def requeue_dead_letter(dead_letter_id: str) -> dict:
    """
    Admin tool: replay a single dead-letter event.
    Resets the original SyncEventLog to PENDING and re-dispatches it.
    """
    from orchestration.models import DeadLetterEvent, SyncEventLog
    from django.conf import settings as s
    db = "default" if getattr(s, "USE_SINGLE_DATABASE", True) else "central_db"

    try:
        dlq = DeadLetterEvent.objects.using(db).get(id=dead_letter_id)
    except DeadLetterEvent.DoesNotExist:
        return {"status": "error", "message": "Dead letter event not found"}

    # Find or recreate the original SyncEventLog
    try:
        original = SyncEventLog.objects.using(db).get(id=dlq.original_event)
        original.status      = SyncEventLog.Status.PENDING
        original.retry_count = 0
        original.error_message = ""
        original.save(using=db, update_fields=["status", "retry_count", "error_message"])
    except SyncEventLog.DoesNotExist:
        # Re-create from DLQ data
        original = SyncEventLog.objects.using(db).create(
            id          = dlq.original_event,
            app_label   = dlq.app_label,
            model_name  = dlq.model_name,
            instance_id = dlq.instance_id,
            operation   = dlq.operation,
            payload     = dlq.payload,
            status      = SyncEventLog.Status.PENDING,
        )

    dlq.resolved    = True
    dlq.resolved_at = timezone.now()
    dlq.notes       = "Replayed via requeue_dead_letter task"
    dlq.save(using=db, update_fields=["resolved", "resolved_at", "notes"])

    sync_event_to_central.apply_async(args=[str(original.id)], countdown=1)
    logger.info("Replayed dead-letter event %s → SyncEventLog %s", dead_letter_id, original.id)
    return {"status": "replayed", "event_id": str(original.id)}

