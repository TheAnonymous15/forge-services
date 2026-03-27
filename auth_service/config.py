# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Configuration
==============================================
Enterprise-grade configuration for the central authentication service.
"""
import os
import secrets
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env')


class Config:
    """Auth Service Configuration."""

    # Service Info
    SERVICE_NAME = "auth-service"
    SERVICE_VERSION = "2.0.0"
    SERVICE_ID = os.getenv('AUTH_SERVICE_ID', secrets.token_hex(16))

    # Server
    HOST = os.getenv('AUTH_SERVICE_HOST', '0.0.0.0')
    PORT = int(os.getenv('AUTH_SERVICE_PORT', 9002))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    # SSL/TLS Configuration (REQUIRED in production)
    SSL_ENABLED = os.getenv('AUTH_SSL_ENABLED', 'True').lower() == 'true'
    SSL_CERT_FILE = os.getenv('AUTH_SSL_CERT', str(BASE_DIR / 'certs' / 'auth_cert.pem'))
    SSL_KEY_FILE = os.getenv('AUTH_SSL_KEY', str(BASE_DIR / 'certs' / 'auth_key.pem'))
    SSL_CA_FILE = os.getenv('AUTH_SSL_CA', None)  # For client cert verification

    # For development - auto-generate self-signed certs if not present
    AUTO_GENERATE_CERTS = os.getenv('AUTH_AUTO_CERTS', 'True').lower() == 'true'

    # Security Keys
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))

    # HMAC Signing Key - Used to sign all responses
    # This key MUST be shared ONLY with trusted services
    HMAC_SECRET_KEY = os.getenv('AUTH_HMAC_SECRET', os.getenv('SECRET_KEY', secrets.token_hex(32)))

    # Service-to-Service Authentication
    # Each service gets a unique API key to communicate with auth service
    SERVICE_API_KEYS = {
        'website': os.getenv('WEBSITE_AUTH_KEY', secrets.token_hex(32)),
        'admin': os.getenv('ADMIN_AUTH_KEY', secrets.token_hex(32)),
        'talent': os.getenv('TALENT_AUTH_KEY', secrets.token_hex(32)),
        'org': os.getenv('ORG_AUTH_KEY', secrets.token_hex(32)),
    }

    # Database
    DATABASE_URL = os.getenv('AUTH_DATABASE_URL', 'sqlite+aiosqlite:///auth_db.sqlite3')

    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ALGORITHM = 'HS256'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_MINUTES', 15)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_DAYS', 7)))

    # WebSocket Configuration
    WS_HEARTBEAT_INTERVAL = 30  # seconds
    WS_CONNECTION_TIMEOUT = 60  # seconds
    WS_MAX_CONNECTIONS_PER_IP = 10

    # Rate Limiting
    RATE_LIMIT_REQUESTS = 100  # requests per window
    RATE_LIMIT_WINDOW = 60  # seconds

    # Password Policy
    MIN_PASSWORD_LENGTH = 8
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    # Token Expiry
    VERIFICATION_TOKEN_HOURS = 24
    PASSWORD_RESET_TOKEN_HOURS = 1

    # Response Signature Settings
    SIGNATURE_ALGORITHM = 'sha256'
    SIGNATURE_HEADER = 'X-Auth-Signature'
    TIMESTAMP_HEADER = 'X-Auth-Timestamp'
    NONCE_HEADER = 'X-Auth-Nonce'
    SERVICE_ID_HEADER = 'X-Auth-Service-ID'

    # Signature validity window (prevent replay attacks)
    SIGNATURE_VALIDITY_SECONDS = 30

    # CORS (restricted in production)
    CORS_ORIGINS = os.getenv('AUTH_CORS_ORIGINS', 'https://localhost:9003,https://localhost:9004').split(',')

    # Logging
    LOG_LEVEL = os.getenv('AUTH_LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('AUTH_LOG_FILE', str(BASE_DIR / 'logs' / 'auth_service.log'))

    # Sub-service endpoints (internal routing)
    SUB_SERVICES = {
        'talent': {
            'name': 'Talent Auth Handler',
            'enabled': True,
        },
        'employer': {
            'name': 'Employer Auth Handler',
            'enabled': True,
        },
        'org_admin': {
            'name': 'Organization Admin Auth Handler',
            'enabled': True,
        },
        'admin': {
            'name': 'System Admin Auth Handler',
            'enabled': True,
        },
    }


class DevelopmentConfig(Config):
    DEBUG = True
    SSL_ENABLED = False  # Disable SSL for local dev
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    DEBUG = False
    SSL_ENABLED = True
    LOG_LEVEL = 'WARNING'
    AUTO_GENERATE_CERTS = False  # Must provide real certs


def get_config():
    env = os.getenv('DJANGO_ENV', 'development').lower()
    return ProductionConfig() if env == 'production' else DevelopmentConfig()


config = get_config()

