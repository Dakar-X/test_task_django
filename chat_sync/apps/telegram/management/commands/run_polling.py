"""
Management command to run Telegram bot in polling mode.

Useful for local development when webhook is not available.

Usage:
    python manage.py run_polling
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.telegram.router import business_router

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run Telegram bot in polling mode (for development)'

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set')

        self.stdout.write(self.style.WARNING(
            'Running in polling mode. For production, use webhook instead.'
        ))

        asyncio.run(self._run_polling())

    async def _run_polling(self):
        """Run the bot in polling mode."""
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()

        # Include business router
        dp.include_router(business_router)

        self.stdout.write(self.style.SUCCESS('Starting polling...'))

        try:
            # Delete webhook first (required for polling)
            await bot.delete_webhook(drop_pending_updates=False)

            # Start polling
            await dp.start_polling(
                bot,
                allowed_updates=[
                    'business_connection',
                    'business_message',
                    'edited_business_message',
                    'deleted_business_messages',
                ],
            )
        finally:
            await bot.session.close()
