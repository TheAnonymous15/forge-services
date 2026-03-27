# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Security Configuration
===========================================
SSL, WebSocket security, and encryption settings.
All communications use TLS 1.2+ and secure WebSockets (WSS).
"""
from django.conf import settings
import ssl


# =============================================================================
# SSL/TLS CONFIGURATION
# =============================================================================

SSL_CONFIG = {
    # Minimum TLS version (TLS 1.2+)
    'min_version': ssl.TLSVersion.TLSv1_2,

    # Preferred cipher suites (in order of preference)
    'ciphers': [
        'ECDHE-ECDSA-AES256-GCM-SHA384',
        'ECDHE-RSA-AES256-GCM-SHA384',
        'ECDHE-ECDSA-CHACHA20-POLY1305',
        'ECDHE-RSA-CHACHA20-POLY1305',
        'ECDHE-ECDSA-AES128-GCM-SHA256',
        'ECDHE-RSA-AES128-GCM-SHA256',
    ],

    # Certificate verification
    'verify_mode': ssl.CERT_REQUIRED,
    'check_hostname': True,
}


def create_ssl_context(purpose=ssl.Purpose.SERVER_AUTH):
    """
    Create a secure SSL context for outbound connections.
    Used for inter-service communication and external API calls.
    """
    ctx = ssl.create_default_context(purpose)
    ctx.minimum_version = SSL_CONFIG['min_version']
    ctx.set_ciphers(':'.join(SSL_CONFIG['ciphers']))
    ctx.check_hostname = SSL_CONFIG['check_hostname']
    ctx.verify_mode = SSL_CONFIG['verify_mode']
    return ctx


# =============================================================================
# WEBSOCKET SECURITY
# =============================================================================

WEBSOCKET_CONFIG = {
    # Always use WSS (WebSocket Secure) in production
    'use_ssl': not settings.DEBUG,

    # WebSocket origins allowed
    'allowed_origins': [
        'https://forgeforthafrica.com',
        'https://www.forgeforthafrica.com',
        'https://app.forgeforthafrica.com',
    ],

    # Development origins (only when DEBUG=True)
    'dev_origins': [
        'http://localhost:3000',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ],

    # Connection limits
    'max_connections_per_user': 5,
    'connection_timeout': 30,  # seconds
    'ping_interval': 25,  # seconds
    'ping_timeout': 10,  # seconds

    # Message limits
    'max_message_size': 1024 * 1024,  # 1MB
    'rate_limit': 100,  # messages per minute
}


def get_allowed_websocket_origins():
    """Get list of allowed WebSocket origins based on environment."""
    origins = list(WEBSOCKET_CONFIG['allowed_origins'])
    if settings.DEBUG:
        origins.extend(WEBSOCKET_CONFIG['dev_origins'])
    return origins


# =============================================================================
# DATABASE SSL CONFIGURATION
# =============================================================================

DATABASE_SSL_CONFIG = {
    # PostgreSQL SSL mode
    'sslmode': 'verify-full',  # Strictest mode

    # Certificate paths (configure via environment)
    'sslcert': settings.BASE_DIR / 'certs' / 'client.crt',
    'sslkey': settings.BASE_DIR / 'certs' / 'client.key',
    'sslrootcert': settings.BASE_DIR / 'certs' / 'ca.crt',
}


def get_database_ssl_options(env='production'):
    """
    Get SSL options for database connections.

    In production: Full certificate verification
    In development: SSL required but no cert verification
    """
    if env == 'production':
        return {
            'sslmode': 'verify-full',
            'sslcert': str(DATABASE_SSL_CONFIG['sslcert']),
            'sslkey': str(DATABASE_SSL_CONFIG['sslkey']),
            'sslrootcert': str(DATABASE_SSL_CONFIG['sslrootcert']),
        }
    else:
        return {
            'sslmode': 'require',
        }


# =============================================================================
# REDIS SSL CONFIGURATION
# =============================================================================

REDIS_SSL_CONFIG = {
    # Use TLS for Redis connections
    'ssl': True,
    'ssl_cert_reqs': 'required',
    'ssl_ca_certs': str(settings.BASE_DIR / 'certs' / 'redis-ca.crt'),
}


def get_redis_ssl_url(base_url: str) -> str:
    """
    Convert redis:// URL to rediss:// (SSL) URL.
    """
    if base_url.startswith('redis://'):
        return base_url.replace('redis://', 'rediss://', 1)
    return base_url


# =============================================================================
# INTER-SERVICE COMMUNICATION
# =============================================================================

SERVICE_SSL_CONFIG = {
    # All internal service calls use HTTPS
    'protocol': 'https',

    # Mutual TLS for service-to-service
    'mtls_enabled': True,

    # Service certificates
    'service_cert': settings.BASE_DIR / 'certs' / 'service.crt',
    'service_key': settings.BASE_DIR / 'certs' / 'service.key',
    'ca_bundle': settings.BASE_DIR / 'certs' / 'ca-bundle.crt',

    # Request timeout
    'timeout': 30,

    # Retry configuration
    'max_retries': 3,
    'retry_backoff': 0.5,
}


class SecureServiceClient:
    """
    HTTP client for secure service-to-service communication.
    Always uses HTTPS with certificate verification.
    """

    def __init__(self):
        import httpx

        self.ssl_context = create_ssl_context()
        self.client = httpx.Client(
            verify=self.ssl_context,
            timeout=SERVICE_SSL_CONFIG['timeout'],
        )

    def get(self, url: str, **kwargs):
        """Make secure GET request."""
        return self.client.get(url, **kwargs)

    def post(self, url: str, **kwargs):
        """Make secure POST request."""
        return self.client.post(url, **kwargs)

    def close(self):
        """Close the client."""
        self.client.close()


# =============================================================================
# SECURITY HEADERS
# =============================================================================

SECURITY_HEADERS = {
    # HSTS - Force HTTPS
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',

    # Prevent clickjacking
    'X-Frame-Options': 'DENY',

    # Prevent MIME sniffing
    'X-Content-Type-Options': 'nosniff',

    # XSS Protection
    'X-XSS-Protection': '1; mode=block',

    # Referrer Policy
    'Referrer-Policy': 'strict-origin-when-cross-origin',

    # Content Security Policy
    'Content-Security-Policy': (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss://*.forgeforthafrica.com https://*.forgeforthafrica.com; "
        "frame-ancestors 'none'; "
        "upgrade-insecure-requests;"
    ),

    # Permissions Policy
    'Permissions-Policy': (
        'accelerometer=(), '
        'camera=(), '
        'geolocation=(), '
        'gyroscope=(), '
        'magnetometer=(), '
        'microphone=(), '
        'payment=(), '
        'usb=()'
    ),
}

