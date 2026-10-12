"""Geocoding provider interface and result dataclass."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeocodeResult:
    """Geocoded location result."""

    label: str
    lat: float
    lon: float


class GeocodingProvider(Protocol):
    """Protocol for location geocoding lookup."""

    def geocode(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        """Search locations matching query string."""
        ...
