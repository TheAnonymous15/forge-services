# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Accounts Service
=====================================
Service layer for accounts/authentication operations.
"""
import logging
from typing import Optional, Dict
from uuid import UUID
from django.core.cache import cache

logger = logging.getLogger('forgeforth.services.accounts')


class AccountsService:
    """
    Service for accounts-related operations.
    Provides a clean interface to the accounts database.
    """

    CACHE_TTL = 300  # 5 minutes

    @classmethod
    def get_user(cls, user_id: UUID) -> Optional[Dict]:
        """Get user by ID."""
        cache_key = f'user:{user_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from accounts.models import User

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

        result = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'role': user.role,
            'is_verified': user.is_verified,
            'is_active': user.is_active,
            'avatar': user.avatar.url if user.avatar else None,
            'date_joined': user.date_joined.isoformat(),
        }

        cache.set(cache_key, result, cls.CACHE_TTL)
        return result

    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[Dict]:
        """Get user by email address."""
        from accounts.models import User

        try:
            user = User.objects.get(email__iexact=email)
            return cls.get_user(user.id)
        except User.DoesNotExist:
            return None

    @classmethod
    def get_users_batch(cls, user_ids: list) -> Dict[str, Dict]:
        """
        Get multiple users by IDs.
        Returns dict mapping user_id -> user data.
        """
        from accounts.models import User

        # Check cache first
        result = {}
        missing_ids = []

        for uid in user_ids:
            cached = cache.get(f'user:{uid}')
            if cached:
                result[str(uid)] = cached
            else:
                missing_ids.append(uid)

        # Fetch missing from database
        if missing_ids:
            users = User.objects.filter(id__in=missing_ids)
            for user in users:
                user_data = {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'full_name': user.full_name,
                    'role': user.role,
                    'avatar': user.avatar.url if user.avatar else None,
                }
                result[str(user.id)] = user_data
                cache.set(f'user:{user.id}', user_data, cls.CACHE_TTL)

        return result

    @classmethod
    def invalidate_user_cache(cls, user_id: UUID):
        """Invalidate cached user data."""
        cache.delete(f'user:{user_id}')
        logger.info(f"Invalidated cache for user {user_id}")

    @classmethod
    def verify_user(cls, user_id: UUID) -> bool:
        """Mark user as verified."""
        from accounts.models import User

        try:
            user = User.objects.get(id=user_id)
            user.is_verified = True
            user.save(update_fields=['is_verified'])
            cls.invalidate_user_cache(user_id)
            return True
        except User.DoesNotExist:
            return False

    @classmethod
    def check_user_exists(cls, email: str) -> bool:
        """Check if a user with email exists."""
        from accounts.models import User
        return User.objects.filter(email__iexact=email).exists()

