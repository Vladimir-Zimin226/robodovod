"""Rebuild the read-only, nonpersistent warehouse guest example from engines."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.service import analyze_capacity  # noqa: E402
from calculation_contracts import CapacityAnalysisRequest, semantic_digest  # noqa: E402
from economics_orchestrator import EconomicsExecutionContextV1, execute_economics_v2  # noqa: E402
from test_economics_orchestrator import _capacity_request, _inputs, _snapshot  # noqa: E402

TARGET = ROOT / "frontend/src/warehouseGuestDemo.json"


def build() -> dict:
    assumptions = json.loads((ROOT / "data/scenarios/warehouse-economics-demo-v1.json").read_text(encoding="utf-8"))
    snapshot = _snapshot()
    snapshot = replace(snapshot, version=replace(
        snapshot.version, id="00000000-0000-0000-0000-000000000031"
    ))
    raw = _capacity_request().model_dump(mode="json")
    for quantity, value in (
        (raw["process"]["demand"], "2000"),
        (raw["process"]["schedule"]["shift_hours"], "11"),
        (raw["role_pool"]["roles"][0]["headcount"], "25"),
        (raw["role_pool"]["roles"][0]["monthly_gross_salary"], "120000"),
    ):
        quantity["raw_value"] = quantity["normalized_value"] = value
    request = CapacityAnalysisRequest.model_validate(raw)
    capacity = analyze_capacity(request, snapshot, "run.demo.warehouse.c11")
    context = EconomicsExecutionContextV1(
        run_id="run.demo.warehouse.economics", project_id=request.project_id,
        tenant_id="tenant.demo", capacity_request=request,
        capacity_response=capacity.response,
        constraint_report=capacity.constraints.model_dump(mode="json"),
        executability=capacity.executability.model_dump(mode="json"),
    )
    inputs = _inputs()
    for field, proposal in assumptions["fields"].items():
        inputs[field] = int(proposal["value"]) if isinstance(inputs.get(field), int) else proposal["value"]
    inputs.update(assumptions["other_inputs"])
    economics = execute_economics_v2(inputs, snapshot, context).result_snapshot
    assert capacity.constraints.eligibility == "NEEDS_VALIDATION"
    assert len(economics["scenarios"]) == 6
    assert {item["procurement"]["procurement_status"] for item in economics["scenarios"]} == {"UNVERIFIED"}
    return {
        "schema_version": "warehouse-guest-demo-v1", "assumptions_version": assumptions["schema_version"],
        "as_of": "2026-09-25", "source": "offline engine capture: scripts/build_warehouse_guest_demo.py",
        "model_notice": "Авторский расчётный профиль MULE из проверочного сценария, не паспорт и не коммерческое предложение",
        "process": "Паллетные перемещения на условном складе: 2 000 паллет/сутки, 2 × 11 ч, плечо 120 м, обмен 90 с",
        "capacity": capacity.response.capacity.model_dump(mode="json"),
        "c05": capacity.constraints.eligibility,
        "procurement": "UNVERIFIED",
        "scenarios": [{
            "acquisition": item["acquisition"], "uncertainty": item["uncertainty"],
            "npv_project": item["financial"]["npv_project"],
            "annual_ledgers": item["financial"]["annual_ledgers"],
        } for item in economics["scenarios"]],
        "sensitivity": economics["sensitivity"]["variants"],
        "input_digest": semantic_digest({"capacity": request.model_dump(mode="json"), "economics": inputs}),
        "result_digest": semantic_digest(economics),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = (json.dumps(build(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if args.check:
        return 0 if TARGET.is_file() and TARGET.read_bytes() == content else 1
    TARGET.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
