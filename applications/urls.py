# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Applications URLs (MVP1)
=============================================
URL patterns for applications API.
"""
from django.urls import path
from . import views

app_name = "applications"

urlpatterns = [
    # Health check
    path('health', views.applications_health, name='health'),

    # My applications (for talents)
    path('my', views.MyApplicationsView.as_view(), name='my_applications'),
    path('my/stats', views.my_application_stats, name='my_stats'),
    path('create', views.ApplicationCreateView.as_view(), name='create'),
    path('<uuid:id>', views.ApplicationDetailView.as_view(), name='detail'),
    path('<uuid:id>/submit', views.SubmitApplicationView.as_view(), name='submit'),
    path('<uuid:id>/withdraw', views.WithdrawApplicationView.as_view(), name='withdraw'),
    path('<uuid:application_id>/history', views.ApplicationHistoryView.as_view(), name='history'),

    # Opportunity applications (for employers)
    path('opportunity/<uuid:opportunity_id>', views.OpportunityApplicationsView.as_view(), name='opportunity_applications'),
    path('review/<uuid:id>', views.ReviewApplicationView.as_view(), name='review'),
    path('bulk-review', views.BulkReviewView.as_view(), name='bulk_review'),

    # Interviews
    path('<uuid:application_id>/interviews', views.InterviewListCreateView.as_view(), name='interviews'),
    path('interviews/<uuid:id>', views.InterviewDetailView.as_view(), name='interview_detail'),
    path('interviews/<uuid:id>/feedback', views.InterviewFeedbackView.as_view(), name='interview_feedback'),

    # Notes
    path('<uuid:application_id>/notes', views.ApplicationNotesView.as_view(), name='notes'),

    # Saved opportunities
    path('saved', views.SavedOpportunitiesView.as_view(), name='saved'),
    path('saved/<uuid:opportunity_id>', views.UnsaveOpportunityView.as_view(), name='unsave'),
]

