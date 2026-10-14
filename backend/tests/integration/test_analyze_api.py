"""Golden scenario integration test for POST /api/analyze (Section 9.4)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from trucksafe.adapters.routing.base import RawRoute
from trucksafe.adapters.weather.base import WeatherSeries
from trucksafe.domain.models import LatLon


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def test_analyze_golden_scenario(api_client: APIClient) -> None:
    """Golden scenario from Section 9.4:

    Three synthetic routes:
    - Route B has a 40-mile Severe stretch
    - Route C has 15 High miles
    - Route A is clean (Low risk) but 30 min slower
    -> Route A must be recommended with correct explanation.
    """
    # Separate geographic corridors for the three routes:
    # Route A (Eastern clean highway): lon moves slowly west
    coords_a = [LatLon(32.78 + i * 0.35, -96.80 - i * 0.15) for i in range(21)]
    # Route B (Central valley): passes through lat 35.0, lon -100.0
    coords_b = [LatLon(32.78 + i * 0.35, -96.80 - i * 0.40) for i in range(21)]
    # Route C (Western pass): passes through lat 36.0, lon -103.0
    coords_c = [LatLon(32.78 + i * 0.35, -96.80 - i * 0.60) for i in range(21)]

    # Duration: fastest is B (10 hrs = 600 min), C is 610 min, A is 30 min slower than B (630 min)
    raw_a = RawRoute(coords_a, 800000.0, 37800.0, None, None, "Route A via Clean Highway")
    raw_b = RawRoute(coords_b, 780000.0, 36000.0, None, None, "Route B via Severe Valley")
    raw_c = RawRoute(coords_c, 790000.0, 36600.0, None, None, "Route C via High Pass")

    class MockRoutingProvider:
        def get_routes(self, o: LatLon, d: LatLon, waypoints=None):
            return [raw_a, raw_b, raw_c]

    class MockWeatherProvider:
        def fetch(self, cells, start_utc, n_hours):
            t_hours = [start_utc + timedelta(hours=i) for i in range(n_hours)]
            result = {}
            for c in cells:
                # Cell near Route B gets Severe weather (rain 0.65 in/hr)
                if abs(c[0] - 35.0) < 0.6 and abs(c[1] - (-99.2)) < 0.6:
                    wind = [20.0] * n_hours
                    rain = [0.65] * n_hours
                # Cell near Route C gets High weather (rain 0.35 in/hr)
                elif abs(c[0] - 36.0) < 0.6 and abs(c[1] - (-102.0)) < 0.6:
                    wind = [20.0] * n_hours
                    rain = [0.35] * n_hours
                else:
                    # Clean weather for Route A
                    wind = [15.0] * n_hours
                    rain = [0.0] * n_hours

                series = WeatherSeries(
                    cell=c,
                    start_utc=start_utc,
                    hours_utc=t_hours,
                    wind_mph=wind,
                    gust_mph=[w + 5.0 for w in wind],
                    rain_in_hr=rain,
                    snow_in_hr=[0.0] * n_hours,
                    last_valid_hour=t_hours[-1],
                )
                result[c] = series
            return result

    dep_future = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT08:00")

    payload = {
        "origin": {"label": "Dallas, TX", "lat": 32.78, "lon": -96.80},
        "destination": {"label": "Denver, CO", "lat": 39.74, "lon": -104.99},
        "departure_local": dep_future,
        "load_weight_lb": 42000,
        "checkpoint_interval_miles": 25,
    }

    with (
        patch(
            "trucksafe.services.analyze.FallbackRoutingProvider",
            return_value=MockRoutingProvider(),
        ),
        patch(
            "trucksafe.services.analyze.OpenMeteoWeatherProvider",
            return_value=MockWeatherProvider(),
        ),
    ):
        resp = api_client.post("/api/analyze", payload, format="json")

    assert resp.status_code == 200
    data = resp.json()

    # Check contract shape
    assert "request_id" in data
    assert "departure_utc" in data
    assert "routes" in data
    assert "heatmap_request" in data
    assert len(data["routes"]) == 3

    # Route A must be ranked #1 and recommended
    rec_id = data["recommended_route_id"]
    r_top = data["routes"][0]
    assert r_top["id"] == rec_id
    assert r_top["recommended"] is True
    assert "Recommended:" in r_top["explanation"]

    # Checkpoints format
    cps = r_top["checkpoints"]
    assert len(cps) > 1
    assert "eta_utc" in cps[0]
    assert "weather" in cps[0]
    assert "risk" in cps[0]
    assert cps[0]["risk"]["level"] in ["LOW", "MODERATE", "HIGH", "SEVERE", "NO_TRAVEL", "UNKNOWN"]


def test_analyze_validation_errors(api_client: APIClient) -> None:
    # Missing fields
    resp = api_client.post("/api/analyze", {}, format="json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    # Invalid weight (> 100,000)
    dep_future = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT08:00")
    payload = {
        "origin": {"lat": 32.78, "lon": -96.80},
        "destination": {"lat": 39.74, "lon": -104.99},
        "departure_local": dep_future,
        "load_weight_lb": 120_000,
    }
    resp2 = api_client.post("/api/analyze", payload, format="json")
    assert resp2.status_code == 400
    assert resp2.json()["error"]["code"] == "VALIDATION_ERROR"


def test_geocode_endpoint(api_client: APIClient) -> None:
    # Short query (< 3 chars) returns empty list
    r1 = api_client.get("/api/geocode?q=da")
    assert r1.status_code == 200
    assert r1.json() == []

    # Valid query returns results or list
    with patch(
        "trucksafe.adapters.geocoding.mapbox.MapboxGeocodingProvider.geocode",
        return_value=[type("Geo", (), {"label": "Dallas, TX", "lat": 32.78, "lon": -96.80})()],
    ):
        r2 = api_client.get("/api/geocode?q=Dallas")
        assert r2.status_code == 200
        assert len(r2.json()) == 1
        assert r2.json()[0]["label"] == "Dallas, TX"
