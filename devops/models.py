# -*- coding: utf-8 -*-
"""
ForgeForth Africa - DevOps Models (MVP1)
=========================================
Infrastructure & DevOps Management.
Deployment records, health checks, service registrations, scheduled jobs.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class ServiceRegistry(models.Model):
    """
    Registry of all microservices / subsystems with their health and configuration.
    """

    class Status(models.TextChoices):
        UP       = 'up',       _('Up')
        DOWN     = 'down',     _('Down')
        DEGRADED = 'degraded', _('Degraded')
        UNKNOWN  = 'unknown',  _('Unknown')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=150)
    description  = models.TextField(blank=True)
    version      = models.CharField(max_length=30, blank=True)
    base_url     = models.CharField(max_length=255, blank=True)
    health_url   = models.CharField(max_length=255, blank=True)
    port         = models.PositiveIntegerField(null=True, blank=True)
    status       = models.CharField(max_length=15, choices=Status.choices, default=Status.UNKNOWN, db_index=True)
    is_active    = models.BooleanField(default=True)
    config       = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'devops'
        db_table  = 'devops_service_registry'
        ordering  = ['name']

    def __str__(self):
        return f"{self.display_name} v{self.version} [{self.status}]"


class HealthCheck(models.Model):
    """
    Periodic health check result for a registered service.
    """

    class Result(models.TextChoices):
        HEALTHY   = 'healthy',   _('Healthy')
        UNHEALTHY = 'unhealthy', _('Unhealthy')
        TIMEOUT   = 'timeout',   _('Timeout')
        ERROR     = 'error',     _('Error')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service      = models.ForeignKey(ServiceRegistry, on_delete=models.CASCADE, related_name='health_checks')
    result       = models.CharField(max_length=15, choices=Result.choices, db_index=True)
    response_ms  = models.PositiveIntegerField(default=0)
    status_code  = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error        = models.TextField(blank=True)
    checked_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'devops'
        db_table  = 'devops_health_checks'
        ordering  = ['-checked_at']
        indexes   = [
            models.Index(fields=['service', 'checked_at']),
        ]

    def __str__(self):
        return f"{self.service.name}: {self.result} in {self.response_ms}ms"


class Deployment(models.Model):
    """
    Deployment record — tracks every time a version is pushed to an environment.
    """

    class Environment(models.TextChoices):
        DEVELOPMENT = 'development', _('Development')
        STAGING     = 'staging',     _('Staging')
        PRODUCTION  = 'production',  _('Production')

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', _('In Progress')
        SUCCESS     = 'success',     _('Success')
        FAILED      = 'failed',      _('Failed')
        ROLLED_BACK = 'rolled_back', _('Rolled Back')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service     = models.ForeignKey(
        ServiceRegistry, on_delete=models.CASCADE, related_name='deployments', null=True, blank=True
    )
    environment = models.CharField(max_length=15, choices=Environment.choices, db_index=True)
    version     = models.CharField(max_length=50)
    git_commit  = models.CharField(max_length=40, blank=True)
    git_branch  = models.CharField(max_length=100, blank=True)
    status      = models.CharField(max_length=15, choices=Status.choices, default=Status.IN_PROGRESS)
    deploy_log  = models.TextField(blank=True)
    deployed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    started_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'devops'
        db_table  = 'devops_deployments'
        ordering  = ['-started_at']

    def __str__(self):
        svc = self.service.name if self.service else 'platform'
        return f"{svc} v{self.version} → {self.environment} [{self.status}]"


class ScheduledJob(models.Model):
    """
    Catalogue of all Celery periodic tasks managed via the platform.
    Complements django-celery-beat with application-level metadata.
    """

    class Status(models.TextChoices):
        ACTIVE   = 'active',   _('Active')
        PAUSED   = 'paused',   _('Paused')
        DISABLED = 'disabled', _('Disabled')

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name          = models.CharField(max_length=200, unique=True)
    task_path     = models.CharField(max_length=255, help_text='Python dotted path to the Celery task')
    description   = models.TextField(blank=True)
    schedule_cron = models.CharField(max_length=100, blank=True)   # Cron expression
    schedule_secs = models.PositiveIntegerField(null=True, blank=True)  # OR interval in seconds
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    last_run_at   = models.DateTimeField(null=True, blank=True)
    last_result   = models.CharField(max_length=20, blank=True)    # success / failure
    run_count     = models.PositiveIntegerField(default=0)
    error_count   = models.PositiveIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'devops'
        db_table  = 'devops_scheduled_jobs'
        ordering  = ['name']

    def __str__(self):
        return f"{self.name} [{self.status}]"


class SystemConfig(models.Model):
    """
    Dynamic key-value configuration store for runtime settings.
    Allows changing non-sensitive configs without redeploying.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key         = models.CharField(max_length=150, unique=True, db_index=True)
    value       = models.TextField()
    value_type  = models.CharField(
        max_length=10, default='str',
        choices=[('str', 'String'), ('int', 'Integer'), ('bool', 'Boolean'), ('json', 'JSON')]
    )
    description = models.TextField(blank=True)
    is_secret   = models.BooleanField(default=False)    # mask value in UI
    updated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'devops'
        db_table  = 'devops_system_config'
        ordering  = ['key']

    def __str__(self):
        return f"{self.key} = {'***' if self.is_secret else self.value[:50]}"
