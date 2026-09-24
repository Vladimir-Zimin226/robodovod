"""Generate C23 SimulationRequest/Report v1 schemas and reference fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation.scheduling import (  # noqa: E402
    SimulationErrorV1,
    SimulationProgressV1,
    SimulationReportV1,
    SimulationRequestV1,
    run_simulation,
)
from scenario_spec_v2 import ScenarioSpecV2  # noqa: E402


CONTRACTS = ROOT / "contracts"
FIXTURES = CONTRACTS / "fixtures"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _schema(model: type, name: str, title: str) -> bytes:
    body = model.model_json_schema(ref_template="#/$defs/{model}", mode="serialization")
    body["$id"] = f"https://robomera.local/contracts/{name}"
    body["title"] = title
    return _json_bytes(body)


def request_fixture() -> SimulationRequestV1:
    scenario = ScenarioSpecV2.model_validate_json(
        (FIXTURES / "scenario-spec-v2.capacity-only-cleaner.golden.json").read_text(encoding="utf-8")
    )
    return SimulationRequestV1(
        schema_version="simulation-request-v1",
        request_id="request.c23.capacity-only",
        tenant_id=scenario.analysis.tenant_id,
        project_id=scenario.analysis.project_id,
        scenario_spec=scenario,
        mode="DAILY",
        peak_factor=None,
        sla=None,
        resources=[],
        limits={
            "max_jobs_per_day": 10000,
            "max_fleet": 100,
            "max_runtime_seconds": 60,
            "progress_event_batch": 1000,
        },
    )


def expected_files() -> tuple[tuple[Path, bytes], ...]:
    request = request_fixture()
    report = run_simulation(request, engine_version="deterministic-queue-v1")
    corrected = run_simulation(request)
    if not isinstance(report, SimulationReportV1):
        raise RuntimeError(f"golden simulation failed: {report}")
    unknown = request.model_dump(mode="json")
    unknown["schema_version"] = "simulation-request-v2"
    extra = request.model_dump(mode="json")
    extra["scheduler_hint"] = "browser-local"
    return (
        (CONTRACTS / "simulation-request-v1.schema.json", _schema(SimulationRequestV1, "simulation-request-v1.schema.json", "Robomera SimulationRequest v1")),
        (CONTRACTS / "simulation-report-v1.schema.json", _schema(SimulationReportV1, "simulation-report-v1.schema.json", "Robomera SimulationReport v1")),
        (CONTRACTS / "simulation-progress-v1.schema.json", _schema(SimulationProgressV1, "simulation-progress-v1.schema.json", "Robomera SimulationProgress v1")),
        (CONTRACTS / "simulation-error-v1.schema.json", _schema(SimulationErrorV1, "simulation-error-v1.schema.json", "Robomera SimulationError v1")),
        (FIXTURES / "simulation-request-v1.capacity-only.golden.json", _json_bytes(request.model_dump(mode="json"))),
        (FIXTURES / "simulation-report-v1.capacity-only.golden.json", _json_bytes(report.model_dump(mode="json"))),
        (FIXTURES / "simulation-report-v2.capacity-only.golden.json", _json_bytes(corrected.model_dump(mode="json"))),
        (FIXTURES / "simulation-request-v1.unknown-version.invalid.json", _json_bytes(unknown)),
        (FIXTURES / "simulation-request-v1.extra-field.invalid.json", _json_bytes(extra)),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = expected_files()
    if args.check:
        return 0 if all(path.is_file() and path.read_bytes() == data for path, data in files) else 1
    for path, data in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
