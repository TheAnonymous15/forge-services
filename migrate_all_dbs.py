#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Multi-Database Migration Script
====================================================
Runs migrations on each Neon PostgreSQL database in the correct order.
Each subsystem has its own database for isolation.
"""

import os
import sys
import subprocess

# Ensure Django settings are loaded
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forgeforth.settings')

# Database migration order (dependencies first)
# Format: (database_alias, [list of apps to migrate])
MIGRATION_ORDER = [
    # 1. Core Django apps - contenttypes and auth FIRST (no user dependency)
    ('default', [
        'contenttypes',
        'auth',
    ]),

    # 2. Accounts app MUST come before admin (admin depends on User model)
    ('accounts_db', [
        'accounts',
    ]),

    # 3. Now admin can be migrated (it references accounts_users)
    ('default', [
        'admin',
        'sessions',
        'token_blacklist',
    ]),

    # 4. Third-party Django apps
    ('default', [
        'django_celery_beat',
        'django_celery_results',
        'auditlog',
    ]),

    # 5. Core app (shared reference data)
    ('default', [
        'core',
    ]),

    # 6. Profiles database
    ('profiles_db', [
        'profiles',
    ]),

    # 7. Organizations database
    ('organizations_db', [
        'organizations',
    ]),

    # 8. Applications database
    ('applications_db', [
        'applications',
    ]),

    # 9. Media database
    ('media_db', [
        'media',
    ]),

    # 10. Storage database
    ('storage_db', [
        'storage',
    ]),

    # 11. Intelligence database
    ('intelligence_db', [
        'intelligence',
    ]),

    # 12. Matching database
    ('matching_db', [
        'matching',
    ]),

    # 13. Communications database
    ('communications_db', [
        'communications',
    ]),

    # 14. Analytics database
    ('analytics_db', [
        'analytics',
    ]),

    # 15. Administration database
    ('administration_db', [
        'administration',
    ]),

    # 16. Security database
    ('security_db', [
        'security',
    ]),

    # 17. Website database
    ('website_db', [
        'website',
    ]),

    # 18. Orchestration database (central sync)
    ('central_db', [
        'orchestration',
    ]),

    # 19. DevOps on default
    ('default', [
        'devops',
    ]),
]


def run_migration(database: str, apps: list) -> bool:
    """Run migrations for specific apps on a specific database."""
    print(f"\n{'='*60}")
    print(f"Migrating database: {database}")
    print(f"Apps: {', '.join(apps)}")
    print('='*60)

    success = True
    for app in apps:
        cmd = [
            sys.executable, 'manage.py', 'migrate',
            app,
            '--database', database,
            '--noinput',
        ]
        print(f"\n  -> Migrating {app}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        if result.returncode != 0:
            print(f"  [FAILED] {app}")
            print(f"  Error: {result.stderr}")
            success = False
        else:
            # Check for actual migrations applied
            if 'No migrations to apply' in result.stdout:
                print(f"  [OK] {app} (no changes)")
            elif 'Applying' in result.stdout:
                print(f"  [OK] {app} (migrations applied)")
            else:
                print(f"  [OK] {app}")

    return success


def main():
    """Main migration runner."""
    print("\n" + "="*60)
    print("  ForgeForth Africa - Multi-Database Migration")
    print("="*60)

    # Check if we're using Neon PostgreSQL
    import django
    django.setup()

    from django.conf import settings

    print(f"\nConfiguration:")
    print(f"  USE_NEON_POSTGRES: {settings.USE_NEON_POSTGRES}")
    print(f"  USE_SINGLE_DATABASE: {settings.USE_SINGLE_DATABASE}")
    print(f"  Number of databases: {len(settings.DATABASES)}")

    if not settings.USE_NEON_POSTGRES:
        print("\n[WARNING] USE_NEON_POSTGRES is False. Using standard migrate.")
        subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'])
        return

    # Run migrations in order
    all_success = True
    for database, apps in MIGRATION_ORDER:
        if database not in settings.DATABASES:
            print(f"\n[SKIP] Database '{database}' not configured")
            continue

        success = run_migration(database, apps)
        if not success:
            all_success = False
            print(f"\n[ERROR] Failed to migrate {database}")
            # Continue with other databases

    print("\n" + "="*60)
    if all_success:
        print("  All migrations completed successfully!")
    else:
        print("  Some migrations failed. Check errors above.")
    print("="*60 + "\n")

    return 0 if all_success else 1


if __name__ == '__main__':
    sys.exit(main())

