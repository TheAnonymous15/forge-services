# -*- coding: utf-8 -*-
"""
ForgeForth Africa - WebSocket Consumers
========================================
Secure WebSocket consumers for real-time communication.
All WebSocket connections use WSS (WebSocket Secure) in production.
"""
import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from asgiref.sync import sync_to_async

logger = logging.getLogger('forgeforth.websocket')


class SecureWebsocketConsumer(AsyncJsonWebsocketConsumer):
    """
    Base WebSocket consumer with security features.

    Security features:
    - Origin validation
    - JWT authentication
    - Rate limiting
    - Connection limits per user
    - Secure message handling
    """

    # Override in subclasses
    requires_authentication = True
    rate_limit = 100  # messages per minute

    async def connect(self):
        """Handle WebSocket connection with security checks."""
        # Validate origin
        if not await self.validate_origin():
            logger.warning(f"WebSocket rejected: invalid origin")
            await self.close(code=4003)
            return

        # Authenticate user if required
        if self.requires_authentication:
            if not await self.authenticate():
                logger.warning(f"WebSocket rejected: authentication failed")
                await self.close(code=4001)
                return

        # Check connection limits
        if not await self.check_connection_limit():
            logger.warning(f"WebSocket rejected: connection limit exceeded")
            await self.close(code=4029)
            return

        # Accept connection
        await self.accept()

        # Track connection
        await self.on_connect()

        logger.info(f"WebSocket connected: user={getattr(self, 'user_id', 'anonymous')}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.on_disconnect()
        logger.info(f"WebSocket disconnected: code={close_code}")

    async def receive_json(self, content, **kwargs):
        """Handle incoming JSON messages with rate limiting."""
        # Rate limit check
        if not await self.check_rate_limit():
            await self.send_json({
                'type': 'error',
                'code': 'RATE_LIMITED',
                'message': 'Too many messages. Please slow down.',
            })
            return

        # Validate message structure
        if not isinstance(content, dict):
            await self.send_json({
                'type': 'error',
                'code': 'INVALID_MESSAGE',
                'message': 'Message must be a JSON object.',
            })
            return

        # Process message
        message_type = content.get('type')
        if message_type:
            handler = getattr(self, f'handle_{message_type}', None)
            if handler:
                await handler(content)
            else:
                await self.send_json({
                    'type': 'error',
                    'code': 'UNKNOWN_TYPE',
                    'message': f'Unknown message type: {message_type}',
                })
        else:
            await self.handle_message(content)

    async def validate_origin(self) -> bool:
        """Validate the WebSocket origin header."""
        from core.security import get_allowed_websocket_origins

        headers = dict(self.scope.get('headers', []))
        origin = headers.get(b'origin', b'').decode('utf-8')

        if not origin:
            # Allow connections without origin in development
            return settings.DEBUG

        allowed = get_allowed_websocket_origins()
        return origin in allowed

    async def authenticate(self) -> bool:
        """Authenticate the WebSocket connection using JWT."""
        # Get token from query string or headers
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = dict(p.split('=') for p in query_string.split('&') if '=' in p)
        token = params.get('token')

        if not token:
            # Try headers
            headers = dict(self.scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode('utf-8')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]

        if not token:
            return False

        # Validate JWT token
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            access_token = AccessToken(token)
            self.user_id = str(access_token['user_id'])
            self.scope['user_id'] = self.user_id
            return True
        except Exception as e:
            logger.error(f"JWT validation failed: {e}")
            return False

    async def check_connection_limit(self) -> bool:
        """Check if user has exceeded connection limit."""
        from core.security import WEBSOCKET_CONFIG
        from django.core.cache import cache

        if not hasattr(self, 'user_id'):
            return True

        cache_key = f'ws_connections:{self.user_id}'
        current = cache.get(cache_key, 0)
        max_connections = WEBSOCKET_CONFIG['max_connections_per_user']

        if current >= max_connections:
            return False

        cache.set(cache_key, current + 1, timeout=3600)
        return True

    async def check_rate_limit(self) -> bool:
        """Check message rate limit."""
        from django.core.cache import cache
        import time

        if not hasattr(self, 'user_id'):
            return True

        cache_key = f'ws_rate:{self.user_id}'
        now = time.time()
        window_start = now - 60  # 1 minute window

        # Get recent message timestamps
        timestamps = cache.get(cache_key, [])
        timestamps = [ts for ts in timestamps if ts > window_start]

        if len(timestamps) >= self.rate_limit:
            return False

        timestamps.append(now)
        cache.set(cache_key, timestamps, timeout=120)
        return True

    async def on_connect(self):
        """Override in subclasses for connection setup."""
        pass

    async def on_disconnect(self):
        """Override in subclasses for disconnection cleanup."""
        # Decrement connection count
        if hasattr(self, 'user_id'):
            from django.core.cache import cache
            cache_key = f'ws_connections:{self.user_id}'
            current = cache.get(cache_key, 1)
            cache.set(cache_key, max(0, current - 1), timeout=3600)

    async def handle_message(self, content):
        """Override in subclasses to handle messages."""
        pass


class NotificationConsumer(SecureWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Users receive notifications for:
    - New messages
    - Application updates
    - Profile views
    - System alerts
    """

    async def on_connect(self):
        """Join user's notification channel."""
        if hasattr(self, 'user_id'):
            self.room_name = f'notifications_{self.user_id}'
            await self.channel_layer.group_add(
                self.room_name,
                self.channel_name
            )

    async def on_disconnect(self):
        """Leave notification channel."""
        await super().on_disconnect()
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(
                self.room_name,
                self.channel_name
            )

    async def notification(self, event):
        """Send notification to client."""
        await self.send_json({
            'type': 'notification',
            'data': event['data'],
        })

    async def handle_mark_read(self, content):
        """Mark notification as read."""
        notification_id = content.get('notification_id')
        if notification_id:
            # TODO: Implement mark as read
            await self.send_json({
                'type': 'ack',
                'notification_id': notification_id,
            })


class ChatConsumer(SecureWebsocketConsumer):
    """
    WebSocket consumer for real-time chat.
    Secure messaging between talents and employers.
    """

    async def on_connect(self):
        """Join chat room."""
        # Get conversation ID from URL
        self.conversation_id = self.scope['url_route']['kwargs'].get('conversation_id')

        if self.conversation_id:
            # Verify user has access to this conversation
            if await self.verify_conversation_access():
                self.room_name = f'chat_{self.conversation_id}'
                await self.channel_layer.group_add(
                    self.room_name,
                    self.channel_name
                )
            else:
                await self.close(code=4003)

    async def on_disconnect(self):
        """Leave chat room."""
        await super().on_disconnect()
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(
                self.room_name,
                self.channel_name
            )

    @database_sync_to_async
    def verify_conversation_access(self) -> bool:
        """Verify user has access to the conversation."""
        # TODO: Implement conversation access check
        return True

    async def handle_message(self, content):
        """Handle incoming chat message."""
        message_text = content.get('message', '').strip()

        if not message_text:
            return

        # Sanitize message
        message_text = self.sanitize_message(message_text)

        # Save message to database
        message_data = await self.save_message(message_text)

        # Broadcast to room
        await self.channel_layer.group_send(
            self.room_name,
            {
                'type': 'chat_message',
                'data': message_data,
            }
        )

    def sanitize_message(self, text: str) -> str:
        """Sanitize message content."""
        import html
        # Escape HTML
        text = html.escape(text)
        # Limit length
        return text[:2000]

    @database_sync_to_async
    def save_message(self, text: str) -> dict:
        """Save message to database."""
        # TODO: Implement message saving
        import uuid
        from datetime import datetime
        return {
            'id': str(uuid.uuid4()),
            'sender_id': self.user_id,
            'text': text,
            'timestamp': datetime.now().isoformat(),
        }

    async def chat_message(self, event):
        """Send chat message to client."""
        await self.send_json({
            'type': 'message',
            'data': event['data'],
        })


class PresenceConsumer(SecureWebsocketConsumer):
    """
    WebSocket consumer for user presence/online status.
    """

    async def on_connect(self):
        """Mark user as online."""
        if hasattr(self, 'user_id'):
            await self.set_user_online(True)

    async def on_disconnect(self):
        """Mark user as offline."""
        await super().on_disconnect()
        if hasattr(self, 'user_id'):
            await self.set_user_online(False)

    @database_sync_to_async
    def set_user_online(self, is_online: bool):
        """Update user online status in cache."""
        from django.core.cache import cache
        from datetime import datetime

        if is_online:
            cache.set(
                f'presence:{self.user_id}',
                datetime.now().isoformat(),
                timeout=300  # 5 minutes
            )
        else:
            cache.delete(f'presence:{self.user_id}')

    async def handle_heartbeat(self, content):
        """Handle heartbeat to maintain presence."""
        await self.set_user_online(True)
        await self.send_json({'type': 'heartbeat_ack'})

