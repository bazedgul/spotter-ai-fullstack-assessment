"""Open-Meteo Forecast API adapter with caching, unit assertions, and chunking."""

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from django.core.cache import cache

from trucksafe.adapters.weather.base import WeatherSeries

logger = logging.getLogger(__name__)


class WeatherAdapterError(Exception):
    """Base exception for weather provider errors."""


class WeatherUnitError(WeatherAdapterError):
    """Raised when Open-Meteo returns units different from requested (A3)."""


class WeatherUnavailable(WeatherAdapterError):
    """Raised when Open-Meteo is unreachable after retries (502)."""


def snap_to_cell(lat: float, lon: float) -> tuple[float, float]:
    """Snap latitude and longitude to 0.05 degree grid center."""
    return round(lat / 0.05) * 0.05, round(lon / 0.05) * 0.05


class OpenMeteoWeatherProvider:
    """Weather provider for Open-Meteo batch hourly forecast."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    MAX_BACKOFF_SECONDS = 30.0

    def __init__(
        self,
        timeout: float = 10.0,
        cache_ttl_s: int = 1800,
        max_retries: int = 2,
    ) -> None:
        self.timeout = timeout
        self.cache_ttl_s = cache_ttl_s
        self.max_retries = max_retries

    def fetch(
        self,
        cells: list[tuple[float, float]],
        start_utc: datetime,
        n_hours: int,
    ) -> dict[tuple[float, float], WeatherSeries]:
        """Fetch weather series for the given cells, utilizing Django cache."""
        if not cells:
            return {}

        start_utc = start_utc.astimezone(UTC)
        start_date = start_utc.date()
        # End date covers start_utc + n_hours
        end_dt = start_utc + timedelta(hours=n_hours)
        end_date = end_dt.date()

        unique_cells = sorted(list(set(cells)))
        results: dict[tuple[float, float], WeatherSeries] = {}
        missing_cells: list[tuple[float, float]] = []

        # 1. Check Cache
        for c in unique_cells:
            cache_key = f"weather:{c[0]:.2f}:{c[1]:.2f}:{start_date}:{end_date}"
            cached_val = cache.get(cache_key)
            if cached_val is not None and isinstance(cached_val, WeatherSeries):
                results[c] = cached_val
            else:
                missing_cells.append(c)

        if not missing_cells:
            return results

        # 2. Chunk missing cells into batches <= 100
        chunk_size = 100
        chunks = [
            missing_cells[i : i + chunk_size] for i in range(0, len(missing_cells), chunk_size)
        ]

        def fetch_chunk(
            cell_chunk: list[tuple[float, float]],
        ) -> dict[tuple[float, float], WeatherSeries]:
            return self._query_open_meteo(cell_chunk, start_date, end_date)

        max_workers = min(6, len(chunks))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunk_results = list(executor.map(fetch_chunk, chunks))

        for batch_dict in chunk_results:
            for cell_coord, series in batch_dict.items():
                results[cell_coord] = series
                cache_key = (
                    f"weather:{cell_coord[0]:.2f}:{cell_coord[1]:.2f}:{start_date}:{end_date}"
                )
                cache.set(cache_key, series, timeout=self.cache_ttl_s)

        return results

    def _query_open_meteo(
        self,
        cells: list[tuple[float, float]],
        start_date: date,
        end_date: date,
    ) -> dict[tuple[float, float], WeatherSeries]:
        lats = ",".join(f"{c[0]:.4f}" for c in cells)
        lons = ",".join(f"{c[1]:.4f}" for c in cells)

        params = {
            "latitude": lats,
            "longitude": lons,
            "hourly": "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        last_err: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(self.BASE_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        return self.parse_response(data, cells)
                    if resp.status_code in (429, 500, 502, 503, 504):
                        last_err = f"HTTP {resp.status_code} ({resp.reason_phrase})"
                        if attempt < self.max_retries:
                            delay = self._retry_delay(resp, attempt)
                            time.sleep(delay)
                        continue
                    raise WeatherAdapterError(
                        f"Open-Meteo returned status {resp.status_code}: {resp.text}"
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as err:
                last_err = f"{type(err).__name__}: {err}"
                if attempt < self.max_retries:
                    time.sleep(self._retry_delay(None, attempt))

        raise WeatherUnavailable(f"Open-Meteo unreachable after retries: {last_err}")

    @classmethod
    def _retry_delay(cls, response: httpx.Response | None, attempt: int) -> float:
        """Return a bounded Retry-After delay or jittered exponential backoff."""
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(cls.MAX_BACKOFF_SECONDS, max(0.0, float(retry_after)))
                except ValueError:
                    try:
                        retry_at = parsedate_to_datetime(retry_after)
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=UTC)
                        seconds = (retry_at - datetime.now(UTC)).total_seconds()
                        return min(cls.MAX_BACKOFF_SECONDS, max(0.0, seconds))
                    except (TypeError, ValueError, OverflowError):
                        pass

        base = min(cls.MAX_BACKOFF_SECONDS, 0.5 * (2**attempt))
        return min(cls.MAX_BACKOFF_SECONDS, base + random.uniform(0.0, 0.25))

    @classmethod
    def parse_response(
        cls,
        data: Any,
        cells: list[tuple[float, float]],
    ) -> dict[tuple[float, float], WeatherSeries]:
        """Parse Open-Meteo JSON payload (single object or list of objects)."""
        raw_items: list[dict[str, Any]]
        if isinstance(data, list):
            raw_items = data
        elif isinstance(data, dict):
            raw_items = [data]
        else:
            raise WeatherAdapterError(f"Unexpected Open-Meteo response type: {type(data)}")

        results: dict[tuple[float, float], WeatherSeries] = {}

        for item, requested_cell in zip(raw_items, cells):
            # Assert hourly units
            units = item.get("hourly_units", {})
            wind_unit = units.get("wind_speed_10m")
            rain_unit = units.get("rain")
            showers_unit = units.get("showers")
            snow_unit = units.get("snowfall")

            # Open-Meteo returns 'mp/h' for mph unit
            if wind_unit not in ("mp/h", "mph"):
                raise WeatherUnitError(f"Unexpected wind unit: {wind_unit}")
            if rain_unit != "inch" or showers_unit != "inch" or snow_unit != "inch":
                raise WeatherUnitError(
                    f"Unexpected precipitation units: rain={rain_unit}, snow={snow_unit}"
                )

            hourly = item.get("hourly", {})
            time_strs: list[str] = hourly.get("time", [])
            winds: list[float | None] = hourly.get("wind_speed_10m", [])
            gusts: list[float | None] = hourly.get("wind_gusts_10m", [])
            rains: list[float | None] = hourly.get("rain", [])
            showers: list[float | None] = hourly.get("showers", [])
            snows: list[float | None] = hourly.get("snowfall", [])

            hours_utc: list[datetime] = []
            combined_rain: list[float | None] = []
            last_valid_hour: datetime | None = None

            for i, t_str in enumerate(time_strs):
                dt = datetime.fromisoformat(t_str).replace(tzinfo=UTC)
                hours_utc.append(dt)

                r_val = rains[i] if i < len(rains) else None
                sh_val = showers[i] if i < len(showers) else None
                if r_val is None and sh_val is None:
                    comb_r = None
                else:
                    comb_r = (r_val or 0.0) + (sh_val or 0.0)
                combined_rain.append(comb_r)

                w_val = winds[i] if i < len(winds) else None
                s_val = snows[i] if i < len(snows) else None

                # Check if all required variables are non-null
                if w_val is not None and comb_r is not None and s_val is not None:
                    last_valid_hour = dt

            series = WeatherSeries(
                cell=requested_cell,
                start_utc=hours_utc[0] if hours_utc else datetime.now(UTC),
                hours_utc=hours_utc,
                wind_mph=winds,
                gust_mph=gusts,
                rain_in_hr=combined_rain,
                snow_in_hr=snows,
                last_valid_hour=last_valid_hour,
            )
            results[requested_cell] = series

        return results
