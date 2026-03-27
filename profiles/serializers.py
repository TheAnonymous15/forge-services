# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Profiles Serializers (MVP1)
================================================
Serializers for talent profiles, education, experience, skills, etc.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import (
    TalentProfile, Education, WorkExperience, Skill, TalentSkill,
    Certification, TalentLanguage
)


# =============================================================================
# NESTED SERIALIZERS (for read operations)
# =============================================================================

class EducationSerializer(serializers.ModelSerializer):
    """Serializer for education entries."""
    education_level = serializers.CharField(source='level', read_only=True)

    class Meta:
        model = Education
        fields = [
            'id', 'institution', 'degree', 'field_of_study',
            'education_level', 'level', 'start_date', 'end_date', 'is_current',
            'grade', 'description', 'activities', 'location'
        ]
        read_only_fields = ['id']

    def validate(self, data):
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] < data['start_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date.'
                })
        return data


class WorkExperienceSerializer(serializers.ModelSerializer):
    """Serializer for work experience entries."""
    skills_used = serializers.JSONField(source='achievements', required=False)

    class Meta:
        model = WorkExperience
        fields = [
            'id', 'company', 'title', 'employment_type', 'location',
            'start_date', 'end_date', 'is_current', 'description',
            'achievements', 'responsibilities', 'is_remote', 'skills_used'
        ]
        read_only_fields = ['id']

    def validate(self, data):
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] < data['start_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date.'
                })
        if data.get('is_current') and data.get('end_date'):
            raise serializers.ValidationError({
                'end_date': 'Current position should not have an end date.'
            })
        return data


class SkillSerializer(serializers.ModelSerializer):
    """Serializer for skills."""
    name = serializers.CharField(source='skill.name', read_only=True)
    category = serializers.CharField(source='skill.category', read_only=True)
    proficiency = serializers.CharField(source='level', read_only=True)
    years_experience = serializers.IntegerField(source='years_of_experience', read_only=True)
    is_verified = serializers.BooleanField(source='skill.is_verified', read_only=True)

    class Meta:
        model = TalentSkill
        fields = [
            'id', 'name', 'category', 'proficiency', 'level',
            'years_experience', 'years_of_experience', 'is_primary', 'is_verified'
        ]
        read_only_fields = ['id', 'is_verified']


class SkillCreateSerializer(serializers.Serializer):
    """Serializer for creating skills."""
    name = serializers.CharField(max_length=100)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    level = serializers.ChoiceField(choices=['beginner', 'intermediate', 'advanced', 'expert'], default='intermediate')
    years_of_experience = serializers.IntegerField(default=0, min_value=0)
    is_primary = serializers.BooleanField(default=False)


class CertificationSerializer(serializers.ModelSerializer):
    """Serializer for certifications."""
    never_expires = serializers.BooleanField(source='does_not_expire', read_only=True)
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = Certification
        fields = [
            'id', 'name', 'issuing_organization', 'credential_id',
            'credential_url', 'issue_date', 'expiry_date',
            'is_verified', 'never_expires', 'does_not_expire', 'description'
        ]
        read_only_fields = ['id', 'is_verified']

    def get_is_verified(self, obj):
        return obj.is_valid


class LanguageSerializer(serializers.ModelSerializer):
    """Serializer for languages."""
    is_native = serializers.SerializerMethodField()

    class Meta:
        model = TalentLanguage
        fields = ['id', 'language', 'proficiency', 'is_native']
        read_only_fields = ['id']

    def get_is_native(self, obj):
        return obj.proficiency == 'native'



# =============================================================================
# PROFILE SERIALIZERS
# =============================================================================

class TalentProfileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for profile listings."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    primary_skills = serializers.SerializerMethodField()
    completion_percentage = serializers.IntegerField(source='completeness_score', read_only=True)

    class Meta:
        model = TalentProfile
        fields = [
            'id', 'user_email', 'user_name', 'headline', 'avatar',
            'country', 'city', 'availability', 'remote_preference',
            'primary_skills', 'completion_percentage', 'is_public'
        ]

    def get_primary_skills(self, obj):
        skills = obj.skills.filter(is_primary=True)[:5]
        return [s.skill.name for s in skills]


class TalentProfileDetailSerializer(serializers.ModelSerializer):
    """Full profile serializer with nested relations."""
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    completion_percentage = serializers.IntegerField(source='completeness_score', read_only=True)

    education = EducationSerializer(many=True, read_only=True)
    work_experience = WorkExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    certifications = CertificationSerializer(many=True, read_only=True)
    languages = LanguageSerializer(many=True, read_only=True)

    class Meta:
        model = TalentProfile
        fields = [
            # User info
            'id', 'user_id', 'user_email', 'user_name',
            # Personal
            'headline', 'bio', 'date_of_birth', 'gender', 'nationality', 'avatar',
            # Contact
            'phone_number', 'phone_secondary', 'website',
            'linkedin_url', 'github_url', 'portfolio_url',
            # Location
            'country', 'state_province', 'city', 'address', 'postal_code',
            # Work preferences
            'employment_status', 'availability', 'available_from',
            'willing_to_relocate', 'preferred_locations', 'remote_preference',
            # Compensation
            'expected_salary_min', 'expected_salary_max', 'salary_currency', 'salary_period',
            # Preferences
            'preferred_opportunity_types', 'preferred_industries',
            # Settings
            'is_public', 'show_email', 'show_phone', 'open_to_opportunities',
            # Nested
            'education', 'work_experience', 'skills', 'certifications', 'languages',
            # Meta
            'completion_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_id', 'completion_percentage', 'created_at', 'updated_at']


class TalentProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating profile."""

    class Meta:
        model = TalentProfile
        fields = [
            # Personal
            'headline', 'bio', 'date_of_birth', 'gender', 'nationality', 'avatar',
            # Contact
            'phone_number', 'phone_secondary', 'website',
            'linkedin_url', 'github_url', 'portfolio_url',
            # Location
            'country', 'state_province', 'city', 'address', 'postal_code',
            # Work preferences
            'employment_status', 'availability', 'available_from',
            'willing_to_relocate', 'preferred_locations', 'remote_preference',
            # Compensation
            'expected_salary_min', 'expected_salary_max', 'salary_currency', 'salary_period',
            # Preferences
            'preferred_opportunity_types', 'preferred_industries',
            # Settings
            'is_public', 'show_email', 'show_phone', 'open_to_opportunities',
        ]

    def validate_date_of_birth(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError('Date of birth cannot be in the future.')
        return value

    def validate(self, data):
        salary_min = data.get('expected_salary_min')
        salary_max = data.get('expected_salary_max')
        if salary_min and salary_max and salary_min > salary_max:
            raise serializers.ValidationError({
                'expected_salary_max': 'Maximum salary must be greater than minimum.'
            })
        return data


# =============================================================================
# PUBLIC PROFILE SERIALIZER (for viewing other profiles)
# =============================================================================

class PublicProfileSerializer(serializers.ModelSerializer):
    """Serializer for public profile view (respects privacy settings)."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()

    education = EducationSerializer(many=True, read_only=True)
    work_experience = WorkExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    certifications = CertificationSerializer(many=True, read_only=True)
    languages = LanguageSerializer(many=True, read_only=True)

    class Meta:
        model = TalentProfile
        fields = [
            'id', 'user_name', 'email', 'phone',
            'headline', 'bio', 'avatar',
            'country', 'city',
            'availability', 'remote_preference',
            'website', 'linkedin_url', 'github_url', 'portfolio_url',
            'education', 'work_experience', 'skills', 'certifications',
            'languages'
        ]

    def get_email(self, obj):
        if obj.show_email:
            return obj.user.email
        return None

    def get_phone(self, obj):
        if obj.show_phone:
            return obj.phone_number
        return None

