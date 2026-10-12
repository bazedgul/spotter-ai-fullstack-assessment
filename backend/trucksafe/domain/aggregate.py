"""Route metric aggregation across checkpoints and owned miles."""

from trucksafe.domain.models import RouteMetrics
from trucksafe.domain.risk import Risk


def aggregate(
    levels: list[Risk | None],
    owned: list[float],
    duration_min: float,
    distance_mi: float,
) -> RouteMetrics:
    """Aggregate checkpoint risk levels weighted by checkpoint owned miles.

    Calculates miles per risk category, distance-weighted average risk on
    known miles only (excluding UNKNOWN), and blocked status.
    """
    miles = {r: 0.0 for r in Risk}
    unknown = 0.0

    for lvl, m in zip(levels, owned):
        if lvl is None:
            unknown += m
        else:
            miles[lvl] += m

    known = distance_mi - unknown
    avg = (
        (sum(int(lvl) * m for lvl, m in zip(levels, owned) if lvl is not None) / known)
        if known > 0.0
        else None
    )

    blocked = any(lvl == Risk.NO_TRAVEL for lvl in levels)
    known_levels = [lvl for lvl in levels if lvl is not None]
    max_level = max(known_levels) if known_levels else None

    return RouteMetrics(
        distance_mi=distance_mi,
        duration_min=duration_min,
        no_travel_miles=miles[Risk.NO_TRAVEL],
        severe_miles=miles[Risk.SEVERE],
        high_miles=miles[Risk.HIGH],
        moderate_miles=miles[Risk.MODERATE],
        low_miles=miles[Risk.LOW],
        unknown_miles=unknown,
        avg_risk=avg,
        max_level=max_level,
        blocked=blocked,
    )
