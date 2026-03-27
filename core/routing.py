# -*- coding: utf-8 -*-
"""
ForgeForth Africa - WebSocket Routing
======================================
URL routing for WebSocket connections.
All WebSocket connections use WSS (Secure WebSocket) in production.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Notifications - real-time alerts for users
    re_path(
        r'ws/notifications/$',
        consumers.NotificationConsumer.as_asgi(),
        name='ws_notifications'
    ),

    # Chat - real-time messaging
    re_path(
        r'ws/chat/(?P<conversation_id>[0-9a-f-]+)/$',
        consumers.ChatConsumer.as_asgi(),
        name='ws_chat'
    ),

    # Presence - online status tracking
    re_path(
        r'ws/presence/$',
        consumers.PresenceConsumer.as_asgi(),
        name='ws_presence'
    ),
]

