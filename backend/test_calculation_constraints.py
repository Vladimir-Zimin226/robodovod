from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from calculation.constraints import (
    ConstraintEvaluationRequest,
    evaluate_constraints,
    load_constraint_rules,
)
from pydantic import ValidationError
from readiness import evaluate_execution_constraints_v2

ROOT = Path(__file__).resolve().parents[1]


def _request(**context_overrides: object) -> dict:
    context = {
        "object_kind": "WAREHOUSE",
        "route_zones": ["storage"],
        "route_floors": [1],
        "max_payload_kg": "500",
        "min_aisle_width_m": "2.2",
        "requirement_sources": {},
        **context_overrides,
    }
    facts = {
        "supported_object_kinds": ["WAREHOUSE"],
        "supported_process_scopes": ["TRANSPORT_CYCLE"],
        "payload_kg": "1000",
        "min_aisle_width_m": "1.8",
        "availability": "0.9",
        "technical_passport_available": True,
    }
    return {
        "input_revision": "revision.test",
        "process_id": "process.test",
        "process_code": "warehouse_receiving_shipping",
        "process_scope": "TRANSPORT_CYCLE",
        "context": context,
        "candidate": {
            "model_id": "model.test",
            "position_id": "position.test",
            **facts,
            "evidence": {
                field: {"evidence_status": "MATCHING_SAFE", "source_ref": f"catalog:{field}"}
                for field in facts
            },
        },
    }


def _evaluate(raw: dict):
    return evaluate_constraints(ConstraintEvaluationRequest.model_validate(raw))


def _check(report, check_id: str):
    return next(item for item in report.checks if item.check_id == check_id)


def _fact(raw: dict, field: str, value: object, status: str = "MATCHING_SAFE") -> None:
    raw["candidate"][field] = value
    raw["candidate"]["evidence"][field] = {
        "evidence_status": status,
        "source_ref": f"catalog:{field}",
    }


def test_rule_registry_is_versioned_unique_and_records_migration_decisions():
    rules = load_constraint_rules()
    assert rules.rules_version == "calculation-constraint-rules-v2"
    assert len({rule.rule_id for rule in rules.rules}) == len(rules.rules)
    notes = " ".join(rules.migration_notes).lower()
    assert "fixed-count" in notes
    assert "autonomy x 0.8" in notes
    assert not any("autonomy" in rule.evaluator for rule in rules.rules)


def test_contract_is_strict_and_process_must_belong_to_object_kind():
    raw = _request()
    raw["extra"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ConstraintEvaluationRequest.model_validate(raw)
    raw = _request()
    raw["process_code"] = "airport_baggage"
    with pytest.raises(ValidationError, match="does not belong"):
        ConstraintEvaluationRequest.model_validate(raw)


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("context", "max_payload_kg", "-1", "non-negative"),
        ("candidate", "availability", "1.01", "between 0 and 1"),
    ],
)
def test_contract_rejects_invalid_physical_domains(target, field, value, message):
    raw = _request()
    raw[target][field] = value
    with pytest.raises(ValidationError, match=message):
        ConstraintEvaluationRequest.model_validate(raw)


def test_contract_rejects_unknown_provenance_binding_keys():
    raw = _request()
    raw["candidate"]["evidence"]["invented_fact"] = {
        "evidence_status": "MATCHING_SAFE", "source_ref": "catalog:invented"
    }
    with pytest.raises(ValidationError, match="unknown evidence keys"):
        ConstraintEvaluationRequest.model_validate(raw)
    raw = _request()
    raw["context"]["requirement_sources"]["invented_requirement"] = {
        "kind": "USER", "source_ref": "input:invented"
    }
    with pytest.raises(ValidationError, match="unknown requirement source keys"):
        ConstraintEvaluationRequest.model_validate(raw)


@pytest.mark.parametrize(
    ("check_id", "context", "fact_field", "passing", "failing"),
    [
        ("payload", {"max_payload_kg": "500"}, "payload_kg", "500", "499.9"),
        ("aisle", {"min_aisle_width_m": "2.2"}, "min_aisle_width_m", "2.2", "2.21"),
        ("lift-height", {"required_lift_height_m": "4"}, "max_lift_height_m", "4", "3.9"),
        ("floor-flatness", {"floor_flatness_mm_2m": "8"}, "floor_flatness_tolerance_mm_2m", "8", "7.9"),
        ("slope", {"max_slope_percent": "5"}, "max_slope_percent", "5", "4.9"),
    ],
)
def test_numeric_constraint_truth_tables(check_id, context, fact_field, passing, failing):
    raw = _request(**context)
    _fact(raw, fact_field, passing)
    assert _check(_evaluate(raw), check_id).status == "PASS"
    _fact(raw, fact_field, failing)
    assert _check(_evaluate(raw), check_id).status == "FAIL"
    raw["candidate"]["evidence"][fact_field]["evidence_status"] = "NOT_FOUND"
    assert _check(_evaluate(raw), check_id).status == "UNKNOWN"


def test_object_and_process_scope_are_evidence_gated():
    raw = _request()
    assert _check(_evaluate(raw), "object-kind").status == "PASS"
    assert _check(_evaluate(raw), "process-scope").status == "PASS"
    _fact(raw, "supported_object_kinds", ["AIRPORT"])
    _fact(raw, "supported_process_scopes", ["CLEANING_AREA"])
    report = _evaluate(raw)
    assert _check(report, "object-kind").status == "FAIL"
    assert _check(report, "process-scope").status == "FAIL"
    assert report.eligibility == "BLOCKED"
    raw["candidate"]["evidence"]["supported_object_kinds"]["evidence_status"] = "NOT_FOUND"
    raw["candidate"]["evidence"]["supported_process_scopes"]["evidence_status"] = "UNKNOWN"
    report = _evaluate(raw)
    assert _check(report, "object-kind").status == "UNKNOWN"
    assert _check(report, "process-scope").status == "UNKNOWN"


def test_only_route_floors_actually_crossed_require_lift_support():
    assert _check(_evaluate(_request(route_floors=[2])), "route-floors").status == "N_A"
    raw = _request(route_floors=[1, 2])
    assert _check(_evaluate(raw), "route-floors").status == "UNKNOWN"
    _fact(raw, "lift_protocols", [])
    assert _check(_evaluate(raw), "route-floors").status == "FAIL"
    _fact(raw, "lift_protocols", ["elevator-api-v1"])
    assert _check(_evaluate(raw), "route-floors").status == "PASS"


def test_cargo_ceiling_and_passport_truth_tables():
    raw = _request(required_cargo_kind="pallet", required_lift_height_m="4", ceiling_height_m="5")
    _fact(raw, "supported_cargo_kinds", ["pallet"])
    _fact(raw, "max_lift_height_m", "4")
    report = _evaluate(raw)
    assert _check(report, "cargo").status == "PASS"
    assert _check(report, "ceiling-clearance").status == "PASS"
    assert _check(report, "passport-availability").status == "PASS"
    raw["context"]["ceiling_height_m"] = "4.99"
    _fact(raw, "supported_cargo_kinds", ["box"])
    _fact(raw, "technical_passport_available", False)
    report = _evaluate(raw)
    assert _check(report, "cargo").status == "FAIL"
    assert _check(report, "ceiling-clearance").status == "FAIL"
    assert _check(report, "passport-availability").status == "FAIL"
    raw["context"]["ceiling_height_m"] = None
    assert _check(_evaluate(raw), "ceiling-clearance").status == "UNKNOWN"


def test_temperature_noise_and_zone_time_scope_truth_tables():
    raw = _request(
        temperature_min_c="-10", temperature_max_c="35", max_noise_dba="50",
        time_scope="NIGHT", route_zones=["ward"],
    )
    for field, value in {
        "temperature_min_c": "-15", "temperature_max_c": "40", "noise_dba": "45",
        "allowed_time_scopes": ["NIGHT"], "allowed_zones": ["ward"],
    }.items():
        _fact(raw, field, value)
    report = _evaluate(raw)
    assert _check(report, "temperature").status == "PASS"
    assert _check(report, "noise").status == "PASS"
    _fact(raw, "allowed_time_scopes", ["DAY"])
    assert _check(_evaluate(raw), "noise").status == "FAIL"
    _fact(raw, "allowed_time_scopes", ["NIGHT"])
    _fact(raw, "allowed_zones", ["corridor"])
    assert _check(_evaluate(raw), "noise").status == "FAIL"
    raw["candidate"]["evidence"]["noise_dba"]["evidence_status"] = "AMBIGUOUS_MODEL_MATCH"
    assert _check(_evaluate(raw), "noise").status == "UNKNOWN"


def test_airside_is_operational_permission_and_unknown_is_not_pass():
    raw = _request(object_kind="AIRPORT", airside_required=True)
    raw["process_code"] = "airport_baggage"
    _fact(raw, "supported_object_kinds", ["AIRPORT"])
    assert _check(_evaluate(raw), "airside").status == "UNKNOWN"
    _fact(raw, "airside_operational_permission", False)
    assert _check(_evaluate(raw), "airside").status == "FAIL"
    _fact(raw, "airside_operational_permission", True)
    assert _check(_evaluate(raw), "airside").status == "PASS"


def test_apron_restricted_zone_and_access_protocols_are_scoped():
    raw = _request(object_kind="AIRPORT", apron_required=True, restricted_zone_required=True, required_access_protocols=["badge", "gate-api"])
    raw["process_code"] = "airport_baggage"
    _fact(raw, "supported_object_kinds", ["AIRPORT"])
    for field, value in {
        "apron_operational_permission": True,
        "restricted_zone_access_supported": True,
        "supported_access_protocols": ["badge", "gate-api"],
    }.items():
        _fact(raw, field, value)
    report = _evaluate(raw)
    assert all(_check(report, item).status == "PASS" for item in ("apron", "restricted-zone", "access-protocols"))
    _fact(raw, "apron_operational_permission", False)
    _fact(raw, "restricted_zone_access_supported", False)
    _fact(raw, "supported_access_protocols", ["badge"])
    report = _evaluate(raw)
    assert all(_check(report, item).status == "FAIL" for item in ("apron", "restricted-zone", "access-protocols"))


def test_clinic_requirements_are_scoped_and_class_b_is_containment_not_explosion():
    raw = _request(object_kind="CLINIC", sanitization_required=False, class_b_containment_required=False)
    raw["process_code"] = "clinic_waste_b"
    _fact(raw, "supported_object_kinds", ["CLINIC"])
    report = _evaluate(raw)
    assert _check(report, "sanitization").status == "N_A"
    assert _check(report, "class-b-containment").status == "N_A"
    raw["context"]["sanitization_required"] = True
    raw["context"]["class_b_containment_required"] = True
    for field in ("sterilization_supported", "class_b_containment_supported", "cleanable_surface", "material_disinfection_supported"):
        _fact(raw, field, True)
    report = _evaluate(raw)
    assert all(_check(report, item).status == "PASS" for item in ("sanitization", "class-b-containment", "cleanable-surface", "material-disinfection"))
    assert "explosion" not in report.model_dump_json().lower()
    for field in ("sterilization_supported", "class_b_containment_supported", "cleanable_surface", "material_disinfection_supported"):
        _fact(raw, field, False)
    report = _evaluate(raw)
    assert all(_check(report, item).status == "FAIL" for item in ("sanitization", "class-b-containment", "cleanable-surface", "material-disinfection"))


def test_floor_covering_outdoor_and_availability_truth_tables():
    raw = _request(floor_covering="epoxy", outdoor_required=True)
    _fact(raw, "supported_floor_coverings", ["epoxy"])
    _fact(raw, "outdoor_supported", True)
    report = _evaluate(raw)
    assert _check(report, "floor-covering").status == "PASS"
    assert _check(report, "outdoor").status == "PASS"
    _fact(raw, "supported_floor_coverings", ["concrete"])
    _fact(raw, "outdoor_supported", False)
    _fact(raw, "availability", "0.39")
    report = _evaluate(raw)
    assert all(_check(report, item).status == "FAIL" for item in ("floor-covering", "outdoor", "availability"))
    raw["candidate"]["evidence"]["availability"]["evidence_status"] = "NOT_FOUND"
    assert _check(_evaluate(raw), "availability").status == "UNKNOWN"


def test_warnings_and_deferred_integrations_never_change_execution_eligibility():
    raw = _request(
        horizon_years=10, budget_rub="100", available_charging_power_kw="5",
        active_area_m2="20", fleet_units=1, required_integrations=["wms"],
    )
    _fact(raw, "expected_life_years", "5")
    _fact(raw, "capex_rub", "101")
    _fact(raw, "charging_power_kw", "6")
    _fact(raw, "supported_integrations", [])
    report = _evaluate(raw)
    assert report.eligibility == "ELIGIBLE"
    assert all(_check(report, item).status == "FAIL" for item in ("life-warning", "budget-warning", "charging-warning", "density-warning"))
    assert _check(report, "integrations").status == "UNKNOWN"
    assert set(report.warning_codes) == {
        "life-warning", "budget-warning", "charging-warning", "density-warning", "integrations"
    }
    _fact(raw, "expected_life_years", "10")
    _fact(raw, "capex_rub", "100")
    _fact(raw, "charging_power_kw", "5")
    _fact(raw, "supported_integrations", ["wms"])
    raw["context"]["active_area_m2"] = "30"
    report = _evaluate(raw)
    assert all(_check(report, item).status == "PASS" for item in ("life-warning", "budget-warning", "charging-warning", "density-warning", "integrations"))


def test_unknown_critical_fact_needs_validation_and_retains_evidence_reason():
    raw = _request()
    raw["candidate"]["evidence"]["payload_kg"]["evidence_status"] = "CONFLICT"
    report = _evaluate(raw)
    check = _check(report, "payload")
    assert check.status == "UNKNOWN"
    assert check.reason_code == "candidate-fact-missing"
    assert report.eligibility == "NEEDS_VALIDATION"


def test_assumed_requirement_never_becomes_final_eligible_pass():
    raw = _request()
    raw["context"]["requirement_sources"]["max_payload_kg"] = {
        "kind": "ASSUMPTION", "source_ref": "assumption:payload"
    }
    report = _evaluate(raw)
    assert _check(report, "payload").status == "ASSUMED"
    assert report.eligibility == "NEEDS_VALIDATION"


def test_readiness_and_execution_delegate_to_the_same_v2_report():
    request = ConstraintEvaluationRequest.model_validate(_request())
    assert evaluate_execution_constraints_v2(request) == evaluate_constraints(request)


def test_generated_schemas_and_profile_goldens_are_current():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_calculation_constraint_contracts.py"), "--check"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for profile in ("warehouse", "airport", "clinic"):
        assert (ROOT / "contracts" / "fixtures" / f"constraint-report-v2.{profile}.json").is_file()
