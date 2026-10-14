"""Analyze pipeline orchestrator coordinating routing, weather, assessment, and recommendation."""

import logging
import math
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings

from trucksafe.adapters.routing.base import RoutingProvider
from trucksafe.adapters.routing.fallback import FallbackRoutingProvider
from trucksafe.adapters.weather.base import WeatherProvider, interpolate_at
from trucksafe.adapters.weather.open_meteo import OpenMeteoWeatherProvider, snap_to_cell
from trucksafe.domain.aggregate import aggregate
from trucksafe.domain.checkpoints import checkpoint_miles, owned_lengths
from trucksafe.domain.geo import point_at_mile, time_at_mile
from trucksafe.domain.models import Assessment, Checkpoint, LatLon, WeatherSample
from trucksafe.domain.recommend import RouteCandidate, explain, get_recommendation_ids, rank_routes
from trucksafe.domain.risk import Risk, assess_checkpoint
from trucksafe.services.presenters import build_heatmap_request, present_checkpoint, present_route
from trucksafe.services.routes_builder import RoutesBuilder
from trucksafe.services.timezones import localize_to_utc, tz_at

logger = logging.getLogger(__name__)


class AnalyzeValidationError(Exception):
    """Raised for input validation failures during analysis."""


class AnalyzeOrchestrator:
    """End-to-end trip safety analysis orchestrator."""

    def __init__(
        self,
        routing_provider: RoutingProvider | None = None,
        weather_provider: WeatherProvider | None = None,
    ) -> None:
        self.routing_provider = routing_provider or FallbackRoutingProvider()
        self.weather_provider = weather_provider or OpenMeteoWeatherProvider()

    def analyze(
        self,
        origin: LatLon,
        origin_label: str,
        destination: LatLon,
        dest_label: str,
        departure_local: str,
        load_weight_lb: float,
        checkpoint_interval_miles: float = 25.0,
        simulate_storm: bool = False,
    ) -> dict[str, Any]:
        t_start = time.perf_counter()
        request_id = str(uuid.uuid4())
        warnings: list[str] = []

        # 1. Resolve Timezone and Validate Departure Window (A12 & A15)
        origin_tz, tz_approx = tz_at(origin.lat, origin.lon)
        if tz_approx:
            warnings.append("Time zone approximated")

        naive_dep = datetime.fromisoformat(departure_local)
        dep_utc = localize_to_utc(naive_dep, origin_tz)

        now_utc = datetime.now(UTC)
        min_dep = now_utc - timedelta(hours=2)
        max_dep = now_utc + timedelta(days=10)

        if dep_utc < min_dep or dep_utc > max_dep:
            raise AnalyzeValidationError(
                f"Departure time must be between 2 hours in the past and 10 days ahead. "
                f"(Received {dep_utc.strftime('%Y-%m-%d %H:%M UTC')})"
            )

        # 2. Routing
        t_route_0 = time.perf_counter()
        routes_builder = RoutesBuilder(self.routing_provider)
        build_result = routes_builder.build_routes(origin, destination)
        warnings.extend(build_result.warnings)
        routes = build_result.routes
        t_route_ms = int((time.perf_counter() - t_route_0) * 1000)

        # Check for fallback router warnings
        if hasattr(self.routing_provider, "last_warning") and self.routing_provider.last_warning:
            warnings.append(self.routing_provider.last_warning)

        # 3. Checkpoints & Weather Sampling Cells
        route_checkpoints: dict[str, list[Checkpoint]] = {}
        route_owned: dict[str, list[float]] = {}
        all_cells: list[tuple[float, float]] = []

        for r in routes:
            ms = checkpoint_miles(r.total_miles, checkpoint_interval_miles)
            owned = owned_lengths(ms)
            route_owned[r.id] = owned

            cps: list[Checkpoint] = []
            for idx, (m, ow) in enumerate(zip(ms, owned)):
                pt = point_at_mile(r.coords, r.cum_miles, m)
                elapsed_sec = time_at_mile(r.cum_miles, r.cum_seconds, m)
                eta = dep_utc + timedelta(seconds=elapsed_sec)
                cp = Checkpoint(
                    index=idx,
                    mile=m,
                    lat=pt.lat,
                    lon=pt.lon,
                    eta_utc=eta,
                    owned_miles=ow,
                )
                cps.append(cp)
                all_cells.append(snap_to_cell(cp.lat, cp.lon))
            route_checkpoints[r.id] = cps

        # 4. Fetch Weather Series
        t_wx_0 = time.perf_counter()
        longest_h = max(r.total_seconds for r in routes) / 3600.0 if routes else 0.0
        n_hours = max(49, math.ceil(longest_h) + 3)
        start_hour = dep_utc.replace(minute=0, second=0, microsecond=0)

        weather_map = self.weather_provider.fetch(all_cells, start_hour, n_hours)
        t_wx_ms = int((time.perf_counter() - t_wx_0) * 1000)

        # 5. Risk Assessment & Aggregation
        t_risk_0 = time.perf_counter()
        candidates: list[RouteCandidate] = []
        route_cp_data: dict[str, list[dict[str, Any]]] = {}

        for r in routes:
            cps = route_checkpoints[r.id]
            ow_list = route_owned[r.id]
            assessments: list[Assessment] = []
            cp_presented: list[dict[str, Any]] = []

            first_nt_mile: float | None = None
            first_nt_note: str | None = None

            for cp in cps:
                cell = snap_to_cell(cp.lat, cp.lon)
                series = weather_map.get(cell)
                if series:
                    sample = interpolate_at(series, cp.eta_utc)
                else:
                    sample = WeatherSample(
                        wind_mph=None,
                        gust_mph=None,
                        rain_in_hr=None,
                        snow_in_hr=None,
                        status="missing",
                    )

                assessment = assess_checkpoint(sample, load_weight_lb)
                assessments.append(assessment)

                # Record first No Travel occurrence for explanation
                if assessment.level == Risk.NO_TRAVEL and first_nt_mile is None:
                    first_nt_mile = cp.mile
                    first_nt_note = next(
                        (d.note for d in assessment.drivers if d.level == Risk.NO_TRAVEL),
                        "Extreme weather condition",
                    )

                cp_presented.append(present_checkpoint(cp, sample, assessment))

            route_cp_data[r.id] = cp_presented

            metrics = aggregate(
                levels=[a.level for a in assessments],
                owned=ow_list,
                duration_min=r.total_seconds / 60.0,
                distance_mi=r.total_miles,
            )

            candidate = RouteCandidate(
                id=r.id,
                label=r.summary,
                metrics=metrics,
                first_no_travel_mile=first_nt_mile,
                first_no_travel_note=first_nt_note,
            )
            candidates.append(candidate)

        ranked = rank_routes(candidates)
        recommended_id, least_risk_id = get_recommendation_ids(ranked)
        explanations, advisory = explain(ranked)
        t_risk_ms = int((time.perf_counter() - t_risk_0) * 1000)

        # 6. Calculate forecast_available_until
        valid_hours = [
            s.last_valid_hour for s in weather_map.values() if s.last_valid_hour is not None
        ]
        if valid_hours:
            raw_until = min(valid_hours)
            horizon_cap = now_utc + timedelta(days=16)
            forecast_until = min(raw_until, horizon_cap)
            forecast_until_str: str | None = forecast_until.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            forecast_until_str = None

        # 7. Format Presented Routes
        path_map = {r.id: r for r in routes}
        routes_presented: list[dict[str, Any]] = []
        for rank_idx, cand in enumerate(ranked, 1):
            is_rec = cand.id == recommended_id
            exp = explanations.get(cand.id, "")
            r_path = path_map[cand.id]
            cp_data = route_cp_data[cand.id]
            routes_presented.append(
                present_route(
                    candidate=cand,
                    path=r_path,
                    rank=rank_idx,
                    is_recommended=is_rec,
                    explanation=exp,
                    checkpoints_data=cp_data,
                )
            )

        # 8. Heatmap Request Payload
        heatmap_request = build_heatmap_request(
            routes=routes,
            departure_utc=dep_utc,
            load_weight_lb=load_weight_lb,
            simulate_storm=simulate_storm,
        )

        total_ms = int((time.perf_counter() - t_start) * 1000)

        return {
            "request_id": request_id,
            "departure_utc": dep_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "origin_tz": getattr(origin_tz, "key", str(origin_tz)),
            "load_weight_lb": load_weight_lb,
            "checkpoint_interval_miles": checkpoint_interval_miles,
            "recommended_route_id": recommended_id,
            "least_risk_route_id": least_risk_id,
            "forecast_available_until": forecast_until_str,
            "advisory": advisory,
            "warnings": warnings,
            "routes": routes_presented,
            "heatmap_request": heatmap_request,
            "meta": {
                "timings_ms": {
                    "routing": t_route_ms,
                    "weather": t_wx_ms,
                    "risk": t_risk_ms,
                    "total": total_ms,
                },
                "providers": {
                    "routing": getattr(settings, "ROUTING_PROVIDER", "mapbox"),
                    "weather": "open-meteo",
                },
            },
        }
