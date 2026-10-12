"""Parametrized boundary tests for risk engine conforming strictly to Section 9.1."""

import pytest

from trucksafe.domain.models import WeatherSample
from trucksafe.domain.risk import (
    Risk,
    apply_load_rules,
    assess_checkpoint,
    classify_rain,
    classify_snow,
    classify_wind,
)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (24.99, Risk.LOW),
        (25.0, Risk.MODERATE),
        (34.99, Risk.MODERATE),
        (35.0, Risk.HIGH),
        (44.99, Risk.HIGH),
        (45.0, Risk.SEVERE),
        (54.99, Risk.SEVERE),
        (55.0, Risk.NO_TRAVEL),
    ],
)
def test_wind_boundaries(mph: float, expected: Risk) -> None:
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    ("in_hr", "expected"),
    [
        (0.099, Risk.LOW),
        (0.10, Risk.MODERATE),
        (0.249, Risk.MODERATE),
        (0.25, Risk.HIGH),
        (0.499, Risk.HIGH),
        (0.50, Risk.SEVERE),
        (1.00, Risk.SEVERE),
        (1.001, Risk.NO_TRAVEL),
    ],
)
def test_rain_boundaries(in_hr: float, expected: Risk) -> None:
    assert classify_rain(in_hr) == expected


@pytest.mark.parametrize(
    ("in_hr", "expected"),
    [
        (0.499, Risk.LOW),
        (0.5, Risk.MODERATE),
        (0.999, Risk.MODERATE),
        (1.0, Risk.HIGH),
        (1.999, Risk.HIGH),
        (2.0, Risk.SEVERE),
        (3.0, Risk.SEVERE),
        (3.001, Risk.NO_TRAVEL),
    ],
)
def test_snow_boundaries(in_hr: float, expected: Risk) -> None:
    assert classify_snow(in_hr) == expected


@pytest.mark.parametrize(
    ("wind_mph", "load_lb", "expected"),
    [
        (40.0, 40_000.0, Risk.HIGH),
        (40.0, 40_001.0, Risk.SEVERE),
        (50.0, 30_000.0, Risk.SEVERE),
        (50.0, 30_001.0, Risk.NO_TRAVEL),
        (55.0, 1.0, Risk.NO_TRAVEL),
        (30.0, 90_000.0, Risk.MODERATE),
    ],
)
def test_load_rule_wind_escalation(wind_mph: float, load_lb: float, expected: Risk) -> None:
    base = classify_wind(wind_mph)
    adjusted, _ = apply_load_rules(wind_mph, load_lb, base)
    assert adjusted == expected


def test_combined_max_condition() -> None:
    # wind 40 (HIGH) + rain 0.6 (SEVERE), load 10,000 -> SEVERE
    sample = WeatherSample(wind_mph=40.0, gust_mph=45.0, rain_in_hr=0.6, snow_in_hr=0.0)
    assessment = assess_checkpoint(sample, load_lb=10_000)
    assert assessment.level == Risk.SEVERE


def test_rain_never_downgraded_by_load() -> None:
    # rain 0.25 (HIGH), load 90,000 -> HIGH (load rule never downgrades or alters rain)
    sample = WeatherSample(wind_mph=0.0, gust_mph=0.0, rain_in_hr=0.25, snow_in_hr=0.0)
    assessment = assess_checkpoint(sample, load_lb=90_000)
    assert assessment.level == Risk.HIGH


def test_missing_wind_yields_unknown() -> None:
    # wind None, rain 0, snow 0 -> UNKNOWN (None), never LOW
    sample = WeatherSample(wind_mph=None, gust_mph=None, rain_in_hr=0.0, snow_in_hr=0.0)
    assessment = assess_checkpoint(sample, load_lb=20_000)
    assert assessment.level is None


def test_known_veto_not_lowered_by_missing_data() -> None:
    # wind 60 (NO_TRAVEL), rain None, snow None -> NO_TRAVEL
    sample = WeatherSample(wind_mph=60.0, gust_mph=70.0, rain_in_hr=None, snow_in_hr=None)
    assessment = assess_checkpoint(sample, load_lb=20_000)
    assert assessment.level == Risk.NO_TRAVEL


def test_missing_input_without_veto_yields_unknown() -> None:
    # wind 20, rain 0.30, snow None -> UNKNOWN (missing input, no veto)
    sample = WeatherSample(wind_mph=20.0, gust_mph=25.0, rain_in_hr=0.30, snow_in_hr=None)
    assessment = assess_checkpoint(sample, load_lb=20_000)
    assert assessment.level is None
