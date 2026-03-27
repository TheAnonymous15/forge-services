# -*- coding: utf-8 -*-
import os
from django.apps import AppConfig


class OrchestrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orchestration"
    verbose_name = "Data Orchestration"

    def ready(self):
        # Wire all signal handlers after all apps are fully loaded
        from orchestration.signals import connect_signals
        connect_signals()

        # Initialize SQLite to Neon sync if configured
        # Only run in main process (not in migrations or shell)
        if os.environ.get('RUN_MAIN') == 'true':
            try:
                from orchestration.sqlite_sync.manager import initialize_on_ready
                initialize_on_ready()
            except Exception as e:
                import logging
                logging.getLogger('forgeforth').warning(f"SQLite sync init skipped: {e}")
