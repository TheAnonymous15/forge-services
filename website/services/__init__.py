# -*- coding: utf-8 -*-
"""
Website Services Package.

Provides:
- BlogService: Blog post CRUD operations
- BlogImageService: Blog image upload and management
- ImageProcessor: Image sanitization and compression
"""

# ImageProcessor can be imported standalone without Django
from .image_processor import ImageProcessor, process_image


def get_blog_service():
    """Lazy import of BlogService to avoid Django settings issues."""
    from .blog_service import BlogService
    return BlogService


def get_blog_image_service():
    """Lazy import of BlogImageService to avoid Django settings issues."""
    from .blog_service import BlogImageService
    return BlogImageService


__all__ = [
    'get_blog_service',
    'get_blog_image_service',
    'ImageProcessor',
    'process_image',
]
