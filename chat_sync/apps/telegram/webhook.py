"""
Async Telegram webhook endpoint.

Processes updates inline (no Celery) since all operations are async and fast.
"""

import json
import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views import View

from apps.chats.models import MessageEvent

from . import handlers

logger = logging.getLogger(__name__)


class TelegramWebhookView(View):
    """
    Async webhook endpoint for Telegram Bot API updates.

    Processes updates inline using async handlers.
    """

    async def post(self, request: HttpRequest) -> HttpResponse:
        # 1. Validate secret token
        if not self._validate_secret(request):
            logger.warning('Invalid webhook secret token')
            return HttpResponse(status=401)

        # 2. Parse JSON
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f'Invalid JSON in webhook: {e}')
            return HttpResponse(status=400)

        # 3. Log event
        update_id = data.get('update_id')
        if update_id:
            await self._log_event(update_id, data)

        # 4. Process inline (async, fast)
        await self._process(data)

        # 5. Return 200
        return HttpResponse('ok', content_type='text/plain')

    def _validate_secret(self, request: HttpRequest) -> bool:
        expected = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
        if not expected:
            return True
        actual = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        return actual == expected

    async def _log_event(self, update_id: int, data: dict) -> None:
        event_type = self._detect_event_type(data)
        try:
            await MessageEvent.objects.aget_or_create(
                telegram_update_id=update_id,
                defaults={'event_type': event_type, 'raw_data': data},
            )
        except Exception as e:
            logger.exception(f'Failed to log event {update_id}: {e}')

    def _detect_event_type(self, data: dict) -> str:
        if 'business_connection' in data:
            return MessageEvent.EventType.CONNECTION
        elif 'business_message' in data:
            return MessageEvent.EventType.MESSAGE
        elif 'edited_business_message' in data:
            return MessageEvent.EventType.EDITED
        elif 'deleted_business_messages' in data:
            return MessageEvent.EventType.DELETED
        return MessageEvent.EventType.MESSAGE

    async def _process(self, data: dict) -> None:
        """Process update inline using async handlers."""
        try:
            if 'business_connection' in data:
                await handlers.process_business_connection(data['business_connection'])

            elif 'business_message' in data:
                await handlers.process_business_message(data['business_message'])

            elif 'edited_business_message' in data:
                await handlers.process_edited_message(data['edited_business_message'])

            elif 'deleted_business_messages' in data:
                await handlers.process_deleted_messages(data['deleted_business_messages'])

        except Exception as e:
            # Log but don't fail the webhook
            logger.exception(f'Failed to process update: {e}')
