# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Core Views
===============================
Health check and diagnostic endpoints.
"""
import ssl
from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache
from django.conf import settings


def health_check(request):
    """
    Basic health check endpoint.
    Returns overall system health status.
    """
    checks = {
        'status': 'healthy',
        'ssl_enforced': not settings.DEBUG,
        'wss_required': getattr(settings, 'WEBSOCKET_SSL_REQUIRED', not settings.DEBUG),
    }

    # Check database
    try:
        connections['default'].ensure_connection()
        checks['database'] = 'connected'
    except Exception as e:
        checks['database'] = 'error'
        checks['status'] = 'degraded'

    # Check cache
    try:
        cache.set('_health', '1', 5)
        if cache.get('_health') == '1':
            checks['cache'] = 'connected'
        else:
            checks['cache'] = 'error'
    except Exception:
        checks['cache'] = 'error'
        checks['status'] = 'degraded'

    status_code = 200 if checks['status'] == 'healthy' else 503
    return JsonResponse(checks, status=status_code)


def database_health(request):
    """
    Database health check with SSL status.
    """
    result = {
        'status': 'unknown',
        'engine': 'unknown',
        'ssl_enabled': False,
    }

    try:
        connection = connections['default']
        connection.ensure_connection()

        result['status'] = 'connected'
        result['engine'] = connection.vendor

        # Check SSL for PostgreSQL
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("SELECT ssl_is_used()")
                row = cursor.fetchone()
                result['ssl_enabled'] = row[0] if row else False

        # Check database options
        db_options = settings.DATABASES.get('default', {}).get('OPTIONS', {})
        result['ssl_mode'] = db_options.get('sslmode', 'not set')

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)

    status_code = 200 if result['status'] == 'connected' else 503
    return JsonResponse(result, status=status_code)


def cache_health(request):
    """
    Cache health check with connection info.
    """
    result = {
        'status': 'unknown',
        'backend': 'unknown',
        'ssl_enabled': False,
    }

    try:
        # Test cache operations
        cache.set('_health_test', 'test_value', 10)
        retrieved = cache.get('_health_test')
        cache.delete('_health_test')

        if retrieved == 'test_value':
            result['status'] = 'healthy'
        else:
            result['status'] = 'degraded'

        # Get backend info
        result['backend'] = cache.__class__.__name__

        # Check if using Redis with SSL
        cache_url = getattr(settings, '_cache_url', '')
        result['ssl_enabled'] = 'rediss://' in str(cache_url)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)

    status_code = 200 if result['status'] == 'healthy' else 503
    return JsonResponse(result, status=status_code)


def ssl_status(request):
    """
    SSL/TLS configuration status.
    """
    result = {
        'https_enforced': not settings.DEBUG and getattr(settings, 'SECURE_SSL_REDIRECT', False),
        'hsts_enabled': getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0,
        'hsts_seconds': getattr(settings, 'SECURE_HSTS_SECONDS', 0),
        'secure_cookies': getattr(settings, 'SESSION_COOKIE_SECURE', False),
        'csrf_secure': getattr(settings, 'CSRF_COOKIE_SECURE', False),
        'wss_required': getattr(settings, 'WEBSOCKET_SSL_REQUIRED', not settings.DEBUG),
        'min_tls_version': 'TLS 1.2',
        'request_is_secure': request.is_secure(),
        'forwarded_proto': request.META.get('HTTP_X_FORWARDED_PROTO', 'none'),
    }

    # Check current connection
    if request.is_secure():
        result['current_connection'] = 'secure (HTTPS)'
    elif request.META.get('HTTP_X_FORWARDED_PROTO') == 'https':
        result['current_connection'] = 'secure (via proxy)'
    else:
        result['current_connection'] = 'insecure (HTTP)'

    # SSL context info
    try:
        ctx = ssl.create_default_context()
        result['ssl_library'] = ssl.OPENSSL_VERSION
        result['supported_protocols'] = {
            'TLSv1': hasattr(ssl, 'TLSVersion') and ssl.TLSVersion.TLSv1 is not None,
            'TLSv1.1': hasattr(ssl, 'TLSVersion') and ssl.TLSVersion.TLSv1_1 is not None,
            'TLSv1.2': hasattr(ssl, 'TLSVersion') and ssl.TLSVersion.TLSv1_2 is not None,
            'TLSv1.3': hasattr(ssl, 'TLSVersion') and hasattr(ssl.TLSVersion, 'TLSv1_3'),
        }
    except Exception as e:
        result['ssl_error'] = str(e)

    return JsonResponse(result)

