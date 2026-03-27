-- ============================================================
-- ForgeForth Africa - PostgreSQL Database Creation Script
-- Run this as the postgres superuser:
--   psql -U postgres -f create_databases.sql
-- ============================================================

-- Create dedicated DB user
CREATE USER ff_user WITH PASSWORD 'ForgeForth2026!Secure' CREATEDB;

-- ── Default DB (Django admin, sessions, celery, devops, website) ──────────────
CREATE DATABASE ff_default  OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;

-- ── Subsystem databases ────────────────────────────────────────────────────────
CREATE DATABASE ff_accounts       OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_profiles       OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_organizations  OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_applications   OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_media          OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_intelligence   OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_communications OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_analytics      OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_administration OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
CREATE DATABASE ff_security       OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;

-- ── Central unified DB (orchestration sink) ───────────────────────────────────
CREATE DATABASE ff_central        OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;

-- ── Website DB (FastAPI website app) ──────────────────────────────────────────
CREATE DATABASE ff_website        OWNER ff_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;

-- ── Grant all privileges ───────────────────────────────────────────────────────
GRANT ALL PRIVILEGES ON DATABASE ff_default        TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_accounts       TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_profiles       TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_organizations  TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_applications   TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_media          TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_intelligence   TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_communications TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_analytics      TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_administration TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_security       TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_central        TO ff_user;
GRANT ALL PRIVILEGES ON DATABASE ff_website        TO ff_user;

-- ── Verify ────────────────────────────────────────────────────────────────────
\l ff_*

