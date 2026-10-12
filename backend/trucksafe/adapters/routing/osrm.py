"""OSRM (Open Source Routing Machine) adapter for keyless routing."""

import logging
from typing import Any

import httpx

from trucksafe.adapters.routing.base import RawRoute
from trucksafe.domain.models import LatLon

logger = logging.getLogger(__name__)


class OSRMRoutingError(Exception):
    """Exception raised when OSRM routing request fails."""


class OSRMRoutingUnavailable(OSRMRoutingError):
    """Exception raised when OSRM server is unreachable or times out."""


class OSRMRoutingProvider:
    """Keyless routing provider using the public OSRM car profile endpoint."""

    DEFAULT_BASE_URL = "https://router.project-osrm.org"

    def __init__(self, base_url: str | None = None, timeout: float = 12.0) -> None:
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    def get_routes(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon] | None = None,
    ) -> list[RawRoute]:
        pts = [origin] + (waypoints or []) + [dest]
        coords_str = ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in pts)

        url = f"{self.base_url}/route/v1/driving/{coords_str}"
        params = {
            "alternatives": "true",
            "overview": "full",
            "geometries": "geojson",
            "annotations": "duration,distance",
        }
        headers = {"User-Agent": "TruckSafe/1.0 (assessment demo)"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.NetworkError) as err:
            logger.warning("OSRM request failed: %s", err)
            raise OSRMRoutingUnavailable(f"OSRM request failed: {err}") from err

        if resp.status_code >= 500:
            raise OSRMRoutingUnavailable(f"OSRM service error {resp.status_code}")
        if resp.status_code != 200:
            raise OSRMRoutingError(f"OSRM status {resp.status_code}: {resp.text}")

        return self.parse_response(resp.json())

    @classmethod
    def parse_response(cls, data: dict[str, Any]) -> list[RawRoute]:
        code = data.get("code")
        if code != "Ok":
            return []

        routes_data = data.get("routes", [])
        raw_routes: list[RawRoute] = []

        for idx, r in enumerate(routes_data):
            geom = r.get("geometry", {})
            raw_coords = geom.get("coordinates", [])
            coords = [LatLon(lat=c[1], lon=c[0]) for c in raw_coords]
            distance_m = float(r.get("distance", 0.0))
            duration_s = float(r.get("duration", 0.0))

            legs = r.get("legs", [])
            seg_durations: list[float] = []
            seg_distances: list[float] = []
            for leg in legs:
                ann = leg.get("annotation", {})
                seg_durations.extend(ann.get("duration", []))
                seg_distances.extend(ann.get("distance", []))

            if len(coords) > 1 and len(seg_durations) == len(coords) - 1:
                final_durations: list[float] | None = seg_durations
                final_distances: list[float] | None = seg_distances
            else:
                final_durations = None
                final_distances = None

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
