# -*- coding: utf-8 -*-
"""
ForgeForth Africa - SQLite Change Listener
==========================================
Monitors SQLite databases for changes using triggers and polling.

Since SQLite doesn't support native notifications like PostgreSQL LISTEN/NOTIFY,
we use a hybrid approach:
1. Insert triggers that log changes to a changelog table
2. Polling mechanism that checks for new changelog entries
3. Django signals as backup for ORM operations
"""
import sqlite3
import json
import time
import logging
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from .models import SyncEvent, SyncEventStore, SyncOperation

logger = logging.getLogger("forgeforth.orchestration.sqlite_listener")


@dataclass
class TableConfig:
    """Configuration for a tracked table."""
    name: str
    primary_key: str = "id"
    columns_to_sync: List[str] = None  # None = all columns
    exclude_columns: List[str] = None


class SQLiteChangeListener:
    """
    Monitors SQLite databases for changes.

    Creates triggers in each tracked database that log changes
    to a local changelog table. A background thread polls this
    changelog and creates SyncEvents.
    """

    CHANGELOG_TABLE = "_forgeforth_changelog"
    POLL_INTERVAL = 1  # seconds

    def __init__(self, event_store: SyncEventStore = None):
        self.event_store = event_store or SyncEventStore()
        self._listeners: Dict[str, Dict] = {}  # subsystem -> config
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def register_database(
        self,
        subsystem: str,
        db_path: str,
        tables: List[TableConfig] = None,
        auto_discover: bool = True
    ):
        """
        Register a SQLite database for change tracking.

        Args:
            subsystem: Name of the subsystem (e.g., 'accounts')
            db_path: Path to the SQLite database file
            tables: List of tables to track (if None and auto_discover=True, tracks all)
            auto_discover: Whether to auto-discover tables
        """
        db_path = str(Path(db_path).resolve())

        if not Path(db_path).exists():
            logger.warning(f"Database not found: {db_path}")
            return

        with self._lock:
            self._listeners[subsystem] = {
                'db_path': db_path,
                'tables': tables or [],
                'last_check_id': 0,
            }

        # Setup changelog table and triggers
        self._setup_changelog(subsystem, db_path)

        if auto_discover and not tables:
            self._auto_discover_tables(subsystem, db_path)

        # Setup triggers for specified tables
        self._setup_triggers(subsystem, db_path)

        # Register with event store
        self.event_store.register_subsystem(
            subsystem,
            db_path,
            [t.name if isinstance(t, TableConfig) else t for t in self._listeners[subsystem]['tables']]
        )

        logger.info(f"Registered database for {subsystem}: {db_path}")

    def _setup_changelog(self, subsystem: str, db_path: str):
        """Create changelog table in the database."""
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(f"""
                -- Changelog table for tracking changes
                CREATE TABLE IF NOT EXISTS {self.CHANGELOG_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    row_id TEXT NOT NULL,
                    old_data TEXT,
                    new_data TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    processed INTEGER DEFAULT 0
                );
                
                CREATE INDEX IF NOT EXISTS idx_changelog_processed 
                ON {self.CHANGELOG_TABLE}(processed, id);
            """)
            conn.commit()
            logger.debug(f"Created changelog table for {subsystem}")
        except Exception as e:
            logger.error(f"Failed to create changelog for {subsystem}: {e}")
        finally:
            conn.close()

    def _auto_discover_tables(self, subsystem: str, db_path: str):
        """Auto-discover tables to track (excluding system tables)."""
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT LIKE 'sqlite_%'
                AND name NOT LIKE '_forgeforth_%'
                AND name NOT LIKE 'django_%'
                """
            )
            tables = [TableConfig(name=row[0]) for row in cursor.fetchall()]

            with self._lock:
                self._listeners[subsystem]['tables'] = tables

            logger.info(f"Auto-discovered {len(tables)} tables for {subsystem}")
        finally:
            conn.close()

    def _setup_triggers(self, subsystem: str, db_path: str):
        """Create INSERT/UPDATE/DELETE triggers for tracked tables."""
        config = self._listeners.get(subsystem)
        if not config:
            return

        conn = sqlite3.connect(db_path)
        try:
            for table in config['tables']:
                table_name = table.name if isinstance(table, TableConfig) else table
                pk = table.primary_key if isinstance(table, TableConfig) else 'id'

                # Get columns for the table
                cursor = conn.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cursor.fetchall()]

                if not columns:
                    logger.warning(f"No columns found for table {table_name}")
                    continue

                # Build JSON object of all columns
                json_cols = ', '.join([f"'{col}', {col}" for col in columns if col != pk])

                # DROP existing triggers first
                for op in ['insert', 'update', 'delete']:
                    trigger_name = f"_ff_sync_{table_name}_{op}"
                    conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

                # INSERT trigger
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS _ff_sync_{table_name}_insert
                    AFTER INSERT ON {table_name}
                    BEGIN
                        INSERT INTO {self.CHANGELOG_TABLE} 
                        (table_name, operation, row_id, new_data)
                        VALUES (
                            '{table_name}',
                            'insert',
                            CAST(NEW.{pk} AS TEXT),
                            json_object({json_cols})
                        );
                    END;
                """)

                # UPDATE trigger
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS _ff_sync_{table_name}_update
                    AFTER UPDATE ON {table_name}
                    BEGIN
                        INSERT INTO {self.CHANGELOG_TABLE}
                        (table_name, operation, row_id, old_data, new_data)
                        VALUES (
                            '{table_name}',
                            'update',
                            CAST(NEW.{pk} AS TEXT),
                            json_object({json_cols.replace('NEW.', 'OLD.').replace(', ', ', OLD.').replace("'", "'")}),
                            json_object({json_cols})
                        );
                    END;
                """)

                # DELETE trigger
                old_json_cols = json_cols.replace('NEW.', 'OLD.').replace(col, f'OLD.{col}' if not col.startswith('OLD.') else col)
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS _ff_sync_{table_name}_delete
                    AFTER DELETE ON {table_name}
                    BEGIN
                        INSERT INTO {self.CHANGELOG_TABLE}
                        (table_name, operation, row_id, old_data)
                        VALUES (
                            '{table_name}',
                            'delete',
                            CAST(OLD.{pk} AS TEXT),
                            json_object({', '.join([f"'{c}', OLD.{c}" for c in columns])})
                        );
                    END;
                """)

                logger.debug(f"Created triggers for {subsystem}.{table_name}")

            conn.commit()
        except Exception as e:
            logger.error(f"Failed to setup triggers for {subsystem}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

    def start(self):
        """Start the polling thread."""
        if self._poll_thread and self._poll_thread.is_alive():
            logger.warning("Listener already running")
            return

        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="SQLiteChangeListener"
        )
        self._poll_thread.start()
        logger.info("SQLite change listener started")

    def stop(self):
        """Stop the polling thread."""
        self._stop_event.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
        logger.info("SQLite change listener stopped")

    def _poll_loop(self):
        """Background loop that polls for changelog entries."""
        while not self._stop_event.is_set():
            try:
                for subsystem, config in list(self._listeners.items()):
                    self._process_changelog(subsystem, config)
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            self._stop_event.wait(self.POLL_INTERVAL)

    def _process_changelog(self, subsystem: str, config: Dict):
        """Process new changelog entries for a subsystem."""
        db_path = config['db_path']
        last_id = config.get('last_check_id', 0)

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                f"""
                SELECT * FROM {self.CHANGELOG_TABLE}
                WHERE id > ? AND processed = 0
                ORDER BY id
                LIMIT 100
                """,
                (last_id,)
            )

            rows = cursor.fetchall()

            for row in rows:
                # Create sync event
                event = SyncEvent(
                    subsystem=subsystem,
                    table_name=row['table_name'],
                    operation=row['operation'],
                    row_id=row['row_id'],
                    data=json.loads(row['new_data'] or row['old_data'] or '{}'),
                )

                # Add to event store
                self.event_store.add_event(event)

                # Mark as processed
                conn.execute(
                    f"UPDATE {self.CHANGELOG_TABLE} SET processed = 1 WHERE id = ?",
                    (row['id'],)
                )

                # Update last check ID
                config['last_check_id'] = row['id']

            if rows:
                conn.commit()
                logger.debug(f"Processed {len(rows)} changelog entries for {subsystem}")

            conn.close()

        except Exception as e:
            logger.error(f"Error processing changelog for {subsystem}: {e}")

    def get_stats(self) -> Dict:
        """Get listener statistics."""
        stats = {
            'running': self._poll_thread.is_alive() if self._poll_thread else False,
            'subsystems': {},
        }

        for subsystem, config in self._listeners.items():
            stats['subsystems'][subsystem] = {
                'db_path': config['db_path'],
                'tables_count': len(config.get('tables', [])),
                'last_check_id': config.get('last_check_id', 0),
            }

        return stats


# Singleton instance
_listener: Optional[SQLiteChangeListener] = None


def get_listener() -> SQLiteChangeListener:
    """Get or create the singleton listener instance."""
    global _listener
    if _listener is None:
        _listener = SQLiteChangeListener()
    return _listener

