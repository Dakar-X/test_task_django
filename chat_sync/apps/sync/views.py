"""
Async DRF views for sync operations.
"""

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SyncState
from .tasks import sync_chats_task


class SyncStartView(APIView):
    """View to start a chat synchronization."""

    async def post(self, request: Request) -> Response:
        """Start a new sync task."""
        max_date = request.data.get('max_date')

        result = sync_chats_task.delay(max_date=max_date)

        return Response(
            {
                'status': 'started',
                'task_id': result.id,
                'message': 'Sync task has been queued.',
            },
            status=status.HTTP_202_ACCEPTED,
        )


class SyncStatusView(APIView):
    """View to check sync task status."""

    async def get(self, request: Request, task_id: str) -> Response:
        """Get the status of a sync task."""
        try:
            state = await SyncState.objects.aget(task_id=task_id)
        except SyncState.DoesNotExist:
            return Response(
                {'error': 'Sync state not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'task_id': state.task_id,
            'status': state.status,
            'cursor': state.cursor,
            'processed_chats': state.processed_chats,
            'error_message': state.error_message or None,
            'started_at': state.started_at.isoformat(),
            'updated_at': state.updated_at.isoformat(),
        })
