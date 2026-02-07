"""
DRF serializers for chat entities.
"""

from rest_framework import serializers

from .models import Customer, Deal


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer."""

    # Use avatar property (returns S3 URL or original URL)
    avatar = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = ['id', 'external_id', 'name', 'avatar']
        read_only_fields = fields


class DealListSerializer(serializers.ModelSerializer):
    """Serializer for Deal list (includes customer)."""

    customer = CustomerSerializer(read_only=True)

    class Meta:
        model = Deal
        fields = [
            'id',
            'external_id',
            'customer',
            'last_message_id',
            'last_message_at',
            'total_messages',
        ]
        read_only_fields = fields


class DealDetailSerializer(serializers.ModelSerializer):
    """Serializer for Deal detail (includes messages from DynamoDB)."""

    customer = CustomerSerializer(read_only=True)
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            'id',
            'external_id',
            'customer',
            'last_message_id',
            'last_message_at',
            'total_messages',
            'messages',
        ]
        read_only_fields = fields

    def get_messages(self, obj: Deal) -> list[dict]:
        """
        Fetch messages from DynamoDB.

        TODO: Add pagination for deals with thousands of messages.
        """
        from apps.sync.services.dynamodb import get_message_store
        store = get_message_store()
        return store.get_messages(obj.external_id)
