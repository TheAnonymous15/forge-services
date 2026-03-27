# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Automated Multi-language Translation System
Future-proof, scalable translation using external APIs with caching.

Features:
- Automatic translation using Google Translate, DeepL, or LibreTranslate
- Intelligent caching to minimize API calls
- RTL language support (Arabic, Hebrew, etc.)
- Batch translation for efficiency
- HTML-aware translation (preserves tags)
- Middleware for automatic page translation
- Jinja2 integration for template translation
"""

# Import languages first (no dependencies)
from .languages import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_language_name,
    get_language_direction,
    get_language_flag,
    is_rtl_language,
)

# Import translator (depends on languages)
from .translator import (
    TranslationService,
    get_translator,
    translate,
    t,
)


def get_jinja2_globals():
    """Get Jinja2 globals lazily to avoid circular imports."""
    from .jinja2_ext import JINJA2_GLOBALS
    return JINJA2_GLOBALS


def get_jinja2_filters():
    """Get Jinja2 filters lazily to avoid circular imports."""
    from .jinja2_ext import JINJA2_FILTERS
    return JINJA2_FILTERS


__all__ = [
    # Languages
    'SUPPORTED_LANGUAGES',
    'DEFAULT_LANGUAGE',
    'get_language_name',
    'get_language_direction',
    'get_language_flag',
    'is_rtl_language',
    # Translator
    'TranslationService',
    'get_translator',
    'translate',
    't',
    # Lazy loaders
    'get_jinja2_globals',
    'get_jinja2_filters',
]

