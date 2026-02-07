"""
Celery tasks for background/deferred operations.

Webhook processing is done inline (async handlers).
Celery is only used for:
- Deferred sync to Telegram (read status)
- Heavy operations (avatar download)
- Periodic tasks
"""

import asyncio
import logging

from celery import shared_task
from django.utils import timezone

from apps.chats.models import Contact, ReadStatus
from apps.sync.services.s3_service import get_s3_service

from .client import get_telegram_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def sync_read_status_to_telegram(self, read_status_id: int) -> dict:
    """
    Sync read status from our app to Telegram.

    Called when operator marks chat as read.
    Deferred because Telegram API call may be slow/fail.
    """
    try:
        return asyncio.run(_sync_read_status(read_status_id))
    except Exception as e:
        logger.exception(f'Failed to sync read status: {e}')
        raise self.retry(exc=e)


async def _sync_read_status(read_status_id: int) -> dict:
    try:
        read_status = await ReadStatus.objects.select_related(
            'chat__business_connection'
        ).aget(id=read_status_id)
    except ReadStatus.DoesNotExist:
        return {'status': 'not_found'}

    if read_status.synced_to_telegram:
        return {'status': 'already_synced'}

    # TODO: Implement actual Telegram sync when API supports it
    # For now, just mark as synced

    read_status.synced_to_telegram = True
    read_status.synced_at = timezone.now()
    await read_status.asave(update_fields=['synced_to_telegram', 'synced_at'])

    return {'status': 'success'}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def download_contact_avatar(self, contact_id: int) -> dict:
    """
    Download contact's avatar from Telegram and upload to S3.

    Deferred because:
    - Telegram API call
    - S3 upload
    - Not critical for UX
    """
    try:
        return asyncio.run(_download_avatar(contact_id))
    except Exception as e:
        logger.exception(f'Failed to download avatar: {e}')
        raise self.retry(exc=e)


async def _download_avatar(contact_id: int) -> dict:
    try:
        contact = await Contact.objects.aget(id=contact_id)
    except Contact.DoesNotExist:
        return {'status': 'not_found'}

    if contact.avatar_s3_key:
        return {'status': 'already_exists'}

    # Download from Telegram
    telegram_service = get_telegram_service()
    photo_bytes = telegram_service.get_user_profile_photo(contact.telegram_user_id)

    if not photo_bytes:
        return {'status': 'no_photo'}

    # Upload to S3
    s3_service = get_s3_service()
    key = f'avatars/contacts/{contact.telegram_user_id}.jpg'
    s3_service.upload_file(key, photo_bytes, 'image/jpeg')

    contact.avatar_s3_key = key
    await contact.asave(update_fields=['avatar_s3_key', 'updated_at'])

    logger.info(f'Downloaded avatar for contact {contact_id}')
    return {'status': 'success', 'key': key}
