"""Tests for timezone resolution and localization."""

from datetime import datetime

from trucksafe.services.timezones import format_local_iso, localize_to_utc, tz_at


def test_timezone_finder_dallas_and_denver() -> None:
    # Dallas, TX is in America/Chicago
    tz_dallas, approx_dallas = tz_at(32.78, -96.80)
    assert not approx_dallas
    assert str(tz_dallas) == "America/Chicago"

    # Denver, CO is in America/Denver
    tz_denver, approx_denver = tz_at(39.74, -104.99)
    assert not approx_denver
    assert str(tz_denver) == "America/Denver"


def test_localize_to_utc() -> None:
    tz_chicago, _ = tz_at(32.78, -96.80)
    # 2026-10-14 08:00 CDT is UTC-5 -> 13:00 UTC
    naive_dt = datetime(2026, 10, 14, 8, 0)
    utc_dt = localize_to_utc(naive_dt, tz_chicago)

    assert utc_dt.year == 2026
    assert utc_dt.month == 10
    assert utc_dt.day == 14
    assert utc_dt.hour == 13
    assert utc_dt.minute == 0


def test_format_local_iso() -> None:
    tz_chicago, _ = tz_at(32.78, -96.80)
    naive_dt = datetime(2026, 10, 14, 8, 0)
    utc_dt = localize_to_utc(naive_dt, tz_chicago)

    iso_str, tz_name = format_local_iso(utc_dt, tz_chicago)
    assert "2026-10-14T08:00:00" in iso_str
    assert tz_name == "America/Chicago"
