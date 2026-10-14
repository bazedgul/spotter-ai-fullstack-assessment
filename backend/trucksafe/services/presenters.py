"""Presenters for formatting analyze API response according to Section 5.10."""

from datetime import datetime
from typing import Any

import polyline

from trucksafe.domain.geo import rdp_simplify
from trucksafe.domain.models import Assessment, Checkpoint, RoutePath, WeatherSample
from trucksafe.domain.recommend import RouteCandidate
from trucksafe.services.timezones import format_local_iso, tz_at


def present_checkpoint(
    cp: Checkpoint,
    weather: WeatherSample,
    assessment: Assessment,
) -> dict[str, Any]:
    """Format a single checkpoint object."""
    cp_tz, _ = tz_at(cp.lat, cp.lon)
    eta_local, tz_name = format_local_iso(cp.eta_utc, cp_tz)

    risk_level_str = assessment.level.name if assessment.level is not None else "UNKNOWN"
    risk_score = int(assessment.level) if assessment.level is not None else -1

    drivers = [
        {
            "condition": d.condition,
            "level": d.level.name,
            "note": d.note,
        }
        for d in assessment.drivers
    ]

    return {
        "index": cp.index,
        "mile": round(cp.mile, 1),
        "lat": round(cp.lat, 6),
        "lon": round(cp.lon, 6),
        "eta_utc": cp.eta_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eta_local": eta_local,
        "tz": tz_name,
        "owned_miles": round(cp.owned_miles, 1),
        "weather": {
            "wind_mph": round(weather.wind_mph, 1) if weather.wind_mph is not None else None,
            "gust_mph": round(weather.gust_mph, 1) if weather.gust_mph is not None else None,
            "rain_in_hr": round(weather.rain_in_hr, 2) if weather.rain_in_hr is not None else None,
            "snow_in_hr": round(weather.snow_in_hr, 2) if weather.snow_in_hr is not None else None,
            "status": weather.status,
        },
        "risk": {
            "level": risk_level_str,
            "score": risk_score,
            "drivers": drivers,
        },
    }


def present_route(
    candidate: RouteCandidate,
    path: RoutePath,
    rank: int,
    is_recommended: bool,
    explanation: str,
    checkpoints_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Format a single route object for API response."""
    m = candidate.metrics
    # Simplify coordinates for display (tolerance ~ 0.0005 deg keeps geometry under budget)
    simplified_coords = rdp_simplify(path.coords, tolerance_deg=0.0005)
    geojson_coords = [[round(p.lon, 6), round(p.lat, 6)] for p in simplified_coords]

    return {
        "id": candidate.id,
        "label": candidate.label,
        "summary": path.summary,
        "rank": rank,
        "recommended": is_recommended,
        "explanation": explanation,
        "distance_miles": round(m.distance_mi, 1),
        "duration_minutes": int(round(m.duration_min)),
        "geometry": {
            "type": "LineString",
            "coordinates": geojson_coords,
        },
        "metrics": {
            "no_travel_miles": round(m.no_travel_miles, 1),
            "severe_miles": round(m.severe_miles, 1),
            "high_miles": round(m.high_miles, 1),
            "moderate_miles": round(m.moderate_miles, 1),
            "low_miles": round(m.low_miles, 1),
            "unknown_miles": round(m.unknown_miles, 1),
            "avg_risk": round(m.avg_risk, 2) if m.avg_risk is not None else None,
            "max_level": m.max_level.name if m.max_level is not None else None,
            "blocked": m.blocked,
        },
        "checkpoints": checkpoints_data,
    }


def build_heatmap_request(
    routes: list[RoutePath],
    departure_utc: datetime,
    load_weight_lb: float,
    simulate_storm: bool,
) -> dict[str, Any]:
    """Build compact heatmap request payload using precision-6 polyline."""
    encoded_routes = []
    for r in routes:
        pts = [(p.lat, p.lon) for p in r.coords]
        encoded = polyline.encode(pts, precision=6)
        encoded_routes.append({"id": r.id, "polyline": encoded})

    return {
        "routes": encoded_routes,
        "departure_utc": departure_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "load_weight_lb": load_weight_lb,
        "simulate_storm": simulate_storm,
    }
