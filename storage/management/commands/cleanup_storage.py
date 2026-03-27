# -*- coding: utf-8 -*-
"""
Storage Subsystem - Management Command: Cleanup Expired Files
"""
from django.core.management.base import BaseCommand
from storage.services import get_storage_service


class Command(BaseCommand):
    help = 'Clean up expired files from storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        storage = get_storage_service()

        if options['dry_run']:
            from storage.models import StoredFile
            from django.utils import timezone

            expired = StoredFile.objects.filter(
                status='active',
                expires_at__lt=timezone.now()
            )
            count = expired.count()

            self.stdout.write(f"Would delete {count} expired files:")
            for f in expired[:20]:
                self.stdout.write(f"  - {f.file_id}: {f.filename}")
            if count > 20:
                self.stdout.write(f"  ... and {count - 20} more")
        else:
            deleted = storage.cleanup_expired()
            self.stdout.write(
                self.style.SUCCESS(f'Deleted {deleted} expired files')
            )

