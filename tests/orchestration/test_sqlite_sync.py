# -*- coding: utf-8 -*-
"""
ForgeForth Africa - SQLite Sync Tests
======================================
Tests for the SQLite to Neon PostgreSQL sync system.
"""
import os
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forgeforth.settings')

import django
django.setup()

from orchestration.sqlite_sync.models import (
    SyncEvent, SyncEventStore, SyncStatus, SyncOperation
)
from orchestration.sqlite_sync.listener import SQLiteChangeListener, TableConfig
from orchestration.sqlite_sync.worker import SyncWorker, NeonConfig, ConnectionPool
from orchestration.sqlite_sync.manager import SyncManager


class TestSyncEvent(unittest.TestCase):
    """Tests for SyncEvent dataclass."""

    def test_create_event(self):
        """Test creating a sync event."""
        event = SyncEvent(
            subsystem='accounts',
            table_name='accounts_user',
            operation='insert',
            row_id='123',
            data={'email': 'test@example.com', 'name': 'Test User'}
        )

        self.assertEqual(event.subsystem, 'accounts')
        self.assertEqual(event.table_name, 'accounts_user')
        self.assertEqual(event.operation, 'insert')
        self.assertEqual(event.row_id, '123')
        self.assertEqual(event.status, 'pending')
        self.assertEqual(event.retry_count, 0)
        self.assertIsNotNone(event.id)

    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = SyncEvent(
            subsystem='profiles',
            table_name='profiles_talentprofile',
            operation='update',
            row_id='456',
            data={'bio': 'Updated bio'}
        )

        data = event.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data['subsystem'], 'profiles')
        self.assertIsInstance(data['data'], str)  # JSON string

    def test_from_dict(self):
        """Test creating event from dictionary."""
        data = {
            'id': 'test-id-123',
            'subsystem': 'organizations',
            'table_name': 'organizations_organization',
            'operation': 'delete',
            'row_id': '789',
            'data': '{"name": "Test Org"}',
            'status': 'completed',
            'retry_count': 2,
        }

        event = SyncEvent.from_dict(data)

        self.assertEqual(event.id, 'test-id-123')
        self.assertEqual(event.subsystem, 'organizations')
        self.assertIsInstance(event.data, dict)
        self.assertEqual(event.data['name'], 'Test Org')


class TestSyncEventStore(unittest.TestCase):
    """Tests for SyncEventStore."""

    def setUp(self):
        """Create temporary database for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / 'test_sync.sqlite3'

        # Reset singleton
        SyncEventStore._instance = None
        self.store = SyncEventStore(str(self.db_path))

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        SyncEventStore._instance = None

    def test_add_event(self):
        """Test adding an event."""
        event = SyncEvent(
            subsystem='accounts',
            table_name='accounts_user',
            operation='insert',
            row_id='1',
            data={'email': 'test@example.com'}
        )

        event_id = self.store.add_event(event)

        self.assertEqual(event_id, event.id)

        # Verify it was stored
        retrieved = self.store.get_event(event_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.subsystem, 'accounts')

    def test_get_pending_events(self):
        """Test retrieving pending events."""
        # Add multiple events
        for i in range(5):
            event = SyncEvent(
                subsystem='profiles',
                table_name='profiles_talentprofile',
                operation='insert',
                row_id=str(i),
                data={'id': i}
            )
            self.store.add_event(event)

        pending = self.store.get_pending_events(limit=10)

        self.assertEqual(len(pending), 5)

    def test_update_event_status(self):
        """Test updating event status."""
        event = SyncEvent(
            subsystem='accounts',
            table_name='accounts_user',
            operation='insert',
            row_id='1',
            data={}
        )
        self.store.add_event(event)

        # Update to completed
        self.store.update_event_status(
            event.id,
            SyncStatus.COMPLETED.value
        )

        updated = self.store.get_event(event.id)
        self.assertEqual(updated.status, 'completed')
        self.assertIsNotNone(updated.synced_at)

    def test_get_stats(self):
        """Test getting statistics."""
        # Add events with different statuses
        for status in ['pending', 'completed', 'failed']:
            event = SyncEvent(
                subsystem='test',
                table_name='test_table',
                operation='insert',
                row_id=status,
                data={},
                status=status
            )
            self.store.add_event(event)

        stats = self.store.get_stats()

        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['pending'], 1)
        self.assertEqual(stats['completed'], 1)
        self.assertEqual(stats['failed'], 1)


class TestSQLiteChangeListener(unittest.TestCase):
    """Tests for SQLiteChangeListener."""

    def setUp(self):
        """Create temporary databases."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a test SQLite database
        self.test_db = Path(self.temp_dir) / 'test_subsystem.sqlite3'
        conn = sqlite3.connect(str(self.test_db))
        conn.execute("""
            CREATE TABLE test_users (
                id INTEGER PRIMARY KEY,
                email TEXT,
                name TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Create store
        store_path = Path(self.temp_dir) / 'sync_store.sqlite3'
        SyncEventStore._instance = None
        self.store = SyncEventStore(str(store_path))

        # Create listener
        self.listener = SQLiteChangeListener(self.store)

    def tearDown(self):
        """Clean up."""
        self.listener.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        SyncEventStore._instance = None

    def test_register_database(self):
        """Test registering a database for tracking."""
        self.listener.register_database(
            subsystem='test',
            db_path=str(self.test_db),
            tables=[TableConfig('test_users', 'id')]
        )

        stats = self.listener.get_stats()
        self.assertIn('test', stats['subsystems'])

    def test_trigger_creation(self):
        """Test that triggers are created."""
        self.listener.register_database(
            subsystem='test',
            db_path=str(self.test_db),
            tables=[TableConfig('test_users', 'id')]
        )

        # Check triggers exist
        conn = sqlite3.connect(str(self.test_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )
        triggers = [row[0] for row in cursor.fetchall()]
        conn.close()

        self.assertTrue(any('test_users_insert' in t for t in triggers))

    def test_insert_captured(self):
        """Test that inserts are captured."""
        self.listener.register_database(
            subsystem='test',
            db_path=str(self.test_db),
            tables=[TableConfig('test_users', 'id')]
        )

        # Insert a row
        conn = sqlite3.connect(str(self.test_db))
        conn.execute(
            "INSERT INTO test_users (email, name) VALUES (?, ?)",
            ('test@example.com', 'Test User')
        )
        conn.commit()
        conn.close()

        # Process changelog manually
        self.listener._process_changelog('test', self.listener._listeners['test'])

        # Check event was created
        events = self.store.get_pending_events()
        self.assertTrue(len(events) > 0)
        self.assertEqual(events[0].operation, 'insert')


class TestNeonConfig(unittest.TestCase):
    """Tests for NeonConfig."""

    def test_from_env_url(self):
        """Test parsing DATABASE_URL format."""
        url = "postgresql://user:pass@ep-xxx.neon.tech/mydb?sslmode=require"

        with patch.dict(os.environ, {'NEON_DATABASE_URL': url}):
            config = NeonConfig.from_env()

        self.assertEqual(config.host, 'ep-xxx.neon.tech')
        self.assertEqual(config.user, 'user')
        self.assertEqual(config.password, 'pass')
        self.assertEqual(config.database, 'mydb')

    def test_is_valid(self):
        """Test validity check."""
        valid = NeonConfig(
            host='test.neon.tech',
            database='testdb',
            user='testuser',
            password='testpass'
        )
        self.assertTrue(valid.is_valid())

        invalid = NeonConfig()
        self.assertFalse(invalid.is_valid())


class TestSyncManager(unittest.TestCase):
    """Tests for SyncManager."""

    def setUp(self):
        """Reset manager state."""
        SyncManager._initialized = False
        SyncManager._listener = None
        SyncManager._worker = None
        SyncManager._store = None

    def tearDown(self):
        """Clean up."""
        if SyncManager._initialized:
            SyncManager.shutdown()

    def test_get_status_uninitialized(self):
        """Test status when not initialized."""
        status = SyncManager.get_status()

        self.assertFalse(status['initialized'])

    @patch.dict(os.environ, {'NEON_DATABASE_URL': ''})
    def test_initialize_without_neon(self):
        """Test initialization without Neon configured."""
        # Should not fail, just warn
        SyncManager.initialize(
            subsystems=['accounts'],
            start_listener=False,
            start_worker=False
        )

        self.assertTrue(SyncManager._initialized)


if __name__ == '__main__':
    unittest.main()

