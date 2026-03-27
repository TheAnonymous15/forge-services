# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Sync Manager
================================
Central manager for SQLite to Neon PostgreSQL synchronization.

Usage:
    from orchestration.sqlite_sync import SyncManager

    # Initialize all subsystems
    SyncManager.initialize()

    # Check status
    SyncManager.get_status()

    # Manual sync
    SyncManager.sync_all()
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .models import SyncEventStore
from .listener import SQLiteChangeListener, TableConfig, get_listener
from .worker import SyncWorker, get_worker, NeonConfig

logger = logging.getLogger("forgeforth.orchestration.sync_manager")


class SyncManager:
    """
    Central manager for the SQLite → Neon sync system.

    Coordinates the listener (which monitors SQLite changes)
    and the worker (which syncs to Neon PostgreSQL).
    """

    _initialized = False
    _listener: Optional[SQLiteChangeListener] = None
    _worker: Optional[SyncWorker] = None
    _store: Optional[SyncEventStore] = None

    # Subsystem database configurations
    SUBSYSTEM_DATABASES = {
        'accounts': 'db_accounts.sqlite3',
        'profiles': 'db_profiles.sqlite3',
        'organizations': 'db_organizations.sqlite3',
        'applications': 'db_applications.sqlite3',
        'media': 'db_media.sqlite3',
        'intelligence': 'db_intelligence.sqlite3',
        'matching': 'db_matching.sqlite3',
        'communications': 'db_communications.sqlite3',
        'analytics': 'db_analytics.sqlite3',
        'administration': 'db_administration.sqlite3',
        'security': 'db_security.sqlite3',
    }

    # Tables to track per subsystem (key models only)
    SUBSYSTEM_TABLES = {
        'accounts': [
            TableConfig('accounts_user', 'id'),
            TableConfig('accounts_loginhistory', 'id'),
        ],
        'profiles': [
            TableConfig('profiles_talentprofile', 'id'),
            TableConfig('profiles_education', 'id'),
            TableConfig('profiles_workexperience', 'id'),
            TableConfig('profiles_skill', 'id'),
            TableConfig('profiles_talentskill', 'id'),
        ],
        'organizations': [
            TableConfig('organizations_organization', 'id'),
            TableConfig('organizations_opportunity', 'id'),
            TableConfig('organizations_organizationmember', 'id'),
        ],
        'applications': [
            TableConfig('applications_application', 'id'),
            TableConfig('applications_applicationstatushistory', 'id'),
            TableConfig('applications_interview', 'id'),
        ],
        'media': [
            TableConfig('media_mediafile', 'id'),
            TableConfig('media_document', 'id'),
        ],
        'intelligence': [
            TableConfig('intelligence_skilltaxonomy', 'id'),
            TableConfig('intelligence_talentscore', 'id'),
        ],
        'matching': [
            TableConfig('matching_matchscore', 'id'),
            TableConfig('matching_recommendation', 'id'),
        ],
        'communications': [
            TableConfig('communications_notification', 'id'),
            TableConfig('communications_message', 'id'),
        ],
        'analytics': [
            TableConfig('analytics_pageview', 'id'),
            TableConfig('analytics_userevent', 'id'),
        ],
    }

    @classmethod
    def initialize(
        cls,
        subsystems: List[str] = None,
        start_listener: bool = True,
        start_worker: bool = True,
        num_workers: int = 2
    ):
        """
        Initialize the sync system.

        Args:
            subsystems: List of subsystems to sync (None = all)
            start_listener: Whether to start the change listener
            start_worker: Whether to start the sync worker
            num_workers: Number of worker threads
        """
        if cls._initialized:
            logger.warning("SyncManager already initialized")
            return

        try:
            from django.conf import settings
            base_dir = Path(settings.BASE_DIR)
        except:
            base_dir = Path(__file__).resolve().parent.parent.parent

        # Create event store
        cls._store = SyncEventStore()

        # Create listener
        cls._listener = get_listener()

        # Create worker
        cls._worker = get_worker()

        # Register subsystems
        subsystems_to_register = subsystems or list(cls.SUBSYSTEM_DATABASES.keys())

        for subsystem in subsystems_to_register:
            db_file = cls.SUBSYSTEM_DATABASES.get(subsystem)
            if not db_file:
                logger.warning(f"Unknown subsystem: {subsystem}")
                continue

            db_path = base_dir / db_file

            # Create empty database if it doesn't exist
            if not db_path.exists():
                cls._create_subsystem_database(db_path, subsystem)

            tables = cls.SUBSYSTEM_TABLES.get(subsystem, [])
            cls._listener.register_database(
                subsystem=subsystem,
                db_path=str(db_path),
                tables=tables,
                auto_discover=len(tables) == 0
            )

            logger.info(f"Registered subsystem: {subsystem}")

        # Start services
        if start_listener:
            cls._listener.start()

        if start_worker:
            neon_config = NeonConfig.from_env()
            if neon_config.is_valid():
                cls._worker.start(num_workers)
            else:
                logger.warning(
                    "Neon PostgreSQL not configured. "
                    "Set NEON_DATABASE_URL or NEON_HOST/NEON_DATABASE/NEON_USER/NEON_PASSWORD "
                    "environment variables to enable cloud sync."
                )

        cls._initialized = True
        logger.info("SyncManager initialized")

    @classmethod
    def _create_subsystem_database(cls, db_path: Path, subsystem: str):
        """Create an empty subsystem database."""
        import sqlite3

        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1")  # Verify connection
        conn.close()

        logger.info(f"Created database: {db_path}")

    @classmethod
    def shutdown(cls):
        """Shutdown the sync system."""
        if cls._listener:
            cls._listener.stop()

        if cls._worker:
            cls._worker.stop()

        cls._initialized = False
        logger.info("SyncManager shutdown complete")

    @classmethod
    def get_status(cls) -> Dict:
        """Get sync system status."""
        return {
            'initialized': cls._initialized,
            'listener': cls._listener.get_stats() if cls._listener else {},
            'worker': cls._worker.get_stats() if cls._worker else {},
            'neon_configured': NeonConfig.from_env().is_valid(),
        }

    @classmethod
    def sync_all(cls) -> Dict:
        """Manually trigger sync of all pending events."""
        if not cls._worker:
            return {'error': 'Worker not initialized'}

        return cls._worker.sync_now()

    @classmethod
    def sync_subsystem(cls, subsystem: str) -> Dict:
        """Sync all data from a specific subsystem."""
        if not cls._store:
            return {'error': 'Store not initialized'}

        # Get all pending events for this subsystem
        conn = cls._store._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id FROM sync_events WHERE subsystem = ? AND status = 'pending'",
                (subsystem,)
            )
            event_ids = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

        if not event_ids:
            return {'message': 'No pending events', 'subsystem': subsystem}

        return cls._worker.sync_now(event_ids)

    @classmethod
    def get_sync_stats(cls, subsystem: str = None) -> Dict:
        """Get sync statistics."""
        if not cls._store:
            return {'error': 'Store not initialized'}

        return cls._store.get_stats(subsystem)

    @classmethod
    def cleanup_completed(cls, days: int = 30) -> int:
        """Remove completed sync events older than X days."""
        if not cls._store:
            return 0

        return cls._store.cleanup_old_events(days)

    @classmethod
    def register_subsystem(
        cls,
        name: str,
        db_path: str,
        tables: List[TableConfig] = None
    ):
        """Register a new subsystem for syncing."""
        if not cls._listener:
            raise RuntimeError("SyncManager not initialized")

        cls._listener.register_database(
            subsystem=name,
            db_path=db_path,
            tables=tables,
            auto_discover=tables is None
        )


# Django app ready hook
def initialize_on_ready():
    """Called from Django app ready() method."""
    # Only initialize if configured
    neon_url = os.environ.get('NEON_DATABASE_URL', '')

    if neon_url or os.environ.get('ENABLE_SQLITE_SYNC', '').lower() == 'true':
        try:
            SyncManager.initialize(
                start_listener=True,
                start_worker=bool(neon_url),
            )
        except Exception as e:
            logger.error(f"Failed to initialize sync: {e}")

