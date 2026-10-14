"""Weather provider interface, series dataclass, and linear interpolation at ETA."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from trucksafe.domain.models import WeatherSample


@dataclass(frozen=True)
class WeatherSeries:
    """Hourly weather series at a discrete grid cell."""

    cell: tuple[float, float]
    start_utc: datetime
    hours_utc: list[datetime]
    wind_mph: list[float | None]
    gust_mph: list[float | None]
    rain_in_hr: list[float | None]
    snow_in_hr: list[float | None]
    last_valid_hour: datetime | None


class WeatherProvider(Protocol):
    """Protocol for fetching batched weather forecast series."""

    def fetch(
        self,
        cells: list[tuple[float, float]],
        start_utc: datetime,
        n_hours: int,
    ) -> dict[tuple[float, float], WeatherSeries]:
        """Fetch or retrieve cached forecast series for cells."""
        ...


def interpolate_at(series: WeatherSeries, target_utc: datetime) -> WeatherSample:
    """Linearly interpolate weather conditions at target_utc (A11).

    If target_utc is outside the series horizon, returns out_of_horizon status.
    If either bracketing hourly value is missing, returns None for that variable.
    """
    if target_utc.tzinfo is None:
        target_utc = target_utc.replace(tzinfo=UTC)

    if not series.hours_utc:
        return WeatherSample(
            wind_mph=None,
            gust_mph=None,
            rain_in_hr=None,
            snow_in_hr=None,
            status="out_of_horizon",
        )

    start = series.hours_utc[0]
    end = series.hours_utc[-1]

    if target_utc < start or target_utc > end:
        return WeatherSample(
            wind_mph=None,
            gust_mph=None,
            rain_in_hr=None,
            snow_in_hr=None,
            status="out_of_horizon",
        )

    delta_sec = (target_utc - start).total_seconds()
    h_idx_float = delta_sec / 3600.0
    h0 = int(math.floor(h_idx_float))
    h1 = int(math.ceil(h_idx_float))

    if h0 == h1:
        w = series.wind_mph[h0]
        g = series.gust_mph[h0]
        r = series.rain_in_hr[h0]
        s = series.snow_in_hr[h0]
        status: Literal["available", "missing"] = (
            "available" if (w is not None and r is not None and s is not None) else "missing"
        )
        return WeatherSample(wind_mph=w, gust_mph=g, rain_in_hr=r, snow_in_hr=s, status=status)

    fraction = h_idx_float - h0

    def lerp(vals: list[float | None]) -> float | None:
        v0 = vals[h0]
        v1 = vals[h1]
        if v0 is None or v1 is None:
            return None
        return v0 + fraction * (v1 - v0)

    w_val = lerp(series.wind_mph)
    g_val = lerp(series.gust_mph)
    r_val = lerp(series.rain_in_hr)
    s_val = lerp(series.snow_in_hr)

    interpolated_status: Literal["available", "missing"] = (
        "available"
        if (w_val is not None and r_val is not None and s_val is not None)
        else "missing"
    )

    return WeatherSample(
        wind_mph=w_val,
        gust_mph=g_val,
        rain_in_hr=r_val,
        snow_in_hr=s_val,
        status=interpolated_status,
    )
