# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Client Library (Mutual Authentication)
===============================================================
Secure client library with mutual authentication support.

Security Features:
1. All requests are cryptographically signed
2. All responses are verified before processing
3. Request-response binding prevents replay attacks
4. Post-quantum hybrid signatures available
5. Automatic rejection of unsigned/invalid responses

Usage:
    from auth_service.client import AuthClient

    client = AuthClient(
        service_name='talent',
        api_key='your-service-api-key',
        hmac_key='shared-hmac-key',
        expected_service_id='ff-auth-svc-001'
    )

    # All requests are signed, all responses are verified
    result = await client.login(email, password)

    if not result.verified:
        # Response signature invalid - DO NOT TRUST
        raise SecurityError("Response verification failed")

    if result.success:
        user = result.user
"""
import os
import ssl
import json
import hmac
import hashlib
import secrets
import asyncio
import logging
import struct
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from contextlib import asynccontextmanager
from enum import Enum

import httpx

logger = logging.getLogger('auth_client')


class SecurityLevel(Enum):
    """Security levels for requests."""
    STANDARD = "standard"
    HIGH = "high"
    QUANTUM_SAFE = "quantum"


@dataclass
class AuthResponse:
    """
    Verified authentication response.

    IMPORTANT: Always check `verified` before trusting the response!
    """
    raw: Dict[str, Any]
    data: Dict[str, Any]
    verified: bool
    success: bool
    error: Optional[str] = None
    request_id: Optional[str] = None

    @property
    def user(self) -> Optional[Dict[str, Any]]:
        return self.data.get('user')

    @property
    def requires_2fa(self) -> bool:
        return self.data.get('requires_2fa', False)

    @property
    def is_authentic(self) -> bool:
        """Returns True only if response is verified AND successful."""
        return self.verified and self.success


class PostQuantumSimulator:
    """Post-quantum signature simulator (must match server implementation)."""

    @staticmethod
    def derive_pq_key(master_key: bytes, context: str) -> bytes:
        info = context.encode('utf-8')
        key_material = b""
        for i in range(4):
            round_input = master_key + info + struct.pack('>I', i)
            key_material += hashlib.sha512(round_input).digest()
        return key_material[:256]

    @staticmethod
    def pq_sign(message: bytes, key: bytes) -> str:
        classical_sig = hmac.new(key[:64], message, hashlib.sha512).digest()
        pq_components = []
        for i in range(4):
            chunk_key = key[64 + i*48:64 + (i+1)*48]
            if len(chunk_key) < 48:
                chunk_key = chunk_key + key[:48 - len(chunk_key)]
            h = hashlib.sha512(chunk_key + message + struct.pack('>I', i)).digest()
            pq_components.append(h[:32])
        pq_sig = b''.join(pq_components)
        return hashlib.sha512(classical_sig + pq_sig).hexdigest()

    @staticmethod
    def pq_verify(message: bytes, signature: str, key: bytes) -> bool:
        expected = PostQuantumSimulator.pq_sign(message, key)
        return hmac.compare_digest(signature, expected)


class RequestSigner:
    """
    Signs outgoing requests with HMAC or post-quantum algorithms.
    """

    def __init__(self, master_key: str, service_name: str):
        self.master_key = master_key.encode('utf-8')
        self.service_name = service_name

        # Derive purpose-specific keys
        self.request_key = hashlib.sha256(self.master_key + b"request_signing_v1").digest()
        self.pq_key = PostQuantumSimulator.derive_pq_key(self.master_key, "pq_signing_v1")

    def generate_request_id(self) -> str:
        """Generate unique request ID for binding."""
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000000)
        random_part = secrets.token_hex(12)
        return f"req_{timestamp}_{random_part}"

    def sign(
        self,
        data: Dict[str, Any],
        security_level: SecurityLevel = SecurityLevel.HIGH
    ) -> Dict[str, Any]:
        """
        Sign a request payload.

        Returns envelope with data and signature metadata.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        nonce = secrets.token_hex(24)
        request_id = self.generate_request_id()

        # Create canonical payload
        body_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        payload = f"{self.service_name}|{request_id}|{timestamp}|{nonce}|{body_str}"

        # Sign based on security level
        if security_level == SecurityLevel.QUANTUM_SAFE:
            signature = PostQuantumSimulator.pq_sign(payload.encode(), self.pq_key)
            algorithm = "pq-hybrid-sha512"
        elif security_level == SecurityLevel.HIGH:
            signature = hmac.new(self.request_key, payload.encode(), hashlib.sha512).hexdigest()
            algorithm = "hmac-sha512"
        else:
            signature = hmac.new(self.request_key, payload.encode(), hashlib.sha256).hexdigest()
            algorithm = "hmac-sha256"

        return {
            'data': data,
            'meta': {
                'signature': signature,
                'timestamp': timestamp,
                'nonce': nonce,
                'service_id': self.service_name,
                'request_id': request_id,
                'algorithm': algorithm
            }
        }


class ResponseVerifier:
    """
    Verifies incoming responses from auth service.

    CRITICAL: Responses that fail verification should NEVER be trusted!
    """

    def __init__(
        self,
        master_key: str,
        expected_service_id: str,
        validity_seconds: int = 30
    ):
        self.master_key = master_key.encode('utf-8')
        self.expected_service_id = expected_service_id
        self.validity_seconds = validity_seconds

        # Derive keys (must match server)
        self.response_key = hashlib.sha256(self.master_key + b"response_signing_v1").digest()
        self.pq_key = PostQuantumSimulator.derive_pq_key(self.master_key, "pq_signing_v1")

        # Nonce tracking to prevent replay
        self._used_nonces: Dict[str, float] = {}

    def verify(
        self,
        response_envelope: Dict[str, Any],
        expected_request_id: str
    ) -> Tuple[bool, str]:
        """
        Verify a response envelope.

        Args:
            response_envelope: The full response with data and meta
            expected_request_id: The request_id from our original request

        Returns:
            Tuple of (is_valid, error_message)
        """
        meta = response_envelope.get('meta', {})
        data = response_envelope.get('data', {})

        # 1. Check request binding (CRITICAL - prevents response replay)
        response_request_id = meta.get('request_id', '')
        if response_request_id != expected_request_id:
            return False, f"Response not bound to our request (expected {expected_request_id}, got {response_request_id})"

        # 2. Check service ID
        service_id = meta.get('service_id', '')
        if service_id != self.expected_service_id:
            return False, f"Response from unexpected service: {service_id}"

        # 3. Check timestamp freshness
        timestamp = meta.get('timestamp', '')
        try:
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age = abs((now - ts).total_seconds())
            if age > self.validity_seconds:
                return False, f"Response too old: {age:.1f}s"
        except (ValueError, TypeError) as e:
            return False, f"Invalid timestamp: {e}"

        # 4. Check nonce hasn't been used
        nonce = meta.get('nonce', '')
        if nonce in self._used_nonces:
            return False, "Response nonce already seen (possible replay attack)"

        # Cleanup old nonces
        cutoff = datetime.now(timezone.utc).timestamp() - (self.validity_seconds * 2)
        self._used_nonces = {n: t for n, t in self._used_nonces.items() if t > cutoff}
        self._used_nonces[nonce] = datetime.now(timezone.utc).timestamp()

        # 5. Verify signature
        algorithm = meta.get('algorithm', 'hmac-sha256')
        signature = meta.get('signature', '')

        body_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        payload = f"{service_id}|{response_request_id}|{timestamp}|{nonce}|{body_str}"

        if algorithm == "pq-hybrid-sha512":
            if not PostQuantumSimulator.pq_verify(payload.encode(), signature, self.pq_key):
                return False, "Invalid post-quantum signature"
        elif algorithm == "hmac-sha512":
            expected = hmac.new(self.response_key, payload.encode(), hashlib.sha512).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return False, "Invalid HMAC-SHA512 signature"
        else:
            expected = hmac.new(self.response_key, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return False, "Invalid HMAC-SHA256 signature"

        return True, "Response verified"


class AuthClient:
    """
    Secure authentication client with mutual authentication.

    All requests are signed. All responses are verified.
    Unverified responses are automatically rejected.
    """

    def __init__(
        self,
        service_name: str,
        api_key: Optional[str] = None,
        auth_url: Optional[str] = None,
        hmac_key: Optional[str] = None,
        expected_service_id: Optional[str] = None,
        ssl_verify: bool = True,
        security_level: SecurityLevel = SecurityLevel.HIGH
    ):
        """
        Initialize the secure auth client.

        Args:
            service_name: Name of this service (talent, org, admin, etc.)
            api_key: API key for this service
            auth_url: Auth service URL
            hmac_key: Shared HMAC key for signing/verification
            expected_service_id: Expected service ID from auth responses
            ssl_verify: Whether to verify SSL certificates
            security_level: Default security level for requests
        """
        self.service_name = service_name
        self.api_key = api_key or os.getenv(f'{service_name.upper()}_AUTH_KEY', '')
        self.auth_url = auth_url or os.getenv('AUTH_SERVICE_URL', 'https://localhost:9002')
        self.hmac_key = hmac_key or os.getenv('AUTH_HMAC_SECRET', '')
        self.expected_service_id = expected_service_id or os.getenv('AUTH_SERVICE_ID', '')
        self.ssl_verify = ssl_verify
        self.security_level = security_level

        # Initialize signer and verifier
        if self.hmac_key:
            self.signer = RequestSigner(self.hmac_key, self.service_name)
            self.verifier = ResponseVerifier(
                self.hmac_key,
                self.expected_service_id,
                validity_seconds=30
            )
        else:
            self.signer = None
            self.verifier = None
            logger.warning("No HMAC key configured - requests will not be signed!")

        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.auth_url,
                verify=self.ssl_verify,
                timeout=30.0,
                headers={
                    'X-Service-Name': self.service_name,
                    'X-Api-Key': self.api_key,
                    'Content-Type': 'application/json'
                }
            )
        return self._http_client

    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        security_level: Optional[SecurityLevel] = None
    ) -> AuthResponse:
        """
        Make a signed request and verify the response.

        1. Sign the request
        2. Send to auth service
        3. Verify response signature
        4. Return only if verified
        """
        level = security_level or self.security_level

        # Sign request
        if self.signer:
            signed_request = self.signer.sign(data, level)
            request_id = signed_request['meta']['request_id']
        else:
            signed_request = {'data': data, 'meta': {'request_id': secrets.token_hex(16)}}
            request_id = signed_request['meta']['request_id']
            logger.warning("Request not signed - HMAC key not configured")

        try:
            client = await self._get_client()
            response = await client.post(endpoint, json=signed_request)
            response_data = response.json()
        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return AuthResponse(
                raw={}, data={}, verified=False, success=False,
                error=f"Connection failed: {e}", request_id=request_id
            )

        # CRITICAL: Verify response before trusting
        if self.verifier:
            is_valid, error_msg = self.verifier.verify(response_data, request_id)

            if not is_valid:
                logger.warning(f"Response verification FAILED: {error_msg}")
                return AuthResponse(
                    raw=response_data,
                    data={},
                    verified=False,
                    success=False,
                    error=f"Response verification failed: {error_msg}",
                    request_id=request_id
                )

            logger.debug("Response signature verified")
        else:
            logger.warning("Response not verified - no verifier configured")

        # Extract data from verified response
        inner_data = response_data.get('data', {})

        return AuthResponse(
            raw=response_data,
            data=inner_data,
            verified=self.verifier is not None,
            success=inner_data.get('success', False),
            error=inner_data.get('error'),
            request_id=request_id
        )

    async def login(
        self,
        email: str,
        password: str,
        role: str = 'talent',
        otp_code: Optional[str] = None,
        security_level: Optional[SecurityLevel] = None
    ) -> AuthResponse:
        """
        Authenticate a user.

        The request is signed. The response is verified.
        Check result.verified before trusting the response!
        """
        return await self._make_request(
            '/api/auth/login',
            {
                'email': email,
                'password': password,
                'role': role,
                'otp_code': otp_code
            },
            security_level
        )

    async def register(
        self,
        email: str,
        password: str,
        role: str = 'talent',
        first_name: str = '',
        last_name: str = '',
        phone_number: str = '',
        consent_privacy: bool = False,
        consent_terms: bool = False,
        consent_marketing: bool = False,
        security_level: Optional[SecurityLevel] = None
    ) -> AuthResponse:
        """Register a new user."""
        return await self._make_request(
            '/api/auth/register',
            {
                'email': email,
                'password': password,
                'role': role,
                'first_name': first_name,
                'last_name': last_name,
                'phone_number': phone_number,
                'consent_privacy': consent_privacy,
                'consent_terms': consent_terms,
                'consent_marketing': consent_marketing
            },
            security_level
        )

    async def validate_token(
        self,
        token: str,
        token_type: str = 'access',
        security_level: Optional[SecurityLevel] = None
    ) -> AuthResponse:
        """Validate a token."""
        return await self._make_request(
            '/api/auth/token/validate',
            {'token': token, 'token_type': token_type},
            security_level
        )


# =============================================================================
# STANDALONE VERIFICATION FUNCTIONS
# =============================================================================

def verify_auth_response(
    response: Dict[str, Any],
    expected_request_id: str,
    hmac_key: str,
    expected_service_id: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify an auth response is authentic.

    Use this if not using the AuthClient class.

    Args:
        response: The full response envelope
        expected_request_id: The request_id from your original request
        hmac_key: The shared HMAC key
        expected_service_id: The expected service ID

    Returns:
        Tuple of (is_valid, data_or_error)
    """
    verifier = ResponseVerifier(hmac_key, expected_service_id)
    is_valid, error = verifier.verify(response, expected_request_id)

    if is_valid:
        return True, response.get('data', {})
    else:
        return False, {'error': error}

