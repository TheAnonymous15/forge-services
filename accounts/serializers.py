# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Accounts Serializers (MVP1)
================================================
Serializers for user authentication, registration, and profile management.
"""
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
import re

from .models import User, EmailVerificationToken, PasswordResetToken, LoginHistory


# =============================================================================
# USER SERIALIZERS
# =============================================================================

class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for responses."""
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone_number', 'avatar', 'role', 'is_verified',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'email', 'role', 'is_verified', 'date_joined', 'last_login']


class UserDetailSerializer(UserSerializer):
    """Detailed user serializer including settings."""
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + [
            'email_notifications', 'sms_notifications', 'push_notifications',
            'timezone', 'language', 'is_2fa_enabled'
        ]


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number', 'avatar',
            'email_notifications', 'sms_notifications', 'push_notifications',
            'timezone', 'language'
        ]

    def validate_phone_number(self, value):
        if value:
            # E.164 format validation
            if not re.match(r'^\+[1-9]\d{1,14}$', value):
                raise serializers.ValidationError(
                    "Phone number must be in E.164 format (e.g., +27123456789)"
                )
        return value


# =============================================================================
# REGISTRATION
# =============================================================================

class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="Email already registered")]
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    consent_privacy = serializers.BooleanField(required=True)
    consent_terms = serializers.BooleanField(required=True)
    consent_marketing = serializers.BooleanField(default=False)

    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'role',
            'consent_privacy', 'consent_terms', 'consent_marketing'
        ]

    def validate_password(self, value):
        """Validate password strength."""
        # Check for uppercase
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        # Check for lowercase
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter")
        # Check for digit
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one digit")
        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character")
        return value

    def validate_consent_privacy(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the privacy policy")
        return value

    def validate_consent_terms(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the terms of service")
        return value

    def validate_role(self, value):
        """Validate that only talent and employer can self-register."""
        if value not in [User.Role.TALENT, User.Role.EMPLOYER]:
            raise serializers.ValidationError("Invalid role for registration")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': "Passwords do not match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            consented_at=timezone.now(),
            **validated_data
        )
        return user


# =============================================================================
# LOGIN
# =============================================================================

class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})

    def validate(self, attrs):
        email = attrs.get('email', '').lower()
        password = attrs.get('password')

        # Check if user exists
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': "Invalid email or password"})

        # Check if account is locked
        if user.is_locked:
            raise serializers.ValidationError({
                'non_field_errors': "Account is temporarily locked. Please try again later."
            })

        # Check if account is active
        if not user.is_active:
            raise serializers.ValidationError({
                'non_field_errors': "Account is deactivated. Please contact support."
            })

        # Authenticate
        authenticated_user = authenticate(email=email, password=password)
        if not authenticated_user:
            user.increment_failed_login()
            raise serializers.ValidationError({'email': "Invalid email or password"})

        # Reset failed login attempts on success
        user.reset_failed_login()

        # Check if email is verified (warning only, don't block)
        attrs['user'] = authenticated_user
        attrs['requires_verification'] = not user.is_verified
        attrs['requires_2fa'] = user.is_2fa_enabled

        return attrs


# =============================================================================
# TOKEN REFRESH
# =============================================================================

class TokenRefreshSerializer(serializers.Serializer):
    """Serializer for JWT token refresh."""
    refresh = serializers.CharField()


# =============================================================================
# PASSWORD MANAGEMENT
# =============================================================================

class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for forgot password request."""
    email = serializers.EmailField()

    def validate_email(self, value):
        # Always return success to prevent email enumeration
        return value.lower()


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for password reset."""
    token = serializers.CharField()
    password = serializers.CharField(
        min_length=8,
        max_length=128,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(style={'input_type': 'password'})

    def validate_password(self, value):
        """Same validation as registration."""
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': "Passwords do not match"})

        # Validate token
        try:
            token_obj = PasswordResetToken.objects.get(token=attrs['token'])
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError({'token': "Invalid or expired token"})

        if not token_obj.is_valid:
            raise serializers.ValidationError({'token': "Invalid or expired token"})

        attrs['token_obj'] = token_obj
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password while logged in."""
    current_password = serializers.CharField(style={'input_type': 'password'})
    new_password = serializers.CharField(
        min_length=8,
        max_length=128,
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(style={'input_type': 'password'})

    def validate_new_password(self, value):
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': "Passwords do not match"})

        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': "Current password is incorrect"})

        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                'new_password': "New password must be different from current password"
            })

        return attrs


# =============================================================================
# EMAIL VERIFICATION
# =============================================================================

class VerifyEmailSerializer(serializers.Serializer):
    """Serializer for email verification."""
    token = serializers.CharField()

    def validate_token(self, value):
        try:
            token_obj = EmailVerificationToken.objects.get(token=value)
        except EmailVerificationToken.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired token")

        if not token_obj.is_valid:
            raise serializers.ValidationError("Invalid or expired token")

        self.token_obj = token_obj
        return value


class ResendVerificationSerializer(serializers.Serializer):
    """Serializer for resending verification email."""
    email = serializers.EmailField()

