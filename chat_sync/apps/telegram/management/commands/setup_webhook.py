"""
Management command to set up Telegram webhook.

Usage:
    python manage.py setup_webhook
    python manage.py setup_webhook --delete
    python manage.py setup_webhook --url https://yourdomain.com/telegram/webhook/
"""

import asyncio

from aiogram import Bot
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Set up or delete Telegram webhook'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='Webhook URL (overrides TELEGRAM_WEBHOOK_URL setting)',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete existing webhook',
        )
        parser.add_argument(
            '--info',
            action='store_true',
            help='Show current webhook info',
        )

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set')

        asyncio.run(self._handle_async(options))

    async def _handle_async(self, options):
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

        try:
            if options['info']:
                await self._show_info(bot)
            elif options['delete']:
                await self._delete_webhook(bot)
            else:
                url = options['url'] or settings.TELEGRAM_WEBHOOK_URL
                if not url:
                    raise CommandError(
                        'Webhook URL not specified. '
                        'Use --url or set TELEGRAM_WEBHOOK_URL'
                    )
                await self._set_webhook(bot, url)
        finally:
            await bot.session.close()

    async def _show_info(self, bot: Bot):
        """Show current webhook info."""
        info = await bot.get_webhook_info()

        self.stdout.write(self.style.SUCCESS('Current webhook info:'))
        self.stdout.write(f'  URL: {info.url or "(not set)"}')
        self.stdout.write(f'  Has custom certificate: {info.has_custom_certificate}')
        self.stdout.write(f'  Pending update count: {info.pending_update_count}')

        if info.last_error_date:
            self.stdout.write(
                self.style.WARNING(f'  Last error: {info.last_error_message}')
            )
            self.stdout.write(f'  Last error date: {info.last_error_date}')

        if info.allowed_updates:
            self.stdout.write(f'  Allowed updates: {", ".join(info.allowed_updates)}')

    async def _set_webhook(self, bot: Bot, url: str):
        """Set webhook URL."""
        secret_token = settings.TELEGRAM_WEBHOOK_SECRET or None

        # Business-related updates
        allowed_updates = [
            'business_connection',
            'business_message',
            'edited_business_message',
            'deleted_business_messages',
        ]

        self.stdout.write(f'Setting webhook to: {url}')

        result = await bot.set_webhook(
            url=url,
            secret_token=secret_token,
            allowed_updates=allowed_updates,
            drop_pending_updates=False,
        )

        if result:
            self.stdout.write(self.style.SUCCESS('Webhook set successfully!'))
            self.stdout.write(f'  Allowed updates: {", ".join(allowed_updates)}')
            if secret_token:
                self.stdout.write('  Secret token: (configured)')
        else:
            self.stdout.write(self.style.ERROR('Failed to set webhook'))

    async def _delete_webhook(self, bot: Bot):
        """Delete webhook."""
        result = await bot.delete_webhook(drop_pending_updates=False)

        if result:
            self.stdout.write(self.style.SUCCESS('Webhook deleted successfully!'))
        else:
            self.stdout.write(self.style.ERROR('Failed to delete webhook'))
