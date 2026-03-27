# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service API Routes
===========================================
FastAPI routes for the authentication microservice.
"""
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator

from .service import AuthService, AuthError, ValidationError

router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = ""
    last_name: str = ""
    phone_number: str = ""
    role: str = "talent"
    consent_privacy: bool = False
    consent_terms: bool = False
    consent_marketing: bool = False

    @validator('role')
    def validate_role(cls, v):
        valid_roles = ['talent', 'employer', 'org_admin']
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    otp_code: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class ValidateTokenRequest(BaseModel):
    token: str
    token_type: str = "access"


class CheckPermissionRequest(BaseModel):
    user_id: str
    permission: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> str:
    """Get user agent from request."""
    return request.headers.get('User-Agent', '')


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/register")
async def register(data: RegisterRequest, request: Request):
    """
    Register a new user account.

    Returns user data and verification token.
    """
    try:
        result = AuthService.register(
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            phone_number=data.phone_number,
            role=data.role,
            consent_privacy=data.consent_privacy,
            consent_terms=data.consent_terms,
            consent_marketing=data.consent_marketing,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        return JSONResponse(content=result, status_code=201)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'field': e.field})
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/login")
async def login(data: LoginRequest, request: Request):
    """
    Authenticate user and return JWT tokens.
    """
    try:
        result = AuthService.login(
            email=data.email,
            password=data.password,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            otp_code=data.otp_code
        )
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/logout")
async def logout(data: LogoutRequest):
    """
    Logout user by blacklisting refresh token.
    """
    try:
        result = AuthService.logout(data.refresh_token)
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/token/refresh")
async def refresh_token(data: RefreshTokenRequest):
    """
    Refresh access token using refresh token.
    """
    try:
        result = AuthService.refresh_tokens(data.refresh_token)
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/token/validate")
async def validate_token(data: ValidateTokenRequest):
    """
    Validate a token and return user info.

    This endpoint is used by other services to validate tokens.
    """
    try:
        result = AuthService.validate_token(data.token, data.token_type)
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/verify-email")
async def verify_email(data: VerifyEmailRequest):
    """
    Verify user email address using verification token.
    """
    try:
        result = AuthService.verify_email(data.token)
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/resend-verification")
async def resend_verification(data: ResendVerificationRequest):
    """
    Resend email verification link.
    """
    try:
        result = AuthService.resend_verification(data.email)
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/password/forgot")
async def forgot_password(data: ForgotPasswordRequest, request: Request):
    """
    Request password reset link.
    """
    try:
        result = AuthService.forgot_password(
            email=data.email,
            ip_address=get_client_ip(request)
        )
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/password/reset")
async def reset_password(data: ResetPasswordRequest):
    """
    Reset password using reset token.
    """
    try:
        result = AuthService.reset_password(
            token=data.token,
            new_password=data.new_password
        )
        return JSONResponse(content=result, status_code=200)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'field': e.field})
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/password/change")
async def change_password(
    data: ChangePasswordRequest,
    authorization: str = Header(...)
):
    """
    Change password for authenticated user.

    Requires Authorization header with Bearer token.
    """
    try:
        # Extract token from header
        if not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail={'error': 'Invalid authorization header'})

        token = authorization[7:]

        # Validate token and get user
        token_info = AuthService.validate_token(token, 'access')
        user_id = token_info['user_id']

        result = AuthService.change_password(
            user_id=user_id,
            current_password=data.current_password,
            new_password=data.new_password
        )
        return JSONResponse(content=result, status_code=200)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'field': e.field})
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})


@router.post("/permission/check")
async def check_permission(data: CheckPermissionRequest):
    """
    Check if user has a specific permission.

    Used by other services for authorization checks.
    """
    has_permission = AuthService.check_permission(data.user_id, data.permission)
    return JSONResponse(content={
        'has_permission': has_permission,
        'user_id': data.user_id,
        'permission': data.permission
    }, status_code=200)


@router.get("/me")
async def get_current_user(authorization: str = Header(...)):
    """
    Get current user info from token.
    """
    try:
        if not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail={'error': 'Invalid authorization header'})

        token = authorization[7:]
        result = AuthService.validate_token(token, 'access')
        return JSONResponse(content=result, status_code=200)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={'error': e.message, 'code': e.code})

