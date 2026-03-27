# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Profiles Service
=====================================
Service layer for talent profile operations.
"""
import logging
from typing import Optional, Dict, List
from uuid import UUID
from django.core.cache import cache

logger = logging.getLogger('forgeforth.services.profiles')


class ProfilesService:
    """
    Service for profiles-related operations.
    Provides a clean interface to the profiles database.
    """

    CACHE_TTL = 300  # 5 minutes

    @classmethod
    def get_talent_profile(cls, user_id: UUID) -> Optional[Dict]:
        """Get talent profile by user ID."""
        cache_key = f'profile:{user_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from profiles.models import TalentProfile

        try:
            profile = TalentProfile.objects.select_related('user').get(user_id=user_id)
        except TalentProfile.DoesNotExist:
            return None

        result = {
            'id': str(profile.id),
            'user_id': str(profile.user_id),
            'headline': profile.headline,
            'bio': profile.bio,
            'avatar': profile.avatar.url if profile.avatar else None,
            'country': profile.country,
            'city': profile.city,
            'employment_status': profile.employment_status,
            'availability': profile.availability,
            'remote_preference': profile.remote_preference,
            'completeness_score': profile.completeness_score,
            'is_public': profile.is_public,
            'views_count': profile.views_count,
        }

        cache.set(cache_key, result, cls.CACHE_TTL)
        return result

    @classmethod
    def get_talent_skills(cls, user_id: UUID) -> List[Dict]:
        """Get skills for a talent."""
        from profiles.models import TalentSkill

        skills = TalentSkill.objects.filter(
            profile__user_id=user_id
        ).select_related('skill').order_by('-is_primary', '-years_of_experience')

        return [
            {
                'name': ts.skill.name,
                'slug': ts.skill.slug,
                'category': ts.skill.category,
                'level': ts.level,
                'years': ts.years_of_experience,
                'is_primary': ts.is_primary,
            }
            for ts in skills
        ]

    @classmethod
    def get_talent_education(cls, user_id: UUID) -> List[Dict]:
        """Get education history for a talent."""
        from profiles.models import Education

        education = Education.objects.filter(
            profile__user_id=user_id
        ).order_by('-end_date', '-start_date')

        return [
            {
                'id': str(e.id),
                'institution': e.institution,
                'degree': e.degree,
                'level': e.level,
                'field': e.field_of_study,
                'start_date': e.start_date.isoformat() if e.start_date else None,
                'end_date': e.end_date.isoformat() if e.end_date else None,
                'is_current': e.is_current,
            }
            for e in education
        ]

    @classmethod
    def get_talent_experience(cls, user_id: UUID) -> List[Dict]:
        """Get work experience for a talent."""
        from profiles.models import WorkExperience

        experience = WorkExperience.objects.filter(
            profile__user_id=user_id
        ).order_by('-is_current', '-end_date', '-start_date')

        return [
            {
                'id': str(w.id),
                'company': w.company,
                'title': w.title,
                'employment_type': w.employment_type,
                'location': w.location,
                'is_remote': w.is_remote,
                'start_date': w.start_date.isoformat() if w.start_date else None,
                'end_date': w.end_date.isoformat() if w.end_date else None,
                'is_current': w.is_current,
                'description': w.description,
            }
            for w in experience
        ]

    @classmethod
    def get_talent_complete(cls, user_id: UUID) -> Optional[Dict]:
        """Get complete talent profile with all related data."""
        profile = cls.get_talent_profile(user_id)
        if not profile:
            return None

        profile['skills'] = cls.get_talent_skills(user_id)
        profile['education'] = cls.get_talent_education(user_id)
        profile['experience'] = cls.get_talent_experience(user_id)

        return profile

    @classmethod
    def update_profile_completeness(cls, user_id: UUID) -> int:
        """Recalculate and update profile completeness score."""
        from profiles.models import TalentProfile

        try:
            profile = TalentProfile.objects.get(user_id=user_id)
            score = profile.calculate_completeness()
            profile.save(update_fields=['completeness_score'])
            cls.invalidate_profile_cache(user_id)
            return score
        except TalentProfile.DoesNotExist:
            return 0

    @classmethod
    def increment_profile_views(cls, user_id: UUID):
        """Increment profile view count."""
        from profiles.models import TalentProfile
        from django.db.models import F

        TalentProfile.objects.filter(user_id=user_id).update(
            views_count=F('views_count') + 1
        )

    @classmethod
    def invalidate_profile_cache(cls, user_id: UUID):
        """Invalidate cached profile data."""
        cache.delete(f'profile:{user_id}')
        logger.info(f"Invalidated cache for profile {user_id}")

    @classmethod
    def search_talents(
        cls,
        query: str = None,
        skills: List[str] = None,
        country: str = None,
        availability: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """
        Search talent profiles.
        """
        from profiles.models import TalentProfile
        from django.db import models

        qs = TalentProfile.objects.filter(
            is_public=True,
            is_searchable=True,
            user__is_active=True,
        ).select_related('user')

        if query:
            qs = qs.filter(
                models.Q(headline__icontains=query) |
                models.Q(bio__icontains=query) |
                models.Q(user__first_name__icontains=query) |
                models.Q(user__last_name__icontains=query)
            )

        if country:
            qs = qs.filter(country__iexact=country)

        if availability:
            qs = qs.filter(availability=availability)

        if skills:
            qs = qs.filter(
                skills__skill__slug__in=skills
            ).distinct()

        total = qs.count()
        profiles = qs.order_by('-completeness_score', '-updated_at')[offset:offset + limit]

        return {
            'total': total,
            'results': [
                {
                    'user_id': str(p.user_id),
                    'name': p.user.full_name,
                    'headline': p.headline,
                    'avatar': p.avatar.url if p.avatar else None,
                    'location': f"{p.city}, {p.country}" if p.city else p.country,
                    'availability': p.availability,
                    'completeness': p.completeness_score,
                }
                for p in profiles
            ]
        }

