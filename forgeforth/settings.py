# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Django Settings
Enterprise Talent Infrastructure Platform
"""

from pathlib import Path
from datetime import timedelta
import os
import logging.handlers
import environ

# ── MySQL driver fallback ────────────────────────────────────────────────────
# On some cPanel hosts mysqlclient cannot compile.  PyMySQL is a pure-Python
# drop-in replacement.  We register it only if mysqlclient is not available.
try:
    import MySQLdb  # noqa: F401 — mysqlclient present, nothing to do
except ImportError:
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass  # Neither installed — will fail loudly only if MySQL is configured
# ────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    USE_S3=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "0.0.0.0", "forgeforthafrica.com", "www.forgeforthafrica.com"]
)

# Accept any host in DEBUG mode (dev only — never set DEBUG=True in production)
if DEBUG:
    ALLOWED_HOSTS = ["*"]
SITE_URL = env("SITE_URL", default="http://localhost:8000")
SITE_NAME = env("SITE_NAME", default="ForgeForth Africa")

MIN_AGE = 18

# -------------------------------------------------------
# API Service & Authentication Settings
# -------------------------------------------------------
# Auth service URL for centralized authentication
AUTH_SERVICE_URL = env("AUTH_SERVICE_URL", default="/api/v1/auth")
# Secret key for signing requests between website and API service
WEBSITE_AUTH_SECRET = env("WEBSITE_AUTH_SECRET", default="website-auth-secret-change-in-production")

# -------------------------------------------------------
# Translation Settings
# -------------------------------------------------------
# DISABLED: Server-side translation causes massive slowdowns
# Using client-side Google Translate Widget instead (instant)
TRANSLATE_RESPONSES = env.bool("TRANSLATE_RESPONSES", default=False)

# -------------------------------------------------------
# Applications
# -------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "channels",  # WebSocket support
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "auditlog",
    "django_extensions",
]

LOCAL_APPS = [
    # Core services (data federation, security)
    "core",
    # 0. Informational website
    "website",
    # 1. Identity & Access Management
    "accounts",
    # 2. User & Talent Profile Management
    "profiles",
    # 3. Organization & Opportunity Management
    "organizations",  # we keep this as sub of the app
    # 4. Application & Workflow Management
    "applications",
    # 5. Secure Media Ingestion & Processing
    "media",
    # 6. Talent Intelligence & Skill Extraction
    "intelligence",
    # 7. Matching & Recommendation Engine
    "matching",
    # 8. Communication & Notification System
    "communications",
    # 9. Analytics & Reporting System
    "analytics",
    # 10. Administration & Governance
    "administration",
    # 11. Security & Compliance Layer
    "security",
    # 12. Infrastructure & DevOps Management
    "devops",
    # 13. Data Orchestration Service (event-driven central sync)
    "orchestration",
    # 14. Secure Storage Service (standalone subsystem)
    "storage",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# -------------------------------------------------------
# Middleware
# -------------------------------------------------------
MIDDLEWARE = [
    "website.middleware.MaintenanceModeMiddleware",   # reads config.json (cached)
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # "auditlog.middleware.AuditlogMiddleware",  # Disabled for performance - enable in production
    # "website.translations.middleware.TranslationMiddleware",  # Disabled - using client-side Google Translate
]

ROOT_URLCONF = "forgeforth.urls"

# -------------------------------------------------------
# Templates
# -------------------------------------------------------
TEMPLATES = [
    # ── Jinja2: used for website app templates ──────────────────────────
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "website" / "templates" / "website"],
        "APP_DIRS": False,
        "OPTIONS": {
            "environment": "website.jinja2_env.environment",
            "extensions": [],
        },
    },
    # ── Django templates: used for admin, DRF, error pages, and all other apps ───────
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "website" / "templates",
            BASE_DIR / "communications" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "website.context_processors.waitlist_context",
            ],
        },
    },
]

WSGI_APPLICATION = "forgeforth.wsgi.application"
ASGI_APPLICATION = "forgeforth.asgi.application"

# -------------------------------------------------------
# Channels / WebSocket Configuration
# -------------------------------------------------------
# Channel layer backend - uses Redis for production, in-memory for dev
_channel_redis_url = env("CHANNEL_REDIS_URL", default=env("CACHE_URL", default=""))

if _channel_redis_url.startswith("redis://") and not DEBUG:
    # Production: Use Redis channel layer with SSL support
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_channel_redis_url],
                "capacity": 1500,
                "expiry": 10,
            },
        },
    }
else:
    # Development: Use in-memory channel layer
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# WebSocket security settings
WEBSOCKET_SSL_REQUIRED = not DEBUG  # Require WSS in production
WEBSOCKET_MAX_CONNECTIONS_PER_USER = 5
WEBSOCKET_RATE_LIMIT = 100  # messages per minute

# -------------------------------------------------------
# Database
#
# The application supports three backends — choose via DATABASE_URL in .env:
#
#   MySQL / MariaDB  (cPanel shared hosting — provided natively, NO install needed)
#     DATABASE_URL=mysql://cpanel_user:password@localhost/cpanel_dbname
#
#   PostgreSQL       (local dev, VPS, or self-managed server)
#     DATABASE_URL=postgres://user:pass@localhost:5432/dbname
#
#   SQLite           (local development only — never production)
#     DATABASE_URL=sqlite:///db.sqlite3
#
# Shared cPanel hosting note:
#   cPanel provides MySQL out of the box.  Create one database through
#   cPanel → MySQL Databases, then set DATABASE_URL to that MySQL URL.
#   All subsystems share that single database (USE_SINGLE_DATABASE=True).
#   No external services, no installs, no extra cost.
#
# Single vs Multi database:
#   USE_SINGLE_DATABASE=True  → all subsystem aliases route to DATABASE_URL
#                                (use this on cPanel / shared hosting)
#   USE_SINGLE_DATABASE=False → each subsystem reads its own *_DATABASE_URL
#                                (use this on VPS / dedicated servers)
#
# DB alias convention : <subsystem>_db  (matches ForgeForthDBRouter.ROUTE_MAP)
# -------------------------------------------------------

def _parse_db_url(url: str) -> dict:
    """
    Parse a database URL string into a Django DATABASES dict entry.
    Handles postgres://, mysql://, sqlite:// transparently.
    """
    cfg = environ.Env.db_url_config(url)

    # Normalise MySQL ENGINE — django-environ sometimes emits the wrong one
    if url.startswith(("mysql://", "mysql+pymysql://", "mysqlclient://")):
        cfg["ENGINE"] = "django.db.backends.mysql"

    # MySQL charset + strict mode
    if cfg.get("ENGINE") == "django.db.backends.mysql":
        cfg.setdefault("OPTIONS", {})
        cfg["OPTIONS"].setdefault("charset", "utf8mb4")
        cfg["OPTIONS"].setdefault("init_command", "SET sql_mode='STRICT_TRANS_TABLES'")

    return cfg


def _load_db(env_key: str, fallback_url: str = None) -> dict:
    """
    Read a DATABASE_URL from env.  Falls back to fallback_url when the key
    is absent (used in multi-DB mode to gracefully fall back to DATABASE_URL).
    Blocks SQLite in production.
    """
    from django.core.exceptions import ImproperlyConfigured
    url = env(env_key, default=None) or fallback_url
    if not url:
        raise ImproperlyConfigured(
            f"Missing database URL: set {env_key} in .env\n"
            f"  cPanel MySQL  → mysql://cpanel_user:pass@localhost/dbname\n"
            f"  PostgreSQL    → postgres://user:pass@localhost:5432/dbname\n"
            f"  Dev SQLite    → sqlite:///db.sqlite3"
        )
    if not DEBUG and url.startswith("sqlite"):
        raise ImproperlyConfigured(
            f"{env_key} uses SQLite — not allowed in production.\n"
            f"  Use MySQL (cPanel) or PostgreSQL."
        )
    return _parse_db_url(url)


# ── Subsystem specs (env prefix, db alias) ──────────────────────────────────
_SUBSYSTEM_DB_SPECS = [
    ("ACCOUNTS",       "accounts_db"),
    ("PROFILES",       "profiles_db"),
    ("ORGANIZATIONS",  "organizations_db"),
    ("APPLICATIONS",   "applications_db"),
    ("MEDIA",          "media_db"),
    ("INTELLIGENCE",   "intelligence_db"),
    ("COMMUNICATIONS", "communications_db"),
    ("ANALYTICS",      "analytics_db"),
    ("ADMINISTRATION", "administration_db"),
    ("SECURITY",       "security_db"),
    ("WEBSITE",        "website_db"),
    ("STORAGE",        "storage_db"),
    ("MATCHING",       "matching_db"),
    ("ORCHESTRATION",  "orchestration_db"),
]

# Database mode flags
USE_SINGLE_DATABASE = env.bool("USE_SINGLE_DATABASE", default=True)
USE_NEON_POSTGRES = env.bool("USE_NEON_POSTGRES", default=False)

_default_url = env("DATABASE_URL", default="sqlite:///db.sqlite3")
_default_cfg = _load_db("DATABASE_URL", _default_url)
_default_cfg["ATOMIC_REQUESTS"] = True

# Connection pooling for better performance with Neon serverless
# Keep connections alive longer to avoid cold start latency
if "postgresql" in _default_cfg.get("ENGINE", ""):
    _default_cfg["CONN_MAX_AGE"] = 60  # Keep connections for 60 seconds
    _default_cfg["CONN_HEALTH_CHECKS"] = True  # Check connection health before use
    _default_cfg.setdefault("OPTIONS", {})
    _default_cfg["OPTIONS"]["connect_timeout"] = 10  # 10 second connection timeout

DATABASES = {"default": _default_cfg}

if USE_NEON_POSTGRES:
    # ── Neon PostgreSQL Mode ─────────────────────────────────────────────────
    # Each subsystem has its own Neon database for isolation & scalability
    # Connection strings: NEON_<SUBSYSTEM>_URL
    for _prefix, _alias in _SUBSYSTEM_DB_SPECS:
        _neon_url = env(f"NEON_{_prefix}_URL", default=None)
        if _neon_url:
            _cfg = _parse_db_url(_neon_url)
            _cfg["ATOMIC_REQUESTS"] = True
            # Force SSL for Neon
            _cfg.setdefault("OPTIONS", {})
            _cfg["OPTIONS"]["sslmode"] = "require"
            DATABASES[_alias] = _cfg
        else:
            # Fallback to default if not configured
            DATABASES[_alias] = _default_cfg.copy()

    # Central/Orchestration database
    _central_url = env("NEON_ORCHESTRATION_URL", default=None)
    if _central_url:
        _central_cfg = _parse_db_url(_central_url)
        _central_cfg["ATOMIC_REQUESTS"] = True
        _central_cfg.setdefault("OPTIONS", {})
        _central_cfg["OPTIONS"]["sslmode"] = "require"
        DATABASES["central_db"] = _central_cfg
    else:
        DATABASES["central_db"] = _default_cfg.copy()

    # Set default to accounts if available
    _accounts_url = env("NEON_ACCOUNTS_URL", default=None)
    if _accounts_url:
        _accounts_cfg = _parse_db_url(_accounts_url)
        _accounts_cfg["ATOMIC_REQUESTS"] = True
        _accounts_cfg.setdefault("OPTIONS", {})
        _accounts_cfg["OPTIONS"]["sslmode"] = "require"
        DATABASES["default"] = _accounts_cfg

elif USE_SINGLE_DATABASE:
    # ── Single-database mode ─────────────────────────────────────────────────
    # All subsystem aliases and central_db share the same physical database.
    for _, _alias in _SUBSYSTEM_DB_SPECS:
        DATABASES[_alias] = _default_cfg.copy()
    DATABASES["central_db"] = _default_cfg.copy()
else:
    # ── Multi-database mode ──────────────────────────────────────────────────
    # Each subsystem reads its own *_DATABASE_URL; falls back to DATABASE_URL.
    for _prefix, _alias in _SUBSYSTEM_DB_SPECS:
        _cfg = _load_db(f"{_prefix}_DATABASE_URL", fallback_url=_default_url)
        _cfg["ATOMIC_REQUESTS"] = True
        DATABASES[_alias] = _cfg

    _central_cfg = _load_db("CENTRAL_DATABASE_URL", fallback_url=_default_url)
    _central_cfg["ATOMIC_REQUESTS"] = True
    DATABASES["central_db"] = _central_cfg

# ── PostgreSQL SSL in production ─────────────────────────────────────────────
if not DEBUG:
    for _alias, _db_cfg in DATABASES.items():
        if "postgresql" in _db_cfg.get("ENGINE", ""):
            _db_cfg.setdefault("OPTIONS", {})
            _db_cfg["OPTIONS"]["sslmode"] = env("DB_SSLMODE", default="require")

# Router selection based on database mode
if USE_NEON_POSTGRES:
    # Neon mode uses multi-database routing
    DATABASE_ROUTERS = ["forgeforth.db_router.ForgeForthDBRouter"]
elif USE_SINGLE_DATABASE:
    DATABASE_ROUTERS = ["forgeforth.db_router.SingleDBRouter"]
else:
    DATABASE_ROUTERS = ["forgeforth.db_router.ForgeForthDBRouter"]

# -------------------------------------------------------
# Cache (falls back to local memory if Redis is not available)
# -------------------------------------------------------
_cache_url = env("CACHE_URL", default="locmemcache://")

# Support for Redis SSL (rediss://) in production
if _cache_url.startswith(("redis://", "rediss://")):
    try:
        import redis as _redis

        # Convert to SSL URL in production if not already
        if not DEBUG and _cache_url.startswith("redis://"):
            _use_ssl = env.bool("REDIS_SSL", default=False)
            if _use_ssl:
                _cache_url = _cache_url.replace("redis://", "rediss://", 1)

        _redis_kwargs = {"socket_connect_timeout": 1}
        if _cache_url.startswith("rediss://"):
            import ssl
            _redis_kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED

        _r = _redis.from_url(_cache_url, **_redis_kwargs)
        _r.ping()

        CACHES = {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": _cache_url,
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "CONNECTION_POOL_KWARGS": {
                        "ssl_cert_reqs": None if DEBUG else "required",
                    } if _cache_url.startswith("rediss://") else {},
                },
            }
        }
    except Exception:
        CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# -------------------------------------------------------
# Auth
# -------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# -------------------------------------------------------
# REST Framework
# -------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
}

# -------------------------------------------------------
# JWT
# -------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# -------------------------------------------------------
# CORS & CSRF
# -------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://localhost:8000", "http://0.0.0.0:9880"]
)
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:8000", "http://0.0.0.0:9880"]
)
CORS_ALLOW_CREDENTIALS = True

# -------------------------------------------------------
# Static & Media
# -------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Use manifest storage in production only — avoids collectstatic requirement in dev
if DEBUG:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Serve website static files at /static/css/, /static/js/, /static/images/
# matching the hardcoded paths used in the Jinja2 templates
STATICFILES_DIRS = [
    BASE_DIR / "website" / "static" / "website",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# -------------------------------------------------------
# Secure Storage Service Settings
# -------------------------------------------------------
# Root directory for encrypted file storage (MUST be outside web root)
SECURE_STORAGE_ROOT = BASE_DIR / "secure_storage"
# Maximum file size (50MB default)
STORAGE_MAX_FILE_SIZE = 50 * 1024 * 1024
# Default signed URL expiry (7 days)
STORAGE_URL_EXPIRY_HOURS = 24 * 7
# Encryption key (set in .env for production)
STORAGE_ENCRYPTION_KEY = env("STORAGE_ENCRYPTION_KEY", default=None)
# Signing key for URLs (set in .env for production)
STORAGE_SIGNING_KEY = env("STORAGE_SIGNING_KEY", default=None)

# Allow larger form data for blog posts that may contain embedded images
# 20 MB — images should be uploaded separately via /api/blog/upload/
# but this covers the HTML content field with possible inline images
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

USE_S3 = env("USE_S3")
if USE_S3:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="forgeforth-media")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="af-south-1")
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = "private"

# -------------------------------------------------------
# Email
# -------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="mail.forgeforthafrica.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="mailer@forgeforthafrica.com")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="ForgeForth Africa <mailer@forgeforthafrica.com>")
CONTACT_EMAIL = env("CONTACT_EMAIL", default="info@forgeforthafrica.com")

# -------------------------------------------------------
# Celery (falls back to synchronous execution if Redis is unavailable)
# -------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="django-db")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Johannesburg"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Orchestration periodic tasks
from celery.schedules import crontab  # noqa: E402
CELERY_BEAT_SCHEDULE = {
    # Re-queue failed sync events every 5 minutes
    "orchestration-retry-failed": {
        "task": "orchestration.retry_failed_events",
        "schedule": 300,   # every 5 minutes
    },
    # Full nightly sync at 02:00 Africa/Johannesburg
    "orchestration-nightly-full-sync": {
        "task": "orchestration.nightly_full_sync",
        "schedule": crontab(hour=2, minute=0),
    },
}

# If broker is unreachable, tasks run synchronously in-process
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True
if CELERY_BROKER_URL.startswith("redis://"):
    try:
        import redis as _redis_check
        _rc = _redis_check.from_url(CELERY_BROKER_URL, socket_connect_timeout=1)
        _rc.ping()
    except Exception:
        CELERY_TASK_ALWAYS_EAGER = True

# -------------------------------------------------------
# API Docs
# -------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "ForgeForth Africa API",
    "DESCRIPTION": "Enterprise Talent Infrastructure Platform — API Reference",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CONTACT": {"email": "api@forgeforthafrica.com"},
    "TAGS": [
        {"name": "auth", "description": "Authentication & Identity"},
        {"name": "profiles", "description": "Talent Profiles"},
        {"name": "organizations", "description": "Organizations & Opportunities"},
        {"name": "applications", "description": "Applications & Workflow"},
        {"name": "matching", "description": "Matching Engine"},
        {"name": "intelligence", "description": "Talent Intelligence"},
        {"name": "communications", "description": "Notifications & Messaging"},
        {"name": "analytics", "description": "Analytics & Reporting"},
    ],
}

# -------------------------------------------------------
# Internationalisation
# -------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------
# Security (production only)
# -------------------------------------------------------
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = "DENY"

# -------------------------------------------------------
# Logging
# -------------------------------------------------------
os.makedirs(BASE_DIR / "logs", exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(BASE_DIR / "logs" / "forgeforth.log"),
            "maxBytes": 5 * 1024 * 1024,   # 5 MB per file
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.security": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        "forgeforth": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}

# -------------------------------------------------------
# Sentry
# -------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.2,
        environment="production",
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------
# Secure Storage Service Configuration
# -------------------------------------------------------
# Storage root - MUST be outside web root for security
SECURE_STORAGE_ROOT = BASE_DIR / "secure_storage"

# Maximum file size (50MB)
STORAGE_MAX_FILE_SIZE = 50 * 1024 * 1024

# Signed URL default expiry (7 days)
STORAGE_URL_EXPIRY_HOURS = 24 * 7

# URL signing key (uses SECRET_KEY by default)
STORAGE_SIGNING_KEY = env("STORAGE_SIGNING_KEY", default=SECRET_KEY)

# Encryption key for stored files (optional)
STORAGE_ENCRYPTION_KEY = env("STORAGE_ENCRYPTION_KEY", default="")

# Default quota per user (1GB)
STORAGE_DEFAULT_USER_QUOTA = 1024 * 1024 * 1024

# Default quota per organization (10GB)
STORAGE_DEFAULT_ORG_QUOTA = 10 * 1024 * 1024 * 1024

# Maximum files per user
STORAGE_MAX_FILES_PER_USER = 10000

# CDN configuration (optional)
STORAGE_CDN_ENABLED = env.bool("STORAGE_CDN_ENABLED", default=False)
STORAGE_CDN_URL = env("STORAGE_CDN_URL", default="")

