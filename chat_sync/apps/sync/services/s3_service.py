"""
S3 storage service with mock implementation for local development.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import ClassVar

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseS3Service(ABC):
    """Abstract base class for S3 service."""

    @abstractmethod
    def upload_file(self, key: str, data: bytes, content_type: str = '') -> str:
        """
        Upload a file to S3.

        Args:
            key: The S3 key for the file.
            data: The file contents as bytes.
            content_type: The MIME type of the file.

        Returns:
            The URL or reference to the uploaded file.
        """
        pass

    @abstractmethod
    def get_file(self, key: str) -> bytes | None:
        """
        Retrieve a file from S3.

        Args:
            key: The S3 key for the file.

        Returns:
            The file contents as bytes, or None if not found.
        """
        pass

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            key: The S3 key for the file.

        Returns:
            True if deleted, False otherwise.
        """
        pass

    def generate_avatar_key(self, customer_id: str, url: str) -> str:
        """
        Generate a unique S3 key for a customer avatar.

        Args:
            customer_id: The customer's external ID.
            url: The original avatar URL.

        Returns:
            A unique S3 key.
        """
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f'avatars/{customer_id}/{url_hash}'


class MockS3Service(BaseS3Service):
    """
    Mock S3 service for local development.

    Stores files in memory.
    """

    _storage: ClassVar[dict[str, bytes]] = {}
    _content_types: ClassVar[dict[str, str]] = {}

    def upload_file(self, key: str, data: bytes, content_type: str = '') -> str:
        """Store file in memory."""
        self._storage[key] = data
        if content_type:
            self._content_types[key] = content_type
        logger.debug(f'MockS3: Uploaded {len(data)} bytes to {key}')
        return f'mock-s3://{key}'

    def get_file(self, key: str) -> bytes | None:
        """Retrieve file from memory."""
        return self._storage.get(key)

    def delete_file(self, key: str) -> bool:
        """Delete file from memory."""
        if key in self._storage:
            del self._storage[key]
            self._content_types.pop(key, None)
            return True
        return False

    def clear_all(self) -> None:
        """Clear all stored files (for testing)."""
        self._storage.clear()
        self._content_types.clear()


class RealS3Service(BaseS3Service):
    """
    Real S3 service using boto3.

    For production use.
    """

    def __init__(self):
        import boto3
        self.client = boto3.client(
            's3',
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = settings.S3_BUCKET

    def upload_file(self, key: str, data: bytes, content_type: str = '') -> str:
        """Upload file to S3."""
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            **extra_args,
        )
        return f's3://{self.bucket}/{key}'

    def get_file(self, key: str) -> bytes | None:
        """Retrieve file from S3."""
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response['Body'].read()
        except self.client.exceptions.NoSuchKey:
            return None

    def delete_file(self, key: str) -> bool:
        """Delete file from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


_s3_service: BaseS3Service | None = None


def get_s3_service() -> BaseS3Service:
    """
    Get the configured S3 service instance.

    Returns MockS3Service for local development, RealS3Service for production.
    """
    global _s3_service
    if _s3_service is None:
        if getattr(settings, 'USE_MOCK_SERVICES', True):
            _s3_service = MockS3Service()
        else:
            _s3_service = RealS3Service()
    return _s3_service
