"""Domain models for trucksafe."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from trucksafe.domain.risk import Risk


@dataclass(frozen=True)
class LatLon:
    """Geographic coordinate pair in degrees."""

    lat: float
    lon: float


@dataclass(frozen=True)
class RoutePath:
    """Full-resolution route geometry and cumulative metrics."""

    id: str
    coords: list[LatLon]
    cum_miles: list[float]
    cum_seconds: list[float]
    summary: str
    provider: str

    @property
    def total_miles(self) -> float:
        return self.cum_miles[-1] if self.cum_miles else 0.0

    @property
    def total_seconds(self) -> float:
        return self.cum_seconds[-1] if self.cum_seconds else 0.0


@dataclass(frozen=True)
class Checkpoint:
    """A sampled checkpoint along a route."""

    index: int
    mile: float
    lat: float
    lon: float
    eta_utc: datetime
    owned_miles: float


@dataclass(frozen=True)
class WeatherSample:
    """Weather condition sampled or interpolated at a checkpoint or corridor point."""

    wind_mph: float | None
    gust_mph: float | None
    rain_in_hr: float | None
    snow_in_hr: float | None
    status: Literal["available", "missing", "out_of_horizon"] = "available"


@dataclass(frozen=True)
class Driver:
    """A factor driving the risk classification at a checkpoint."""

    condition: Literal["wind", "rain", "snow", "load_rule"]
    level: Risk
    note: str


@dataclass(frozen=True)
class Assessment:
    """Checkpoint risk assessment (level is None when UNKNOWN)."""

    level: Risk | None
    drivers: list[Driver]


@dataclass(frozen=True)
class RouteMetrics:
    """Aggregated exposure metrics for a route."""

    distance_mi: float
    duration_min: float
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    unknown_miles: float
    avg_risk: float | None
    max_level: Risk | None
    blocked: bool
