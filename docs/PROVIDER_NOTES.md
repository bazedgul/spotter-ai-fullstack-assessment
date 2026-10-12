# 3rd-Party Provider Notes & Real Response Signatures

Recorded from live API calls and official specifications for M2 verification.

## 1. Open-Meteo Forecast API (`api.open-meteo.com/v1/forecast`)
- **Single Location Call:**
  - Endpoint: `https://api.open-meteo.com/v1/forecast?latitude=32.78&longitude=-96.80&hourly=wind_speed_10m,wind_gusts_10m,rain,showers,snowfall&wind_speed_unit=mph&precipitation_unit=inch&timezone=GMT`
  - Returns a single JSON dictionary with keys: `latitude`, `longitude`, `generationtime_ms`, `utc_offset_seconds`, `timezone`, `timezone_abbreviation`, `elevation`, `hourly_units`, `hourly`.
- **Multi-Location Call:**
  - Endpoint with comma-separated coordinates: `latitude=32.78,39.74&longitude=-96.80,-104.99`
  - Returns a JSON **list of objects** (each having the shape of a single location result).
- **Observed `hourly_units`:**
  - `'wind_speed_10m': 'mp/h'` (Note the forward slash in `mp/h`)
  - `'wind_gusts_10m': 'mp/h'`
  - `'rain': 'inch'`
  - `'showers': 'inch'`
  - `'snowfall': 'inch'`
  - `'time': 'iso8601'`
- **Data Series Semantics:**
  - Hourly timestamps: UTC formatted `YYYY-MM-DDTHH:00` (e.g., `"2026-10-13T00:00"`).
  - Missing/null values: JSON `null` (mapped to Python `None`, never converted to `0.0`).

## 2. OSRM Driving Router (`router.project-osrm.org/route/v1/driving`)
- **Endpoint:** `https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?alternatives=true&overview=full&geometries=geojson&annotations=duration,distance`
- **Response Shape:**
  - `code`: `"Ok"`
  - `routes`: array of route objects
  - `waypoints`: array of waypoint objects
- **Route Object Fields:**
  - `distance`: total distance in meters (float)
  - `duration`: total duration in seconds (float)
  - `geometry`: GeoJSON object `{"type": "LineString", "coordinates": [[lon, lat], ...]}`
  - `legs`: array of leg objects
    - `legs[0].annotation.duration`: list of segment durations in seconds.
    - `legs[0].annotation.distance`: list of segment distances in meters.
    - **Annotation invariant:** `len(annotation['duration']) == len(coordinates) - 1`.

## 3. Mapbox Directions API v5 (`api.mapbox.com/directions/v5/mapbox/driving`)
- **Endpoint:** `GET https://api.mapbox.com/directions/v5/mapbox/driving/{lon},{lat};{lon},{lat}?alternatives=true&geometries=geojson&overview=full&steps=false&annotations=distance,duration&access_token=...`
- **Parameters:** `steps=false` ensures lightweight payload for 1,500+ mile routes.
- **Route Fields:**
  - `routes[*].distance`: meters
  - `routes[*].duration`: seconds
  - `routes[*].geometry`: GeoJSON LineString
  - `routes[*].legs[*].annotation.duration`: segment durations matching `len(coords) - 1`.
  - `routes[*].legs[0].summary`: street/corridor summary (e.g., `"I-35 N, US-287 N"`).

## 4. Mapbox Geocoding v6 (`api.mapbox.com/search/geocode/v6/forward`)
- **Endpoint:** `GET /search/geocode/v6/forward?q=...&autocomplete=true&limit=5&country=us,ca&access_token=...`
- **Response Shape:**
  - `type`: `"FeatureCollection"`
  - `features[*].properties.full_address` or `name`: human readable location label.
  - `features[*].geometry.coordinates`: `[lon, lat]` (Note GeoJSON order: longitude first, latitude second).
