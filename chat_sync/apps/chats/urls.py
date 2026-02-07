"""
URL configuration for chats app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DealViewSet

router = DefaultRouter()
router.register('deals', DealViewSet, basename='deal')

urlpatterns = [
    path('', include(router.urls)),
]
