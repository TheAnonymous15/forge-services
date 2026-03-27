# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Data Orchestration Service
===============================================
Event-driven sync from subsystem PostgreSQL databases → Central PostgreSQL DB.

Architecture:
  Subsystem write → Django signal → Celery task (Redis queue)
      → Orchestration worker → Central DB write
      → Retry on failure (exponential backoff)
      → Dead letter queue on exhausted retries
      → Nightly full-sync safety net (Celery beat)
"""

