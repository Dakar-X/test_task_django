"""
WebSocket consumers for real-time chat notifications.
"""

import logging
from typing import Any

from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time chat notifications.

    Handles connections for business account owners to receive:
    - New messages in their chats
    - Message read status updates
    - Chat updates (archive, unread count)
    - Connection status changes

    URL: ws://host/ws/chats/{user_id}/
    where user_id is the Telegram user ID of the business account.
    """

    def __init__(self):
        self.group_name = None
        self.user_id = None

    async def connect(self) -> None:
        """Handle WebSocket connection."""
        self.user_id: str = self.scope['url_route']['kwargs']['user_id']
        self.group_name: str = f'user_{self.user_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        logger.info(f'WebSocket connected for user {self.user_id}')

    async def disconnect(self, code: int) -> None:
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f'WebSocket disconnected for user {self.user_id}, code: {code}')

    async def receive_json(self, content: dict[str, Any], **kwargs) -> None:
        """
        Handle incoming WebSocket messages from client.

        Supported message types:
        - ping: Health check, responds with pong
        - subscribe: Subscribe to specific chat updates
        """
        message_type = content.get('type')
        logger.debug(f'Received message from user {self.user_id}: {message_type}')

        if message_type == 'ping':
            await self.send_json({'type': 'pong'})

        elif message_type == 'subscribe':
            # Could be used to subscribe to specific chats
            chat_ids = content.get('chat_ids', [])
            await self.send_json({
                'type': 'subscribed',
                'chat_ids': chat_ids,
            })

    # Event handlers - called when messages are sent to the group

    async def new_message(self, event: dict[str, Any]) -> None:
        """
        Handle new message event.

        Sent when a new message arrives in one of user's chats.
        """
        await self.send_json({
            'type': 'new_message',
            'chat_id': event['deal_id'],
            'message': event['message'],
        })

    async def message_read(self, event: dict[str, Any]) -> None:
        """
        Handle message read event.

        Sent when a message is marked as read.
        """
        await self.send_json({
            'type': 'message_read',
            'chat_id': event['deal_id'],
            'last_read_message_id': event['last_read_message_id'],
        })

    async def chat_updated(self, event: dict[str, Any]) -> None:
        """
        Handle chat updated event.

        Sent when chat properties change (archived, unread count, etc).
        """
        await self.send_json({
            'type': 'chat_updated',
            'chat_id': event['deal_id'],
            'data': event['data'],
        })

    async def connection_status(self, event: dict[str, Any]) -> None:
        """
        Handle connection status event.

        Sent when business connection is enabled/disabled.
        """
        await self.send_json({
            'type': 'connection_status',
            'connection_id': event['connection_id'],
            'is_active': event['is_active'],
        })
