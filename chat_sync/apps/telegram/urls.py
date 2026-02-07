"""
URL configuration for Telegram integration.
"""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .webhook import TelegramWebhookView

urlpatterns = [
    path('webhook/', csrf_exempt(TelegramWebhookView.as_view()), name='telegram-webhook'),
]
