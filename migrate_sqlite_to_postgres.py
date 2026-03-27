#!/usr/bin/env python3
"""
ForgeForth Africa — SQLite → PostgreSQL Data Migration
=======================================================
Exports all existing data from db.sqlite3 and imports it into the
correct PostgreSQL databases after `manage.py migrate` has been run.

Usage (on the server after running create_databases.sql and manage.py migrate):
    python migrate_sqlite_to_postgres.py

Requirements:
    psycopg2-binary must be installed (pip install psycopg2-binary)
    All PostgreSQL databases must already exist and be migrated.
"""

import os
import sys
import json
import sqlite3
import datetime

# ---------------------------------------------------------------------------
# Connection config — matches .env
# ---------------------------------------------------------------------------
PG_HOST     = os.environ.get("PG_HOST",     "localhost")
PG_PORT     = int(os.environ.get("PG_PORT", "5432"))
PG_USER     = os.environ.get("PG_USER",     "ff_user")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "ForgeForth2026!Secure")

# Map: sqlite table name → target postgres database name
TABLE_DB_MAP = {
    # website / default DB
    "website_blogpost":            "ff_default",
    "website_blogimage":           "ff_default",
    "website_talentwaitlist":      "ff_default",
    "website_partnerregistration": "ff_default",
    "website_contactmessage":      "ff_default",
    "website_newslettersubscriber":"ff_default",
    "django_session":              "ff_default",

    # accounts DB
    "accounts_users":              "ff_accounts",
    "accounts_emailverificationtoken": "ff_accounts",
    "accounts_loginhistory":       "ff_accounts",
}

SQLITE_FILE = os.path.join(os.path.dirname(__file__), "db.sqlite3")

# ---------------------------------------------------------------------------

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_pg_conn(dbname):
    import psycopg2
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=dbname,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def sqlite_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def has_rows(conn, table):
    try:
        return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] > 0
    except Exception:
        return False


def get_columns(conn, table):
    cur = conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
    return [d[0] for d in cur.description]


def migrate_table(sqlite_conn, table, pg_dbname):
    if not has_rows(sqlite_conn, table):
        log(f"  SKIP  {table} — empty")
        return 0

    columns = get_columns(sqlite_conn, table)
    rows = sqlite_conn.execute(f'SELECT * FROM "{table}"').fetchall()

    try:
        pg = get_pg_conn(pg_dbname)
    except Exception as e:
        log(f"  ERROR connecting to {pg_dbname}: {e}")
        return 0

    cur = pg.cursor()

    # Check if the table exists in postgres
    cur.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s)",
        (table,)
    )
    if not cur.fetchone()[0]:
        log(f"  SKIP  {table} — table does not exist in {pg_dbname} (run migrate first)")
        pg.close()
        return 0

    # Check if already has data (avoid double import)
    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    existing = cur.fetchone()[0]
    if existing > 0:
        log(f"  SKIP  {table} — already has {existing} rows in {pg_dbname}")
        pg.close()
        return 0

    cols_str  = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

    count = 0
    for row in rows:
        try:
            cur.execute(insert_sql, list(row))
            count += 1
        except Exception as e:
            pg.rollback()
            log(f"  WARN  row in {table} skipped: {e}")

    pg.commit()
    pg.close()
    return count


def main():
    if not os.path.exists(SQLITE_FILE):
        log(f"SQLite file not found: {SQLITE_FILE}")
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        log("psycopg2 not installed — run: pip install psycopg2-binary")
        sys.exit(1)

    log("=" * 60)
    log("ForgeForth Africa — SQLite → PostgreSQL Migration")
    log("=" * 60)

    sqlite_conn = sqlite3.connect(SQLITE_FILE)
    all_tables  = sqlite_tables(sqlite_conn)

    log(f"SQLite tables found: {len(all_tables)}")
    log("")

    total_rows = 0
    for table, pg_db in TABLE_DB_MAP.items():
        if table not in all_tables:
            log(f"  SKIP  {table} — not in sqlite")
            continue
        log(f"  Migrating {table} → {pg_db} ...")
        n = migrate_table(sqlite_conn, table, pg_db)
        if n:
            log(f"  OK    {table} — {n} rows imported")
            total_rows += n

    sqlite_conn.close()

    log("")
    log("=" * 60)
    log(f"Migration complete — {total_rows} total rows imported")
    log("=" * 60)
    log("")
    log("Next steps:")
    log("  1. python manage.py createsuperuser  (re-create admin user)")
    log("  2. python manage.py collectstatic")
    log("  3. python start.py")


if __name__ == "__main__":
    main()

