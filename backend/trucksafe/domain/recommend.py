"""Route ranking, safety vetoes, and deterministic explanation generator."""

from dataclasses import dataclass

from trucksafe.domain.models import RouteMetrics


@dataclass(frozen=True)
class RouteCandidate:
    """Route candidate for ranking and explanation generation."""

    id: str
    label: str
    metrics: RouteMetrics
    first_no_travel_mile: float | None = None
    first_no_travel_note: str | None = None


def rank_key(m: RouteMetrics, route_id: str) -> tuple[bool, int, int, int, float, int, int, str]:
    """Sort key for deterministic ranking (A9).

    Criteria in order:
    1. blocked (False before True)
    2. no_travel_miles (ascending)
    3. severe_miles (ascending)
    4. high_miles (ascending)
    5. avg_risk (ascending, None treated as 9.0)
    6. unknown_miles (ascending)
    7. duration_min (ascending)
    8. route_id (alphabetical tie-breaker)
    """
    return (
        m.blocked,
        round(m.no_travel_miles),
        round(m.severe_miles),
        round(m.high_miles),
        round(m.avg_risk, 2) if m.avg_risk is not None else 9.0,
        round(m.unknown_miles),
        round(m.duration_min),
        route_id,
    )


def rank_routes(candidates: list[RouteCandidate]) -> list[RouteCandidate]:
    """Sort candidate routes by the A9 ranking key."""
    return sorted(candidates, key=lambda c: rank_key(c.metrics, c.id))


def get_recommendation_ids(
    ranked: list[RouteCandidate],
) -> tuple[str | None, str | None]:
    """Determine recommended_route_id and least_risk_route_id.

    If any unblocked route exists:
      recommended_route_id is the first unblocked route, least_risk_route_id is None.
    If all routes are blocked:
      recommended_route_id is None, least_risk_route_id is the first ranked route.
    """
    if not ranked:
        return None, None

    if all(c.metrics.blocked for c in ranked):
        return None, ranked[0].id

    for c in ranked:
        if not c.metrics.blocked:
            return c.id, None

    return None, None


def explain(
    ranked: list[RouteCandidate],
) -> tuple[dict[str, str], str | None]:
    """Generate deterministic explanation strings per route and global advisory.

    Follows Section 5.5 fixed templates exactly.
    """
    if not ranked:
        return {}, None

    explanations: dict[str, str] = {}
    advisory: str | None = None

    all_blocked = all(c.metrics.blocked for c in ranked)
    if all_blocked:
        best_blocked = ranked[0]
        x = round(best_blocked.metrics.no_travel_miles)
        advisory = (
            f"No route is safe under the supplied rules at this departure time. "
            f"{best_blocked.label} has the fewest No Travel miles ({x}). "
            f"Consider delaying departure."
        )

    # Find the fastest route overall
    fastest = min(ranked, key=lambda c: c.metrics.duration_min)

    # First, handle single-route scenario
    if len(ranked) == 1:
        c = ranked[0]
        if c.metrics.blocked:
            m = round(c.first_no_travel_mile or 0.0)
            note = c.first_no_travel_note or "Wind ≥55 mph"
            x = round(c.metrics.no_travel_miles)
            explanations[c.id] = (
                f"Not recommended: {x} No Travel miles (first at mile {m}: {note})."
            )
        else:
            lvl = c.metrics.max_level.name if c.metrics.max_level is not None else "UNKNOWN"
            explanations[c.id] = f"Only one route available; highest risk level on route: {lvl}."
        return explanations, advisory

    # If all routes are blocked, each gets the blocked template
    if all_blocked:
        for c in ranked:
            m = round(c.first_no_travel_mile or 0.0)
            note = c.first_no_travel_note or "Wind ≥55 mph"
            x = round(c.metrics.no_travel_miles)
            explanations[c.id] = (
                f"Not recommended: {x} No Travel miles (first at mile {m}: {note})."
            )
        return explanations, advisory

    # At least one route is unblocked
    recommended = next(c for c in ranked if not c.metrics.blocked)
    # Runner-up is the second ranked route
    runner_up = ranked[1] if ranked[0].id == recommended.id else ranked[0]

    # Build recommended route explanation based on deciding criterion D
    best_m = recommended.metrics
    run_m = runner_up.metrics

    base_exp = ""
    # D: severe miles or runner-up blocked
    if runner_up.metrics.blocked or round(best_m.severe_miles) != round(run_m.severe_miles):
        a = round(best_m.severe_miles)
        b = round(run_m.severe_miles)
        base_exp = f"Recommended: {a} severe miles vs {b} on {runner_up.label}."
    elif round(best_m.high_miles) != round(run_m.high_miles):
        a = round(best_m.high_miles)
        b = round(run_m.high_miles)
        base_exp = (
            f"Recommended: same severe miles as {runner_up.label}, but {a} high miles vs {b}."
        )
    elif round(best_m.avg_risk or 0.0, 2) != round(run_m.avg_risk or 0.0, 2):
        a_f = best_m.avg_risk or 0.0
        b_f = run_m.avg_risk or 0.0
        base_exp = (
            f"Recommended: same severe and high miles as {runner_up.label}, "
            f"lower average risk ({a_f:.2f} vs {b_f:.2f})."
        )
    else:
        # D: duration / unknown miles
        diff_min = round(run_m.duration_min) - round(best_m.duration_min)
        base_exp = (
            f"Recommended: same weather exposure as {runner_up.label} and {diff_min} min faster."
        )

    # Suffix for recommended route
    if round(best_m.duration_min) <= round(fastest.metrics.duration_min):
        suffix = " It is also the fastest route."
    else:
        slower_min = round(best_m.duration_min) - round(fastest.metrics.duration_min)
        suffix = f" It is {slower_min} min slower than the fastest route ({fastest.label})."

    explanations[recommended.id] = base_exp + suffix

    # Build explanations for remaining routes
    for c in ranked:
        if c.id == recommended.id:
            continue
        if c.metrics.blocked:
            m = round(c.first_no_travel_mile or 0.0)
            note = c.first_no_travel_note or "Wind ≥55 mph"
            x = round(c.metrics.no_travel_miles)
            explanations[c.id] = (
                f"Not recommended: {x} No Travel miles (first at mile {m}: {note})."
            )
        elif c.metrics.unknown_miles > 0:
            u = round(c.metrics.unknown_miles)
            explanations[c.id] = (
                f"Forecast unavailable for {u} miles; compared on known miles only."
            )
        else:
            diff_time = round(c.metrics.duration_min - best_m.duration_min)
            time_part = f"+{diff_time} min" if diff_time >= 0 else f"{diff_time} min"
            explanations[c.id] = (
                f"Alternative route: {round(c.metrics.severe_miles)} severe miles, "
                f"{round(c.metrics.high_miles)} high miles ({time_part})."
            )

    return explanations, advisory
