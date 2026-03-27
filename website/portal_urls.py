# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Portal URL Configuration
=============================================
Unified portal routes for talent and organization dashboards.
Comprehensive full-scale portal with all features.
"""
from django.urls import path
from . import portal_views

app_name = "portal"

urlpatterns = [
    # =========================================================================
    # Authentication
    # =========================================================================
    path("login/", portal_views.portal_login_page, name="login"),
    path("login/submit/", portal_views.portal_login_submit, name="login_submit"),
    path("logout/", portal_views.portal_logout, name="logout"),

    # =========================================================================
    # Talent Portal - Main Pages
    # =========================================================================
    path("talent/dashboard/", portal_views.talent_dashboard, name="talent_dashboard"),
    path("talent/profile/", portal_views.talent_profile, name="talent_profile"),
    path("talent/resume/", portal_views.talent_resume, name="talent_resume"),
    path("talent/documents/", portal_views.talent_documents, name="talent_documents"),
    path("talent/opportunities/", portal_views.talent_opportunities, name="talent_opportunities"),
    path("talent/opportunity/<slug:slug>/", portal_views.talent_opportunity_detail, name="talent_opportunity_detail"),
    path("talent/applications/", portal_views.talent_applications, name="talent_applications"),
    path("talent/application/<uuid:application_id>/", portal_views.talent_application_detail, name="talent_application_detail"),
    path("talent/saved/", portal_views.talent_saved, name="talent_saved"),
    path("talent/interviews/", portal_views.talent_interviews, name="talent_interviews"),
    path("talent/recommendations/", portal_views.talent_recommendations, name="talent_recommendations"),
    path("talent/messages/", portal_views.talent_messages, name="talent_messages"),
    path("talent/notifications/", portal_views.talent_notifications, name="talent_notifications"),
    path("talent/settings/", portal_views.talent_settings, name="talent_settings"),
    path("talent/help/", portal_views.talent_help, name="talent_help"),

    # Progress & Goals
    path("talent/progress/", portal_views.talent_progress, name="talent_progress"),
    path("talent/goals/", portal_views.talent_goals, name="talent_goals"),
    path("talent/activities/", portal_views.talent_activities, name="talent_activities"),
    path("talent/contributions/", portal_views.talent_contributions, name="talent_contributions"),

    # Learning & Growth
    path("talent/skillsets/", portal_views.talent_skillsets, name="talent_skillsets"),
    path("talent/skills/", portal_views.talent_skills, name="talent_skills"),
    path("talent/certifications/", portal_views.talent_certifications, name="talent_certifications"),
    path("talent/learning/", portal_views.talent_learning, name="talent_learning"),

    # Network
    path("talent/connections/", portal_views.talent_connections, name="talent_connections"),
    path("talent/mentors/", portal_views.talent_mentors, name="talent_mentors"),
    path("talent/become-mentor/", portal_views.talent_become_mentor, name="talent_become_mentor"),

    # =========================================================================
    # Talent Portal - Actions API
    # =========================================================================
    path("talent/api/apply/<uuid:opportunity_id>/", portal_views.talent_apply_opportunity, name="talent_apply"),
    path("talent/api/save/<uuid:opportunity_id>/", portal_views.talent_save_opportunity, name="talent_save"),
    path("talent/api/withdraw/<uuid:application_id>/", portal_views.talent_withdraw_application, name="talent_withdraw"),

    # =========================================================================
    # Talent Portal - Profile API
    # =========================================================================
    path("talent/api/profile/update/", portal_views.talent_update_profile, name="talent_update_profile"),
    path("talent/api/education/add/", portal_views.talent_add_education, name="talent_add_education"),
    path("talent/api/education/delete/<uuid:education_id>/", portal_views.talent_delete_education, name="talent_delete_education"),
    path("talent/api/experience/add/", portal_views.talent_add_experience, name="talent_add_experience"),
    path("talent/api/experience/delete/<uuid:experience_id>/", portal_views.talent_delete_experience, name="talent_delete_experience"),
    path("talent/api/skill/add/", portal_views.talent_add_skill, name="talent_add_skill"),
    path("talent/api/skill/remove/<uuid:skill_id>/", portal_views.talent_remove_skill, name="talent_remove_skill"),

    # =========================================================================
    # Talent Portal - Notifications API
    # =========================================================================
    path("talent/api/notification/read/<uuid:notification_id>/", portal_views.talent_mark_notification_read, name="talent_mark_notification_read"),
    path("talent/api/recommendation/dismiss/<uuid:recommendation_id>/", portal_views.talent_dismiss_recommendation, name="talent_dismiss_recommendation"),

    # =========================================================================
    # Talent Portal - Documents API
    # =========================================================================
    path("talent/api/documents/upload/", portal_views.talent_upload_document, name="talent_upload_document"),
    path("talent/api/documents/delete/<uuid:document_id>/", portal_views.talent_delete_document, name="talent_delete_document"),
    path("talent/api/documents/rename/<uuid:document_id>/", portal_views.talent_rename_document, name="talent_rename_document"),
    path("talent/api/documents/set-primary/<uuid:document_id>/", portal_views.talent_set_primary_document, name="talent_set_primary_document"),
    path("talent/api/documents/update/<uuid:document_id>/", portal_views.talent_update_document, name="talent_update_document"),
    path("talent/api/documents/preview/<uuid:document_id>/", portal_views.talent_document_preview, name="talent_document_preview"),
    path("talent/api/documents/download/<uuid:document_id>/", portal_views.talent_download_document, name="talent_download_document"),
    path("talent/api/documents/stats/", portal_views.talent_document_stats, name="talent_document_stats"),

    # =========================================================================
    # Talent Portal - Resume Builder API
    # =========================================================================
    path("talent/api/resume/analyze/", portal_views.talent_resume_analyze, name="talent_resume_analyze"),
    path("talent/api/resume/suggestions/", portal_views.talent_resume_suggestions, name="talent_resume_suggestions"),
    path("talent/api/resume/export/pdf/", portal_views.talent_resume_export_pdf, name="talent_resume_export_pdf"),
    path("talent/api/resume/export/html/", portal_views.talent_resume_export_html, name="talent_resume_export_html"),
    path("talent/api/resume/save/", portal_views.talent_resume_save, name="talent_resume_save"),

    # =========================================================================
    # Organization Portal
    # =========================================================================
    path("org/dashboard/", portal_views.org_dashboard, name="org_dashboard"),
    path("org/opportunities/", portal_views.org_opportunities, name="org_opportunities"),
    path("org/applications/", portal_views.org_applications, name="org_applications"),
    path("org/team/", portal_views.org_team, name="org_team"),
    path("org/settings/", portal_views.org_settings, name="org_settings"),
]

