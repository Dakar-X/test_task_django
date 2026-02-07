"""
Models for synchronization state tracking.
"""

from django.db import models


class SyncState(models.Model):
    """
    Tracks the state of chat synchronization for fault tolerance.

    Stores cursor position and progress to allow resuming after failures.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    task_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    cursor = models.CharField(max_length=255, blank=True)
    max_date = models.DateTimeField(null=True, blank=True)
    processed_chats = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sync_states'
        ordering = ['-started_at']

    def __str__(self) -> str:
        return f'SyncState {self.task_id} - {self.status}'
