# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organizations URLs (MVP1)
==============================================
URL patterns for organizations API.
"""
from django.urls import path
from . import views

app_name = "organizations"

urlpatterns = [
    # Health check
    path('health', views.organizations_health, name='health'),

    # Industries
    path('industries', views.IndustryListView.as_view(), name='industry_list'),

    # Public organization listings
    path('', views.OrganizationListView.as_view(), name='organization_list'),
    path('public/<slug:slug>', views.OrganizationDetailView.as_view(), name='organization_detail'),

    # My organizations
    path('my', views.MyOrganizationsView.as_view(), name='my_organizations'),
    path('create', views.OrganizationCreateView.as_view(), name='organization_create'),
    path('manage/<slug:slug>', views.OrganizationManageView.as_view(), name='organization_manage'),

    # Organization members
    path('<slug:slug>/members', views.OrganizationMembersView.as_view(), name='organization_members'),
    path('<slug:slug>/members/invite', views.InviteMemberView.as_view(), name='invite_member'),
    path('<slug:slug>/members/<uuid:member_id>', views.RemoveMemberView.as_view(), name='remove_member'),

    # Organization opportunities
    path('<slug:slug>/opportunities', views.OrganizationOpportunitiesView.as_view(), name='org_opportunities'),

    # Public opportunity search
    path('opportunities', views.OpportunitySearchView.as_view(), name='opportunity_search'),
    path('opportunities/stats', views.opportunity_stats, name='opportunity_stats'),
    path('opportunities/<slug:slug>', views.OpportunityDetailView.as_view(), name='opportunity_detail'),

    # Manage opportunities
    path('opportunities/<uuid:id>/manage', views.OpportunityManageView.as_view(), name='opportunity_manage'),
    path('opportunities/<uuid:id>/publish', views.OpportunityPublishView.as_view(), name='opportunity_publish'),
]

