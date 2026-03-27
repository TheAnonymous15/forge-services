# -*- coding: utf-8 -*-
import csv
import json
import re
import logging
from datetime import datetime

from django.http import Http404, HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator

from .blog_data import BLOG_CATEGORIES
from .models import PartnerRegistration, ContactMessage, BlogPost, BlogImage, TalentWaitlist
from .services.blog_service import BlogService, BlogImageService

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# SPA-aware render helper
# - Normal request  → full page (base.html + content block)
# - SPA request     → only the inner content of <main>...</main>
#   so navbar/footer from base.html are NOT injected twice
# -------------------------------------------------------
def render_page(request, template, context=None):
    context = context or {}
    is_spa = request.headers.get("X-Requested-With") == "SPA"

    full_html = render_to_string(template, context, request=request, using="jinja2")

    if is_spa:
        # Extract only what is inside <main>…</main> to avoid
        # re-injecting the navbar and footer that are already in the DOM
        match = re.search(r'<main[^>]*>(.*?)</main>', full_html, re.DOTALL)
        content = match.group(1).strip() if match else full_html
        response = HttpResponse(content)
        response["X-Page-Title"] = context.get("page_title", "ForgeForth Africa")
        return response

    return HttpResponse(full_html)


# -------------------------------------------------------
# Pages  (short paths — Jinja2 DIRS = website/templates/website/)
# -------------------------------------------------------

def home(request):
    return render_page(request, "pages/index.html", {
        "page_title": "ForgeForth Africa - Forging Africa's Future Through Talent",
        "waitlist_count": "10,000+",
    })


def about(request):
    return render_page(request, "pages/about.html", {
        "page_title": "About Us - ForgeForth Africa",
    })


def for_talent(request):
    return render_page(request, "pages/for_talent.html", {
        "page_title": "For Talent - ForgeForth Africa",
    })


def for_employers(request):
    return render_page(request, "pages/for_employers.html", {
        "page_title": "For Employers - ForgeForth Africa",
    })


def platform(request):
    return render_page(request, "pages/platform.html", {
        "page_title": "Platform Overview - ForgeForth Africa",
    })


def why_africa(request):
    return render_page(request, "pages/why_africa.html", {
        "page_title": "Why Africa - ForgeForth Africa",
    })


def gallery(request):
    return render_page(request, "pages/gallery.html", {
        "page_title": "Our Gallery - ForgeForth Africa",
        "images": [],
    })


def contact(request):
    return render_page(request, "pages/contact.html", {
        "page_title": "Contact Us - ForgeForth Africa",
    })


def blog(request):
    # Get query parameters
    category = request.GET.get('category', '')
    search = request.GET.get('q', '')
    page = request.GET.get('page', 1)

    # Query published posts from DB only
    qs = BlogPost.objects.filter(status='published')

    if category:
        qs = qs.filter(category=category)

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(excerpt__icontains=search) |
            Q(content__icontains=search) |
            Q(tags__icontains=search)
        )

    qs = qs.order_by('-published_at', '-created_at')

    # Build article dicts for template
    articles = []
    for post in qs:
        articles.append({
            'slug': post.slug,
            'blog_id': post.blog_id,
            'title': post.title,
            'excerpt': post.excerpt,
            'category': post.get_category_display(),
            'category_slug': post.category,
            'author': post.author_name,
            'author_initials': post.author_initials,
            'date': post.published_at.strftime('%b %d, %Y') if post.published_at else post.created_at.strftime('%b %d, %Y'),
            'read_time': post.read_time,
            'featured': post.is_featured,
            'tags': post.tags,
            'is_db': True,
            'view_count': post.view_count,
            'share_url': post.share_url,
        })

    # Paginate – 9 per page
    paginator = Paginator(articles, 9)
    page_obj = paginator.get_page(page)

    return render_page(request, "pages/blog.html", {
        "page_title": "Blog - ForgeForth Africa",
        "articles": page_obj.object_list,
        "page_obj": page_obj,
        "categories": BLOG_CATEGORIES,
        "current_category": category,
        "search_query": search,
        "total_count": paginator.count,
    })


def parse_content_to_body(content: str) -> list:
    """
    Convert a plain-text / markdown-lite blog content string into a list of
    (text, type) tuples that the blog_article template understands.

    Recognised patterns:
      ## Heading text   → ('Heading text', 'h2')
      # Heading text    → ('Heading text', 'h2')
      Any other line    → (line, None)   ← rendered as <p>

    Empty lines are skipped.
    """
    body = []
    if not content:
        return body

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        # Support markdown-style headings
        if line.startswith('## '):
            body.append((line[3:].strip(), 'h2'))
        elif line.startswith('# '):
            body.append((line[2:].strip(), 'h2'))
        else:
            body.append((line, None))

    return body


def blog_article(request, slug):
    # First try database
    try:
        post = BlogPost.objects.get(slug=slug, status='published')
        post.increment_views()

        # Get related posts
        related_posts = BlogPost.objects.filter(
            status='published',
            category=post.category
        ).exclude(pk=post.pk)[:3]

        related = [{
            'slug': p.slug,
            'blog_id': p.blog_id,
            'title': p.title,
            'excerpt': p.excerpt,
            'category': p.get_category_display(),
            'author': p.author_name,
            'author_initials': p.author_initials,
            'date': p.published_at.strftime('%b %d, %Y') if p.published_at else '',
            'read_time': p.read_time,
            'tags': p.tags or [],
            'share_url': p.share_url,
        } for p in related_posts]

        # Detect if content is HTML (from Quill) or plain text
        content = post.content or ''
        is_html = content.strip().startswith('<')

        # ── Fix base64 images: extract, save to disk, replace src ──
        if is_html and 'data:image/' in content:
            try:
                from website.services.blog_service import extract_base64_images_from_content
                fixed = extract_base64_images_from_content(post.blog_id, content)
                if fixed != content:
                    # Persist cleaned content back to DB so we don't redo this every request
                    BlogPost.objects.filter(pk=post.pk).update(content=fixed)
                    content = fixed
                    logger.info(f"Extracted base64 images from post {post.blog_id}")
            except Exception as _e:
                logger.warning(f"Could not extract base64 images for {post.blog_id}: {_e}")

        return render_page(request, "pages/blog_article.html", {
            "page_title": f"{post.title} - ForgeForth Blog",
            "article": {
                'slug': post.slug,
                'blog_id': post.blog_id,
                'title': post.title,
                'excerpt': post.excerpt,
                'content': content,
                'body': None if is_html else parse_content_to_body(content),
                'is_html': is_html,
                'category': post.get_category_display(),
                'author': post.author_name,
                'author_initials': post.author_initials,
                'author_bio': post.author_bio,
                'date': post.published_at.strftime('%b %d, %Y') if post.published_at else post.created_at.strftime('%b %d, %Y'),
                'read_time': post.read_time,
                'tags': post.tags,
                'is_db': True,
                'view_count': post.view_count,
                'share_url': post.share_url,
            },
            "related": related,
        })
    except BlogPost.DoesNotExist:
        raise Http404("Article not found")


def blog_by_id(request, blog_id):
    """Access blog post by its short unique ID (for sharing links like /blog/p/abc12xyz)."""
    try:
        post = BlogPost.objects.get(blog_id=blog_id, status='published')
        return redirect('website:blog_article', slug=post.slug)
    except BlogPost.DoesNotExist:
        raise Http404("Article not found")


# -------------------------------------------------------
# Blog Posting / Management
# -------------------------------------------------------

def blog_create(request):
    """Page for creating a new blog post with image upload support."""
    if request.method == 'GET':
        return render_page(request, "pages/blog_create.html", {
            "page_title": "Write a Blog Post - ForgeForth Africa",
            "categories": BlogPost.CATEGORY_CHOICES,
        })

    # Handle POST - create blog post
    try:
        # Check if multipart form data (with files) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.POST
            featured_image = request.FILES.get('featured_image')
        else:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            featured_image = None

        # Use BlogService for creation
        post, error = BlogService.create_post(
            title=data.get('title', ''),
            content=data.get('content', ''),
            excerpt=data.get('excerpt', ''),
            category=data.get('category', 'insights'),
            tags=data.get('tags', ''),
            author_name=data.get('author_name', 'Community Contributor'),
            author_email=data.get('author_email', ''),
            status=data.get('status', 'draft'),
            featured_image_url=data.get('featured_image_url', ''),
            featured_image_file=featured_image,
        )

        if error:
            return JsonResponse({
                'success': False,
                'error': error
            }, status=400)

        return JsonResponse({
            'success': True,
            'message': 'Blog post created successfully!',
            'blog_id': post.blog_id,
            'slug': post.slug,
            'share_url': post.share_url,
            'status': post.status,
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating blog post: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to create blog post'
        }, status=500)


def blog_preview(request, blog_id):
    """Preview a blog post (even if draft)."""
    try:
        post = BlogPost.objects.get(blog_id=blog_id)

        content = post.content or ''
        is_html = content.strip().startswith('<')

        # Fix base64 images on preview too
        if is_html and 'data:image/' in content:
            try:
                from website.services.blog_service import extract_base64_images_from_content
                fixed = extract_base64_images_from_content(post.blog_id, content)
                if fixed != content:
                    BlogPost.objects.filter(pk=post.pk).update(content=fixed)
                    content = fixed
            except Exception as _e:
                logger.warning(f"Could not extract base64 images for preview {post.blog_id}: {_e}")
        return render_page(request, "pages/blog_article.html", {
            "page_title": f"Preview: {post.title} - ForgeForth Blog",
            "article": {
                'slug': post.slug,
                'blog_id': post.blog_id,
                'title': post.title,
                'excerpt': post.excerpt,
                'content': content,
                'body': None if is_html else parse_content_to_body(content),
                'is_html': is_html,
                'category': post.get_category_display(),
                'author': post.author_name,
                'author_initials': post.author_initials,
                'date': post.created_at.strftime('%b %d, %Y'),
                'read_time': post.read_time,
                'tags': post.tags,
                'is_preview': True,
                'status': post.status,
            },
            "related": [],
            "is_preview": True,
        })
    except BlogPost.DoesNotExist:
        raise Http404("Blog post not found")


@csrf_exempt
def blog_api(request):
    """API endpoint for blog operations."""
    if request.method == 'GET':
        # List all published posts
        posts = BlogPost.objects.filter(status='published').values(
            'blog_id', 'slug', 'title', 'excerpt', 'category',
            'author_name', 'created_at', 'published_at', 'view_count'
        )
        return JsonResponse({
            'success': True,
            'posts': list(posts)
        })

    elif request.method == 'POST':
        # Create new post (same as blog_create POST handler)
        try:
            data = json.loads(request.body)

            title = data.get('title', '').strip()
            content = data.get('content', '').strip()

            if not title or not content:
                return JsonResponse({
                    'success': False,
                    'error': 'Title and content are required'
                }, status=400)

            excerpt = data.get('excerpt', content[:200] + ('...' if len(content) > 200 else ''))

            post = BlogPost.objects.create(
                title=title,
                content=content,
                excerpt=excerpt,
                category=data.get('category', 'insights'),
                author_name=data.get('author_name', 'Community Contributor'),
                author_email=data.get('author_email', ''),
                tags=data.get('tags', []),
                status=data.get('status', 'draft'),
            )

            return JsonResponse({
                'success': True,
                'blog_id': post.blog_id,
                'slug': post.slug,
                'share_url': post.share_url,
            })

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Blog API error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def blog_image_upload(request):
    """API endpoint for uploading images to blog posts."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        # Get the uploaded file
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'success': False, 'error': 'No image file provided'}, status=400)

        # Get optional blog_id to attach image to a post
        blog_id = request.POST.get('blog_id')
        blog_post = None
        if blog_id:
            try:
                blog_post = BlogPost.objects.get(blog_id=blog_id)
            except BlogPost.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Blog post not found'}, status=404)

        # Upload the image
        blog_image, error = BlogImageService.upload_image(
            file=image_file,
            blog_post=blog_post,
            alt_text=request.POST.get('alt_text', ''),
            caption=request.POST.get('caption', ''),
        )

        if error:
            return JsonResponse({'success': False, 'error': error}, status=400)

        return JsonResponse({
            'success': True,
            'url': blog_image.url,
            'image': {
                'id': str(blog_image.id),
                'url': blog_image.url,
                'thumbnail': blog_image.thumbnail_url,
                'width': blog_image.width,
                'height': blog_image.height,
                'filename': blog_image.original_filename,
            },
            # For markdown insertion
            'markdown': f'![{blog_image.alt_text or blog_image.original_filename}]({blog_image.url})',
        })

    except Exception as e:
        logger.error(f"Image upload error: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to upload image'}, status=500)


def blog_image_serve(request, token):
    """Serve a blog image by its secure token."""
    image = BlogImageService.get_image_by_token(token)
    if not image:
        raise Http404("Image not found")

    # Check if file exists
    if not image.exists():
        raise Http404("Image not found")

    try:
        return FileResponse(
            open(image.full_path, 'rb'),
            content_type=image.mime_type,
            as_attachment=False
        )
    except Exception:
        raise Http404("Image not found")


def serve_blog_media(request, path):
    """
    Serve blog media files from protected directory.
    This ensures images are served through Django with security checks.
    """
    from pathlib import Path
    import mimetypes

    # Security: Clean the path to prevent directory traversal
    clean_path = Path(path).resolve()

    # Get the blog media root
    from website.models import BLOG_MEDIA_ROOT

    # Build the full path
    full_path = BLOG_MEDIA_ROOT / path

    # Security: Ensure the resolved path is within BLOG_MEDIA_ROOT
    try:
        full_path.resolve().relative_to(BLOG_MEDIA_ROOT.resolve())
    except ValueError:
        raise Http404("Invalid path")

    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise Http404("File not found")

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(full_path))
    if not content_type:
        content_type = 'application/octet-stream'

    # Only serve allowed image types
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if content_type not in allowed_types:
        raise Http404("File type not allowed")

    try:
        response = FileResponse(
            open(full_path, 'rb'),
            content_type=content_type,
            as_attachment=False
        )
        # Add cache headers for images
        response['Cache-Control'] = 'public, max-age=86400'  # Cache for 1 day
        return response
    except Exception:
        raise Http404("Could not serve file")


def privacy_policy(request):
    return render_page(request, "pages/privacy_policy.html", {
        "page_title": "Privacy Policy - ForgeForth Africa",
    })


def terms_of_service(request):
    return render_page(request, "pages/terms_of_service.html", {
        "page_title": "Terms of Service - ForgeForth Africa",
    })


def cookie_policy(request):
    return render_page(request, "pages/cookie_policy.html", {
        "page_title": "Cookie Policy - ForgeForth Africa",
    })


def foundation(request):
    """Life of Purpose Foundation page."""
    return render_page(request, "pages/foundation.html", {
        "page_title": "The Foundation - Life of Purpose | ForgeForth Africa",
    })

# -------------------------------------------------------
# Authentication Pages
# -------------------------------------------------------
import os

def register_page(request):
    """Registration page for new users."""
    user_type = request.GET.get("type", "talent")  # talent or employer
    talent_portal_url = os.getenv("TALENT_PORTAL_URL", "https://localhost:9003")
    return render_page(request, "pages/auth/register.html", {
        "page_title": "Create Account - ForgeForth Africa",
        "user_type": user_type,
        "talent_portal_url": talent_portal_url,
    })


def login_page(request):
    """Login page - redirects to the Talent Portal login."""
    from django.shortcuts import redirect
    talent_portal_url = os.getenv("TALENT_PORTAL_URL", "https://localhost:9003")
    next_url = request.GET.get("next", "")
    redirect_url = f"{talent_portal_url}/login"
    if next_url:
        redirect_url += f"?next={next_url}"
    return redirect(redirect_url)


def health(request):
    """Lightweight health-check endpoint.

    The maintenance/coming_soon pages poll this every 3 seconds.
    Returns:
      {"status": "healthy"}       — both modes OFF, site is live
      {"status": "maintenance"}   — maintenance mode ON
      {"status": "oncoming"}      — coming soon mode ON
    """
    import json as _json
    import os

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as fh:
                data = _json.load(fh)
                if int(data.get("oncoming", 0)) == 1:
                    return JsonResponse({"status": "oncoming"}, status=503)
                if int(data.get("maintenance_mode", 0)) == 1:
                    return JsonResponse({"status": "maintenance"}, status=503)
    except Exception:
        pass

    return JsonResponse({"status": "healthy"})


def api_country_codes(request):
    """
    API endpoint to get country calling codes.
    GET /api/country-codes/

    Returns cached country codes with dial codes and flags.
    Query params:
        - refresh=1: Force refresh from API
    """
    from .services.country_codes import get_country_codes

    force_refresh = request.GET.get('refresh') == '1'

    try:
        countries = get_country_codes(force_refresh=force_refresh)
        return JsonResponse({
            'success': True,
            'countries': countries,
            'count': len(countries)
        })
    except Exception as e:
        logger.error(f"Error fetching country codes: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch country codes'
        }, status=500)


# -------------------------------------------------------
# Custom Error Handlers
# -------------------------------------------------------

def error_404(request, exception=None):
    """Custom 404 Not Found handler."""
    return render(request, "website/errors/404.html", status=404)


def error_500(request):
    """Custom 500 Internal Server Error handler."""
    return render(request, "website/errors/500.html", status=500)


def error_403(request, exception=None):
    """Custom 403 Forbidden handler."""
    return render(request, "website/errors/403.html", status=403)


def error_400(request, exception=None):
    """Custom 400 Bad Request handler."""
    return render(request, "website/errors/404.html", status=400)


# -------------------------------------------------------
# API Endpoints for Form Submissions
# -------------------------------------------------------

def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@csrf_exempt
@require_POST
def api_partner_registration(request):
    """
    Handle partner/employer registration submissions.
    POST /api/partner-waitlist/
    """
    try:
        data = json.loads(request.body)

        # Validate required fields
        required_fields = ['organization_name', 'industry', 'company_size', 'country',
                          'first_name', 'last_name', 'job_title', 'email']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }, status=400)

        # Validate interest types
        interest_types = data.get('interest_types', [])
        if not interest_types:
            return JsonResponse({
                'success': False,
                'error': 'Please select at least one interest type'
            }, status=400)

        # Create registration
        registration = PartnerRegistration.objects.create(
            organization_name=data['organization_name'],
            industry=data['industry'],
            company_size=data['company_size'],
            country=data['country'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            job_title=data['job_title'],
            email=data['email'],
            phone=data.get('phone', ''),
            interest_types=interest_types,
            message=data.get('message', ''),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )

        logger.info(f"New partner registration: {registration.organization_name} ({registration.email})")

        return JsonResponse({
            'success': True,
            'message': 'Thank you for registering! Our team will be in touch shortly.',
            'id': registration.id
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Partner registration error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=500)


@csrf_exempt
@require_POST
def api_talent_waitlist(request):
    """
    Handle talent/individual registration submissions.
    POST /api/talent-waitlist/

    Note: This endpoint now redirects registration data to the main api_register
    endpoint for full user account creation. The platform is now live, not waitlist.
    """
    # Forward to the main registration endpoint
    return api_register(request)



@csrf_exempt
@require_POST
def api_callback_request(request):
    """
    Handle callback request submissions.
    POST /api/callback/
    """
    from .email_service import email_service

    try:
        data = json.loads(request.body)

        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        time = data.get('time', '').strip() if data.get('time') else None
        timezone = data.get('timezone', '').strip() if data.get('timezone') else 'Africa/Johannesburg'
        channel = data.get('channel', '').strip().lower() if data.get('channel') else 'phone'

        # Validate channel
        if channel not in ['phone', 'whatsapp']:
            channel = 'phone'

        # Validate required fields
        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Name is required'
            }, status=400)

        if not phone:
            return JsonResponse({
                'success': False,
                'error': 'Phone number is required'
            }, status=400)

        # Basic phone validation (at least 7 digits)
        phone_digits = ''.join(c for c in phone if c.isdigit())
        if len(phone_digits) < 7:
            return JsonResponse({
                'success': False,
                'error': 'Please provide a valid phone number'
            }, status=400)

        success, message = email_service.send_callback_request(name, phone, time, timezone, channel)

        if success:
            return JsonResponse({
                'success': True,
                'message': 'Thank you! We\'ll call you back shortly.'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to submit callback request. Please try again later.'
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Callback request error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }, status=500)


@csrf_exempt
@require_POST
def api_contact_form(request):
    """
    Handle contact form submissions.
    POST /api/contact/
    """
    from .email_service import email_service

    try:
        data = json.loads(request.body)

        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        inquiry_type = data.get('inquiry_type', '').strip()
        company = data.get('company', '').strip()
        phone = data.get('phone', '').strip()

        # Validate required fields
        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Name is required'
            }, status=400)

        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)

        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message is required'
            }, status=400)

        # Also save to database
        try:
            ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject or 'No subject',
                message=message,
                inquiry_type=inquiry_type or 'general',
                company=company,
                phone=phone,
                ip_address=get_client_ip(request),
            )
        except Exception as db_error:
            logger.warning(f"Failed to save contact message to DB: {db_error}")

        success, msg = email_service.send_contact_form_email(
            name=name,
            email=email,
            subject=subject,
            message=message,
            inquiry_type=inquiry_type,
            company=company,
            phone=phone
        )

        if success:
            return JsonResponse({
                'success': True,
                'message': 'Thank you! We\'ll get back to you within 24-48 hours.'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to send message. Please try again later.'
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Contact form error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }, status=500)


@csrf_exempt
@require_POST
def api_register(request):
    """
    Handle user registration.
    POST /api/auth/register/

    Creates user account, generates verification token, sends verification email.
    User must verify email before they can login.
    """
    from accounts.models import User, EmailVerificationToken
    from communications.services import EmailService
    from django.conf import settings

    try:
        data = json.loads(request.body)

        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name', 'role']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'Please provide your {field.replace("_", " ")}'
                }, status=400)

        # Validate email format
        email = data['email'].strip().lower()
        if not re.match(r'^[\w\.\-\+]+@[\w\.-]+\.\w+$', email):
            return JsonResponse({
                'success': False,
                'error': 'Please provide a valid email address'
            }, status=400)

        # Validate password strength
        password = data['password']
        if len(password) < 8:
            return JsonResponse({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }, status=400)

        # Check password has letters and numbers
        has_letter = any(c.isalpha() for c in password)
        has_number = any(c.isdigit() for c in password)
        if not (has_letter and has_number):
            return JsonResponse({
                'success': False,
                'error': 'Password must contain both letters and numbers'
            }, status=400)

        # Validate consent
        if not data.get('consent_terms'):
            return JsonResponse({
                'success': False,
                'error': 'You must agree to the Terms of Service'
            }, status=400)

        if not data.get('consent_privacy'):
            return JsonResponse({
                'success': False,
                'error': 'You must agree to the Privacy Policy'
            }, status=400)

        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'error': 'An account with this email already exists'
            }, status=400)

        # Check if phone number already exists (if provided)
        phone_number = data.get('phone_number', '').strip()
        if phone_number:
            # Normalize phone number - remove spaces, dashes
            phone_number = re.sub(r'[\s\-\(\)]', '', phone_number)
            if User.objects.filter(phone_number=phone_number).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'An account with this phone number already exists'
                }, status=400)

        # Create user (unverified)
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            phone_number=phone_number,
            role=data['role'],
            consent_terms=True,
            consent_privacy=True,
            consent_marketing=data.get('consent_marketing', False),
            consented_at=timezone.now(),
            is_verified=False,  # Must verify email first
        )

        # Create verification token
        verification_token = EmailVerificationToken.create_token(user, expires_hours=24)

        # Build verification URL
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:9880')
        verification_url = f"{site_url}/verify-email?token={verification_token.token}"

        # Send verification email
        email_sent = False
        try:
            email_sent = EmailService.send_verification_email(
                user=user,
                token=verification_token.token
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")

        logger.info(f"New user registered: {user.email} (role: {user.role}, email_sent: {email_sent})")

        return JsonResponse({
            'success': True,
            'message': 'Account created! Please check your email to verify your account.',
            'email_sent': email_sent,
            'user_email': user.email,
            'requires_verification': True,
            'redirect_url': '/portal/login/'
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred during registration. Please try again.'
        }, status=500)


@csrf_exempt
def verify_email(request):
    """
    Verify user's email address.
    GET /verify-email?token=<token>&uid=<user_id>&ts=<timestamp>&sig=<signature>

    Calls the API service to validate the verification token.
    """
    import requests
    import os

    token_str = request.GET.get('token', '')
    uid = request.GET.get('uid', '')
    ts = request.GET.get('ts', '')
    sig = request.GET.get('sig', '')

    if not token_str:
        return render_page(request, "pages/auth/verification_result.html", {
            "page_title": "Email Verification",
            "success": False,
            "error": "No verification token provided.",
        })

    # Get API service URL
    api_service_url = os.getenv('API_SERVICE_URL', 'http://localhost:9001')

    try:
        # Call API service to verify the email
        response = requests.post(
            f"{api_service_url}/api/v1/auth/verify-email/",
            json={
                'token': token_str,
                'uid': uid,
                'ts': ts,
                'sig': sig,
            },
            headers={
                'Content-Type': 'application/json',
            },
            timeout=30
        )

        result = response.json()

        if response.status_code == 200 and result.get('success'):
            # Verification successful
            # Determine the correct login URL based on environment
            is_production = os.getenv('DJANGO_ENV', 'development') == 'production'
            if is_production:
                login_url = "https://talent.forgeforthafrica.com/portal/login/"
            else:
                talent_portal_url = os.getenv('TALENT_PORTAL_URL', 'http://localhost:9003')
                login_url = f"{talent_portal_url}/portal/login/"

            return render_page(request, "pages/auth/verification_result.html", {
                "page_title": "Email Verified!",
                "success": True,
                "user_email": result.get('data', {}).get('email', ''),
                "user_name": result.get('data', {}).get('first_name', ''),
                "login_url": login_url,
            })
        else:
            # Verification failed
            error_msg = "Invalid verification link. Please check your email for the correct link."

            if result.get('error'):
                error_obj = result['error']
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get('message', error_msg)
                else:
                    error_msg = str(error_obj)

            # Check for specific error types
            already_verified = 'already' in error_msg.lower() or 'used' in error_msg.lower()
            expired = 'expired' in error_msg.lower()

            # Determine the correct login URL based on environment
            is_production = os.getenv('DJANGO_ENV', 'development') == 'production'
            if is_production:
                login_url = "https://talent.forgeforthafrica.com/portal/login/"
            else:
                talent_portal_url = os.getenv('TALENT_PORTAL_URL', 'http://localhost:9003')
                login_url = f"{talent_portal_url}/portal/login/"

            return render_page(request, "pages/auth/verification_result.html", {
                "page_title": "Email Verification",
                "success": False,
                "error": error_msg,
                "already_verified": already_verified,
                "expired": expired,
                "login_url": login_url,
            })

    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to API service for email verification")
        return render_page(request, "pages/auth/verification_result.html", {
            "page_title": "Email Verification",
            "success": False,
            "error": "Service temporarily unavailable. Please try again later.",
        })
    except requests.exceptions.Timeout:
        logger.error("API service timeout during email verification")
        return render_page(request, "pages/auth/verification_result.html", {
            "page_title": "Email Verification",
            "success": False,
            "error": "Request timed out. Please try again.",
        })
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        return render_page(request, "pages/auth/verification_result.html", {
            "page_title": "Email Verification",
            "success": False,
            "error": "An error occurred. Please try again or contact support.",
        })


@csrf_exempt
@require_POST
def resend_verification_email(request):
    """
    Resend verification email.
    POST /api/auth/resend-verification/
    """
    from accounts.models import User, EmailVerificationToken
    from communications.services import EmailService
    from django.conf import settings

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()

        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Please provide your email address'
            }, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if user exists
            return JsonResponse({
                'success': True,
                'message': 'If an account exists with this email, a verification link has been sent.'
            })

        if user.is_verified:
            return JsonResponse({
                'success': False,
                'error': 'Your email is already verified. You can login now.'
            }, status=400)

        # Invalidate old tokens
        EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )

        # Create new token
        verification_token = EmailVerificationToken.create_token(user, expires_hours=24)

        # Send email
        try:
            EmailService.send_verification_email(user=user, token=verification_token.token)
        except Exception as e:
            logger.error(f"Failed to resend verification email to {email}: {e}")

        return JsonResponse({
            'success': True,
            'message': 'If an account exists with this email, a verification link has been sent.'
        })

    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=500)


# -------------------------------------------------------
# Admin Dashboard View
# -------------------------------------------------------


def admin_dashboard(request):
    """
    Admin dashboard to view all registrations, messages, and partner registrations.
    Route: /view/
    Uses Django templates (not Jinja2) for proper CSRF support.
    """
    from django.shortcuts import redirect

    # Handle logout
    if request.GET.get('action') == 'logout':
        logout(request)
        return redirect('website:admin_dashboard')

    # Check if user is authenticated
    if not request.user.is_authenticated:
        # Handle login
        if request.method == 'POST':
            email = request.POST.get('email', '')
            password = request.POST.get('password', '')
            user = authenticate(request, email=email, password=password)
            if user is not None and user.is_staff:
                login(request, user)
                # Redirect to avoid form resubmission on refresh (PRG pattern)
                return redirect('website:admin_dashboard')
            else:
                return render(request, 'admin_view/login.html', {
                    'error': 'Invalid credentials or insufficient permissions'
                })
        return render(request, 'admin_view/login.html')


    return render(request, 'admin_view/dashboard.html', get_dashboard_context())


def get_dashboard_context():
    """Get context data for the dashboard."""
    registrations = TalentWaitlist.objects.all().order_by('-created_at')
    partners = PartnerRegistration.objects.all().order_by('-created_at')
    messages = ContactMessage.objects.all().order_by('-created_at')

    return {
        'registrations': registrations,
        'partners': partners,
        'messages': messages,
        'stats': {
            'registrations': registrations.count(),
            'partners': partners.count(),
            'messages': messages.count(),
            'unread': messages.filter(is_read=False).count(),
        }
    }


@csrf_exempt
@require_POST
def api_toggle_read(request):
    """Toggle read status of a message."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        msg_id = data.get('id')
        if msg_id:
            msg = ContactMessage.objects.get(id=msg_id)
            msg.is_read = not msg.is_read
            msg.save()
            return JsonResponse({'success': True, 'is_read': msg.is_read})
    except ContactMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
@require_POST
def api_toggle_contacted(request):
    """Toggle contacted status of a registration or partner."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        item_id = data.get('id')
        item_type = data.get('type')  # 'registration' or 'partner'

        if item_type == 'registration':
            item = TalentWaitlist.objects.get(id=item_id)
        elif item_type == 'partner':
            item = PartnerRegistration.objects.get(id=item_id)
        else:
            return JsonResponse({'error': 'Invalid type'}, status=400)

        item.is_contacted = not item.is_contacted
        item.save()
        return JsonResponse({'success': True, 'is_contacted': item.is_contacted})

    except (TalentWaitlist.DoesNotExist, PartnerRegistration.DoesNotExist):
        return JsonResponse({'error': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def export_registrations_csv(request):
    """Export talent registrations as CSV."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="talent_registrations_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Full Name', 'Email', 'Phone', 'Country', 'Opportunities', 'Skills', 'Preferred Fields', 'Contacted', 'Registered At'])

    for reg in TalentWaitlist.objects.all().order_by('-created_at'):
        writer.writerow([
            reg.id,
            reg.full_name,
            reg.email,
            reg.phone,
            reg.country,
            ', '.join(reg.opportunity_types) if reg.opportunity_types else '',
            ', '.join(reg.skills) if reg.skills else '',
            ', '.join(reg.preferred_fields) if reg.preferred_fields else '',
            'Yes' if reg.is_contacted else 'No',
            reg.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    return response


def export_partners_csv(request):
    """Export partner registrations as CSV."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="partner_registrations_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Organization', 'Industry', 'Size', 'Country', 'Contact Name', 'Job Title', 'Email', 'Phone', 'Interests', 'Message', 'Contacted', 'Registered At'])

    for partner in PartnerRegistration.objects.all().order_by('-created_at'):
        writer.writerow([
            partner.id,
            partner.organization_name,
            partner.industry,
            partner.company_size,
            partner.country,
            partner.full_name,
            partner.job_title,
            partner.email,
            partner.phone,
            ', '.join(partner.interest_types) if partner.interest_types else '',
            partner.message,
            'Yes' if partner.is_contacted else 'No',
            partner.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    return response


def export_messages_csv(request):
    """Export contact messages as CSV."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="contact_messages_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Full Name', 'Email', 'Phone', 'Country', 'Message', 'Read', 'Replied', 'Sent At'])

    for msg in ContactMessage.objects.all().order_by('-created_at'):
        writer.writerow([
            msg.id,
            msg.full_name,
            msg.email,
            msg.phone,
            msg.country,
            msg.message,
            'Yes' if msg.is_read else 'No',
            'Yes' if msg.is_replied else 'No',
            msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    return response


def export_all_csv(request):
    """Export all data (talents, partners, messages) as a combined ZIP file."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    import zipfile
    from io import BytesIO, StringIO

    # Create in-memory ZIP file
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Talents CSV
        talents_csv = StringIO()
        writer = csv.writer(talents_csv)
        writer.writerow(['ID', 'Full Name', 'Email', 'Phone', 'Country', 'Opportunities', 'Skills', 'Fields', 'Contacted', 'Registered At'])
        for reg in TalentWaitlist.objects.all().order_by('-created_at'):
            writer.writerow([
                reg.id,
                reg.full_name,
                reg.email,
                reg.phone or '',
                reg.country or '',
                ', '.join(reg.opportunity_types) if reg.opportunity_types else '',
                ', '.join(reg.skills) if reg.skills else '',
                ', '.join(reg.preferred_fields) if reg.preferred_fields else '',
                'Yes' if reg.is_contacted else 'No',
                reg.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        zip_file.writestr('talent_registrations.csv', talents_csv.getvalue())

        # Partners CSV
        partners_csv = StringIO()
        writer = csv.writer(partners_csv)
        writer.writerow(['ID', 'Organization', 'Industry', 'Country', 'Contact', 'Job Title', 'Email', 'Phone', 'Interests', 'Message', 'Contacted', 'Registered At'])
        for partner in PartnerRegistration.objects.all().order_by('-created_at'):
            writer.writerow([
                partner.id,
                partner.organization_name,
                partner.industry,
                partner.country,
                partner.full_name,
                partner.job_title,
                partner.email,
                partner.phone,
                ', '.join(partner.interest_types) if partner.interest_types else '',
                partner.message,
                'Yes' if partner.is_contacted else 'No',
                partner.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        zip_file.writestr('partner_registrations.csv', partners_csv.getvalue())

        # Messages CSV
        messages_csv = StringIO()
        writer = csv.writer(messages_csv)
        writer.writerow(['ID', 'Full Name', 'Email', 'Phone', 'Country', 'Message', 'Read', 'Replied', 'Sent At'])
        for msg in ContactMessage.objects.all().order_by('-created_at'):
            writer.writerow([
                msg.id,
                msg.full_name,
                msg.email,
                msg.phone,
                msg.country,
                msg.message,
                'Yes' if msg.is_read else 'No',
                'Yes' if msg.is_replied else 'No',
                msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        zip_file.writestr('contact_messages.csv', messages_csv.getvalue())

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="forgeforth_all_data_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip"'
    return response
