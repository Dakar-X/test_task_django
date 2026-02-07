"""
DRF views for chat entities.

PERSISTENCE REQUIREMENT:
"We must only return chats that have both the customer and
the message successfully saved"

This is enforced by filtering on sync_status=COMPLETE.
"""

from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Deal
from .serializers import DealDetailSerializer, DealListSerializer


class DealViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Deal model.

    Only returns COMPLETE deals (customer + message saved).
    """

    def get_queryset(self):
        """
        Return only complete deals.

        Per requirements: "We must only return chats that have both
        the customer and the message successfully saved"
        """
        return Deal.objects.filter(
            sync_status=Deal.SyncStatus.COMPLETE,
            customer__isnull=False,
        ).select_related('customer').order_by('-last_message_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DealDetailSerializer
        return DealListSerializer
