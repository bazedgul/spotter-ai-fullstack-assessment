"""Weather risk classification and load rules engine."""

from enum import IntEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from trucksafe.domain.models import Assessment, WeatherSample


class Risk(IntEnum):
    """Ordered risk levels. UNKNOWN is represented as None in domain code."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


def classify_wind(mph: float) -> Risk:
    """Classify sustained wind speed in mph (lower-inclusive, half-open)."""
    if mph >= 55:
        return Risk.NO_TRAVEL
    if mph >= 45:
        return Risk.SEVERE
    if mph >= 35:
        return Risk.HIGH
    if mph >= 25:
        return Risk.MODERATE
    return Risk.LOW


def _lower_inclusive(v: float, mod_ge: float, high_ge: float, sev_ge: float, nt_gt: float) -> Risk:
    """Helper for lower-bound inclusive precipitation boundaries."""
    if v > nt_gt:
        return Risk.NO_TRAVEL
    if v >= sev_ge:
        return Risk.SEVERE
    if v >= high_ge:
        return Risk.HIGH
    if v >= mod_ge:
        return Risk.MODERATE
    return Risk.LOW


def classify_rain(in_hr: float) -> Risk:
    """Classify rainfall rate in inches per hour."""
    return _lower_inclusive(in_hr, 0.10, 0.25, 0.50, 1.00)


def classify_snow(in_hr: float) -> Risk:
    """Classify snowfall rate in inches per hour."""
    return _lower_inclusive(in_hr, 0.5, 1.0, 2.0, 3.0)


def apply_load_rules(wind_mph: float, load_lb: float, base: Risk) -> tuple[Risk, str | None]:
    """Apply vehicle gross load rules to escalate wind risk."""
    if wind_mph >= 55:
        return Risk.NO_TRAVEL, "Wind ≥55 mph: No Travel for any load"
    if 45 <= wind_mph < 55 and load_lb > 30_000:
        return Risk.NO_TRAVEL, "Wind 45–54 mph with load >30,000 lb: No Travel"
    if 35 <= wind_mph < 45 and load_lb > 40_000:
        return max(base, Risk.SEVERE), "Wind 35–44 mph with load >40,000 lb: Severe"
    return base, None


def assess_checkpoint(s: "WeatherSample", load_lb: float) -> "Assessment":
    """Compute overall checkpoint risk from weather conditions and vehicle load."""
    from trucksafe.domain.models import Assessment, Driver

    levels: list[Risk] = []
    drivers: list[Driver] = []
    missing = False

    if s.wind_mph is None:
        missing = True
    else:
        base = classify_wind(s.wind_mph)
        adjusted, note = apply_load_rules(s.wind_mph, load_lb, base)
        levels.append(adjusted)
        drivers.append(Driver("wind", base, f"{s.wind_mph:.0f} mph"))
        if note:
            drivers.append(Driver("load_rule", adjusted, note))

    precip_checks: list[tuple[Literal["rain", "snow"], float | None]] = [
        ("rain", s.rain_in_hr),
        ("snow", s.snow_in_hr),
    ]

    for name, value in precip_checks:
        if value is None:
            missing = True
            continue
        lvl = classify_rain(value) if name == "rain" else classify_snow(value)
        levels.append(lvl)
        drivers.append(Driver(name, lvl, f"{value:.2f} in/hr"))

    top = max(levels, default=None)
    if top == Risk.NO_TRAVEL:
        level: Risk | None = top
    elif missing:
        level = None
    else:
        level = top

    return Assessment(level, drivers)
