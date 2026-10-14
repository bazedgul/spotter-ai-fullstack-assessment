"""Build the compact 49-hour corridor payload used by the map heat layer."""

from datetime import UTC, datetime, timedelta
from typing import Any

import polyline

from trucksafe.adapters.weather.base import interpolate_at
from trucksafe.adapters.weather.open_meteo import OpenMeteoWeatherProvider, snap_to_cell
from trucksafe.domain.models import LatLon, WeatherSample
from trucksafe.domain.risk import assess_checkpoint


def build_heatmap(payload: dict[str, Any]) -> dict[str, Any]:
    points: list[LatLon] = []
    for route in payload.get("routes", []):
        decoded = polyline.decode(route["polyline"], precision=6)
        stride = max(1, len(decoded) // 300)
        points.extend(LatLon(lat, lon) for lat, lon in decoded[::stride])
    unique: dict[tuple[float, float], LatLon] = {snap_to_cell(p.lat, p.lon): p for p in points}
    cells = list(unique)
    departure_value = payload["departure_utc"]
    if isinstance(departure_value, datetime):
        departure = departure_value
    else:
        departure = datetime.fromisoformat(str(departure_value).replace("Z", "+00:00"))
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=UTC)
    provider = OpenMeteoWeatherProvider()
    series = provider.fetch(cells, departure.replace(minute=0, second=0, microsecond=0), 49)
    load = float(payload["load_weight_lb"])
    output: list[dict[str, Any]] = []
    for cell, point in unique.items():
        weather = series.get(cell)
        values: dict[str, list[float]] = {f"h{i}": [] for i in range(49)}
        wind_values: dict[str, float] = {}
        rain_values: dict[str, float] = {}
        snow_values: dict[str, float] = {}
        for hour in range(49):
            sample = (
                interpolate_at(weather, departure + timedelta(hours=hour))
                if weather
                else WeatherSample(None, None, None, None, "missing")
            )
            assessment = assess_checkpoint(sample, load)
            values[f"h{hour}"].append(-1 if assessment.level is None else int(assessment.level))
            wind_values[f"h{hour}"] = sample.wind_mph if sample.wind_mph is not None else -1
            rain_values[f"h{hour}"] = sample.rain_in_hr if sample.rain_in_hr is not None else -1
            snow_values[f"h{hour}"] = sample.snow_in_hr if sample.snow_in_hr is not None else -1
        output.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [point.lon, point.lat]},
                "properties": {
                    **{key: vals[0] for key, vals in values.items()},
                    **{f"wind_{key}": value for key, value in wind_values.items()},
                    **{f"rain_{key}": value for key, value in rain_values.items()},
                    **{f"snow_{key}": value for key, value in snow_values.items()},
                },
            }
        )
    return {"hours": 49, "features": output, "warnings": []}
