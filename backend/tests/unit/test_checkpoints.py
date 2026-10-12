"""Unit tests for checkpoint generation and mile ownership allocation."""

import pytest

from trucksafe.domain.checkpoints import checkpoint_miles, owned_lengths


@pytest.mark.parametrize(
    ("total", "interval", "expected_count"),
    [
        (100.0, 25.0, 5),  # 0, 25, 50, 75, 100
        (102.0, 25.0, 5),  # 0, 25, 50, 75, (100 dropped because 102 - 100 < 0.25*25=6.25), 102
        (107.0, 25.0, 6),  # 0, 25, 50, 75, 100, 107
        (10.0, 25.0, 2),  # 0, 10
        (500.0, 50.0, 11),  # 0, 50..500
    ],
)
def test_checkpoint_miles_generation(total: float, interval: float, expected_count: int) -> None:
    ms = checkpoint_miles(total, interval)
    assert len(ms) == expected_count
    assert ms[0] == 0.0
    assert ms[-1] == total
    assert ms == sorted(ms)
    assert len(set(ms)) == len(ms)  # strictly increasing


def test_drop_near_end_rule() -> None:
    # interval 25: threshold 0.25 * 25 = 6.25.
    # total = 105. 100 is within 105 - 6.25 = 98.75. So 100 < 98.75 is FALSE.
    # 100 is dropped!
    ms = checkpoint_miles(105.0, 25.0)
    assert 100.0 not in ms
    assert ms[-1] == 105.0
    assert ms[-2] == 75.0


@pytest.mark.parametrize(
    ("total", "interval"),
    [
        (100.0, 10.0),
        (253.7, 25.0),
        (12.3, 25.0),
        (1420.5, 50.0),
        (0.5, 10.0),
    ],
)
def test_owned_lengths_sum_invariant(total: float, interval: float) -> None:
    ms = checkpoint_miles(total, interval)
    owned = owned_lengths(ms)
    assert len(owned) == len(ms)
    assert sum(owned) == pytest.approx(total, abs=1e-9)
    for length in owned:
        assert length > 0.0
