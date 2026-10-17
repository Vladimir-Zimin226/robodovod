"""Build a second, independently calculated warehouse guest scenario.

The baseline stays in the immutable v2 guest package. This file records the
same warehouse and robot assumptions at 2,400 instead of 2,000 pallets/day.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

from calculation.scheduling import SimulationReportV3, SimulationRequestV2, run_simulation  # noqa: E402
from calculation_contracts import semantic_digest  # noqa: E402
from build_warehouse_guest_demo import build_capture  # noqa: E402
from build_warehouse_guest_investor_report import report_bytes  # noqa: E402

TARGET = ROOT / "frontend/src/warehouseGuestComparisonV1.json"
BASE = ROOT / "frontend/src/warehouseGuestPackageV2.json"
PUBLIC = ROOT / "frontend/public/demo/warehouse-comparison-v1/scenario.json"
PDF = PUBLIC.parent / "report.pdf"
MANIFEST = PUBLIC.parent / "manifest.json"


def build() -> dict:
    baseline = json.loads(BASE.read_text(encoding="utf-8"))
    demo, assumptions, capacity_request, inputs, execution = build_capture(2400, "-peak")
    spec = execution.scenario_spec_snapshot
    primary = next(item for item in spec["operating_windows"] if item["window_id"] == "window.primary")
    request = SimulationRequestV2.model_validate({
        "schema_version": "simulation-request-v2",
        "request_id": "simulation.public.warehouse.pallet.peak.v1",
        "tenant_id": execution.result_snapshot["tenant_id"],
        "project_id": execution.result_snapshot["project_id"],
        "scenario_spec": spec,
        "mode": "DAILY", "peak_factor": None, "sla": None, "resources": [],
        "limits": {"max_jobs_per_day": 10000, "max_fleet": 100,
                   "max_runtime_seconds": 60, "progress_event_batch": 1000},
        "model_start": {"weekday": "MONDAY", "seconds_from_midnight": int(primary["start_time"]["value"]),
                        "timezone": primary["timezone"]},
        "process_chain": None,
    })
    report = run_simulation(request)
    if not isinstance(report, SimulationReportV3):
        raise ValueError(f"public comparison simulation failed: {report}")
    report_json = report.model_dump(mode="json")
    if (baseline["demo"]["input_digest"] == demo["input_digest"]
            or baseline["assumptions"] != assumptions
            or baseline["simulation"]["request"]["scenario_spec"]["profile"] != spec["profile"]
            or spec["analysis"]["capacity_run_id"] != "run.demo.warehouse.c11-peak"
            or spec["analysis"]["capacity_request_digest"] != semantic_digest(capacity_request)
            or demo["input_digest"] != semantic_digest({"capacity": capacity_request.model_dump(mode="json"), "economics": inputs})
            or demo["result_digest"] != semantic_digest(execution.result_snapshot)
            or report_json["workload"]["daily_units"] != "2400"
            or report_json["workload"]["fleet_units"] != demo["capacity"]["value"]["selected_fleet"]
            or report_json["replay"]["canonical_request_digest"] != semantic_digest(request)
            or report_json["replay"]["scenario_spec_digest"] != semantic_digest(request.scenario_spec)):
        raise ValueError("public comparison has inconsistent calculations")
    return {
        "schema_version": "warehouse-guest-comparison-v1",
        "baseline_package_version": baseline["schema_version"],
        "baseline_input_digest": baseline["demo"]["input_digest"],
        "title": "Повышенная нагрузка · 2 400 паллет в сутки",
        "difference": "Тот же авторский профиль объекта и робота, маршрут 120 м, две смены по 11 ч и денежные допущения; меняется только суточный спрос. Условная геометрия сцены перестраивается под размер парка.",
        "demo": demo,
        "simulation": {"request": request.model_dump(mode="json"), "report": report_json},
        "bindings": {
            "capacity_economics_input_digest": demo["input_digest"],
            "economics_result_digest": demo["result_digest"],
            "scenario_revision_id": spec["revision_id"],
            "simulation_report_digest": report_json["replay"]["report_content_digest"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    comparison = build()
    content = (json.dumps(comparison, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    baseline = json.loads(BASE.read_text(encoding="utf-8"))
    full = {**baseline, "schema_version": comparison["schema_version"], "title": comparison["title"],
            "demo": comparison["demo"], "simulation": comparison["simulation"], "bindings": comparison["bindings"]}
    pdf = report_bytes(full, presentation_name="warehouse-comparison-v1",
                       source_note="Обследование → проверка поставщика → пилот → решение. Этот PDF использует сохранённые числа варианта с нагрузкой 2 400 паллет/сутки; JSON содержит исходные данные и контрольные суммы.")
    sha = lambda body: "sha256:" + hashlib.sha256(body).hexdigest()
    manifest = (json.dumps({"schema_version": "warehouse-comparison-manifest-v1",
        "baseline_input_digest": comparison["baseline_input_digest"], "bindings": comparison["bindings"],
        "files": {"scenario.json": {"sha256": sha(content), "bytes": len(content)},
                  "report.pdf": {"sha256": sha(pdf), "bytes": len(pdf)}}}, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    expected = {TARGET: content, PUBLIC: content, PDF: pdf, MANIFEST: manifest}
    if args.check:
        return 0 if all(path.is_file() and path.read_bytes() == body for path, body in expected.items()) else 1
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    for path, body in expected.items():
        path.write_bytes(body)
        print(f"{path.relative_to(ROOT)}: {len(body)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
