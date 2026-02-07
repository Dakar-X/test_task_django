"""
DynamoDB message storage with mock implementation for local development.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseMessageStore(ABC):
    """Abstract base class for message storage."""

    @abstractmethod
    def save_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        created_at: datetime,
    ) -> None:
        """
        Save a message to the store.

        Args:
            chat_id: The chat/deal external ID.
            message_id: The unique message ID.
            text: The message text.
            created_at: When the message was created.
        """
        pass

    @abstractmethod
    def get_messages(self, chat_id: str) -> list[dict[str, Any]]:
        """
        Get all messages for a chat.

        Args:
            chat_id: The chat/deal external ID.

        Returns:
            List of message dictionaries.
        """
        pass

    @abstractmethod
    def get_message(self, chat_id: str, message_id: str) -> dict[str, Any] | None:
        """
        Get a specific message.

        Args:
            chat_id: The chat/deal external ID.
            message_id: The message ID.

        Returns:
            Message dictionary or None if not found.
        """
        pass

    @abstractmethod
    def delete_message(self, chat_id: str, message_id: str) -> bool:
        """
        Delete a message.

        Args:
            chat_id: The chat/deal external ID.
            message_id: The message ID.

        Returns:
            True if deleted, False otherwise.
        """
        pass


class MockMessageStore(BaseMessageStore):
    """
    Mock DynamoDB message store for local development.

    Stores messages in memory.
    """

    _messages: ClassVar[dict[str, dict[str, dict[str, Any]]]] = {}

    def save_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        created_at: datetime,
    ) -> None:
        """Store message in memory."""
        if chat_id not in self._messages:
            self._messages[chat_id] = {}

        self._messages[chat_id][message_id] = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'created_at': created_at.isoformat(),
        }
        logger.debug(f'MockDynamoDB: Saved message {message_id} to chat {chat_id}')

    def get_messages(self, chat_id: str) -> list[dict[str, Any]]:
        """Retrieve all messages for a chat."""
        chat_messages = self._messages.get(chat_id, {})
        messages = list(chat_messages.values())
        return sorted(messages, key=lambda m: m['created_at'])

    def get_message(self, chat_id: str, message_id: str) -> dict[str, Any] | None:
        """Retrieve a specific message."""
        chat_messages = self._messages.get(chat_id, {})
        return chat_messages.get(message_id)

    def delete_message(self, chat_id: str, message_id: str) -> bool:
        """Delete a message from memory."""
        if chat_id in self._messages and message_id in self._messages[chat_id]:
            del self._messages[chat_id][message_id]
            return True
        return False

    def clear_all(self) -> None:
        """Clear all stored messages (for testing)."""
        self._messages.clear()


class PynamoDBMessageStore(BaseMessageStore):
    """
    Real DynamoDB message store using PynamoDB.

    For production use.
    """

    def __init__(self):
        from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
        from pynamodb.models import Model

        class MessageModel(Model):
            class Meta:
                table_name = 'messages'
                region = settings.DYNAMODB_REGION
                host = settings.DYNAMODB_HOST

            chat_id = UnicodeAttribute(hash_key=True)
            message_id = UnicodeAttribute(range_key=True)
            text = UnicodeAttribute()
            created_at = UTCDateTimeAttribute()

        self.model = MessageModel
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Create the table if it doesn't exist."""
        if not self.model.exists():
            self.model.create_table(
                read_capacity_units=5,
                write_capacity_units=5,
                wait=True,
            )

    def save_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        created_at: datetime,
    ) -> None:
        """Save message to DynamoDB."""
        message = self.model(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            created_at=created_at,
        )
        message.save()

    def get_messages(self, chat_id: str) -> list[dict[str, Any]]:
        """Retrieve all messages for a chat from DynamoDB."""
        messages = []
        for item in self.model.query(chat_id):
            messages.append({
                'chat_id': item.chat_id,
                'message_id': item.message_id,
                'text': item.text,
                'created_at': item.created_at.isoformat(),
            })
        return sorted(messages, key=lambda m: m['created_at'])

    def get_message(self, chat_id: str, message_id: str) -> dict[str, Any] | None:
        """Retrieve a specific message from DynamoDB."""
        try:
            item = self.model.get(chat_id, message_id)
            return {
                'chat_id': item.chat_id,
                'message_id': item.message_id,
                'text': item.text,
                'created_at': item.created_at.isoformat(),
            }
        except self.model.DoesNotExist:
            return None

    def delete_message(self, chat_id: str, message_id: str) -> bool:
        """Delete a message from DynamoDB."""
        try:
            item = self.model.get(chat_id, message_id)
            item.delete()
            return True
        except self.model.DoesNotExist:
            return False


_message_store: BaseMessageStore | None = None


def get_message_store() -> BaseMessageStore:
    """
    Get the configured message store instance.

    Returns MockMessageStore for local development, PynamoDBMessageStore for production.
    """
    global _message_store
    if _message_store is None:
        if getattr(settings, 'USE_MOCK_SERVICES', True):
            _message_store = MockMessageStore()
        else:
            _message_store = PynamoDBMessageStore()
    return _message_store
