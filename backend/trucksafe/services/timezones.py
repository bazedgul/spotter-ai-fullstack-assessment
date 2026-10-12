"""Timezone resolution using timezonefinder with fixed-offset fallback."""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

# Instantiate once at module import (A12 / Section 5.9)
try:
    from timezonefinder import TimezoneFinder

    _tf: TimezoneFinder | None = TimezoneFinder()
except Exception as exc:
    logger.warning("Could not initialize TimezoneFinder (%s); using fixed offsets.", exc)
    _tf = None


def tz_at(lat: float, lon: float) -> tuple[ZoneInfo, bool]:
    """Find the ZoneInfo for given coordinates.

    Returns (zone_info, is_approximated).
    If lookup fails or returns None, falls back to fixed offset
    timezone(timedelta(hours=round(lon/15))).
    """
    if _tf is not None:
        try:
            tz_name = _tf.timezone_at(lat=lat, lng=lon)
            if tz_name:
                return ZoneInfo(tz_name), False
        except (ZoneInfoNotFoundError, Exception) as err:
            logger.warning("Timezone lookup error at (%s, %s): %s", lat, lon, err)

    # Fallback to approximate fixed offset (no DST)
    hours_offset = int(round(lon / 15.0))
    approx_name = f"Etc/GMT{'-' if hours_offset >= 0 else '+'}{abs(hours_offset)}"
    try:
        return ZoneInfo(approx_name), True
    except Exception:
        # Final fallback using UTC
        return ZoneInfo("UTC"), True


def localize_to_utc(naive_dt: datetime, tz: ZoneInfo) -> datetime:
    """Localize naive datetime in origin's timezone and convert to UTC."""
    if naive_dt.tzinfo is not None:
        return naive_dt.astimezone(UTC)
    # fold=0 handles ambiguous DST transition per Section 8
    localized = naive_dt.replace(tzinfo=tz, fold=0)
    return localized.astimezone(UTC)


def format_local_iso(dt_utc: datetime, tz: ZoneInfo) -> tuple[str, str]:
    """Format UTC datetime into local ISO string and IANA timezone name."""
    local_dt = dt_utc.astimezone(tz)
    tz_name = getattr(tz, "key", str(tz))
    return local_dt.isoformat(), tz_name
