"""
URL configuration for chat_sync project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # REST API
    path('api/v1/', include('apps.chats.urls')),
    path('api/v1/sync/', include('apps.sync.urls')),

    # Telegram webhook
    path('telegram/', include('apps.telegram.urls')),
]
