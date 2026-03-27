# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Profiles URLs (MVP1)
=========================================
URL patterns for profiles API.
"""
from django.urls import path
from . import views

app_name = "profiles"

urlpatterns = [
    # Health check
    path('health', views.profiles_health, name='health'),

    # My profile
    path('me', views.MyProfileView.as_view(), name='my_profile'),
    path('me/completion', views.profile_completion, name='profile_completion'),

    # Public profiles
    path('search', views.ProfileSearchView.as_view(), name='profile_search'),
    path('<uuid:id>', views.ProfileDetailView.as_view(), name='profile_detail'),

    # Education
    path('me/education', views.EducationListCreateView.as_view(), name='education_list'),
    path('me/education/<uuid:id>', views.EducationDetailView.as_view(), name='education_detail'),

    # Work Experience
    path('me/experience', views.WorkExperienceListCreateView.as_view(), name='experience_list'),
    path('me/experience/<uuid:id>', views.WorkExperienceDetailView.as_view(), name='experience_detail'),

    # Skills
    path('me/skills', views.SkillListCreateView.as_view(), name='skill_list'),
    path('me/skills/bulk', views.BulkSkillsView.as_view(), name='skill_bulk'),
    path('me/skills/<uuid:id>', views.SkillDetailView.as_view(), name='skill_detail'),

    # Certifications
    path('me/certifications', views.CertificationListCreateView.as_view(), name='certification_list'),
    path('me/certifications/<uuid:id>', views.CertificationDetailView.as_view(), name='certification_detail'),

    # Languages
    path('me/languages', views.LanguageListCreateView.as_view(), name='language_list'),
    path('me/languages/<uuid:id>', views.LanguageDetailView.as_view(), name='language_detail'),
]

