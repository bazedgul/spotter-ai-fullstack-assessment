"""URL patterns for trucksafe API."""

from django.urls import path

from trucksafe.api.views import analyze_trip, geocode_search, health_check, heatmap_trip

urlpatterns = [
    path("health", health_check, name="health-check"),
    path("geocode", geocode_search, name="geocode-search"),
    path("analyze", analyze_trip, name="analyze-trip"),
    path("heatmap", heatmap_trip, name="heatmap-trip"),
]
