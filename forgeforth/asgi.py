# -*- coding: utf-8 -*-
"""
ASGI config for ForgeForth Africa.

Supports both HTTP and WebSocket protocols.
All WebSocket connections use WSS (Secure WebSocket) in production.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "forgeforth.settings")

# Initialize Django ASGI application early to ensure settings are loaded
django_asgi_app = get_asgi_application()

# Import channels components after Django setup
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack

from core.routing import websocket_urlpatterns


class SecureWebSocketMiddleware:
    """
    Middleware to enforce secure WebSocket connections in production.
    Rejects non-SSL WebSocket connections when not in DEBUG mode.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from django.conf import settings

        if scope['type'] == 'websocket':
            # In production, require secure connection
            if not settings.DEBUG:
                # Check if connection is secure (via proxy or direct SSL)
                headers = dict(scope.get('headers', []))

                # Check X-Forwarded-Proto header (common for reverse proxies)
                forwarded_proto = headers.get(b'x-forwarded-proto', b'').decode()

                # Check if connection is secure
                is_secure = (
                    scope.get('scheme') == 'wss' or
                    forwarded_proto == 'https' or
                    scope.get('server', ('', 443))[1] == 443
                )

                if not is_secure:
                    # Reject insecure WebSocket connection
                    await send({
                        'type': 'websocket.close',
                        'code': 4000,
                    })
                    return

        return await self.app(scope, receive, send)


application = ProtocolTypeRouter({
    # HTTP requests handled by Django
    'http': django_asgi_app,

    # WebSocket requests with security middleware stack
    'websocket': SecureWebSocketMiddleware(
        AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        )
    ),
})
