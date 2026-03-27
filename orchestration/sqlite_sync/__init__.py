# -*- coding: utf-8 -*-
"""
ForgeForth Africa - SQLite to Neon PostgreSQL Sync
===================================================
Event-driven synchronization from local SQLite databases to central Neon PostgreSQL.

Architecture:
    ┌──────────────────────────────────────────────────────────────────────┐
    │                        Local Environment                              │
    │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐         │
    │  │ Accounts  │  │ Profiles  │  │   Orgs    │  │   Apps    │  ...    │
    │  │  SQLite   │  │  SQLite   │  │  SQLite   │  │  SQLite   │         │
    │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘         │
    │        │              │              │              │               │
    │        └──────────────┴──────────────┴──────────────┘               │
    │                              │                                       │
    │                    ┌─────────▼─────────┐                            │
    │                    │  SQLite Listener  │ (Watches for changes)      │
    │                    └─────────┬─────────┘                            │
    │                              │                                       │
    │                    ┌─────────▼─────────┐                            │
    │                    │   Event Queue     │ (Local change log)         │
    │                    └─────────┬─────────┘                            │
    │                              │                                       │
    │                    ┌─────────▼─────────┐                            │
    │                    │  Sync Worker      │ (Async background)         │
    │                    └─────────┬─────────┘                            │
    └──────────────────────────────┼───────────────────────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │     HTTPS       │
                          └────────┬────────┘
                                   │
    ┌──────────────────────────────▼───────────────────────────────────────┐
    │                     Neon PostgreSQL (Cloud)                          │
    │  ┌────────────────────────────────────────────────────────────────┐  │
    │  │                   Central Database                             │  │
    │  │  • All subsystem data unified                                  │  │
    │  │  • High availability                                           │  │
    │  │  • Scalable                                                    │  │
    │  │  • Full-text search                                            │  │
    │  └────────────────────────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────────────────────────┘

Benefits:
- Local SQLite for fast reads/writes (no network latency)
- Cloud PostgreSQL for durability, scale, analytics
- Event-driven: only syncs what changes
- Resilient: retries on failure, works offline
- Audit trail: full sync history

Usage:
    from orchestration.sqlite_sync import SyncManager

    # Initialize sync for all subsystems
    SyncManager.initialize()

    # Or for specific subsystem
    SyncManager.register_subsystem('accounts', 'db_accounts.sqlite3')
"""

from .manager import SyncManager
from .listener import SQLiteChangeListener
from .worker import SyncWorker
from .models import SyncEvent, SyncStatus

__all__ = [
    'SyncManager',
    'SQLiteChangeListener',
    'SyncWorker',
    'SyncEvent',
    'SyncStatus',
]

