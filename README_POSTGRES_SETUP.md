# ForgeForth Africa — PostgreSQL Setup Guide

## Databases Overview

| Alias | Database Name | Purpose |
|---|---|---|
| default | ff_default | Django admin, sessions, celery, website |
| accounts_db | ff_accounts | User accounts & auth |
| profiles_db | ff_profiles | Talent profiles |
| organizations_db | ff_organizations | Organizations & opportunities |
| applications_db | ff_applications | Job applications & workflow |
| media_db | ff_media | Media files & documents |
| intelligence_db | ff_intelligence | AI/ML skill extraction & matching |
| communications_db | ff_communications | Notifications & messages |
| analytics_db | ff_analytics | Analytics & reporting |
| administration_db | ff_administration | Admin governance & audit |
| security_db | ff_security | Security events & compliance |
| central_db | ff_central | Orchestration sink (mirrors all) |
| ff_website | ff_website | FastAPI informational website |

---

## Step 1 — Create All Databases (run once on the server)

```bash
psql -U postgres -f create_databases.sql
```

This creates:
- User `ff_user` with password `ForgeForth2026!Secure`
- All 13 databases listed above
- Grants all privileges to `ff_user`

---

## Step 2 — Install Requirements

```bash
pip install -r requirements.production.txt
```

---

## Step 3 — Run Migrations (all databases)

```bash
python manage.py migrate --database=default
python manage.py migrate --database=accounts_db
python manage.py migrate --database=profiles_db
python manage.py migrate --database=organizations_db
python manage.py migrate --database=applications_db
python manage.py migrate --database=media_db
python manage.py migrate --database=intelligence_db
python manage.py migrate --database=communications_db
python manage.py migrate --database=analytics_db
python manage.py migrate --database=administration_db
python manage.py migrate --database=security_db
python manage.py migrate --database=central_db
```

Or just run `start.py` — it does all of this automatically.

---

## Step 4 — Migrate Existing SQLite Data to PostgreSQL

If there is existing data in `db.sqlite3` (blogs, users, waitlist, etc):

```bash
python migrate_sqlite_to_postgres.py
```

---

## Step 5 — Start the Application

```bash
python start.py
```

`start.py` handles everything: pip install → migrations → data migration → collectstatic → gunicorn.

---

## Changing the Password

If you change the database password:
1. Update `.env` — all `*_DATABASE_URL` entries
2. Update `create_databases.sql` — the `CREATE USER` line
3. Update `migrate_sqlite_to_postgres.py` — `PG_PASSWORD` default

---

## FastAPI Website Database

The FastAPI informational website (`/website`) uses its own database `ff_website`.
Its URL is set in `/website/.env`:

```
DATABASE_URL=postgresql+asyncpg://ff_user:ForgeForth2026!Secure@localhost:5432/ff_website
```

