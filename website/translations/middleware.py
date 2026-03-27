# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Translation Middleware
Automatically translates pages based on user language preference.
"""

import re
import json
import logging
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import translation
from .languages import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, get_language_direction

logger = logging.getLogger('forgeforth.translations')


class TranslationMiddleware:
    """
    Middleware that handles automatic translation of responses.

    Language detection priority:
    1. URL parameter (?lang=xx)
    2. Cookie (ff_lang)
    3. Session
    4. Accept-Language header
    5. Default (English)
    """

    # Paths to skip translation (API, admin, static files)
    SKIP_PATHS = [
        '/api/',
        '/admin/',
        '/static/',
        '/media/',
        '/__debug__/',
        '/health',
    ]

    # Content types to translate
    TRANSLATABLE_CONTENT_TYPES = [
        'text/html',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Detect user's preferred language
        lang = self._detect_language(request)

        # Store language in request for views to access
        request.LANGUAGE_CODE = lang
        request.LANGUAGE_DIR = get_language_direction(lang)
        request.LANGUAGE_INFO = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES.get(DEFAULT_LANGUAGE))

        # Activate Django's translation system
        translation.activate(lang)

        # Get response
        response = self.get_response(request)

        # Set language cookie if changed
        if hasattr(request, '_lang_changed') and request._lang_changed:
            response.set_cookie(
                'ff_lang',
                lang,
                max_age=365 * 24 * 60 * 60,  # 1 year
                httponly=False,  # Allow JS access for language switcher
                samesite='Lax'
            )

        # Translate response if needed (disabled by default for performance)
        # Enable by setting TRANSLATE_RESPONSES = True in settings
        if getattr(settings, 'TRANSLATE_RESPONSES', False):
            if self._should_translate(request, response, lang):
                response = self._translate_response(response, lang)

        # Add language header
        response['Content-Language'] = lang

        # Deactivate translation
        translation.deactivate()

        return response

    def _detect_language(self, request: HttpRequest) -> str:
        """Detect user's preferred language."""

        # 1. Check URL parameter
        url_lang = request.GET.get('lang', '').lower()
        if url_lang in SUPPORTED_LANGUAGES:
            request._lang_changed = True
            request.session['lang'] = url_lang
            return url_lang

        # 2. Check cookie
        cookie_lang = request.COOKIES.get('ff_lang', '').lower()
        if cookie_lang in SUPPORTED_LANGUAGES:
            return cookie_lang

        # 3. Check session
        session_lang = request.session.get('lang', '').lower() if hasattr(request, 'session') else ''
        if session_lang in SUPPORTED_LANGUAGES:
            return session_lang

        # 4. Check Accept-Language header
        accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if accept_lang:
            # Parse Accept-Language header
            for lang_tag in accept_lang.split(','):
                lang_code = lang_tag.split(';')[0].strip().split('-')[0].lower()
                if lang_code in SUPPORTED_LANGUAGES:
                    return lang_code

        # 5. Default
        return DEFAULT_LANGUAGE

    def _should_translate(self, request: HttpRequest, response: HttpResponse, lang: str) -> bool:
        """Check if response should be translated."""

        # Don't translate if language is default (English)
        if lang == DEFAULT_LANGUAGE:
            return False

        # Don't translate error responses
        if response.status_code >= 400:
            return False

        # Check path
        path = request.path
        for skip_path in self.SKIP_PATHS:
            if path.startswith(skip_path):
                return False

        # Check content type
        content_type = response.get('Content-Type', '')
        if not any(ct in content_type for ct in self.TRANSLATABLE_CONTENT_TYPES):
            return False

        return True

    def _translate_response(self, response: HttpResponse, target_lang: str) -> HttpResponse:
        """Translate the response content."""
        try:
            from .translator import get_translator

            # Get response content
            content = response.content.decode('utf-8')

            # Translate HTML content
            translator = get_translator()
            translated_content = translator.translate_html(content, target_lang)

            # Update HTML lang attribute and direction
            translated_content = self._update_html_lang(translated_content, target_lang)

            # Update response
            response.content = translated_content.encode('utf-8')
            response['Content-Length'] = len(response.content)

        except Exception as e:
            logger.error(f"Response translation failed: {e}")

        return response

    def _update_html_lang(self, html: str, lang: str) -> str:
        """Update the HTML lang attribute and direction."""
        direction = get_language_direction(lang)

        # Update <html> tag
        html = re.sub(
            r'<html([^>]*)lang="[^"]*"([^>]*)>',
            f'<html\\1lang="{lang}"\\2>',
            html
        )

        # Add or update dir attribute for RTL languages
        if direction == 'rtl':
            if 'dir=' in html:
                html = re.sub(
                    r'<html([^>]*)dir="[^"]*"([^>]*)>',
                    f'<html\\1dir="rtl"\\2>',
                    html
                )
            else:
                html = re.sub(
                    r'<html([^>]*)>',
                    f'<html\\1 dir="rtl">',
                    html,
                    count=1
                )

        return html

