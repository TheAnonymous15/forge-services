# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Root URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [

    # Admin
    path("admin/", admin.site.urls),

    # -------------------------------------------------------
    # Core Services (Health Checks, Diagnostics)
    # -------------------------------------------------------
    path("api/", include("core.urls")),

    # -------------------------------------------------------
    # Informational Website
    # -------------------------------------------------------
    path("", include("website.urls")),

    # -------------------------------------------------------
    # Unified Portal (Talent & Organization Dashboards)
    # -------------------------------------------------------
    path("portal/", include("website.portal_urls", namespace="portal")),

    # -------------------------------------------------------
    # API v1
    # -------------------------------------------------------

    # 1. Identity & Access Management
    path("api/v1/auth/", include("accounts.urls")),

    # 2. User & Talent Profile Management
    path("api/v1/profiles/", include("profiles.urls")),

    # 3. Organization & Opportunity Management
    path("api/v1/organizations/", include("organizations.urls")),

    # 4. Application & Workflow Management
    path("api/v1/applications/", include("applications.urls")),

    # 5. Secure Media Ingestion & Processing
    path("api/v1/media/", include("media.urls")),

    # 6. Talent Intelligence & Skill Extraction
    path("api/v1/intelligence/", include("intelligence.urls")),

    # 7. Matching & Recommendation Engine
    path("api/v1/matching/", include("matching.urls")),

    # 8. Communication & Notification System
    path("api/v1/communications/", include("communications.urls")),

    # 9. Analytics & Reporting System
    path("api/v1/analytics/", include("analytics.urls")),

    # 10. Administration & Governance
    path("api/v1/administration/", include("administration.urls")),

    # 11. Security & Compliance Layer
    path("api/v1/security/", include("security.urls")),

    # 12. Infrastructure & DevOps Management
    path("api/v1/devops/", include("devops.urls")),

    # -------------------------------------------------------
    # Secure Storage Service (standalone subsystem)
    # -------------------------------------------------------
    path("storage/", include("storage.urls")),

    # -------------------------------------------------------
    # API Docs
    # -------------------------------------------------------
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# -------------------------------------------------------
# Custom Error Handlers
# -------------------------------------------------------
handler400 = 'website.views.error_400'
handler403 = 'website.views.error_403'
handler404 = 'website.views.error_404'
handler500 = 'website.views.error_500'

