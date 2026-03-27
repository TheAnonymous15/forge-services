from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from pathlib import Path
import uuid
import secrets
import string
import os


# Protected blog media directory
BLOG_MEDIA_ROOT = Path(settings.BASE_DIR) / 'website' / 'blog_media'


def generate_blog_id():
    """Generate a short unique blog ID (8 characters)."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))


class BlogPost(models.Model):
    """
    Blog posts for the ForgeForth Africa website.
    Each post has a unique shareable ID.
    Images stored in protected directory: website/blog_media/{blog_id}/
    """
    CATEGORY_CHOICES = [
        ('insights', 'Insights'),
        ('stories', 'Success Stories'),
        ('tips', 'Career Tips'),
        ('news', 'Platform News'),
        ('africa', 'Africa Focus'),
        ('tech', 'Technology'),
        ('skills', 'Skills & Learning'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    # Unique identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blog_id = models.CharField(max_length=8, unique=True, default=generate_blog_id,
                               help_text="Short unique ID for sharing (e.g., abc12xyz)")
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    # Content
    title = models.CharField(max_length=255)
    excerpt = models.TextField(max_length=500, help_text="Brief summary shown in listings")
    content = models.TextField(help_text="Full blog content (supports Markdown)")

    # Featured Image - URL or path to protected storage
    featured_image_url = models.URLField(blank=True, default='', help_text="External URL to featured image")
    featured_image_path = models.CharField(max_length=255, blank=True, default='',
                                           help_text="Path to image in protected storage (e.g., {blog_id}/featured_xxx.jpg)")

    # Categorization
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='insights')
    tags = models.JSONField(default=list, help_text="List of tags")

    # Author info
    author_name = models.CharField(max_length=100, default='ForgeForth Team')
    author_email = models.EmailField(blank=True, default='')
    author_bio = models.TextField(blank=True, default='', max_length=300)
    author_avatar_path = models.CharField(max_length=255, blank=True, default='')

    # Status & Publishing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)

    # SEO
    meta_title = models.CharField(max_length=70, blank=True, default='')
    meta_description = models.CharField(max_length=160, blank=True, default='')

    # Statistics
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"
        indexes = [
            models.Index(fields=['blog_id']),
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.title} ({self.blog_id})"

    def save(self, *args, **kwargs):
        # Auto-generate slug from title
        if not self.slug:
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = self.blog_id
            slug = base_slug
            counter = 1
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        # Set published_at when first published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def featured_image(self):
        """Return the best available featured image URL."""
        if self.featured_image_path:
            return f"/blog-media/{self.featured_image_path}"
        return self.featured_image_url or ''

    @property
    def featured_image_full_path(self):
        """Return the full filesystem path to the featured image."""
        if self.featured_image_path:
            return BLOG_MEDIA_ROOT / self.featured_image_path
        return None

    @property
    def read_time(self):
        """Estimate read time based on word count."""
        word_count = len(self.content.split())
        minutes = max(1, word_count // 200)
        return f"{minutes} min read"

    @property
    def share_url(self):
        """Return the shareable URL using blog_id."""
        return f"/blog/p/{self.blog_id}"

    @property
    def full_url(self):
        """Return the full URL using slug."""
        return f"/blog/{self.slug}/"

    @property
    def author_initials(self):
        """Get author initials for avatar."""
        parts = self.author_name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return self.author_name[:2].upper()

    @property
    def media_dir(self):
        """Get the media directory path for this blog."""
        return BLOG_MEDIA_ROOT / self.blog_id

    def increment_views(self):
        """Increment view count."""
        self.view_count += 1
        self.save(update_fields=['view_count'])

    def get_images(self):
        """Get all images associated with this blog post."""
        return self.images.all()


def generate_upload_token():
    """Generate a secure token for image uploads."""
    return secrets.token_hex(32)


class BlogImage(models.Model):
    """
    Stores images uploaded for blog posts.
    Images are stored in protected directory: website/blog_media/{blog_id}/
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blog_post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='images',
                                  null=True, blank=True, help_text="Associated blog post (optional for temp uploads)")

    # Image paths (relative to BLOG_MEDIA_ROOT)
    image_path = models.CharField(max_length=255, help_text="Path to image in protected storage")
    thumbnail_path = models.CharField(max_length=255, blank=True, default='', help_text="Path to thumbnail")

    # Metadata
    original_filename = models.CharField(max_length=255, blank=True, default='')
    alt_text = models.CharField(max_length=255, blank=True, default='', help_text="Alt text for accessibility")
    caption = models.CharField(max_length=500, blank=True, default='')

    # File info
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=50, default='image/jpeg')

    # Security
    upload_token = models.CharField(max_length=64, unique=True, default=generate_upload_token,
                                    help_text="Token for secure access before blog is published")
    is_verified = models.BooleanField(default=False, help_text="Image has been scanned and verified safe")

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Blog Image"
        verbose_name_plural = "Blog Images"

    def __str__(self):
        return f"Image for {self.blog_post.blog_id if self.blog_post else 'unattached'}: {self.original_filename}"

    @property
    def url(self):
        """Return the URL for serving this image."""
        return f"/blog-media/{self.image_path}" if self.image_path else ''

    @property
    def thumbnail_url(self):
        """Return the URL for the thumbnail."""
        return f"/blog-media/{self.thumbnail_path}" if self.thumbnail_path else self.url

    @property
    def full_path(self):
        """Return the full filesystem path to the image."""
        return BLOG_MEDIA_ROOT / self.image_path if self.image_path else None

    @property
    def thumbnail_full_path(self):
        """Return the full filesystem path to the thumbnail."""
        return BLOG_MEDIA_ROOT / self.thumbnail_path if self.thumbnail_path else None

    @property
    def secure_url(self):
        """Return a secure URL with token for unpublished posts."""
        return f"/api/blog/image/{self.upload_token}/"

    def exists(self):
        """Check if the image file exists on disk."""
        return self.full_path.exists() if self.full_path else False


class PartnerRegistration(models.Model):
    """
    Stores partner/employer waitlist registrations from the Partner Modal.
    """
    INTEREST_CHOICES = [
        ('hire_talent', 'Hire Talent'),
        ('internships', 'Offer Internships'),
        ('volunteer', 'Volunteer Programs'),
        ('partnership', 'Partnership'),
    ]

    # Organization Details
    organization_name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100)
    company_size = models.CharField(max_length=50)
    country = models.CharField(max_length=100)

    # Contact Person
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    job_title = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, default='')

    # Interest
    interest_types = models.JSONField(default=list, help_text="List of interest types")
    message = models.TextField(blank=True, default='')

    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    is_contacted = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='', help_text="Internal notes")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Partner Registration"
        verbose_name_plural = "Partner Registrations"

    def __str__(self):
        return f"{self.organization_name} - {self.email}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def interest_display(self):
        """Return human-readable interest types."""
        mapping = dict(self.INTEREST_CHOICES)
        return [mapping.get(i, i) for i in self.interest_types]


class TalentWaitlist(models.Model):
    """
    Stores talent waitlist registrations from the Waitlist Modal.
    """
    OPPORTUNITY_CHOICES = [
        ('volunteer', 'Volunteer Programs'),
        ('internship', 'Internship'),
        ('job', 'Job Opportunity'),
        ('skillup', 'SkillUp Programs'),
    ]

    # Personal Info
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')

    # Opportunities
    opportunity_types = models.JSONField(default=list, help_text="List of opportunity types")

    # Skills & Fields
    skills = models.JSONField(default=list, help_text="List of skills")
    skills_other = models.CharField(max_length=255, blank=True, default='')
    preferred_fields = models.JSONField(default=list, help_text="List of preferred fields")
    fields_other = models.CharField(max_length=255, blank=True, default='')

    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    is_contacted = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='', help_text="Internal notes")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Talent Waitlist"
        verbose_name_plural = "Talent Waitlist Entries"

    def __str__(self):
        return f"{self.full_name} - {self.email}"


class ContactMessage(models.Model):
    """
    Stores contact form submissions.
    """
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    message = models.TextField()

    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    is_replied = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"

    def __str__(self):
        return f"{self.full_name} - {self.created_at.strftime('%Y-%m-%d')}"
