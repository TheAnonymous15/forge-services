# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Middleware
===========================================
Django middleware for authenticating requests via the Auth Service.
"""
import logging
from django.http import JsonResponse
from django.conf import settings

from auth_service.client import AuthClient, AuthClientError

logger = logging.getLogger('forgeforth.auth')


class AuthServiceMiddleware:
    """
    Middleware that validates JWT tokens with the Auth Service.

    For API endpoints (starting with /api/), this middleware:
    1. Extracts the Bearer token from the Authorization header
    2. Validates the token with the Auth Service
    3. Attaches user info to the request

    Usage in settings.py:
        MIDDLEWARE = [
            ...
            'core.middleware.AuthServiceMiddleware',
            ...
        ]
    """

    # Paths that don't require authentication
    EXEMPT_PATHS = [
        '/api/auth/',          # Auth service handles its own auth
        '/api/v1/auth/',       # Legacy auth endpoints
        '/api/schema/',        # API docs
        '/api/docs/',          # Swagger UI
        '/api/redoc/',         # Redoc
        '/health',             # Health check
        '/api/health',         # API health check
    ]

    # Paths that allow optional authentication
    OPTIONAL_AUTH_PATHS = [
        '/api/v1/profiles/',   # Public profiles
        '/api/v1/jobs/',       # Public job listings
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.auth_client = AuthClient()

    def __call__(self, request):
        # Skip non-API paths
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # Skip exempt paths
        for exempt in self.EXEMPT_PATHS:
            if request.path.startswith(exempt):
                return self.get_response(request)

        # Check for Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header:
            # Check if path allows optional auth
            for optional in self.OPTIONAL_AUTH_PATHS:
                if request.path.startswith(optional):
                    request.auth_user = None
                    return self.get_response(request)

            return JsonResponse({
                'error': 'Authorization header required',
                'code': 'missing_auth'
            }, status=401)

        # Extract token
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Invalid authorization header format',
                'code': 'invalid_auth_format'
            }, status=401)

        token = auth_header[7:]  # Remove 'Bearer ' prefix

        # Validate token with Auth Service
        try:
            result = self.auth_client.validate_token(token, 'access')

            if not result.get('valid'):
                return JsonResponse({
                    'error': 'Invalid token',
                    'code': 'invalid_token'
                }, status=401)

            # Attach user info to request
            request.auth_user = {
                'id': result['user_id'],
                'email': result['email'],
                'role': result['role'],
                'is_verified': result['is_verified'],
                'permissions': result.get('permissions', [])
            }

        except AuthClientError as e:
            logger.warning(f"Auth validation failed: {e.message}")
            return JsonResponse({
                'error': e.message,
                'code': e.code
            }, status=e.status_code)

        except Exception as e:
            logger.error(f"Auth service error: {e}")
            return JsonResponse({
                'error': 'Authentication service unavailable',
                'code': 'auth_unavailable'
            }, status=503)

        return self.get_response(request)


def require_auth(view_func):
    """
    Decorator to require authentication on a view.

    Usage:
        @require_auth
        def my_view(request):
            user = request.auth_user
            ...
    """
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'auth_user') or request.auth_user is None:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'auth_required'
            }, status=401)

        return view_func(request, *args, **kwargs)

    return wrapper


def require_permission(permission):
    """
    Decorator to require a specific permission.

    Usage:
        @require_permission('jobs:write')
        def create_job(request):
            ...
    """
    def decorator(view_func):
        from functools import wraps

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'auth_user') or request.auth_user is None:
                return JsonResponse({
                    'error': 'Authentication required',
                    'code': 'auth_required'
                }, status=401)

            permissions = request.auth_user.get('permissions', [])

            if '*' not in permissions and permission not in permissions:
                return JsonResponse({
                    'error': 'Permission denied',
                    'code': 'forbidden',
                    'required_permission': permission
                }, status=403)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def require_role(*roles):
    """
    Decorator to require specific user roles.

    Usage:
        @require_role('admin', 'staff')
        def admin_view(request):
            ...
    """
    def decorator(view_func):
        from functools import wraps

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'auth_user') or request.auth_user is None:
                return JsonResponse({
                    'error': 'Authentication required',
                    'code': 'auth_required'
                }, status=401)

            user_role = request.auth_user.get('role')

            if user_role not in roles:
                return JsonResponse({
                    'error': 'Access denied for this role',
                    'code': 'forbidden',
                    'user_role': user_role,
                    'allowed_roles': list(roles)
                }, status=403)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def require_verified_email(view_func):
    """
    Decorator to require verified email.

    Usage:
        @require_verified_email
        def sensitive_view(request):
            ...
    """
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'auth_user') or request.auth_user is None:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'auth_required'
            }, status=401)

        if not request.auth_user.get('is_verified'):
            return JsonResponse({
                'error': 'Email verification required',
                'code': 'email_not_verified'
            }, status=403)

        return view_func(request, *args, **kwargs)

    return wrapper

