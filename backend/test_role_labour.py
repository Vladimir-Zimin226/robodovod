from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.labour import LabourAnalysisRequestV1, LabourResultV1, calculate_role_labour
from calculation.service import analyze_role_labour
from calculation_contracts import KnownQuantity, MissingQuantity, NormalizedProcess, RoleEntry, RolePool


ROOT = Path(__file__).resolve().parents[1]
DIGEST = "sha256:" + "1" * 64


def q(name: str, value: str, unit: str, kind: str, provenance: str = "prov.user") -> KnownQuantity:
    return KnownQuantity(
        name=name, raw_value=value, raw_unit=unit, normalized_value=value,
        unit=unit, quantity_kind=kind, provenance_ref=provenance,
    )


def salary(value: str = "100000", provenance: str = "prov.salary") -> KnownQuantity:
    return q("monthly_gross_salary", value, "RUB/person/month", "MONEY", provenance)


def role(role_id: str, code: str, headcount: int, processes: list[str], *, salary_value: str | None = "100000", marker: str | None = None, scope: str = "WAREHOUSE") -> RoleEntry:
    salary_value_obj = salary(salary_value) if salary_value is not None else MissingQuantity(
        name="monthly_gross_salary", quantity_kind="MONEY", expected_unit="RUB/person/month",
        missing_reason="MISSING_INPUT",
    )
    return RoleEntry(
        role_id=role_id, object_scope=scope, role_code=code,
        headcount=q("role_headcount", str(headcount), "person", "COUNT"),
        monthly_gross_salary=salary_value_obj, zero_cost_marker=marker, process_ids=processes,
    )


def process(process_id: str, code: str, role_id: str | None, *, object_kind: str = "WAREHOUSE", scope: str = "TRANSPORT_CYCLE", kind: str = "PALLET", demand: str = "1400", shifts: str = "2", hours: str = "8") -> NormalizedProcess:
    unit = {
        "PALLET": "pallet/day", "ITEM": "item/day", "PORTION": "portion/day", "CART": "cart/day",
        "SQUARE_METER": "m2/day",
    }[kind]
    payload = dict(
        process_id=process_id, input_revision="revision.c14", object_kind=object_kind,
        process_code=code, scope=scope, active=True, quantity_kind=kind,
        demand=q("demand_per_day", demand, unit, "FLOW"),
        schedule={
            "shifts_per_day": q("shifts_per_day", shifts, "shift", "COUNT"),
            "shift_hours": q("shift_hours", hours, "h", "TIME"),
            "days_per_year": q("days_per_year", "365", "day", "TIME"),
        },
        role_refs=[] if role_id is None else [role_id],
    )
    if scope in {"TRANSPORT_CYCLE", "DELIVERY_CYCLE"}:
        payload["route_distance"] = q("one_way_distance", "100", "m", "DISTANCE")
    return NormalizedProcess.model_validate(payload)


def process_input(value: NormalizedProcess, role_id: str | None, *, fleet: int = 5, coverage: str = "1", manual: str | None = "100", status: str = "COMPLETE") -> dict:
    capacity = {
        "process_id": value.process_id, "input_revision": value.input_revision,
        "capacity_run_id": f"capacity.{value.process_id}", "capacity_status": status,
        "selected_fleet": fleet if status in {"COMPLETE", "WITH_ASSUMPTIONS"} else None,
        "coverage": coverage if status in {"COMPLETE", "WITH_ASSUMPTIONS"} else None,
        "capacity_result_digest": DIGEST,
    }
    return {
        "process": value.model_dump(mode="json"), "capacity": capacity, "role_id": role_id,
        "manual_units_per_shift": None if manual is None else {
            "value": manual, "unit": f"{str(value.quantity_kind).lower()}/shift",
            "source": "USER", "provenance_ref": "prov.manual",
        },
    }


def request(*, object_kind: str = "WAREHOUSE", roles: list[RoleEntry] | None = None, processes: list[dict] | None = None, allocations: list[dict] | None = None, deficit_costs: list[dict] | None = None) -> LabourAnalysisRequestV1:
    if processes is None:
        value = process("process.receiving", "warehouse_receiving_shipping", "role.driver")
        processes = [process_input(value, "role.driver")]
    if roles is None:
        roles = [
            role("role.driver", "forklift_driver", 20, ["process.receiving"]),
            role("role.tech", "tech_support", 1, [], scope="SITE"),
        ]
    return LabourAnalysisRequestV1.model_validate({
        "run_id": "run.c14", "project_id": "project.c14", "tenant_id": "tenant.c14",
        "input_revision": "revision.c14", "object_id": f"object.{object_kind.lower()}",
        "object_kind": object_kind, "uncertainty": "BASE",
        "role_pool": {"pool_id": "pool.c14", "object_kind": object_kind, "roles": [item.model_dump(mode="json") for item in roles]},
        "processes": processes, "allocations": allocations or [], "deficit_costs": deficit_costs or [],
        "salary_sources": [
            {"role_id": item.role_id, "provenance_ref": item.monthly_gross_salary.provenance_ref, "source": "USER"}
            for item in roles if isinstance(item.monthly_gross_salary, KnownQuantity)
        ],
    })


def test_warehouse_rotation_27_and_conservation_golden():
    result = analyze_role_labour(request())
    process_result = result.processes[0]
    driver = result.roles[0]
    assert process_result.person_shifts == 14
    assert process_result.rotation_factor == "1.9075"
    assert process_result.required_people == 27
    assert (process_result.applied, process_result.transferred, process_result.released) == (20, 5, 15)
    assert process_result.applied == process_result.transferred + process_result.released
    assert (result.operating_staff.control_required, result.operating_staff.control_additional) == (5, 0)
    assert driver.deficit == 7 and driver.surplus == 0
    assert driver.remaining == driver.headcount - driver.released
    assert [item.released for item in driver.annual_staffing] == [8, 13, 15, 15, 15]
    assert driver.deficit_cost_source == "DEFAULT_ANNUAL_DIRECT"
    assert result.labour_status == result.finance_status == "COMPLETE"
    assert result.forklifts.withdrawn <= result.forklifts.base_count
    assert result.replay.capacity_result_digests == [DIGEST]


def test_missing_salary_is_local_incomplete_and_capacity_projection_is_immutable():
    roles = [
        role("role.driver", "forklift_driver", 20, ["process.receiving"], salary_value=None),
        role("role.tech", "tech_support", 1, [], scope="SITE"),
    ]
    value = request(roles=roles)
    original = copy.deepcopy(value.processes[0].capacity.model_dump(mode="json"))
    result = calculate_role_labour(value)
    assert result.labour_status == result.finance_status == "INCOMPLETE"
    assert result.roles[0].money is None
    assert result.roles[0].deficit_cost_source == "INCOMPLETE"
    assert value.processes[0].capacity.model_dump(mode="json") == original
    assert result.replay.capacity_result_digests == [DIGEST]


def test_zero_salary_requires_marker_and_marked_zero_is_explicit():
    with pytest.raises(ValidationError, match="ZERO_COST_ROLE"):
        role("role.driver", "forklift_driver", 20, ["process.receiving"], salary_value="0")
    roles = [
        role("role.driver", "forklift_driver", 20, ["process.receiving"], salary_value="0", marker="ZERO_COST_ROLE"),
        role("role.tech", "tech_support", 1, [], scope="SITE"),
    ]
    result = calculate_role_labour(request(roles=roles))
    assert result.roles[0].money.zero_cost_role is True
    assert result.roles[0].money.annual_direct == "0"


def test_known_salary_requires_user_or_file_binding():
    raw = request().model_dump(mode="json")
    raw["salary_sources"] = []
    with pytest.raises(ValidationError, match="USER/FILE source binding"):
        LabourAnalysisRequestV1.model_validate(raw)


def test_shared_role_allocation_is_deterministic_and_role_deficits_do_not_offset():
    first = process("process.a", "airport_internal_logistics", "role.trolley", object_kind="AIRPORT", kind="CART", demand="300", shifts="3", hours="8")
    second = process("process.b", "airport_waste", "role.trolley", object_kind="AIRPORT", kind="ITEM", demand="100", shifts="3", hours="8")
    processes = [process_input(first, "role.trolley", fleet=2, manual="100"), process_input(second, "role.trolley", fleet=1, manual="100")]
    roles = [
        role("role.trolley", "trolley_operator", 7, ["process.a", "process.b"], scope="AIRPORT"),
        role("role.tech", "tech_support", 1, [], scope="SITE"),
    ]
    left = calculate_role_labour(request(object_kind="AIRPORT", roles=roles, processes=processes))
    right = calculate_role_labour(request(object_kind="AIRPORT", roles=roles, processes=list(reversed(processes))))
    assert [(x.process_id, x.allocated_people) for x in left.allocations] == [(x.process_id, x.allocated_people) for x in right.allocations]
    assert sum(item.allocated_people for item in left.allocations) == 7
    assert all(item.method == "PERSON_SHIFTS_LARGEST_REMAINDER" for item in left.allocations)
    assert left.roles[0].deficit == max(0, left.roles[0].required_people - 7)
    assert left.total_deficit == sum(item.deficit for item in left.roles)
    assert left.total_surplus == sum(item.surplus for item in left.roles)


def test_explicit_partial_allocation_preserves_unallocated_pool_and_deficit_can_be_disabled():
    value = process("process.receiving", "warehouse_receiving_shipping", "role.driver")
    result = calculate_role_labour(request(
        processes=[process_input(value, "role.driver")],
        allocations=[{"role_id": "role.driver", "shares": {"process.receiving": "0.5"}, "source": "FILE", "provenance_ref": "prov.allocation"}],
        deficit_costs=[{"role_id": "role.driver", "annual_cost_per_person": "0", "semantics": "DEFICIT_NOT_MONETIZED", "source": "USER", "provenance_ref": "prov.deficit"}],
    ))
    assert result.allocations[0].allocated_people == 10
    assert result.roles[0].unallocated_people == 10
    assert result.roles[0].deficit_cost_source == "DISABLED"
    assert result.roles[0].annual_deficit_cost == "0"


def test_site_control_and_technicians_are_counted_once_and_fleet_zero_creates_none():
    airport = process("process.baggage", "airport_baggage", "role.baggage", object_kind="AIRPORT", kind="ITEM", demand="35000", shifts="3", hours="8")
    roles = [role("role.baggage", "baggage_handler", 40, ["process.baggage"], scope="AIRPORT")]
    result = calculate_role_labour(request(object_kind="AIRPORT", roles=roles, processes=[process_input(airport, "role.baggage", fleet=0, coverage="0", manual="1000")]))
    assert result.operating_staff.total_selected_fleet == 0
    assert result.operating_staff.control_required == result.operating_staff.technicians_required == 0
    assert result.operating_staff.status == "NOT_APPLICABLE"
    assert "control-salary-missing" not in result.issues
    assert "technician-salary-missing" not in result.issues


def test_small_pult_limit_and_surplus_policy_are_explicit():
    value = process("process.receiving", "warehouse_receiving_shipping", "role.driver", demand="100", shifts="2", hours="8")
    roles = [
        role("role.driver", "forklift_driver", 30, ["process.receiving"]),
        role("role.control", "control_operator", 1, [], scope="SITE"),
        role("role.tech", "tech_support", 1, [], scope="SITE"),
    ]
    base = request(roles=roles, processes=[process_input(value, "role.driver", fleet=1, coverage="1", manual="100")])
    raw = base.model_dump(mode="json")
    raw["replacement_limit"] = "0"
    limited = calculate_role_labour(LabourAnalysisRequestV1.model_validate(raw))
    assert limited.processes[0].applied == 0
    assert limited.operating_staff.control_required == 2
    assert limited.operating_staff.control_transferred == 0
    assert limited.operating_staff.control_additional == 2
    raw["replacement_limit"] = "1"
    raw["allow_surplus_replacement"] = False
    conservative = calculate_role_labour(LabourAnalysisRequestV1.model_validate(raw))
    raw["allow_surplus_replacement"] = True
    opted_in = calculate_role_labour(LabourAnalysisRequestV1.model_validate(raw))
    assert conservative.processes[0].robot_replacement == conservative.processes[0].required_people
    assert opted_in.processes[0].robot_replacement == 30


def test_cleaning_manual_productivity_uses_useful_factor_once():
    value = process("process.cleaning", "warehouse_cleaning", "role.cleaner", scope="CLEANING_AREA", kind="SQUARE_METER", demand="5000", shifts="2", hours="8")
    roles = [
        role("role.cleaner", "cleaner", 5, ["process.cleaning"]),
        role("role.tech", "tech_support", 1, [], scope="SITE"),
    ]
    result = calculate_role_labour(request(roles=roles, processes=[process_input(value, "role.cleaner", fleet=1, coverage="1", manual=None)]))
    assert result.processes[0].manual_units_per_shift == "2040"
    assert result.processes[0].person_shifts == 3


def test_clinic_and_no_role_processes_have_explicit_outcomes():
    clinic = process("process.food", "clinic_food", "role.food", object_kind="CLINIC", scope="DELIVERY_CYCLE", kind="PORTION", demand="1950", shifts="3", hours="8")
    safety = process("process.safety", "clinic_safety_requirements", None, object_kind="CLINIC", scope="CONSTRAINT_ONLY", kind="ITEM", demand="1", shifts="3", hours="8")
    roles = [
        role("role.food", "catering_worker", 15, ["process.food"], scope="CLINIC"),
        role("role.tech", "tech_support", 1, [], scope="SITE"),
    ]
    result = calculate_role_labour(request(object_kind="CLINIC", roles=roles, processes=[
        process_input(clinic, "role.food", fleet=3, coverage="0.8", manual="200"),
        process_input(safety, None, fleet=0, coverage="0", manual=None, status="NOT_APPLICABLE"),
    ]))
    by_id = {item.process_id: item for item in result.processes}
    assert by_id["process.food"].status == "COMPLETE"
    assert by_id["process.safety"].status == "NO_FOT_BENEFIT"
    assert by_id["process.safety"].released is None


@pytest.mark.parametrize("name", ["warehouse", "airport", "clinic"])
def test_golden_fixture_and_strict_schemas_load(name: str):
    fixture = json.loads((ROOT / f"contracts/fixtures/role-labour-v1.{name}.golden.json").read_text(encoding="utf-8"))
    value = LabourAnalysisRequestV1.model_validate(fixture["request"])
    actual = calculate_role_labour(value).model_dump(mode="json")
    assert actual == fixture["result"]
    LabourResultV1.model_validate(actual)
    for name in ("role-labour-analysis-v1.schema.json", "role-labour-result-v1.schema.json"):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False


def test_negative_fixture_covers_missing_salary_and_invalid_salary_sources():
    fixture = json.loads((ROOT / "contracts/fixtures/role-labour-v1.negative.json").read_text(encoding="utf-8"))
    incomplete = LabourAnalysisRequestV1.model_validate(fixture["valid_incomplete"]["request"])
    assert calculate_role_labour(incomplete).model_dump(mode="json") == fixture["valid_incomplete"]["result"]
    assert fixture["valid_incomplete"]["result"]["finance_status"] == "INCOMPLETE"
    for case in fixture["invalid"]:
        with pytest.raises(ValidationError, match=case["error_contains"]):
            LabourAnalysisRequestV1.model_validate(case["request"])
