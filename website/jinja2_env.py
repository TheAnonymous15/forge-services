# -*- coding: utf-8 -*-
"""
Jinja2 environment for the website app.
Bridges Django's static files, URL reversal, request context, and translations into Jinja2.
"""

from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html
from jinja2 import Environment
from datetime import datetime


def csrf_input(request):
    """Generate a hidden input field with the CSRF token for Jinja2 templates."""
    return format_html('<input type="hidden" name="csrfmiddlewaretoken" value="{}">', get_token(request))


def date_filter(value, format_string='%b %d, %Y'):
    """
    Format a datetime object as a string.
    Usage: {{ post.created_at|date('M d, Y') }}
    """
    if value is None:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return value

    # Common format patterns (Django/PHP style to Python strftime style)
    if format_string == 'M d, Y':
        py_format = '%b %d, %Y'
    elif format_string == 'F d, Y':
        py_format = '%B %d, %Y'
    elif format_string == 'd/m/Y':
        py_format = '%d/%m/%Y'
    elif format_string == 'Y-m-d':
        py_format = '%Y-%m-%d'
    else:
        py_format = format_string

    try:
        return value.strftime(py_format)
    except (AttributeError, ValueError):
        return str(value)


SKILLS_LIST = [
    'Software Dev', 'Data Science', 'AI / ML', 'Cybersecurity', 'Cloud / DevOps',
    'Design / UX', 'Product Mgmt', 'Marketing', 'Finance', 'Accounting',
    'Healthcare', 'Nursing', 'Teaching', 'Legal', 'HR',
    'Engineering', 'Agriculture', 'Media', 'Customer Service', 'Operations',
    'Sales', 'Research', 'Architecture', 'Logistics', 'Other',
]

FIELDS_LIST = [
    {'value': 'technology',    'label': 'Technology'},
    {'value': 'healthcare',    'label': 'Healthcare'},
    {'value': 'education',     'label': 'Education'},
    {'value': 'finance',       'label': 'Finance'},
    {'value': 'marketing',     'label': 'Marketing'},
    {'value': 'design',        'label': 'Design'},
    {'value': 'engineering',   'label': 'Engineering'},
    {'value': 'legal',         'label': 'Legal'},
    {'value': 'hr',            'label': 'Human Resources'},
    {'value': 'operations',    'label': 'Operations'},
    {'value': 'agriculture',   'label': 'Agriculture'},
    {'value': 'media',         'label': 'Media'},
    {'value': 'research',      'label': 'Research'},
    {'value': 'hospitality',   'label': 'Hospitality'},
    {'value': 'manufacturing', 'label': 'Manufacturing'},
    {'value': 'other',         'label': 'Other'},
]


def environment(**options):
    # Remove 'using' kwarg if Django passes it — Jinja2 doesn't understand it
    options.pop("using", None)
    env = Environment(**options)

    # Import translation functions (lazy to avoid circular imports)
    from datetime import datetime
    from website.translations import SUPPORTED_LANGUAGES
    from website.translations.jinja2_ext import (
        JINJA2_GLOBALS,
        JINJA2_FILTERS,
        get_available_languages,
    )
    from django.conf import settings
    import os

    # API Service URL - defaults to localhost:9001 in development
    api_service_url = os.getenv('API_SERVICE_URL', 'http://localhost:9001')
    if not settings.DEBUG:
        api_service_url = os.getenv('API_SERVICE_URL', 'https://api.forgeforthafrica.com')

    # Talent Portal URL - different for dev and prod
    if settings.DEBUG:
        talent_portal_url = os.getenv('TALENT_PORTAL_URL_DEV', 'http://localhost:9003')
    else:
        talent_portal_url = os.getenv('TALENT_PORTAL_URL_PROD', 'https://talent.forgeforthafrica.com')

    env.globals.update({
        # {{ static('website/css/style.css') }}  →  /static/website/css/style.css
        "static": static,
        # {{ url('website:home') }}
        "url": reverse,
        # {{ csrf_input(request) }} - generates CSRF hidden input
        "csrf_input": csrf_input,
        # {{ now() }} - current datetime
        "now": datetime.now,
        # Modal data available on every page
        "skills_list": SKILLS_LIST,
        "fields_list": FIELDS_LIST,
        # Available languages for language switcher
        "available_languages": get_available_languages(),
        "SUPPORTED_LANGUAGES": SUPPORTED_LANGUAGES,
        # API configuration for AJAX requests
        "api_service_url": api_service_url,
        "website_auth_secret": os.getenv('WEBSITE_AUTH_KEY', ''),
        "AUTH_SERVICE_URL": getattr(settings, 'AUTH_SERVICE_URL', '/api/v1/auth'),
        "WEBSITE_AUTH_SECRET": getattr(settings, 'WEBSITE_AUTH_SECRET', ''),
        "SITE_URL": getattr(settings, 'SITE_URL', ''),
        "SITE_NAME": getattr(settings, 'SITE_NAME', 'ForgeForth Africa'),
        # Portal URLs
        "talent_portal_url": talent_portal_url,
        # Registration settings (absolute value from settings)
        "min_age": settings.MIN_AGE,
        # Django settings object for templates
        "settings": settings,
    })

    # Add translation globals
    env.globals.update(JINJA2_GLOBALS)

    # Add translation filters
    for name, func in JINJA2_FILTERS.items():
        env.filters[name] = func

    # Add custom filters
    env.filters['date'] = date_filter

    return env
