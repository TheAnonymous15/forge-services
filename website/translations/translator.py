# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Automated Translation Service
Future-proof, scalable translation system using external APIs with caching.
"""

import hashlib
import json
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache
import threading

logger = logging.getLogger('forgeforth.translations')

# Translation cache directory
CACHE_DIR = Path(__file__).parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)


class TranslationService:
    """
    Automated translation service with multiple provider support.
    - Google Translate (free tier via googletrans or paid via Cloud API)
    - DeepL (high quality, paid)
    - LibreTranslate (self-hosted, free)
    - Fallback to original text if all fail
    """

    # Singleton instance
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._cache: Dict[str, Dict[str, str]] = {}
        self._provider = None
        self._load_cache()
        self._init_provider()

    def _init_provider(self):
        """Initialize the best available translation provider."""
        # Try providers in order of preference

        # 1. Try DeepL (best quality)
        deepl_key = os.environ.get('DEEPL_API_KEY')
        if deepl_key:
            try:
                import deepl
                self._deepl_client = deepl.Translator(deepl_key)
                self._provider = 'deepl'
                logger.info("Translation provider: DeepL")
                return
            except ImportError:
                logger.warning("DeepL key found but deepl package not installed")
            except Exception as e:
                logger.warning(f"DeepL initialization failed: {e}")

        # 2. Try Google Cloud Translate (paid, high quality)
        google_creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if google_creds:
            try:
                from google.cloud import translate_v2 as translate
                self._google_client = translate.Client()
                self._provider = 'google_cloud'
                logger.info("Translation provider: Google Cloud Translate")
                return
            except ImportError:
                logger.warning("Google credentials found but google-cloud-translate not installed")
            except Exception as e:
                logger.warning(f"Google Cloud Translate initialization failed: {e}")

        # 3. Try free googletrans library (rate limited but free)
        try:
            from googletrans import Translator
            self._googletrans_client = Translator()
            self._provider = 'googletrans'
            logger.info("Translation provider: googletrans (free)")
            return
        except ImportError:
            logger.warning("googletrans package not installed")
        except Exception as e:
            logger.warning(f"googletrans initialization failed: {e}")

        # 4. Try LibreTranslate (self-hosted or public instances)
        libre_url = os.environ.get('LIBRETRANSLATE_URL', 'https://libretranslate.com')
        libre_key = os.environ.get('LIBRETRANSLATE_API_KEY', '')
        try:
            import requests
            # Test connection
            resp = requests.get(f"{libre_url}/languages", timeout=5)
            if resp.status_code == 200:
                self._libre_url = libre_url
                self._libre_key = libre_key
                self._provider = 'libretranslate'
                logger.info(f"Translation provider: LibreTranslate ({libre_url})")
                return
        except Exception as e:
            logger.warning(f"LibreTranslate initialization failed: {e}")

        # 5. No provider available - will use fallback
        self._provider = None
        logger.warning("No translation provider available. Using fallback (original text).")

    def _get_cache_key(self, text: str, target_lang: str) -> str:
        """Generate a unique cache key for text + language."""
        content = f"{text}:{target_lang}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_cache(self):
        """Load translation cache from disk."""
        cache_file = CACHE_DIR / 'translations.json'
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} cached translations")
            except Exception as e:
                logger.error(f"Failed to load translation cache: {e}")
                self._cache = {}

    def _save_cache(self):
        """Save translation cache to disk."""
        cache_file = CACHE_DIR / 'translations.json'
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save translation cache: {e}")

    def translate(self, text: str, target_lang: str, source_lang: str = 'en') -> str:
        """
        Translate text to target language.

        Args:
            text: Text to translate
            target_lang: Target language code (e.g., 'fr', 'sw', 'ar')
            source_lang: Source language code (default: 'en')

        Returns:
            Translated text, or original text if translation fails
        """
        # Don't translate if target is same as source
        if target_lang == source_lang:
            return text

        # Don't translate empty text
        if not text or not text.strip():
            return text

        # Check cache first
        cache_key = self._get_cache_key(text, target_lang)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Translate using available provider
        translated = self._do_translate(text, target_lang, source_lang)

        # Cache the result
        if translated and translated != text:
            self._cache[cache_key] = translated
            # Save cache periodically (every 100 new translations)
            if len(self._cache) % 100 == 0:
                self._save_cache()

        return translated or text

    def _do_translate(self, text: str, target_lang: str, source_lang: str) -> Optional[str]:
        """Perform actual translation using the configured provider."""
        if not self._provider:
            return None

        try:
            if self._provider == 'deepl':
                return self._translate_deepl(text, target_lang, source_lang)
            elif self._provider == 'google_cloud':
                return self._translate_google_cloud(text, target_lang, source_lang)
            elif self._provider == 'googletrans':
                return self._translate_googletrans(text, target_lang, source_lang)
            elif self._provider == 'libretranslate':
                return self._translate_libretranslate(text, target_lang, source_lang)
        except Exception as e:
            logger.error(f"Translation failed ({self._provider}): {e}")
            return None

        return None

    def _translate_deepl(self, text: str, target_lang: str, source_lang: str) -> str:
        """Translate using DeepL API."""
        # DeepL uses uppercase language codes
        target = target_lang.upper()
        # Handle special cases
        if target == 'EN':
            target = 'EN-US'
        if target == 'PT':
            target = 'PT-BR'

        result = self._deepl_client.translate_text(text, target_lang=target)
        return result.text

    def _translate_google_cloud(self, text: str, target_lang: str, source_lang: str) -> str:
        """Translate using Google Cloud Translate API."""
        result = self._google_client.translate(text, target_language=target_lang)
        return result['translatedText']

    def _translate_googletrans(self, text: str, target_lang: str, source_lang: str) -> str:
        """Translate using free googletrans library."""
        result = self._googletrans_client.translate(text, dest=target_lang, src=source_lang)
        return result.text

    def _translate_libretranslate(self, text: str, target_lang: str, source_lang: str) -> str:
        """Translate using LibreTranslate API."""
        import requests

        payload = {
            'q': text,
            'source': source_lang,
            'target': target_lang,
            'format': 'text'
        }
        if self._libre_key:
            payload['api_key'] = self._libre_key

        response = requests.post(
            f"{self._libre_url}/translate",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()['translatedText']

    def translate_dict(self, data: Dict[str, Any], target_lang: str, source_lang: str = 'en') -> Dict[str, Any]:
        """
        Recursively translate all string values in a dictionary.

        Args:
            data: Dictionary with string values to translate
            target_lang: Target language code
            source_lang: Source language code

        Returns:
            Dictionary with translated values
        """
        if target_lang == source_lang:
            return data

        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.translate(value, target_lang, source_lang)
            elif isinstance(value, dict):
                result[key] = self.translate_dict(value, target_lang, source_lang)
            elif isinstance(value, list):
                result[key] = [
                    self.translate(item, target_lang, source_lang) if isinstance(item, str)
                    else self.translate_dict(item, target_lang, source_lang) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def translate_html(self, html: str, target_lang: str, source_lang: str = 'en') -> str:
        """
        Translate text content in HTML while preserving tags.

        Args:
            html: HTML string to translate
            target_lang: Target language code
            source_lang: Source language code

        Returns:
            HTML with translated text content
        """
        if target_lang == source_lang:
            return html

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')

            # Find all text nodes
            for element in soup.find_all(string=True):
                # Skip script and style content
                if element.parent.name in ['script', 'style', 'code', 'pre']:
                    continue

                text = str(element).strip()
                if text and len(text) > 1:  # Skip single characters
                    translated = self.translate(text, target_lang, source_lang)
                    element.replace_with(translated)

            return str(soup)
        except ImportError:
            logger.warning("BeautifulSoup not installed. HTML translation unavailable.")
            return html
        except Exception as e:
            logger.error(f"HTML translation failed: {e}")
            return html

    def batch_translate(self, texts: list, target_lang: str, source_lang: str = 'en') -> list:
        """
        Translate multiple texts efficiently (uses batching where supported).

        Args:
            texts: List of texts to translate
            target_lang: Target language code
            source_lang: Source language code

        Returns:
            List of translated texts
        """
        if target_lang == source_lang:
            return texts

        # Check cache for all texts first
        results = []
        to_translate = []
        to_translate_indices = []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                results.append(text)
            else:
                cache_key = self._get_cache_key(text, target_lang)
                if cache_key in self._cache:
                    results.append(self._cache[cache_key])
                else:
                    results.append(None)  # Placeholder
                    to_translate.append(text)
                    to_translate_indices.append(i)

        # Translate uncached texts
        if to_translate:
            # Some providers support batch translation
            if self._provider == 'deepl' and hasattr(self, '_deepl_client'):
                try:
                    target = target_lang.upper()
                    if target == 'EN':
                        target = 'EN-US'
                    batch_results = self._deepl_client.translate_text(to_translate, target_lang=target)
                    for idx, result in zip(to_translate_indices, batch_results):
                        results[idx] = result.text
                        cache_key = self._get_cache_key(texts[idx], target_lang)
                        self._cache[cache_key] = result.text
                except Exception as e:
                    logger.error(f"Batch translation failed: {e}")
                    # Fall back to individual translation
                    for idx, text in zip(to_translate_indices, to_translate):
                        results[idx] = self.translate(text, target_lang, source_lang)
            else:
                # Individual translation for other providers
                for idx, text in zip(to_translate_indices, to_translate):
                    results[idx] = self.translate(text, target_lang, source_lang)

        self._save_cache()
        return results

    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current translation provider."""
        return {
            'provider': self._provider or 'none',
            'cache_size': len(self._cache),
            'available': self._provider is not None
        }

    def clear_cache(self):
        """Clear the translation cache."""
        self._cache = {}
        cache_file = CACHE_DIR / 'translations.json'
        if cache_file.exists():
            cache_file.unlink()
        logger.info("Translation cache cleared")


# Global translator instance
_translator: Optional[TranslationService] = None


def get_translator() -> TranslationService:
    """Get the global translator instance."""
    global _translator
    if _translator is None:
        _translator = TranslationService()
    return _translator


def translate(text: str, target_lang: str, source_lang: str = 'en') -> str:
    """Convenience function for translating text."""
    return get_translator().translate(text, target_lang, source_lang)


def t(text: str, lang: str = 'en') -> str:
    """Short alias for translate function."""
    return translate(text, lang)

