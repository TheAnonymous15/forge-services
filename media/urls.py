# -*- coding: utf-8 -*-
"""
Media API URLs
==============
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MediaUploadView,
    MediaFileViewSet,
    DocumentViewSet,
    ProcessingJobViewSet,
)

app_name = "media"

router = DefaultRouter()
router.register(r'files', MediaFileViewSet, basename='mediafile')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'jobs', ProcessingJobViewSet, basename='processingjob')

urlpatterns = [
    path('upload/', MediaUploadView.as_view(), name='upload'),
    path('', include(router.urls)),
]
