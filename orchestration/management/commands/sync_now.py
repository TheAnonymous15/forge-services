# -*- coding: utf-8 -*-
                        self.stdout.write(f"  - {error}")
                    for error in result['errors'][:5]:
                if result.get('errors'):
                ))
                    f"Failed: {result.get('failed', 0)} events"
                self.stdout.write(self.style.WARNING(
            if result.get('failed', 0) > 0:
            ))
                f"Synced: {result.get('success', 0)} events"
            self.stdout.write(self.style.SUCCESS(
            self.stdout.write('')
        else:
            self.stdout.write(self.style.ERROR(f"Error: {result['error']}"))
        if 'error' in result:

            result = SyncManager.sync_all()
            self.stdout.write("Syncing all pending events...")
        else:
            result = SyncManager.sync_subsystem(subsystem)
            self.stdout.write(f"Syncing subsystem: {subsystem}")
        if subsystem:

        subsystem = options.get('subsystem')

            return
            )
                'Set NEON_DATABASE_URL environment variable.'
            self.stdout.write(
            )
                self.style.ERROR('Neon PostgreSQL not configured!')
            self.stdout.write(
        if not neon_config.is_valid():
        neon_config = NeonConfig.from_env()
        # Check Neon configuration

        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('ForgeForth Africa - Manual Sync'))

        from orchestration.sqlite_sync.worker import NeonConfig
        from orchestration.sqlite_sync import SyncManager
    def handle(self, *args, **options):

        )
            help='Force sync even if worker is running'
            action='store_true',
            '--force',
        parser.add_argument(
        )
            help='Maximum events to sync (default: 100)'
            default=100,
            type=int,
            '--limit',
        parser.add_argument(
        )
            help='Sync only specific subsystem'
            type=str,
            '--subsystem',
        parser.add_argument(
    def add_arguments(self, parser):

    help = 'Manually trigger sync of pending events to Neon PostgreSQL'
class Command(BaseCommand):


from django.core.management.base import BaseCommand
"""
    python manage.py sync_now --limit 100
    python manage.py sync_now --subsystem accounts
    python manage.py sync_now
Usage:

Manually trigger sync of pending events to Neon PostgreSQL.
================================================
ForgeForth Africa - Sync Now Management Command
"""

