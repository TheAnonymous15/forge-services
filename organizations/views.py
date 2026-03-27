# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organizations Views (MVP1)
===============================================
API endpoints for organizations, opportunities, and members.
"""
from rest_framework import status, generics, permissions, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, F
import logging

from .models import (
    Industry, Organization, OrganizationMember, Opportunity
)
from .serializers import (
    IndustrySerializer,
    OrganizationListSerializer, OrganizationDetailSerializer,
    OrganizationCreateSerializer, OrganizationUpdateSerializer,
    OrganizationMemberSerializer, InviteMemberSerializer,
    OpportunityListSerializer, OpportunityDetailSerializer,
    OpportunityCreateSerializer, OpportunityUpdateSerializer,
    OpportunityPublishSerializer
)

logger = logging.getLogger('forgeforth.organizations')


# =============================================================================
# PERMISSIONS
# =============================================================================

class IsOrganizationMember(permissions.BasePermission):
    """Check if user is a member of the organization."""

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Organization):
            org = obj
        elif hasattr(obj, 'organization'):
            org = obj.organization
        else:
            return False

        return OrganizationMember.objects.filter(
            organization=org,
            user=request.user,
            is_active=True
        ).exists()


class IsOrganizationAdmin(permissions.BasePermission):
    """Check if user is an admin of the organization."""

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Organization):
            org = obj
        elif hasattr(obj, 'organization'):
            org = obj.organization
        else:
            return False

        return OrganizationMember.objects.filter(
            organization=org,
            user=request.user,
            role__in=['owner', 'admin'],
            is_active=True
        ).exists()


class CanManageOpportunities(permissions.BasePermission):
    """Check if user can manage opportunities."""

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Opportunity):
            org = obj.organization
        elif isinstance(obj, Organization):
            org = obj
        else:
            return False

        return OrganizationMember.objects.filter(
            organization=org,
            user=request.user,
            role__in=['owner', 'admin', 'recruiter', 'hiring_manager'],
            is_active=True
        ).exists()


# =============================================================================
# INDUSTRY VIEWS
# =============================================================================

class IndustryListView(generics.ListAPIView):
    """List all industries."""
    queryset = Industry.objects.filter(is_active=True).order_by('name')
    serializer_class = IndustrySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None  # Return all industries


# =============================================================================
# ORGANIZATION VIEWS
# =============================================================================

class OrganizationListView(generics.ListAPIView):
    """List public organizations."""
    serializer_class = OrganizationListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'tagline', 'description', 'city', 'country']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        queryset = Organization.objects.filter(
            is_public=True,
            status='verified'
        ).select_related('industry')

        # Filter by industry
        industry = self.request.query_params.get('industry')
        if industry:
            queryset = queryset.filter(industry__slug=industry)

        # Filter by type
        org_type = self.request.query_params.get('type')
        if org_type:
            queryset = queryset.filter(org_type=org_type)

        # Filter by hiring status
        is_hiring = self.request.query_params.get('is_hiring')
        if is_hiring:
            queryset = queryset.filter(is_hiring=True)

        # Filter by country
        country = self.request.query_params.get('country')
        if country:
            queryset = queryset.filter(country__icontains=country)

        return queryset


class OrganizationDetailView(generics.RetrieveAPIView):
    """View organization details by slug."""
    serializer_class = OrganizationDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return Organization.objects.filter(is_public=True, status='verified')


class OrganizationCreateView(generics.CreateAPIView):
    """Create a new organization."""
    serializer_class = OrganizationCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        org = serializer.save(status='pending')

        # Make creator the owner
        OrganizationMember.objects.create(
            organization=org,
            user=self.request.user,
            role='owner',
            is_active=True
        )

        # Update user role
        user = self.request.user
        if user.role == 'talent':
            user.role = 'employer'
            user.save(update_fields=['role'])

        logger.info(f"Organization {org.id} created by user {self.request.user.id}")


class MyOrganizationsView(generics.ListAPIView):
    """List organizations the current user belongs to."""
    serializer_class = OrganizationListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Organization.objects.filter(
            members__user=self.request.user,
            members__is_active=True
        ).distinct()


class OrganizationManageView(generics.RetrieveUpdateAPIView):
    """Retrieve and update organization (for members)."""
    permission_classes = [permissions.IsAuthenticated, IsOrganizationAdmin]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return OrganizationUpdateSerializer
        return OrganizationDetailSerializer

    def get_queryset(self):
        return Organization.objects.filter(
            members__user=self.request.user,
            members__is_active=True
        )


# =============================================================================
# ORGANIZATION MEMBER VIEWS
# =============================================================================

class OrganizationMembersView(generics.ListAPIView):
    """List organization members."""
    serializer_class = OrganizationMemberSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        org_slug = self.kwargs.get('slug')
        return OrganizationMember.objects.filter(
            organization__slug=org_slug,
            is_active=True
        ).select_related('user')


class InviteMemberView(APIView):
    """Invite a new member to the organization."""
    permission_classes = [permissions.IsAuthenticated, IsOrganizationAdmin]

    def post(self, request, slug):
        org = get_object_or_404(Organization, slug=slug)
        self.check_object_permissions(request, org)

        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from accounts.models import User

        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()

        if not user:
            return Response(
                {'error': 'User with this email not found. They must register first.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if already a member
        if OrganizationMember.objects.filter(organization=org, user=user).exists():
            return Response(
                {'error': 'User is already a member of this organization.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create membership
        member = OrganizationMember.objects.create(
            organization=org,
            user=user,
            role=serializer.validated_data['role'],
            title=serializer.validated_data.get('title', ''),
            is_active=True
        )

        logger.info(f"User {user.id} invited to org {org.id} by {request.user.id}")

        return Response(
            OrganizationMemberSerializer(member).data,
            status=status.HTTP_201_CREATED
        )


class RemoveMemberView(APIView):
    """Remove a member from the organization."""
    permission_classes = [permissions.IsAuthenticated, IsOrganizationAdmin]

    def delete(self, request, slug, member_id):
        org = get_object_or_404(Organization, slug=slug)
        self.check_object_permissions(request, org)

        member = get_object_or_404(OrganizationMember, id=member_id, organization=org)

        # Can't remove owner
        if member.role == 'owner':
            return Response(
                {'error': 'Cannot remove the organization owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member.is_active = False
        member.save(update_fields=['is_active'])

        logger.info(f"Member {member_id} removed from org {org.id} by {request.user.id}")

        return Response(status=status.HTTP_204_NO_CONTENT)


# =============================================================================
# OPPORTUNITY VIEWS
# =============================================================================

class OpportunitySearchView(generics.ListAPIView):
    """Search and list public opportunities."""
    serializer_class = OpportunityListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'organization__name', 'city', 'country']
    ordering_fields = ['published_at', 'deadline', 'salary_min']
    ordering = ['-is_featured', '-published_at']

    def get_queryset(self):
        queryset = Opportunity.objects.filter(
            status='open',
            organization__is_public=True,
            organization__status='verified'
        ).select_related('organization')

        # Filter by type
        opp_type = self.request.query_params.get('type')
        if opp_type:
            queryset = queryset.filter(opportunity_type=opp_type)

        # Filter by experience level
        experience = self.request.query_params.get('experience')
        if experience:
            queryset = queryset.filter(experience_level=experience)

        # Filter by remote policy
        remote = self.request.query_params.get('remote')
        if remote:
            queryset = queryset.filter(remote_policy=remote)

        # Filter by country
        country = self.request.query_params.get('country')
        if country:
            queryset = queryset.filter(
                Q(country__icontains=country) | Q(location__icontains=country)
            )

        # Filter by skills
        skills = self.request.query_params.get('skills')
        if skills:
            skill_list = [s.strip().lower() for s in skills.split(',')]
            for skill in skill_list:
                queryset = queryset.filter(required_skills__icontains=skill)

        # Filter by salary range
        min_salary = self.request.query_params.get('min_salary')
        if min_salary:
            queryset = queryset.filter(salary_min__gte=min_salary)

        return queryset


class OpportunityDetailView(generics.RetrieveAPIView):
    """View opportunity details."""
    serializer_class = OpportunityDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return Opportunity.objects.filter(
            status='open',
            organization__is_public=True
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Increment view count
        Opportunity.objects.filter(pk=instance.pk).update(views_count=F('views_count') + 1)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class OrganizationOpportunitiesView(generics.ListCreateAPIView):
    """List and create opportunities for an organization."""
    permission_classes = [permissions.IsAuthenticated, CanManageOpportunities]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OpportunityCreateSerializer
        return OpportunityListSerializer

    def get_queryset(self):
        org_slug = self.kwargs.get('slug')
        return Opportunity.objects.filter(
            organization__slug=org_slug,
            organization__members__user=self.request.user,
            organization__members__is_active=True
        ).distinct()

    def perform_create(self, serializer):
        org_slug = self.kwargs.get('slug')
        org = get_object_or_404(Organization, slug=org_slug)
        self.check_object_permissions(self.request, org)

        opp = serializer.save(
            organization=org,
            created_by=self.request.user,
            status='draft'
        )
        logger.info(f"Opportunity {opp.id} created by user {self.request.user.id}")


class OpportunityManageView(generics.RetrieveUpdateDestroyAPIView):
    """Manage a specific opportunity."""
    permission_classes = [permissions.IsAuthenticated, CanManageOpportunities]
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return OpportunityUpdateSerializer
        return OpportunityDetailSerializer

    def get_queryset(self):
        return Opportunity.objects.filter(
            organization__members__user=self.request.user,
            organization__members__is_active=True
        ).distinct()

    def perform_destroy(self, instance):
        logger.info(f"Opportunity {instance.id} deleted by user {self.request.user.id}")
        instance.delete()


class OpportunityPublishView(APIView):
    """Publish, unpublish, or close an opportunity."""
    permission_classes = [permissions.IsAuthenticated, CanManageOpportunities]

    def post(self, request, id):
        opportunity = get_object_or_404(Opportunity, id=id)
        self.check_object_permissions(request, opportunity)

        serializer = OpportunityPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']

        if action == 'publish':
            if opportunity.status == 'open':
                return Response({'error': 'Opportunity is already published.'}, status=400)
            opportunity.status = 'open'
            opportunity.published_at = timezone.now()
        elif action == 'unpublish':
            opportunity.status = 'draft'
        elif action == 'close':
            opportunity.status = 'closed'

        opportunity.save(update_fields=['status', 'published_at', 'updated_at'])
        logger.info(f"Opportunity {id} {action}ed by user {request.user.id}")

        return Response(OpportunityDetailSerializer(opportunity).data)


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def organizations_health(request):
    """Health check for organizations service."""
    return Response({
        'status': 'healthy',
        'service': 'organizations',
        'total_organizations': Organization.objects.filter(status='verified').count(),
        'open_opportunities': Opportunity.objects.filter(status='open').count(),
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def opportunity_stats(request):
    """Get opportunity statistics."""
    from django.db.models import Count

    stats = {
        'total_open': Opportunity.objects.filter(status='open').count(),
        'by_type': dict(
            Opportunity.objects.filter(status='open')
            .values('opportunity_type')
            .annotate(count=Count('id'))
            .values_list('opportunity_type', 'count')
        ),
        'by_experience': dict(
            Opportunity.objects.filter(status='open')
            .values('experience_level')
            .annotate(count=Count('id'))
            .values_list('experience_level', 'count')
        ),
        'by_remote': dict(
            Opportunity.objects.filter(status='open')
            .values('remote_policy')
            .annotate(count=Count('id'))
            .values_list('remote_policy', 'count')
        ),
    }

    return Response(stats)

