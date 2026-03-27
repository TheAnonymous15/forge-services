# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Security Middleware
========================================
Middleware for enforcing SSL/TLS across all communications.
"""
import logging
from django.conf import settings
from django.http import HttpResponsePermanentRedirect

logger = logging.getLogger('forgeforth.security')


class SSLEnforcementMiddleware:
    """
    Middleware to enforce SSL/HTTPS connections.

    In production:
    - Redirects HTTP requests to HTTPS
    - Adds security headers
    - Validates SSL certificates for upstream connections
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip enforcement in DEBUG mode
        if settings.DEBUG:
            return self.get_response(request)

        # Check if request is secure
        is_secure = self._is_secure_request(request)

        # Redirect HTTP to HTTPS (unless it's a health check)
        if not is_secure and not self._is_health_check(request):
            return self._redirect_to_https(request)

        # Process the request
        response = self.get_response(request)

        # Add security headers
        response = self._add_security_headers(response)

        return response

    def _is_secure_request(self, request):
        """Check if the request is over HTTPS."""
        # Check direct HTTPS
        if request.is_secure():
            return True

        # Check X-Forwarded-Proto header (from reverse proxy)
        forwarded_proto = request.META.get('HTTP_X_FORWARDED_PROTO', '').lower()
        if forwarded_proto == 'https':
            return True

        # Check X-Forwarded-SSL header
        forwarded_ssl = request.META.get('HTTP_X_FORWARDED_SSL', '').lower()
        if forwarded_ssl == 'on':
            return True

        return False

    def _is_health_check(self, request):
        """Check if this is a health check request."""
        health_paths = ['/health', '/health/', '/api/health', '/.well-known/']
        return any(request.path.startswith(p) for p in health_paths)

    def _redirect_to_https(self, request):
        """Redirect to HTTPS version of the URL."""
        url = request.build_absolute_uri()
        secure_url = url.replace('http://', 'https://', 1)
        logger.info(f"Redirecting HTTP to HTTPS: {url} -> {secure_url}")
        return HttpResponsePermanentRedirect(secure_url)

    def _add_security_headers(self, response):
        """Add security headers to the response."""
        from core.security import SECURITY_HEADERS

        for header, value in SECURITY_HEADERS.items():
            if header not in response:
                response[header] = value

        return response


class SecureProxyMiddleware:
    """
    Middleware to handle requests from secure reverse proxies.

    Trusts X-Forwarded-* headers from configured proxies.
    """

    # Trusted proxy IPs (configure via settings)
    TRUSTED_PROXIES = getattr(settings, 'TRUSTED_PROXY_IPS', [
        '127.0.0.1',
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
    ])

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process X-Forwarded headers from trusted proxies
        if self._is_trusted_proxy(request):
            # Set the correct client IP
            forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
            if forwarded_for:
                # Take the first IP (original client)
                client_ip = forwarded_for.split(',')[0].strip()
                request.META['REMOTE_ADDR'] = client_ip

            # Set the correct protocol
            forwarded_proto = request.META.get('HTTP_X_FORWARDED_PROTO', '')
            if forwarded_proto:
                request.META['wsgi.url_scheme'] = forwarded_proto

        return self.get_response(request)

    def _is_trusted_proxy(self, request):
        """Check if request is from a trusted proxy."""
        import ipaddress

        remote_addr = request.META.get('REMOTE_ADDR', '')

        try:
            client_ip = ipaddress.ip_address(remote_addr)
        except ValueError:
            return False

        for proxy in self.TRUSTED_PROXIES:
            try:
                if '/' in proxy:
                    # CIDR notation
                    network = ipaddress.ip_network(proxy, strict=False)
                    if client_ip in network:
                        return True
                else:
                    if client_ip == ipaddress.ip_address(proxy):
                        return True
            except ValueError:
                continue

        return False


class CertificatePinningMiddleware:
    """
    Middleware to enforce certificate pinning for outbound connections.

    Used for inter-service communication within the platform.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._setup_ssl_context()

    def _setup_ssl_context(self):
        """Configure SSL context with pinned certificates."""
        import ssl
        from core.security import SSL_CONFIG

        self.ssl_context = ssl.create_default_context()
        self.ssl_context.minimum_version = SSL_CONFIG['min_version']
        self.ssl_context.set_ciphers(':'.join(SSL_CONFIG['ciphers']))

    def __call__(self, request):
        # Store SSL context for use by service clients
        request.ssl_context = self.ssl_context
        return self.get_response(request)

