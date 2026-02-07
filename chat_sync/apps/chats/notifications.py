"""
WebSocket notification utilities for chat events.
"""

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def _get_group_name(user_id: str) -> str:
    """Get the channel group name for a user."""
    return f'user_{user_id}'


def _send_to_group(group_name: str, message: dict[str, Any]) -> None:
    """Send message to a channel group."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning('Channel layer not configured, skipping notification')
        return

    try:
        async_to_sync(channel_layer.group_send)(group_name, message)
    except Exception as e:
        logger.exception(f'Failed to send to group {group_name}: {e}')


def notify_new_message(user_id: str, deal_id: str, message: dict[str, Any]) -> None:
    """
    Notify user about a new message in their chat.

    Args:
        user_id: Telegram user ID of the business account owner.
        deal_id: Chat ID.
        message: Message data.
    """
    _send_to_group(
        _get_group_name(user_id),
        {
            'type': 'new_message',
            'deal_id': deal_id,
            'message': message,
        }
    )


def notify_message_read(
    user_id: str,
    deal_id: str,
    last_read_message_id: str,
) -> None:
    """
    Notify user that a message was read.

    Args:
        user_id: Telegram user ID of the business account owner.
        deal_id: Chat ID.
        last_read_message_id: ID of the last read message.
    """
    _send_to_group(
        _get_group_name(user_id),
        {
            'type': 'message_read',
            'deal_id': deal_id,
            'last_read_message_id': last_read_message_id,
        }
    )


def notify_chat_updated(user_id: str, deal_id: str, data: dict[str, Any]) -> None:
    """
    Notify user that chat was updated (archived, unread count changed, etc).

    Args:
        user_id: Telegram user ID of the business account owner.
        deal_id: Chat ID.
        data: Update data.
    """
    _send_to_group(
        _get_group_name(user_id),
        {
            'type': 'chat_updated',
            'deal_id': deal_id,
            'data': data,
        }
    )


def notify_connection_status(user_id: str, connection_id: str, is_active: bool) -> None:
    """
    Notify user about business connection status change.

    Args:
        user_id: Telegram user ID of the business account owner.
        connection_id: Business connection ID.
        is_active: Whether the connection is now active.
    """
    _send_to_group(
        _get_group_name(user_id),
        {
            'type': 'connection_status',
            'connection_id': connection_id,
            'is_active': is_active,
        }
    )
