"""Tests for Open-Meteo weather adapter, unit checks, and interpolation."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from trucksafe.adapters.weather.base import WeatherSeries, interpolate_at
from trucksafe.adapters.weather.open_meteo import (
    OpenMeteoWeatherProvider,
    WeatherUnavailable,
    WeatherUnitError,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_open_meteo_single_location_fixture() -> None:
    fixture_path = FIXTURES_DIR / "open_meteo_single.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    cell = (32.80, -96.80)
    series_map = OpenMeteoWeatherProvider.parse_response(data, [cell])
    assert cell in series_map
    series = series_map[cell]
    assert len(series.hours_utc) > 24
    assert len(series.wind_mph) == len(series.hours_utc)
    assert len(series.rain_in_hr) == len(series.hours_utc)
    assert series.last_valid_hour is not None


def test_open_meteo_multi_location_fixture() -> None:
    fixture_path = FIXTURES_DIR / "open_meteo_multi.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    cells = [(32.80, -96.80), (39.75, -105.00)]
    series_map = OpenMeteoWeatherProvider.parse_response(data, cells)
    assert len(series_map) == 2
    assert cells[0] in series_map
    assert cells[1] in series_map


def test_open_meteo_unit_assertion_failure() -> None:
    fixture_path = FIXTURES_DIR / "open_meteo_single.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    # Corrupt units to km/h
    data["hourly_units"]["wind_speed_10m"] = "km/h"
    with pytest.raises(WeatherUnitError, match="Unexpected wind unit"):
        OpenMeteoWeatherProvider.parse_response(data, [(32.80, -96.80)])


def test_interpolation_logic_a11() -> None:
    t0 = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)
    t2 = datetime(2026, 10, 14, 14, 0, tzinfo=UTC)

    series = WeatherSeries(
        cell=(30.0, -90.0),
        start_utc=t0,
        hours_utc=[t0, t1, t2],
        wind_mph=[10.0, 20.0, 30.0],
        gust_mph=[15.0, 25.0, 35.0],
        rain_in_hr=[0.0, 0.4, 0.8],
        snow_in_hr=[0.0, 0.0, 0.0],
        last_valid_hour=t2,
    )

    # Exact hour t0
    s_exact = interpolate_at(series, t0)
    assert s_exact.wind_mph == 10.0
    assert s_exact.status == "available"

    # Midpoint between t0 (12:00) and t1 (13:00) -> 12:30
    t_mid = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
    s_mid = interpolate_at(series, t_mid)
    assert s_mid.wind_mph == pytest.approx(15.0)
    assert s_mid.rain_in_hr == pytest.approx(0.2)
    assert s_mid.status == "available"

    # None bracket yields None
    series_missing = WeatherSeries(
        cell=(30.0, -90.0),
        start_utc=t0,
        hours_utc=[t0, t1, t2],
        wind_mph=[10.0, None, 30.0],
        gust_mph=[15.0, None, 35.0],
        rain_in_hr=[0.0, 0.4, 0.8],
        snow_in_hr=[0.0, 0.0, 0.0],
        last_valid_hour=t2,
    )
    s_bracket = interpolate_at(series_missing, t_mid)
    assert s_bracket.wind_mph is None
    assert s_bracket.status == "missing"

    # Out of horizon before or after series -> out_of_horizon, never extrapolate
    t_before = datetime(2026, 10, 14, 11, 0, tzinfo=UTC)
    t_after = datetime(2026, 10, 14, 16, 0, tzinfo=UTC)
    assert interpolate_at(series, t_before).status == "out_of_horizon"
    assert interpolate_at(series, t_after).status == "out_of_horizon"
    assert interpolate_at(series, t_after).wind_mph is None


def _fixture_response() -> httpx.Response:
    with open(FIXTURES_DIR / "open_meteo_single.json", encoding="utf-8") as f:
        return httpx.Response(200, json=json.load(f))


def test_open_meteo_429_retry_after_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [httpx.Response(429, headers={"Retry-After": "7"})] * 3
    sleeps: list[float] = []
    monkeypatch.setattr(httpx.Client, "get", lambda _client, *_args, **_kwargs: responses.pop(0))
    monkeypatch.setattr("trucksafe.adapters.weather.open_meteo.time.sleep", sleeps.append)

    with pytest.raises(WeatherUnavailable, match="HTTP 429"):
        OpenMeteoWeatherProvider()._query_open_meteo(
            [(32.8, -96.8)], date(2026, 10, 15), date(2026, 10, 16)
        )
    assert sleeps == [7.0, 7.0]


def test_open_meteo_429_retry_after_http_date(monkeypatch: pytest.MonkeyPatch) -> None:
    retry_at = (datetime.now(UTC) + timedelta(seconds=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    response = httpx.Response(429, headers={"Retry-After": retry_at})
    monkeypatch.setattr(httpx.Client, "get", lambda _client, *_args, **_kwargs: response)
    sleeps: list[float] = []
    monkeypatch.setattr("trucksafe.adapters.weather.open_meteo.time.sleep", sleeps.append)

    with pytest.raises(WeatherUnavailable, match="HTTP 429"):
        OpenMeteoWeatherProvider()._query_open_meteo(
            [(32.8, -96.8)], date(2026, 10, 15), date(2026, 10, 16)
        )
    assert len(sleeps) == 2
    assert all(0 <= delay <= 30 for delay in sleeps)


def test_open_meteo_429_without_retry_after_uses_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(429)
    monkeypatch.setattr(httpx.Client, "get", lambda _client, *_args, **_kwargs: response)
    monkeypatch.setattr("trucksafe.adapters.weather.open_meteo.random.uniform", lambda _a, _b: 0.0)
    sleeps: list[float] = []
    monkeypatch.setattr("trucksafe.adapters.weather.open_meteo.time.sleep", sleeps.append)

    with pytest.raises(WeatherUnavailable, match="HTTP 429"):
        OpenMeteoWeatherProvider()._query_open_meteo(
            [(32.8, -96.8)], date(2026, 10, 15), date(2026, 10, 16)
        )
    assert sleeps == [0.5, 1.0]


def test_open_meteo_transient_429_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [httpx.Response(429), _fixture_response()]
    monkeypatch.setattr(httpx.Client, "get", lambda _client, *_args, **_kwargs: responses.pop(0))
    monkeypatch.setattr("trucksafe.adapters.weather.open_meteo.time.sleep", lambda _seconds: None)

    result = OpenMeteoWeatherProvider()._query_open_meteo(
        [(32.8, -96.8)], date(2026, 10, 15), date(2026, 10, 16)
    )
    assert (32.8, -96.8) in result


def test_open_meteo_timeout_retries_and_preserves_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(_client: httpx.Client, *_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout")

    monkeypatch.setattr(httpx.Client, "get", timeout)
    monkeypatch.setattr("trucksafe.adapters.weather.open_meteo.time.sleep", lambda _seconds: None)

    with pytest.raises(WeatherUnavailable, match="ReadTimeout: upstream timeout"):
        OpenMeteoWeatherProvider()._query_open_meteo(
            [(32.8, -96.8)], date(2026, 10, 15), date(2026, 10, 16)
        )
