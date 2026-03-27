# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Jinja2 Translation Extensions
Provides translation functions and filters for templates.
"""

from markupsafe import Markup
from jinja2 import pass_context
from .languages import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, get_language_direction, get_language_flag
from .translator import get_translator, translate


@pass_context
def trans(context, text: str) -> str:
    """
    Translate text in Jinja2 templates.

    Usage in template:
        {{ trans('Hello World') }}
        {{ _('Hello World') }}  # Short alias
    """
    request = context.get('request')
    if not request:
        return text

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if lang == DEFAULT_LANGUAGE:
        return text

    return translate(text, lang)


@pass_context
def trans_html(context, html: str) -> Markup:
    """
    Translate HTML content while preserving tags.

    Usage:
        {{ trans_html('<p>Hello <strong>World</strong></p>') }}
    """
    request = context.get('request')
    if not request:
        return Markup(html)

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if lang == DEFAULT_LANGUAGE:
        return Markup(html)

    translator = get_translator()
    translated = translator.translate_html(html, lang)
    return Markup(translated)


def get_current_language(request) -> dict:
    """Get current language info for templates."""
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    return {
        'code': lang,
        'name': SUPPORTED_LANGUAGES.get(lang, {}).get('name', lang),
        'native_name': SUPPORTED_LANGUAGES.get(lang, {}).get('native_name', lang),
        'direction': get_language_direction(lang),
        'flag': get_language_flag(lang),
        'is_rtl': get_language_direction(lang) == 'rtl',
    }


def get_available_languages() -> list:
    """Get list of available languages for language switcher."""
    return [
        {
            'code': code,
            'name': info['name'],
            'native_name': info['native_name'],
            'flag': info['flag'],
            'direction': info['direction'],
            'region': info.get('region', ''),
        }
        for code, info in SUPPORTED_LANGUAGES.items()
    ]


def language_switcher_data(request) -> dict:
    """Get data needed for the language switcher component."""
    current = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    return {
        'current': get_current_language(request),
        'available': get_available_languages(),
        'current_code': current,
    }


# Template globals and filters to register
JINJA2_GLOBALS = {
    'trans': trans,
    '_': trans,  # Short alias
    'trans_html': trans_html,
    'get_current_language': get_current_language,
    'get_available_languages': get_available_languages,
    'language_switcher_data': language_switcher_data,
    'SUPPORTED_LANGUAGES': SUPPORTED_LANGUAGES,
}

JINJA2_FILTERS = {
    'translate': lambda text, lang: translate(text, lang),
}

