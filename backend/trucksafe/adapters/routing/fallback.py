"""Fallback routing provider wrapping primary (Mapbox) and secondary (OSRM)."""

import logging

from trucksafe.adapters.routing.base import RawRoute
from trucksafe.adapters.routing.mapbox import (
    MapboxAuthError,
    MapboxRoutingProvider,
    MapboxRoutingUnavailable,
)
from trucksafe.adapters.routing.osrm import OSRMRoutingProvider
from trucksafe.domain.models import LatLon

logger = logging.getLogger(__name__)


class FallbackRoutingProvider:
    """Delegates to Mapbox, falling back to OSRM on 5xx, timeouts, or missing token."""

    def __init__(
        self,
        primary: MapboxRoutingProvider | None = None,
        secondary: OSRMRoutingProvider | None = None,
    ) -> None:
        self.primary = primary or MapboxRoutingProvider()
        self.secondary = secondary or OSRMRoutingProvider()
        self.last_warning: str | None = None

    def get_routes(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon] | None = None,
    ) -> list[RawRoute]:
        self.last_warning = None

        if not self.primary.access_token:
            logger.info("Mapbox token not provided; using keyless OSRM provider.")
            self.last_warning = "Primary router unavailable; used fallback (car profile)."
            return self.secondary.get_routes(origin, dest, waypoints)

        try:
            return self.primary.get_routes(origin, dest, waypoints)
        except (MapboxRoutingUnavailable, MapboxAuthError) as err:
            logger.warning("Primary router failed (%s); using OSRM fallback.", err)
            self.last_warning = "Primary router unavailable; used fallback (car profile)."
            return self.secondary.get_routes(origin, dest, waypoints)
