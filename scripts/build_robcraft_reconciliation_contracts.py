"""Generate C25 RobCraft renderer report/comparison schemas and goldens."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation.robcraft_reconciliation import (  # noqa: E402
    RobCraftKpiComparisonV1,
    RobCraftRendererReportV1,
    compare_robcraft_report,
)
from calculation.scheduling import SimulationReportV1  # noqa: E402


CONTRACTS = ROOT / "contracts"
FIXTURES = CONTRACTS / "fixtures"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _schema(model: type, name: str, title: str) -> bytes:
    body = model.model_json_schema(ref_template="#/$defs/{model}", mode="serialization")
    body["$id"] = f"https://robomera.local/contracts/{name}"
    body["title"] = title
    return _json_bytes(body)


def renderer_fixture(report: SimulationReportV1) -> RobCraftRendererReportV1:
    return RobCraftRendererReportV1(
        schema_version="robcraft-renderer-report-v1",
        status="LOCAL_VISUAL_OBSERVATION_ONLY",
        bindings={
            "scenario_revision_id": report.scenario_revision_id,
            "scenario_spec_version": "scenario-spec-v2",
            "scenario_seed": "scenario-7f8b86a3c2db426a",
            "authoritative_report_id": report.report_id,
            "authoritative_report_digest": report.replay.report_content_digest,
            "scheduler_seed": report.time_basis.seed,
        },
        versions={
            "renderer_engine_version": "robcraft-time-step-v1",
            "event_profile_version": "robcraft-visual-events-v1",
            "report_version": "robcraft-renderer-report-v1",
        },
        measurement_basis={
            "kind": "C23_MEASUREMENT_WINDOW",
            "elapsed_seconds": "86400",
            "operating_hours_per_day": report.time_basis.operating_hours_per_day,
            "operating_window_refs": report.time_basis.window_refs,
            "warmup_days": report.time_basis.warmup_days,
            "measurement_days": report.time_basis.measurement_days,
        },
        geometry={
            "source": "SYNTHETIC",
            "status": "MODIFIED",
            "base_revision_id": report.scenario_revision_id,
            "economics_status": "UNCHANGED",
            "analytical_route_ref": None,
            "analytical_distance_value": None,
            "analytical_distance_unit": None,
        },
        observed={
            "completed_units": "44400",
            "throughput_units_per_hour": "1850",
            "throughput_unit": report.capacity.unit,
            "queued_jobs": 66,
            "average_queue_seconds": "120",
        },
        utilization={
            "moving_percent": "47.5",
            "moving_basis": "ROBOT_MOVING_TIME_OVER_RENDERER_ELAPSED_FLEET_TIME",
            "productive_percent": None,
            "productive_status": "NOT_EVALUATED_LOCAL_TIME_STEP",
        },
        energy={
            "value": "314.25",
            "unit": "ARBITRARY_RENDERER_UNIT",
            "economics_status": "NOT_COMPARABLE_TO_RUB_OR_KWH",
        },
        model_status={
            "sla": "NOT_EVALUATED_USE_C23_REPORT",
            "failures": "VISUAL_DEMO_ONLY_NOT_ANALYTICAL",
            "charging": "VISUAL_DEMO_ONLY_NOT_ANALYTICAL",
            "engineering_claim": "CONCEPTUAL_VISUALIZATION_NOT_CERTIFICATION",
        },
        limitations=[
            "moving-utilization-is-not-productive-utilization",
            "energy-is-arbitrary-renderer-unit",
            "failures-and-charging-are-visual-demo-only",
            "use-c23-report-for-capacity-queue-sla-and-finance",
        ],
    )


def expected_files() -> tuple[tuple[Path, bytes], ...]:
    report = SimulationReportV1.model_validate_json(
        (FIXTURES / "simulation-report-v1.capacity-only.golden.json").read_text(encoding="utf-8")
    )
    renderer = renderer_fixture(report)
    comparison = compare_robcraft_report(report, renderer)
    return (
        (CONTRACTS / "robcraft-renderer-report-v1.schema.json", _schema(RobCraftRendererReportV1, "robcraft-renderer-report-v1.schema.json", "Robomera RobCraft RendererReport v1")),
        (CONTRACTS / "robcraft-kpi-comparison-v1.schema.json", _schema(RobCraftKpiComparisonV1, "robcraft-kpi-comparison-v1.schema.json", "Robomera RobCraft KPI Comparison v1")),
        (FIXTURES / "robcraft-renderer-report-v1.geometry-modified.golden.json", _json_bytes(renderer.model_dump(mode="json"))),
        (FIXTURES / "robcraft-kpi-comparison-v1.deviation.golden.json", _json_bytes(comparison.model_dump(mode="json"))),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = expected_files()
    if args.check:
        return 0 if all(path.is_file() and path.read_bytes() == data for path, data in files) else 1
    for path, data in files:
        path.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
