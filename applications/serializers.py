# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Applications Serializers (MVP1)
====================================================
Serializers for applications, interviews, and related entities.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import (
    Application, ApplicationStatusHistory, Interview,
    ApplicationNote, SavedOpportunity
)


# =============================================================================
# APPLICATION SERIALIZERS
# =============================================================================

class ApplicationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for application listings."""
    applicant_name = serializers.CharField(source='applicant.full_name', read_only=True)
    applicant_email = serializers.EmailField(source='applicant.email', read_only=True)
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    organization_name = serializers.CharField(source='opportunity.organization.name', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'applicant_name', 'applicant_email',
            'opportunity_title', 'organization_name',
            'status', 'score', 'match_score',
            'is_starred', 'submitted_at', 'created_at'
        ]


class ApplicationDetailSerializer(serializers.ModelSerializer):
    """Full application serializer."""
    applicant_name = serializers.CharField(source='applicant.full_name', read_only=True)
    applicant_email = serializers.EmailField(source='applicant.email', read_only=True)
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    organization_name = serializers.CharField(source='opportunity.organization.name', read_only=True)
    can_withdraw = serializers.BooleanField(read_only=True)
    interviews_count = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id', 'applicant', 'applicant_name', 'applicant_email',
            'opportunity', 'opportunity_title', 'organization_name',
            'cover_letter', 'resume', 'portfolio_url', 'answers',
            'status', 'score', 'match_score',
            'is_starred', 'is_archived', 'can_withdraw',
            'interviews_count',
            'submitted_at', 'reviewed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'applicant', 'opportunity', 'status', 'score', 'match_score',
            'submitted_at', 'reviewed_at', 'created_at', 'updated_at'
        ]

    def get_interviews_count(self, obj):
        return obj.interviews.count()


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating applications."""

    class Meta:
        model = Application
        fields = [
            'opportunity', 'cover_letter', 'resume', 'portfolio_url', 'answers'
        ]

    def validate_opportunity(self, value):
        # Check if opportunity is open
        if value.status != 'open':
            raise serializers.ValidationError('This opportunity is no longer accepting applications.')

        # Check deadline
        if value.deadline and value.deadline < timezone.now().date():
            raise serializers.ValidationError('The application deadline has passed.')

        return value

    def validate(self, data):
        user = self.context['request'].user
        opportunity = data.get('opportunity')

        # Check if already applied
        if Application.objects.filter(applicant=user, opportunity=opportunity).exists():
            raise serializers.ValidationError({
                'opportunity': 'You have already applied to this opportunity.'
            })

        return data


class ApplicationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating draft applications."""

    class Meta:
        model = Application
        fields = ['cover_letter', 'resume', 'portfolio_url', 'answers']


class ApplicationReviewSerializer(serializers.ModelSerializer):
    """Serializer for employer review actions."""

    class Meta:
        model = Application
        fields = ['status', 'score', 'internal_notes', 'rejection_reason', 'is_starred']

    def validate_status(self, value):
        instance = self.instance
        if instance:
            # Validate status transitions
            valid_transitions = {
                'submitted': ['under_review', 'rejected'],
                'under_review': ['shortlisted', 'rejected'],
                'shortlisted': ['interview', 'rejected'],
                'interview': ['assessment', 'offer', 'rejected'],
                'assessment': ['offer', 'rejected'],
                'offer': ['accepted', 'rejected'],
            }

            current = instance.status
            allowed = valid_transitions.get(current, [])

            if value not in allowed and value != current:
                raise serializers.ValidationError(
                    f'Cannot transition from {current} to {value}. Allowed: {allowed}'
                )

        return value


# =============================================================================
# INTERVIEW SERIALIZERS
# =============================================================================

class InterviewSerializer(serializers.ModelSerializer):
    """Serializer for interviews."""
    interviewer_names = serializers.SerializerMethodField()

    class Meta:
        model = Interview
        fields = [
            'id', 'application', 'interview_type', 'title', 'description',
            'scheduled_at', 'duration_minutes', 'timezone',
            'location', 'meeting_link',
            'interviewers', 'interviewer_names',
            'status', 'feedback', 'rating',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_interviewer_names(self, obj):
        return [i.full_name for i in obj.interviewers.all()]


class InterviewCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating interviews."""

    class Meta:
        model = Interview
        fields = [
            'application', 'interview_type', 'title', 'description',
            'scheduled_at', 'duration_minutes', 'timezone',
            'location', 'meeting_link', 'meeting_password',
            'interviewers'
        ]

    def validate_scheduled_at(self, value):
        if value < timezone.now():
            raise serializers.ValidationError('Interview cannot be scheduled in the past.')
        return value


class InterviewFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for interview feedback."""

    class Meta:
        model = Interview
        fields = ['status', 'feedback', 'rating']

    def validate_rating(self, value):
        if value and (value < 1 or value > 5):
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value


# =============================================================================
# NOTE SERIALIZERS
# =============================================================================

class ApplicationNoteSerializer(serializers.ModelSerializer):
    """Serializer for application notes."""
    author_name = serializers.CharField(source='author.full_name', read_only=True)

    class Meta:
        model = ApplicationNote
        fields = ['id', 'content', 'is_private', 'author', 'author_name', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


# =============================================================================
# SAVED OPPORTUNITY SERIALIZERS
# =============================================================================

class SavedOpportunitySerializer(serializers.ModelSerializer):
    """Serializer for saved opportunities."""
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    organization_name = serializers.CharField(source='opportunity.organization.name', read_only=True)
    opportunity_status = serializers.CharField(source='opportunity.status', read_only=True)

    class Meta:
        model = SavedOpportunity
        fields = [
            'id', 'opportunity', 'opportunity_title', 'organization_name',
            'opportunity_status', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# =============================================================================
# STATUS HISTORY SERIALIZER
# =============================================================================

class StatusHistorySerializer(serializers.ModelSerializer):
    """Serializer for status history."""
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True)

    class Meta:
        model = ApplicationStatusHistory
        fields = [
            'id', 'from_status', 'to_status',
            'changed_by', 'changed_by_name', 'notes', 'created_at'
        ]

