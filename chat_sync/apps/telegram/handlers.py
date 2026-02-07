"""
Async handlers for Telegram Business webhook events.

Uses unified models:
- Customer (from chats app) for contact data
- Deal (from chats app) for chat data
- TelegramAccount, BusinessConnection, TelegramChat for Telegram-specific data
"""

import logging
from datetime import datetime, timezone
from typing import Any

from django.utils import timezone as dj_timezone

from apps.chats.models import Customer, Deal
from apps.sync.services.dynamodb import get_message_store

from .models import BusinessConnection, TelegramAccount, TelegramChat

logger = logging.getLogger(__name__)


async def process_business_connection(data: dict[str, Any]) -> None:
    """
    Handle business_connection update.

    Creates/updates TelegramAccount and BusinessConnection.
    """
    connection_id = data['id']
    user_data = data['user']
    is_enabled = data.get('is_enabled', True)

    # Get or create TelegramAccount
    account, _ = await TelegramAccount.objects.aupdate_or_create(
        telegram_user_id=user_data['id'],
        defaults={
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'username': user_data.get('username', ''),
            'is_bot_connected': is_enabled,
            'connected_at': dj_timezone.now() if is_enabled else None,
        },
    )

    # Get or create BusinessConnection
    status = BusinessConnection.Status.ACTIVE if is_enabled else BusinessConnection.Status.DISABLED

    await BusinessConnection.objects.aupdate_or_create(
        connection_id=connection_id,
        defaults={
            'account': account,
            'can_reply': data.get('can_reply', True),
            'status': status,
        },
    )

    logger.info(f'Business connection {connection_id}: enabled={is_enabled}')


async def process_business_message(data: dict[str, Any]) -> None:
    """
    Handle business_message update.

    Creates Customer, Deal, TelegramChat if needed.
    Saves message to DynamoDB.
    """
    business_connection_id = data.get('business_connection_id')
    if not business_connection_id:
        logger.warning('Message has no business_connection_id')
        return

    # Get connection
    try:
        connection = await BusinessConnection.objects.select_related('account').aget(
            connection_id=business_connection_id
        )
    except BusinessConnection.DoesNotExist:
        logger.error(f'Connection not found: {business_connection_id}')
        return

    chat_data = data['chat']
    from_data = data.get('from', {})

    # Is message outgoing (from business to customer)?
    is_outgoing = from_data.get('id') == connection.account.telegram_user_id

    # Get customer info (the other party)
    if is_outgoing:
        customer_tg_id = chat_data['id']
        customer_info = chat_data
    else:
        customer_tg_id = from_data.get('id', chat_data['id'])
        customer_info = from_data if from_data else chat_data

    # Get or create Customer
    customer, _ = await Customer.objects.aupdate_or_create(
        external_id=f'tg_{customer_tg_id}',
        defaults={
            'name': f"{customer_info.get('first_name', '')} {customer_info.get('last_name', '')}".strip(),
            'avatar_url': '',  # Telegram doesn't provide URL directly
        },
    )

    # Get or create Deal
    deal_external_id = f'tg_chat_{chat_data["id"]}_{business_connection_id}'
    message_text = data.get('text', '') or data.get('caption', '')
    message_date = datetime.fromtimestamp(data['date'], tz=timezone.utc)

    deal, deal_created = await Deal.objects.aupdate_or_create(
        external_id=deal_external_id,
        defaults={
            'customer': customer,
            'last_message_id': str(data['message_id']),
            'last_message_at': message_date,
            'sync_status': Deal.SyncStatus.COMPLETE,
        },
    )

    # Get or create TelegramChat link
    await TelegramChat.objects.aget_or_create(
        deal=deal,
        defaults={
            'connection': connection,
            'telegram_chat_id': chat_data['id'],
        },
    )

    # Save message to DynamoDB
    message_store = get_message_store()
    message_store.save_message(
        chat_id=deal.external_id,
        message_id=str(data['message_id']),
        text=message_text,
        created_at=message_date,
    )

    # Increment counter
    deal.total_messages += 1
    await deal.asave(update_fields=['total_messages', 'updated_at'])

    logger.debug(f'Message {data["message_id"]} saved to deal {deal.id}')


async def process_edited_message(data: dict[str, Any]) -> None:
    """Handle edited message - update in DynamoDB."""
    business_connection_id = data.get('business_connection_id')
    if not business_connection_id:
        return

    deal_external_id = f'tg_chat_{data["chat"]["id"]}_{business_connection_id}'

    try:
        deal = await Deal.objects.aget(external_id=deal_external_id)
    except Deal.DoesNotExist:
        return

    message_text = data.get('text', '') or data.get('caption', '')
    message_date = datetime.fromtimestamp(data['date'], tz=timezone.utc)

    message_store = get_message_store()
    message_store.save_message(
        chat_id=deal.external_id,
        message_id=str(data['message_id']),
        text=message_text,
        created_at=message_date,
    )

    logger.debug(f'Edited message {data["message_id"]} updated')


async def process_deleted_messages(data: dict[str, Any]) -> None:
    """Handle deleted messages - remove from DynamoDB."""
    business_connection_id = data.get('business_connection_id')
    if not business_connection_id:
        return

    deal_external_id = f'tg_chat_{data["chat"]["id"]}_{business_connection_id}'
    message_ids = data.get('message_ids', [])

    try:
        deal = await Deal.objects.aget(external_id=deal_external_id)
    except Deal.DoesNotExist:
        return

    message_store = get_message_store()
    for msg_id in message_ids:
        message_store.delete_message(deal.external_id, str(msg_id))

    deal.total_messages = max(0, deal.total_messages - len(message_ids))
    await deal.asave(update_fields=['total_messages', 'updated_at'])

    logger.debug(f'Deleted {len(message_ids)} messages from deal {deal.id}')
