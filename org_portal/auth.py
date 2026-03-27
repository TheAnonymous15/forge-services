# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organization Portal Auth Client
===================================================
Handles authentication with the central Auth Service.
"""
import logging
from typing import Dict, Any, Optional
from functools import wraps
import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse

from .config import config

logger = logging.getLogger('org_portal.auth')


class AuthClient:
    """Client for communicating with Auth Service."""

    def __init__(self):
        self.base_url = config.AUTH_SERVICE_URL.rstrip('/')
        self.timeout = 10

    async def register(
        self,
        email: str,
        password: str,
        role: str = 'organization',
        first_name: str = '',
        phone_number: str = '',
        consent_privacy: bool = False,
        consent_terms: bool = False,
        extra_data: Dict = None
    ) -> tuple:
        """Register a new organization user."""
        async with httpx.AsyncClient() as client:
            data = {
                'email': email,
                'password': password,
                'first_name': first_name,
                'phone_number': phone_number,
                'role': role,
                'consent_privacy': consent_privacy,
                'consent_terms': consent_terms
            }
            if extra_data:
                data.update(extra_data)

            response = await client.post(
                f"{self.base_url}/api/auth/register",
                json=data,
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def login(self, email: str, password: str, role: str = 'organization') -> tuple:
        """Login and get tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/login",
                json={'email': email, 'password': password, 'role': role},
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def logout(self, refresh_token: str) -> tuple:
        """Logout and invalidate token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/logout",
                json={'refresh_token': refresh_token},
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def validate_token(self, token: str) -> Optional[Dict]:
        """Validate access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/token/validate",
                json={'token': token, 'token_type': 'access'},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return None

    async def refresh_token(self, refresh_token: str) -> tuple:
        """Refresh access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/token/refresh",
                json={'refresh_token': refresh_token},
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def get_current_user(self, access_token: str) -> Optional[Dict]:
        """Get current user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/auth/me",
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return None


# Singleton instance
auth_client = AuthClient()


def get_session_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get user from session."""
    return request.session.get('user')


def get_access_token(request: Request) -> Optional[str]:
    """Get access token from session."""
    return request.session.get('access_token')


def login_required(func):
    """Decorator to require login for routes."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_session_user(request)
        if not user:
            redirect_url = f"/auth/login?next={request.url.path}"
            return RedirectResponse(url=redirect_url, status_code=302)

        # Validate token is still valid
        access_token = get_access_token(request)
        if access_token:
            try:
                valid = await auth_client.validate_token(access_token)
                if not valid:
                    # Try to refresh
                    refresh_token = request.session.get('refresh_token')
                    if refresh_token:
                        result, status = await auth_client.refresh_token(refresh_token)
                        if status == 200 and result.get('access'):
                            request.session['access_token'] = result['access']
                        else:
                            # Refresh failed, logout
                            request.session.clear()
                            return RedirectResponse(url="/auth/login", status_code=302)
            except Exception as e:
                logger.error(f"Token validation error: {e}")

        return await func(request, *args, **kwargs)
    return wrapper

