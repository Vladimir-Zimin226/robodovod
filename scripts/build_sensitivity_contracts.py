"""Build/check C20 sensitivity schemas and deterministic fixtures."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.economics.allocation import (
    MultiprocessAllocationRequestV1,
    calculate_multiprocess_allocation,
)
from calculation.economics.allocation import (
    _digest as allocation_digest,
)
from calculation.economics.sensitivity import (
    ZERO_DIGEST,
    SensitivityRequestV1,
    SensitivityResultV1,
    _digest,
    calculate_sensitivity,
)


def _base_raw() -> dict:
    fixture = json.loads(
        (ROOT / "contracts/fixtures/multiprocess-allocation-v1.golden.json").read_text(encoding="utf-8")
    )
    return fixture["request"]


def _capacity(process_id: str, fleet: int, demand: str, marker: str) -> dict:
    return {
        "process_id": process_id,
        "result_version": "capacity-analysis-response-v2",
        "result_digest": "sha256:" + marker * 64,
        "selected_fleet": fleet,
        "demand_value": demand,
        "demand_unit": "unit/day",
        "provenance_ref": f"input.c20.{process_id}.demand",
    }


def _scale_role_money(raw: dict, factor: Decimal, provenance: str) -> None:
    money = raw["labour_result"]["roles"][0]["money"]
    for field in ("monthly_gross", "annual_gross", "annual_direct", "annual_full", "annual_fixed_overhead"):
        money[field] = format(Decimal(money[field]) * factor, "f")
    money["salary_provenance_ref"] = provenance
    raw["labour_result"]["replay"]["canonical_input_digest"] = "sha256:" + ("c" if factor < 1 else "d") * 64
    raw["labour_result"]["replay"]["trace_content_digest"] = "sha256:" + ("e" if factor < 1 else "f") * 64
    raw["labour_result_digest"] = allocation_digest(raw["labour_result"])


def _variant(parameter: str, direction: str, base_capacity: list[dict]) -> dict:
    lower = direction == "LOWER"
    factor = Decimal("0.90") if lower else Decimal("1.10")
    suffix = f"{parameter.lower()}.{direction.lower()}"
    raw = copy.deepcopy(_base_raw())
    raw["run_id"] = f"run.c20.{suffix}"
    capacity = copy.deepcopy(base_capacity)
    if parameter == "EQUIPMENT_PRICE":
        base_value = Decimal(2500000)
        config = raw["configurations"][0]
        config["direct_capex_cashflow"] = "9000000" if lower else "11000000"
        config["allocation_basis_direct_capital"] = "7200000" if lower else "8800000"
        config["source_run_id"] = f"run.c16.{suffix}"
        config["source_result_digest"] = "sha256:" + ("1" if lower else "2") * 64
        engines = ["purchase-cost-ledger-v1", "full-cashflows-reconciliation-v1", "multiprocess-allocation-v1"]
        scope_id, unit = "position.alpha", "RUB/robot"
    elif parameter == "OPERATION_VOLUME":
        base_value = Decimal(1000)
        config = raw["configurations"][0]
        config["source_run_id"] = f"run.c16.{suffix}"
        config["source_result_digest"] = "sha256:" + ("3" if lower else "4") * 64
        for flow in config["annual_cashflows"]:
            flow["scenario_cf"] = "36000000" if lower else "44000000"
        capacity[0]["demand_value"] = "900" if lower else "1100"
        capacity[0]["result_digest"] = "sha256:" + ("5" if lower else "6") * 64
        if not lower:
            capacity[0]["selected_fleet"] = 5
            config["direct_capex_cashflow"] = "12500000"
            config["allocation_basis_direct_capital"] = "10000000"
            raw["labour_result"]["operating_staff"]["total_selected_fleet"] = 8
            raw["labour_result_digest"] = allocation_digest(raw["labour_result"])
        engines = [
            "capacity-analysis-service-v2", "role-labour-baseline-v1",
            "purchase-cost-ledger-v1", "full-cashflows-reconciliation-v1",
            "multiprocess-allocation-v1",
        ]
        scope_id, unit = "process.internal", "unit/day"
    else:
        base_value = Decimal(100000)
        provenance = f"input.c20.salary.{direction.lower()}"
        _scale_role_money(raw, factor, provenance)
        engines = ["role-labour-baseline-v1", "multiprocess-allocation-v1"]
        scope_id, unit = "role.trolley", "RUB/person/month"
    variant_value = base_value * factor
    return {
        "variant_id": f"variant.{suffix}",
        "derived_run_id": raw["run_id"],
        "status": "EXECUTABLE",
        "override": {
            "parameter_id": parameter,
            "direction": direction,
            "delta_fraction": "-0.10" if lower else "0.10",
            "scope_id": scope_id,
            "base_value": format(base_value, "f"),
            "variant_value": format(variant_value, "f"),
            "unit": unit,
            "source": "USER",
            "provenance_ref": f"input.c20.override.{suffix}",
        },
        "capacity_bindings": capacity,
        "rerun_engines": engines,
        "allocation_request": raw,
        "blocker_codes": [],
    }


def build_request() -> SensitivityRequestV1:
    base_request = MultiprocessAllocationRequestV1.model_validate(_base_raw())
    base_result = calculate_multiprocess_allocation(base_request)
    capacity = [
        _capacity("process.internal", 4, "1000", "8"),
        _capacity("process.waste", 3, "500", "9"),
    ]
    variants = [
        _variant(parameter, direction, capacity)
        for parameter in ("EQUIPMENT_PRICE", "OPERATION_VOLUME", "ROLE_SALARY")
        for direction in ("LOWER", "UPPER")
    ]
    ranking_fixture = json.loads(
        (ROOT / "contracts/fixtures/ranking-v2.golden.json").read_text(encoding="utf-8")
    )
    return SensitivityRequestV1.model_validate({
        "run_id": "run.c20.golden",
        "parent_run_id": base_result.run_id,
        "project_id": base_result.project_id,
        "tenant_id": base_result.tenant_id,
        "object_id": base_result.object_id,
        "baseline_allocation_request": base_request.model_dump(mode="json"),
        "baseline_allocation_result": base_result.model_dump(mode="json"),
        "baseline_allocation_result_digest": _digest(base_result),
        "ranking_result_digest": _digest(ranking_fixture["result"]),
        "selected_candidate_id": "candidate.beta",
        "selected_configuration_id": "config.internal",
        "baseline_capacity_bindings": capacity,
        "variants": variants,
    })


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    request = build_request()
    raw = request.model_dump(mode="json")
    bad_percent = copy.deepcopy(raw)
    bad_percent["variants"][0]["override"]["delta_fraction"] = "-0.20"
    price_changes_capacity = copy.deepcopy(raw)
    price_variant = next(item for item in price_changes_capacity["variants"] if item["override"]["parameter_id"] == "EQUIPMENT_PRICE")
    price_variant["capacity_bindings"][0]["selected_fleet"] += 1
    bad_baseline = copy.deepcopy(raw)
    bad_baseline["baseline_allocation_result_digest"] = ZERO_DIGEST
    result = calculate_sensitivity(request)
    negative = {"invalid": [
        {"case": "not-ten-percent", "request": bad_percent, "error_contains": "exactly +/-10 percent"},
        {"case": "price-mutates-capacity", "request": price_changes_capacity, "error_contains": "cannot change capacity"},
        {"case": "tampered-baseline", "request": bad_baseline, "error_contains": "baseline allocation result digest mismatch"},
    ]}
    return {
        ROOT / "contracts/sensitivity-request-v1.schema.json": encoded(SensitivityRequestV1.model_json_schema()),
        ROOT / "contracts/sensitivity-result-v1.schema.json": encoded(SensitivityResultV1.model_json_schema()),
        ROOT / "contracts/fixtures/sensitivity-v1.golden.json": encoded({
            "request": raw, "result": result.model_dump(mode="json")
        }),
        ROOT / "contracts/fixtures/sensitivity-v1.negative.json": encoded(negative),
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
        print("C20 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
