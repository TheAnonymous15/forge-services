# -*- coding: utf-8 -*-
"""
Media Serializers
=================
DRF serializers for media models.
"""
from rest_framework import serializers
from .models import MediaFile, Document, ProcessingJob


class MediaFileSerializer(serializers.ModelSerializer):
    """Serializer for MediaFile model."""

    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    size_kb = serializers.ReadOnlyField()
    is_image = serializers.ReadOnlyField()

    class Meta:
        model = MediaFile
        fields = [
            'id',
            'file_type',
            'status',
            'original_filename',
            'file_size',
            'size_kb',
            'mime_type',
            'extension',
            'url',
            'thumbnail_url',
            'is_image',
            'is_sanitised',
            'threat_detected',
            'is_public',
            'metadata',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'file_size', 'mime_type', 'extension',
            'is_sanitised', 'threat_detected', 'metadata',
            'created_at', 'updated_at',
        ]

    def get_url(self, obj):
        """Get the URL for the processed (or original) file."""
        return obj.url if obj.status == MediaFile.Status.READY else None

    def get_thumbnail_url(self, obj):
        """Get the thumbnail URL if available."""
        if obj.thumbnail_path:
            from django.conf import settings
            return f"{settings.MEDIA_URL}{obj.thumbnail_path}"
        return None


class MediaFileUploadSerializer(serializers.Serializer):
    """Serializer for file upload requests."""

    file = serializers.FileField(required=True)
    file_type = serializers.ChoiceField(
        choices=MediaFile.FileType.choices,
        required=False,
        default=MediaFile.FileType.OTHER
    )
    is_public = serializers.BooleanField(required=False, default=False)

    def validate_file(self, value):
        """Validate uploaded file."""
        # Check file size (max 500MB)
        max_size = 500 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File too large. Maximum size is {max_size // (1024*1024)}MB"
            )
        return value


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document model."""

    media_file = MediaFileSerializer(read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'media_file',
            'title',
            'description',
            'is_primary',
            'pages',
            'extracted_text',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'media_file', 'pages', 'extracted_text', 'created_at', 'updated_at']


class ProcessingJobSerializer(serializers.ModelSerializer):
    """Serializer for ProcessingJob model."""

    media_file_id = serializers.UUIDField(source='media_file.id', read_only=True)
    media_file_name = serializers.CharField(source='media_file.original_filename', read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingJob
        fields = [
            'id',
            'media_file_id',
            'media_file_name',
            'job_type',
            'status',
            'result',
            'error',
            'duration',
            'started_at',
            'finished_at',
            'created_at',
        ]

    def get_duration(self, obj):
        """Calculate job duration in seconds."""
        if obj.started_at and obj.finished_at:
            delta = obj.finished_at - obj.started_at
            return delta.total_seconds()
        return None

