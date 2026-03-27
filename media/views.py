# -*- coding: utf-8 -*-
"""
Media API Views
===============
REST API endpoints for media upload and processing.
"""
import logging
import os
import uuid
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings

from .models import MediaFile, Document, ProcessingJob
from .serializers import (
    MediaFileSerializer,
    MediaFileUploadSerializer,
    DocumentSerializer,
    ProcessingJobSerializer,
)
from .services import MediaRouter
from .tasks import process_media_async

logger = logging.getLogger(__name__)


class MediaUploadView(APIView):
    """
    Upload and process media files.

    POST /api/v1/media/upload/

    Automatically detects media type and routes to appropriate processor.
    Small files are processed synchronously, large files queued for async.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Upload a media file.

        Request body (multipart/form-data):
            - file: The file to upload (required)
            - file_type: Type hint ('cv', 'profile_photo', etc.) (optional)
            - is_public: Whether file is publicly accessible (optional, default False)

        Returns:
            MediaFile details including processing status
        """
        serializer = MediaFileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data['file']
        file_type = serializer.validated_data.get('file_type', MediaFile.FileType.OTHER)
        is_public = serializer.validated_data.get('is_public', False)

        try:
            # Read file data
            uploaded_file.seek(0)
            data = uploaded_file.read()
            uploaded_file.seek(0)

            # Detect media type
            router = MediaRouter()
            media_type, mime_type = router.detect_type(data)

            # Validate size
            size_error = router.validate_size(data, media_type)
            if size_error:
                return Response(
                    {'error': size_error},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate storage path
            stored_filename = f"{uuid.uuid4().hex}_{uploaded_file.name}"
            relative_path = os.path.join(
                'uploads',
                str(request.user.id) if request.user.is_authenticated else 'anonymous',
                media_type.value,
                stored_filename
            )

            # Create directory and save original file
            full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, 'wb') as f:
                f.write(data)

            # Create MediaFile record
            media_file = MediaFile.objects.create(
                owner=request.user if request.user.is_authenticated else None,
                file_type=file_type,
                status=MediaFile.Status.PENDING,
                original_filename=uploaded_file.name,
                stored_filename=stored_filename,
                file_path=relative_path,
                file_size=len(data),
                mime_type=mime_type,
                extension=os.path.splitext(uploaded_file.name)[1].lstrip('.'),
                is_public=is_public,
            )

            # Decide sync vs async processing
            if router.should_process_async(data):
                # Queue for async processing
                process_media_async.delay(str(media_file.id))
                media_file.status = MediaFile.Status.PENDING
            else:
                # Process synchronously
                result = router.process(data)

                if result.success:
                    # Save processed file
                    if result.content:
                        processed_filename = f"processed_{stored_filename}"
                        if result.extension:
                            base = os.path.splitext(processed_filename)[0]
                            processed_filename = f"{base}.{result.extension}"

                        processed_path = os.path.join(
                            os.path.dirname(relative_path),
                            processed_filename
                        )

                        with open(os.path.join(settings.MEDIA_ROOT, processed_path), 'wb') as f:
                            f.write(result.content)

                        media_file.processed_path = processed_path

                    # Save thumbnail
                    if result.thumbnail:
                        thumb_filename = f"thumb_{stored_filename}.webp"
                        thumb_path = os.path.join(
                            os.path.dirname(relative_path),
                            'thumbnails',
                            thumb_filename
                        )

                        thumb_full = os.path.join(settings.MEDIA_ROOT, thumb_path)
                        os.makedirs(os.path.dirname(thumb_full), exist_ok=True)

                        with open(thumb_full, 'wb') as f:
                            f.write(result.thumbnail)

                        media_file.thumbnail_path = thumb_path

                    media_file.status = MediaFile.Status.READY
                    media_file.is_sanitised = True
                    media_file.checksum_sha256 = result.checksum_sha256
                    media_file.mime_type = result.mime_type or mime_type
                    media_file.metadata = result.metadata or {}

                    if result.threats_sanitized:
                        media_file.threat_detected = True
                        media_file.threat_detail = '\n'.join(result.threats_sanitized)

                    # Create Document if text was extracted
                    if result.extracted_text:
                        Document.objects.create(
                            media_file=media_file,
                            owner=media_file.owner,
                            extracted_text=result.extracted_text,
                            pages=result.metadata.get('pages', 0),
                        )
                else:
                    media_file.status = MediaFile.Status.FAILED
                    media_file.metadata = {'error': result.error}

            media_file.save()

            return Response(
                MediaFileSerializer(media_file).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Upload failed: {e}", exc_info=True)
            return Response(
                {'error': f'Upload failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MediaFileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for MediaFile CRUD operations.
    """
    serializer_class = MediaFileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return files owned by the current user."""
        return MediaFile.objects.filter(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """
        Reprocess a media file.

        POST /api/v1/media/files/{id}/reprocess/
        """
        media_file = self.get_object()

        if media_file.status == MediaFile.Status.PROCESSING:
            return Response(
                {'error': 'File is already being processed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        media_file.status = MediaFile.Status.PENDING
        media_file.save(update_fields=['status'])

        process_media_async.delay(str(media_file.id))

        return Response({'status': 'queued'})

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Get download URL for a media file.

        GET /api/v1/media/files/{id}/download/
        """
        media_file = self.get_object()

        if media_file.status != MediaFile.Status.READY:
            return Response(
                {'error': 'File not ready for download'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'url': media_file.url,
            'filename': media_file.original_filename,
            'mime_type': media_file.mime_type,
            'size': media_file.file_size,
        })


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Document records (extracted text from uploaded docs).
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)


class ProcessingJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing processing job status.
    """
    serializer_class = ProcessingJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProcessingJob.objects.filter(
            media_file__owner=self.request.user
        ).select_related('media_file')

