# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organizations Service
==========================================
Service layer for organization and opportunity operations.
"""
import logging
from typing import Optional, Dict, List
from uuid import UUID
from django.core.cache import cache
from django.db import models

logger = logging.getLogger('forgeforth.services.organizations')


class OrganizationsService:
    """
    Service for organizations-related operations.
    Provides a clean interface to the organizations database.
    """

    CACHE_TTL = 300  # 5 minutes

    @classmethod
    def get_organization(cls, org_id: UUID) -> Optional[Dict]:
        """Get organization by ID."""
        cache_key = f'org:{org_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from organizations.models import Organization

        try:
            org = Organization.objects.select_related('industry').get(id=org_id)
        except Organization.DoesNotExist:
            return None

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
            'country': org.country,
            'city': org.city,
            'status': org.status,
            'is_verified': org.status == 'verified',
            'is_hiring': org.is_hiring,
        }

        cache.set(cache_key, result, cls.CACHE_TTL)
        return result

    @classmethod
    def get_organization_by_slug(cls, slug: str) -> Optional[Dict]:
        """Get organization by slug."""
        from organizations.models import Organization

        try:
            org = Organization.objects.get(slug=slug)
            return cls.get_organization(org.id)
        except Organization.DoesNotExist:
            return None

    @classmethod
    def get_opportunity(cls, opportunity_id: UUID) -> Optional[Dict]:
        """Get opportunity by ID."""
        cache_key = f'opportunity:{opportunity_id}'
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
            'opportunity_type': opp.opportunity_type,
            'experience_level': opp.experience_level,
            'category': opp.category,
            'location': opp.location,
            'country': opp.country,
            'city': opp.city,
            'remote_policy': opp.remote_policy,
            'salary_display': opp.salary_display,
            'status': opp.status,
            'is_open': opp.is_open,
            'is_featured': opp.is_featured,
            'deadline': opp.deadline.isoformat() if opp.deadline else None,
            'published_at': opp.published_at.isoformat() if opp.published_at else None,
            'required_skills': opp.required_skills,
            'organization': {
                'id': str(opp.organization.id),
                'name': opp.organization.name,
                'slug': opp.organization.slug,
                'logo': opp.organization.logo.url if opp.organization.logo else None,
            },
        }

        cache.set(cache_key, result, cls.CACHE_TTL)
        return result

    @classmethod
    def list_opportunities(
        cls,
        organization_id: UUID = None,
        opportunity_type: str = None,
        status: str = 'open',
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """List opportunities with filters."""
        from organizations.models import Opportunity

        qs = Opportunity.objects.select_related('organization')

        if organization_id:
            qs = qs.filter(organization_id=organization_id)

        if opportunity_type:
            qs = qs.filter(opportunity_type=opportunity_type)

        if status:
            qs = qs.filter(status=status)

        total = qs.count()
        opportunities = qs.order_by('-is_featured', '-published_at')[offset:offset + limit]

        return {
            'total': total,
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
                }
                for o in opportunities
            ]
        }

    @classmethod
    def search_opportunities(
        cls,
        query: str = None,
        opportunity_type: str = None,
        location: str = None,
        remote_only: bool = False,
        experience_level: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """Search opportunities."""
        from organizations.models import Opportunity

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
                models.Q(country__icontains=location) |
                models.Q(location__icontains=location)
            )

        if remote_only:
            qs = qs.filter(remote_policy='remote')

        if experience_level:
            qs = qs.filter(experience_level=experience_level)

        total = qs.count()
        opportunities = qs.order_by('-is_featured', '-published_at')[offset:offset + limit]

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
                    'experience': o.experience_level,
                    'location': o.location or f"{o.city}, {o.country}" if o.city else o.country,
                    'remote': o.remote_policy,
                    'salary': o.salary_display,
                    'is_featured': o.is_featured,
                    'deadline': o.deadline.isoformat() if o.deadline else None,
                    'organization': {
                        'id': str(o.organization.id),
                        'name': o.organization.name,
                        'slug': o.organization.slug,
                        'logo': o.organization.logo.url if o.organization.logo else None,
                    },
                }
                for o in opportunities
            ]
        }

    @classmethod
    def increment_opportunity_views(cls, opportunity_id: UUID):
        """Increment opportunity view count."""
        from organizations.models import Opportunity
        from django.db.models import F

        Opportunity.objects.filter(id=opportunity_id).update(
            views_count=F('views_count') + 1
        )

    @classmethod
    def get_organization_members(cls, org_id: UUID) -> List[Dict]:
        """Get organization members."""
        from organizations.models import OrganizationMember

        members = OrganizationMember.objects.filter(
            organization_id=org_id,
            is_active=True
        ).select_related('user')

        return [
            {
                'user_id': str(m.user_id),
                'name': m.user.full_name,
                'email': m.user.email,
                'role': m.role,
                'title': m.title,
                'joined_at': m.joined_at.isoformat(),
            }
            for m in members
        ]

    @classmethod
    def invalidate_organization_cache(cls, org_id: UUID):
        """Invalidate cached organization data."""
        cache.delete(f'org:{org_id}')
        logger.info(f"Invalidated cache for organization {org_id}")

    @classmethod
    def invalidate_opportunity_cache(cls, opportunity_id: UUID):
        """Invalidate cached opportunity data."""
        cache.delete(f'opportunity:{opportunity_id}')
        logger.info(f"Invalidated cache for opportunity {opportunity_id}")

