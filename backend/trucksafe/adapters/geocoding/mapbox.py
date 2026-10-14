"""Mapbox Geocoding v6 adapter with keyless fallback."""

import logging
from typing import Any

import httpx
from django.conf import settings

from trucksafe.adapters.geocoding.base import GeocodeResult

logger = logging.getLogger(__name__)


class MapboxGeocodingProvider:
    """Geocoding provider using Mapbox Geocoding v6 forward search."""

    def __init__(self, access_token: str | None = None, timeout: float = 6.0) -> None:
        self.access_token = access_token or getattr(settings, "MAPBOX_TOKEN", "")
        self.countries = getattr(settings, "GEOCODE_COUNTRIES", "us,ca")
        self.timeout = timeout

    def geocode(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        query = query.strip()
        if len(query) < 3:
            return []

        if not self.access_token:
            return self._fallback_geocode(query, limit)

        url = "https://api.mapbox.com/search/geocode/v6/forward"
        params = {
            "q": query,
            "autocomplete": "true",
            "limit": str(limit),
            "country": self.countries,
            "access_token": self.access_token,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    return self.parse_response(resp.json())
                if resp.status_code in (401, 403):
                    logger.warning("Mapbox Geocoding unauthorized; using keyless fallback.")
                    return self._fallback_geocode(query, limit)
        except Exception as err:
            logger.warning("Mapbox Geocoding failed (%s); using keyless fallback.", err)

        return self._fallback_geocode(query, limit)

    @classmethod
    def parse_response(cls, data: dict[str, Any]) -> list[GeocodeResult]:
        features = data.get("features", [])
        results: list[GeocodeResult] = []

        for f in features:
            props = f.get("properties", {})
            label = props.get("full_address") or props.get("name") or ""
            geom = f.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) >= 2 and label:
                # GeoJSON coordinates order: [lon, lat]
                results.append(
                    GeocodeResult(label=label, lat=float(coords[1]), lon=float(coords[0]))
                )

        return results

    def _fallback_geocode(self, query: str, limit: int) -> list[GeocodeResult]:
        """Keyless fallback using Photon (OSM-based geocoder)."""
        # Keep the local demo usable when both the server-side Mapbox token and
        # outbound geocoding access are unavailable. These are deterministic
        # city-centre coordinates, not route or weather data.
        demo_places = {
            "dallas": GeocodeResult("Dallas, TX, United States", 32.7767, -96.7970),
            "houston": GeocodeResult("Houston, TX, United States", 29.7604, -95.3698),
            "denver": GeocodeResult("Denver, CO, United States", 39.7392, -104.9903),
            "austin": GeocodeResult("Austin, TX, United States", 30.2672, -97.7431),
            "chicago": GeocodeResult("Chicago, IL, United States", 41.8781, -87.6298),
        }
        local = demo_places.get(query.casefold())
        if local is not None:
            return [local]

        url = "https://photon.komoot.io/api/"
        params = {"q": query, "limit": str(limit)}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    results: list[GeocodeResult] = []
                    for f in data.get("features", []):
                        props = f.get("properties", {})
                        name = props.get("name", "")
                        state = props.get("state", "")
                        country = props.get("country", "")
                        parts = [p for p in [name, state, country] if p]
                        label = ", ".join(parts)
                        geom = f.get("geometry", {})
                        coords = geom.get("coordinates", [])
                        if len(coords) >= 2 and label:
                            results.append(
                                GeocodeResult(
                                    label=label,
                                    lat=float(coords[1]),
                                    lon=float(coords[0]),
                                )
                            )
                    return results
        except Exception as err:
            logger.warning("Fallback geocoding failed: %s", err)

        return []
