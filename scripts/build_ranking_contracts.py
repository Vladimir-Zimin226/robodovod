"""Build/check C19 ranking schemas and golden/negative fixtures."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.executability import RunExecutabilityResult
from calculation.ranking import (
    DATA_FIELDS,
    RankingRequestV2,
    RankingResultV2,
    _digest,
    calculate_ranking,
)


def data_fields(status: str = "VERIFIED") -> list[dict]:
    return [{
        "field_id": field_id, "importance": importance, "status": status,
        "matching_safe": status == "VERIFIED",
        "provenance_ref": f"catalog.ranking.{field_id}" if status in ("VERIFIED", "UNVERIFIED") else None,
    } for field_id, importance in DATA_FIELDS.items()]


def build_request() -> RankingRequestV2:
    constraint = json.loads((ROOT / "contracts/fixtures/constraint-report-v2.warehouse.json").read_text(encoding="utf-8"))["report"]
    allocation = json.loads((ROOT / "contracts/fixtures/multiprocess-allocation-v1.golden.json").read_text(encoding="utf-8"))["result"]
    allocation_digest = _digest(allocation)
    candidates = []
    specs = [
        ("candidate.alpha", "config.alpha", "model.alpha", "position.alpha", "0.55", "2.00", "800", 7, "10000000"),
        ("candidate.beta", "config.beta", "model.beta", "position.beta", "0.85", "1.80", "1000", 9, "20000000"),
        ("candidate.gamma", "config.gamma", "model.gamma", "position.gamma", "0.92", "1.60", "1250", 8, "20000000"),
    ]
    for index, (candidate_id, config_id, model_id, position_id, availability, aisle, payload, trl, npv) in enumerate(specs):
        report = copy.deepcopy(constraint)
        report.update({"input_revision": "revision.c19", "process_id": "process.receiving", "model_id": model_id, "position_id": position_id})
        for check in report["checks"]:
            if check["available"] is not None:
                check["available"]["source_ref"] = f"catalog:{model_id}:{check['check_id']}"
            if check["check_id"] == "availability":
                check["available"]["value"] = availability
            elif check["check_id"] == "aisle":
                check["available"]["value"] = aisle
            elif check["check_id"] == "payload":
                check["available"]["value"] = payload
        execution = RunExecutabilityResult.model_validate({
            "model_id": model_id, "position_id": position_id, "profile_id": "TRANSPORT_CYCLE_V1",
            "status": "EXECUTABLE", "dependencies": [], "blocker_codes": [],
        }).model_dump(mode="json")
        candidates.append({
            "candidate_id": candidate_id, "configuration_id": config_id, "model_id": model_id, "position_id": position_id,
            "constraint_report": report, "constraint_report_digest": _digest(report),
            "executability": execution, "executability_digest": _digest(execution),
            "trl": {"status": "VERIFIED", "value": trl, "matching_safe": True, "provenance_ref": f"catalog:{model_id}:trl"},
            "integrations": {"required_ids": [], "supported_matching_safe_ids": [], "unknown_ids": [], "provenance_refs": []},
            "data_fields": data_fields(),
            "penalty_context": {"equipment_class": "AMR", "quantity_kind": "PALLET",
                "demand_per_day": "6000" if index == 2 else "4000", "demand_provenance_ref": "input.demand"},
            "finance_status": "COMPLETE", "npv_project": npv, "allocation_result_digest": allocation_digest,
        })
    return RankingRequestV2.model_validate({
        "run_id": "run.c19.golden", "project_id": "project.c18", "tenant_id": "tenant.c18",
        "input_revision": "revision.c19", "process_id": "process.receiving",
        "cohort": {"cohort_id": allocation["cohort_id"], "allocation_run_id": allocation["run_id"],
            "allocation_result_digest": allocation_digest, "anchor_configuration_id": "config.alpha"},
        "candidates": candidates,
    })


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    request = build_request()
    raw = request.model_dump(mode="json")
    fake_verified = copy.deepcopy(raw)
    field = fake_verified["candidates"][0]["data_fields"][0]
    field.update({"status": "UNVERIFIED", "matching_safe": True})
    bad_digest = copy.deepcopy(raw)
    bad_digest["candidates"][0]["constraint_report_digest"] = "sha256:" + "0" * 64
    fake_npv = copy.deepcopy(raw)
    fake_npv["candidates"][0].update({"finance_status": "INCOMPLETE", "npv_project": "0"})
    negative = {"invalid": [
        {"case": "unverified-cannot-be-matching-safe", "request": fake_verified, "error_contains": "cannot become matching-safe"},
        {"case": "constraint-digest-mismatch", "request": bad_digest, "error_contains": "constraint report digest mismatch"},
        {"case": "incomplete-finance-fake-npv", "request": fake_npv, "error_contains": "forbids fake NPV"},
    ]}
    result = calculate_ranking(request)
    return {
        ROOT / "contracts/ranking-request-v2.schema.json": encoded(RankingRequestV2.model_json_schema()),
        ROOT / "contracts/ranking-result-v2.schema.json": encoded(RankingResultV2.model_json_schema()),
        ROOT / "contracts/fixtures/ranking-v2.golden.json": encoded({"request": raw, "result": result.model_dump(mode="json")}),
        ROOT / "contracts/fixtures/ranking-v2.negative.json": encoded(negative),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift: list[str] = []
    for path, content in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if drift:
        print("C19 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
