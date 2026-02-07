"""
Telegram-specific models.

Extends base chats models for Telegram Business integration.
"""

from django.db import models

from apps.chats.models import Customer, Deal


class TelegramAccount(models.Model):
    """
    Telegram Business account owner.

    Links to Customer for unified customer management.
    """

    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='telegram_account',
        null=True,
        blank=True,
    )

    telegram_user_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True)

    is_bot_connected = models.BooleanField(default=False)
    connected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'telegram_accounts'

    def __str__(self) -> str:
        return f'{self.first_name} (@{self.username})' if self.username else self.first_name


class BusinessConnection(models.Model):
    """
    Telegram Business connection (bot linked to business account).
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        DISABLED = 'disabled', 'Disabled'
        REVOKED = 'revoked', 'Revoked'

    connection_id = models.CharField(max_length=255, unique=True, db_index=True)
    account = models.ForeignKey(
        TelegramAccount,
        on_delete=models.CASCADE,
        related_name='connections',
    )

    can_reply = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_connections'

    def __str__(self) -> str:
        return f'Connection {self.connection_id}'


class TelegramChat(models.Model):
    """
    Links Telegram chat to Deal.

    Allows Deal to be used both for mock API sync and Telegram.
    """

    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name='telegram_chat',
    )

    connection = models.ForeignKey(
        BusinessConnection,
        on_delete=models.CASCADE,
        related_name='chats',
    )

    telegram_chat_id = models.BigIntegerField(db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'telegram_chats'
        unique_together = ('connection', 'telegram_chat_id')

    def __str__(self) -> str:
        return f'TG Chat {self.telegram_chat_id} -> Deal {self.deal_id}'
