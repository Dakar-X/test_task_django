"""
Celery tasks for chat synchronization.
"""

import logging
from datetime import datetime

from celery import shared_task
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

from .models import SyncState
from .services.sync_service import SyncService

logger = logging.getLogger(__name__)

SYNC_LOCK_KEY = 'sync_chats_lock'
SYNC_LOCK_TIMEOUT = 3600  # 1 hour


@shared_task(bind=True, max_retries=3)
def sync_chats_task(self, max_date: str | None = None) -> dict:
    """
    Celery task to synchronize chats from external API.

    Uses distributed locking to prevent concurrent execution.
    Supports resuming from failed/interrupted syncs.

    Args:
        max_date: Optional ISO date string. If provided, only sync
                  chats with messages before this date.

    Returns:
        Dict with status and processed count.
    """
    if not cache.add(SYNC_LOCK_KEY, self.request.id, timeout=SYNC_LOCK_TIMEOUT):
        logger.warning('Another sync is already running')
        return {'status': 'skipped', 'reason': 'Another sync is running'}

    state = None
    try:
        state = _get_or_create_sync_state(
            task_id=self.request.id,
            max_date=max_date,
        )
        state.status = SyncState.Status.RUNNING
        state.save(update_fields=['status', 'updated_at'])

        sync_service = SyncService(state)
        sync_service.run()

        state.status = SyncState.Status.COMPLETED
        state.save(update_fields=['status', 'updated_at'])

        logger.info(f'Sync completed: {state.processed_chats} chats processed')
        return {
            'status': 'completed',
            'processed': state.processed_chats,
            'task_id': state.task_id,
        }

    except Exception as e:
        logger.exception(f'Sync failed: {e}')
        if state:
            state.status = SyncState.Status.FAILED
            state.error_message = str(e)
            state.save(update_fields=['status', 'error_message', 'updated_at'])

        raise self.retry(exc=e, countdown=60)

    finally:
        cache.delete(SYNC_LOCK_KEY)


def _get_or_create_sync_state(
    task_id: str,
    max_date: str | None,
) -> SyncState:
    """
    Get an existing incomplete sync state or create a new one.

    This allows resuming interrupted syncs from the last cursor position.

    Args:
        task_id: The Celery task ID.
        max_date: Optional max date string.

    Returns:
        SyncState instance.
    """
    incomplete_state = SyncState.objects.filter(
        status__in=[SyncState.Status.RUNNING, SyncState.Status.PENDING]
    ).first()

    if incomplete_state:
        logger.info(
            f'Resuming incomplete sync {incomplete_state.task_id} '
            f'from cursor {incomplete_state.cursor}'
        )
        return incomplete_state

    parsed_date = None
    if max_date:
        parsed_date = parse_datetime(max_date)
        if parsed_date is None:
            try:
                parsed_date = datetime.fromisoformat(max_date)
            except ValueError:
                logger.warning(f'Could not parse max_date: {max_date}')

    return SyncState.objects.create(
        task_id=task_id,
        status=SyncState.Status.PENDING,
        max_date=parsed_date,
    )
