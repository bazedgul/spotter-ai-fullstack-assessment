"""API views for TruckSafe endpoints."""

import logging

from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from trucksafe.adapters.geocoding.mapbox import MapboxGeocodingProvider
from trucksafe.adapters.weather.open_meteo import WeatherUnavailable
from trucksafe.api.errors import error_response
from trucksafe.api.serializers import AnalyzeRequestSerializer, HeatmapRequestSerializer
from trucksafe.api.throttles import AnalyzeRateThrottle
from trucksafe.domain.models import LatLon
from trucksafe.services.analyze import (
    AnalyzeOrchestrator,
    AnalyzeValidationError,
)
from trucksafe.services.heatmap import build_heatmap
from trucksafe.services.routes_builder import (
    RouteNotFoundError,
    RouteTooLongError,
    RouteValidationError,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:
    """Health check endpoint."""
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
def geocode_search(request: Request) -> Response:
    """Location autocompletion endpoint proxied through backend (Section 5.8)."""
    q = request.query_params.get("q", "").strip()
    if len(q) < 3:
        return Response([])

    cache_key = f"geocode:{q.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    provider = MapboxGeocodingProvider()
    results = provider.geocode(q)
    data = [{"label": r.label, "lat": round(r.lat, 6), "lon": round(r.lon, 6)} for r in results]

    cache.set(cache_key, data, timeout=86400)
    return Response(data)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnalyzeRateThrottle])
def analyze_trip(request: Request) -> Response:
    """Trip safety and route comparison endpoint (Section 5.10)."""
    serializer = AnalyzeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            code="VALIDATION_ERROR",
            message="Invalid request parameters",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    validated = serializer.validated_data
    orig_data = validated["origin"]
    dest_data = validated["destination"]

    origin = LatLon(lat=orig_data["lat"], lon=orig_data["lon"])
    dest = LatLon(lat=dest_data["lat"], lon=dest_data["lon"])

    orchestrator = AnalyzeOrchestrator()

    try:
        result = orchestrator.analyze(
            origin=origin,
            origin_label=orig_data.get("label", ""),
            destination=dest,
            dest_label=dest_data.get("label", ""),
            departure_local=validated["departure_local"],
            load_weight_lb=validated["load_weight_lb"],
            checkpoint_interval_miles=validated["checkpoint_interval_miles"],
            simulate_storm=validated.get("simulate_storm", False),
        )
        return Response(result)

    except (AnalyzeValidationError, RouteValidationError) as exc:
        return error_response(
            code="VALIDATION_ERROR",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except RouteNotFoundError as exc:
        return error_response(
            code="NO_ROUTE_FOUND",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except RouteTooLongError as exc:
        return error_response(
            code="ROUTE_TOO_LONG",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except WeatherUnavailable as exc:
        return error_response(
            code="WEATHER_UNAVAILABLE",
            message=str(exc),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        logger.exception("Unexpected error in /api/analyze: %s", exc)
        return error_response(
            code="INTERNAL_ERROR",
            message="An unexpected server error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnalyzeRateThrottle])
def heatmap_trip(request: Request) -> Response:
    serializer = HeatmapRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response("VALIDATION_ERROR", "Invalid heatmap request", serializer.errors)
    try:
        return Response(build_heatmap(serializer.validated_data))
    except WeatherUnavailable as exc:
        return error_response(
            "WEATHER_UNAVAILABLE", str(exc), status_code=status.HTTP_502_BAD_GATEWAY
        )
    except Exception:
        logger.exception("Unexpected error in /api/heatmap")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred", status_code=500)
