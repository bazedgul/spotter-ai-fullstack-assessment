"""Route orchestration, via-waypoint diversification, truck speed capping, and validation."""

import itertools
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.conf import settings

from trucksafe.adapters.routing.base import RawRoute, RoutingProvider
from trucksafe.domain.geo import (
    bearing,
    cumulative_miles,
    haversine_miles,
    offset_point,
    overlap_fraction,
    point_at_mile,
)
from trucksafe.domain.models import LatLon, RoutePath


class RouteValidationError(Exception):
    """Raised for invalid trip parameters (too short, too long, invalid coords)."""


class RouteNotFoundError(Exception):
    """Raised when no drivable path could be found."""


class RouteTooLongError(Exception):
    """Raised when trip exceeds max distance limit (4,000 mi)."""


@dataclass
class RoutesBuildResult:
    """Result of route generation containing RoutePaths and potential warnings."""

    routes: list[RoutePath]
    warnings: list[str]


def raw_route_to_path(raw: RawRoute, route_id: str, label: str, provider: str) -> RoutePath:
    """Convert RawRoute to RoutePath with truck speed capping applied (A10)."""
    coords = raw.coords
    cum_miles = cumulative_miles(coords)
    speed_cap_mph = float(getattr(settings, "TRUCK_MAX_AVG_SPEED_MPH", 62.0))

    n_segments = len(coords) - 1
    if n_segments <= 0:
        return RoutePath(
            id=route_id,
            coords=coords,
            cum_miles=[0.0],
            cum_seconds=[0.0],
            summary=raw.summary or label,
            provider=provider,
        )

    # Calculate segment lengths
    seg_miles = [cum_miles[i + 1] - cum_miles[i] for i in range(n_segments)]

    if raw.seg_durations_s and len(raw.seg_durations_s) == n_segments:
        raw_durations = raw.seg_durations_s
    else:
        # Fallback: distribute total duration proportionally by segment miles
        tot_m = sum(seg_miles)
        if tot_m > 0:
            raw_durations = [raw.duration_s * (m / tot_m) for m in seg_miles]
        else:
            raw_durations = [raw.duration_s / n_segments] * n_segments

    # Cap segment speed so truck never exceeds speed_cap_mph (62 mph)
    # seg_seconds = max(api_seconds, seg_miles / 62 * 3600)
    capped_seg_seconds = [
        max(api_sec, (m / speed_cap_mph) * 3600.0) for api_sec, m in zip(raw_durations, seg_miles)
    ]

    cum_seconds = [0.0] + list(itertools.accumulate(capped_seg_seconds))

    return RoutePath(
        id=route_id,
        coords=coords,
        cum_miles=cum_miles,
        cum_seconds=cum_seconds,
        summary=raw.summary or label,
        provider=provider,
    )


class RoutesBuilder:
    """Builds up to 3 distinct routes between origin and destination."""

    def __init__(self, provider: RoutingProvider) -> None:
        self.provider = provider
        self.total_provider_calls = 0

    def build_routes(
        self,
        origin: LatLon,
        dest: LatLon,
    ) -> RoutesBuildResult:
        straight_dist = haversine_miles(origin, dest)
        if straight_dist < 0.5:
            raise RouteValidationError("Origin and destination must be at least 0.5 miles apart")

        warnings: list[str] = []

        # Step 1: Initial call to provider
        self.total_provider_calls += 1
        initial_routes = self.provider.get_routes(origin, dest)
        if not initial_routes:
            raise RouteNotFoundError("No drivable route found between origin and destination")

        # Check max distance (4,000 miles)
        fastest_initial = min(initial_routes, key=lambda r: r.duration_s)
        total_initial_miles = fastest_initial.distance_m / 1609.344
        if total_initial_miles > 4000.0:
            raise RouteTooLongError("Route exceeds maximum trip distance of 4,000 miles")

        # De-duplicate initial routes with overlap_fraction >= 0.98
        distinct_raw: list[RawRoute] = []
        for candidate in initial_routes:
            is_dup = any(
                overlap_fraction(candidate.coords, kept.coords) >= 0.98 for kept in distinct_raw
            )
            if not is_dup:
                distinct_raw.append(candidate)

        # Step 2: Via-waypoint augmentation if < 3 distinct routes
        if len(distinct_raw) < 3 and distinct_raw:
            base_route = distinct_raw[0]
            base_coords = base_route.coords
            base_cum = cumulative_miles(base_coords)
            total_m = base_cum[-1]

            fractions = [0.5, 0.35, 0.65]
            sides = [1.0, -1.0]
            offset_dist = max(10.0, min(40.0, 0.08 * total_m))

            # Generate via points
            candidates_via: list[LatLon] = []
            for frac in fractions:
                pt_on_path = point_at_mile(base_coords, base_cum, total_m * frac)
                # Compute local tangent bearing
                m_prev = max(0.0, total_m * frac - 5.0)
                m_next = min(total_m, total_m * frac + 5.0)
                p1 = point_at_mile(base_coords, base_cum, m_prev)
                p2 = point_at_mile(base_coords, base_cum, m_next)
                path_brng = bearing(p1, p2)

                for side in sides:
                    perp_brng = (path_brng + side * 90.0) % 360.0
                    via_pt = offset_point(pt_on_path, perp_brng, offset_dist)
                    candidates_via.append(via_pt)

            # Limit to 6 candidates
            candidates_via = candidates_via[:6]

            # Parallel query for via routes (bounded, max 6 calls)
            def fetch_via(via: LatLon) -> list[RawRoute]:
                try:
                    return self.provider.get_routes(origin, dest, waypoints=[via])
                except Exception:
                    return []

            max_workers = min(6, len(candidates_via))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(fetch_via, candidates_via))
                self.total_provider_calls += len(candidates_via)

            fastest_sec = fastest_initial.duration_s
            fastest_dist = fastest_initial.distance_m

            # Collect and filter candidates
            accepted_via: list[RawRoute] = []
            for subroutes in results:
                for r in subroutes:
                    # Candidate validation:
                    # 1. duration <= 1.5 * fastest
                    # 2. distance <= 1.5 * fastest
                    if r.duration_s > 1.5 * fastest_sec:
                        continue
                    if r.distance_m > 1.5 * fastest_dist:
                        continue

                    # 3. overlap_fraction vs every kept route < 0.90
                    all_kept = distinct_raw + accepted_via
                    if any(overlap_fraction(r.coords, kept.coords) >= 0.90 for kept in all_kept):
                        continue

                    accepted_via.append(r)

            # Sort accepted by duration and take until 3
            accepted_via.sort(key=lambda r: r.duration_s)
            for r in accepted_via:
                if len(distinct_raw) >= 3:
                    break
                distinct_raw.append(r)

        if len(distinct_raw) < 3:
            warnings.append(f"Only {len(distinct_raw)} distinct routes available for this trip.")

        # Convert to RoutePaths with labels Route A, Route B, Route C
        provider_name = (
            getattr(self.provider, "__class__", type)
            .__name__.replace("RoutingProvider", "")
            .lower()
            or "router"
        )
        route_paths: list[RoutePath] = []
        for i, raw in enumerate(distinct_raw[:3]):
            label = f"Route {chr(ord('A') + i)}"
            route_id = f"r{i + 1}"
            route_paths.append(
                raw_route_to_path(raw, route_id=route_id, label=label, provider=provider_name)
            )

        return RoutesBuildResult(routes=route_paths, warnings=warnings)
