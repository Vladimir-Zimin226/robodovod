from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from calculation.economics.allocation import (
    MultiprocessAllocationRequestV1,
    MultiprocessAllocationResultV1,
    _digest,
    calculate_multiprocess_allocation,
)
from calculation.service import analyze_multiprocess_allocation
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> dict:
    return json.loads((ROOT / "contracts/fixtures/multiprocess-allocation-v1.golden.json").read_text(encoding="utf-8"))


def request() -> MultiprocessAllocationRequestV1:
    return MultiprocessAllocationRequestV1.model_validate(fixture()["request"])


def redigest_labour(raw: dict) -> None:
    raw["labour_result_digest"] = _digest(raw["labour_result"])


def test_golden_contract_service_and_byte_stable_replay():
    data = fixture()
    value = MultiprocessAllocationRequestV1.model_validate(data["request"])
    first = analyze_multiprocess_allocation(value)
    second = calculate_multiprocess_allocation(value)
    assert first.model_dump(mode="json") == data["result"] == second.model_dump(mode="json")
    MultiprocessAllocationResultV1.model_validate(data["result"])
    assert first.status == "COMPLETE"


def test_capital_fot_cashflow_and_role_pool_conservation():
    result = calculate_multiprocess_allocation(request())
    assert sum((Decimal(item.allocated_shared_capex_cashflow) for item in result.processes), Decimal(0)) == Decimal(result.shared_capex_cashflow)
    assert all(item.released <= item.allocated_people for item in result.role_conservation)
    assert sum(item.released for item in result.role_conservation) == result.total_released_people
    for project in result.annual_ledgers:
        process = [item.annual_ledgers[project.year - 1] for item in result.processes]
        assert sum((Decimal(item.combined_baseline_cf) for item in process), Decimal(0)) == Decimal(project.combined_baseline_cf)
        assert sum((Decimal(item.combined_scenario_cf) for item in process), Decimal(0)) == Decimal(project.combined_scenario_cf)
        assert sum((Decimal(item.allocated_baseline_fot) for item in process), Decimal(0)) == Decimal(project.object_baseline_fot)
        assert sum((Decimal(item.allocated_scenario_fot) for item in process), Decimal(0)) == Decimal(project.object_scenario_fot)
    assert result.control_required_once == result.processes[0].allocated_role_people * 0 + request().labour_result.operating_staff.control_required
    assert result.technicians_required_once == request().labour_result.operating_staff.technicians_required


def test_reordered_input_is_identical_including_replay_digest():
    raw = request().model_dump(mode="json")
    raw["configurations"].reverse()
    reordered = calculate_multiprocess_allocation(MultiprocessAllocationRequestV1.model_validate(raw))
    assert reordered.model_dump(mode="json") == calculate_multiprocess_allocation(request()).model_dump(mode="json")


def test_zero_direct_capital_uses_equal_allocation_and_stable_cent_remainder():
    raw = request().model_dump(mode="json")
    for item in raw["configurations"]:
        item["allocation_basis_direct_capital"] = "0"
    raw["shared_site_capital"].update({"capex_gross": "0.01", "capex_amortizable": "0.01", "capex_cashflow": "0.01"})
    result = calculate_multiprocess_allocation(MultiprocessAllocationRequestV1.model_validate(raw))
    assert [item.capital_allocation_method for item in result.processes] == ["EQUAL_ZERO_DENOMINATOR"] * 2
    assert [(item.process_id, item.allocated_shared_capex_cashflow) for item in result.processes] == [
        ("process.internal", "0.01"), ("process.waste", "0.00")
    ]


def test_single_process_receives_whole_shared_site_cost_without_duplication():
    raw = request().model_dump(mode="json")
    keep = raw["configurations"][0]["process_id"]
    raw["configurations"] = [raw["configurations"][0]]
    labour = raw["labour_result"]
    labour["processes"] = [item for item in labour["processes"] if item["process_id"] == keep]
    labour["allocations"] = [item for item in labour["allocations"] if item["process_id"] == keep]
    role = labour["roles"][0]
    process = labour["processes"][0]
    role["allocated_people"] = sum(item["allocated_people"] for item in labour["allocations"])
    role["unallocated_people"] = role["headcount"] - role["allocated_people"]
    role["released"] = process["released"]
    role["transferred"] = process["transferred"]
    role["remaining"] = role["headcount"] - role["released"]
    labour["total_released"] = role["released"]
    labour["total_transferred"] = role["transferred"]
    labour["operating_staff"]["control_transferred"] = role["transferred"]
    redigest_labour(raw)
    result = calculate_multiprocess_allocation(MultiprocessAllocationRequestV1.model_validate(raw))
    assert len(result.processes) == 1
    assert result.processes[0].allocated_shared_capex_cashflow == result.shared_capex_cashflow


def test_model_identity_does_not_duplicate_single_site_capital():
    raw = request().model_dump(mode="json")
    raw["configurations"][0]["model_id"] = "model.same"
    raw["configurations"][1]["model_id"] = "model.same"
    result = calculate_multiprocess_allocation(MultiprocessAllocationRequestV1.model_validate(raw))
    assert Decimal(result.shared_capex_cashflow) == Decimal(request().shared_site_capital.capex_cashflow)
    assert result.project_capex_cashflow == "50000000.00"


def test_project_payback_is_derived_from_combined_differential_cashflow():
    result = calculate_multiprocess_allocation(request())
    flows = [Decimal(result.initial_scenario_cf)] + [Decimal(item.differential_cf) for item in result.annual_ledgers]
    assert flows[0] == -Decimal(result.project_capex_cashflow)
    assert result.simple_payback.status == "COMPLETE"
    assert Decimal(result.simple_payback.value) > 0


def test_negative_fixture_and_snapshot_tenant_digest_guards():
    negative = json.loads((ROOT / "contracts/fixtures/multiprocess-allocation-v1.negative.json").read_text(encoding="utf-8"))
    for case in negative["invalid"]:
        with pytest.raises(ValidationError, match=case["error_contains"]):
            MultiprocessAllocationRequestV1.model_validate(case["request"])
    raw = request().model_dump(mode="json")
    raw["labour_result_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="digest mismatch"):
        MultiprocessAllocationRequestV1.model_validate(raw)


def test_incomplete_or_tampered_role_conservation_is_rejected():
    raw = request().model_dump(mode="json")
    raw["labour_result"]["roles"][0]["released"] += 1
    redigest_labour(raw)
    with pytest.raises(ValidationError, match="released people mismatch"):
        MultiprocessAllocationRequestV1.model_validate(raw)


def test_generated_schemas_are_strict_and_contracts_forbid_shared_in_process_projection():
    for name in ("multiprocess-allocation-request-v1.schema.json", "multiprocess-allocation-result-v1.schema.json"):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
    raw = request().model_dump(mode="json")
    raw["configurations"][0]["excludes_object_shared_costs"] = False
    with pytest.raises(ValidationError):
        MultiprocessAllocationRequestV1.model_validate(raw)
