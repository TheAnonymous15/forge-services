# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Profiles Views (MVP1)
==========================================
API endpoints for talent profiles, education, experience, skills, etc.
"""
from rest_framework import status, generics, permissions, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q
import logging

from .models import (
    TalentProfile, Education, WorkExperience, Skill, TalentSkill,
    Certification, TalentLanguage
)
from .serializers import (
    TalentProfileListSerializer, TalentProfileDetailSerializer,
    TalentProfileUpdateSerializer, PublicProfileSerializer,
    EducationSerializer, WorkExperienceSerializer, SkillSerializer,
    SkillCreateSerializer, CertificationSerializer, LanguageSerializer
)

logger = logging.getLogger('forgeforth.profiles')


# =============================================================================
# PERMISSIONS
# =============================================================================

class IsProfileOwner(permissions.BasePermission):
    """Permission to check if user owns the profile."""

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.user == request.user
        return obj.user == request.user


class IsProfileOwnerOrReadOnly(permissions.BasePermission):
    """Allow read for all, write only for owner."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, 'profile'):
            return obj.profile.user == request.user
        return obj.user == request.user


# =============================================================================
# PROFILE VIEWS
# =============================================================================

class MyProfileView(generics.RetrieveUpdateAPIView):
    """
    GET: Retrieve current user's profile
    PUT/PATCH: Update current user's profile
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TalentProfileUpdateSerializer
        return TalentProfileDetailSerializer

    def get_object(self):
        profile, created = TalentProfile.objects.get_or_create(user=self.request.user)
        if created:
            logger.info(f"Created profile for user {self.request.user.id}")
        return profile

    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Profile updated for user {self.request.user.id}")


class ProfileDetailView(generics.RetrieveAPIView):
    """View a public profile by ID."""
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicProfileSerializer
    queryset = TalentProfile.objects.filter(is_public=True)
    lookup_field = 'id'


class ProfileSearchView(generics.ListAPIView):
    """Search and list public profiles."""
    permission_classes = [permissions.AllowAny]
    serializer_class = TalentProfileListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['headline', 'bio', 'user__first_name', 'user__last_name', 'city', 'country']
    ordering_fields = ['created_at', 'updated_at', 'completion_percentage']
    ordering = ['-updated_at']

    def get_queryset(self):
        queryset = TalentProfile.objects.filter(
            is_public=True,
            open_to_opportunities=True
        ).select_related('user').prefetch_related('skills')

        # Filter by skills
        skills = self.request.query_params.get('skills')
        if skills:
            skill_list = [s.strip() for s in skills.split(',')]
            queryset = queryset.filter(skills__name__in=skill_list).distinct()

        # Filter by availability
        availability = self.request.query_params.get('availability')
        if availability:
            queryset = queryset.filter(availability=availability)

        # Filter by remote preference
        remote = self.request.query_params.get('remote')
        if remote:
            queryset = queryset.filter(remote_preference=remote)

        # Filter by country
        country = self.request.query_params.get('country')
        if country:
            queryset = queryset.filter(country__icontains=country)

        # Filter by city
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)

        return queryset


# =============================================================================
# EDUCATION VIEWS
# =============================================================================

class EducationListCreateView(generics.ListCreateAPIView):
    """List and create education entries for current user."""
    serializer_class = EducationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Education.objects.filter(profile__user=self.request.user).order_by('-start_date')

    def perform_create(self, serializer):
        profile = get_object_or_404(TalentProfile, user=self.request.user)
        serializer.save(profile=profile)
        logger.info(f"Education added for user {self.request.user.id}")


class EducationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an education entry."""
    serializer_class = EducationSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileOwner]
    lookup_field = 'id'

    def get_queryset(self):
        return Education.objects.filter(profile__user=self.request.user)

    def perform_destroy(self, instance):
        logger.info(f"Education {instance.id} deleted for user {self.request.user.id}")
        instance.delete()


# =============================================================================
# WORK EXPERIENCE VIEWS
# =============================================================================

class WorkExperienceListCreateView(generics.ListCreateAPIView):
    """List and create work experience entries for current user."""
    serializer_class = WorkExperienceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WorkExperience.objects.filter(profile__user=self.request.user).order_by('-start_date')

    def perform_create(self, serializer):
        profile = get_object_or_404(TalentProfile, user=self.request.user)
        serializer.save(profile=profile)
        logger.info(f"Work experience added for user {self.request.user.id}")


class WorkExperienceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a work experience entry."""
    serializer_class = WorkExperienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileOwner]
    lookup_field = 'id'

    def get_queryset(self):
        return WorkExperience.objects.filter(profile__user=self.request.user)


# =============================================================================
# SKILLS VIEWS
# =============================================================================

class SkillListCreateView(generics.ListAPIView):
    """List skills for current user."""
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TalentSkill.objects.filter(profile__user=self.request.user).select_related('skill').order_by('-is_primary', 'skill__name')


class SkillDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a skill."""
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileOwner]
    lookup_field = 'id'

    def get_queryset(self):
        return TalentSkill.objects.filter(profile__user=self.request.user)


class BulkSkillsView(APIView):
    """Add multiple skills at once."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.utils.text import slugify

        profile = get_object_or_404(TalentProfile, user=request.user)
        skills_data = request.data.get('skills', [])

        if not isinstance(skills_data, list):
            return Response(
                {'error': 'Skills must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_skills = []
        for skill_data in skills_data:
            if isinstance(skill_data, str):
                skill_data = {'name': skill_data}

            serializer = SkillCreateSerializer(data=skill_data)
            if serializer.is_valid():
                name = serializer.validated_data['name']

                # Get or create the skill
                skill, _ = Skill.objects.get_or_create(
                    slug=slugify(name),
                    defaults={
                        'name': name,
                        'category': serializer.validated_data.get('category', '')
                    }
                )

                # Check if talent already has this skill
                existing = TalentSkill.objects.filter(
                    profile=profile,
                    skill=skill
                ).first()

                if not existing:
                    talent_skill = TalentSkill.objects.create(
                        profile=profile,
                        skill=skill,
                        level=serializer.validated_data.get('level', 'intermediate'),
                        years_of_experience=serializer.validated_data.get('years_of_experience', 0),
                        is_primary=serializer.validated_data.get('is_primary', False)
                    )
                    created_skills.append(SkillSerializer(talent_skill).data)

        return Response({
            'created': len(created_skills),
            'skills': created_skills
        }, status=status.HTTP_201_CREATED)


# =============================================================================
# CERTIFICATIONS VIEWS
# =============================================================================

class CertificationListCreateView(generics.ListCreateAPIView):
    """List and create certifications for current user."""
    serializer_class = CertificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Certification.objects.filter(profile__user=self.request.user).order_by('-issue_date')

    def perform_create(self, serializer):
        profile = get_object_or_404(TalentProfile, user=self.request.user)
        serializer.save(profile=profile)


class CertificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a certification."""
    serializer_class = CertificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileOwner]
    lookup_field = 'id'

    def get_queryset(self):
        return Certification.objects.filter(profile__user=self.request.user)


# =============================================================================
# LANGUAGES VIEWS
# =============================================================================

class LanguageListCreateView(generics.ListCreateAPIView):
    """List and create languages for current user."""
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TalentLanguage.objects.filter(profile__user=self.request.user).order_by('language')

    def perform_create(self, serializer):
        profile = get_object_or_404(TalentProfile, user=self.request.user)
        serializer.save(profile=profile)


class LanguageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a language."""
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileOwner]
    lookup_field = 'id'

    def get_queryset(self):
        return TalentLanguage.objects.filter(profile__user=self.request.user)


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def profile_completion(request):
    """Get profile completion status."""
    profile = get_object_or_404(TalentProfile, user=request.user)

    # Update completion score
    profile.calculate_completeness()
    profile.save(update_fields=['completeness_score'])

    # Calculate completion breakdown
    completion = {
        'percentage': profile.completeness_score,
        'sections': {
            'basic_info': bool(profile.headline and profile.bio),
            'contact': bool(profile.phone_number),
            'location': bool(profile.country and profile.city),
            'education': profile.education.exists(),
            'experience': profile.work_experience.exists(),
            'skills': profile.skills.count() >= 3,
            'preferences': bool(profile.availability and profile.remote_preference),
        }
    }

    # Suggestions
    suggestions = []
    if not completion['sections']['basic_info']:
        suggestions.append('Add a headline and bio to introduce yourself')
    if not completion['sections']['education']:
        suggestions.append('Add your education history')
    if not completion['sections']['experience']:
        suggestions.append('Add your work experience')
    if not completion['sections']['skills']:
        suggestions.append('Add at least 3 skills')

    completion['suggestions'] = suggestions

    return Response(completion)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def profiles_health(request):
    """Health check for profiles service."""
    return Response({
        'status': 'healthy',
        'service': 'profiles',
        'total_profiles': TalentProfile.objects.count(),
        'public_profiles': TalentProfile.objects.filter(is_public=True).count(),
    })

