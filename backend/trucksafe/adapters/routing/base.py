"""Routing provider interfaces and raw route representations."""

from dataclasses import dataclass
from typing import Protocol

from trucksafe.domain.models import LatLon


@dataclass(frozen=True)
class RawRoute:
    """Raw route geometry and timing data returned by an external routing provider."""

    coords: list[LatLon]
    distance_m: float
    duration_s: float
    seg_durations_s: list[float] | None
    seg_distances_m: list[float] | None
    summary: str


class RoutingProvider(Protocol):
    """Protocol implemented by routing engines (Mapbox, OSRM, etc.)."""

    def get_routes(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon] | None = None,
    ) -> list[RawRoute]:
        """Fetch routes between origin and destination with optional via waypoints."""
        ...
