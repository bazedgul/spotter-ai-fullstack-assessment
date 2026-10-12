"""Tests for Mapbox and OSRM routing adapters using recorded fixtures."""

import json
from pathlib import Path

from trucksafe.adapters.routing.fallback import FallbackRoutingProvider
from trucksafe.adapters.routing.mapbox import MapboxRoutingProvider, MapboxRoutingUnavailable
from trucksafe.adapters.routing.osrm import OSRMRoutingProvider
from trucksafe.domain.models import LatLon

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_mapbox_parse_recorded_fixture() -> None:
    fixture_path = FIXTURES_DIR / "mapbox_directions.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    routes = MapboxRoutingProvider.parse_response(data)
    assert len(routes) == 1
    r = routes[0]
    assert len(r.coords) == 5
    assert r.summary == "I-35 N, US-287 N"
    assert r.distance_m == 1050000.0
    assert r.duration_s == 38200.5
    assert r.seg_durations_s is not None
    assert len(r.seg_durations_s) == len(r.coords) - 1


def test_mapbox_annotation_mismatch_fallback() -> None:
    fixture_path = FIXTURES_DIR / "mapbox_directions.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    # Corrupt duration annotation length
    data["routes"][0]["legs"][0]["annotation"]["duration"] = [100.0]  # Only 1 item instead of 4

    routes = MapboxRoutingProvider.parse_response(data)
    assert len(routes) == 1
    # When mismatch occurs, seg_durations_s falls back to None so caller distributes by distance
    assert routes[0].seg_durations_s is None


def test_osrm_parse_recorded_fixture() -> None:
    fixture_path = FIXTURES_DIR / "osrm_directions.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    routes = OSRMRoutingProvider.parse_response(data)
    assert len(routes) >= 1
    r = routes[0]
    assert len(r.coords) > 100
    assert r.distance_m > 0
    assert r.duration_s > 0
    assert r.seg_durations_s is not None
    assert len(r.seg_durations_s) == len(r.coords) - 1


def test_fallback_routing_provider_on_mapbox_failure() -> None:
    class FailingMapbox:
        access_token = "valid-token"

        def get_routes(self, *args, **kwargs):
            raise MapboxRoutingUnavailable("Mapbox 502")

    fixture_path = FIXTURES_DIR / "osrm_directions.json"
    with open(fixture_path, encoding="utf-8") as f:
        osrm_data = json.load(f)

    class WorkingOSRM:
        def get_routes(self, *args, **kwargs):
            return OSRMRoutingProvider.parse_response(osrm_data)

    fallback = FallbackRoutingProvider(
        primary=FailingMapbox(),
        secondary=WorkingOSRM(),  # type: ignore[arg-type]
    )
    routes = fallback.get_routes(LatLon(40.7, -74.0), LatLon(39.9, -75.1))
    assert len(routes) >= 1
    assert "used fallback" in (fallback.last_warning or "")
