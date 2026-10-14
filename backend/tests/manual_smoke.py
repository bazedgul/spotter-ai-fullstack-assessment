"""Manual smoke script for real live end-to-end trip verification (Gate M3)."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from trucksafe.domain.models import LatLon  # noqa: E402
from trucksafe.services.analyze import AnalyzeOrchestrator  # noqa: E402


def run_smoke() -> None:
    orch = AnalyzeOrchestrator()
    origin = LatLon(32.78, -96.80)
    dest = LatLon(39.74, -104.99)
    dep_local = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT08:00")

    print("Calling AnalyzeOrchestrator with live OSRM and live Open-Meteo...")
    result = orch.analyze(
        origin=origin,
        origin_label="Dallas, TX",
        destination=dest,
        dest_label="Denver, CO",
        departure_local=dep_local,
        load_weight_lb=42000.0,
        checkpoint_interval_miles=50.0,
    )

    print("SUCCESS! Real trip analysis succeeded.")
    print("Request ID:", result["request_id"])
    print("Routes returned:", len(result["routes"]))
    for r in result["routes"]:
        lbl = r["label"]
        rnk = r["rank"]
        rec = r["recommended"]
        dist = r["distance_miles"]
        dur = r["duration_minutes"]
        sev = r["metrics"]["severe_miles"]
        hi = r["metrics"]["high_miles"]
        print(
            f"  {lbl} (Rank {rnk}, Rec: {rec}): {dist} mi, {dur} min, "
            f"Severe: {sev} mi, High: {hi} mi"
        )
        print(f"    Explanation: {r['explanation']}")

    print("Recommended Route ID:", result["recommended_route_id"])
    print("Forecast Available Until:", result["forecast_available_until"])
    print("Meta Timings (ms):", result["meta"]["timings_ms"])


if __name__ == "__main__":
    run_smoke()
