# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Talent Portal Auth Client
=============================================
Handles authentication with the central Auth Service.
"""
import os
import logging
from typing import Dict, Any, Optional
from functools import wraps
import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse

from .config import config

logger = logging.getLogger('talent_portal.auth')


class AuthClient:
    """Client for communicating with Auth Service."""

    def __init__(self):
        self.base_url = config.AUTH_SERVICE_URL.rstrip('/')
        self.timeout = 10

    async def register(
        self,
        email: str,
        password: str,
        first_name: str = '',
        last_name: str = '',
        phone_number: str = '',
        consent_privacy: bool = False,
        consent_terms: bool = False,
        consent_marketing: bool = False
    ) -> Dict[str, Any]:
        """Register a new talent."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/register",
                json={
                    'email': email,
                    'password': password,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone_number': phone_number,
                    'role': 'talent',  # Always talent for this portal
                    'consent_privacy': consent_privacy,
                    'consent_terms': consent_terms,
                    'consent_marketing': consent_marketing
                },
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def login(self, email: str, password: str, otp_code: str = None) -> Dict[str, Any]:
        """Login and get tokens."""
        async with httpx.AsyncClient() as client:
            data = {'email': email, 'password': password}
            if otp_code:
                data['otp_code'] = otp_code

            response = await client.post(
                f"{self.base_url}/api/auth/login",
                json=data,
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def logout(self, refresh_token: str) -> Dict[str, Any]:
        """Logout and invalidate token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/logout",
                json={'refresh_token': refresh_token},
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def validate_token(self, token: str) -> Dict[str, Any]:
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

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/token/refresh",
                json={'refresh_token': refresh_token},
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def get_current_user(self, access_token: str) -> Dict[str, Any]:
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

    async def forgot_password(self, email: str) -> Dict[str, Any]:
        """Request password reset."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/password/forgot",
                json={'email': email},
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def reset_password(self, token: str, new_password: str) -> Dict[str, Any]:
        """Reset password with token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/password/reset",
                json={'token': token, 'new_password': new_password},
                timeout=self.timeout
            )
            return response.json(), response.status_code

    async def verify_email(self, token: str) -> Dict[str, Any]:
        """Verify email with token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/verify-email",
                json={'token': token},
                timeout=self.timeout
            )
            return response.json(), response.status_code


# Singleton instance
auth_client = AuthClient()


def get_session_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get user from session."""
    return request.session.get('user')


def get_access_token(request: Request) -> Optional[str]:
    """Get access token from session."""
    return request.session.get('access_token')


def get_refresh_token(request: Request) -> Optional[str]:
    """Get refresh token from session."""
    return request.session.get('refresh_token')


def login_required(func):
    """Decorator to require login for a route."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_session_user(request)
        access_token = get_access_token(request)

        if not user or not access_token:
            # Store intended destination
            request.session['next'] = str(request.url)
            return RedirectResponse(url='/auth/login', status_code=302)

        # Validate token is still valid
        try:
            validation = await auth_client.validate_token(access_token)
            if not validation or not validation.get('valid'):
                # Try to refresh
                refresh_token = get_refresh_token(request)
                if refresh_token:
                    result, status = await auth_client.refresh_token(refresh_token)
                    if status == 200 and result.get('access'):
                        request.session['access_token'] = result['access']
                    else:
                        # Refresh failed, require re-login
                        request.session.clear()
                        return RedirectResponse(url='/auth/login', status_code=302)
                else:
                    request.session.clear()
                    return RedirectResponse(url='/auth/login', status_code=302)
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            # On error, allow through but log it
            pass

        # Add user to request state
        request.state.user = user
        request.state.access_token = access_token

        return await func(request, *args, **kwargs)

    return wrapper


def verified_email_required(func):
    """Decorator to require verified email."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_session_user(request)

        if not user:
            return RedirectResponse(url='/auth/login', status_code=302)

        if not user.get('is_verified'):
            return RedirectResponse(url='/auth/verify-email-required', status_code=302)

        return await func(request, *args, **kwargs)

    return wrapper

