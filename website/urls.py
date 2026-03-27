# -*- coding: utf-8 -*-
from django.urls import path
from . import views
from .translations.api import translate_api, languages_api, translation_status_api

app_name = "website"

urlpatterns = [
    # Pages
    path("", views.home, name="home"),
    path("health", views.health, name="health"),
    path("about/", views.about, name="about"),
    path("for-talent/", views.for_talent, name="for_talent"),
    path("for-employers/", views.for_employers, name="for_employers"),
    path("platform/", views.platform, name="platform"),
    path("why-africa/", views.why_africa, name="why_africa"),
    path("gallery/", views.gallery, name="gallery"),
    path("contact/", views.contact, name="contact"),
    path("blog/", views.blog, name="blog"),
    path("blog/write/", views.blog_create, name="blog_create"),
    path("blog/p/<str:blog_id>/", views.blog_by_id, name="blog_by_id"),
    path("blog/preview/<str:blog_id>/", views.blog_preview, name="blog_preview"),
    path("blog/<slug:slug>/", views.blog_article, name="blog_article"),
    path("api/blog/", views.blog_api, name="blog_api"),
    path("api/blog/upload/", views.blog_image_upload, name="blog_image_upload"),
    path("api/blog/image/<str:token>/", views.blog_image_serve, name="blog_image_serve"),
    path("blog-media/<path:path>", views.serve_blog_media, name="serve_blog_media"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms-of-service/", views.terms_of_service, name="terms_of_service"),
    path("cookie-policy/", views.cookie_policy, name="cookie_policy"),
    path("foundation/", views.foundation, name="foundation"),

    # Authentication Pages (Web)
    path("accounts/register/", views.register_page, name="register"),
    path("accounts/login/", views.login_page, name="login"),
    path("verify-email", views.verify_email, name="verify_email"),

    # API Endpoints for Form Submissions
    path("api/partner-waitlist/", views.api_partner_registration, name="api_partner_registration"),
    path("api/talent-waitlist/", views.api_talent_waitlist, name="api_talent_waitlist"),
    path("api/contact/", views.api_contact_form, name="api_contact_form"),
    path("api/callback/", views.api_callback_request, name="api_callback_request"),
    path("api/auth/register/", views.api_register, name="api_register"),
    path("api/auth/resend-verification/", views.resend_verification_email, name="resend_verification"),

    # Translation API
    path("api/translate/", translate_api, name="translate_api"),
    path("api/translate/languages/", languages_api, name="languages_api"),
    path("api/translate/status/", translation_status_api, name="translation_status_api"),

    # Country Codes API
    path("api/country-codes/", views.api_country_codes, name="api_country_codes"),

    # Admin Dashboard
    path("view/", views.admin_dashboard, name="admin_dashboard"),
    path("view/api/toggle-read/", views.api_toggle_read, name="api_toggle_read"),
    path("view/api/toggle-contacted/", views.api_toggle_contacted, name="api_toggle_contacted"),
    path("view/export/all/", views.export_all_csv, name="export_all_csv"),
    path("view/export/registrations/", views.export_registrations_csv, name="export_registrations_csv"),
    path("view/export/partners/", views.export_partners_csv, name="export_partners_csv"),
    path("view/export/messages/", views.export_messages_csv, name="export_messages_csv"),
]
