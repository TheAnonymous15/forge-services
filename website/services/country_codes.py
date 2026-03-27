# -*- coding: utf-8 -*-
"""
Country Codes Service
Fetches country calling codes from REST Countries API and caches them locally.
"""
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

# Cache file location
CACHE_DIR = Path(__file__).parent.parent / 'cache'
CACHE_FILE = CACHE_DIR / 'country_codes.json'
CACHE_DURATION_DAYS = 30  # Refresh cache after 30 days


def ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cached_codes():
    """Get country codes from cache if valid."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Check if cache is still valid
                cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
                if datetime.now() - cached_at < timedelta(days=CACHE_DURATION_DAYS):
                    return data.get('countries', [])
    except Exception as e:
        logger.warning(f"Error reading cache: {e}")
    return None


def save_to_cache(countries):
    """Save country codes to cache."""
    try:
        ensure_cache_dir()
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'cached_at': datetime.now().isoformat(),
                'countries': countries
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"Cached {len(countries)} country codes")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def fetch_from_api():
    """Fetch country codes from REST Countries API."""
    try:
        # Use REST Countries API
        url = "https://restcountries.com/v3.1/all?fields=name,idd,cca2,flag"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        data = response.json()
        countries = []

        for country in data:
            name = country.get('name', {}).get('common', '')
            idd = country.get('idd', {})
            root = idd.get('root', '')
            suffixes = idd.get('suffixes', [])
            cca2 = country.get('cca2', '')
            flag = country.get('flag', '')

            # Build dial code(s)
            if root and suffixes:
                # Take the first suffix for simplicity
                dial_code = f"{root}{suffixes[0]}" if suffixes else root
            elif root:
                dial_code = root
            else:
                continue  # Skip countries without dial codes

            # Clean dial code
            dial_code = dial_code.replace(' ', '')

            if dial_code and name:
                countries.append({
                    'name': name,
                    'code': cca2,
                    'dial_code': dial_code,
                    'flag': flag
                })

        # Sort by name
        countries.sort(key=lambda x: x['name'])

        # Move popular African countries to top
        priority_codes = ['ZA', 'KE', 'NG', 'GH', 'UG', 'TZ', 'ET', 'EG', 'MA', 'RW']
        priority_countries = []
        other_countries = []

        for c in countries:
            if c['code'] in priority_codes:
                priority_countries.append(c)
            else:
                other_countries.append(c)

        # Sort priority by the order in priority_codes
        priority_countries.sort(key=lambda x: priority_codes.index(x['code']) if x['code'] in priority_codes else 999)

        return priority_countries + other_countries

    except requests.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching country codes: {e}")
        return None


def get_fallback_codes():
    """Return fallback country codes if API and cache fail."""
    return [
        {'name': 'South Africa', 'code': 'ZA', 'dial_code': '+27', 'flag': '🇿🇦'},
        {'name': 'Kenya', 'code': 'KE', 'dial_code': '+254', 'flag': '🇰🇪'},
        {'name': 'Nigeria', 'code': 'NG', 'dial_code': '+234', 'flag': '🇳🇬'},
        {'name': 'Ghana', 'code': 'GH', 'dial_code': '+233', 'flag': '🇬🇭'},
        {'name': 'Uganda', 'code': 'UG', 'dial_code': '+256', 'flag': '🇺🇬'},
        {'name': 'Tanzania', 'code': 'TZ', 'dial_code': '+255', 'flag': '🇹🇿'},
        {'name': 'Ethiopia', 'code': 'ET', 'dial_code': '+251', 'flag': '🇪🇹'},
        {'name': 'Egypt', 'code': 'EG', 'dial_code': '+20', 'flag': '🇪🇬'},
        {'name': 'Morocco', 'code': 'MA', 'dial_code': '+212', 'flag': '🇲🇦'},
        {'name': 'Rwanda', 'code': 'RW', 'dial_code': '+250', 'flag': '🇷🇼'},
        {'name': 'Cameroon', 'code': 'CM', 'dial_code': '+237', 'flag': '🇨🇲'},
        {'name': 'Ivory Coast', 'code': 'CI', 'dial_code': '+225', 'flag': '🇨🇮'},
        {'name': 'Senegal', 'code': 'SN', 'dial_code': '+221', 'flag': '🇸🇳'},
        {'name': 'Zimbabwe', 'code': 'ZW', 'dial_code': '+263', 'flag': '🇿🇼'},
        {'name': 'Zambia', 'code': 'ZM', 'dial_code': '+260', 'flag': '🇿🇲'},
        {'name': 'Botswana', 'code': 'BW', 'dial_code': '+267', 'flag': '🇧🇼'},
        {'name': 'Namibia', 'code': 'NA', 'dial_code': '+264', 'flag': '🇳🇦'},
        {'name': 'Mozambique', 'code': 'MZ', 'dial_code': '+258', 'flag': '🇲🇿'},
        {'name': 'Algeria', 'code': 'DZ', 'dial_code': '+213', 'flag': '🇩🇿'},
        {'name': 'Tunisia', 'code': 'TN', 'dial_code': '+216', 'flag': '🇹🇳'},
        {'name': 'United States', 'code': 'US', 'dial_code': '+1', 'flag': '🇺🇸'},
        {'name': 'United Kingdom', 'code': 'GB', 'dial_code': '+44', 'flag': '🇬🇧'},
        {'name': 'India', 'code': 'IN', 'dial_code': '+91', 'flag': '🇮🇳'},
        {'name': 'China', 'code': 'CN', 'dial_code': '+86', 'flag': '🇨🇳'},
        {'name': 'Australia', 'code': 'AU', 'dial_code': '+61', 'flag': '🇦🇺'},
        {'name': 'Germany', 'code': 'DE', 'dial_code': '+49', 'flag': '🇩🇪'},
        {'name': 'France', 'code': 'FR', 'dial_code': '+33', 'flag': '🇫🇷'},
        {'name': 'United Arab Emirates', 'code': 'AE', 'dial_code': '+971', 'flag': '🇦🇪'},
        {'name': 'Canada', 'code': 'CA', 'dial_code': '+1', 'flag': '🇨🇦'},
        {'name': 'Brazil', 'code': 'BR', 'dial_code': '+55', 'flag': '🇧🇷'},
    ]


def get_country_codes(force_refresh=False):
    """
    Get country codes - tries cache first, then API, then fallback.

    Args:
        force_refresh: If True, skip cache and fetch from API

    Returns:
        List of country code dictionaries
    """
    # Try cache first (unless force refresh)
    if not force_refresh:
        cached = get_cached_codes()
        if cached:
            logger.debug(f"Using cached country codes ({len(cached)} countries)")
            return cached

    # Fetch from API
    logger.info("Fetching country codes from API...")
    countries = fetch_from_api()

    if countries:
        save_to_cache(countries)
        return countries

    # Try cache even if expired
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cached = data.get('countries', [])
                if cached:
                    logger.warning("Using expired cache as fallback")
                    return cached
    except Exception:
        pass

    # Last resort: use fallback
    logger.warning("Using fallback country codes")
    return get_fallback_codes()


# Pre-load cache on module import (non-blocking)
def init_cache():
    """Initialize cache in background."""
    try:
        if not CACHE_FILE.exists():
            # Only fetch if no cache exists
            countries = fetch_from_api()
            if countries:
                save_to_cache(countries)
    except Exception as e:
        logger.debug(f"Cache init skipped: {e}")

