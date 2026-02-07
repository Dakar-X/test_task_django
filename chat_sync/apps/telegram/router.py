"""
aiogram router for polling mode (development).

In production, use webhook which processes updates directly via handlers.
"""

import logging

from aiogram import Router
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message

from . import handlers

logger = logging.getLogger(__name__)

business_router = Router(name='business')


@business_router.business_connection()
async def on_business_connection(event: BusinessConnection) -> None:
    """Handle business connection update (polling mode)."""
    # Convert aiogram type to dict for unified handler
    data = {
        'id': event.id,
        'user': {
            'id': event.user.id,
            'first_name': event.user.first_name,
            'last_name': event.user.last_name or '',
            'username': event.user.username or '',
        },
        'user_chat_id': event.user_chat_id,
        'date': int(event.date.timestamp()),
        'can_reply': event.can_reply,
        'is_enabled': event.is_enabled,
    }
    await handlers.process_business_connection(data)


@business_router.business_message()
async def on_business_message(message: Message) -> None:
    """Handle business message (polling mode)."""
    data = _message_to_dict(message)
    await handlers.process_business_message(data)


@business_router.edited_business_message()
async def on_edited_business_message(message: Message) -> None:
    """Handle edited business message (polling mode)."""
    data = _message_to_dict(message)
    await handlers.process_edited_message(data)


@business_router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted) -> None:
    """Handle deleted messages (polling mode)."""
    data = {
        'business_connection_id': event.business_connection_id,
        'chat': {
            'id': event.chat.id,
            'type': event.chat.type,
        },
        'message_ids': event.message_ids,
    }
    await handlers.process_deleted_messages(data)


def _message_to_dict(message: Message) -> dict:
    """Convert aiogram Message to dict for unified handler."""
    data = {
        'message_id': message.message_id,
        'date': int(message.date.timestamp()),
        'chat': {
            'id': message.chat.id,
            'type': message.chat.type,
            'first_name': message.chat.first_name or '',
            'last_name': message.chat.last_name or '',
            'username': message.chat.username or '',
        },
        'text': message.text or '',
        'caption': message.caption or '',
        'business_connection_id': message.business_connection_id,
    }

    if message.from_user:
        data['from'] = {
            'id': message.from_user.id,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name or '',
            'username': message.from_user.username or '',
            'is_bot': message.from_user.is_bot,
        }

    return data
