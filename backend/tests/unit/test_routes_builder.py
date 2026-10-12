"""Dedicated tests for routes_builder via-waypoint augmentation (Section 9.4)."""

import pytest

from trucksafe.adapters.routing.base import RawRoute
from trucksafe.domain.geo import overlap_fraction
from trucksafe.domain.models import LatLon
from trucksafe.services.routes_builder import (
    RoutesBuilder,
    RouteTooLongError,
    RouteValidationError,
)


def make_raw_route(coords: list[LatLon], duration_s: float = 3600.0) -> RawRoute:
    seg_dur = [duration_s / (len(coords) - 1)] * (len(coords) - 1)
    seg_dist = [1000.0] * (len(coords) - 1)
    return RawRoute(
        coords=coords,
        distance_m=1000.0 * (len(coords) - 1),
        duration_s=duration_s,
        seg_durations_s=seg_dur,
        seg_distances_m=seg_dist,
        summary="Test Route",
    )


def test_builder_single_route_via_augment() -> None:
    origin = LatLon(32.78, -96.80)
    dest = LatLon(39.74, -104.99)

    class MockProviderSingle:
        calls = 0

        def get_routes(
            self, o: LatLon, d: LatLon, waypoints: list[LatLon] | None = None
        ) -> list[RawRoute]:
            self.calls += 1
            if not waypoints:
                # Base direct route
                coords = [LatLon(32.78 + i * 0.35, -96.80 - i * 0.4) for i in range(21)]
                return [make_raw_route(coords, duration_s=10000.0)]
            else:
                # Via detour route passing through the waypoint
                via = waypoints[0]
                leg1 = [
                    LatLon(
                        o.lat + (via.lat - o.lat) * i / 10.0, o.lon + (via.lon - o.lon) * i / 10.0
                    )
                    for i in range(10)
                ]
                leg2 = [
                    LatLon(
                        via.lat + (d.lat - via.lat) * j / 10.0,
                        via.lon + (d.lon - via.lon) * j / 10.0,
                    )
                    for j in range(11)
                ]
                return [make_raw_route(leg1 + leg2, duration_s=12000.0)]

    provider = MockProviderSingle()
    builder = RoutesBuilder(provider)  # type: ignore[arg-type]
    result = builder.build_routes(origin, dest)

    assert len(result.routes) == 3
    assert builder.total_provider_calls <= 7
    # Pairwise overlap < 0.90
    for i in range(len(result.routes)):
        for j in range(i + 1, len(result.routes)):
            overlap = overlap_fraction(result.routes[i].coords, result.routes[j].coords)
            assert overlap < 0.90


def test_builder_duplicate_routes_replaced() -> None:
    origin = LatLon(32.78, -96.80)
    dest = LatLon(39.74, -104.99)

    class MockProviderDuplicates:
        calls = 0

        def get_routes(
            self, o: LatLon, d: LatLon, waypoints: list[LatLon] | None = None
        ) -> list[RawRoute]:
            self.calls += 1
            if not waypoints:
                base_coords = [LatLon(32.78 + i * 0.35, -96.80 - i * 0.4) for i in range(21)]
                # Return 3 routes where 2 are duplicates
                r1 = make_raw_route(base_coords, 10000.0)
                r2 = make_raw_route(list(base_coords), 10000.0)  # duplicate of r1
                return [r1, r2]
            else:
                via = waypoints[0]
                leg1 = [
                    LatLon(
                        o.lat + (via.lat - o.lat) * i / 10.0, o.lon + (via.lon - o.lon) * i / 10.0
                    )
                    for i in range(10)
                ]
                leg2 = [
                    LatLon(
                        via.lat + (d.lat - via.lat) * j / 10.0,
                        via.lon + (d.lon - via.lon) * j / 10.0,
                    )
                    for j in range(11)
                ]
                return [make_raw_route(leg1 + leg2, duration_s=11500.0)]

    provider = MockProviderDuplicates()
    builder = RoutesBuilder(provider)  # type: ignore[arg-type]
    result = builder.build_routes(origin, dest)

    assert len(result.routes) == 3
    assert builder.total_provider_calls <= 7


def test_builder_via_all_rejected_returns_real_count() -> None:
    origin = LatLon(32.78, -96.80)
    dest = LatLon(39.74, -104.99)

    class MockProviderFailingVia:
        def get_routes(
            self, o: LatLon, d: LatLon, waypoints: list[LatLon] | None = None
        ) -> list[RawRoute]:
            if not waypoints:
                coords = [LatLon(32.78 + i * 0.35, -96.80 - i * 0.4) for i in range(21)]
                return [make_raw_route(coords, 10000.0)]
            # All via calls fail / return empty
            return []

    builder = RoutesBuilder(MockProviderFailingVia())  # type: ignore[arg-type]
    result = builder.build_routes(origin, dest)

    assert len(result.routes) == 1
    assert any("Only 1 distinct routes available" in w for w in result.warnings)
    assert builder.total_provider_calls <= 7


def test_builder_validations() -> None:
    provider = RoutesBuilder(None)  # type: ignore[arg-type]

    # Origin ≈ Dest (< 0.5 miles)
    with pytest.raises(RouteValidationError):
        provider.build_routes(LatLon(30.0, -90.0), LatLon(30.001, -90.001))

    # Route > 4000 miles
    class VeryLongRouteProvider:
        def get_routes(self, *args, **kwargs):
            coords = [LatLon(0.0, 0.0), LatLon(80.0, 80.0)]
            return [
                RawRoute(
                    coords,
                    distance_m=8000000.0,
                    duration_s=300000.0,
                    seg_durations_s=None,
                    seg_distances_m=None,
                    summary="",
                )
            ]

    builder_long = RoutesBuilder(VeryLongRouteProvider())  # type: ignore[arg-type]
    with pytest.raises(RouteTooLongError):
        builder_long.build_routes(LatLon(0.0, 0.0), LatLon(80.0, 80.0))
