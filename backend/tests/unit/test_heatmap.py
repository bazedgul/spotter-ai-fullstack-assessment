from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import polyline

from trucksafe.adapters.weather.base import WeatherSeries
from trucksafe.services.heatmap import build_heatmap


def test_heatmap_returns_49_preloaded_hours() -> None:
    start = datetime(2026, 10, 14, tzinfo=UTC)
    coords = [(32.78, -96.80), (33.0, -96.6)]
    hours = [start + timedelta(hours=i) for i in range(49)]
    series = WeatherSeries(
        (32.8, -96.8), start, hours, [20.0] * 49, [30.0] * 49, [0.1] * 49, [0.0] * 49, hours[-1]
    )
    with patch(
        "trucksafe.services.heatmap.OpenMeteoWeatherProvider.fetch",
        return_value={(32.8, -96.8): series},
    ):
        result = build_heatmap(
            {
                "routes": [{"polyline": polyline.encode(coords, precision=6)}],
                "departure_utc": "2026-10-14T00:00:00Z",
                "load_weight_lb": 42000,
            }
        )
    assert result["hours"] == 49
    assert len(result["features"]) == 2
    assert set(result["features"][0]["properties"]) >= {
        "h0",
        "h48",
        "wind_h0",
        "rain_h0",
        "snow_h0",
    }


def test_heatmap_accepts_serializer_datetime() -> None:
    """DRF DateTimeField passes a datetime, not the original request string."""
    start = datetime(2026, 10, 15, tzinfo=UTC)
    coords = [(32.78, -96.80), (33.0, -96.6)]
    hours = [start + timedelta(hours=i) for i in range(49)]
    series = WeatherSeries(
        (32.8, -96.8), start, hours, [20.0] * 49, [30.0] * 49, [0.1] * 49, [0.0] * 49, hours[-1]
    )
    with patch(
        "trucksafe.services.heatmap.OpenMeteoWeatherProvider.fetch",
        return_value={(32.8, -96.8): series},
    ):
        result = build_heatmap(
            {
                "routes": [{"polyline": polyline.encode(coords, precision=6)}],
                "departure_utc": start,
                "load_weight_lb": 45000,
            }
        )
    assert result["hours"] == 49
    assert result["features"]
