"""DRF serializers for request validation and formatting."""

from rest_framework import serializers


class LocationSerializer(serializers.Serializer):
    """Geographic point with a human-readable display label."""

    label = serializers.CharField(max_length=255, required=False, default="")
    lat = serializers.FloatField(min_value=-90.0, max_value=90.0)
    lon = serializers.FloatField(min_value=-180.0, max_value=180.0)


class AnalyzeRequestSerializer(serializers.Serializer):
    """Request payload serializer for POST /api/analyze."""

    origin = LocationSerializer()
    destination = LocationSerializer()
    departure_local = serializers.CharField(max_length=64)
    load_weight_lb = serializers.FloatField(min_value=0.001, max_value=100_000.0)
    checkpoint_interval_miles = serializers.ChoiceField(
        choices=[10, 25, 50],
        default=25,
    )
    simulate_storm = serializers.BooleanField(required=False, default=False)

    def validate_departure_local(self, value: str) -> str:
        try:
            from datetime import datetime

            datetime.fromisoformat(value)
        except ValueError as err:
            raise serializers.ValidationError(
                "Invalid departure_local format. Expected ISO-8601 string (e.g. 2026-10-14T08:00)."
            ) from err
        return value


class HeatmapRequestSerializer(serializers.Serializer):
    routes = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    departure_utc = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0.001, max_value=100_000)
    simulate_storm = serializers.BooleanField(required=False, default=False)
