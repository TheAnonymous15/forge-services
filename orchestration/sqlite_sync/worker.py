# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Sync Worker
===============================
Background worker that syncs events from local SQLite to Neon PostgreSQL.

Features:
- Async processing with connection pooling
- Automatic retry with exponential backoff
- Batch processing for efficiency
- Dead letter queue for failed events
- Health monitoring and metrics
"""
import os
import json
import time
import logging
import threading
import queue
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import execute_values, Json

from .models import SyncEvent, SyncEventStore, SyncStatus

logger = logging.getLogger("forgeforth.orchestration.sync_worker")


@dataclass
class NeonConfig:
    """Configuration for Neon PostgreSQL connection."""
    host: str = ""
    port: int = 5432
    database: str = ""
    user: str = ""
    password: str = ""
    sslmode: str = "require"
    pool_min: int = 1
    pool_max: int = 10

    @classmethod
    def from_env(cls) -> 'NeonConfig':
        """Load configuration from environment variables."""
        # Parse DATABASE_URL if available (Neon format)
        database_url = os.environ.get('NEON_DATABASE_URL', '')

        if database_url:
            # Parse: postgresql://user:pass@host/dbname?sslmode=require
            import urllib.parse
            parsed = urllib.parse.urlparse(database_url)
            return cls(
                host=parsed.hostname or '',
                port=parsed.port or 5432,
                database=parsed.path.lstrip('/') if parsed.path else '',
                user=parsed.username or '',
                password=parsed.password or '',
                sslmode=urllib.parse.parse_qs(parsed.query).get('sslmode', ['require'])[0],
            )

        return cls(
            host=os.environ.get('NEON_HOST', ''),
            port=int(os.environ.get('NEON_PORT', 5432)),
            database=os.environ.get('NEON_DATABASE', ''),
            user=os.environ.get('NEON_USER', ''),
            password=os.environ.get('NEON_PASSWORD', ''),
            sslmode=os.environ.get('NEON_SSLMODE', 'require'),
        )

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return bool(self.host and self.database and self.user)

    def get_dsn(self) -> str:
        """Get connection DSN string."""
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password} sslmode={self.sslmode}"
        )


class ConnectionPool:
    """Thread-safe connection pool for Neon PostgreSQL."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config: NeonConfig = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, config: NeonConfig = None):
        if self._initialized:
            return

        self.config = config or NeonConfig.from_env()
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._initialized = True

    def _create_pool(self):
        """Create the connection pool."""
        if self._pool:
            return

        if not self.config.is_valid():
            logger.warning("Neon PostgreSQL not configured - sync disabled")
            return

        try:
            self._pool = pool.ThreadedConnectionPool(
                self.config.pool_min,
                self.config.pool_max,
                self.config.get_dsn()
            )
            logger.info(f"Connected to Neon PostgreSQL: {self.config.host}")
        except Exception as e:
            logger.error(f"Failed to connect to Neon: {e}")
            self._pool = None

    def get_connection(self):
        """Get a connection from the pool."""
        if not self._pool:
            self._create_pool()

        if self._pool:
            return self._pool.getconn()
        return None

    def return_connection(self, conn):
        """Return a connection to the pool."""
        if self._pool and conn:
            self._pool.putconn(conn)

    def close_all(self):
        """Close all connections."""
        if self._pool:
            self._pool.closeall()
            self._pool = None


class SyncWorker:
    """
    Background worker that processes sync events.

    Reads events from SyncEventStore, transforms data,
    and writes to Neon PostgreSQL.
    """

    BATCH_SIZE = 50
    RETRY_DELAYS = [5, 15, 60, 300, 900]  # seconds: 5s, 15s, 1m, 5m, 15m

    def __init__(
        self,
        event_store: SyncEventStore = None,
        pool: ConnectionPool = None
    ):
        self.event_store = event_store or SyncEventStore()
        self.pool = pool or ConnectionPool()
        self._work_queue: queue.Queue = queue.Queue()
        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._stats = {
            'events_processed': 0,
            'events_failed': 0,
            'bytes_synced': 0,
            'last_sync': None,
        }

    def start(self, num_workers: int = 2):
        """Start worker threads."""
        self._stop_event.clear()

        # Start event fetcher
        fetcher = threading.Thread(
            target=self._fetch_loop,
            daemon=True,
            name="SyncWorker-Fetcher"
        )
        fetcher.start()
        self._workers.append(fetcher)

        # Start sync workers
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._work_loop,
                daemon=True,
                name=f"SyncWorker-{i}"
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"Sync worker started with {num_workers} workers")

    def stop(self):
        """Stop all workers."""
        self._stop_event.set()

        # Clear queue
        while not self._work_queue.empty():
            try:
                self._work_queue.get_nowait()
            except queue.Empty:
                break

        # Wait for workers
        for worker in self._workers:
            worker.join(timeout=5)

        self._workers.clear()
        self.pool.close_all()
        logger.info("Sync worker stopped")

    def _fetch_loop(self):
        """Continuously fetch pending events."""
        while not self._stop_event.is_set():
            try:
                events = self.event_store.get_pending_events(self.BATCH_SIZE)

                for event in events:
                    # Mark as in progress
                    self.event_store.update_event_status(
                        event.id,
                        SyncStatus.IN_PROGRESS.value
                    )
                    self._work_queue.put(event)

                if not events:
                    # No events, wait a bit
                    self._stop_event.wait(2)

            except Exception as e:
                logger.error(f"Error fetching events: {e}")
                self._stop_event.wait(5)

    def _work_loop(self):
        """Process events from the queue."""
        while not self._stop_event.is_set():
            try:
                event = self._work_queue.get(timeout=1)
                self._process_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in work loop: {e}")

    def _process_event(self, event: SyncEvent):
        """Process a single sync event."""
        try:
            conn = self.pool.get_connection()
            if not conn:
                # No connection available, retry later
                self._handle_failure(event, "No database connection")
                return

            try:
                # Sync to Neon
                success = self._sync_to_neon(conn, event)

                if success:
                    self.event_store.update_event_status(
                        event.id,
                        SyncStatus.COMPLETED.value
                    )
                    self._stats['events_processed'] += 1
                    self._stats['last_sync'] = datetime.utcnow().isoformat()
                    self._stats['bytes_synced'] += len(json.dumps(event.data))
                    logger.debug(f"Synced event {event.id} ({event.operation} on {event.table_name})")
                else:
                    self._handle_failure(event, "Sync returned false")

            finally:
                self.pool.return_connection(conn)

        except Exception as e:
            logger.error(f"Failed to process event {event.id}: {e}")
            self._handle_failure(event, str(e))

    def _sync_to_neon(self, conn, event: SyncEvent) -> bool:
        """
        Sync a single event to Neon PostgreSQL.

        Creates tables if needed, then performs the operation.
        """
        try:
            # Build table name (subsystem_tablename)
            neon_table = f"ff_{event.subsystem}_{event.table_name}"

            with conn.cursor() as cur:
                # Ensure table exists (simple auto-create)
                self._ensure_table_exists(cur, neon_table, event.data)

                if event.operation == 'insert':
                    self._do_insert(cur, neon_table, event)
                elif event.operation == 'update':
                    self._do_upsert(cur, neon_table, event)
                elif event.operation == 'delete':
                    self._do_delete(cur, neon_table, event)

                conn.commit()
                return True

        except Exception as e:
            conn.rollback()
            logger.error(f"Neon sync error: {e}")
            return False

    def _ensure_table_exists(self, cursor, table_name: str, sample_data: Dict):
        """Create table if it doesn't exist (simple schema)."""
        # Get columns from sample data
        columns = []
        for key, value in sample_data.items():
            if key == 'id':
                columns.append(f"{key} TEXT PRIMARY KEY")
            elif isinstance(value, bool):
                columns.append(f"{key} BOOLEAN")
            elif isinstance(value, int):
                columns.append(f"{key} BIGINT")
            elif isinstance(value, float):
                columns.append(f"{key} DOUBLE PRECISION")
            elif isinstance(value, dict) or isinstance(value, list):
                columns.append(f"{key} JSONB")
            else:
                columns.append(f"{key} TEXT")

        # Add metadata columns
        columns.extend([
            "_ff_synced_at TIMESTAMPTZ DEFAULT NOW()",
            "_ff_source_subsystem TEXT",
            "_ff_sync_id TEXT",
        ])

        create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {', '.join(columns)}
            )
        """

        try:
            cursor.execute(create_sql)
        except Exception as e:
            # Table might already exist with different schema
            logger.debug(f"Table creation note: {e}")

    def _do_insert(self, cursor, table: str, event: SyncEvent):
        """Perform INSERT operation."""
        data = event.data.copy()
        data['_ff_source_subsystem'] = event.subsystem
        data['_ff_sync_id'] = event.id

        columns = list(data.keys())
        values = list(data.values())

        # Use ON CONFLICT to handle duplicates
        placeholders = ', '.join(['%s'] * len(values))
        cursor.execute(
            f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET
            {', '.join([f'{c} = EXCLUDED.{c}' for c in columns if c != 'id'])}
            """,
            values
        )

    def _do_upsert(self, cursor, table: str, event: SyncEvent):
        """Perform UPSERT operation."""
        # Same as insert with ON CONFLICT
        self._do_insert(cursor, table, event)

    def _do_delete(self, cursor, table: str, event: SyncEvent):
        """Perform DELETE operation (soft delete - mark as deleted)."""
        # We keep the record but mark it as deleted
        cursor.execute(
            f"""
            UPDATE {table} 
            SET _ff_deleted = TRUE, _ff_deleted_at = NOW()
            WHERE id = %s
            """,
            (event.row_id,)
        )

    def _handle_failure(self, event: SyncEvent, error: str):
        """Handle a failed sync event."""
        self._stats['events_failed'] += 1

        if event.retry_count >= len(self.RETRY_DELAYS):
            # Move to dead letter
            self.event_store.update_event_status(
                event.id,
                SyncStatus.DEAD_LETTER.value,
                error_message=error
            )
            logger.warning(f"Event {event.id} moved to dead letter queue")
        else:
            # Mark as failed for retry
            self.event_store.update_event_status(
                event.id,
                SyncStatus.FAILED.value,
                error_message=error,
                increment_retry=True
            )

    def sync_now(self, event_ids: List[str] = None) -> Dict:
        """Manually trigger sync for specific events or all pending."""
        results = {'success': 0, 'failed': 0, 'errors': []}

        if event_ids:
            events = [self.event_store.get_event(eid) for eid in event_ids]
            events = [e for e in events if e]
        else:
            events = self.event_store.get_pending_events(100)

        for event in events:
            try:
                self._process_event(event)
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(str(e))

        return results

    def get_stats(self) -> Dict:
        """Get worker statistics."""
        store_stats = self.event_store.get_stats()
        return {
            **self._stats,
            'queue_size': self._work_queue.qsize(),
            'workers_active': sum(1 for w in self._workers if w.is_alive()),
            'store_stats': store_stats,
        }


# Singleton instance
_worker: Optional[SyncWorker] = None


def get_worker() -> SyncWorker:
    """Get or create the singleton worker instance."""
    global _worker
    if _worker is None:
        _worker = SyncWorker()
    return _worker

