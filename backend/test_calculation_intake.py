from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from calculation.intake import (
    PROCESS_DEFINITIONS,
    CalculationIntakeRequestV2,
    RawProvenance,
    RawQuantity,
    RawSource,
    adapt_project_file_v1,
    normalize_intake,
    process_projection,
)
from calculation_contracts import ObjectKind, ProcessCode, RoleCode
from project_file_intake import build_csv_template, inspect_project_file

ROOT = Path(__file__).resolve().parents[1]


def _source(source: str = "USER") -> dict:
    if source == "FILE":
        return {"source": source, "file_name": "input.csv", "file_sha256": "a" * 64, "row": 2}
    if source == "LLM":
        return {"source": source, "raw_text": "2000 pallets each day", "llm_message_id": "message.1"}
    return {"source": source, "raw_text": "2000"}


def _request(source: str = "USER") -> dict:
    provenance = _source(source)
    salary_provenance = _source("USER") if source == "LLM" else provenance
    return {
        "schema_version": "calculation-intake-v2",
        "input_revision": "revision.1",
        "object_id": "object.warehouse",
        "object_kind": "WAREHOUSE",
        "processes": [{
            "block_id": "block.receiving",
            "process_id": "process.receiving",
            "process_code": "warehouse_receiving_shipping",
            "active": True,
            "activation_source": source if source in {"USER", "FILE", "LLM"} else "USER",
            "quantity_kind": "PALLET",
            "demand": {"value": "2000", "unit": "pallet/day", "provenance": provenance},
            "schedule": {
                "shifts_per_day": {"value": "2", "unit": "shift", "provenance": provenance},
                "shift_hours": {"value": "11", "unit": "h", "provenance": provenance},
                "days_per_year": {"value": "365", "unit": "day", "provenance": provenance},
            },
            "route_distance": {"value": "0.12", "unit": "km", "provenance": provenance},
            "role_refs": ["role.forklift"],
        }],
        "roles": [{
            "role_id": "role.forklift",
            "object_scope": "WAREHOUSE",
            "role_code": "forklift_driver",
            "headcount": {"value": "25", "unit": "person", "provenance": provenance},
            "monthly_gross_salary": {"value": "120000", "unit": "RUB/person/month", "provenance": salary_provenance},
            "process_ids": ["process.receiving"],
        }],
    }


def test_strict_contract_rejects_extra_fields_unknown_codes_and_duplicate_roles():
    raw = _request()
    raw["hidden"] = 1
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CalculationIntakeRequestV2.model_validate(raw)
    unknown = _request()
    unknown["processes"][0]["process_code"] = "warehouse_magic"
    with pytest.raises(ValidationError):
        CalculationIntakeRequestV2.model_validate(unknown)
    duplicate = _request()
    second = copy.deepcopy(duplicate["roles"][0])
    second["role_id"] = "role.forklift.2"
    duplicate["roles"].append(second)
    with pytest.raises(ValidationError, match="duplicate object-scoped role"):
        CalculationIntakeRequestV2.model_validate(duplicate)


@pytest.mark.parametrize("source", ["USER", "FILE", "LLM"])
def test_manual_file_and_llm_preserve_raw_provenance_with_same_semantics(source: str):
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(_request(source)))
    assert response.valid
    process = response.normalized_processes[0]
    assert process.demand.normalized_value == "2000"
    assert process.route_distance.normalized_value == "120"
    assert any(node.provenance.source == source for node in response.conversions)


def test_quantity_kinds_are_not_silently_interchangeable():
    raw = _request()
    raw["processes"][0]["quantity_kind"] = "DELIVERY"
    raw["processes"][0]["demand"]["unit"] = "delivery/day"
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(raw))
    assert not response.valid
    assert [error.code for error in response.errors] == ["quantity-kind-mismatch"]
    assert response.normalized_processes == []


def test_schedule_over_24_hours_is_an_error_and_never_clamped():
    raw = _request()
    raw["processes"][0]["schedule"]["shifts_per_day"]["value"] = "3"
    raw["processes"][0]["schedule"]["shift_hours"]["value"] = "12"
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(raw))
    assert not response.valid
    assert "schedule-invalid" in {error.code for error in response.errors}
    assert response.normalized_processes[0].schedule is None
    assert not any(node.normalized_value == "24" and node.field.endswith("shift_hours") for node in response.conversions)


def test_active_zero_demand_returns_field_error_instead_of_a_clamp_or_exception():
    raw = _request()
    raw["processes"][0]["demand"]["value"] = "0"
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(raw))
    assert not response.valid
    assert "demand-not-positive" in {error.code for error in response.errors}
    assert response.normalized_processes == []


def test_inactive_block_needs_no_demand_or_schedule_and_keeps_identity():
    raw = _request()
    process = raw["processes"][0]
    process["active"] = False
    process["demand"] = None
    process["schedule"] = None
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(raw))
    assert response.valid
    assert response.normalized_processes[0].process_id == "process.receiving"
    assert response.normalized_processes[0].demand.missing_reason == "NOT_APPLICABLE"


def test_salary_is_monthly_gross_user_or_file_without_default():
    missing = _request()
    missing["roles"][0]["monthly_gross_salary"] = None
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(missing))
    assert response.valid
    assert response.role_pool.roles[0].monthly_gross_salary.status == "MISSING"
    assert any(field.endswith("monthly_gross_salary") for field in response.required_inputs)

    preset = _request()
    preset["roles"][0]["monthly_gross_salary"]["provenance"] = _source("PRESET")
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(preset))
    assert not response.valid
    assert response.role_pool.roles[0].monthly_gross_salary.status == "MISSING"
    assert "salary-confirmation-required" in {error.code for error in response.errors}

    negative = _request()
    negative["roles"][0]["monthly_gross_salary"]["value"] = "-1"
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(negative))
    assert not response.valid
    assert "salary-negative" in {error.code for error in response.errors}
    assert response.role_pool.roles[0].monthly_gross_salary.status == "MISSING"


def test_all_28_policy_blocks_and_union_roles_are_exact():
    assert len(PROCESS_DEFINITIONS) == 28
    assert [len(process_projection(kind)) for kind in ObjectKind] == [6, 10, 12]
    projected_roles = {role for definition in PROCESS_DEFINITIONS.values() for role in definition.roles}
    assert projected_roles <= set(RoleCode)
    assert set(PROCESS_DEFINITIONS) == set(ProcessCode)


@pytest.mark.parametrize(
    ("profile_code", "expected_blocks", "kind", "value", "raw_count"),
    [
        ("warehouse", 6, "PALLET", "2000", 42),
        ("airport", 10, "ITEM", "35000", 39),
        ("medical_facility", 12, "PORTION", "1950", 57),
    ],
)
def test_v1_file_adapter_golden_preserves_profile_and_typed_demand(profile_code, expected_blocks, kind, value, raw_count):
    filename, payload = build_csv_template(profile_code)
    legacy = inspect_project_file(filename, payload, profile_code)
    request = adapt_project_file_v1(legacy, input_revision="revision.adapter", object_id=f"object.{profile_code}")
    response = normalize_intake(request)
    assert response.valid
    assert len(request.processes) == expected_blocks
    assert len(request.raw_profile_parameters) == raw_count
    assert request.source_profile_version.startswith("organizer-object-profiles-v1:sha256:")
    active = [item for item in response.normalized_processes if item.active]
    assert len(active) == 1
    assert active[0].quantity_kind == kind
    assert active[0].demand.normalized_value == value
    assert response.role_pool.roles[0].monthly_gross_salary.status == "MISSING"
    if kind in {"ITEM", "PORTION"}:
        assert any(field.endswith("explicit_batch") for field in response.required_inputs)


def test_generated_schemas_and_golden_fixtures_are_strict_and_loadable():
    for name in ("warehouse", "airport", "clinic"):
        fixture = json.loads((ROOT / "contracts" / "fixtures" / f"calculation-intake-v2.{name}.json").read_text(encoding="utf-8"))
        request = CalculationIntakeRequestV2.model_validate(fixture["request"])
        assert normalize_intake(request).model_dump(mode="json") == fixture["response"]
    schema = json.loads((ROOT / "contracts" / "calculation-intake-request-v2.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False


def test_additional_income_and_allocation_are_raw_deferred_extensions():
    raw = _request()
    raw["additional_income_raw"] = {"value": "50000", "unit": "RUB", "provenance": _source()}
    raw["roles"][0]["allocation_shares"] = {"process.receiving": "1"}
    response = normalize_intake(CalculationIntakeRequestV2.model_validate(raw))
    assert response.raw_extensions["additional_income_raw"]["value"] == "50000"
    assert response.raw_extensions["role_allocations_raw"] == {"role.forklift": {"process.receiving": "1"}}


def test_production_app_exposes_v2_intake_normalization_http_route():
    from main import app

    payload = _request()
    expected = normalize_intake(CalculationIntakeRequestV2.model_validate(payload))
    with TestClient(app) as client:
        response = client.post("/api/v2/calculation-intake/normalize", json=payload)
        assert response.status_code == 200, response.text
        assert response.json() == expected.model_dump(mode="json")
        assert client.post("/api/v2/calculation-intake/normalize", json={}).status_code == 422
