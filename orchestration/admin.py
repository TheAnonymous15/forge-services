# -*- coding: utf-8 -*-
"""
Orchestration Admin — ForgeForth Africa
Central data sync monitoring dashboard.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from orchestration.models import (
    SyncEventLog,
    DeadLetterEvent,
    FullSyncReport,
    CentralUser,
    CentralProfile,
    CentralOrganization,
    CentralOpportunity,
    CentralApplication,
    CentralSkill,
)


# ── SyncEventLog ─────────────────────────────────────────────────────────────

@admin.register(SyncEventLog)
class SyncEventLogAdmin(admin.ModelAdmin):
    list_display     = ("id_short", "app_label", "model_name", "instance_id", "operation", "status_badge", "retry_count", "created_at", "synced_at")
    list_filter      = ("status", "app_label", "operation")
    search_fields    = ("app_label", "model_name", "instance_id", "error_message")
    ordering         = ("-created_at",)
    readonly_fields  = ("id", "app_label", "model_name", "instance_id", "operation", "payload", "error_message", "celery_task_id", "created_at", "synced_at", "retry_count")
    date_hierarchy   = "created_at"
    list_per_page    = 50

    actions = ["requeue_selected"]

    def id_short(self, obj):
        return str(obj.id)[:8] + "…"
    id_short.short_description = "ID"

    def status_badge(self, obj):
        colours = {
            "pending":  "#f59e0b",
            "success":  "#10b981",
            "failed":   "#ef4444",
            "retrying": "#6366f1",
            "dead":     "#64748b",
        }
        colour = colours.get(obj.status, "#94a3b8")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:9999px;font-size:11px">{}</span>',
            colour, obj.status.upper()
        )
    status_badge.short_description = "Status"

    @admin.action(description="Re-queue selected events")
    def requeue_selected(self, request, queryset):
        from orchestration.tasks import sync_event_to_central
        count = 0
        for event in queryset.exclude(status=SyncEventLog.Status.SUCCESS):
            event.status      = SyncEventLog.Status.PENDING
            event.retry_count = 0
            event.error_message = ""
            event.save(update_fields=["status", "retry_count", "error_message"])
            sync_event_to_central.apply_async(args=[str(event.id)], countdown=1)
            count += 1
        self.message_user(request, f"Re-queued {count} events.")


# ── DeadLetterEvent ──────────────────────────────────────────────────────────

@admin.register(DeadLetterEvent)
class DeadLetterEventAdmin(admin.ModelAdmin):
    list_display    = ("id_short", "app_label", "model_name", "instance_id", "operation", "retry_count", "resolved_badge", "created_at")
    list_filter     = ("resolved", "app_label", "operation")
    search_fields   = ("app_label", "model_name", "instance_id", "last_error")
    ordering        = ("-created_at",)
    readonly_fields = ("id", "original_event", "app_label", "model_name", "instance_id", "operation", "payload", "last_error", "retry_count", "created_at")
    list_per_page   = 50

    actions = ["replay_selected"]

    def id_short(self, obj):
        return str(obj.id)[:8] + "…"
    id_short.short_description = "ID"

    def resolved_badge(self, obj):
        if obj.resolved:
            return format_html('<span style="color:#10b981;font-weight:bold">Resolved</span>')
        return format_html('<span style="color:#ef4444;font-weight:bold">Unresolved</span>')
    resolved_badge.short_description = "Resolved"

    @admin.action(description="Replay selected dead-letter events")
    def replay_selected(self, request, queryset):
        from orchestration.tasks import requeue_dead_letter
        count = 0
        for dlq in queryset.filter(resolved=False):
            requeue_dead_letter.apply_async(args=[str(dlq.id)], countdown=1)
            count += 1
        self.message_user(request, f"Replayed {count} dead-letter events.")


# ── FullSyncReport ────────────────────────────────────────────────────────────

@admin.register(FullSyncReport)
class FullSyncReportAdmin(admin.ModelAdmin):
    list_display  = ("id_short", "status", "total_synced", "total_failed", "started_at", "completed_at", "duration")
    list_filter   = ("status",)
    ordering      = ("-started_at",)
    readonly_fields = ("id", "started_at", "completed_at", "status", "total_synced", "total_failed", "details", "error_message")
    list_per_page = 30

    def id_short(self, obj):
        return str(obj.id)[:8] + "…"
    id_short.short_description = "ID"

    def duration(self, obj):
        if obj.completed_at and obj.started_at:
            delta = obj.completed_at - obj.started_at
            return f"{delta.total_seconds():.1f}s"
        return "—"
    duration.short_description = "Duration"


# ── Central Mirror Models (read-only) ─────────────────────────────────────────

@admin.register(CentralUser)
class CentralUserAdmin(admin.ModelAdmin):
    list_display  = ("email", "first_name", "last_name", "role", "is_active", "is_verified", "synced_at")
    list_filter   = ("role", "is_active", "is_verified")
    search_fields = ("email", "first_name", "last_name")
    ordering      = ("-synced_at",)
    readonly_fields = [f.name for f in CentralUser._meta.get_fields() if hasattr(f, "name")]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CentralProfile)
class CentralProfileAdmin(admin.ModelAdmin):
    list_display  = ("user_id", "headline", "country", "city", "experience_years", "availability", "synced_at")
    list_filter   = ("availability", "employment_status", "is_public")
    search_fields = ("headline", "bio", "country", "city")
    ordering      = ("-synced_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CentralOrganization)
class CentralOrganizationAdmin(admin.ModelAdmin):
    list_display  = ("name", "org_type", "industry", "country", "city", "is_verified", "synced_at")
    list_filter   = ("org_type", "is_verified", "country")
    search_fields = ("name", "industry", "country", "city")
    ordering      = ("-synced_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CentralOpportunity)
class CentralOpportunityAdmin(admin.ModelAdmin):
    list_display  = ("title", "opp_type", "location", "is_remote", "status", "deadline", "synced_at")
    list_filter   = ("opp_type", "is_remote", "status")
    search_fields = ("title", "location")
    ordering      = ("-synced_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CentralApplication)
class CentralApplicationAdmin(admin.ModelAdmin):
    list_display  = ("id", "applicant_id", "opportunity_id", "status", "applied_at", "synced_at")
    list_filter   = ("status",)
    ordering      = ("-synced_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CentralSkill)
class CentralSkillAdmin(admin.ModelAdmin):
    list_display  = ("name", "category", "usage_count", "updated_at")
    list_filter   = ("category",)
    search_fields = ("name", "category")
    ordering      = ("-usage_count",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
