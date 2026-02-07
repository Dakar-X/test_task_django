"""
Telegram Bot client using aiogram.

Provides both synchronous (for Django views/Celery) and async access.
"""

import logging
from functools import lru_cache

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from asgiref.sync import async_to_sync
from django.conf import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_bot() -> Bot:
    """
    Get the aiogram Bot instance (singleton).

    Uses lru_cache for singleton pattern.
    """
    return Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


class TelegramService:
    """
    Synchronous wrapper for aiogram Bot.

    Allows using Bot from synchronous Django views and Celery tasks.
    For async contexts (Channels consumers), use get_bot() directly.
    """

    def __init__(self):
        self.bot = get_bot()

    def send_message(
        self,
        business_connection_id: str,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> int:
        """
        Send a message via business connection.

        Returns message_id of sent message.
        """
        return async_to_sync(self._send_message)(
            business_connection_id,
            chat_id,
            text,
            reply_to_message_id,
        )

    async def _send_message(
        self,
        business_connection_id: str,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None,
    ) -> int:
        result = await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            business_connection_id=business_connection_id,
            reply_to_message_id=reply_to_message_id,
        )
        return result.message_id

    def get_business_connection(self, business_connection_id: str) -> dict:
        """Get business connection info."""
        return async_to_sync(self._get_business_connection)(business_connection_id)

    async def _get_business_connection(self, business_connection_id: str) -> dict:
        conn = await self.bot.get_business_connection(business_connection_id)
        return {
            'id': conn.id,
            'user_id': conn.user.id,
            'user_first_name': conn.user.first_name,
            'user_last_name': conn.user.last_name or '',
            'user_username': conn.user.username or '',
            'user_chat_id': conn.user_chat_id,
            'date': conn.date,
            'can_reply': conn.can_reply,
            'is_enabled': conn.is_enabled,
        }

    def get_user_profile_photo(self, user_id: int) -> bytes | None:
        """Download user's profile photo."""
        return async_to_sync(self._get_user_profile_photo)(user_id)

    async def _get_user_profile_photo(self, user_id: int) -> bytes | None:
        photos = await self.bot.get_user_profile_photos(user_id, limit=1)

        if not photos.photos:
            return None

        # Get largest photo from first set
        photo_sizes = photos.photos[0]
        if not photo_sizes:
            return None

        largest = max(photo_sizes, key=lambda p: p.file_size or 0)

        # Download
        from io import BytesIO
        file = await self.bot.download(largest.file_id, destination=BytesIO())
        return file.read() if file else None

    def download_file(self, file_id: str) -> bytes | None:
        """Download any file by file_id."""
        return async_to_sync(self._download_file)(file_id)

    async def _download_file(self, file_id: str) -> bytes | None:
        from io import BytesIO
        file = await self.bot.download(file_id, destination=BytesIO())
        return file.read() if file else None


# Singleton service instance
_service: TelegramService | None = None


def get_telegram_service() -> TelegramService:
    """Get the TelegramService instance (sync wrapper)."""
    global _service
    if _service is None:
        _service = TelegramService()
    return _service
