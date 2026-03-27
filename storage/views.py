# -*- coding: utf-8 -*-
"""
Storage Subsystem - Views
==========================
HTTP endpoints for file storage operations.

All file access is via signed URLs - no direct path access.
"""
import json
import logging
from django.http import HttpResponse, JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib.admin.views.decorators import staff_member_required

from .services import get_storage_service, FileCategory, AccessLevel

logger = logging.getLogger(__name__)


def get_request_context(request):
    """Extract request context for audit logging."""
    return {
        'ip_address': get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'request_id': request.META.get('HTTP_X_REQUEST_ID', ''),
        'service_name': request.META.get('HTTP_X_SERVICE_NAME', 'web'),
    }


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@require_GET
def serve_file(request, token):
    """
    Serve a file using signed URL token.
    This is the ONLY public endpoint for file access.

    Usage:
        GET /storage/file/{token}/
        GET /storage/file/{token}/?download=1  (force download)
    """
    storage = get_storage_service()
    result = storage.retrieve_with_token(
        token=token,
        request_context=get_request_context(request)
    )

    if not result['success']:
        return JsonResponse({
            'error': result.get('error', 'Access denied')
        }, status=403)

    content = result['content']
    file_info = result['file_info']

    # Determine content disposition
    disposition = 'inline'
    if request.GET.get('download') == '1':
        disposition = 'attachment'

    # Create response
    response = HttpResponse(
        content,
        content_type=file_info['mime_type']
    )

    # Set headers
    filename = file_info['filename']
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    response['Content-Length'] = len(content)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, max-age=3600'

    # Security headers
    response['X-Frame-Options'] = 'DENY'
    response['X-XSS-Protection'] = '1; mode=block'

    return response


@csrf_exempt
@require_POST
def api_upload(request):
    """
    API endpoint to upload a file.
    Requires authentication.

    POST /storage/api/upload/

    Form data:
        - file: The file to upload (required)
        - category: File category (optional, default: 'other')
        - access_level: Access level (optional, default: based on category)
        - metadata: JSON string of additional metadata (optional)
        - related_entity_type: Related model type (optional)
        - related_entity_id: Related model ID (optional)
        - expires_in_hours: Auto-expire after N hours (optional)
    """
    # Check authentication
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    # Get file from request
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)

    uploaded_file = request.FILES['file']

    # Read file content
    content = uploaded_file.read()

    # Get parameters
    category = request.POST.get('category', FileCategory.OTHER)
    access_level = request.POST.get('access_level')

    # Parse metadata
    metadata = {}
    if 'metadata' in request.POST:
        try:
            metadata = json.loads(request.POST['metadata'])
        except json.JSONDecodeError:
            pass

    # Parse expires_in_hours
    expires_in_hours = None
    if 'expires_in_hours' in request.POST:
        try:
            expires_in_hours = int(request.POST['expires_in_hours'])
        except ValueError:
            pass

    # Store file
    storage = get_storage_service()
    result = storage.store(
        data=content,
        filename=uploaded_file.name,
        category=category,
        owner_id=str(request.user.id),
        owner_type='user',
        access_level=access_level,
        mime_type=uploaded_file.content_type,
        related_entity_type=request.POST.get('related_entity_type'),
        related_entity_id=request.POST.get('related_entity_id'),
        metadata=metadata,
        tags=request.POST.getlist('tags'),
        description=request.POST.get('description', ''),
        expires_in_hours=expires_in_hours,
        request_context=get_request_context(request),
    )

    if not result['success']:
        return JsonResponse({
            'error': result.get('error', 'Upload failed')
        }, status=400)

    return JsonResponse({
        'success': True,
        'file_id': result['file_id'],
        'signed_url': result['signed_url'],
        'url_expires_at': result['url_expires_at'],
        'file_info': result['stored_file'],
    })


@require_GET
def api_file_info(request, file_id):
    """
    Get file information (no content).

    GET /storage/api/file/{file_id}/
    """
    # Check authentication
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    storage = get_storage_service()
    info = storage.get_file_info(file_id)

    if info is None:
        return JsonResponse({'error': 'File not found'}, status=404)

    # Check ownership (unless admin)
    if not request.user.is_staff:
        if info.get('owner_id') != str(request.user.id):
            return JsonResponse({'error': 'Access denied'}, status=403)

    return JsonResponse(info)


@csrf_exempt
@require_POST
def api_delete_file(request, file_id):
    """
    Delete a file.

    POST /storage/api/file/{file_id}/delete/

    Body (optional):
        {"hard_delete": true}  - Also removes from disk
    """
    # Check authentication
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    storage = get_storage_service()

    # Check ownership
    info = storage.get_file_info(file_id)
    if info is None:
        return JsonResponse({'error': 'File not found'}, status=404)

    # Only owner or staff can delete
    if not request.user.is_staff:
        if info.get('owner_id') != str(request.user.id):
            return JsonResponse({'error': 'Access denied'}, status=403)

    # Parse hard_delete option
    hard_delete = False
    if request.body:
        try:
            data = json.loads(request.body)
            hard_delete = data.get('hard_delete', False)
        except json.JSONDecodeError:
            pass

    # Delete
    success = storage.delete(
        file_id=file_id,
        user_id=str(request.user.id),
        hard_delete=hard_delete,
        request_context=get_request_context(request),
    )

    return JsonResponse({
        'success': success,
        'hard_delete': hard_delete,
    })


@csrf_exempt
@require_POST
def api_generate_signed_url(request, file_id):
    """
    Generate a signed URL for a file.

    POST /storage/api/file/{file_id}/signed-url/

    Body (optional):
        {
            "expires_in_hours": 168,  // Default 7 days
            "max_uses": 0,            // 0 = unlimited
            "allowed_ips": ["1.2.3.4"]
        }
    """
    # Check authentication
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    storage = get_storage_service()

    # Check ownership
    info = storage.get_file_info(file_id)
    if info is None:
        return JsonResponse({'error': 'File not found'}, status=404)

    if not request.user.is_staff:
        if info.get('owner_id') != str(request.user.id):
            return JsonResponse({'error': 'Access denied'}, status=403)

    # Parse parameters
    expires_in_hours = 24 * 7  # Default 7 days
    max_uses = 0
    allowed_ips = None

    if request.body:
        try:
            data = json.loads(request.body)
            expires_in_hours = data.get('expires_in_hours', expires_in_hours)
            max_uses = data.get('max_uses', 0)
            allowed_ips = data.get('allowed_ips')
        except json.JSONDecodeError:
            pass

    # Generate URL
    token = storage.get_signed_url(
        file_id=file_id,
        expires_in_hours=expires_in_hours,
        max_uses=max_uses,
        allowed_ips=allowed_ips,
        created_by_id=str(request.user.id),
    )

    if token is None:
        return JsonResponse({'error': 'Failed to generate URL'}, status=400)

    return JsonResponse({
        'success': True,
        'token': token,
        'url': request.build_absolute_uri(f'/storage/file/{token}/'),
        'expires_in_hours': expires_in_hours,
    })


@staff_member_required
@require_GET
def api_stats(request):
    """
    Get storage statistics.
    Admin only.

    GET /storage/api/stats/
    """
    storage = get_storage_service()
    stats = storage.get_stats()
    return JsonResponse(stats)


@staff_member_required
@require_GET
def api_list_files(request):
    """
    List files with filtering.
    Admin only.

    GET /storage/api/files/

    Query params:
        - category: Filter by category
        - owner_id: Filter by owner
        - status: Filter by status (default: active)
        - page: Page number (default: 1)
        - limit: Items per page (default: 50)
    """
    from storage.models import StoredFile

    files = StoredFile.objects.all()

    # Filters
    category = request.GET.get('category')
    if category:
        files = files.filter(category=category)

    owner_id = request.GET.get('owner_id')
    if owner_id:
        files = files.filter(owner_id=owner_id)

    status = request.GET.get('status', 'active')
    if status:
        files = files.filter(status=status)

    # Pagination
    page = int(request.GET.get('page', 1))
    limit = min(int(request.GET.get('limit', 50)), 100)
    offset = (page - 1) * limit

    total = files.count()
    files = files.order_by('-created_at')[offset:offset + limit]

    return JsonResponse({
        'files': [
            {
                'file_id': f.file_id,
                'filename': f.filename,
                'category': f.category,
                'mime_type': f.mime_type,
                'size': f.original_size,
                'owner_id': f.owner_id,
                'status': f.status,
                'created_at': f.created_at.isoformat(),
            }
            for f in files
        ],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit,
        }
    })


@staff_member_required
@require_GET
def api_orphan_files(request):
    """
    List orphan files detected.
    Admin only.

    GET /storage/api/orphans/
    """
    from storage.models import OrphanFile

    orphans = OrphanFile.objects.filter(status='detected').order_by('-detected_at')[:100]

    return JsonResponse({
        'orphans': [
            {
                'id': str(o.id),
                'storage_path': o.storage_path,
                'file_size': o.file_size,
                'detected_at': o.detected_at.isoformat(),
            }
            for o in orphans
        ],
        'total': OrphanFile.objects.filter(status='detected').count(),
    })


@staff_member_required
@csrf_exempt
@require_POST
def api_cleanup_orphans(request):
    """
    Cleanup orphan files.
    Admin only.

    POST /storage/api/orphans/cleanup/
    """
    storage = get_storage_service()

    # Find new orphans
    found = storage.find_orphan_files()

    # Delete old orphans
    deleted = storage.cleanup_orphans(older_than_days=7)

    return JsonResponse({
        'success': True,
        'orphans_found': len(found),
        'orphans_deleted': deleted,
    })

