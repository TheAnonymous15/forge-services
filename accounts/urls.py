# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Accounts URLs (MVP1)
=========================================
URL patterns for authentication API.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "accounts"

urlpatterns = [
    # Health check
    path('health', views.auth_health, name='health'),

    # Registration
    path('register', views.RegisterView.as_view(), name='register'),

    # Login / Logout
    path('login', views.LoginView.as_view(), name='login'),
    path('logout', views.LogoutView.as_view(), name='logout'),
    path('token/refresh', TokenRefreshView.as_view(), name='token_refresh'),

    # Email verification
    path('verify-email', views.VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification', views.ResendVerificationView.as_view(), name='resend_verification'),

    # Password management
    path('password/forgot', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('password/reset', views.ResetPasswordView.as_view(), name='reset_password'),
    path('password/change', views.ChangePasswordView.as_view(), name='change_password'),

    # Current user
    path('me', views.CurrentUserView.as_view(), name='current_user'),
]
