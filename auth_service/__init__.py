# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service
================================
Central authentication service with mutual authentication.

Security Architecture:
1. All requests from services MUST be signed
2. All responses from auth service ARE signed
3. Services MUST verify response signatures before trusting data
4. Post-quantum hybrid algorithms available for future-proofing
5. Request-response binding prevents replay attacks

Port: 9002 (configurable)

Usage - Auth Service (Server):
    python start_auth.py

Usage - Client Service:
    from auth_service.client import AuthClient, SecurityLevel

    client = AuthClient(
        service_name='talent',
        api_key='your-api-key',
        hmac_key='shared-hmac-key',
        expected_service_id='ff-auth-svc-001'
    )

    result = await client.login(email, password, role='talent')

    # CRITICAL: Always check verification status!
    if not result.verified:
        raise SecurityError("Response not verified - do not trust!")

    if result.success:
        user = result.user
"""
from .config import config, get_config

# Import security components
from .security import (
    SignatureError,
    SecurityLevel,
    SignedRequest,
    SignedResponse,
    MutualAuthManager,
    auth_manager,
    sign_request,
    verify_request,
    sign_response,
    verify_response,
    security_manager,
)

# Import client
from .client import (
    AuthClient,
    AuthResponse,
    RequestSigner,
    ResponseVerifier,
    verify_auth_response,
)

__version__ = '2.0.0'
__all__ = [
    # Config
    'config',
    'get_config',

    # Security
    'SignatureError',
    'SecurityLevel',
    'SignedRequest',
    'SignedResponse',
    'MutualAuthManager',
    'auth_manager',
    'sign_request',
    'verify_request',
    'sign_response',
    'verify_response',
    'security_manager',

    # Client
    'AuthClient',
    'AuthResponse',
    'RequestSigner',
    'ResponseVerifier',
    'verify_auth_response',
]

