"""Mapbox Directions API v5 adapter."""

import logging
from typing import Any

import httpx
from django.conf import settings

from trucksafe.adapters.routing.base import RawRoute
from trucksafe.domain.models import LatLon

logger = logging.getLogger(__name__)


class MapboxRoutingError(Exception):
    """Exception raised when Mapbox Directions request fails."""


class MapboxAuthError(MapboxRoutingError):
    """Exception raised when Mapbox token is missing or invalid."""


class MapboxRoutingUnavailable(MapboxRoutingError):
    """Exception raised when Mapbox experiences 5xx or network timeout."""


class MapboxRoutingProvider:
    """Routing adapter using Mapbox Directions v5 with driving profile."""

    def __init__(self, access_token: str | None = None, timeout: float = 12.0) -> None:
        self.access_token = access_token or getattr(settings, "MAPBOX_TOKEN", "")
        self.timeout = timeout

    def get_routes(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon] | None = None,
    ) -> list[RawRoute]:
        if not self.access_token:
            raise MapboxAuthError("MAPBOX_TOKEN is missing or empty")

        # Format coordinates: lon,lat;lon,lat
        pts = [origin] + (waypoints or []) + [dest]
        coords_str = ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in pts)

        url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords_str}"
        params = {
            "alternatives": "true",
            "geometries": "geojson",
            "overview": "full",
            "steps": "false",
            "annotations": "distance,duration",
            "access_token": self.access_token,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as err:
            logger.warning("Mapbox Directions network error: %s", err)
            raise MapboxRoutingUnavailable(f"Mapbox request failed: {err}") from err

        if resp.status_code == 401:
            raise MapboxAuthError("Invalid Mapbox access token")
        if resp.status_code >= 500:
            raise MapboxRoutingUnavailable(f"Mapbox server error {resp.status_code}")
        if resp.status_code != 200:
            raise MapboxRoutingError(f"Mapbox error status {resp.status_code}: {resp.text}")

        return self.parse_response(resp.json())

    @classmethod
    def parse_response(cls, data: dict[str, Any]) -> list[RawRoute]:
        routes_data = data.get("routes", [])
        raw_routes: list[RawRoute] = []

        for idx, r in enumerate(routes_data):
            geom = r.get("geometry", {})
            raw_coords = geom.get("coordinates", [])
            coords = [LatLon(lat=c[1], lon=c[0]) for c in raw_coords]
            distance_m = float(r.get("distance", 0.0))
            duration_s = float(r.get("duration", 0.0))

            # Concatenate leg annotations
            legs = r.get("legs", [])
            seg_durations: list[float] = []
            seg_distances: list[float] = []
            for leg in legs:
                ann = leg.get("annotation", {})
                seg_durations.extend(ann.get("duration", []))
                seg_distances.extend(ann.get("distance", []))

            # Validate annotation length invariant: len == len(coords) - 1
            if len(coords) > 1 and len(seg_durations) == len(coords) - 1:
                final_durations: list[float] | None = seg_durations
                final_distances: list[float] | None = seg_distances
            else:
                # Annotation length mismatch fallback: scale by segment distances
                final_durations = None
                final_distances = None

            summary = ""
            if legs and legs[0].get("summary"):
                summary = str(legs[0]["summary"])
            if not summary:
                summary = f"Route {chr(ord('A') + idx)}"

            raw_routes.append(
                RawRoute(
                    coords=coords,
                    distance_m=distance_m,
                    duration_s=duration_s,
                    seg_durations_s=final_durations,
                    seg_distances_m=final_distances,
                    summary=summary,
                )
            )

        return raw_routes
