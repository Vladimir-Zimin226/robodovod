"""Build the anonymized, deterministic 220-pallet F5 acceptance package."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from calculation.final_export import build_final_export
from calculation.scheduling import SimulationRequestV1, run_simulation
from calculation_contracts import semantic_digest
from simulation_artifacts import StoredSimulationEvidence
from test_final_economics import _run

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/planning/assets/f5/sample-220-pallets-120m.zip"


def main() -> None:
    run, linked, _ = _run(demand="220")
    request = SimulationRequestV1.model_validate({
        "schema_version": "simulation-request-v1",
        "request_id": "simulation.f5.sample.220p.120m",
        "tenant_id": run.result_snapshot["tenant_id"],
        "project_id": run.project_id,
        "scenario_spec": run.scenario_spec_snapshot,
        "mode": "DAILY", "peak_factor": None, "sla": None, "resources": [],
        "limits": {"max_jobs_per_day": 10000, "max_fleet": 100,
                   "max_runtime_seconds": 60, "progress_event_batch": 1000},
    })
    report = run_simulation(request)
    simulation = StoredSimulationEvidence(
        artifact_id=uuid.UUID("00000000-0000-4000-8000-000000000025"),
        analysis_run_id=uuid.UUID(run.run_id),
        project_id=uuid.UUID(run.project_id),
        request=request, report=report,
        request_digest=semantic_digest(request),
        report_digest=semantic_digest(report),
        scenario_spec_digest=semantic_digest(request.scenario_spec),
    )
    package = build_final_export(run, linked, simulation)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(package.archive)
    print(f"{OUTPUT.relative_to(ROOT)} sha256:{hashlib.sha256(package.archive).hexdigest()}")


if __name__ == "__main__":
    main()
