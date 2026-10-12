# Progress Tracker — Weather-Aware Truck Routing

- [x] **M0: Scaffolding** — Repo structure, Django+DRF, Vite+React18+TS, Makefile, configs, `/api/health`, `.env.example`, `PROGRESS.md`
- [ ] **M1: Domain Core & Tests** — Pure Python domain (`trucksafe/domain`), models, geo, risk rules, checkpoints, aggregation, recommendation, full boundary test suite
- [ ] **M2: Adapters & Fixtures** — Real API fixtures recorded in `backend/tests/fixtures/`, `docs/PROVIDER_NOTES.md`, Mapbox/OSRM routing adapters + fallback + via-augment, Open-Meteo weather + cache + interpolation, Mapbox geocoding, timezones
- [ ] **M3: Analyze Service & API** — Analyze pipeline orchestrator, presenters, serializers, error envelope, throttles, golden integration test
- [ ] **M4: Frontend Core** — Trip form + geocoding combobox, results cards, checkpoint table, MapLibre routes + checkpoints + popups, selection sync
- [ ] **M5: Heatmap & Slider** — `/api/heatmap`, corridor builder, client-side zero-network slider, playback, metric switch, legend
- [ ] **M6: Polish & Deployment** — Loading/error states, a11y, Docker multi-stage build, CI workflow, simulate storm demo preset
- [ ] **M7: Documentation & Deliverables** — README with assumptions A1–A17, architecture diagram, Loom script, final verification

## Milestone Notes
- **M0**: Completed. Scaffolding, Django + DRF, Vite + React 18 + TS strict + Tailwind, vitest, pytest, ruff, mypy, `/api/health` integration test all green. CI workflow configured.
