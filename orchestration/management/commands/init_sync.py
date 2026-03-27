# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Initialize Sync Management Command
=======================================================
Initialize the SQLite to Neon sync system.

Usage:
    python manage.py init_sync
    python manage.py init_sync --subsystems accounts,profiles
    python manage.py init_sync --no-worker
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Initialize SQLite to Neon PostgreSQL sync system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subsystems',
            type=str,
            help='Comma-separated list of subsystems to initialize'
        )
        parser.add_argument(
            '--no-listener',
            action='store_true',
            help='Do not start the change listener'
        )
        parser.add_argument(
            '--no-worker',
            action='store_true',
            help='Do not start the sync worker'
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=2,
            help='Number of worker threads (default: 2)'
        )

    def handle(self, *args, **options):
        from orchestration.sqlite_sync import SyncManager
        from orchestration.sqlite_sync.worker import NeonConfig

        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write(self.style.HTTP_INFO('  ForgeForth Africa - Sync System Initialization'))
        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write('')

        # Parse subsystems
        subsystems = None
        if options.get('subsystems'):
            subsystems = [s.strip() for s in options['subsystems'].split(',')]
            self.stdout.write(f"Subsystems: {', '.join(subsystems)}")
        else:
            self.stdout.write("Subsystems: All")

        # Check Neon configuration
        neon_config = NeonConfig.from_env()
        if neon_config.is_valid():
            self.stdout.write(
                self.style.SUCCESS(f"Neon PostgreSQL: {neon_config.host}")
            )
        else:
            self.stdout.write(
                self.style.WARNING("Neon PostgreSQL: Not configured (sync disabled)")
            )

        self.stdout.write('')
        self.stdout.write("Initializing...")

        try:
            SyncManager.initialize(
                subsystems=subsystems,
                start_listener=not options.get('no_listener'),
                start_worker=not options.get('no_worker') and neon_config.is_valid(),
                num_workers=options.get('workers', 2)
            )

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Sync system initialized successfully!'))

            # Show status
            status = SyncManager.get_status()

            listener = status.get('listener', {})
            self.stdout.write(f"  Listener running: {listener.get('running', False)}")
            self.stdout.write(f"  Subsystems registered: {len(listener.get('subsystems', {}))}")

            worker = status.get('worker', {})
            self.stdout.write(f"  Workers active: {worker.get('workers_active', 0)}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Initialization failed: {e}"))
            import traceback
            traceback.print_exc()

        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=' * 60))

