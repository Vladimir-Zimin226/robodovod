"""Build/check C14 strict schemas and warehouse/airport/clinic goldens."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.labour import LabourAnalysisRequestV1, LabourResultV1, calculate_role_labour  # noqa: E402
from calculation_contracts import KnownQuantity, NormalizedProcess, RoleEntry  # noqa: E402

DIGEST = "sha256:" + "1" * 64


def q(name: str, value: str, unit: str, kind: str, provenance: str = "prov.user") -> KnownQuantity:
    return KnownQuantity(name=name, raw_value=value, raw_unit=unit, normalized_value=value,
                         unit=unit, quantity_kind=kind, provenance_ref=provenance)


def role(role_id: str, code: str, count: int, process_ids: list[str], object_scope: str, salary: str = "100000") -> RoleEntry:
    return RoleEntry(
        role_id=role_id, object_scope=object_scope, role_code=code,
        headcount=q("role_headcount", str(count), "person", "COUNT"),
        monthly_gross_salary=q("monthly_gross_salary", salary, "RUB/person/month", "MONEY", f"prov.salary.{role_id}"),
        process_ids=process_ids,
    )


def process(process_id: str, code: str, object_kind: str, scope: str, kind: str, demand: str, shifts: str, hours: str, role_id: str | None) -> NormalizedProcess:
    unit = {"PALLET": "pallet/day", "ITEM": "item/day", "PORTION": "portion/day", "CART": "cart/day", "BIN": "bin/day"}[kind]
    payload = {
        "process_id": process_id, "input_revision": "revision.c14", "object_kind": object_kind,
        "process_code": code, "scope": scope, "active": True, "quantity_kind": kind,
        "demand": q("demand_per_day", demand, unit, "FLOW"),
        "schedule": {
            "shifts_per_day": q("shifts_per_day", shifts, "shift", "COUNT"),
            "shift_hours": q("shift_hours", hours, "h", "TIME"),
            "days_per_year": q("days_per_year", "365", "day", "TIME"),
        },
        "role_refs": [] if role_id is None else [role_id],
    }
    if scope in ("TRANSPORT_CYCLE", "DELIVERY_CYCLE"):
        payload["route_distance"] = q("one_way_distance", "100", "m", "DISTANCE")
    return NormalizedProcess.model_validate(payload)


def labour_input(value: NormalizedProcess, role_id: str | None, fleet: int, coverage: str, manual: str | None, *, status: str = "COMPLETE") -> dict:
    return {
        "process": value.model_dump(mode="json"),
        "capacity": {
            "process_id": value.process_id, "input_revision": value.input_revision,
            "capacity_run_id": f"capacity.{value.process_id}", "capacity_status": status,
            "selected_fleet": fleet if status in ("COMPLETE", "WITH_ASSUMPTIONS") else None,
            "coverage": coverage if status in ("COMPLETE", "WITH_ASSUMPTIONS") else None,
            "capacity_result_digest": DIGEST,
        },
        "role_id": role_id,
        "manual_units_per_shift": None if manual is None else {
            "value": manual, "unit": f"{str(value.quantity_kind).lower()}/shift",
            "source": "USER", "provenance_ref": "prov.manual",
        },
    }


def build_request(name: str) -> LabourAnalysisRequestV1:
    if name == "warehouse":
        value = process("process.receiving", "warehouse_receiving_shipping", "WAREHOUSE", "TRANSPORT_CYCLE", "PALLET", "1400", "2", "8", "role.driver")
        roles = [role("role.driver", "forklift_driver", 20, [value.process_id], "WAREHOUSE"), role("role.tech", "tech_support", 1, [], "SITE")]
        processes = [labour_input(value, "role.driver", 5, "1", "100")]
        object_kind = "WAREHOUSE"
    elif name == "airport":
        first = process("process.internal", "airport_internal_logistics", "AIRPORT", "TRANSPORT_CYCLE", "CART", "300", "3", "8", "role.trolley")
        second = process("process.waste", "airport_waste", "AIRPORT", "TRANSPORT_CYCLE", "BIN", "100", "3", "8", "role.trolley")
        roles = [role("role.trolley", "trolley_operator", 20, [first.process_id, second.process_id], "AIRPORT")]
        processes = [labour_input(first, "role.trolley", 0, "0", "100"), labour_input(second, "role.trolley", 0, "0", "100")]
        object_kind = "AIRPORT"
    else:
        food = process("process.food", "clinic_food", "CLINIC", "DELIVERY_CYCLE", "PORTION", "1950", "3", "8", "role.food")
        safety = process("process.safety", "clinic_safety_requirements", "CLINIC", "CONSTRAINT_ONLY", "ITEM", "1", "3", "8", None)
        roles = [role("role.food", "catering_worker", 15, [food.process_id], "CLINIC"), role("role.tech", "tech_support", 1, [], "SITE")]
        processes = [labour_input(food, "role.food", 3, "0.8", "200"), labour_input(safety, None, 0, "0", None, status="NOT_APPLICABLE")]
        object_kind = "CLINIC"
    return LabourAnalysisRequestV1.model_validate({
        "run_id": f"run.c14.{name}", "project_id": f"project.c14.{name}", "tenant_id": "tenant.c14",
        "input_revision": "revision.c14", "object_id": f"object.{name}", "object_kind": object_kind,
        "uncertainty": "BASE", "role_pool": {"pool_id": f"pool.c14.{name}", "object_kind": object_kind, "roles": [item.model_dump(mode="json") for item in roles]},
        "processes": processes,
        "salary_sources": [{"role_id": item.role_id, "provenance_ref": item.monthly_gross_salary.provenance_ref, "source": "USER"} for item in roles],
    })


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    result = {
        ROOT / "contracts" / "role-labour-analysis-v1.schema.json": encoded(LabourAnalysisRequestV1.model_json_schema()),
        ROOT / "contracts" / "role-labour-result-v1.schema.json": encoded(LabourResultV1.model_json_schema()),
    }
    for name in ("warehouse", "airport", "clinic"):
        request = build_request(name)
        fixture = {"request": request.model_dump(mode="json"), "result": calculate_role_labour(request).model_dump(mode="json")}
        result[ROOT / "contracts" / "fixtures" / f"role-labour-v1.{name}.golden.json"] = encoded(fixture)
    base = build_request("warehouse").model_dump(mode="json")
    missing_salary = copy.deepcopy(base)
    missing_salary["role_pool"]["roles"][0]["monthly_gross_salary"] = {
        "status": "MISSING", "name": "monthly_gross_salary", "quantity_kind": "MONEY",
        "expected_unit": "RUB/person/month", "missing_reason": "MISSING_INPUT",
    }
    missing_salary["salary_sources"] = [item for item in missing_salary["salary_sources"] if item["role_id"] != "role.driver"]
    missing_request = LabourAnalysisRequestV1.model_validate(missing_salary)
    no_binding = copy.deepcopy(base)
    no_binding["salary_sources"] = []
    zero_unmarked = copy.deepcopy(base)
    zero_unmarked["role_pool"]["roles"][0]["monthly_gross_salary"]["raw_value"] = "0"
    zero_unmarked["role_pool"]["roles"][0]["monthly_gross_salary"]["normalized_value"] = "0"
    negative = {
        "valid_incomplete": {
            "request": missing_request.model_dump(mode="json"),
            "result": calculate_role_labour(missing_request).model_dump(mode="json"),
        },
        "invalid": [
            {"case": "known-salary-without-user-file-binding", "request": no_binding, "error_contains": "USER/FILE source binding"},
            {"case": "zero-salary-without-marker", "request": zero_unmarked, "error_contains": "ZERO_COST_ROLE"},
        ],
    }
    result[ROOT / "contracts" / "fixtures" / "role-labour-v1.negative.json"] = encoded(negative)
    return result


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
        print("C14 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
