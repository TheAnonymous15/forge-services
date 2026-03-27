# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Accounts Views (MVP1)
==========================================
API endpoints for authentication, registration, and user management.
"""
from rest_framework import status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import logout
from django.utils import timezone
from django.conf import settings
import logging

from .models import User, EmailVerificationToken, PasswordResetToken, LoginHistory
from .serializers import (
    UserSerializer, UserDetailSerializer, UserUpdateSerializer,
    RegisterSerializer, LoginSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer, ChangePasswordSerializer,
    VerifyEmailSerializer, ResendVerificationSerializer
)
from communications.services import EmailService

logger = logging.getLogger('forgeforth.accounts')


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_tokens_for_user(user):
    """Generate JWT tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# =============================================================================
# REGISTRATION
# =============================================================================

class RegisterView(generics.CreateAPIView):
    """
    Register a new user account.

    POST /api/v1/auth/register
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create verification token
        token = EmailVerificationToken.create_token(user)

        # Send verification email
        try:
            EmailService.send_verification_email(user, token.token)
        except Exception as e:
            logger.warning(f"Failed to send verification email to {user.email}: {e}")

        logger.info(f"New user registered: {user.email} (role: {user.role})")

        return Response({
            'success': True,
            'message': 'Registration successful. Please verify your email.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


# =============================================================================
# LOGIN / LOGOUT
# =============================================================================

class LoginView(APIView):
    """
    Authenticate user and return JWT tokens.

    POST /api/v1/auth/login
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            # Log failed attempt
            email = request.data.get('email', '')
            LoginHistory.objects.create(
                email=email,
                status=LoginHistory.Status.FAILED,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                failure_reason=str(e)
            )
            raise

        user = serializer.validated_data['user']
        requires_2fa = serializer.validated_data.get('requires_2fa', False)

        # If 2FA is required, return partial response
        if requires_2fa:
            LoginHistory.objects.create(
                user=user,
                email=user.email,
                status=LoginHistory.Status.REQUIRES_2FA,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response({
                'requires_2fa': True,
                'message': 'Please enter your 2FA code'
            }, status=status.HTTP_200_OK)

        # Generate tokens
        tokens = get_tokens_for_user(user)

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Log successful login
        LoginHistory.objects.create(
            user=user,
            email=user.email,
            status=LoginHistory.Status.SUCCESS,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        logger.info(f"User logged in: {user.email}")

        response_data = {
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': UserSerializer(user).data
        }

        if serializer.validated_data.get('requires_verification'):
            response_data['warning'] = 'Please verify your email address'

        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Logout user and blacklist refresh token.

    POST /api/v1/auth/logout
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except TokenError:
            pass  # Token was already blacklisted or invalid

        logger.info(f"User logged out: {request.user.email}")
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)


# =============================================================================
# EMAIL VERIFICATION
# =============================================================================

class VerifyEmailView(APIView):
    """
    Verify user email address.

    POST /api/v1/auth/verify-email
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_obj = serializer.token_obj
        user = token_obj.user

        # Mark user as verified
        user.is_verified = True
        user.save(update_fields=['is_verified'])

        # Mark token as used
        token_obj.use()

        logger.info(f"Email verified: {user.email}")

        return Response({
            'success': True,
            'message': 'Email verified successfully'
        }, status=status.HTTP_200_OK)


class ResendVerificationView(APIView):
    """
    Resend email verification link.

    POST /api/v1/auth/resend-verification
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email__iexact=email, is_verified=False)
            token = EmailVerificationToken.create_token(user)
            # Send verification email
            try:
                EmailService.send_verification_email(user, token.token)
            except Exception as e:
                logger.warning(f"Failed to send verification email to {user.email}: {e}")
        except User.DoesNotExist:
            pass  # Don't reveal if email exists

        # Always return success to prevent email enumeration
        return Response({
            'success': True,
            'message': 'If your email is registered and unverified, you will receive a verification link.'
        }, status=status.HTTP_200_OK)


# =============================================================================
# PASSWORD MANAGEMENT
# =============================================================================

class ForgotPasswordView(APIView):
    """
    Request password reset link.

    POST /api/v1/auth/password/forgot
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
            token = PasswordResetToken.create_token(
                user,
                ip_address=get_client_ip(request)
            )
            # Send password reset email
            try:
                EmailService.send_password_reset_email(user, token.token)
            except Exception as e:
                logger.warning(f"Failed to send password reset email to {user.email}: {e}")
            logger.info(f"Password reset requested: {email}")
        except User.DoesNotExist:
            pass  # Don't reveal if email exists

        # Always return success to prevent email enumeration
        return Response({
            'success': True,
            'message': 'If your email is registered, you will receive a password reset link.'
        }, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """
    Reset password using token.

    POST /api/v1/auth/password/reset
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_obj = serializer.validated_data['token_obj']
        user = token_obj.user

        # Set new password
        user.set_password(serializer.validated_data['password'])
        user.last_password_change = timezone.now()
        user.save(update_fields=['password', 'last_password_change'])

        # Mark token as used
        token_obj.use()

        # Blacklist all existing refresh tokens for this user
        # (This requires custom implementation or using a different approach)

        logger.info(f"Password reset completed: {user.email}")

        return Response({
            'success': True,
            'message': 'Password reset successful. You can now login with your new password.'
        }, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """
    Change password for authenticated user.

    POST /api/v1/auth/password/change
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.last_password_change = timezone.now()
        user.save(update_fields=['password', 'last_password_change'])

        # Generate new tokens
        tokens = get_tokens_for_user(user)

        logger.info(f"Password changed: {user.email}")

        return Response({
            'success': True,
            'message': 'Password changed successfully',
            'access': tokens['access'],
            'refresh': tokens['refresh']
        }, status=status.HTTP_200_OK)


# =============================================================================
# USER PROFILE
# =============================================================================

class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    Get or update current user profile.

    GET /api/v1/auth/me
    PATCH /api/v1/auth/me
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserDetailSerializer
        return UserUpdateSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        logger.info(f"User profile updated: {instance.email}")

        return Response({
            'success': True,
            'user': UserDetailSerializer(instance).data
        })


# =============================================================================
# HEALTH CHECK
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def auth_health(request):
    """
    Health check for auth service.

    GET /api/v1/auth/health
    """
    return Response({
        'status': 'healthy',
        'service': 'auth',
        'timestamp': timezone.now().isoformat()
    })

