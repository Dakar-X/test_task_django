"""
URL configuration for sync app.
"""

from django.urls import path

from .views import SyncStartView, SyncStatusView

urlpatterns = [
    path('start/', SyncStartView.as_view(), name='sync-start'),
    path('status/<str:task_id>/', SyncStatusView.as_view(), name='sync-status'),
]
