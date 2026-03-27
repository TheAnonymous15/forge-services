# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Core URLs
==============================
URL routing for core services (health checks, diagnostics).
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Health check endpoints
    path('health/', views.health_check, name='health'),
    path('health/db/', views.database_health, name='health_db'),
    path('health/cache/', views.cache_health, name='health_cache'),
    path('health/ssl/', views.ssl_status, name='health_ssl'),
]

