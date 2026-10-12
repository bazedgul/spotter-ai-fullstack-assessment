# Architecture & Implementation Decisions

Record of decisions made following AGENTS.md locked decisions and defaults.

| ID | Decision | Rationale | Status |
|---|---|---|---|
| D-01 | Half-open lower-bound inclusive boundary convention (A1) | Strict conformance with `<` spec wording and safety conservatism. | Locked |
| D-02 | Pure Python domain core | Zero external framework or HTTP dependencies in `trucksafe/domain` ensures strict testability. | Locked |
| D-03 | Sustained 10m wind for classification, gusts displayed (A2) | Conforms to assessment criteria while keeping driver situational awareness. | Locked |
| D-04 | MapLibre layer-based rendering with zero-DOM markers (A12) | Maximizes WebGL performance with thousands of checkpoints/corridor coordinates. | Locked |
| D-05 | Zero-network client-side slider for 48h forecast | Heatmap returns all 49 time-slices upfront to achieve 60fps slider response. | Locked |
