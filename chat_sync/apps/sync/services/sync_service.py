"""
Main synchronization service for importing chats from external API.

Critical Requirements:
1. PERSISTENCE: Only return deals with customer + message saved (sync_status=COMPLETE)
2. RESILIENCE: Resume from exact point on failure (cursor in SyncState)
3. CONSISTENCY: DynamoDB message + SQL counter must be synchronized
4. CONCURRENCY: Distributed lock prevents parallel execution (handled in task)

Architecture notes for future developer:
- Each chat is processed atomically
- Cursor is saved AFTER successful page processing
- Deal.sync_status transitions: PENDING -> COMPLETE (or FAILED)
- Customer avatar upload is async (Celery task), doesn't block sync
"""

import logging
from datetime import datetime
from typing import Any

from django.db import transaction

from apps.chats.models import Customer, Deal
from apps.sync.models import SyncState

from .dynamodb import get_message_store
from .external_api import Chat, ChatPage, get_external_api_client
from .s3_service import get_s3_service

logger = logging.getLogger(__name__)


class SyncService:
    """
    Service for synchronizing chats from external API.

    Two scenarios:
    1. Initial Run: Sync all chats up to max_date
    2. Incremental Run: Sync until no changes detected (same last_message_id)
    """

    def __init__(self, state: SyncState):
        self.state = state
        self.api_client = get_external_api_client()
        self.message_store = get_message_store()
        self.s3_service = get_s3_service()

    def run(self) -> None:
        """
        Run synchronization process.

        Fetches pages of chats, processes each, saves cursor after each page.
        """
        logger.info(f'Starting sync task {self.state.task_id}, cursor={self.state.cursor}')
        cursor = self.state.cursor or None

        try:
            while True:
                # Fetch page from API
                # NOTE: API may fail or have high latency - retries handled by Celery
                page = self.api_client.get_chats(cursor=cursor)

                # Process all chats in page
                should_stop = self._process_page(page)

                # Save cursor AFTER successful processing (resilience)
                if page.next_cursor:
                    self._save_cursor(page.next_cursor)

                if should_stop or not page.has_more:
                    logger.info(f'Sync stopping: should_stop={should_stop}, has_more={page.has_more}')
                    break

                cursor = page.next_cursor

            logger.info(f'Sync completed. Processed {self.state.processed_chats} chats.')

        except Exception as e:
            logger.exception(f'Sync failed at cursor={cursor}: {e}')
            raise

    def _process_page(self, page: ChatPage) -> bool:
        """
        Process a page of chats.

        Returns True if sync should stop (reached max_date or no changes).
        """
        for chat in page.chats:
            should_stop = self._process_chat(chat)
            if should_stop:
                return True
        return False

    def _process_chat(self, chat: Chat) -> bool:
        """
        Process a single chat atomically.

        Order of operations (for consistency):
        1. Check if should skip (max_date or no changes)
        2. Get/create Customer
        3. Create/update Deal (sync_status=PENDING)
        4. Save message to DynamoDB
        5. Update Deal (sync_status=COMPLETE, increment counter)

        Returns True if sync should stop.
        """
        # Check max_date (Initial Run scenario)
        if self.state.max_date and chat.last_message.created_at < self.state.max_date:
            logger.debug(f'Chat {chat.external_id}: reached max_date, stopping')
            return True

        # Check if chat unchanged (Incremental Run scenario)
        existing_deal = Deal.objects.filter(external_id=chat.external_id).first()
        if existing_deal and existing_deal.last_message_id == chat.last_message.message_id:
            logger.debug(f'Chat {chat.external_id}: unchanged, stopping')
            return True

        # Process chat atomically
        try:
            self._sync_chat_atomic(chat, existing_deal)
            self._increment_processed()
        except Exception as e:
            logger.exception(f'Failed to sync chat {chat.external_id}: {e}')
            # Mark deal as failed if it exists
            if existing_deal:
                existing_deal.sync_status = Deal.SyncStatus.FAILED
                existing_deal.save(update_fields=['sync_status', 'updated_at'])
            # Don't stop sync, continue with next chat
            # TODO: Consider adding to retry queue

        return False

    def _sync_chat_atomic(self, chat: Chat, existing_deal: Deal | None) -> None:
        """
        Sync a single chat with consistency guarantees.

        IMPORTANT: DynamoDB write + SQL update must both succeed
        for deal to be marked COMPLETE.
        """
        with transaction.atomic():
            # 1. Get or create customer
            customer = self._get_or_create_customer(chat)

            # 2. Create or update deal (initially PENDING)
            deal = self._create_or_update_deal(chat, customer, existing_deal)

            # 3. Save message to DynamoDB
            # NOTE: DynamoDB is eventually consistent, but for our use case
            # we need strong consistency. Consider using DynamoDB transactions
            # or a two-phase commit pattern for production.
            self._save_message_to_dynamodb(chat, deal)

            # 4. Mark deal as COMPLETE and increment counter
            # This happens in same SQL transaction as step 2
            deal.sync_status = Deal.SyncStatus.COMPLETE
            deal.total_messages += 1
            deal.save(update_fields=['sync_status', 'total_messages', 'updated_at'])

            logger.debug(f'Chat {chat.external_id} synced successfully')

    def _get_or_create_customer(self, chat: Chat) -> Customer:
        """
        Get or create customer.

        Requirements:
        - If customer doesn't exist, create them
        - If customer is new, save avatar to S3 (async)
        - If customer exists, skip update
        """
        customer, created = Customer.objects.get_or_create(
            external_id=chat.customer.external_id,
            defaults={
                'name': chat.customer.name,
                'avatar_url': chat.customer.avatar_url,
            },
        )

        if created and chat.customer.avatar_url:
            # Queue avatar upload (don't block sync)
            # TODO: Replace with actual Celery task
            self._queue_avatar_upload(customer, chat.customer.avatar_url)

        return customer

    def _queue_avatar_upload(self, customer: Customer, avatar_url: str) -> None:
        """
        Queue avatar upload to S3.

        NOTE: This is async - deal can be returned with original URL
        until S3 upload completes.

        TODO: Implement as Celery task:
        - Download avatar from avatar_url
        - Upload to S3
        - Update customer.avatar_s3_key
        - Handle failures (retry, dead letter queue)
        """
        # For now, upload synchronously (pseudocode for test task)
        try:
            import httpx
            response = httpx.get(avatar_url, timeout=10.0)
            if response.status_code == 200:
                key = f'avatars/{customer.external_id}.jpg'
                self.s3_service.upload_file(key, response.content, 'image/jpeg')
                customer.avatar_s3_key = key
                customer.save(update_fields=['avatar_s3_key', 'updated_at'])
        except Exception as e:
            logger.warning(f'Failed to upload avatar for {customer.external_id}: {e}')
            # Don't fail the sync - avatar can be uploaded later

    def _create_or_update_deal(
        self,
        chat: Chat,
        customer: Customer,
        existing_deal: Deal | None,
    ) -> Deal:
        """Create or update deal with PENDING status."""
        if existing_deal:
            existing_deal.customer = customer
            existing_deal.last_message_id = chat.last_message.message_id
            existing_deal.last_message_at = chat.last_message.created_at
            existing_deal.sync_status = Deal.SyncStatus.PENDING
            existing_deal.save(update_fields=[
                'customer',
                'last_message_id',
                'last_message_at',
                'sync_status',
                'updated_at',
            ])
            return existing_deal

        return Deal.objects.create(
            external_id=chat.external_id,
            customer=customer,
            last_message_id=chat.last_message.message_id,
            last_message_at=chat.last_message.created_at,
            sync_status=Deal.SyncStatus.PENDING,
        )

    def _save_message_to_dynamodb(self, chat: Chat, deal: Deal) -> None:
        """
        Save message to DynamoDB.

        CONSISTENCY NOTE:
        This is outside SQL transaction. If this fails after SQL commit,
        we have inconsistent state. Options:
        1. Use DynamoDB transactions (preferred)
        2. Two-phase commit
        3. Saga pattern with compensation
        4. Accept eventual consistency + repair job

        For this implementation, we save to DynamoDB first, then update SQL.
        If DynamoDB fails, SQL transaction rolls back.
        If SQL fails after DynamoDB write, we have orphan message in DynamoDB
        (can be cleaned up by repair job).

        TODO for production:
        - Implement idempotency (use message_id as DynamoDB key)
        - Add repair job to reconcile DynamoDB and SQL
        """
        self.message_store.save_message(
            chat_id=deal.external_id,
            message_id=chat.last_message.message_id,
            text=chat.last_message.text,
            created_at=chat.last_message.created_at,
        )

    def _save_cursor(self, cursor: str) -> None:
        """
        Save cursor after successful page processing.

        This ensures we can resume from exactly where we left off.
        """
        self.state.cursor = cursor
        self.state.save(update_fields=['cursor', 'updated_at'])

    def _increment_processed(self) -> None:
        """Increment processed counter."""
        self.state.processed_chats += 1
        self.state.save(update_fields=['processed_chats', 'updated_at'])
