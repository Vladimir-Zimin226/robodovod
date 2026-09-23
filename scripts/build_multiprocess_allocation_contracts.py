"""Build/check C18 allocation schemas and deterministic fixtures."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_role_labour_contracts import build_request as build_labour_request, role  # noqa: E402
from calculation.economics.allocation import (  # noqa: E402
    MultiprocessAllocationRequestV1,
    MultiprocessAllocationResultV1,
    _digest,
    calculate_multiprocess_allocation,
)
from calculation.labour import LabourAnalysisRequestV1, calculate_role_labour  # noqa: E402


def build_request() -> MultiprocessAllocationRequestV1:
    raw = build_labour_request("airport").model_dump(mode="json")
    raw.update({
        "run_id": "run.c18.labour", "project_id": "project.c18", "tenant_id": "tenant.c18",
        "input_revision": "revision.c18", "object_id": "object.c18", "uncertainty": "BASE",
    })
    for index, item in enumerate(raw["processes"]):
        item["process"]["input_revision"] = "revision.c18"
        item["capacity"]["input_revision"] = "revision.c18"
        item["capacity"]["selected_fleet"] = 4 - index
        item["capacity"]["coverage"] = "0.8" if index == 0 else "0.6"
    raw["role_pool"]["roles"].extend([
        role("role.tech", "tech_support", 1, [], "SITE").model_dump(mode="json"),
        role("role.control", "control_operator", 0, [], "SITE").model_dump(mode="json"),
    ])
    raw["salary_sources"].extend([
        {"role_id": "role.tech", "provenance_ref": "prov.salary.role.tech", "source": "USER"},
        {"role_id": "role.control", "provenance_ref": "prov.salary.role.control", "source": "USER"},
    ])
    labour = calculate_role_labour(LabourAnalysisRequestV1.model_validate(raw))
    labour_json = labour.model_dump(mode="json")
    configs = []
    values = [
        ("process.internal", "config.internal", "model.alpha", "position.alpha", "10000000", "8000000", "40000000"),
        ("process.waste", "config.waste", "model.beta", "position.beta", "30000000", "24000000", "50000000"),
    ]
    for process_id, config_id, model_id, position_id, capex, basis, scenario in values:
        configs.append({
            "configuration_id": config_id, "process_id": process_id, "model_id": model_id,
            "position_id": position_id, "acquisition": "PURCHASE", "source_run_id": f"run.c16.{process_id}",
            "source_result_version": "financial-result-v1", "source_result_digest": "sha256:" + ("a" if process_id.endswith("internal") else "b") * 64,
            "cashflow_basis": "PRIMARY_PRETAX",
            "direct_capex_cashflow": capex, "allocation_basis_direct_capital": basis,
            "annual_cashflows": [
                {"year": year, "baseline_cf": "0", "scenario_cf": scenario} for year in range(1, 6)
            ],
        })
    return MultiprocessAllocationRequestV1.model_validate({
        "run_id": "run.c18.golden", "project_id": "project.c18", "tenant_id": "tenant.c18",
        "input_revision": "revision.c18", "object_id": "object.c18", "cohort_id": "cohort.c18.anchor-01",
        "uncertainty": "BASE", "configurations": configs, "labour_result": labour_json,
        "labour_result_digest": _digest(labour_json),
        "shared_site_capital": {
            "capex_gross": "10000000", "capex_amortizable": "9000000", "capex_cashflow": "10000000",
            "source": "USER", "provenance_ref": "prov.c18.shared-site-capital",
        },
        "shared_annual_costs": [
            {"year": year, "baseline_cost": "100000", "scenario_cost": "200000", "source": "USER",
             "provenance_ref": f"prov.c18.shared-annual.{year}"} for year in range(1, 6)
        ],
        "discount_rate": {"value": "0.15", "source": "POLICY", "provenance_ref": "finance.discount.default-rate"},
    })


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    request = build_request()
    raw = request.model_dump(mode="json")
    wrong_tenant = copy.deepcopy(raw)
    wrong_tenant["tenant_id"] = "tenant.other"
    duplicated_process = copy.deepcopy(raw)
    duplicated_process["configurations"][1]["process_id"] = duplicated_process["configurations"][0]["process_id"]
    included_shared = copy.deepcopy(raw)
    included_shared["configurations"][0]["excludes_object_shared_costs"] = False
    negative = {
        "invalid": [
            {"case": "tenant-mismatch", "request": wrong_tenant, "error_contains": "identity/revision mismatch"},
            {"case": "duplicate-process", "request": duplicated_process, "error_contains": "identities must be unique"},
            {"case": "process-projection-includes-shared", "request": included_shared, "error_contains": "Input should be True"},
        ]
    }
    result = calculate_multiprocess_allocation(request)
    return {
        ROOT / "contracts/multiprocess-allocation-request-v1.schema.json": encoded(MultiprocessAllocationRequestV1.model_json_schema()),
        ROOT / "contracts/multiprocess-allocation-result-v1.schema.json": encoded(MultiprocessAllocationResultV1.model_json_schema()),
        ROOT / "contracts/fixtures/multiprocess-allocation-v1.golden.json": encoded({
            "request": raw, "result": result.model_dump(mode="json")
        }),
        ROOT / "contracts/fixtures/multiprocess-allocation-v1.negative.json": encoded(negative),
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
        print("C18 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
