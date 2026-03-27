# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Applications Views (MVP1)
==============================================
API endpoints for applications, interviews, and workflow management.
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
    Application, ApplicationStatusHistory, Interview,
    ApplicationNote, SavedOpportunity, ApplicationStatus
)
from .serializers import (
    ApplicationListSerializer, ApplicationDetailSerializer,
    ApplicationCreateSerializer, ApplicationUpdateSerializer,
    ApplicationReviewSerializer,
    InterviewSerializer, InterviewCreateSerializer, InterviewFeedbackSerializer,
    ApplicationNoteSerializer, SavedOpportunitySerializer,
    StatusHistorySerializer
)
from organizations.models import Organization, Opportunity, OrganizationMember

logger = logging.getLogger('forgeforth.applications')


# =============================================================================
# PERMISSIONS
# =============================================================================

class IsApplicant(permissions.BasePermission):
    """Check if user is the applicant."""

    def has_object_permission(self, request, view, obj):
        return obj.applicant == request.user


class IsOrgMemberForApplication(permissions.BasePermission):
    """Check if user is a member of the opportunity's organization."""

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'opportunity'):
            org = obj.opportunity.organization
        elif hasattr(obj, 'application'):
            org = obj.application.opportunity.organization
        else:
            return False

        return OrganizationMember.objects.filter(
            organization=org,
            user=request.user,
            is_active=True
        ).exists()


# =============================================================================
# APPLICANT VIEWS (for talents)
# =============================================================================

class MyApplicationsView(generics.ListAPIView):
    """List current user's applications."""
    serializer_class = ApplicationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'submitted_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Application.objects.filter(
            applicant=self.request.user
        ).select_related('opportunity', 'opportunity__organization')

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by archived
        show_archived = self.request.query_params.get('archived')
        if show_archived != 'true':
            queryset = queryset.filter(is_archived=False)

        return queryset


class ApplicationCreateView(generics.CreateAPIView):
    """Create a new application."""
    serializer_class = ApplicationCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        application = serializer.save(
            applicant=self.request.user,
            status=ApplicationStatus.DRAFT
        )

        # Log status history
        ApplicationStatusHistory.objects.create(
            application=application,
            to_status=ApplicationStatus.DRAFT,
            changed_by=self.request.user,
            notes='Application created'
        )

        logger.info(f"Application {application.id} created by user {self.request.user.id}")


class ApplicationDetailView(generics.RetrieveUpdateAPIView):
    """View and update own application."""
    permission_classes = [permissions.IsAuthenticated, IsApplicant]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ApplicationUpdateSerializer
        return ApplicationDetailSerializer

    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status != ApplicationStatus.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Can only update draft applications.')
        serializer.save()


class SubmitApplicationView(APIView):
    """Submit a draft application."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        application = get_object_or_404(Application, id=id, applicant=request.user)

        if application.status != ApplicationStatus.DRAFT:
            return Response(
                {'error': 'Application has already been submitted.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate application has required content
        if not application.cover_letter and not application.resume:
            return Response(
                {'error': 'Please provide a cover letter or resume before submitting.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = application.status
        application.status = ApplicationStatus.SUBMITTED
        application.submitted_at = timezone.now()
        application.save(update_fields=['status', 'submitted_at', 'updated_at'])

        # Update opportunity application count
        Opportunity.objects.filter(pk=application.opportunity_id).update(
            applications_count=F('applications_count') + 1
        )

        # Log status history
        ApplicationStatusHistory.objects.create(
            application=application,
            from_status=old_status,
            to_status=ApplicationStatus.SUBMITTED,
            changed_by=request.user,
            notes='Application submitted'
        )

        logger.info(f"Application {id} submitted by user {request.user.id}")

        return Response(ApplicationDetailSerializer(application).data)


class WithdrawApplicationView(APIView):
    """Withdraw an application."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        application = get_object_or_404(Application, id=id, applicant=request.user)

        if not application.can_withdraw:
            return Response(
                {'error': 'This application cannot be withdrawn at this stage.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = application.status
        application.status = ApplicationStatus.WITHDRAWN
        application.save(update_fields=['status', 'updated_at'])

        # Log status history
        ApplicationStatusHistory.objects.create(
            application=application,
            from_status=old_status,
            to_status=ApplicationStatus.WITHDRAWN,
            changed_by=request.user,
            notes=request.data.get('reason', 'Application withdrawn by applicant')
        )

        logger.info(f"Application {id} withdrawn by user {request.user.id}")

        return Response(ApplicationDetailSerializer(application).data)


# =============================================================================
# EMPLOYER VIEWS (for organizations)
# =============================================================================

class OpportunityApplicationsView(generics.ListAPIView):
    """List applications for an opportunity."""
    serializer_class = ApplicationListSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrgMemberForApplication]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'submitted_at', 'score', 'match_score']
    ordering = ['-submitted_at']

    def get_queryset(self):
        opp_id = self.kwargs.get('opportunity_id')
        queryset = Application.objects.filter(
            opportunity_id=opp_id
        ).exclude(
            status=ApplicationStatus.DRAFT
        ).select_related('applicant')

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter starred
        starred = self.request.query_params.get('starred')
        if starred == 'true':
            queryset = queryset.filter(is_starred=True)

        return queryset


class ReviewApplicationView(generics.RetrieveUpdateAPIView):
    """Review and update application status."""
    serializer_class = ApplicationReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrgMemberForApplication]
    lookup_field = 'id'

    def get_queryset(self):
        return Application.objects.exclude(status=ApplicationStatus.DRAFT)

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ApplicationDetailSerializer
        return ApplicationReviewSerializer

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status

        updated = serializer.save(
            reviewed_by=self.request.user,
            reviewed_at=timezone.now()
        )

        # Log status change if status changed
        new_status = updated.status
        if old_status != new_status:
            ApplicationStatusHistory.objects.create(
                application=updated,
                from_status=old_status,
                to_status=new_status,
                changed_by=self.request.user,
                notes=self.request.data.get('notes', '')
            )

            logger.info(
                f"Application {updated.id} status changed from {old_status} to {new_status} "
                f"by user {self.request.user.id}"
            )


class BulkReviewView(APIView):
    """Bulk update application status."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        application_ids = request.data.get('application_ids', [])
        new_status = request.data.get('status')
        notes = request.data.get('notes', '')

        if not application_ids or not new_status:
            return Response(
                {'error': 'application_ids and status are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate status
        valid_statuses = [s[0] for s in ApplicationStatus.choices]
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_count = 0
        for app_id in application_ids:
            try:
                application = Application.objects.get(id=app_id)

                # Check permission
                if not OrganizationMember.objects.filter(
                    organization=application.opportunity.organization,
                    user=request.user,
                    is_active=True
                ).exists():
                    continue

                old_status = application.status
                application.status = new_status
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.save()

                ApplicationStatusHistory.objects.create(
                    application=application,
                    from_status=old_status,
                    to_status=new_status,
                    changed_by=request.user,
                    notes=notes
                )

                updated_count += 1
            except Application.DoesNotExist:
                continue

        return Response({'updated': updated_count})


# =============================================================================
# INTERVIEW VIEWS
# =============================================================================

class InterviewListCreateView(generics.ListCreateAPIView):
    """List and create interviews for an application."""
    permission_classes = [permissions.IsAuthenticated, IsOrgMemberForApplication]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return InterviewCreateSerializer
        return InterviewSerializer

    def get_queryset(self):
        app_id = self.kwargs.get('application_id')
        return Interview.objects.filter(application_id=app_id)

    def perform_create(self, serializer):
        app_id = self.kwargs.get('application_id')
        application = get_object_or_404(Application, id=app_id)

        interview = serializer.save(
            application=application,
            created_by=self.request.user
        )

        # Update application status if needed
        if application.status == ApplicationStatus.SHORTLISTED:
            old_status = application.status
            application.status = ApplicationStatus.INTERVIEW
            application.save(update_fields=['status', 'updated_at'])

            ApplicationStatusHistory.objects.create(
                application=application,
                from_status=old_status,
                to_status=ApplicationStatus.INTERVIEW,
                changed_by=self.request.user,
                notes='Interview scheduled'
            )

        logger.info(f"Interview {interview.id} created for application {app_id}")


class InterviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Manage a specific interview."""
    serializer_class = InterviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrgMemberForApplication]
    lookup_field = 'id'

    def get_queryset(self):
        return Interview.objects.all()


class InterviewFeedbackView(APIView):
    """Add feedback to an interview."""
    permission_classes = [permissions.IsAuthenticated, IsOrgMemberForApplication]

    def post(self, request, id):
        interview = get_object_or_404(Interview, id=id)
        self.check_object_permissions(request, interview)

        serializer = InterviewFeedbackSerializer(interview, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(InterviewSerializer(interview).data)


# =============================================================================
# NOTES VIEWS
# =============================================================================

class ApplicationNotesView(generics.ListCreateAPIView):
    """List and create notes for an application."""
    serializer_class = ApplicationNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrgMemberForApplication]

    def get_queryset(self):
        app_id = self.kwargs.get('application_id')
        return ApplicationNote.objects.filter(application_id=app_id)

    def perform_create(self, serializer):
        app_id = self.kwargs.get('application_id')
        application = get_object_or_404(Application, id=app_id)
        serializer.save(application=application, author=self.request.user)


# =============================================================================
# SAVED OPPORTUNITIES VIEWS
# =============================================================================

class SavedOpportunitiesView(generics.ListCreateAPIView):
    """List and save opportunities."""
    serializer_class = SavedOpportunitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedOpportunity.objects.filter(
            user=self.request.user
        ).select_related('opportunity', 'opportunity__organization')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UnsaveOpportunityView(APIView):
    """Remove a saved opportunity."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, opportunity_id):
        saved = get_object_or_404(
            SavedOpportunity,
            user=request.user,
            opportunity_id=opportunity_id
        )
        saved.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =============================================================================
# STATUS HISTORY VIEW
# =============================================================================

class ApplicationHistoryView(generics.ListAPIView):
    """View application status history."""
    serializer_class = StatusHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        app_id = self.kwargs.get('application_id')
        application = get_object_or_404(Application, id=app_id)

        # Check if user is applicant or org member
        if application.applicant != self.request.user:
            if not OrganizationMember.objects.filter(
                organization=application.opportunity.organization,
                user=self.request.user,
                is_active=True
            ).exists():
                return ApplicationStatusHistory.objects.none()

        return ApplicationStatusHistory.objects.filter(application_id=app_id)


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def applications_health(request):
    """Health check for applications service."""
    return Response({
        'status': 'healthy',
        'service': 'applications',
        'total_applications': Application.objects.count(),
        'pending_review': Application.objects.filter(status=ApplicationStatus.SUBMITTED).count(),
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_application_stats(request):
    """Get application statistics for current user."""
    from django.db.models import Count

    apps = Application.objects.filter(applicant=request.user)

    stats = {
        'total': apps.count(),
        'by_status': dict(
            apps.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        ),
        'interviews_scheduled': Interview.objects.filter(
            application__applicant=request.user,
            status='scheduled'
        ).count(),
        'saved_opportunities': SavedOpportunity.objects.filter(user=request.user).count(),
    }

    return Response(stats)

