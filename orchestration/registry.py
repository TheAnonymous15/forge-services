# -*- coding: utf-8 -*-
"""
ForgeForth Africa — Mirror Registry
=====================================
Maps  "app_label.ModelName"  →  handler function

Each handler receives (operation: str, payload: dict) and is responsible
for upserting / deleting the corresponding central mirror record.

Add a new entry here whenever a new subsystem model needs to be centralised.
"""
import logging
import uuid
from typing import Dict, Callable

logger = logging.getLogger("forgeforth.orchestration.registry")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_uuid(value):
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _parse_dt(value):
    """Parse an ISO datetime string or return None."""
    if not value:
        return None
    from django.utils.dateparse import parse_datetime
    return parse_datetime(str(value))


def _get_db():
    from django.conf import settings as s
    return "default" if getattr(s, "USE_SINGLE_DATABASE", True) else "central_db"


# ── Handler: accounts.User ───────────────────────────────────────────────────

def _handle_user(operation: str, payload: dict):
    from orchestration.models import CentralUser
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return

    if operation == "delete":
        CentralUser.objects.using(db).filter(id=pk).delete()
        return

    CentralUser.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            email       = payload.get("email", ""),
            first_name  = payload.get("first_name", ""),
            last_name   = payload.get("last_name", ""),
            role        = payload.get("role", ""),
            is_active   = payload.get("is_active", True),
            is_verified = payload.get("is_verified", False),
            date_joined = _parse_dt(payload.get("date_joined")),
            last_login  = _parse_dt(payload.get("last_login")),
        ),
    )


# ── Handler: profiles.TalentProfile ─────────────────────────────────────────

def _handle_profile(operation: str, payload: dict):
    from orchestration.models import CentralProfile
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return

    if operation == "delete":
        CentralProfile.objects.using(db).filter(id=pk).delete()
        return

    CentralProfile.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            user_id           = _to_uuid(payload.get("user_id")) or _to_uuid(payload.get("user")),
            headline          = payload.get("headline", ""),
            bio               = payload.get("bio", ""),
            country           = payload.get("country", ""),
            city              = payload.get("city", ""),
            skills            = payload.get("skills", []),
            experience_years  = int(payload.get("experience_years", 0)),
            availability      = payload.get("availability", ""),
            employment_status = payload.get("employment_status", ""),
            is_public         = payload.get("is_public", True),
        ),
    )


# ── Handler: organizations.Organization ──────────────────────────────────────

def _handle_organization(operation: str, payload: dict):
    from orchestration.models import CentralOrganization
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return

    if operation == "delete":
        CentralOrganization.objects.using(db).filter(id=pk).delete()
        return

    CentralOrganization.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            owner_id    = _to_uuid(payload.get("owner_id")) or _to_uuid(payload.get("owner")),
            name        = payload.get("name", ""),
            org_type    = payload.get("org_type", payload.get("type", "")),
            industry    = payload.get("industry", ""),
            country     = payload.get("country", ""),
            city        = payload.get("city", ""),
            size        = payload.get("size", ""),
            status      = payload.get("status", ""),
            is_verified = payload.get("is_verified", False),
        ),
    )


# ── Handler: organizations.Opportunity ───────────────────────────────────────

def _handle_opportunity(operation: str, payload: dict):
    from orchestration.models import CentralOpportunity
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return

    if operation == "delete":
        CentralOpportunity.objects.using(db).filter(id=pk).delete()
        return

    CentralOpportunity.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            organization_id = _to_uuid(payload.get("organization_id")) or _to_uuid(payload.get("organization")),
            title           = payload.get("title", ""),
            opp_type        = payload.get("opp_type", payload.get("type", "")),
            location        = payload.get("location", ""),
            is_remote       = payload.get("is_remote", False),
            required_skills = payload.get("required_skills", []),
            status          = payload.get("status", ""),
            deadline        = _parse_dt(payload.get("deadline")),
            created_at      = _parse_dt(payload.get("created_at")),
        ),
    )


# ── Handler: applications.Application ────────────────────────────────────────

def _handle_application(operation: str, payload: dict):
    from orchestration.models import CentralApplication
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return

    if operation == "delete":
        CentralApplication.objects.using(db).filter(id=pk).delete()
        return

    CentralApplication.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            applicant_id    = _to_uuid(payload.get("applicant_id")) or _to_uuid(payload.get("applicant")),
            opportunity_id  = _to_uuid(payload.get("opportunity_id")) or _to_uuid(payload.get("opportunity")),
            organization_id = _to_uuid(payload.get("organization_id")) or _to_uuid(payload.get("organization")),
            status          = payload.get("status", ""),
            applied_at      = _parse_dt(payload.get("applied_at")),
            updated_at      = _parse_dt(payload.get("updated_at")),
        ),
    )


# ── Handler: media.MediaFile ──────────────────────────────────────────────────

def _handle_media_file(operation: str, payload: dict):
    from orchestration.models import CentralMediaFile
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralMediaFile.objects.using(db).filter(id=pk).delete()
        return
    CentralMediaFile.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            owner_id   = _to_uuid(payload.get("owner_id")) or _to_uuid(payload.get("owner")),
            file_type  = payload.get("file_type", ""),
            mime_type  = payload.get("mime_type", ""),
            file_size  = int(payload.get("file_size", 0) or 0),
            status     = payload.get("status", ""),
            is_public  = payload.get("is_public", False),
            created_at = _parse_dt(payload.get("created_at")),
        ),
    )


def _handle_document(operation: str, payload: dict):
    from orchestration.models import CentralDocument
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralDocument.objects.using(db).filter(id=pk).delete()
        return
    CentralDocument.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            owner_id    = _to_uuid(payload.get("owner_id")) or _to_uuid(payload.get("owner")),
            doc_type    = payload.get("doc_type", payload.get("document_type", "")),
            is_verified = payload.get("is_verified", False),
            created_at  = _parse_dt(payload.get("created_at")),
        ),
    )


# ── Handler: intelligence subsystem ─────────────────────────────────────────

def _handle_talent_score(operation: str, payload: dict):
    from orchestration.models import CentralTalentScore
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralTalentScore.objects.using(db).filter(id=pk).delete()
        return
    CentralTalentScore.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            profile_id       = _to_uuid(payload.get("profile_id")) or _to_uuid(payload.get("profile")),
            overall_score    = float(payload.get("overall_score", 0.0) or 0.0),
            skill_score      = float(payload.get("skill_score", 0.0) or 0.0),
            experience_score = float(payload.get("experience_score", 0.0) or 0.0),
            education_score  = float(payload.get("education_score", 0.0) or 0.0),
            completeness     = float(payload.get("completeness", 0.0) or 0.0),
            computed_at      = _parse_dt(payload.get("computed_at")),
        ),
    )


def _handle_skill_extraction(operation: str, payload: dict):
    from orchestration.models import CentralSkillExtraction
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralSkillExtraction.objects.using(db).filter(id=pk).delete()
        return
    CentralSkillExtraction.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            profile_id       = _to_uuid(payload.get("profile_id")) or _to_uuid(payload.get("profile")),
            extracted_skills = payload.get("extracted_skills", []),
            confidence       = float(payload.get("confidence", 0.0) or 0.0),
            source           = payload.get("source", ""),
            created_at       = _parse_dt(payload.get("created_at")),
        ),
    )


# ── Handler: matching subsystem ───────────────────────────────────────────────

def _handle_match_score(operation: str, payload: dict):
    from orchestration.models import CentralMatchScore
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralMatchScore.objects.using(db).filter(id=pk).delete()
        return
    CentralMatchScore.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            profile_id     = _to_uuid(payload.get("profile_id")) or _to_uuid(payload.get("profile")),
            opportunity_id = _to_uuid(payload.get("opportunity_id")) or _to_uuid(payload.get("opportunity")),
            score          = float(payload.get("score", 0.0) or 0.0),
            match_factors  = payload.get("match_factors", {}),
            is_recommended = payload.get("is_recommended", False),
            computed_at    = _parse_dt(payload.get("computed_at")),
        ),
    )


# ── Handler: communications subsystem ────────────────────────────────────────

def _handle_notification(operation: str, payload: dict):
    from orchestration.models import CentralNotification
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralNotification.objects.using(db).filter(id=pk).delete()
        return
    CentralNotification.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            recipient_id = _to_uuid(payload.get("recipient_id")) or _to_uuid(payload.get("recipient")),
            notif_type   = payload.get("notif_type", payload.get("notification_type", "")),
            channel      = payload.get("channel", ""),
            is_read      = payload.get("is_read", False),
            created_at   = _parse_dt(payload.get("created_at")),
        ),
    )


def _handle_message(operation: str, payload: dict):
    from orchestration.models import CentralMessage
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralMessage.objects.using(db).filter(id=pk).delete()
        return
    CentralMessage.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            sender_id    = _to_uuid(payload.get("sender_id")) or _to_uuid(payload.get("sender")),
            recipient_id = _to_uuid(payload.get("recipient_id")) or _to_uuid(payload.get("recipient")),
            thread_id    = _to_uuid(payload.get("thread_id")),
            is_read      = payload.get("is_read", False),
            created_at   = _parse_dt(payload.get("created_at")),
        ),
    )


# ── Handler: analytics subsystem ─────────────────────────────────────────────

def _handle_analytics_event(operation: str, payload: dict):
    from orchestration.models import CentralAnalyticsEvent
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralAnalyticsEvent.objects.using(db).filter(id=pk).delete()
        return
    CentralAnalyticsEvent.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            user_id    = _to_uuid(payload.get("user_id")) or _to_uuid(payload.get("user")),
            event_name = payload.get("event_name", payload.get("name", "")),
            event_data = payload.get("event_data", payload.get("data", {})),
            session_id = payload.get("session_id", ""),
            created_at = _parse_dt(payload.get("created_at")),
        ),
    )


def _handle_metric_snapshot(operation: str, payload: dict):
    from orchestration.models import CentralMetricSnapshot
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralMetricSnapshot.objects.using(db).filter(id=pk).delete()
        return
    CentralMetricSnapshot.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            metric_name  = payload.get("metric_name", ""),
            metric_value = float(payload.get("metric_value", payload.get("value", 0.0)) or 0.0),
            period       = payload.get("period", ""),
            recorded_at  = _parse_dt(payload.get("recorded_at")),
        ),
    )


# ── Handler: administration subsystem ────────────────────────────────────────

def _handle_admin_audit_log(operation: str, payload: dict):
    from orchestration.models import CentralAdminAuditLog
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralAdminAuditLog.objects.using(db).filter(id=pk).delete()
        return
    CentralAdminAuditLog.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            actor_id    = _to_uuid(payload.get("actor_id")) or _to_uuid(payload.get("actor")),
            action      = payload.get("action", ""),
            target_type = payload.get("target_type", payload.get("content_type", "")),
            target_id   = str(payload.get("target_id", "") or ""),
            details     = payload.get("details", payload.get("extra", {})),
            ip_address  = payload.get("ip_address"),
            created_at  = _parse_dt(payload.get("created_at")),
        ),
    )


def _handle_feature_flag(operation: str, payload: dict):
    from orchestration.models import CentralFeatureFlag
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralFeatureFlag.objects.using(db).filter(id=pk).delete()
        return
    CentralFeatureFlag.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            name        = payload.get("name", ""),
            is_enabled  = payload.get("is_enabled", payload.get("enabled", False)),
            rollout_pct = int(payload.get("rollout_pct", payload.get("rollout_percentage", 0)) or 0),
            updated_at  = _parse_dt(payload.get("updated_at")),
        ),
    )


# ── Handler: security subsystem ──────────────────────────────────────────────

def _handle_security_event(operation: str, payload: dict):
    from orchestration.models import CentralSecurityEvent
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralSecurityEvent.objects.using(db).filter(id=pk).delete()
        return
    CentralSecurityEvent.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            user_id    = _to_uuid(payload.get("user_id")) or _to_uuid(payload.get("user")),
            event_type = payload.get("event_type", ""),
            severity   = payload.get("severity", ""),
            ip_address = payload.get("ip_address"),
            details    = payload.get("details", {}),
            resolved   = payload.get("resolved", False),
            created_at = _parse_dt(payload.get("created_at")),
        ),
    )


def _handle_consent_record(operation: str, payload: dict):
    from orchestration.models import CentralConsentRecord
    db = _get_db()
    pk = _to_uuid(payload.get("id"))
    if pk is None:
        return
    if operation == "delete":
        CentralConsentRecord.objects.using(db).filter(id=pk).delete()
        return
    CentralConsentRecord.objects.using(db).update_or_create(
        id=pk,
        defaults=dict(
            user_id      = _to_uuid(payload.get("user_id")) or _to_uuid(payload.get("user")),
            consent_type = payload.get("consent_type", ""),
            is_granted   = payload.get("is_granted", payload.get("granted", False)),
            ip_address   = payload.get("ip_address"),
            granted_at   = _parse_dt(payload.get("granted_at")),
            revoked_at   = _parse_dt(payload.get("revoked_at")),
        ),
    )


# ── Registry map ─────────────────────────────────────────────────────────────

MIRROR_REGISTRY: Dict[str, Callable] = {
    # accounts subsystem
    "accounts.User":             _handle_user,
    "accounts.ForgeForthUser":   _handle_user,   # alias

    # profiles subsystem
    "profiles.TalentProfile":    _handle_profile,
    "profiles.Profile":          _handle_profile,

    # organizations subsystem
    "organizations.Organization":  _handle_organization,
    "organizations.Opportunity":   _handle_opportunity,
    "organizations.JobPosting":    _handle_opportunity,  # alias

    # applications subsystem
    "applications.Application":    _handle_application,

    # media subsystem
    "media.MediaFile":             _handle_media_file,
    "media.Document":              _handle_document,

    # intelligence subsystem
    "intelligence.TalentScore":    _handle_talent_score,
    "intelligence.SkillExtraction":_handle_skill_extraction,

    # matching subsystem
    "matching.MatchScore":         _handle_match_score,

    # communications subsystem
    "communications.Notification": _handle_notification,
    "communications.Message":      _handle_message,

    # analytics subsystem
    "analytics.UserEvent":              _handle_analytics_event,
    "analytics.PlatformMetricSnapshot": _handle_metric_snapshot,

    # administration subsystem
    "administration.AdminAuditLog":  _handle_admin_audit_log,
    "administration.FeatureFlag":    _handle_feature_flag,

    # security subsystem
    "security.SecurityEvent":    _handle_security_event,
    "security.ConsentRecord":    _handle_consent_record,
}


def register(key: str, handler: Callable) -> None:
    """
    Register a custom mirror handler at runtime.
    Usage:
        from orchestration.registry import register
        register("myapp.MyModel", my_handler)
    """
    MIRROR_REGISTRY[key] = handler
    logger.debug("Mirror handler registered for %s", key)

