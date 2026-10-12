"""Unit tests for geographic calculations, interpolation, simplification, and overlap."""

import pytest

from trucksafe.domain.geo import (
    bearing,
    cumulative_miles,
    haversine_miles,
    offset_point,
    overlap_fraction,
    point_at_mile,
    rdp_simplify,
    time_at_mile,
)
from trucksafe.domain.models import LatLon


def test_haversine_known_distance() -> None:
    # Equator 1 degree of longitude is ~69.17 miles
    p1 = LatLon(0.0, 0.0)
    p2 = LatLon(0.0, 1.0)
    d = haversine_miles(p1, p2)
    assert 68.0 < d < 70.0
    assert haversine_miles(p1, p1) == 0.0


def test_synthetic_straight_path_interpolation() -> None:
    # Straight path along meridian from lat 0 to lat 10 (approx 690 miles)
    coords = [LatLon(lat=float(i), lon=0.0) for i in range(11)]
    cum_miles = cumulative_miles(coords)
    # Total seconds with 60 mph constant speed (1 minute per mile = 60s per mile)
    cum_seconds = [m * 60.0 for m in cum_miles]

    total_miles = cum_miles[-1]
    mid_mile = total_miles / 2.0

    mid_pt = point_at_mile(coords, cum_miles, mid_mile)
    assert mid_pt.lat == pytest.approx(5.0, abs=1e-3)
    assert mid_pt.lon == pytest.approx(0.0, abs=1e-4)

    mid_time = time_at_mile(cum_miles, cum_seconds, mid_mile)
    assert mid_time == pytest.approx(mid_mile * 60.0, abs=1e-3)

    # Clamping boundaries
    pt_start = point_at_mile(coords, cum_miles, -5.0)
    assert pt_start == coords[0]
    pt_end = point_at_mile(coords, cum_miles, total_miles + 50.0)
    assert pt_end == coords[-1]


def test_bearing_cardinal_directions() -> None:
    origin = LatLon(0.0, 0.0)
    north = LatLon(1.0, 0.0)
    east = LatLon(0.0, 1.0)
    south = LatLon(-1.0, 0.0)
    west = LatLon(0.0, -1.0)

    assert bearing(origin, north) == pytest.approx(0.0, abs=1e-2)
    assert bearing(origin, east) == pytest.approx(90.0, abs=1e-2)
    assert bearing(origin, south) == pytest.approx(180.0, abs=1e-2)
    assert bearing(origin, west) == pytest.approx(270.0, abs=1e-2)


def test_offset_point_round_trip() -> None:
    origin = LatLon(35.0, -90.0)
    # Offset North by 10 miles
    p_north = offset_point(origin, 0.0, 10.0)
    assert p_north.lat > origin.lat
    assert haversine_miles(origin, p_north) == pytest.approx(10.0, abs=1e-2)


def test_rdp_simplify_keeps_endpoints() -> None:
    coords = [
        LatLon(0.0, 0.0),
        LatLon(0.0001, 0.0001),  # tiny jitter
        LatLon(1.0, 1.0),
        LatLon(2.0, 2.0),
    ]
    simplified = rdp_simplify(coords, tolerance_deg=0.01)
    assert simplified[0] == coords[0]
    assert simplified[-1] == coords[-1]
    assert len(simplified) < len(coords)


def test_overlap_fraction() -> None:
    path_a = [LatLon(30.0 + i * 0.1, -95.0) for i in range(20)]
    path_identical = list(path_a)
    # Identical paths have overlap ~ 1.0
    assert overlap_fraction(path_a, path_identical) == pytest.approx(1.0, abs=1e-2)

    # Completely disjoint path (different state/ocean)
    path_disjoint = [LatLon(45.0 + i * 0.1, -75.0) for i in range(20)]
    assert overlap_fraction(path_a, path_disjoint) == pytest.approx(0.0, abs=1e-2)
