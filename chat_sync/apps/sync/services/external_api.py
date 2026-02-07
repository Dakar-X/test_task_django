"""
External API client with mock implementation.

Mock API format (from test task):

GET /api/v1/chats?cursor={cursor}
{
    "items": [
        {
            "id": "chat_123",
            "customer_id": "cust_999",
            "last_message": {
                "id": "msg_555",
                "text": "Hello!",
                "created_at": "2024-05-20T10:00:00Z"
            }
        }
    ],
    "next_cursor": "NDI="
}

GET /api/v1/customers/{customer_id}
{
    "id": "cust_999",
    "name": "John Doe",
    "avatar_url": "https://example.com/photo.jpg"
}

"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Message in a chat."""
    message_id: str
    text: str
    created_at: datetime


@dataclass
class ChatCustomer:
    """Customer data."""
    external_id: str
    name: str
    avatar_url: str


@dataclass
class Chat:
    """Chat from external API."""
    external_id: str
    customer: ChatCustomer
    last_message: ChatMessage


@dataclass
class ChatPage:
    """Page of chats from API."""
    chats: list[Chat]
    next_cursor: str | None
    has_more: bool


class ExternalAPIError(Exception):
    """Error from external API."""
    pass


class MockExternalAPIClient:
    """
    Mock external API client.

    Simulates:
    - Cursor-based pagination
    - Occasional failures (for resilience testing)
    - High latency (random delays)

    For test task: generates predictable data for verification.
    """

    def __init__(
        self,
        total_chats: int = 50,
        page_size: int = 10,
        failure_rate: float = 0.0,  # Set > 0 to simulate failures
        base_date: datetime | None = None,
    ):
        self.total_chats = total_chats
        self.page_size = page_size
        self.failure_rate = failure_rate
        self.base_date = base_date or datetime(2024, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        self._customers_cache: dict[str, ChatCustomer] = {}

    def get_chats(self, cursor: str | None = None) -> ChatPage:
        """
        Fetch page of chats.

        Args:
            cursor: Base64-encoded page number (or None for first page)

        Returns:
            ChatPage with chats and next_cursor

        Raises:
            ExternalAPIError: If API fails (simulated)
        """
        # Simulate occasional failures
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            raise ExternalAPIError('Simulated API failure')

        # Decode cursor (page number)
        page_num = self._decode_cursor(cursor)
        start_idx = page_num * self.page_size
        end_idx = min(start_idx + self.page_size, self.total_chats)

        # Generate chats for this page
        chats = []
        for i in range(start_idx, end_idx):
            chat = self._generate_chat(i)
            chats.append(chat)

        # Determine pagination
        has_more = end_idx < self.total_chats
        next_cursor = self._encode_cursor(page_num + 1) if has_more else None

        logger.debug(
            f'MockAPI: page={page_num}, chats={len(chats)}, has_more={has_more}'
        )

        return ChatPage(
            chats=chats,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def get_customer(self, customer_id: str) -> ChatCustomer:
        """
        Fetch customer data.

        Args:
            customer_id: Customer external ID

        Returns:
            ChatCustomer

        Raises:
            ExternalAPIError: If API fails or customer not found
        """
        # Simulate occasional failures
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            raise ExternalAPIError('Simulated API failure')

        if customer_id in self._customers_cache:
            return self._customers_cache[customer_id]

        raise ExternalAPIError(f'Customer not found: {customer_id}')

    def _generate_chat(self, index: int) -> Chat:
        """Generate a chat with predictable data."""
        chat_id = f'chat_{index:04d}'
        customer_id = f'cust_{index:04d}'
        message_id = f'msg_{index:04d}'

        # Messages are ordered by date descending (newest first)
        message_date = self.base_date - timedelta(hours=index)

        # Create customer
        customer = ChatCustomer(
            external_id=customer_id,
            name=f'Customer {index}',
            avatar_url=f'https://example.com/avatars/{customer_id}.jpg',
        )
        self._customers_cache[customer_id] = customer

        # Create message
        message = ChatMessage(
            message_id=message_id,
            text=f'Message from customer {index}',
            created_at=message_date,
        )

        return Chat(
            external_id=chat_id,
            customer=customer,
            last_message=message,
        )

    def _decode_cursor(self, cursor: str | None) -> int:
        """Decode cursor to page number."""
        if not cursor:
            return 0
        try:
            import base64
            decoded = base64.b64decode(cursor).decode('utf-8')
            return int(decoded)
        except Exception:
            return 0

    def _encode_cursor(self, page_num: int) -> str:
        """Encode page number to cursor."""
        import base64
        return base64.b64encode(str(page_num).encode('utf-8')).decode('utf-8')


# Singleton client
_client: MockExternalAPIClient | None = None


def get_external_api_client() -> MockExternalAPIClient:
    """Get the external API client instance."""
    global _client
    if _client is None:
        _client = MockExternalAPIClient()
    return _client


def reset_api_client() -> None:
    """Reset client (for testing)."""
    global _client
    _client = None
