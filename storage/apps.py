# -*- coding: utf-8 -*-
"""
Storage App Configuration
"""
from django.apps import AppConfig


class StorageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'storage'
    verbose_name = 'Secure File Storage'

    def ready(self):
        """
        Initialize storage service when Django starts.
        """
        # Import signals or do any app initialization here
        pass

