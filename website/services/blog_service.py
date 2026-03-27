# -*- coding: utf-8 -*-
"""
Blog Service - Handles blog post creation, image uploads, and management.
Provides secure storage for blog content and images in protected directories.

Storage Structure:
    website/blog_media/
        ├── {blog_id}/
        │   ├── featured.jpg
        │   ├── img_abc123.jpg
        │   ├── img_def456.png
        │   └── thumbnails/
        │       ├── thumb_abc123.jpg
        │       └── thumb_def456.jpg
        └── avatars/
            └── author_xyz.jpg
"""
import os
import secrets
import hashlib
import logging
import shutil
from pathlib import Path
from io import BytesIO
from typing import Optional, Tuple, List, Dict, Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.db import transaction

from PIL import Image

from website.models import BlogPost, BlogImage
from website.services.image_processor import ImageProcessor

logger = logging.getLogger(__name__)

# Protected blog media directory
BLOG_MEDIA_ROOT = Path(settings.BASE_DIR) / 'website' / 'blog_media'

# Custom storage for blog media (protected directory)
blog_media_storage = FileSystemStorage(
    location=str(BLOG_MEDIA_ROOT),
    base_url='/blog-media/'  # Served via Django view, not directly
)

# Allowed image types
ALLOWED_IMAGE_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp'],
}

# Max file sizes
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_FEATURED_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

# Thumbnail settings
THUMBNAIL_SIZE = (300, 300)


def ensure_blog_media_dir():
    """Ensure the blog_media root directory exists with proper permissions."""
    BLOG_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    # Set restrictive permissions (owner can read/write/execute, group can read/execute)
    try:
        os.chmod(BLOG_MEDIA_ROOT, 0o750)
    except Exception:
        pass
    return BLOG_MEDIA_ROOT


def get_blog_media_path(blog_id: str) -> Path:
    """Get the media directory path for a specific blog post."""
    ensure_blog_media_dir()
    blog_dir = BLOG_MEDIA_ROOT / blog_id
    blog_dir.mkdir(parents=True, exist_ok=True)
    return blog_dir


def get_blog_thumbnail_path(blog_id: str) -> Path:
    """Get the thumbnail directory path for a specific blog post."""
    blog_dir = get_blog_media_path(blog_id)
    thumb_dir = blog_dir / 'thumbnails'
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return thumb_dir


def generate_secure_filename(original_name: str, prefix: str = 'img', force_webp: bool = True) -> str:
    """
    Generate a secure unique filename.

    Args:
        original_name: Original filename
        prefix: Prefix for the new filename
        force_webp: If True, always use .webp extension (for processed images)

    Returns:
        Secure filename with unique ID
    """
    unique_id = secrets.token_hex(8)

    if force_webp:
        # After image processing, all images are converted to WebP
        return f"{prefix}_{unique_id}.webp"
    else:
        # Preserve original extension (for cases where we don't process)
        ext = Path(original_name).suffix.lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            ext = '.webp'
        return f"{prefix}_{unique_id}{ext}"


def delete_blog_media_folder(blog_id: str) -> bool:
    """Delete the entire media folder for a blog post."""
    try:
        blog_dir = BLOG_MEDIA_ROOT / blog_id
        if blog_dir.exists():
            shutil.rmtree(blog_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to delete blog media folder {blog_id}: {e}")
        return False


def extract_base64_images_from_content(blog_id: str, html_content: str) -> str:
    """
    Find all base64 data: image URLs embedded in HTML content,
    save each as a real file in blog_media/{blog_id}/, and replace
    the src attribute with the /blog-media/... URL.

    This repairs content created before the server-side upload handler
    was implemented.  Safe to call multiple times (skips non-base64 srcs).
    """
    import re
    import base64
    import mimetypes

    def replace_match(m):
        mime = m.group(1)          # e.g. image/jpeg
        b64  = m.group(2)
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return m.group(0)      # leave unchanged on decode error

        ext = mimetypes.guess_extension(mime) or '.webp'
        ext = ext.lstrip('.')
        if ext in ('jpe', 'jpg', 'jpeg'):
            ext = 'jpg'

        # Save to blog_media dir
        blog_dir = get_blog_media_path(blog_id)
        filename = generate_secure_filename(f'inline.{ext}', 'img')
        file_path = blog_dir / filename

        try:
            from website.services.image_processor import ImageProcessor
            from django.core.files.uploadedfile import InMemoryUploadedFile
            import io
            in_file = InMemoryUploadedFile(
                io.BytesIO(raw), 'image', filename, mime, len(raw), None
            )
            processor = ImageProcessor()
            result = processor.process_uploaded_file(in_file)
            if result['success']:
                filename = filename.rsplit('.', 1)[0] + '.webp'
                file_path = blog_dir / filename
                with open(file_path, 'wb') as f:
                    f.write(result['content'])
            else:
                # Fallback: save raw
                with open(file_path, 'wb') as f:
                    f.write(raw)
        except Exception as e:
            logger.warning(f"Image processor failed during extraction, saving raw: {e}")
            with open(file_path, 'wb') as f:
                f.write(raw)

        url = f"/blog-media/{blog_id}/{filename}"
        return f'src="{url}"'

    # Match src="data:image/...;base64,..."
    pattern = re.compile(
        r'src="data:(image/[a-zA-Z+]+);base64,([A-Za-z0-9+/=\n]+?)"',
        re.DOTALL
    )
    updated = pattern.sub(replace_match, html_content)
    return updated


class BlogService:
    """Service class for blog operations."""

    @staticmethod
    def create_post(
        title: str,
        content: str,
        author_name: str = "Community Contributor",
        author_email: str = "",
        excerpt: str = "",
        category: str = "insights",
        tags: List[str] = None,
        status: str = "draft",
        featured_image_url: str = "",
        featured_image_file: UploadedFile = None,
    ) -> Tuple[BlogPost, Optional[str]]:
        """
        Create a new blog post.

        Returns:
            Tuple of (BlogPost, error_message)
        """
        try:
            # Validate
            if not title or not title.strip():
                return None, "Title is required"
            if not content or not content.strip():
                return None, "Content is required"

            # Auto-generate excerpt if not provided
            if not excerpt:
                # Strip HTML tags if content is from Quill editor
                import re as _re
                plain = _re.sub(r'<[^>]+>', ' ', content)
                plain = _re.sub(r'\s+', ' ', plain).strip()
                excerpt = plain[:280].strip()
                if len(plain) > 280:
                    last_period = excerpt.rfind('.')
                    if last_period > 80:
                        excerpt = excerpt[:last_period + 1]
                    else:
                        excerpt += '…'

            # Process tags
            if tags is None:
                tags = []
            elif isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',') if t.strip()]

            with transaction.atomic():
                post = BlogPost.objects.create(
                    title=title.strip(),
                    content=content.strip(),
                    excerpt=excerpt.strip(),
                    author_name=author_name.strip() or "Community Contributor",
                    author_email=author_email.strip(),
                    category=category,
                    tags=tags,
                    status=status,
                    featured_image_url=featured_image_url,
                )

                # Handle featured image upload
                if featured_image_file:
                    success, error = BlogImageService.save_featured_image(post, featured_image_file)
                    if not success:
                        logger.warning(f"Failed to save featured image: {error}")

                return post, None

        except Exception as e:
            logger.error(f"Error creating blog post: {e}")
            return None, str(e)

    @staticmethod
    def update_post(
        blog_id: str,
        **kwargs
    ) -> Tuple[Optional[BlogPost], Optional[str]]:
        """Update an existing blog post."""
        try:
            post = BlogPost.objects.get(blog_id=blog_id)

            # Update allowed fields
            allowed_fields = [
                'title', 'content', 'excerpt', 'category', 'tags',
                'author_name', 'author_email', 'author_bio',
                'status', 'is_featured', 'allow_comments',
                'meta_title', 'meta_description', 'featured_image_url'
            ]

            for field in allowed_fields:
                if field in kwargs:
                    setattr(post, field, kwargs[field])

            # Handle status change to published
            if kwargs.get('status') == 'published' and not post.published_at:
                post.published_at = timezone.now()

            post.save()
            return post, None

        except BlogPost.DoesNotExist:
            return None, "Blog post not found"
        except Exception as e:
            logger.error(f"Error updating blog post: {e}")
            return None, str(e)

    @staticmethod
    def get_post_by_id(blog_id: str, include_drafts: bool = False) -> Optional[BlogPost]:
        """Get a blog post by its unique ID."""
        try:
            qs = BlogPost.objects.filter(blog_id=blog_id)
            if not include_drafts:
                qs = qs.filter(status='published')
            return qs.first()
        except Exception:
            return None

    @staticmethod
    def get_post_by_slug(slug: str, include_drafts: bool = False) -> Optional[BlogPost]:
        """Get a blog post by its slug."""
        try:
            qs = BlogPost.objects.filter(slug=slug)
            if not include_drafts:
                qs = qs.filter(status='published')
            return qs.first()
        except Exception:
            return None

    @staticmethod
    def list_posts(
        category: str = None,
        status: str = 'published',
        search: str = None,
        page: int = 1,
        per_page: int = 10,
        featured_only: bool = False,
    ) -> Dict[str, Any]:
        """List blog posts with filtering and pagination."""
        from django.db.models import Q
        from django.core.paginator import Paginator

        qs = BlogPost.objects.all()

        if status:
            qs = qs.filter(status=status)

        if category:
            qs = qs.filter(category=category)

        if featured_only:
            qs = qs.filter(is_featured=True)

        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(excerpt__icontains=search) |
                Q(content__icontains=search)
            )

        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page)

        return {
            'posts': list(page_obj.object_list),
            'total': paginator.count,
            'pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_prev': page_obj.has_previous(),
        }

    @staticmethod
    def delete_post(blog_id: str) -> Tuple[bool, Optional[str]]:
        """Delete a blog post and its associated images."""
        try:
            post = BlogPost.objects.get(blog_id=blog_id)

            # Delete the entire blog media folder (contains all images)
            delete_blog_media_folder(blog_id)

            # Delete the database record
            post.delete()

            logger.info(f"Blog post deleted: {blog_id}")
            return True, None

        except BlogPost.DoesNotExist:
            return False, "Blog post not found"
        except Exception as e:
            logger.error(f"Error deleting blog post: {e}")
            return False, str(e)


class BlogImageService:
    """Service class for blog image operations."""

    @staticmethod
    def validate_image(file: UploadedFile, max_size: int = MAX_IMAGE_SIZE) -> Tuple[bool, Optional[str]]:
        """
        Validate an uploaded image file.

        Checks:
        - File size
        - MIME type
        - Actual image validity
        """
        # Check file size
        if file.size > max_size:
            return False, f"File too large. Maximum size is {max_size // (1024*1024)}MB"

        # Check MIME type
        content_type = file.content_type
        if content_type not in ALLOWED_IMAGE_TYPES:
            return False, f"Invalid file type: {content_type}. Allowed types: JPEG, PNG, GIF, WebP"

        # Verify it's actually an image
        try:
            img = Image.open(file)
            img.verify()
            file.seek(0)  # Reset file pointer
        except Exception:
            return False, "Invalid image file"

        return True, None

    @staticmethod
    def create_thumbnail(image_file: UploadedFile, size: Tuple[int, int] = THUMBNAIL_SIZE) -> Optional[ContentFile]:
        """Create a thumbnail from an image file in WebP format."""
        try:
            img = Image.open(image_file)

            # Convert to RGB if necessary (WebP supports RGBA too)
            if img.mode in ('P', 'L', '1'):
                img = img.convert('RGB')
            elif img.mode == 'RGBA':
                pass  # Keep alpha for WebP
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Save to buffer as WebP
            buffer = BytesIO()
            img.save(buffer, format='WEBP', quality=85, optimize=True)
            buffer.seek(0)

            return ContentFile(buffer.read())

        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")
            return None

    @staticmethod
    def upload_image(
        file: UploadedFile,
        blog_post: BlogPost = None,
        alt_text: str = "",
        caption: str = "",
    ) -> Tuple[Optional[BlogImage], Optional[str]]:
        """
        Upload an image for a blog post to protected storage.

        Process:
        1. Sanitize: Remove metadata, embedded code, validate structure
        2. Compress: Convert to WebP with >90% quality, <1MB size
        3. Save to: blog_media/{blog_id}/img_xxx.webp

        Returns:
            Tuple of (BlogImage, error_message)
        """
        # First, validate basic file properties
        valid, error = BlogImageService.validate_image(file)
        if not valid:
            return None, error

        try:
            # Process image: sanitize and compress to WebP
            processor = ImageProcessor()
            result = processor.process_uploaded_file(file)

            if not result['success']:
                logger.warning(f"Image processing failed: {result['error']}")
                return None, result['error']

            processed_content = result['content']
            metadata = result['metadata']

            # Get dimensions from metadata
            width, height = metadata.get('final_size', (0, 0))

            # Determine blog_id for directory
            blog_id = blog_post.blog_id if blog_post else 'uploads'

            # Generate secure filename (always .webp now)
            secure_name = generate_secure_filename(file.name, 'img')

            # Get the blog's media directory
            blog_dir = get_blog_media_path(blog_id)
            thumb_dir = get_blog_thumbnail_path(blog_id)

            # Save the processed image to the protected directory
            image_path = blog_dir / secure_name
            with open(image_path, 'wb') as f:
                f.write(processed_content)

            # Create thumbnail from processed image
            thumbnail_path_str = ""
            try:
                thumb_img = Image.open(BytesIO(processed_content))
                thumb_img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

                thumb_name = f"thumb_{secure_name}"
                thumb_path = thumb_dir / thumb_name

                # Save thumbnail as WebP
                thumb_img.save(str(thumb_path), format='WEBP', quality=85)
                thumbnail_path_str = f"{blog_id}/thumbnails/{thumb_name}"
            except Exception as e:
                logger.warning(f"Failed to create thumbnail: {e}")

            # Create the image record
            blog_image = BlogImage(
                blog_post=blog_post,
                original_filename=file.name,
                alt_text=alt_text,
                caption=caption,
                file_size=len(processed_content),
                width=width,
                height=height,
                mime_type='image/webp',
                # Store relative paths from blog_media root
                image_path=f"{blog_id}/{secure_name}",
                thumbnail_path=thumbnail_path_str,
            )
            blog_image.save()

            logger.info(
                f"Image uploaded: {file.name} -> {secure_name} "
                f"({metadata.get('original_bytes', 0)} -> {len(processed_content)} bytes, "
                f"{metadata.get('compression_ratio', 0)}x compression)"
            )

            return blog_image, None

        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            return None, str(e)

    @staticmethod
    def save_featured_image(post: BlogPost, file: UploadedFile) -> Tuple[bool, Optional[str]]:
        """
        Save a featured image for a blog post to protected storage.

        Process:
        1. Validate file size (max 10MB input)
        2. Sanitize: Remove metadata, embedded code
        3. Compress: Convert to WebP with >90% quality, <1MB output
        """
        valid, error = BlogImageService.validate_image(file, MAX_FEATURED_IMAGE_SIZE)
        if not valid:
            return False, error

        try:
            # Process image: sanitize and compress to WebP
            processor = ImageProcessor()
            result = processor.process_uploaded_file(file)

            if not result['success']:
                logger.warning(f"Featured image processing failed: {result['error']}")
                return False, result['error']

            processed_content = result['content']
            metadata = result['metadata']

            # Get the blog's media directory
            blog_dir = get_blog_media_path(post.blog_id)

            # Generate secure filename for featured image (always .webp)
            secure_name = generate_secure_filename(file.name, 'featured')

            # Delete old featured image if exists
            if post.featured_image_path:
                old_path = BLOG_MEDIA_ROOT / post.featured_image_path
                if old_path.exists():
                    try:
                        old_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete old featured image: {e}")

            # Save the new featured image
            image_path = blog_dir / secure_name
            with open(image_path, 'wb') as f:
                f.write(processed_content)

            # Update the post with the relative path
            post.featured_image_path = f"{post.blog_id}/{secure_name}"
            post.save(update_fields=['featured_image_path'])

            logger.info(
                f"Featured image saved: {file.name} -> {secure_name} "
                f"({metadata.get('original_bytes', 0)} -> {len(processed_content)} bytes)"
            )

            return True, None

        except Exception as e:
            logger.error(f"Error saving featured image: {e}")
            return False, str(e)

    @staticmethod
    def get_image_by_token(token: str) -> Optional[BlogImage]:
        """Get an image by its upload token (for secure access)."""
        try:
            return BlogImage.objects.get(upload_token=token)
        except BlogImage.DoesNotExist:
            return None

    @staticmethod
    def delete_image(image_id: str) -> Tuple[bool, Optional[str]]:
        """Delete a blog image from storage and database."""
        try:
            image = BlogImage.objects.get(pk=image_id)

            # Delete image file from disk
            if image.image_path:
                file_path = BLOG_MEDIA_ROOT / image.image_path
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete image file: {e}")

            # Delete thumbnail from disk
            if image.thumbnail_path:
                thumb_path = BLOG_MEDIA_ROOT / image.thumbnail_path
                if thumb_path.exists():
                    try:
                        thumb_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete thumbnail: {e}")

            # Delete database record
            image.delete()

            logger.info(f"Image deleted: {image_id}")
            return True, None

        except BlogImage.DoesNotExist:
            return False, "Image not found"
        except Exception as e:
            logger.error(f"Error deleting image: {e}")
            return False, str(e)

