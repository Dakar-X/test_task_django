"""
Models for chat synchronization.

Based on test task requirements:
- deals table: external_id, last_message_id, last_message_at, total_messages
- customers table: id, name, avatar
"""

from django.db import models


class Customer(models.Model):
    """
    Customer from external API.

    Requirements:
    - If customer doesn't exist, create them
    - If customer is new, save avatar to S3
    - If customer exists, skip update
    """

    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    # Avatar: original URL from API, S3 key after upload
    avatar_url = models.URLField(blank=True)
    avatar_s3_key = models.CharField(max_length=512, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customers'

    def __str__(self) -> str:
        return f'{self.name} ({self.external_id})'

    @property
    def avatar(self) -> str:
        """
        Return S3 URL if available, otherwise original URL.

        Per requirements: "You may return the original avatar URL provided
        by the API if the avatar has not yet been saved to S3 storage."
        """
        if self.avatar_s3_key:
            # TODO: Generate presigned S3 URL or public URL
            return f'https://s3.amazonaws.com/bucket/{self.avatar_s3_key}'
        return self.avatar_url


class Deal(models.Model):
    """
    Chat/Deal from external API.

    Requirements:
    - Store: external_id, last_message_id, last_message_at, total_messages
    - Only return deals that have both customer and message saved (is_complete)
    """

    class SyncStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'      # Created, but not fully synced
        COMPLETE = 'complete', 'Complete'   # Customer + message saved
        FAILED = 'failed', 'Failed'         # Sync failed

    external_id = models.CharField(max_length=255, unique=True, db_index=True)

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='deals',
        null=True,  # Can be null during sync
        blank=True,
    )

    # Last message info (from API)
    last_message_id = models.CharField(max_length=255, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Counter - incremented when message saved to DynamoDB
    total_messages = models.PositiveIntegerField(default=0)

    # Sync status for persistence requirement
    # "We must only return chats that have both the customer
    # and the message successfully saved"
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'deals'
        ordering = ['-last_message_at']

    def __str__(self) -> str:
        return f'Deal {self.external_id}'

    @property
    def is_complete(self) -> bool:
        """Check if deal has complete data (customer + message)."""
        return self.sync_status == self.SyncStatus.COMPLETE


class DealManager(models.Manager):
    """Custom manager for Deal with common queries."""

    def complete(self):
        """Return only complete deals (customer + message saved)."""
        return self.filter(sync_status=Deal.SyncStatus.COMPLETE)


# Add manager to Deal
Deal.objects = DealManager()
Deal.objects.model = Deal
