# AGENTS.md — Weather-Aware Truck Routing (Spotter AI Full-Stack Assessment)

> Read this file COMPLETELY before writing any code. It is the single source of truth.
> Copy it to the repo root as `AGENTS.md` (and also as `CLAUDE.md` if you use Claude Code).
> Budget: max 16 work hours. Priority: **correctness and clarity over extra features.**
>
> **v3:** added Top-15 non-negotiables, `forecast_available_until` definition, fixed `explain()` templates + tests, backend-final validation, lighter Mapbox call (`steps=false`), 1-worker cache rule, timezone fallback, heatmap fallback layer, gust display, via-augment test, mandatory M2 fixture gate, CI workflow, demo preset.
>
> **v2 changelog (merged with an independent review):** boundary convention changed to half-open/lower-inclusive (safer, matches the spec's `<` wording); explicit **UNKNOWN** state (missing weather is never 0 and never extrapolated); blocked routes are **never labelled recommended**; honesty/handoff/multi-agent rules added; safety disclaimer added; no stop-and-wait Phase 0.

---

## Top 15 non-negotiables (re-read before every milestone)

1. The spec is **locked**; do not re-debate stack, providers, or architecture.
2. Weather is sampled at each checkpoint's **ETA** (cumulative per-segment time), never "now".
3. Exact thresholds with the **A1 half-open boundaries**; **no rounding** before classifying.
4. Load rules only **escalate** risk, never lower it.
5. Missing/out-of-horizon weather = **UNKNOWN** (`None`): never 0, never Low, never extrapolated.
6. A route with any No Travel is **blocked** and **never "recommended"**; No Travel ranks before Severe.
7. Ranking uses the **A9 key** exactly (`blocked, no_travel, severe, high, avg, unknown, duration, route_id`).
8. Route risk uses **mile ownership (A6)** and distance-weighted average (A7) — not checkpoint counts.
9. Departure is interpreted in the **origin's time zone**; the **backend is the final validator**.
10. Domain code (`trucksafe/domain`) is **pure Python**: no Django, no HTTP, no env.
11. **Real API fixtures before parsers** (M2 gate); tests never touch the network.
12. Map = GeoJSON **layers**, no DOM markers; slider = **zero network** (`setPaintProperty`).
13. Secrets are **server-side only**; commit `.env.example`, never `.env`.
14. **Honesty:** never claim tests pass / deployed unless actually run; label simulated data.
15. Work by **milestone gates**; max **3 different fix attempts** per error, then log in `docs/BLOCKERS.md` and use the fallback; write a **handoff report** each milestone.

---

## 0. Agent operating rules (anti-error, anti-loop)

1. **The spec is locked.** Section 2 decisions are final. Do not re-debate stack, providers, or architecture.
2. **Ambiguity → pick the documented default, log it in `docs/DECISIONS.md`, move on.** Only ask the human for: API keys/secrets, hosting credentials, or something that blocks all progress.
3. **Work milestone by milestone (Section 11).** Each milestone ends with a GATE (commands that must pass). Do not start the next milestone until the gate is green. Commit after each gate: `feat(scope): message`.
4. **Retry limit:** if the same error persists after 3 *different* fix attempts, STOP. Write it in `docs/BLOCKERS.md`, implement the documented fallback (fixture / mock / simpler path) and continue. Never repeat the same failed command more than twice. Never loop.
5. **Never invent third-party API fields.** Before writing a parser, make one real call (or read the official docs), save the real response as a fixture in `backend/tests/fixtures/`, and parse that. Tests never hit the network.
6. **No extra features.** Anything not in this file is out of scope (no auth, no user accounts, no DB models, no HOS/rest-stop logic, no truck-restriction routing). The only optional extra is the "Simulate storm" demo toggle (Section 9.5).
7. **No refactoring of finished milestones** unless a test fails or the spec changes.
8. **Pure domain core.** Risk/geo/recommendation code must not import Django, HTTP clients, or env. It must be unit-testable with plain `pytest`.
9. **Pin dependencies** (`requirements.txt` with exact versions via `pip freeze`, `package-lock.json` committed). Use latest stable at install time.
10. **Keep `PROGRESS.md` updated** (checkbox per milestone + 1-line notes). Keep `make check` green at every commit.
11. **Secrets never in git.** `.env.example` is committed; `.env` is gitignored. Mapbox token stays server-side only.
12. **Every assumption goes in the README "Assumptions" section.** Reviewers reward explicit, sensible assumptions.
13. **Honesty.** Never write "tests pass", "deployed", or "works" unless the command was actually run and its exit status confirmed. Never fabricate routes, weather, forecast coverage, or results. Mock/demo data is always labelled (e.g. "SIMULATED"). Never present output as certified safety guidance.
14. **Handoff report after every milestone:** (1) summary, (2) exact files touched, (3) commands run + real results, (4) known limitations/assumptions, (5) remaining work + time estimate, (6) confirmation that no secrets/unrelated changes were added.
15. **Phase 0 is not a stop-and-wait.** Inspect the repo (`git status`, manifests) in ≤15 min. If it is empty, scaffold (M0) and continue. Stop only for missing secrets/credentials.
16. **Multiple agents (optional):** Planner/Reviewer, Backend, Frontend, Integration-Reviewer. Define API schemas + shared enums (Risk names, units, timestamp semantics) FIRST; never edit the same file in parallel; integrate early. One agent = same phases sequentially.

---

## 1. Mission and success criteria

Build a **React + Django** web app that helps a truck driver pick the safest route using **weather, load weight, and travel time**.

**User inputs:** origin, destination, departure date/time, load weight.

**App must:**
1. Generate **3 route options** via a routing API.
2. Sample weather at checkpoints every **10 / 25 / 50 miles** (user-selectable), using the truck's **ETA at each checkpoint**.
3. Compute weather risk with the provided thresholds + load rules.
4. **Recommend** the best route (weather risk first, then time).
5. Show all routes, checkpoints, risk levels, ETAs, route summaries **on a map**.
6. Show a **weather heatmap along the trip corridor** with a **0–48 h forecast slider**.

**Grading weights → where effort goes**

| Weight | Area | What wins it |
|---|---|---|
| 40% | Routes, weather, risk, recommendation logic | Exact thresholds, boundary handling, ETA-correct weather, correct mile accounting, deterministic ranking, unit tests |
| 35% | UI, map & heatmap smoothness/performance | Layer-based map (no DOM markers), instant slider (no network on drag), skeleton/loading/error states |
| 10% | Code quality | Layered architecture, typed, tested, linted |
| 5% | Docs & Loom | Clear README + assumptions + 7-min walkthrough |

---

## 2. Locked decisions

| Concern | Decision | Why |
|---|---|---|
| Frontend | **Vite + React 18 + TypeScript (strict)** | Fast, typed |
| Styling | **Tailwind CSS** | Speed, consistency |
| Server state | **TanStack Query** | Cancellation, caching, retry |
| UI state | **Zustand** (selected route, hour, metric, interval, heatmap on/off) | Tiny, no boilerplate |
| Forms | **react-hook-form + zod** | Validation w/ clear messages |
| Map | **MapLibre GL JS via `react-map-gl/maplibre`**, basemap **Carto Positron** style (`https://basemaps.cartocdn.com/gl/positron-gl-style/style.json`, keyless; env-overridable) | GPU layers, native heatmap layer, no map token |
| Backend | **Django (latest stable LTS) + Django REST Framework** | Required |
| HTTP client | **httpx** (sync) + `ThreadPoolExecutor` for parallel calls | Simple, robust under gunicorn gthread |
| Routing | **Mapbox Directions API** (`driving` profile, `alternatives=true`) behind a `RoutingProvider` interface; **OSRM** adapter as keyless fallback | Reliable alternatives, geojson geometry, per-segment annotations |
| Geocoding | **Mapbox Geocoding v6** proxied through Django (`/api/geocode`) | Token stays server-side, cached |
| Weather | **Open-Meteo Forecast API** (no key), multi-location batch, hourly, mph/inch units | Free, hourly 16-day, batch |
| Time zones | **`timezonefinder`** + stdlib `zoneinfo` | Departure is interpreted in the *origin's* local time |
| Polyline | `polyline` package (precision 6) | Pass corridor to heatmap endpoint |
| Cache | Django `LocMemCache` (no Redis, no DB) | Stateless, enough for demo |
| Testing | `pytest`, `pytest-django`, `respx` (mock httpx); `vitest` + Testing Library | |
| Lint/format | `ruff` (lint+format), `mypy` (domain + services), `eslint`, `tsc --noEmit` | |
| Deploy | **Single Docker service**: multi-stage build (node → python), Django serves API + built SPA via WhiteNoise. Target: Render (or Railway/Fly). Keep-alive ping on `/api/health` | One URL, no CORS, simplest to evaluate |

**Env vars**

| Var | Used by | Default / note |
|---|---|---|
| `DJANGO_SECRET_KEY` | backend | required in prod |
| `DJANGO_DEBUG` | backend | `0` in prod |
| `DJANGO_ALLOWED_HOSTS` | backend | comma list |
| `MAPBOX_TOKEN` | backend | required for routing+geocoding (secret, server-side) |
| `ROUTING_PROVIDER` | backend | `mapbox` (auto-falls back to `osrm` on 5xx/timeout) |
| `GEOCODE_COUNTRIES` | backend | `us,ca` |
| `TRUCK_MAX_AVG_SPEED_MPH` | backend | `62` |
| `WEATHER_CACHE_TTL_S` | backend | `1800` |
| `VITE_MAP_STYLE_URL` | frontend | Carto Positron URL |

---

## 3. Domain rules (verbatim from the assessment) + interpretation

### 3.1 Thresholds

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | <25 | 25–34 | 35–44 | 45–54 | ≥55 |
| Rain (in/hr) | <0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow (in/hr) | <0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

### 3.2 Load rules
- Wind **≥55 mph → No Travel** for any load.
- Wind **45–54 mph AND load >30,000 lb → No Travel**.
- Wind **35–44 mph AND load >40,000 lb → Severe**.

### 3.3 Recommendation preference (in order)
1. Fewest **Severe** miles → 2. Fewest **High** miles → 3. Lowest **average risk** → 4. **Shortest travel time**.

### 3.4 Interpretation decisions (LOCKED — put in README "Assumptions")

- **A1 Boundaries (half-open, lower-bound inclusive; the more conservative reading).** The table's ranges touch at endpoints. Because the spec writes Low as `<25`, `<0.10`, `<0.5` (strict), a value exactly on a boundary belongs to the **higher** class. Only the No-Travel edge for rain/snow is the spec's explicit strict `>`.
  - Wind: Low `<25`; Moderate `[25,35)`; High `[35,45)`; Severe `[45,55)`; No Travel `≥55`.
  - Rain: Low `<0.10`; Moderate `[0.10,0.25)`; High `[0.25,0.50)`; Severe `[0.50, 1.00]`; No Travel `>1.00`.
  - Snow: Low `<0.5`; Moderate `[0.5,1.0)`; High `[1.0,2.0)`; Severe `[2.0, 3.0]`; No Travel `>3.0`.
  - **No rounding before comparison** (rounding would turn `24.99` into `25.0` or `0.099` into `0.10` and break boundary tests). Compare the parsed values as-is; they come from JSON decimals, not arithmetic.
- **A2 Wind metric.** Use **sustained 10 m wind speed** (`wind_speed_10m`). Gusts are returned and **displayed** (checkpoint popup/table, labelled "gust") but not classified (config flag `WIND_METRIC=sustained|gust` exists in domain settings; default sustained). README must state this is a **deliberate, conscious design choice**: classification follows the assessment's wind thresholds on sustained speed; gusts are shown for driver awareness.
- **A3 Rain** = `rain + showers` (liquid; hourly values at 1-hour steps are in/hr rates, never accumulations over longer windows). **Snow** = `snowfall` (in/hr, inch unit requested). Wind in mph.
- **A4 Checkpoint risk** = max over {wind, rain, snow} after applying load rules. Load rules only *escalate*, never reduce.
- **A5 "Every 10 / 25 / 50 miles"** = user-selectable interval (default 25). Checkpoints at mile 0, I, 2I, … plus the destination. A regular checkpoint closer than `0.25*I` to the destination is dropped.
- **A6 Miles per risk level.** Each checkpoint "owns" the stretch from the midpoint to its previous checkpoint to the midpoint to its next one (origin starts at 0, destination ends at total). Severe/High/etc. miles = sum of owned lengths with that level.
- **A7 Average risk** = distance-weighted mean of risk scores (Low=0, Moderate=1, High=2, Severe=3, No Travel=4) over **known** miles only. Unknown miles are excluded from the mean and reported separately (`unknown_miles`).
- **A8 No Travel handling (safety veto).** A route with any No Travel checkpoint is `blocked`. `blocked` routes always rank below unblocked ones, then `no_travel_miles` comes **before** Severe in the key. **A blocked route is never `recommended`.** If every route is blocked: `recommended_route_id = null`, `least_risk_route_id` = best-ranked route (UI label: "Least-risk comparison — not safe to travel"), plus advisory "consider delaying departure".
- **A9 Ranking key (all ascending):** `(blocked, round(no_travel_mi), round(severe_mi), round(high_mi), round(avg_risk,2), round(unknown_mi), round(duration_min), route_id)`. Rounding (1 mile / 0.01 / 1 minute) makes the order transitive and stops float noise from deciding the winner; `route_id` is the stable final tie-breaker. Fewer unknown miles is preferred before duration because less-certain routes are less comparable.
- **A10 ETA.** Cumulative driving time from route annotations (per-segment duration), each segment capped so the truck never exceeds `TRUCK_MAX_AVG_SPEED_MPH` (`seg_seconds = max(api_seconds, seg_miles/62*3600)`). **No rest breaks / HOS** modeled (state in README limitations).
- **A11 Weather at ETA.** Linear interpolation between the two bracketing hourly values; if either bracketing value is missing → `None`. If ETA is beyond the fetched series → status `out_of_horizon`, values `None` (**never clamp or extrapolate**), plus a warning.
- **A12 Departure time zone.** The `datetime-local` value is interpreted in the **origin's** time zone (resolved server-side). All ETAs are returned as UTC + each checkpoint's local time + IANA tz.
- **A13 Heatmap slider** = hours after departure hour (0–48), i.e., "what is the weather at each corridor point at departure+N h". It classifies with the same rules and the same load weight.
- **A14 Load weight** validated `0 < lb ≤ 100,000`.
- **A15 Departure window** validated `now−2h ≤ departure ≤ now+10 days` (forecast horizon safety). **The backend is the final authority**: it localizes the naive `departure_local` in the origin's time zone, converts to UTC, then validates the window. The browser only does a loose sanity check (see 6.2) because it cannot know the origin's time zone.
- **A16 UNKNOWN state.** Missing/out-of-horizon weather yields risk `UNKNOWN` (represented as `None` in code, `"UNKNOWN"` in the API, `-1` in heatmap arrays). It is **never Low and never 0**. A known veto is never lowered by missing data: if any known condition is No Travel, the checkpoint is No Travel.
- **A17 Safety disclaimer.** Output is informational, not certified trucking guidance; forecasts can be incomplete; drivers must follow official restrictions and company policy. Shown in the UI footer and README.

---

## 4. Architecture

### 4.1 Layers (dependencies point inward only)

```
Interface (DRF views, serializers)        ← HTTP only
Application services (analyze, heatmap)   ← orchestration, parallelism, caching
Adapters (routing, weather, geocoding)    ← 3rd-party APIs behind interfaces
Domain (geo, risk, aggregate, recommend)  ← PURE Python, no I/O
```

### 4.2 Request flow

```
POST /api/analyze
 → validate → resolve origin tz → localize departure → UTC
 → RoutingProvider.get_routes()  (≤1 base call + ≤6 bounded augment calls, parallel)
 → per route: RoutePath (coords, cum_miles, cum_seconds)
 → resample checkpoints (I miles) → ETA per checkpoint
 → WeatherProvider.fetch(cells, start_hour, hours)  (deduped, batched, cached, parallel)
 → interpolate at ETA → assess (thresholds + load rules)
 → aggregate per route → rank → recommend → explanation
 → response (+ ready-made heatmap_request)

POST /api/heatmap   (called by the frontend right after analyze, shows routes first)
 → corridor points (route samples + lateral offsets) → cells
 → WeatherProvider.fetch(cells, start_hour, 49h)  (cache hits for shared cells)
 → per point per hour: risk/wind/rain/snow arrays
 → response (compact JSON, gzip)
```

### 4.3 Repo layout

```
.
├── AGENTS.md  PROGRESS.md  README.md  Makefile  Dockerfile  render.yaml  .env.example
├── .github/workflows/ci.yml         # runs `make check` on push + PR (Python + Node setup, caches)
├── docs/ DECISIONS.md BLOCKERS.md ARCHITECTURE.md (mermaid) LOOM_SCRIPT.md
├── backend/
│   ├── manage.py  requirements.txt  pyproject.toml (ruff, mypy, pytest cfg)
│   ├── config/ {settings.py, urls.py, wsgi.py}
│   ├── trucksafe/
│   │   ├── domain/                 # PURE
│   │   │   ├── models.py           # frozen dataclasses
│   │   │   ├── units.py            # M_PER_MILE=1609.344 etc.
│   │   │   ├── geo.py              # haversine, cumulative, point_at_mile, time_at_mile, bearing, offset, simplify (RDP), overlap
│   │   │   ├── risk.py             # Risk enum, classify_*, apply_load_rules, assess_checkpoint
│   │   │   ├── checkpoints.py      # generate_checkpoint_miles, ownership lengths
│   │   │   ├── aggregate.py        # route metrics
│   │   │   └── recommend.py        # rank_key, rank_routes, explain
│   │   ├── adapters/
│   │   │   ├── routing/ {base.py, mapbox.py, osrm.py, fallback.py}
│   │   │   ├── weather/ {base.py, open_meteo.py, cache.py, storm_overlay.py (optional)}
│   │   │   └── geocoding/ {base.py, mapbox.py}
│   │   ├── services/ {routes_builder.py, analyze.py, heatmap.py, timezones.py, presenters.py}
│   │   └── api/ {views.py, serializers.py, errors.py, urls.py, throttles.py}
│   └── tests/ {unit/, integration/, fixtures/}
└── frontend/
    ├── package.json  vite.config.ts (dev proxy /api → :8000)  tailwind.config.ts  tsconfig.json
    └── src/
        ├── main.tsx  App.tsx
        ├── api/ {client.ts, types.ts, hooks.ts}
        ├── store/ useUiStore.ts
        ├── lib/ {risk.ts, format.ts, geo.ts}
        └── features/
            ├── trip-form/ {TripForm.tsx, LocationInput.tsx, schema.ts}
            ├── routes/ {RouteList.tsx, RouteCard.tsx, CheckpointTable.tsx, RiskBadge.tsx, RiskStrip.tsx}
            ├── map/ {MapView.tsx, layers.ts, useFitBounds.ts, CheckpointPopup.tsx}
            └── heatmap/ {HeatmapControls.tsx, useHeatmapLayer.ts, usePlayback.ts, Legend.tsx}
```

---

## 5. Backend specification

### 5.1 Domain models (frozen dataclasses, `domain/models.py`)

```python
@dataclass(frozen=True) class LatLon: lat: float; lon: float
@dataclass(frozen=True) class RoutePath:
    id: str; coords: list[LatLon]; cum_miles: list[float]; cum_seconds: list[float]
    summary: str; provider: str
    @property total_miles / total_seconds
@dataclass(frozen=True) class Checkpoint: index: int; mile: float; lat: float; lon: float; eta_utc: datetime; owned_miles: float
@dataclass(frozen=True) class WeatherSample: wind_mph: float | None; gust_mph: float | None; rain_in_hr: float | None; snow_in_hr: float | None; status: Literal["available", "missing", "out_of_horizon"] = "available"
@dataclass(frozen=True) class Driver: condition: Literal["wind","rain","snow","load_rule"]; level: Risk; note: str
@dataclass(frozen=True) class Assessment: level: Risk; drivers: list[Driver]
@dataclass(frozen=True) class RouteMetrics:
    distance_mi; duration_min; no_travel_miles; severe_miles; high_miles; moderate_miles; low_miles; unknown_miles; avg_risk (None if all unknown); max_level; blocked
```

### 5.2 Risk core (`domain/risk.py`) — implement EXACTLY this logic

```python
from enum import IntEnum

class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

# UNKNOWN is deliberately NOT a Risk member. An unknown level is `None` everywhere in code.

def classify_wind(mph: float) -> Risk:            # lower-inclusive, half-open (A1)
    if mph >= 55: return Risk.NO_TRAVEL
    if mph >= 45: return Risk.SEVERE
    if mph >= 35: return Risk.HIGH
    if mph >= 25: return Risk.MODERATE
    return Risk.LOW

def _lower_inclusive(v: float, mod_ge: float, high_ge: float, sev_ge: float, nt_gt: float) -> Risk:
    if v > nt_gt:    return Risk.NO_TRAVEL        # spec says strictly ">"
    if v >= sev_ge:  return Risk.SEVERE
    if v >= high_ge: return Risk.HIGH
    if v >= mod_ge:  return Risk.MODERATE
    return Risk.LOW

def classify_rain(in_hr: float) -> Risk:
    return _lower_inclusive(in_hr, 0.10, 0.25, 0.50, 1.00)

def classify_snow(in_hr: float) -> Risk:
    return _lower_inclusive(in_hr, 0.5, 1.0, 2.0, 3.0)

def apply_load_rules(wind_mph: float, load_lb: float, base: Risk) -> tuple[Risk, str | None]:
    if wind_mph >= 55:
        return Risk.NO_TRAVEL, "Wind ≥55 mph: No Travel for any load"
    if 45 <= wind_mph < 55 and load_lb > 30_000:
        return Risk.NO_TRAVEL, "Wind 45–54 mph with load >30,000 lb: No Travel"
    if 35 <= wind_mph < 45 and load_lb > 40_000:
        return max(base, Risk.SEVERE), "Wind 35–44 mph with load >40,000 lb: Severe"
    return base, None                              # rules only ESCALATE, never lower

def assess_checkpoint(s: WeatherSample, load_lb: float) -> Assessment:
    levels: list[Risk] = []
    drivers: list[Driver] = []
    missing = False
    if s.wind_mph is None:
        missing = True
    else:
        base = classify_wind(s.wind_mph)
        adjusted, note = apply_load_rules(s.wind_mph, load_lb, base)
        levels.append(adjusted)
        drivers.append(Driver("wind", base, f"{s.wind_mph:.0f} mph"))
        if note:
            drivers.append(Driver("load_rule", adjusted, note))
    for name, value, fn in (("rain", s.rain_in_hr, classify_rain), ("snow", s.snow_in_hr, classify_snow)):
        if value is None:
            missing = True
            continue
        lvl = fn(value)
        levels.append(lvl)
        drivers.append(Driver(name, lvl, f"{value:.2f} in/hr"))
    top = max(levels, default=None)
    if top == Risk.NO_TRAVEL:
        level = top            # a known veto is never lowered by missing data
    elif missing:
        level = None           # UNKNOWN: never silently LOW
    else:
        level = top
    return Assessment(level, drivers)
```

Mandatory unit tests (parametrized) — see Section 10.1.

### 5.3 Geometry (`domain/geo.py`)

- `haversine_miles(a, b)`; `cumulative_miles(coords)`.
- `point_at_mile(coords, cum_miles, m) -> LatLon` using `bisect` + linear interpolation inside the segment.
- `time_at_mile(cum_miles, cum_seconds, m) -> float` (same method).
- `bearing(a, b)`, `offset_point(p, bearing_deg, miles)` (spherical destination formula) for lateral heatmap points and via-waypoints.
- `rdp_simplify(coords, tolerance_deg)` for display geometry (target ≤ 3,000 points per route; analysis always uses the full-resolution path).
- `overlap_fraction(a, b, max_dist_miles=1.25)` : sample A at 60 evenly spaced points; fraction whose nearest B-sample (200 samples) is within the distance.

### 5.4 Checkpoints and mile ownership (`domain/checkpoints.py`)

```python
def checkpoint_miles(total: float, interval: float) -> list[float]:
    ms = [0.0]; m = interval
    while m < total - 0.25 * interval:
        ms.append(m); m += interval
    ms.append(total)
    return ms     # first=0, last=total, strictly increasing

def owned_lengths(ms: list[float]) -> list[float]:
    # bounds: 0, midpoints..., total
    b = [ms[0]] + [(ms[i] + ms[i+1]) / 2 for i in range(len(ms) - 1)] + [ms[-1]]
    return [b[i+1] - b[i] for i in range(len(ms))]   # sums to total
```
Invariant tests: `sum(owned) == total` (±1e-9); ≥2 checkpoints always.

### 5.5 Aggregation + recommendation

```python
def aggregate(levels: list[Risk | None], owned: list[float], duration_min: float, distance_mi: float) -> RouteMetrics:
    miles = {r: 0.0 for r in Risk}
    unknown = 0.0
    for lvl, m in zip(levels, owned):
        if lvl is None: unknown += m
        else: miles[lvl] += m
    known = distance_mi - unknown
    avg = (sum(int(l) * m for l, m in zip(levels, owned) if l is not None) / known) if known > 0 else None
    blocked = any(l == Risk.NO_TRAVEL for l in levels)
    ...  # build RouteMetrics (unknown_miles=unknown, avg_risk=avg, blocked=blocked)
```

```python
def rank_key(m: RouteMetrics, route_id: str):
    return (m.blocked, round(m.no_travel_miles), round(m.severe_miles), round(m.high_miles),
            round(m.avg_risk, 2) if m.avg_risk is not None else 9.0,
            round(m.unknown_miles), round(m.duration_min), route_id)
```
`rank_routes` sorts by `rank_key`. `recommended_route_id` = first route with `blocked == False`, else `null`. When all are blocked, `least_risk_route_id` = first ranked route (never labelled "recommended").

`explain()` is a pure function returning **fixed templates** (no free-form text). `D` = deciding criterion = the first key field (after `blocked`) where the best route differs from the runner-up.

| Case | Template |
|---|---|
| D = no_travel/severe | `Recommended: {a} severe miles vs {b} on {RunnerUp}.` |
| D = high | `Recommended: same severe miles as {RunnerUp}, but {a} high miles vs {b}.` |
| D = avg risk | `Recommended: same severe and high miles as {RunnerUp}, lower average risk ({a:.2f} vs {b:.2f}).` |
| D = unknown/duration | `Recommended: same weather exposure as {RunnerUp} and {n} min faster.` |
| Only one route | `Only one route available; highest risk level on route: {LEVEL}.` |
| Suffix (best is not fastest) | ` It is {n} min slower than the fastest route ({Label}).` |
| Suffix (best is fastest) | ` It is also the fastest route.` |
| Blocked route card (not recommended) | `Not recommended: {x} No Travel miles (first at mile {m}: {driver note}).` |
| Route with unknown miles | `Forecast unavailable for {u} miles; compared on known miles only.` |
| All blocked (global advisory) | `No route is safe under the supplied rules at this departure time. {Label} has the fewest No Travel miles ({x}). Consider delaying departure.` |

Numbers are formatted with 0 decimals for miles (1 for avg risk 2) and whole minutes. A blocked route's `recommendation_reason`/`explanation` must never contain the word "Recommended".

### 5.6 Routing adapters

Interface:
```python
class RoutingProvider(Protocol):
    def get_routes(self, origin: LatLon, dest: LatLon, waypoints: list[LatLon] | None = None) -> list[RawRoute]: ...
```
`RawRoute`: `coords: list[LatLon]`, `distance_m`, `duration_s`, `seg_durations_s: list[float] | None`, `summary: str`.

**Mapbox** — `GET https://api.mapbox.com/directions/v5/mapbox/driving/{lon},{lat};{lon},{lat}` with `alternatives=true&geometries=geojson&overview=full&steps=false&annotations=distance,duration&access_token=…`.
- Verify real response shape once → save fixture. Per-segment `legs[*].annotation.duration` concatenated across legs must have `len == len(coords)-1`, otherwise fall back to scaling total duration by distance.
- **Payload size:** use `steps=false` (steps on 1,500+ mile routes can be several MB and slow). Route name: use `legs[0].summary` **only if the response actually provides a non-empty one** (join legs for via-routes → `via {summary}`); otherwise label simply **"Route A / Route B / Route C"**. Do NOT re-request with `steps=true` just for a name. Record in `docs/PROVIDER_NOTES.md` what the real response returned.

**OSRM** — `GET {base}/route/v1/driving/{lon},{lat};{lon},{lat}?alternatives=3&overview=full&geometries=geojson&annotations=duration,distance`. Car profile; fallback and dev only.

**Fallback wrapper**: Mapbox on 5xx/timeout/network error → OSRM; add warning `"Primary router unavailable; used fallback (car profile)."`. 401/422 are NOT retried (config/user errors).

**Ensuring 3 routes (`services/routes_builder.py`) — bounded, no loops:**
1. Call provider once. De-duplicate with `overlap_fraction ≥ 0.98` (identical routes).
2. If < 3 distinct: generate up to **6** via-candidates in parallel: for fractions `[0.5, 0.35, 0.65]` × sides `[+1, −1]`, point = path point at that fraction offset perpendicular by `clamp(0.08*total_miles, 10, 40)` miles. Request `origin→via→dest`.
3. Accept candidate if: `overlap_fraction vs every kept route < 0.90`, `duration ≤ 1.5×fastest`, `distance ≤ 1.5×fastest`. Sort accepted by duration and take until 3.
4. Still < 3 → return what exists + warning `"Only N distinct routes available for this trip."` (UI shows it). Never exceed 7 provider calls total.

Validation: reject `origin≈dest` (<0.5 mi) and `total > 4,000 mi` (422).

### 5.7 Weather adapter (`adapters/weather/open_meteo.py`)

```
GET https://api.open-meteo.com/v1/forecast
  ?latitude=a,b,c&longitude=x,y,z
  &hourly=wind_speed_10m,wind_gusts_10m,rain,showers,snowfall
  &wind_speed_unit=mph&precipitation_unit=inch&timezone=GMT
  &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
Rules:
- **Single location returns an object, multiple returns a list** — normalize both.
- **Assert `hourly_units`**: wind `mp/h`, rain/showers/snowfall `inch`. Mismatch → raise `WeatherUnitError` (never silently misclassify). Verify real unit strings from the fixture.
- Times are naive UTC (`timezone=GMT`); parse as UTC.
- `null` values → `None` (status `missing`), **never 0.0**; count gaps and surface a warning.
- Chunk **≤100 locations/request**, up to 6 threads, timeout 10 s, **2 retries** with exponential backoff on 429/5xx/timeouts. Persistent failure → `WeatherUnavailable` (502). **Never fabricate weather.**
- **Cells:** snap lat/lon to 0.05° grid (`round(x/0.05)*0.05`), query the cell center. All checkpoints/heatmap points that share a cell share a data series.
- **Cache key:** `(cell_lat, cell_lon, start_date, end_date)`; TTL `WEATHER_CACHE_TTL_S`.
- Date window: `start = floor_hour(dep_utc)`, `hours = max(49, ceil(longest_route_h) + 3)`; `end_date` derived from that. Series object: `start_utc`, arrays of length N.
- `interpolate(series, t_utc) -> WeatherSample` implements A11.
- **`forecast_available_until`** (response field) = `min( last_valid_hour , now_utc + 16 days )`, where `last_valid_hour` is the latest hourly timestamp for which **all required variables are non-null** in the fetched series; across cells use the **minimum** over the cells actually used (conservative). `null` only if no valid hour exists. The UI shows it in the summary row, and checkpoints/heatmap hours after it show "forecast unavailable".
- Attribution required in UI footer: "Weather data by Open-Meteo.com (CC BY 4.0)".

### 5.8 Geocoding adapter
`GET /api/geocode?q=<text>` → Mapbox v6 forward (`autocomplete=true&limit=5&country={GEOCODE_COUNTRIES}`) → `[{label, lat, lon}]`. Min 3 chars, cache 24 h, throttled.

### 5.9 Time zones (`services/timezones.py`)
`tz_at(lat, lon) -> ZoneInfo` via `timezonefinder` (instantiate **once at module import**, never per request or per checkpoint; if the import/lookup fails or returns `None`, fall back to an **approximate fixed offset** `timezone(timedelta(hours=round(lon/15)))` (no DST), log a warning, and add the response warning "Time zone approximated"). `localize(naive_dt, tz)` → UTC. Checkpoint local times via `tz_at(checkpoint)`; compute only once per checkpoint.

### 5.10 API contract

All errors: `{"error": {"code": "...", "message": "human readable", "details": {...}}}`
Codes: `VALIDATION_ERROR 400`, `NO_ROUTE_FOUND 422`, `ROUTE_TOO_LONG 422`, `RATE_LIMITED 429`, `ROUTING_FAILED 502`, `WEATHER_UNAVAILABLE 502`, `INTERNAL_ERROR 500`.

**`GET /api/health`** → `{"status":"ok"}`.

**`POST /api/analyze`**
```json
{
  "origin":      {"label": "Dallas, TX", "lat": 32.78, "lon": -96.80},
  "destination": {"label": "Denver, CO", "lat": 39.74, "lon": -104.99},
  "departure_local": "2026-10-14T08:00",
  "load_weight_lb": 42000,
  "checkpoint_interval_miles": 25,
  "simulate_storm": false
}
```
Response:
```json
{
  "request_id": "uuid",
  "departure_utc": "2026-10-14T13:00:00Z",
  "origin_tz": "America/Chicago",
  "load_weight_lb": 42000,
  "checkpoint_interval_miles": 25,
  "recommended_route_id": "r2",
  "least_risk_route_id": null,
  "forecast_available_until": "2026-10-30T00:00:00Z",
  "advisory": null,
  "warnings": [],
  "routes": [{
    "id": "r1", "label": "Route A", "summary": "via I-35 N, US-287 N",
    "rank": 2, "recommended": false, "explanation": "…",
    "distance_miles": 801.4, "duration_minutes": 760,
    "geometry": {"type": "LineString", "coordinates": [[lon, lat], "…"]},
    "metrics": {"no_travel_miles": 0, "severe_miles": 12.5, "high_miles": 40.0,
                "moderate_miles": 120.2, "low_miles": 628.7, "unknown_miles": 0,
                "avg_risk": 0.42, "max_level": "SEVERE", "blocked": false},
    "checkpoints": [{
      "index": 0, "mile": 0, "lat": 32.78, "lon": -96.80,
      "eta_utc": "2026-10-14T13:00:00Z", "eta_local": "2026-10-14T08:00:00-05:00", "tz": "America/Chicago",
      "owned_miles": 12.5,
      "weather": {"wind_mph": 14.2, "gust_mph": 22.0, "rain_in_hr": 0.0, "snow_in_hr": 0.0, "status": "available"},
      "risk": {"level": "LOW", "score": 0,
               "drivers": [{"condition": "wind", "level": "LOW", "note": "14 mph"}]}
    }]
  }],
  "heatmap_request": {"routes": [{"id": "r1", "polyline": "<polyline6>"}],
                      "departure_utc": "…", "load_weight_lb": 42000, "simulate_storm": false},
  "meta": {"timings_ms": {"routing": 0, "weather": 0, "risk": 0, "total": 0}, "providers": {"routing": "mapbox", "weather": "open-meteo"}}
}
```
Routes are returned **sorted by rank**; `geometry` is RDP-simplified for display.

**`POST /api/heatmap`** body = `heatmap_request` echoed unchanged by the frontend.
```json
{
  "start_utc": "2026-10-14T13:00:00Z", "hours": 49,
  "points": [{"lat": 33.1, "lon": -97.0,
              "risk": [0,0,1,"…49 ints"], "wind": [14.2,"…"], "rain": [0.0,"…"], "snow": [0.0,"…"]}],
  "meta": {"point_count": 612, "spacing_miles": 10}
}
```
Rain/snow rounded to 0.01, wind to 0.1. Missing/out-of-horizon hours: `risk = -1` and `null` in the value arrays (never 0). Enable `GZipMiddleware`.

Checklist for nullable weather fields in `/api/analyze`: `wind_mph`, `gust_mph`, `rain_in_hr`, `snow_in_hr` may be `null` with `status` ∈ `available | missing | out_of_horizon`; `risk.level` may be `"UNKNOWN"`.

Corridor construction: for each route, sample every `S = max(10, total_miles/120)` miles; add lateral points ±`HEATMAP_LATERAL_MILES` (default 10) perpendicular to local bearing; snap to cells; dedupe; cap 700 cells (increase `S` until under cap). No loops: compute `S` in closed form from total sample count.

**`GET /api/geocode`** as in 5.8.

### 5.11 Platform concerns
- DRF throttles: anonymous 60/min global, `/api/analyze` 12/min, `/api/heatmap` 12/min.
- Structured logging (JSON-ish) with `request_id` and per-stage timings.
- Security headers via Django defaults, `SECURE_*` in prod, `ALLOWED_HOSTS` from env.
- WhiteNoise serves `frontend/dist`; catch-all view returns `index.html` for non-`/api/` paths.
- `gunicorn config.wsgi --workers 1 --threads 4 --timeout 60` — **one worker** because `LocMemCache` is per-process (two workers would halve the cache hit rate and make the heatmap/analyze cache inconsistent). Document this limitation in the README (Redis would be the next step for multi-worker).

---

## 6. Frontend specification

### 6.1 UX layout
- **Desktop:** fixed left panel (≈400 px): Trip form → Results (route cards). Map fills the rest. Heatmap control bar floats bottom-center over the map.
- **Mobile:** map on top, bottom sheet for form/results; heatmap controls above the sheet.
- Footer: attribution (Open-Meteo, Carto, OpenStreetMap contributors, Mapbox routing/geocoding) + safety disclaimer (A17).

### 6.2 Trip form
- `LocationInput`: accessible combobox (arrow keys/Enter/Esc), 300 ms debounce, calls `/api/geocode`, aborts stale requests, stores `{label, lat, lon}`.
- Departure: `<input type="datetime-local">`, helper text "Interpreted in the origin's local time". Default = next full hour.
- Load weight: number input (lb) with quick presets (20k / 35k / 45k / 60k).
- Checkpoint interval: segmented control **10 / 25 / 50 mi** (default 25).
- zod validation is **loose and client-side only**: required fields, numeric weight (A14), interval ∈ {10,25,50}, origin ≠ destination, and a loose departure sanity window (`browser now − 26 h … now + 11 days`, because the browser does not know the origin's time zone). **The backend is the final authority** (A15); map backend `VALIDATION_ERROR.details` to inline field errors. Submit disabled while pending.
- Submit → `useAnalyze` mutation (AbortController on resubmit). On success → store result, auto-select recommended route, `fitBounds`, trigger `useHeatmap` with `heatmap_request`.

### 6.3 Results panel
- **Route cards** (sorted by rank): label, "Recommended" badge, `via` summary, distance, duration (`13 h 05 m`), ETA at destination (destination-local), delta vs fastest ("+22 min"), metrics chips (No Travel / Severe / High / Unknown miles, avg risk), a **RiskStrip** (thin SVG bar showing the risk level across the route, proportional to owned miles), and the one-line `explanation`.
- Selecting a card selects the route on the map (and vice versa).
- **CheckpointTable** (expandable under the selected card): mile, ETA (local, with tz abbreviation), wind / rain / snow, risk badge, drivers on hover/expand. Virtualize only if >150 rows (otherwise plain).
- Banners: `advisory` (all routes blocked), `warnings[]`, "Only N distinct routes available".
- States: idle empty-state, loading skeleton with stage text, error with retry, partial (routes ready, heatmap loading spinner).

### 6.4 Map (MapLibre) — performance rules
- **No DOM markers.** Everything is GeoJSON sources + layers.
- Sources/layers (bottom → top): `heatmap` → `routes-casing` (white, wide) → `routes-line` (data-driven color/width/opacity) → `checkpoints` circles (colored by risk score, larger for the selected route; others small/low-opacity) → selected-route labels.
- Route identity colors (color-blind-safe, distinct from risk colors): A `#1f77b4` blue, B `#7b4fd6` violet, C `#00a6a6` teal. Recommended route gets a thicker line + star badge on its card.
- Risk colors: Low `#2e9e5b`, Moderate `#f2c230`, High `#f28c28`, Severe `#d93636`, No Travel `#3b0a45` (always paired with text/icon, never color-only).
- Interactions: click route line selects route; click checkpoint opens a popup (ETA, weather values, risk, drivers); hover cursor pointer; `fitBounds` with left padding for the panel.
- Memoize GeoJSON with `useMemo`; update sources only when data changes; lazy-load the map chunk (`React.lazy`) to keep initial bundle small.

### 6.5 Heatmap + slider
- Control bar: **range slider 0–48 (step 1)**, label `+12 h · Tue 8:00 PM` (origin-local time), play/pause (advance 1 h every 400 ms, loop at 48), metric chips **Risk / Wind / Rain / Snow**, legend, on/off toggle.
- **Zero network on slider drag.** `/api/heatmap` returns all 49 hours once.
- Build the heat GeoJSON **once per (data, metric)** with per-hour properties `h0 … h48` (normalized value for the active metric: risk/4, wind/55, rain/1.0, snow/3.0, clamped 0..1). Slider changes call `map.setPaintProperty('heat-layer', 'heatmap-weight', ['get', 'h' + hour])` throttled with `requestAnimationFrame`. No `setData` on drag.
- Heatmap layer: `heatmap-radius` interpolated by zoom (≈ z4: 18 px → z8: 40 → z12: 90), `heatmap-opacity` 0.75, color ramp from density: transparent → yellow → orange → red → deep purple. Low weather = transparent (state this in the legend; also state "smoothed visualization between sampled points, not extra observations"). Points with risk `-1` render as gray "no data" circles with weight 0 and tooltip "forecast unavailable" — never as Low. A faint small circle layer shows the sampled points (zoom ≥ 6) so calm areas don't look "missing".
- Heatmap uses the same risk logic/load weight as route risk (computed server-side).
- **Density overlap control:** keep corridor sample spacing uniform (same `S` for all routes), weights normalized to 0..1, `heatmap-intensity` constant. Shared cells are deduped server-side so overlapping routes do not double-weight.
- **Fallback (`VITE_HEATMAP_MODE=heat|blur`, default `heat`):** if the density heatmap looks wrong (cluster saturation, muddy colors), switch to a **blurred-circle layer**: `circle` layer, `circle-color` stepped by risk score, `circle-radius` interpolated by zoom to cover the spacing, `circle-blur` ≈ 1, `circle-opacity` ≈ 0.55, hour driven by the same `['get','h'+hour]` expression. Both modes share the same data and slider code.

### 6.6 State and data
- `useUiStore`: `selectedRouteId`, `hour`, `metric`, `heatmapOn`, `playing`.
- React Query for `geocode`, `analyze` (mutation), `heatmap` (query keyed by `request_id`, `staleTime: Infinity`).
- Types in `api/types.ts` mirror Section 5.10 exactly. Parse defensively (optional chaining on non-critical fields).
- Formatting helpers in `lib/format.ts`: miles (1 decimal), duration, local time via `Intl.DateTimeFormat(undefined, {timeZone: tz, …})`.

### 6.6.1 Accessibility
Keyboard-operable form/combobox/slider, visible focus, `aria-live="polite"` for result status, risk never color-only, contrast ≥ 4.5:1.

---

## 7. Performance budgets (verify and mention in README)

| Metric | Target |
|---|---|
| `/api/analyze`, 500-mi trip, cold cache | p95 < 8 s |
| Same, warm cache | < 3 s |
| `/api/heatmap` payload | < 400 KB gzip |
| Slider drag | no network; ≥ 55 fps on a mid laptop |
| Initial JS (excluding map chunk) | < 200 KB gzip |
| Provider calls per analyze | routing ≤ 7, weather ≤ ceil(cells/100) |

---

## 8. Edge cases (each must have a test or documented handling)

| Case | Handling |
|---|---|
| Origin ≈ destination | 400 `VALIDATION_ERROR` |
| No drivable route / geocode outside coverage | 422 `NO_ROUTE_FOUND` |
| Route > 4,000 mi | 422 `ROUTE_TOO_LONG` |
| Router returns 1–2 routes | via-augment (bounded), else warning |
| Duplicate routes | de-dupe (A: overlap ≥ 0.98) |
| Departure in past > 2 h or > 10 days ahead | 400 with clear message |
| DST transition / ambiguous local time | `zoneinfo` fold=0; documented |
| ETA beyond forecast series | status `out_of_horizon`, risk UNKNOWN, warning; never extrapolate |
| Open-Meteo single vs multi-location JSON shape | normalized in adapter |
| Open-Meteo null values | → `None` / UNKNOWN + warning count (never 0) |
| Unit mismatch in response | raise, 502, never classify |
| Weather API 429/5xx | retry ×2 w/ backoff then 502 `WEATHER_UNAVAILABLE` |
| Mapbox 5xx/timeout | OSRM fallback + warning |
| All routes blocked | `recommended_route_id = null`, `least_risk_route_id` set, advisory; UI never says "recommended" |
| Very short route (< interval) | checkpoints = origin + destination |
| Weight exactly 30,000 / 40,000 | rules use strict `>` |
| User resubmits quickly | cancel previous request (AbortController) |

---

## 9. Testing

### 9.1 Risk boundary tests (parametrized, MUST exist)

| Input | Expected |
|---|---|
| wind 24.99 / 25 / 34.99 / 35 / 44.99 / 45 / 54.99 / 55 | LOW / MOD / MOD / HIGH / HIGH / SEVERE / SEVERE / NO_TRAVEL |
| rain 0.099 / 0.10 / 0.249 / 0.25 / 0.499 / 0.50 / 1.00 / 1.001 | LOW / MOD / MOD / HIGH / HIGH / SEVERE / SEVERE / NO_TRAVEL |
| snow 0.499 / 0.5 / 0.999 / 1.0 / 1.999 / 2.0 / 3.0 / 3.001 | LOW / MOD / MOD / HIGH / HIGH / SEVERE / SEVERE / NO_TRAVEL |
| wind 40, load 40,000 | HIGH |
| wind 40, load 40,001 | SEVERE |
| wind 50, load 30,000 | SEVERE |
| wind 50, load 30,001 | NO_TRAVEL |
| wind 55, load 1 | NO_TRAVEL |
| wind 30, load 90,000 | MODERATE (rule not triggered) |
| wind 40 + rain 0.6, load 10,000 | SEVERE (max of conditions) |
| rain 0.25, load 90,000 | HIGH (load rule never downgrades or alters rain) |
| wind None, rain 0, snow 0 | UNKNOWN (`None`), never LOW |
| wind 60, rain None, snow None | NO_TRAVEL (known veto not lowered by missing data) |
| wind 20, rain 0.30, snow None | UNKNOWN (missing input, no veto) |

### 9.2 Domain tests
- `checkpoint_miles`: first 0, last total, increasing, drop-near-end rule; `owned_lengths` sums to total.
- `point_at_mile`/`time_at_mile` on a synthetic straight path with constant speed (exact expectations).
- ETA speed cap applied; fallback when annotations missing.
- `aggregate`: hand-computed miles per level and weighted average.
- `rank_routes`: table-driven cases — severe beats high beats avg beats time; No Travel route loses to Severe route; rounding tie-break; all-blocked.
- `interpolate`: midpoint, exact hour, a `None` bracket → `None`, beyond series → `out_of_horizon` (no clamping/extrapolation).
- `aggregate`: unknown miles excluded from average and reported; all-unknown route → `avg_risk is None`.
- `rank_routes`: blocked route never recommended; all-blocked → `recommended = None`, `least_risk_route_id` set; stable `route_id` tie-break.
- `explain()`: one test per template row above (deciding-criterion variants, only-one-route, blocked card, unknown miles, all-blocked advisory, fastest vs slower suffix); assert blocked explanations never contain "Recommended".
- `rdp_simplify` keeps endpoints; `overlap_fraction` identical = 1.0, disjoint = 0.0.

### 9.3 Adapter tests (recorded fixtures + `respx`)
- Mapbox parse (coords, durations, summary), annotation length mismatch fallback, 5xx → OSRM fallback.
- Open-Meteo single-location and multi-location JSON, unit assertion, null handling, retry/backoff, chunking.

### 9.4 Integration / API tests
- `/api/analyze` golden scenario with mocked providers: three synthetic routes where B has a 40-mile Severe stretch, C has 15 High miles, A is clean but 30 min slower → A recommended with correct explanation; response shape matches contract.
- **Via-waypoint augmentation (dedicated test):** (a) mocked router returns only 1 route → builder issues bounded via-requests and returns 3 distinct routes (pairwise `overlap_fraction` < 0.90, detour ≤ 1.5×); (b) router returns 3 routes of which 2 are duplicates (overlap ≥ 0.98) → duplicates rejected and replaced; (c) via-candidates all rejected/failing → returns the real count (1–2) with warning `"Only N distinct routes available"` and **never** pads with duplicates; (d) assert total provider calls ≤ 7.
- Validation errors, error envelope, throttling disabled in tests.
- `/api/heatmap`: 49-length arrays, point cap, cache hit on second call (assert mocked weather called once).

### 9.5 Optional (only after M6): "Simulate storm" demo toggle
Real weather is often calm, which makes demos boring and the logic unprovable. Add `StormOverlay` wrapping the weather provider when `simulate_storm=true`: a stationary storm at ~45% of the first route, radius 60 mi, peak wind ≈ 48 mph, rain ≈ 0.6 in/hr, smooth falloff and a time envelope peaking ~6 h after departure. UI shows a clear **"SIMULATED"** badge. Default off. Time-box 45 min; skip if behind. **Demo preset (for the Loom):** a small "Load demo trip" button that fills a fixed realistic trip (e.g. Denver, CO → Salt Lake City, UT, 45,000 lb, interval 25) and turns on the simulated-storm toggle so the demo reliably shows Severe/High/No Travel behavior; the preset and storm are always visibly labelled "DEMO / SIMULATED".

### 9.6 Frontend tests (vitest)
- `schema.ts` validation; `format.ts` helpers; `RiskBadge` renders text + icon; slider updates store; hour → expression key `h{n}`; route selection sync.
- Optional Playwright smoke test (form → results → slider) only if time remains.

---

## 10. Quality gates and commands

`Makefile` targets: `install`, `dev` (backend + frontend), `test`, `lint`, `build`, `check`.

```
make check =
  cd backend && ruff check . && ruff format --check . && mypy trucksafe/domain trucksafe/services && pytest -q
  cd frontend && npm run lint && npm run typecheck && npm test -- --run && npm run build
```

---

## 11. Milestones (≈16 h total; each ends with a GATE)

| # | Milestone | Est. | Gate |
|---|---|---|---|
| M0 | Scaffolding: repo, Django+DRF project, Vite+TS+Tailwind, Makefile, lint/test configs, `/api/health`, `.env.example`, PROGRESS.md | 1.0 h | `make check` green; health endpoint works |
| M1 | **Domain core + tests**: models, units, geo, risk, checkpoints, aggregate, recommend | 3.0 h | all Section 9.1–9.2 tests pass; mypy clean |
| M2 | **Adapters**: record real fixtures first; Mapbox, OSRM, fallback, routes_builder, Open-Meteo + cache + interpolation, geocoding, timezones | 2.5 h | **MANDATORY:** real-response fixtures saved in `backend/tests/fixtures/` (Mapbox directions, Mapbox geocode, Open-Meteo single- and multi-location, OSRM) AND `docs/PROVIDER_NOTES.md` lists the real field names/units seen (e.g. Open-Meteo `hourly_units`, Mapbox annotation lengths); parsers written against those fixtures; adapter tests pass; one real smoke call each (manual script, not in CI). If a key is missing, record real keyless fixtures (OSRM + Open-Meteo), log it in `docs/BLOCKERS.md`, and continue. |
| M3 | **Analyze service + API**: orchestrator, presenters, serializers, error envelope, throttles, timings | 1.5 h | golden integration test passes; manual curl with a real trip returns 3 routes |
| M4 | **Frontend core**: form + geocode combobox, results cards, checkpoint table, map routes + checkpoints + popups, states | 3.5 h | end-to-end manual run on a real trip; route/card selection syncs |
| M5 | **Heatmap**: `/api/heatmap`, corridor builder, frontend layer + slider + playback + metric toggle + legend | 2.0 h | slider drag has no network, smooth; payload within budget |
| M6 | Polish + deploy: loading/error states, a11y pass, Docker, Render, keep-alive, perf check; (optional 9.5 storm demo) | 1.5 h | hosted URL works from a clean browser; `make check` green locally **and in GitHub Actions** (README shows the CI badge) |
| M7 | Docs + Loom: README, ARCHITECTURE.md, assumptions, limitations, LOOM_SCRIPT.md | 1.0 h | README checklist (Section 13) complete |

If time runs short: cut the storm toggle, then Playwright, then mobile bottom-sheet polish. **Never cut** domain tests, error states, or the README assumptions.

---

## 12. Deployment

- **Dockerfile (multi-stage):** stage 1 `node` builds `frontend/dist`; stage 2 `python:3.x-slim` installs backend requirements, copies `dist` into `backend/staticfiles/spa`, runs `collectstatic`, starts gunicorn.
- **Render:** web service from Docker, env vars from Section 2, health check path `/api/health`.
- Free tier sleeps: add an external uptime ping (UptimeRobot) every 5 min on `/api/health` and mention a possible 30–50 s cold start in the README.
- Verify in an incognito window: form → analysis → map → heatmap slider.

---

## 13. Documentation deliverables

**README.md must contain:** safety disclaimer (informational only, not certified trucking guidance) + one-paragraph overview + screenshot/GIF; live URL; quick start (`make install`, env, `make dev`); architecture diagram (mermaid) and layer description; API summary; **Risk logic & Assumptions (A1–A15)**; recommendation algorithm with an example; performance notes (cell snapping, batching, cache, heatmap zero-network slider); testing instructions; limitations (no HOS/rest breaks, car-profile routing durations capped for trucks, forecast ≤ 10 days, Open-Meteo resolution, per-process in-memory cache so 1 gunicorn worker); "What I'd do next" (truck-aware router e.g. HERE with gross weight, NWS alerts, departure-time suggestion (propose a safe departure window when all routes are blocked), `drf-spectacular` API schema at `/api/schema/`, Redis cache for multi-worker deploys, Playwright E2E in CI).

**`docs/LOOM_SCRIPT.md` (target 7 min):**
1. 0:00–0:30 Problem and what was built.
2. 0:30–1:30 Live demo: enter trip, load weight, interval.
3. 1:30–3:00 Results: 3 routes, recommendation + explanation, metrics, checkpoint ETAs and weather.
4. 3:00–4:00 Heatmap: slider, play, metrics (use the Simulate storm demo if the real weather is calm, and say it is simulated).
5. 4:00–5:30 Architecture: layers, pure domain core, adapters, ETA-based sampling, mile ownership, ranking rules + boundary assumptions.
6. 5:30–6:30 Testing and performance (show tests, timings, no-network slider).
7. 6:30–7:00 Tradeoffs, limitations, next steps.

---

## 14. Final Definition of Done (check every box)

**Functional**
- [ ] Inputs: origin, destination, departure date/time, load weight, interval (10/25/50)
- [ ] 3 routes shown (or explicit warning if fewer exist)
- [ ] Weather sampled at checkpoints using ETA at each checkpoint
- [ ] Risk uses exact thresholds + boundary decisions + load rules
- [ ] Recommendation follows the 4-step preference (with No Travel veto first), shows an explanation, and a blocked route is never labelled recommended
- [ ] Missing/out-of-horizon weather is UNKNOWN everywhere (API, risk, heatmap, UI) — never Low, never 0
- [ ] Map shows all routes, checkpoints (risk-colored), popups with ETA/weather/risk, route summaries
- [ ] Heatmap along corridor with 0–48 h slider, play, metric toggle, legend

**Quality**
- [ ] Section 9.1 boundary tests all present and green
- [ ] `make check` green locally and in GitHub Actions (CI badge in README); no `any`, no unused code, no TODOs left
- [ ] No secrets in git; Mapbox token server-side only
- [ ] Error envelope everywhere; every Section 8 case handled
- [ ] Performance budgets (Section 7) measured and noted in README

**Delivery**
- [ ] GitHub repo (clean history, conventional commits)
- [ ] Hosted app URL works in incognito
- [ ] README complete (Section 13)
- [ ] Loom 5–10 min recorded
- [ ] Links ready to submit: GitHub + hosted + Loom

---

## 15. Don'ts (common failure modes)

- Don't sample weather at "now"; always at each checkpoint's **ETA**.
- Don't use the route's total duration for every checkpoint; use cumulative per-segment time.
- Don't classify with raw floats (round to source precision first) and don't use `>=` where the spec says `>`.
- Don't let Severe-miles ranking ignore No Travel.
- Don't use DOM markers or `setData` per slider tick.
- Don't call third-party APIs from tests or from the browser (all through Django).
- Don't swallow errors or fabricate fallback weather. Don't substitute 0 for missing data, don't clamp/extrapolate past the forecast, don't label a No-Travel route "recommended".
- Don't round weather values before classifying.
- Don't claim tests pass / app is deployed without having run the command / opened the URL.
- Don't add libraries "just in case"; every dependency must be used.
- Don't forget attribution (Open-Meteo, Carto, OSM).

---

## 16. Enhancement priority (if time is short)

| Phase | Items | Status in this file |
|---|---|---|
| 1 — must (text/clarity, ~20 min) | Top-15 block, `forecast_available_until`, `explain()` templates + tests, backend-final validation, mandatory M2 fixture gate | Done (v3) |
| 2 — quality/performance | `steps=false` Mapbox call, via-augmentation test plan | Done (v3) |
| 3 — if time remains | 1-worker cache rule, timezone fallback, heatmap blur fallback, gust display, GitHub Actions CI, demo preset | Specified; implement during M3–M6 |
| 4 — skip, document only | HERE truck-aware routing, departure-time suggestion, `drf-spectacular` | README "What I'd do next" |

Cut order when behind: demo preset → Playwright → mobile bottom-sheet polish. **Never cut:** domain tests, UNKNOWN handling, error states, README assumptions.
