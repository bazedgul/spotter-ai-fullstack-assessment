"""Unit tests for route ranking, safety vetoes, and deterministic explanations."""

from trucksafe.domain.models import RouteMetrics
from trucksafe.domain.recommend import (
    RouteCandidate,
    explain,
    get_recommendation_ids,
    rank_routes,
)
from trucksafe.domain.risk import Risk


def make_metrics(
    *,
    blocked: bool = False,
    no_travel: float = 0.0,
    severe: float = 0.0,
    high: float = 0.0,
    moderate: float = 0.0,
    low: float = 100.0,
    unknown: float = 0.0,
    avg_risk: float | None = 0.5,
    duration: float = 600.0,
    distance: float = 500.0,
    max_level: Risk | None = Risk.LOW,
) -> RouteMetrics:
    return RouteMetrics(
        distance_mi=distance,
        duration_min=duration,
        no_travel_miles=no_travel,
        severe_miles=severe,
        high_miles=high,
        moderate_miles=moderate,
        low_miles=low,
        unknown_miles=unknown,
        avg_risk=avg_risk,
        max_level=max_level,
        blocked=blocked,
    )


def test_ranking_severe_beats_high() -> None:
    # Route A has 0 severe, 20 high miles
    # Route B has 10 severe, 0 high miles
    r_a = RouteCandidate("rA", "Route A", make_metrics(severe=0.0, high=20.0, duration=600.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(severe=10.0, high=0.0, duration=500.0))

    ranked = rank_routes([r_b, r_a])
    assert [r.id for r in ranked] == ["rA", "rB"]


def test_ranking_high_beats_avg_risk() -> None:
    # Both have 0 severe. Route A has 10 high miles, avg 1.2. Route B has 20 high miles, avg 0.8
    r_a = RouteCandidate("rA", "Route A", make_metrics(severe=0.0, high=10.0, avg_risk=1.2))
    r_b = RouteCandidate("rB", "Route B", make_metrics(severe=0.0, high=20.0, avg_risk=0.8))

    ranked = rank_routes([r_b, r_a])
    assert [r.id for r in ranked] == ["rA", "rB"]


def test_ranking_avg_risk_beats_duration() -> None:
    # Both 0 severe, 0 high. Route A has avg 0.3, duration 700. Route B has avg 0.7, duration 600
    r_a = RouteCandidate("rA", "Route A", make_metrics(avg_risk=0.3, duration=700.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(avg_risk=0.7, duration=600.0))

    ranked = rank_routes([r_b, r_a])
    assert [r.id for r in ranked] == ["rA", "rB"]


def test_ranking_duration_tie_breaker() -> None:
    # Equal weather exposure. Route A is 550 min, Route B is 600 min
    r_a = RouteCandidate("rA", "Route A", make_metrics(avg_risk=0.5, duration=550.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(avg_risk=0.5, duration=600.0))

    ranked = rank_routes([r_b, r_a])
    assert [r.id for r in ranked] == ["rA", "rB"]


def test_ranking_no_travel_route_loses_to_severe() -> None:
    # Route A has 50 miles of Severe but unblocked
    # Route B has 1 mile of No Travel (blocked)
    r_a = RouteCandidate("rA", "Route A", make_metrics(blocked=False, severe=50.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(blocked=True, no_travel=1.0, severe=0.0))

    ranked = rank_routes([r_b, r_a])
    assert [r.id for r in ranked] == ["rA", "rB"]
    rec_id, least_risk_id = get_recommendation_ids(ranked)
    assert rec_id == "rA"
    assert least_risk_id is None


def test_ranking_stable_route_id_tie_break() -> None:
    # Identical metrics, sorted by route_id
    r_b = RouteCandidate("rB", "Route B", make_metrics(duration=500.0))
    r_a = RouteCandidate("rA", "Route A", make_metrics(duration=500.0))

    ranked = rank_routes([r_b, r_a])
    assert [r.id for r in ranked] == ["rA", "rB"]


def test_all_routes_blocked_handling() -> None:
    r_a = RouteCandidate(
        "rA",
        "Route A",
        make_metrics(blocked=True, no_travel=5.0),
        first_no_travel_mile=10.0,
        first_no_travel_note="Wind ≥55 mph",
    )
    r_b = RouteCandidate(
        "rB",
        "Route B",
        make_metrics(blocked=True, no_travel=15.0),
        first_no_travel_mile=20.0,
        first_no_travel_note="Wind 50 mph with load >30k",
    )

    ranked = rank_routes([r_b, r_a])
    rec_id, least_risk_id = get_recommendation_ids(ranked)
    # When all routes are blocked, recommended_route_id is None and least_risk_route_id is set
    assert rec_id is None
    assert least_risk_id == "rA"

    explanations, advisory = explain(ranked)
    assert advisory is not None
    assert "No route is safe under the supplied rules" in advisory
    assert "Route A has the fewest No Travel miles (5)" in advisory
    # Blocked route explanation must never contain 'Recommended'
    for exp in explanations.values():
        assert "Recommended" not in exp
        assert "Not recommended:" in exp


def test_explain_deciding_criterion_severe() -> None:
    r_a = RouteCandidate("rA", "Route A", make_metrics(severe=10.0, duration=500.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(severe=35.0, duration=500.0))
    ranked = [r_a, r_b]

    explanations, _ = explain(ranked)
    assert "Recommended: 10 severe miles vs 35 on Route B." in explanations["rA"]
    assert "It is also the fastest route." in explanations["rA"]


def test_explain_deciding_criterion_high() -> None:
    r_a = RouteCandidate("rA", "Route A", make_metrics(severe=0.0, high=15.0, duration=600.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(severe=0.0, high=40.0, duration=580.0))
    ranked = [r_a, r_b]

    explanations, _ = explain(ranked)
    exp = explanations["rA"]
    assert "Recommended: same severe miles as Route B, but 15 high miles vs 40." in exp
    assert "It is 20 min slower than the fastest route (Route B)." in exp


def test_explain_deciding_criterion_avg_risk() -> None:
    r_a = RouteCandidate(
        "rA", "Route A", make_metrics(severe=0.0, high=0.0, avg_risk=0.42, duration=600.0)
    )
    r_b = RouteCandidate(
        "rB", "Route B", make_metrics(severe=0.0, high=0.0, avg_risk=0.88, duration=600.0)
    )
    ranked = [r_a, r_b]

    explanations, _ = explain(ranked)
    exp = explanations["rA"]
    assert (
        "Recommended: same severe and high miles as Route B, lower average risk (0.42 vs 0.88)."
        in exp
    )


def test_explain_deciding_criterion_duration() -> None:
    r_a = RouteCandidate("rA", "Route A", make_metrics(avg_risk=0.5, duration=500.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(avg_risk=0.5, duration=540.0))
    ranked = [r_a, r_b]

    explanations, _ = explain(ranked)
    assert "Recommended: same weather exposure as Route B and 40 min faster." in explanations["rA"]


def test_explain_single_route_available() -> None:
    r_a = RouteCandidate("rA", "Route A", make_metrics(max_level=Risk.HIGH))
    explanations, _ = explain([r_a])
    assert explanations["rA"] == "Only one route available; highest risk level on route: HIGH."


def test_explain_route_with_unknown_miles() -> None:
    r_a = RouteCandidate("rA", "Route A", make_metrics(severe=0.0, duration=500.0))
    r_b = RouteCandidate("rB", "Route B", make_metrics(severe=20.0, unknown=45.0, duration=520.0))
    explanations, _ = explain([r_a, r_b])
    assert "Forecast unavailable for 45 miles; compared on known miles only." in explanations["rB"]
