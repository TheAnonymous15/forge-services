# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Supported Languages Configuration
Comprehensive list of supported languages with metadata for UI and translation.
"""

# Default language (English)
DEFAULT_LANGUAGE = 'en'

# Supported languages with full metadata
# Format: code -> { name, native_name, flag, direction, region }
SUPPORTED_LANGUAGES = {
    # ── English (Default) ────────────────────────────────────
    'en': {
        'name': 'English',
        'native_name': 'English',
        'flag': '🇬🇧',
        'direction': 'ltr',
        'region': 'Global',
    },

    # ── Major African Languages ──────────────────────────────
    'sw': {
        'name': 'Swahili',
        'native_name': 'Kiswahili',
        'flag': '🇰🇪',
        'direction': 'ltr',
        'region': 'East Africa',
    },
    'am': {
        'name': 'Amharic',
        'native_name': 'አማርኛ',
        'flag': '🇪🇹',
        'direction': 'ltr',
        'region': 'Ethiopia',
    },
    'ha': {
        'name': 'Hausa',
        'native_name': 'Hausa',
        'flag': '🇳🇬',
        'direction': 'ltr',
        'region': 'West Africa',
    },
    'yo': {
        'name': 'Yoruba',
        'native_name': 'Yorùbá',
        'flag': '🇳🇬',
        'direction': 'ltr',
        'region': 'Nigeria',
    },
    'ig': {
        'name': 'Igbo',
        'native_name': 'Igbo',
        'flag': '🇳🇬',
        'direction': 'ltr',
        'region': 'Nigeria',
    },
    'zu': {
        'name': 'Zulu',
        'native_name': 'isiZulu',
        'flag': '🇿🇦',
        'direction': 'ltr',
        'region': 'South Africa',
    },
    'xh': {
        'name': 'Xhosa',
        'native_name': 'isiXhosa',
        'flag': '🇿🇦',
        'direction': 'ltr',
        'region': 'South Africa',
    },
    'af': {
        'name': 'Afrikaans',
        'native_name': 'Afrikaans',
        'flag': '🇿🇦',
        'direction': 'ltr',
        'region': 'South Africa',
    },
    'so': {
        'name': 'Somali',
        'native_name': 'Soomaali',
        'flag': '🇸🇴',
        'direction': 'ltr',
        'region': 'Horn of Africa',
    },
    'rw': {
        'name': 'Kinyarwanda',
        'native_name': 'Ikinyarwanda',
        'flag': '🇷🇼',
        'direction': 'ltr',
        'region': 'Rwanda',
    },

    # ── Colonial/Official Languages ──────────────────────────
    'fr': {
        'name': 'French',
        'native_name': 'Français',
        'flag': '🇫🇷',
        'direction': 'ltr',
        'region': 'Francophone Africa',
    },
    'pt': {
        'name': 'Portuguese',
        'native_name': 'Português',
        'flag': '🇵🇹',
        'direction': 'ltr',
        'region': 'Lusophone Africa',
    },
    'ar': {
        'name': 'Arabic',
        'native_name': 'العربية',
        'flag': '🇸🇦',
        'direction': 'rtl',
        'region': 'North Africa & Middle East',
    },
    'es': {
        'name': 'Spanish',
        'native_name': 'Español',
        'flag': '🇪🇸',
        'direction': 'ltr',
        'region': 'Equatorial Guinea',
    },

    # ── International Languages ──────────────────────────────
    'zh': {
        'name': 'Chinese (Simplified)',
        'native_name': '中文',
        'flag': '🇨🇳',
        'direction': 'ltr',
        'region': 'China',
    },
    'de': {
        'name': 'German',
        'native_name': 'Deutsch',
        'flag': '🇩🇪',
        'direction': 'ltr',
        'region': 'Germany',
    },
    'hi': {
        'name': 'Hindi',
        'native_name': 'हिन्दी',
        'flag': '🇮🇳',
        'direction': 'ltr',
        'region': 'India',
    },
    'ja': {
        'name': 'Japanese',
        'native_name': '日本語',
        'flag': '🇯🇵',
        'direction': 'ltr',
        'region': 'Japan',
    },
    'ko': {
        'name': 'Korean',
        'native_name': '한국어',
        'flag': '🇰🇷',
        'direction': 'ltr',
        'region': 'Korea',
    },
    'ru': {
        'name': 'Russian',
        'native_name': 'Русский',
        'flag': '🇷🇺',
        'direction': 'ltr',
        'region': 'Russia',
    },
    'tr': {
        'name': 'Turkish',
        'native_name': 'Türkçe',
        'flag': '🇹🇷',
        'direction': 'ltr',
        'region': 'Turkey',
    },
    'it': {
        'name': 'Italian',
        'native_name': 'Italiano',
        'flag': '🇮🇹',
        'direction': 'ltr',
        'region': 'Italy',
    },
    'nl': {
        'name': 'Dutch',
        'native_name': 'Nederlands',
        'flag': '🇳🇱',
        'direction': 'ltr',
        'region': 'Netherlands',
    },
    'pl': {
        'name': 'Polish',
        'native_name': 'Polski',
        'flag': '🇵🇱',
        'direction': 'ltr',
        'region': 'Poland',
    },
}


def get_language_name(code: str) -> str:
    """Get the English name of a language by its code."""
    lang = SUPPORTED_LANGUAGES.get(code.lower())
    return lang['name'] if lang else code


def get_language_native_name(code: str) -> str:
    """Get the native name of a language by its code."""
    lang = SUPPORTED_LANGUAGES.get(code.lower())
    return lang['native_name'] if lang else code


def get_language_direction(code: str) -> str:
    """Get the text direction (ltr/rtl) for a language."""
    lang = SUPPORTED_LANGUAGES.get(code.lower())
    return lang['direction'] if lang else 'ltr'


def get_language_flag(code: str) -> str:
    """Get the flag emoji for a language."""
    lang = SUPPORTED_LANGUAGES.get(code.lower())
    return lang['flag'] if lang else '🌍'


def is_rtl_language(code: str) -> bool:
    """Check if a language uses right-to-left text direction."""
    return get_language_direction(code) == 'rtl'


def get_language_info(code: str) -> dict:
    """Get full information about a language."""
    return SUPPORTED_LANGUAGES.get(code.lower(), {
        'name': code,
        'native_name': code,
        'flag': '🌍',
        'direction': 'ltr',
        'region': 'Unknown',
    })

