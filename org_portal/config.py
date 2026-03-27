# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organization Portal Configuration
=====================================================
"""
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env')


class Config:
    """Base configuration."""

    # Service Info
    SERVICE_NAME = "org-portal"
    SERVICE_VERSION = "1.0.0"

    # Server
    HOST = os.getenv('ORG_PORTAL_HOST', '0.0.0.0')
    PORT = int(os.getenv('ORG_PORTAL_PORT', 9004))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')

    # Auth Service
    AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:9002')

    # Main API Service (for organizations, opportunities, applications, etc.)
    API_SERVICE_URL = os.getenv('API_SERVICE_URL', 'http://localhost:9880')
    API_BASE_URL = API_SERVICE_URL + '/api/v1'

    # Database (for local caching/session if needed)
    DATABASE_URL = os.getenv('ORG_DATABASE_URL', 'sqlite:///org_portal.sqlite3')

    # Session
    SESSION_SECRET = os.getenv('SESSION_SECRET', SECRET_KEY)
    SESSION_EXPIRE_MINUTES = int(os.getenv('SESSION_EXPIRE_MINUTES', 60 * 24))  # 24 hours

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:9004,http://localhost:9880').split(',')

    # Static Files
    STATIC_DIR = Path(__file__).parent / 'static'
    TEMPLATES_DIR = Path(__file__).parent / 'templates'

    # Logging
    LOG_LEVEL = os.getenv('ORG_LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('ORG_LOG_FILE', str(BASE_DIR / 'logs' / 'org_portal.log'))

    # Site Info
    SITE_NAME = "ForgeForth Africa - Organization Portal"
    SITE_URL = os.getenv('ORG_PORTAL_URL', f'http://localhost:{PORT}')
    MAIN_SITE_URL = os.getenv('SITE_URL', 'http://localhost:9880')


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = 'WARNING'


def get_config():
    env = os.getenv('DJANGO_ENV', 'development').lower()
    configs = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
    }
    return configs.get(env, DevelopmentConfig)()


config = get_config()

