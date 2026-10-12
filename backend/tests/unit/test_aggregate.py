"""Unit tests for route risk aggregation conforming to Section 9.2 and A6/A7."""

import pytest

from trucksafe.domain.aggregate import aggregate
from trucksafe.domain.risk import Risk


def test_hand_computed_aggregation() -> None:
    # 100 miles route with 4 checkpoints:
    # Checkpoint 0: LOW (0), owned 20 miles
    # Checkpoint 1: MODERATE (1), owned 30 miles
    # Checkpoint 2: HIGH (2), owned 30 miles
    # Checkpoint 3: SEVERE (3), owned 20 miles
    levels = [Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE]
    owned = [20.0, 30.0, 30.0, 20.0]
    total_miles = 100.0
    duration_min = 120.0

    metrics = aggregate(levels, owned, duration_min, total_miles)

    assert metrics.distance_mi == 100.0
    assert metrics.duration_min == 120.0
    assert metrics.low_miles == 20.0
    assert metrics.moderate_miles == 30.0
    assert metrics.high_miles == 30.0
    assert metrics.severe_miles == 20.0
    assert metrics.no_travel_miles == 0.0
    assert metrics.unknown_miles == 0.0
    assert metrics.blocked is False
    assert metrics.max_level == Risk.SEVERE

    # Weighted average: (0*20 + 1*30 + 2*30 + 3*20) / 100
    # = (0 + 30 + 60 + 60) / 100 = 150 / 100 = 1.5
    assert metrics.avg_risk == pytest.approx(1.5, abs=1e-3)


def test_aggregation_with_unknown_miles() -> None:
    # 100 miles:
    # 40 miles LOW (0)
    # 20 miles SEVERE (3)
    # 40 miles UNKNOWN (None)
    levels = [Risk.LOW, Risk.SEVERE, None]
    owned = [40.0, 20.0, 40.0]
    total_miles = 100.0
    duration_min = 100.0

    metrics = aggregate(levels, owned, duration_min, total_miles)
    assert metrics.unknown_miles == 40.0
    assert metrics.low_miles == 40.0
    assert metrics.severe_miles == 20.0
    assert metrics.blocked is False

    # Known miles = 60. Weighted sum = 0*40 + 3*20 = 60. Avg = 60 / 60 = 1.0
    assert metrics.avg_risk == pytest.approx(1.0, abs=1e-3)


def test_all_unknown_route_yields_none_avg() -> None:
    levels = [None, None]
    owned = [50.0, 50.0]
    metrics = aggregate(levels, owned, duration_min=100.0, distance_mi=100.0)

    assert metrics.unknown_miles == 100.0
    assert metrics.avg_risk is None
    assert metrics.max_level is None
    assert metrics.blocked is False


def test_blocked_route_detection() -> None:
    levels = [Risk.LOW, Risk.NO_TRAVEL, Risk.LOW]
    owned = [10.0, 5.0, 85.0]
    metrics = aggregate(levels, owned, duration_min=100.0, distance_mi=100.0)

    assert metrics.blocked is True
    assert metrics.no_travel_miles == 5.0
    assert metrics.max_level == Risk.NO_TRAVEL
