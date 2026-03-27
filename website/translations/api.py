# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Translation API Views
Provides API endpoints for client-side translation requests.
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache

from website.translations import get_translator, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

logger = logging.getLogger('forgeforth.translations')


@require_http_methods(["POST"])
@csrf_protect
def translate_api(request):
    """
    API endpoint for translating text.

    POST /api/translate/

    Request body:
        {
            "text": "Hello world",  # Single text
            "texts": ["Hello", "World"],  # Or multiple texts
            "target_lang": "fr",
            "source_lang": "en"  # Optional, defaults to 'en'
        }

    Response:
        {
            "translation": "Bonjour le monde",  # For single text
            "translations": ["Bonjour", "Monde"],  # For multiple texts
            "source_lang": "en",
            "target_lang": "fr"
        }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    target_lang = data.get('target_lang', '').lower()
    source_lang = data.get('source_lang', DEFAULT_LANGUAGE).lower()

    # Validate target language
    if not target_lang:
        return JsonResponse({'error': 'target_lang is required'}, status=400)

    if target_lang not in SUPPORTED_LANGUAGES:
        return JsonResponse({
            'error': f'Unsupported target language: {target_lang}',
            'supported': list(SUPPORTED_LANGUAGES.keys())
        }, status=400)

    # Get translator
    translator = get_translator()

    # Check if single text or batch
    if 'text' in data:
        text = data['text']
        if not text or not isinstance(text, str):
            return JsonResponse({'error': 'text must be a non-empty string'}, status=400)

        # Rate limiting check (simple implementation)
        rate_key = f"translate_rate:{request.META.get('REMOTE_ADDR', 'unknown')}"
        rate_count = cache.get(rate_key, 0)
        if rate_count > 100:  # 100 requests per minute
            return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
        cache.set(rate_key, rate_count + 1, 60)

        # Translate
        try:
            translation = translator.translate(text, target_lang, source_lang)
            return JsonResponse({
                'translation': translation,
                'source_lang': source_lang,
                'target_lang': target_lang,
            })
        except Exception as e:
            logger.error(f"Translation API error: {e}")
            return JsonResponse({'error': 'Translation failed'}, status=500)

    elif 'texts' in data:
        texts = data['texts']
        if not texts or not isinstance(texts, list):
            return JsonResponse({'error': 'texts must be a non-empty list'}, status=400)

        # Limit batch size
        if len(texts) > 50:
            return JsonResponse({'error': 'Maximum 50 texts per request'}, status=400)

        # Rate limiting
        rate_key = f"translate_rate:{request.META.get('REMOTE_ADDR', 'unknown')}"
        rate_count = cache.get(rate_key, 0)
        if rate_count > 100:
            return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
        cache.set(rate_key, rate_count + len(texts), 60)

        # Batch translate
        try:
            translations = translator.batch_translate(texts, target_lang, source_lang)
            return JsonResponse({
                'translations': translations,
                'source_lang': source_lang,
                'target_lang': target_lang,
            })
        except Exception as e:
            logger.error(f"Batch translation API error: {e}")
            return JsonResponse({'error': 'Translation failed'}, status=500)

    else:
        return JsonResponse({'error': 'text or texts field required'}, status=400)


@require_http_methods(["GET"])
def languages_api(request):
    """
    API endpoint to get supported languages.

    GET /api/translate/languages/

    Response:
        {
            "languages": [
                {
                    "code": "en",
                    "name": "English",
                    "native_name": "English",
                    "direction": "ltr",
                    "flag": "🇬🇧"
                },
                ...
            ],
            "default": "en"
        }
    """
    languages = [
        {
            'code': code,
            'name': info['name'],
            'native_name': info['native_name'],
            'direction': info['direction'],
            'flag': info['flag'],
            'region': info.get('region', ''),
        }
        for code, info in SUPPORTED_LANGUAGES.items()
    ]

    return JsonResponse({
        'languages': languages,
        'default': DEFAULT_LANGUAGE,
    })


@require_http_methods(["GET"])
def translation_status_api(request):
    """
    API endpoint to check translation service status.

    GET /api/translate/status/

    Response:
        {
            "status": "ok",
            "provider": "googletrans",
            "cache_size": 1234
        }
    """
    translator = get_translator()
    info = translator.get_provider_info()

    return JsonResponse({
        'status': 'ok' if info['available'] else 'degraded',
        'provider': info['provider'],
        'cache_size': info['cache_size'],
    })

