# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Data Federation Service
============================================
Central service for cross-database communication and data aggregation.

This service is responsible for:
1. Aggregating data from multiple databases
2. Handling cross-database queries
3. Maintaining data consistency via events
4. Caching frequently accessed cross-service data
"""
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from django.core.cache import cache
from django.db import connections
from django.conf import settings

logger = logging.getLogger('forgeforth.federation')


class DataFederationService:
    """
    Central service for cross-database data operations.

    This service acts as the "glue" between isolated databases,
    providing a unified interface for querying and aggregating
    data across subsystems.
    """

    # Cache TTL defaults (in seconds)
    CACHE_TTL_SHORT = 60  # 1 minute
    CACHE_TTL_MEDIUM = 300  # 5 minutes
    CACHE_TTL_LONG = 3600  # 1 hour

    # Database aliases
    DB_ACCOUNTS = 'accounts_db'
    DB_PROFILES = 'profiles_db'
    DB_ORGANIZATIONS = 'organizations_db'
    DB_APPLICATIONS = 'applications_db'
    DB_COMMUNICATIONS = 'communications_db'
    DB_ANALYTICS = 'analytics_db'

    @classmethod
    def get_database(cls, db_alias: str):
        """Get database connection by alias."""
        # In single-DB mode, always return default
        if getattr(settings, 'USE_SINGLE_DATABASE', True):
            return connections['default']
        return connections[db_alias]

    # =========================================================================
    # TALENT AGGREGATION
    # =========================================================================

    @classmethod
    def get_talent_full_profile(cls, talent_id: UUID) -> Optional[Dict]:
        """
        Aggregate complete talent profile from multiple databases.

        Combines:
        - User data (accounts_db)
        - Profile data (profiles_db)
        - Application stats (applications_db)
        - Unread messages count (communications_db)
        """
        cache_key = f'talent_full:{talent_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from accounts.models import User
        from profiles.models import TalentProfile

        try:
            user = User.objects.get(id=talent_id)
        except User.DoesNotExist:
            return None

        try:
            profile = TalentProfile.objects.select_related('user').prefetch_related(
                'education', 'work_experience', 'skills__skill',
                'certifications', 'languages'
            ).get(user_id=talent_id)
        except TalentProfile.DoesNotExist:
            profile = None

        result = {
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.full_name,
                'avatar': user.avatar.url if user.avatar else None,
                'is_verified': user.is_verified,
                'date_joined': user.date_joined.isoformat(),
            },
            'profile': None,
            'stats': cls._get_talent_stats(talent_id),
        }

        if profile:
            result['profile'] = {
                'headline': profile.headline,
                'bio': profile.bio,
                'country': profile.country,
                'city': profile.city,
                'employment_status': profile.employment_status,
                'availability': profile.availability,
                'remote_preference': profile.remote_preference,
                'completeness_score': profile.completeness_score,
                'skills': [
                    {
                        'name': ts.skill.name,
                        'level': ts.level,
                        'years': ts.years_of_experience,
                        'is_primary': ts.is_primary,
                    }
                    for ts in profile.skills.all()
                ],
                'education': [
                    {
                        'institution': e.institution,
                        'degree': e.degree,
                        'field': e.field_of_study,
                        'start': e.start_date.isoformat() if e.start_date else None,
                        'end': e.end_date.isoformat() if e.end_date else None,
                    }
                    for e in profile.education.all()
                ],
                'experience': [
                    {
                        'company': w.company,
                        'title': w.title,
                        'type': w.employment_type,
                        'start': w.start_date.isoformat() if w.start_date else None,
                        'end': w.end_date.isoformat() if w.end_date else None,
                        'is_current': w.is_current,
                    }
                    for w in profile.work_experience.all()
                ],
            }

        cache.set(cache_key, result, cls.CACHE_TTL_MEDIUM)
        return result

    @classmethod
    def _get_talent_stats(cls, talent_id: UUID) -> Dict:
        """Get talent statistics from applications database."""
        # TODO: Implement when applications app is ready
        return {
            'total_applications': 0,
            'pending_applications': 0,
            'interviews_scheduled': 0,
            'unread_messages': 0,
        }

    # =========================================================================
    # ORGANIZATION AGGREGATION
    # =========================================================================

    @classmethod
    def get_organization_full_profile(cls, org_id: UUID) -> Optional[Dict]:
        """
        Aggregate complete organization profile.

        Combines:
        - Organization data (organizations_db)
        - Active opportunities count
        - Member list
        - Application stats
        """
        cache_key = f'org_full:{org_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from organizations.models import Organization, Opportunity

        try:
            org = Organization.objects.prefetch_related(
                'members__user', 'locations'
            ).get(id=org_id)
        except Organization.DoesNotExist:
            return None

        active_opportunities = Opportunity.objects.filter(
            organization_id=org_id,
            status='open'
        ).count()

        result = {
            'id': str(org.id),
            'name': org.name,
            'slug': org.slug,
            'tagline': org.tagline,
            'description': org.description,
            'org_type': org.org_type,
            'industry': org.industry.name if org.industry else None,
            'size': org.size,
            'logo': org.logo.url if org.logo else None,
            'website': org.website,
            'location': {
                'country': org.country,
                'city': org.city,
            },
            'status': org.status,
            'is_verified': org.status == 'verified',
            'stats': {
                'active_opportunities': active_opportunities,
                'total_opportunities': org.total_opportunities,
                'total_hires': org.total_hires,
                'member_count': org.members.filter(is_active=True).count(),
            },
            'members': [
                {
                    'user_id': str(m.user_id),
                    'name': m.user.full_name,
                    'role': m.role,
                    'title': m.title,
                }
                for m in org.members.filter(is_active=True)[:10]
            ],
            'locations': [
                {
                    'name': loc.name,
                    'city': loc.city,
                    'country': loc.country,
                    'is_hq': loc.is_headquarters,
                }
                for loc in org.locations.all()
            ],
        }

        cache.set(cache_key, result, cls.CACHE_TTL_MEDIUM)
        return result

    # =========================================================================
    # OPPORTUNITY AGGREGATION
    # =========================================================================

    @classmethod
    def get_opportunity_with_org(cls, opportunity_id: UUID) -> Optional[Dict]:
        """
        Get opportunity with organization details.
        """
        cache_key = f'opp_full:{opportunity_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from organizations.models import Opportunity

        try:
            opp = Opportunity.objects.select_related(
                'organization', 'organization__industry'
            ).get(id=opportunity_id)
        except Opportunity.DoesNotExist:
            return None

        result = {
            'id': str(opp.id),
            'title': opp.title,
            'slug': opp.slug,
            'description': opp.description,
            'summary': opp.summary,
            'type': opp.opportunity_type,
            'experience_level': opp.experience_level,
            'location': opp.location,
            'remote_policy': opp.remote_policy,
            'salary': opp.salary_display,
            'status': opp.status,
            'is_open': opp.is_open,
            'deadline': opp.deadline.isoformat() if opp.deadline else None,
            'published_at': opp.published_at.isoformat() if opp.published_at else None,
            'required_skills': opp.required_skills,
            'organization': {
                'id': str(opp.organization.id),
                'name': opp.organization.name,
                'slug': opp.organization.slug,
                'logo': opp.organization.logo.url if opp.organization.logo else None,
                'industry': opp.organization.industry.name if opp.organization.industry else None,
            },
            'stats': {
                'views': opp.views_count,
                'applications': opp.applications_count,
            }
        }

        cache.set(cache_key, result, cls.CACHE_TTL_SHORT)
        return result

    # =========================================================================
    # SEARCH / DISCOVERY
    # =========================================================================

    @classmethod
    def search_talents(
        cls,
        query: str = None,
        skills: List[str] = None,
        location: str = None,
        availability: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """
        Search talents across the platform.
        Uses profiles_db with optional full-text search.
        """
        from profiles.models import TalentProfile

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

        if location:
            qs = qs.filter(
                models.Q(city__icontains=location) |
                models.Q(country__icontains=location)
            )

        if availability:
            qs = qs.filter(availability=availability)

        if skills:
            qs = qs.filter(skills__skill__name__in=skills).distinct()

        total = qs.count()
        results = qs[offset:offset + limit]

        return {
            'total': total,
            'limit': limit,
            'offset': offset,
            'results': [
                {
                    'id': str(p.user_id),
                    'name': p.user.full_name,
                    'headline': p.headline,
                    'avatar': p.avatar.url if p.avatar else None,
                    'location': f"{p.city}, {p.country}" if p.city else p.country,
                    'availability': p.availability,
                    'completeness': p.completeness_score,
                }
                for p in results
            ]
        }

    @classmethod
    def search_opportunities(
        cls,
        query: str = None,
        opportunity_type: str = None,
        location: str = None,
        remote_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """
        Search opportunities across the platform.
        """
        from organizations.models import Opportunity
        from django.db import models

        qs = Opportunity.objects.filter(
            status='open',
            organization__is_public=True,
        ).select_related('organization')

        if query:
            qs = qs.filter(
                models.Q(title__icontains=query) |
                models.Q(description__icontains=query) |
                models.Q(organization__name__icontains=query)
            )

        if opportunity_type:
            qs = qs.filter(opportunity_type=opportunity_type)

        if location:
            qs = qs.filter(
                models.Q(city__icontains=location) |
                models.Q(country__icontains=location)
            )

        if remote_only:
            qs = qs.filter(remote_policy='remote')

        total = qs.count()
        results = qs.order_by('-is_featured', '-published_at')[offset:offset + limit]

        return {
            'total': total,
            'limit': limit,
            'offset': offset,
            'results': [
                {
                    'id': str(o.id),
                    'title': o.title,
                    'slug': o.slug,
                    'type': o.opportunity_type,
                    'location': o.location or f"{o.city}, {o.country}" if o.city else o.country,
                    'remote': o.remote_policy,
                    'salary': o.salary_display,
                    'is_featured': o.is_featured,
                    'organization': {
                        'name': o.organization.name,
                        'logo': o.organization.logo.url if o.organization.logo else None,
                    },
                    'published_at': o.published_at.isoformat() if o.published_at else None,
                }
                for o in results
            ]
        }

    # =========================================================================
    # CACHE INVALIDATION
    # =========================================================================

    @classmethod
    def invalidate_talent_cache(cls, talent_id: UUID):
        """Invalidate all cached data for a talent."""
        cache.delete_many([
            f'talent_full:{talent_id}',
            f'talent_search:{talent_id}',
        ])
        logger.info(f"Invalidated cache for talent {talent_id}")

    @classmethod
    def invalidate_organization_cache(cls, org_id: UUID):
        """Invalidate all cached data for an organization."""
        cache.delete_many([
            f'org_full:{org_id}',
            f'org_opportunities:{org_id}',
        ])
        logger.info(f"Invalidated cache for organization {org_id}")

    @classmethod
    def invalidate_opportunity_cache(cls, opportunity_id: UUID):
        """Invalidate cached opportunity data."""
        cache.delete(f'opp_full:{opportunity_id}')
        logger.info(f"Invalidated cache for opportunity {opportunity_id}")

    # =========================================================================
    # HEALTH CHECKS
    # =========================================================================

    @classmethod
    def check_all_databases(cls) -> Dict[str, bool]:
        """
        Check connectivity to all databases.
        Returns dict of database alias -> healthy status.
        """
        results = {}

        if getattr(settings, 'USE_SINGLE_DATABASE', True):
            # Single database mode
            try:
                connections['default'].ensure_connection()
                results['default'] = True
            except Exception as e:
                logger.error(f"Database default unhealthy: {e}")
                results['default'] = False
        else:
            # Multi-database mode
            db_aliases = [
                'default', cls.DB_ACCOUNTS, cls.DB_PROFILES,
                cls.DB_ORGANIZATIONS, cls.DB_APPLICATIONS,
                cls.DB_COMMUNICATIONS, cls.DB_ANALYTICS,
            ]

            for alias in db_aliases:
                try:
                    connections[alias].ensure_connection()
                    results[alias] = True
                except Exception as e:
                    logger.error(f"Database {alias} unhealthy: {e}")
                    results[alias] = False

        return results

