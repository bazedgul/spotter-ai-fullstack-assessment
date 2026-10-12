"""URL patterns for trucksafe API."""

from django.urls import path

from trucksafe.api.views import health_check

urlpatterns = [
    path("health", health_check, name="health-check"),
]
