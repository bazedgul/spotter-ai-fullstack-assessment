"""Geographic calculations, interpolation, simplification, and route overlap."""

import bisect
import math

from trucksafe.domain.models import LatLon
from trucksafe.domain.units import EARTH_RADIUS_MILES


def haversine_miles(a: LatLon, b: LatLon) -> float:
    """Great-circle distance between two coordinates in miles."""
    if a.lat == b.lat and a.lon == b.lon:
        return 0.0

    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)

    h = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(h), math.sqrt(max(0.0, 1.0 - h)))
    return EARTH_RADIUS_MILES * c


def cumulative_miles(coords: list[LatLon]) -> list[float]:
    """Compute cumulative distance in miles along a coordinate sequence."""
    if not coords:
        return []
    cum = [0.0]
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine_miles(coords[i], coords[i + 1])
        cum.append(total)
    return cum


def point_at_mile(coords: list[LatLon], cum_miles: list[float], m: float) -> LatLon:
    """Interpolate coordinates along a path at a target mile marker."""
    if not coords:
        raise ValueError("Cannot sample an empty coordinate path")
    if len(coords) == 1 or m <= 0.0:
        return coords[0]
    if m >= cum_miles[-1]:
        return coords[-1]

    idx = bisect.bisect_right(cum_miles, m)
    i0 = idx - 1
    i1 = idx

    d0 = cum_miles[i0]
    d1 = cum_miles[i1]
    span = d1 - d0
    if span <= 1e-12:
        return coords[i0]

    t = (m - d0) / span
    lat = coords[i0].lat + t * (coords[i1].lat - coords[i0].lat)
    lon = coords[i0].lon + t * (coords[i1].lon - coords[i0].lon)
    return LatLon(lat=lat, lon=lon)


def time_at_mile(cum_miles: list[float], cum_seconds: list[float], m: float) -> float:
    """Interpolate elapsed duration (in seconds) along a path at a target mile marker."""
    if not cum_seconds or not cum_miles:
        return 0.0
    if len(cum_seconds) == 1 or m <= 0.0:
        return cum_seconds[0]
    if m >= cum_miles[-1]:
        return cum_seconds[-1]

    idx = bisect.bisect_right(cum_miles, m)
    i0 = idx - 1
    i1 = idx

    d0 = cum_miles[i0]
    d1 = cum_miles[i1]
    span = d1 - d0
    if span <= 1e-12:
        return cum_seconds[i0]

    t = (m - d0) / span
    return cum_seconds[i0] + t * (cum_seconds[i1] - cum_seconds[i0])


def bearing(a: LatLon, b: LatLon) -> float:
    """Calculate the initial bearing from point a to point b in degrees [0, 360)."""
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0


def offset_point(p: LatLon, bearing_deg: float, miles: float) -> LatLon:
    """Calculate target coordinates displaced from p by bearing and distance."""
    if miles == 0.0:
        return p

    lat1 = math.radians(p.lat)
    lon1 = math.radians(p.lon)
    d_r = miles / EARTH_RADIUS_MILES
    brng = math.radians(bearing_deg)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(d_r) + math.cos(lat1) * math.sin(d_r) * math.cos(brng)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(d_r) * math.cos(lat1),
        math.cos(d_r) - math.sin(lat1) * math.sin(lat2),
    )

    deg_lat = math.degrees(lat2)
    deg_lon = (math.degrees(lon2) + 540.0) % 360.0 - 180.0
    return LatLon(lat=deg_lat, lon=deg_lon)


def _perpendicular_distance_sq(pt: LatLon, line_start: LatLon, line_end: LatLon) -> float:
    """Squared Euclidean distance in degrees from pt to line segment."""
    dx = line_end.lon - line_start.lon
    dy = line_end.lat - line_start.lat
    norm_sq = dx * dx + dy * dy
    if norm_sq == 0.0:
        px = pt.lon - line_start.lon
        py = pt.lat - line_start.lat
        return px * px + py * py

    dot = (pt.lon - line_start.lon) * dx + (pt.lat - line_start.lat) * dy
    t = max(0.0, min(1.0, dot / norm_sq))
    proj_x = line_start.lon + t * dx
    proj_y = line_start.lat + t * dy
    px = pt.lon - proj_x
    py = pt.lat - proj_y
    return px * px + py * py


def rdp_simplify(coords: list[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Ramer-Douglas-Peucker line simplification preserving endpoints."""
    if len(coords) <= 2 or tolerance_deg <= 0.0:
        return coords

    tol_sq = tolerance_deg * tolerance_deg
    stack: list[tuple[int, int]] = [(0, len(coords) - 1)]
    keep = [False] * len(coords)
    keep[0] = True
    keep[-1] = True

    while stack:
        start_idx, end_idx = stack.pop()
        max_dist_sq = -1.0
        max_idx = -1

        start_pt = coords[start_idx]
        end_pt = coords[end_idx]

        for i in range(start_idx + 1, end_idx):
            d_sq = _perpendicular_distance_sq(coords[i], start_pt, end_pt)
            if d_sq > max_dist_sq:
                max_dist_sq = d_sq
                max_idx = i

        if max_dist_sq > tol_sq and max_idx != -1:
            keep[max_idx] = True
            stack.append((start_idx, max_idx))
            stack.append((max_idx, end_idx))

    return [coord for idx, coord in enumerate(coords) if keep[idx]]


def overlap_fraction(a: list[LatLon], b: list[LatLon], max_dist_miles: float = 1.25) -> float:
    """Calculate the fraction of route A within max_dist_miles of route B.

    Samples A at 60 points and checks distance against 200 samples of B.
    """
    if not a or not b:
        return 0.0
    if len(a) == 1 and len(b) == 1:
        return 1.0 if haversine_miles(a[0], b[0]) <= max_dist_miles else 0.0

    cum_a = cumulative_miles(a)
    tot_a = cum_a[-1]
    if tot_a <= 0.0:
        return 1.0 if haversine_miles(a[0], b[0]) <= max_dist_miles else 0.0

    cum_b = cumulative_miles(b)
    tot_b = cum_b[-1]
    if tot_b <= 0.0:
        return 0.0

    n_samples_a = 60
    n_samples_b = 200

    pts_a = [point_at_mile(a, cum_a, tot_a * i / (n_samples_a - 1)) for i in range(n_samples_a)]
    pts_b = [point_at_mile(b, cum_b, tot_b * j / (n_samples_b - 1)) for j in range(n_samples_b)]

    matched = 0
    for p_a in pts_a:
        # Check if any sample of B is within distance
        for p_b in pts_b:
            if haversine_miles(p_a, p_b) <= max_dist_miles:
                matched += 1
                break

    return matched / n_samples_a
