# -*- coding: utf-8 -*-
import os
from django.conf import settings as django_settings


def waitlist_context(request):
    """Provide skills, fields lists and API configuration to all templates globally."""
    skills_list = [
        'Software Dev', 'Data Science', 'AI / ML', 'Cybersecurity', 'Cloud / DevOps',
        'Design / UX', 'Product Mgmt', 'Marketing', 'Finance', 'Accounting',
        'Healthcare', 'Nursing', 'Teaching', 'Legal', 'HR',
        'Engineering', 'Agriculture', 'Media', 'Customer Service', 'Operations',
        'Sales', 'Research', 'Architecture', 'Logistics', 'Other',
    ]
    fields_list = [
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

    # API Service URL - defaults to localhost:9001 in development
    api_service_url = os.getenv('API_SERVICE_URL', 'http://localhost:9001')
    if not django_settings.DEBUG:
        api_service_url = os.getenv('API_SERVICE_URL', 'https://api.forgeforthafrica.com')

    # Talent Portal URL - different for dev and prod
    if django_settings.DEBUG:
        talent_portal_url = os.getenv('TALENT_PORTAL_URL_DEV', 'http://localhost:9003')
    else:
        talent_portal_url = os.getenv('TALENT_PORTAL_URL_PROD', 'https://talent.forgeforthafrica.com')

    return {
        'skills_list': skills_list,
        'fields_list': fields_list,
        # API configuration for AJAX requests
        'api_service_url': api_service_url,
        'website_auth_secret': os.getenv('WEBSITE_AUTH_KEY', ''),
        'AUTH_SERVICE_URL': getattr(django_settings, 'AUTH_SERVICE_URL', '/api/v1/auth'),
        'WEBSITE_AUTH_SECRET': getattr(django_settings, 'WEBSITE_AUTH_SECRET', ''),
        'SITE_URL': getattr(django_settings, 'SITE_URL', ''),
        'SITE_NAME': getattr(django_settings, 'SITE_NAME', 'ForgeForth Africa'),
        # Portal URLs
        'talent_portal_url': talent_portal_url,
        # Registration settings (absolute value from settings)
        'min_age': int(django_settings.MIN_AGE)
    }

