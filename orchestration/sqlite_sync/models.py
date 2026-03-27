# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Sync Event Models
=====================================
Local SQLite models for tracking sync events and status.
"""
import enum
import uuid
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict


class SyncStatus(enum.Enum):
    """Status of a sync event."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class SyncOperation(enum.Enum):
    """Type of database operation."""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class SyncEvent:
    """
    Represents a database change that needs to be synced.

    Stored in a local SQLite changelog database.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subsystem: str = ""  # e.g., 'accounts', 'profiles'
    table_name: str = ""  # e.g., 'accounts_user'
    operation: str = "insert"  # insert, update, delete
    row_id: str = ""  # Primary key of the affected row
    data: Dict[str, Any] = field(default_factory=dict)  # Row data as JSON
    status: str = "pending"
    retry_count: int = 0
    max_retries: int = 5
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    synced_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'subsystem': self.subsystem,
            'table_name': self.table_name,
            'operation': self.operation,
            'row_id': str(self.row_id),
            'data': json.dumps(self.data) if isinstance(self.data, dict) else self.data,
            'status': self.status,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'error_message': self.error_message,
            'created_at': self.created_at,
            'synced_at': self.synced_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncEvent':
        """Create from dictionary."""
        data_json = data.get('data', '{}')
        if isinstance(data_json, str):
            try:
                data['data'] = json.loads(data_json)
            except json.JSONDecodeError:
                data['data'] = {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SyncEventStore:
    """
    SQLite-based storage for sync events.

    Uses a dedicated changelog database separate from subsystem databases.
    """

    _instance = None

    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        if db_path is None:
            from django.conf import settings
            db_path = str(Path(settings.BASE_DIR) / 'sync_changelog.sqlite3')

        self.db_path = db_path
        self._create_tables()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """Create sync event tables."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                -- Main sync event log
                CREATE TABLE IF NOT EXISTS sync_events (
                    id TEXT PRIMARY KEY,
                    subsystem TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    row_id TEXT NOT NULL,
                    data TEXT,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 5,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    synced_at TEXT,
                    
                    -- Indexes for efficient querying
                    CONSTRAINT valid_status CHECK (
                        status IN ('pending', 'in_progress', 'completed', 'failed', 'dead_letter')
                    )
                );
                
                CREATE INDEX IF NOT EXISTS idx_sync_events_status 
                ON sync_events(status);
                
                CREATE INDEX IF NOT EXISTS idx_sync_events_subsystem 
                ON sync_events(subsystem);
                
                CREATE INDEX IF NOT EXISTS idx_sync_events_created 
                ON sync_events(created_at);
                
                -- Sync statistics
                CREATE TABLE IF NOT EXISTS sync_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subsystem TEXT NOT NULL,
                    date TEXT NOT NULL,
                    events_created INTEGER DEFAULT 0,
                    events_synced INTEGER DEFAULT 0,
                    events_failed INTEGER DEFAULT 0,
                    bytes_transferred INTEGER DEFAULT 0,
                    avg_sync_time_ms INTEGER DEFAULT 0,
                    UNIQUE(subsystem, date)
                );
                
                -- Subsystem registration
                CREATE TABLE IF NOT EXISTS registered_subsystems (
                    name TEXT PRIMARY KEY,
                    db_path TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    last_sync TEXT,
                    tables_tracked TEXT,  -- JSON array
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def add_event(self, event: SyncEvent) -> str:
        """Add a new sync event."""
        conn = self._get_connection()
        try:
            data = event.to_dict()
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])

            conn.execute(
                f"INSERT INTO sync_events ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
            conn.commit()
            return event.id
        finally:
            conn.close()

    def get_pending_events(self, limit: int = 100) -> List[SyncEvent]:
        """Get pending events to process."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM sync_events 
                WHERE status = 'pending' OR (status = 'failed' AND retry_count < max_retries)
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            return [SyncEvent.from_dict(dict(row)) for row in rows]
        finally:
            conn.close()

    def update_event_status(
        self,
        event_id: str,
        status: str,
        error_message: str = None,
        increment_retry: bool = False
    ):
        """Update event status."""
        conn = self._get_connection()
        try:
            updates = ["status = ?"]
            params = [status]

            if error_message:
                updates.append("error_message = ?")
                params.append(error_message)

            if status == 'completed':
                updates.append("synced_at = ?")
                params.append(datetime.utcnow().isoformat())

            if increment_retry:
                updates.append("retry_count = retry_count + 1")

            params.append(event_id)

            conn.execute(
                f"UPDATE sync_events SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
        finally:
            conn.close()

    def get_event(self, event_id: str) -> Optional[SyncEvent]:
        """Get a specific event."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM sync_events WHERE id = ?",
                (event_id,)
            )
            row = cursor.fetchone()
            if row:
                return SyncEvent.from_dict(dict(row))
            return None
        finally:
            conn.close()

    def get_stats(self, subsystem: str = None) -> Dict[str, Any]:
        """Get sync statistics."""
        conn = self._get_connection()
        try:
            where = ""
            params = []
            if subsystem:
                where = "WHERE subsystem = ?"
                params.append(subsystem)

            cursor = conn.execute(
                f"""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'dead_letter' THEN 1 ELSE 0 END) as dead_letter
                FROM sync_events {where}
                """,
                params
            )
            row = cursor.fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def cleanup_old_events(self, days: int = 30) -> int:
        """Remove completed events older than X days."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                DELETE FROM sync_events 
                WHERE status = 'completed' 
                AND datetime(synced_at) < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def register_subsystem(
        self,
        name: str,
        db_path: str,
        tables: List[str] = None
    ):
        """Register a subsystem for syncing."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO registered_subsystems 
                (name, db_path, tables_tracked, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, db_path, json.dumps(tables or []), datetime.utcnow().isoformat())
            )
            conn.commit()
        finally:
            conn.close()

    def get_registered_subsystems(self) -> List[Dict[str, Any]]:
        """Get all registered subsystems."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM registered_subsystems WHERE is_active = 1"
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                data = dict(row)
                if data.get('tables_tracked'):
                    data['tables_tracked'] = json.loads(data['tables_tracked'])
                result.append(data)
            return result
        finally:
            conn.close()

