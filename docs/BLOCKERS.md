# Blockers and Mitigations Log

This document tracks persistent issues (per Rule 4: STOP after 3 different attempts, log, use fallback).

| Issue | Discovered | Attempts | Resolution / Fallback |
|---|---|---|---|
| `MAPBOX_TOKEN` not supplied in environment | Milestone 2 | Checked environment & .env | Fallback implemented: OSRM router (`http://router.project-osrm.org`) used as primary/fallback keyless routing provider per locked spec Section 2 & 5.6. Mapbox adapter gracefully falls back to OSRM when token is absent or returns 401/5xx. Mapbox geocoding falls back to Photon/OSM geocoding if token is absent. |
