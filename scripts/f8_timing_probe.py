"""Measure representative local 220/120 economics and C23 without DB writes."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_f5_sample import _run  # noqa: E402
from calculation.scheduling import SimulationRequestV1, run_simulation  # noqa: E402


def main() -> None:
    times = []
    for index in range(3):
        start = time.perf_counter()
        run, _linked, _ = _run(demand="220")
        economics_ms = (time.perf_counter() - start) * 1000
        request = SimulationRequestV1.model_validate({
            "schema_version": "simulation-request-v1", "request_id": f"simulation.f8.probe.{index}",
            "tenant_id": run.result_snapshot["tenant_id"], "project_id": run.project_id,
            "scenario_spec": run.scenario_spec_snapshot, "mode": "DAILY", "peak_factor": None,
            "sla": None, "resources": [], "limits": {"max_jobs_per_day": 10000, "max_fleet": 100,
            "max_runtime_seconds": 60, "progress_event_batch": 1000},
        })
        start = time.perf_counter()
        report = run_simulation(request)
        simulation_ms = (time.perf_counter() - start) * 1000
        times.append({"economics_ms": round(economics_ms, 2), "simulation_ms": round(simulation_ms, 2),
                      "economics_schema": run.result_snapshot["schema_version"],
                      "simulation_schema": report.schema_version})
    output = ROOT / "docs" / "delivery" / "f8" / "timing-probe.json"
    output.write_text(json.dumps({"mode": "local in-process, synthetic 220 pallets/day and 120 m",
        "runs": times, "economics_target_ms": 10000, "simulation_target_ms": 60000,
        "within_targets": all(item["economics_ms"] <= 10000 and item["simulation_ms"] <= 60000 for item in times),
        "http_or_database_time_included": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
