import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.robcraft_reconciliation import (
    RobCraftRendererReportV1,
    compare_robcraft_report,
)
from calculation.scheduling import SimulationReportV1


ROOT = Path(__file__).resolve().parents[1]


def _authoritative() -> SimulationReportV1:
    raw = json.loads((ROOT / "contracts/fixtures/simulation-report-v1.capacity-only.golden.json").read_text(encoding="utf-8"))
    return SimulationReportV1.model_validate(raw)


def _renderer(report: SimulationReportV1, throughput: str = "2112.5", *, kind: str = "C23_MEASUREMENT_WINDOW") -> dict:
    return {
        "schema_version": "robcraft-renderer-report-v1",
        "status": "LOCAL_VISUAL_OBSERVATION_ONLY",
        "bindings": {
            "scenario_revision_id": report.scenario_revision_id,
            "scenario_spec_version": "scenario-spec-v2",
            "scenario_seed": "scenario-7f8b86a3c2db426a",
            "authoritative_report_id": report.report_id,
            "authoritative_report_digest": report.replay.report_content_digest,
            "scheduler_seed": report.time_basis.seed,
        },
        "versions": {
            "renderer_engine_version": "robcraft-time-step-v1",
            "event_profile_version": "robcraft-visual-events-v1",
            "report_version": "robcraft-renderer-report-v1",
        },
        "measurement_basis": {
            "kind": kind,
            "elapsed_seconds": "86400",
            "operating_hours_per_day": report.time_basis.operating_hours_per_day,
            "operating_window_refs": report.time_basis.window_refs,
            "warmup_days": report.time_basis.warmup_days if kind == "C23_MEASUREMENT_WINDOW" else None,
            "measurement_days": report.time_basis.measurement_days if kind == "C23_MEASUREMENT_WINDOW" else None,
        },
        "geometry": {
            "source": "SYNTHETIC",
            "status": "MODIFIED",
            "base_revision_id": report.scenario_revision_id,
            "economics_status": "UNCHANGED",
            "analytical_route_ref": None,
            "analytical_distance_value": None,
            "analytical_distance_unit": None,
        },
        "observed": {
            "completed_units": "50700",
            "throughput_units_per_hour": throughput,
            "throughput_unit": report.capacity.unit,
            "queued_jobs": 0,
            "average_queue_seconds": "0",
        },
        "utilization": {
            "moving_percent": "50",
            "moving_basis": "ROBOT_MOVING_TIME_OVER_RENDERER_ELAPSED_FLEET_TIME",
            "productive_percent": None,
            "productive_status": "NOT_EVALUATED_LOCAL_TIME_STEP",
        },
        "energy": {"value": "123", "unit": "ARBITRARY_RENDERER_UNIT", "economics_status": "NOT_COMPARABLE_TO_RUB_OR_KWH"},
        "model_status": {
            "sla": "NOT_EVALUATED_USE_C23_REPORT",
            "failures": "VISUAL_DEMO_ONLY_NOT_ANALYTICAL",
            "charging": "VISUAL_DEMO_ONLY_NOT_ANALYTICAL",
            "engineering_claim": "CONCEPTUAL_VISUALIZATION_NOT_CERTIFICATION",
        },
        "limitations": ["live-window-not-c23-measurement-window"],
    }


@pytest.mark.parametrize(("throughput", "status", "warning"), [
    ("1901.25", "CONSISTENT", False),  # exactly 10%
    ("1901.03875", "DEVIATION", True),  # 10.01%
])
def test_comparison_uses_strictly_greater_than_ten_percent(throughput, status, warning):
    report = _authoritative()
    result = compare_robcraft_report(report, RobCraftRendererReportV1.model_validate(_renderer(report, throughput)))
    assert result.status == status
    assert result.warning is warning
    assert result.geometry_status == "MODIFIED"
    assert result.economics_status == "UNCHANGED"


def test_live_short_window_is_not_compared_to_c23():
    report = _authoritative()
    result = compare_robcraft_report(report, RobCraftRendererReportV1.model_validate(_renderer(report, "1", kind="LIVE_RENDERER_WINDOW")))
    assert result.status == "NOT_COMPARABLE"
    assert result.deviation_percent is None
    assert result.warning is False
    assert "measurement-basis-mismatch" in result.reasons


def test_stale_digest_and_extra_fields_are_rejected():
    report = _authoritative()
    stale = RobCraftRendererReportV1.model_validate(_renderer(report))
    stale_data = stale.model_dump(mode="json")
    stale_data["bindings"]["authoritative_report_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="stale or mismatched"):
        compare_robcraft_report(report, RobCraftRendererReportV1.model_validate(stale_data))
    with pytest.raises(ValidationError):
        RobCraftRendererReportV1.model_validate({**_renderer(report), "finance": {}})


def test_committed_contracts_and_geometry_modified_goldens_are_current():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_robcraft_reconciliation_contracts.py"), "--check"],
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0
    renderer = RobCraftRendererReportV1.model_validate_json(
        (ROOT / "contracts/fixtures/robcraft-renderer-report-v1.geometry-modified.golden.json").read_text(encoding="utf-8")
    )
    assert renderer.geometry.status == "MODIFIED"
    assert renderer.geometry.economics_status == "UNCHANGED"
