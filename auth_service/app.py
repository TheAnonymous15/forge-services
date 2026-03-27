# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Application
============================================
Central authentication service with mutual authentication.

All requests MUST be signed. All responses ARE signed.
Unsigned requests are rejected. Unsigned responses should be rejected by clients.

Port: 9002 (configurable via AUTH_SERVICE_PORT)
"""
import os
import sys
import ssl
import json
import logging
import asyncio
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import uvicorn

from auth_service.config import config
from auth_service.security import (
    auth_manager, sign_response, verify_request, SignedRequest,
    SecurityLevel, SignatureError
)

# Configure logging
os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOG_FILE)
    ]
)
logger = logging.getLogger('auth_service')


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class LoginData(BaseModel):
    """Login request payload."""
    email: EmailStr
    password: str = Field(..., min_length=1)
    role: str = Field(default='talent')
    otp_code: Optional[str] = None


class RegisterData(BaseModel):
    """Registration request payload."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field(default='talent')
    first_name: str = ''
    last_name: str = ''
    phone_number: str = ''
    consent_privacy: bool = False
    consent_terms: bool = False
    consent_marketing: bool = False


class SignedRequestEnvelope(BaseModel):
    """Signed request envelope."""
    data: Dict
    meta: Dict


# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan."""
    logger.info("=" * 60)
    logger.info("ForgeForth Africa - Auth Service Starting")
    logger.info("=" * 60)
    logger.info(f"Service ID: {config.SERVICE_ID}")
    logger.info(f"Version: {config.SERVICE_VERSION}")
    logger.info(f"SSL: {config.SSL_ENABLED}")
    logger.info(f"Mutual Auth: ENABLED")
    logger.info("=" * 60)

    yield

    logger.info("Auth Service shutdown complete")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title="ForgeForth Africa - Auth Service",
    description="""
    Central authentication service with mutual authentication.
    
    Security Features:
    - All requests must be signed
    - All responses are signed
    - Request-response binding
    - Post-quantum hybrid algorithms
    - Nonce-based replay protection
    """,
    version=config.SERVICE_VERSION,
    docs_url="/docs" if config.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS if not config.DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Auth-Service-ID"] = config.SERVICE_ID
    return response


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_client_ip(request: Request) -> str:
    """Get client IP."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def verify_signed_request(
    envelope: SignedRequestEnvelope,
    x_service_name: str = Header(None),
    x_api_key: str = Header(None)
) -> tuple[Dict, str]:
    """
    Verify incoming signed request.

    Returns:
        Tuple of (request_data, request_id)

    Raises:
        HTTPException if verification fails
    """
    # First check API key (quick rejection)
    if not x_service_name or not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing service credentials (X-Service-Name, X-Api-Key)"
        )

    if not auth_manager.verify_api_key(x_api_key, x_service_name):
        logger.warning(f"Invalid API key from: {x_service_name}")
        raise HTTPException(status_code=401, detail="Invalid service credentials")

    # Verify signature
    is_valid, error_msg, request_id = verify_request(envelope.dict())

    if not is_valid:
        logger.warning(f"Request verification failed: {error_msg}")
        raise HTTPException(
            status_code=400,
            detail=f"Request signature verification failed: {error_msg}"
        )

    logger.debug(f"Request verified from {x_service_name}, request_id={request_id}")
    return envelope.data, request_id


# =============================================================================
# MOCK AUTH HANDLERS (Replace with actual database handlers)
# =============================================================================

# In-memory user storage for demo (replace with database)
MOCK_USERS: Dict[str, Dict] = {}


async def handle_login(
    email: str,
    password: str,
    role: str,
    ip_address: str
) -> Dict:
    """Handle login request."""
    # Check if user exists
    user = MOCK_USERS.get(email.lower())

    if not user:
        return {
            'success': False,
            'error': 'Invalid email or password',
            'code': 'INVALID_CREDENTIALS'
        }

    # Check password (in real app, use bcrypt)
    if user['password'] != password:
        return {
            'success': False,
            'error': 'Invalid email or password',
            'code': 'INVALID_CREDENTIALS'
        }

    # Check role
    if user['role'] != role:
        return {
            'success': False,
            'error': 'Invalid credentials for this portal',
            'code': 'ROLE_MISMATCH'
        }

    # Success
    return {
        'success': True,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'first_name': user['first_name'],
            'last_name': user['last_name'],
            'role': user['role']
        },
        'message': 'Authentication successful'
    }


async def handle_register(
    email: str,
    password: str,
    role: str,
    first_name: str,
    last_name: str,
    consent_privacy: bool,
    consent_terms: bool,
    ip_address: str
) -> Dict:
    """Handle registration request."""
    if not consent_privacy or not consent_terms:
        return {
            'success': False,
            'error': 'You must accept privacy policy and terms',
            'code': 'CONSENT_REQUIRED'
        }

    if email.lower() in MOCK_USERS:
        return {
            'success': False,
            'error': 'Email already registered',
            'code': 'EMAIL_EXISTS'
        }

    # Create user
    user_id = secrets.token_hex(16)
    MOCK_USERS[email.lower()] = {
        'id': user_id,
        'email': email.lower(),
        'password': password,
        'first_name': first_name,
        'last_name': last_name,
        'role': role,
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    return {
        'success': True,
        'user': {
            'id': user_id,
            'email': email.lower(),
            'first_name': first_name,
            'last_name': last_name,
            'role': role
        },
        'message': 'Registration successful'
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health():
    """Health check (unsigned)."""
    return {
        'status': 'healthy',
        'service': config.SERVICE_NAME,
        'service_id': config.SERVICE_ID,
        'mutual_auth': True,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/auth/login")
async def login(
    request: Request,
    envelope: SignedRequestEnvelope,
    x_service_name: str = Header(None),
    x_api_key: str = Header(None)
):
    """
    Authenticate a user.

    Request must be signed. Response is signed.
    """
    # Verify request signature
    data, request_id = await verify_signed_request(
        envelope, x_service_name, x_api_key
    )

    # Validate data
    try:
        login_data = LoginData(**data)
    except Exception as e:
        response_data = {'success': False, 'error': str(e), 'code': 'VALIDATION_ERROR'}
        return JSONResponse(content=sign_response(response_data, request_id))

    # Process login
    ip_address = get_client_ip(request)
    result = await handle_login(
        email=login_data.email,
        password=login_data.password,
        role=login_data.role,
        ip_address=ip_address
    )

    # Sign and return response (bound to request_id)
    signed_response = sign_response(result, request_id, SecurityLevel.HIGH)

    status_code = 200 if result.get('success') else 401
    return JSONResponse(content=signed_response, status_code=status_code)


@app.post("/api/auth/register")
async def register(
    request: Request,
    envelope: SignedRequestEnvelope,
    x_service_name: str = Header(None),
    x_api_key: str = Header(None)
):
    """
    Register a new user.

    Request must be signed. Response is signed.
    """
    # Verify request signature
    data, request_id = await verify_signed_request(
        envelope, x_service_name, x_api_key
    )

    # Validate data
    try:
        reg_data = RegisterData(**data)
    except Exception as e:
        response_data = {'success': False, 'error': str(e), 'code': 'VALIDATION_ERROR'}
        return JSONResponse(content=sign_response(response_data, request_id))

    # Process registration
    ip_address = get_client_ip(request)
    result = await handle_register(
        email=reg_data.email,
        password=reg_data.password,
        role=reg_data.role,
        first_name=reg_data.first_name,
        last_name=reg_data.last_name,
        consent_privacy=reg_data.consent_privacy,
        consent_terms=reg_data.consent_terms,
        ip_address=ip_address
    )

    # Sign and return response
    signed_response = sign_response(result, request_id, SecurityLevel.HIGH)

    status_code = 201 if result.get('success') else 400
    return JSONResponse(content=signed_response, status_code=status_code)


@app.post("/api/auth/token/validate")
async def validate_token(
    envelope: SignedRequestEnvelope,
    x_service_name: str = Header(None),
    x_api_key: str = Header(None)
):
    """Validate a token."""
    data, request_id = await verify_signed_request(
        envelope, x_service_name, x_api_key
    )

    # TODO: Implement actual token validation
    result = {'valid': True, 'success': True}

    return JSONResponse(content=sign_response(result, request_id))


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the auth service."""
    print()
    print("=" * 60)
    print("  ForgeForth Africa - Auth Service")
    print("=" * 60)
    print(f"  URL:           http{'s' if config.SSL_ENABLED else ''}://{config.HOST}:{config.PORT}")
    print(f"  Service ID:    {config.SERVICE_ID}")
    print(f"  SSL:           {'Enabled' if config.SSL_ENABLED else 'Disabled'}")
    print(f"  Mutual Auth:   ENABLED")
    print(f"  PQ Algorithms: Available")
    print("=" * 60)
    print()
    print("  Security: All requests must be signed.")
    print("            All responses are signed.")
    print("            Verify signatures before trusting!")
    print()

    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        ssl_keyfile=config.SSL_KEY_FILE if config.SSL_ENABLED else None,
        ssl_certfile=config.SSL_CERT_FILE if config.SSL_ENABLED else None,
    )


if __name__ == "__main__":
    main()

