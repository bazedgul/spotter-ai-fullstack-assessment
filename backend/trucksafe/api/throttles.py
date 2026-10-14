"""Rate throttle classes for TruckSafe endpoints."""

from rest_framework.throttling import AnonRateThrottle


class AnalyzeRateThrottle(AnonRateThrottle):
    """Throttle for /api/analyze endpoint (12 requests/min)."""

    scope = "analyze"


class HeatmapRateThrottle(AnonRateThrottle):
    """Throttle for /api/heatmap endpoint (12 requests/min)."""

    scope = "heatmap"
