# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organizations Serializers (MVP1)
=====================================================
Serializers for organizations, opportunities, and members.
"""
from rest_framework import serializers
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Industry, Organization, OrganizationMember, Opportunity
)


# =============================================================================
# INDUSTRY SERIALIZER
# =============================================================================

class IndustrySerializer(serializers.ModelSerializer):
    """Serializer for industries."""

    class Meta:
        model = Industry
        fields = ['id', 'name', 'slug', 'description', 'icon']
        read_only_fields = ['id', 'slug']


# =============================================================================
# ORGANIZATION SERIALIZERS
# =============================================================================

class OrganizationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for organization listings."""
    industry_name = serializers.CharField(source='industry.name', read_only=True)
    opportunities_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'slug', 'tagline', 'logo',
            'org_type', 'industry_name', 'size', 'country', 'city',
            'status', 'is_hiring', 'opportunities_count'
        ]

    def get_opportunities_count(self, obj):
        return obj.opportunities.filter(status='open').count()


class OrganizationDetailSerializer(serializers.ModelSerializer):
    """Full organization serializer."""
    industry = IndustrySerializer(read_only=True)
    industry_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    open_opportunities = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'slug', 'tagline', 'description',
            'org_type', 'industry', 'industry_id', 'size', 'founded_year',
            'logo', 'cover_image', 'brand_color',
            'email', 'phone', 'website',
            'linkedin_url', 'twitter_url', 'facebook_url',
            'country', 'state_province', 'city', 'address', 'postal_code',
            'status', 'is_public', 'is_hiring',
            'employee_count', 'culture_description', 'benefits',
            'open_opportunities', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'status', 'created_at', 'updated_at']

    def get_open_opportunities(self, obj):
        opportunities = obj.opportunities.filter(status='open')[:5]
        return OpportunityListSerializer(opportunities, many=True).data


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating organizations."""
    industry_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Organization
        fields = [
            'name', 'tagline', 'description',
            'org_type', 'industry_id', 'size', 'founded_year',
            'logo', 'email', 'phone', 'website',
            'country', 'state_province', 'city', 'address', 'postal_code',
        ]

    def validate_name(self, value):
        # Check for duplicate names
        slug = slugify(value)
        if Organization.objects.filter(slug=slug).exists():
            raise serializers.ValidationError('An organization with this name already exists.')
        return value

    def create(self, validated_data):
        industry_id = validated_data.pop('industry_id', None)
        validated_data['slug'] = slugify(validated_data['name'])

        if industry_id:
            validated_data['industry_id'] = industry_id

        return super().create(validated_data)


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating organizations."""
    industry_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Organization
        fields = [
            'name', 'tagline', 'description',
            'org_type', 'industry_id', 'size', 'founded_year',
            'logo', 'cover_image', 'brand_color',
            'email', 'phone', 'website',
            'linkedin_url', 'twitter_url', 'facebook_url',
            'country', 'state_province', 'city', 'address', 'postal_code',
            'is_public', 'is_hiring',
            'culture_description', 'benefits',
        ]


# =============================================================================
# ORGANIZATION MEMBER SERIALIZERS
# =============================================================================

class OrganizationMemberSerializer(serializers.ModelSerializer):
    """Serializer for organization members."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = OrganizationMember
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'role', 'title',
            'is_active', 'joined_at'
        ]
        read_only_fields = ['id', 'joined_at']


class InviteMemberSerializer(serializers.Serializer):
    """Serializer for inviting members."""
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['admin', 'recruiter', 'hiring_manager', 'viewer'])
    title = serializers.CharField(max_length=100, required=False, allow_blank=True)


# =============================================================================
# OPPORTUNITY SERIALIZERS
# =============================================================================

class OpportunityListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for opportunity listings."""
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    organization_logo = serializers.ImageField(source='organization.logo', read_only=True)
    location_display = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = [
            'id', 'title', 'slug', 'opportunity_type', 'experience_level',
            'organization_name', 'organization_logo',
            'location_display', 'remote_policy', 'salary_display',
            'status', 'is_featured', 'deadline', 'published_at',
            'views_count', 'applications_count'
        ]

    def get_location_display(self, obj):
        if obj.location:
            return obj.location
        parts = [obj.city, obj.country]
        return ', '.join(filter(None, parts)) or 'Remote'


class OpportunityDetailSerializer(serializers.ModelSerializer):
    """Full opportunity serializer."""
    organization = OrganizationListSerializer(read_only=True)

    class Meta:
        model = Opportunity
        fields = [
            'id', 'organization', 'title', 'slug', 'summary', 'description',
            'opportunity_type', 'experience_level', 'category',
            'location', 'country', 'city', 'remote_policy',
            'salary_min', 'salary_max', 'salary_currency', 'salary_period',
            'salary_display', 'hide_salary',
            'required_skills', 'preferred_skills', 'benefits',
            'application_instructions', 'external_url',
            'status', 'is_featured', 'is_urgent',
            'deadline', 'start_date',
            'positions_available', 'positions_filled',
            'views_count', 'applications_count',
            'published_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'views_count', 'applications_count',
            'published_at', 'created_at', 'updated_at'
        ]


class OpportunityCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating opportunities."""

    class Meta:
        model = Opportunity
        fields = [
            'title', 'summary', 'description',
            'opportunity_type', 'experience_level', 'category',
            'location', 'country', 'city', 'remote_policy',
            'salary_min', 'salary_max', 'salary_currency', 'salary_period',
            'salary_display', 'hide_salary',
            'required_skills', 'preferred_skills', 'benefits',
            'application_instructions', 'external_url',
            'is_featured', 'is_urgent',
            'deadline', 'start_date', 'positions_available',
        ]

    def validate_title(self, value):
        if len(value) < 5:
            raise serializers.ValidationError('Title must be at least 5 characters.')
        return value

    def validate(self, data):
        salary_min = data.get('salary_min')
        salary_max = data.get('salary_max')
        if salary_min and salary_max and salary_min > salary_max:
            raise serializers.ValidationError({
                'salary_max': 'Maximum salary must be greater than minimum.'
            })

        deadline = data.get('deadline')
        if deadline and deadline < timezone.now().date():
            raise serializers.ValidationError({
                'deadline': 'Deadline cannot be in the past.'
            })

        return data

    def create(self, validated_data):
        validated_data['slug'] = slugify(validated_data['title'])
        # Ensure unique slug
        base_slug = validated_data['slug']
        counter = 1
        while Opportunity.objects.filter(slug=validated_data['slug']).exists():
            validated_data['slug'] = f"{base_slug}-{counter}"
            counter += 1

        return super().create(validated_data)


class OpportunityUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating opportunities."""

    class Meta:
        model = Opportunity
        fields = [
            'title', 'summary', 'description',
            'opportunity_type', 'experience_level', 'category',
            'location', 'country', 'city', 'remote_policy',
            'salary_min', 'salary_max', 'salary_currency', 'salary_period',
            'salary_display', 'hide_salary',
            'required_skills', 'preferred_skills', 'benefits',
            'application_instructions', 'external_url',
            'status', 'is_featured', 'is_urgent',
            'deadline', 'start_date',
            'positions_available', 'positions_filled',
        ]


class OpportunityPublishSerializer(serializers.Serializer):
    """Serializer for publishing an opportunity."""
    action = serializers.ChoiceField(choices=['publish', 'unpublish', 'close'])

