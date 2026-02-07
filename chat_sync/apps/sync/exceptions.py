"""
Custom exceptions for the sync service.
"""


class SyncError(Exception):
    """Base exception for sync errors."""
    pass


class ExternalAPIError(SyncError):
    """Error when communicating with the external API."""
    pass


class StorageError(SyncError):
    """Error when storing data to S3 or DynamoDB."""
    pass


class ConcurrencyError(SyncError):
    """Error when another sync is already running."""
    pass
