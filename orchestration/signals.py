# -*- coding: utf-8 -*-
"""
ForgeForth Africa — Orchestration Signal Handlers
==================================================
Wires Django post_save / post_delete signals for every tracked subsystem
model to the EventBus.

This file is imported by OrchestrationConfig.ready() in apps.py.
It uses lazy model references (app_label, model_name strings) so the import
order does not matter — Django resolves them after all apps are loaded.
"""
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps

from orchestration.event_bus import EventBus, TRACKED_APPS

logger = logging.getLogger("forgeforth.orchestration.signals")


# ── Generic sender factory ────────────────────────────────────────────────────

def _make_save_handler(app_label: str):
    def _handler(sender, instance, created, **kwargs):
        op = "create" if created else "update"
        EventBus.publish(instance, operation=op)
    _handler.__name__ = f"_save_{app_label}"
    return _handler


def _make_delete_handler(app_label: str):
    def _handler(sender, instance, **kwargs):
        EventBus.publish(instance, operation="delete")
    _handler.__name__ = f"_delete_{app_label}"
    return _handler


# ── Model map — which models to track per subsystem ──────────────────────────
# Format: "app_label": ["ModelName", ...]
# Add entries here as new models are created.

TRACKED_MODELS = {
    "accounts": [
        "User",
        "EmailVerificationToken",
        "LoginHistory",
    ],
    "profiles": [
        "TalentProfile",
        "Education",
        "WorkExperience",
        "Skill",
        "TalentSkill",
        "Certification",
        "TalentLanguage",
    ],
    "organizations": [
        "Organization",
        "Opportunity",
        "OrganizationMember",
        "OrganizationLocation",
    ],
    "applications": [
        "Application",
        "ApplicationStatusHistory",
        "Interview",
        "SavedOpportunity",
    ],
    "media": [
        "MediaFile",
        "Document",
        "ProcessingJob",
    ],
    "intelligence": [
        "SkillTaxonomy",
        "CVParseResult",
        "TalentScore",
        "SkillExtraction",
        "IntelligenceInsight",
    ],
    "matching": [
        "MatchScore",
        "Recommendation",
        "SearchIndex",
    ],
    "communications": [
        "Notification",
        "EmailLog",
        "Message",
        "Announcement",
    ],
    "analytics": [
        "PageView",
        "UserEvent",
        "PlatformMetricSnapshot",
        "Report",
    ],
    "administration": [
        "StaffRole",
        "StaffRoleAssignment",
        "FeatureFlag",
        "AdminAuditLog",
        "SupportTicket",
    ],
    "security": [
        "APIKey",
        "SecurityEvent",
        "ConsentRecord",
        "BlockedIP",
    ],
}


# ── Wire signals after all apps are ready ────────────────────────────────────

def connect_signals():
    """
    Called from OrchestrationConfig.ready().
    Dynamically connect post_save / post_delete for every tracked model.
    Silently skips models that don't exist yet (future migrations).
    """
    registered = 0
    for app_label, model_names in TRACKED_MODELS.items():
        for model_name in model_names:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                # Model does not exist yet — skip gracefully
                continue

            save_handler   = _make_save_handler(f"{app_label}_{model_name}")
            delete_handler = _make_delete_handler(f"{app_label}_{model_name}")

            post_save.connect(
                save_handler,
                sender=model,
                weak=False,
                dispatch_uid=f"orch_save_{app_label}_{model_name}",
            )
            post_delete.connect(
                delete_handler,
                sender=model,
                weak=False,
                dispatch_uid=f"orch_delete_{app_label}_{model_name}",
            )
            registered += 1
            logger.debug("Orchestration: registered signals for %s.%s", app_label, model_name)

    logger.info("Orchestration: connected %d model signal pairs", registered)

