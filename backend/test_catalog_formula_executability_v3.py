from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from calculation.executability import (
    CatalogCandidateInput,
    ExecutabilityProfilesV3,
    ScenarioValue,
    audit_catalog_candidate,
    candidate_from_repository,
    evaluate_run_executability,
    load_executability_profiles,
    registry_payload,
)
from catalog_repository import CapacityRuntimeDTO, CatalogFactDTO, CatalogModelDTO

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "review" / "catalog-formula-executability-audit-v3.json"
POOL_DIFF = ROOT / "data" / "review" / "catalog-formula-executability-pool-diff-v3.json"


def _candidate() -> CatalogCandidateInput:
    return CatalogCandidateInput.model_validate({
        "model_id": "model.synthetic.transport",
        "position_id": "position.synthetic.transport",
        "name": "Synthetic transport fixture",
        "system_family": "SYNTHETIC_TEST_ONLY",
        "identity_status": "MATCHED",
        "profile_id": "TRANSPORT_CYCLE_V1",
        "readiness_v2_status": "CALCULATION_READY",
        "facts": [
            {"field_path": "specs.max_speed", "value": "1", "unit": "m/s", "evidence_status": "MATCHING_SAFE", "source_refs": ["fixture:speed"]},
            {"field_path": "specs.payload", "value": "1000", "unit": "kg", "evidence_status": "MATCHING_SAFE", "source_refs": ["fixture:payload"]},
        ],
    })


def _scenario() -> list[ScenarioValue]:
    raw = [
        ("process.demand_per_day", "2000", "pallet/day"),
        ("process.exchange_total_time_s", "90", "s"),
        ("process.one_way_distance_m", "120", "m"),
        ("process.shift_hours", "11", "h"),
        ("process.shifts_per_day", "2", "shift"),
        ("process.units_per_trip", "1", "unit/trip"),
    ]
    return [ScenarioValue(input_path=path, value=value, unit=unit, source_ref=f"fixture:{path}") for path, value, unit in raw]


def test_profiles_have_closed_ordered_formula_dependencies_without_legacy_fallbacks():
    profiles = load_executability_profiles()
    assert [item.profile_id for item in profiles.profiles] == sorted(item.profile_id for item in profiles.profiles)
    assert {item.profile_id for item in profiles.profiles} == {
        "TRANSPORT_CYCLE_V1", "DELIVERY_CYCLE_V1", "CLEANING_AREA_V1", "PALLETIZING_THROUGHPUT_V1"
    }
    transport = next(item for item in profiles.profiles if item.profile_id == "TRANSPORT_CYCLE_V1")
    assert [item.formula_id for item in transport.formulas] == ["F01", "F02", "F03", "F04", "F07"]
    assert all("fallback" not in item.model_dump() for item in transport.scenario_inputs)
    assert {item.input_path for item in transport.scenario_inputs if item.required} >= {
        "process.demand_per_day", "process.exchange_total_time_s", "process.one_way_distance_m",
        "process.shift_hours", "process.shifts_per_day", "process.units_per_trip",
    }


def test_profile_contract_rejects_unresolved_formula_dependency():
    raw = load_executability_profiles().model_dump(mode="json")
    raw["profiles"][0]["formulas"][0]["input_ids"].append("missing.input")
    with pytest.raises(ValueError, match="unresolved"):
        ExecutabilityProfilesV3.model_validate(raw)


def test_safe_facts_policy_and_scenario_inputs_are_separate():
    result = audit_catalog_candidate(_candidate(), registry_payload())
    assert result.catalog_status == "CATALOG_EXECUTABLE"
    assert result.run_executability == "NOT_EVALUATED"
    assert all(item.status == "RESOLVED_SAFE_FACT" for item in result.available_facts)
    assert all(item.status in {"REQUIRED_SCENARIO_INPUT", "OPTIONAL_SCENARIO_INPUT"} for item in result.required_scenario_inputs)
    assert all(item.status == "RESOLVED_POLICY" for item in result.policy_bindings)
    assert result.assumptions
    assert all(item.permitted_scope == "TRANSPORT_CYCLE_V1" for item in result.assumptions)
    assert all(item.vendor_fact is False for item in result.assumptions)


@pytest.mark.parametrize("evidence_status", ["CONFLICT", "AMBIGUOUS_MODEL_MATCH", "NOT_FOUND", "UNKNOWN"])
def test_unsafe_evidence_statuses_are_local_missing_safe_fact(evidence_status):
    raw = _candidate().model_dump(mode="json")
    raw["facts"][0]["evidence_status"] = evidence_status
    result = audit_catalog_candidate(CatalogCandidateInput.model_validate(raw), registry_payload())
    assert result.catalog_status == "MISSING_SAFE_FACT"
    assert result.blockers == ["fact.max-speed"]


def test_wrong_unit_and_domain_are_not_treated_as_missing_or_converted_unsafely():
    raw = _candidate().model_dump(mode="json")
    raw["facts"][0]["unit"] = "mph"
    result = audit_catalog_candidate(CatalogCandidateInput.model_validate(raw), registry_payload())
    assert result.catalog_status == "INVALID_FACT"
    assert result.available_facts[0].status == "INVALID_UNIT"
    raw = _candidate().model_dump(mode="json")
    raw["facts"][1]["value"] = "0"
    result = audit_catalog_candidate(CatalogCandidateInput.model_validate(raw), registry_payload())
    assert result.catalog_status == "INVALID_FACT"
    assert next(item for item in result.available_facts if item.requirement_id == "fact.payload").status == "INVALID_DOMAIN"


def test_exact_conversions_and_conservative_range_resolution_are_traced():
    raw = _candidate().model_dump(mode="json")
    raw["facts"][0].update({"value": 15, "unit": "km/h"})
    raw["facts"][1].update({"value": 3, "unit": "t"})
    result = audit_catalog_candidate(CatalogCandidateInput.model_validate(raw), registry_payload())
    speed, payload = result.available_facts
    assert speed.value == "4.166666666666666666666666667"
    assert speed.unit == "m/s"
    assert payload.value == "3000" and payload.unit == "kg"
    assert "unit-conversion:kmh-to-mps" in speed.source_refs

    cleaning_raw = _candidate().model_dump(mode="json")
    cleaning_raw.update({
        "profile_id": "CLEANING_AREA_V1",
        "facts": [{"field_path": "capacity.cleaning_rate_m2_h", "value": {"min": 700, "max": 1200}, "unit": "m²/h", "evidence_status": "MATCHING_SAFE", "source_refs": ["fixture:range"]}],
    })
    cleaning = CatalogCandidateInput.model_validate(cleaning_raw)
    result = audit_catalog_candidate(cleaning, registry_payload())
    assert result.catalog_status == "CATALOG_EXECUTABLE"
    assert result.available_facts[0].value == 700
    assert result.available_facts[0].unit == "m2/h"
    assert "normalization:conservative-range-minimum" in result.available_facts[0].source_refs


def test_unknown_identity_or_profile_is_explicitly_unsupported():
    raw = _candidate().model_dump(mode="json")
    raw["identity_status"] = "UNKNOWN"
    result = audit_catalog_candidate(CatalogCandidateInput.model_validate(raw), registry_payload())
    assert result.catalog_status == "UNKNOWN_IDENTITY"
    assert result.blockers == ["unknown-identity"]
    raw = _candidate().model_dump(mode="json")
    raw["profile_id"] = "UNKNOWN_PROFILE"
    raw["readiness_v2_status"] = "UNSUPPORTED_CAPACITY_PROFILE"
    result = audit_catalog_candidate(CatalogCandidateInput.model_validate(raw), registry_payload())
    assert result.catalog_status == "UNSUPPORTED_PROFILE"
    assert result.unsupported_reason == "profile-not-supported-by-formula-bundle"


def test_run_requires_all_inputs_and_c05_eligibility_without_clamp():
    registry = registry_payload()
    assert evaluate_run_executability(_candidate(), _scenario(), "ELIGIBLE", registry).status == "EXECUTABLE"
    missing = _scenario()[:-1]
    result = evaluate_run_executability(_candidate(), missing, "ELIGIBLE", registry)
    assert result.status == "MISSING_INPUT"
    assert "input.units-per-trip" in result.blocker_codes
    invalid_hours = _scenario()
    next(item for item in invalid_hours if item.input_path == "process.shifts_per_day").value = "3"
    next(item for item in invalid_hours if item.input_path == "process.shift_hours").value = "12"
    result = evaluate_run_executability(_candidate(), invalid_hours, "ELIGIBLE", registry)
    assert result.status == "MISSING_INPUT"
    assert "input.operating-hours" in result.blocker_codes
    assert evaluate_run_executability(_candidate(), _scenario(), "NEEDS_VALIDATION", registry).status == "NEEDS_VALIDATION"
    assert evaluate_run_executability(_candidate(), _scenario(), "BLOCKED", registry).status == "BLOCKED"


def test_run_rejects_duplicate_unknown_and_wrong_unit_scenario_values():
    values = _scenario()
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_run_executability(_candidate(), [*values, copy.deepcopy(values[0])], "ELIGIBLE", registry_payload())
    unknown = [*values, ScenarioValue(input_path="process.magic", value="1", unit="1", source_ref="fixture:magic")]
    with pytest.raises(ValueError, match="not declared"):
        evaluate_run_executability(_candidate(), unknown, "ELIGIBLE", registry_payload())
    next(item for item in values if item.input_path == "process.one_way_distance_m").unit = "kg"
    result = evaluate_run_executability(_candidate(), values, "ELIGIBLE", registry_payload())
    assert result.status == "MISSING_INPUT"
    assert "input.one-way-distance" in result.blocker_codes


def test_repository_projection_needs_no_robot_or_cost_fields():
    facts = (
        CatalogFactDTO(code="max_speed", scope_code="GLOBAL", value=1, canonical_unit="m/s", resolution_status="VERIFIED_OFFICIAL", evidence_id="e-speed"),
        CatalogFactDTO(code="payload", scope_code="GLOBAL", value=1000, canonical_unit="kg", resolution_status="VERIFIED_OFFICIAL", evidence_id="e-payload"),
    )
    model = CatalogModelDTO(
        id="model.repository", source_namespace="fixture", source_record_key="model.repository",
        organizer_id=None, manufacturer=None, name="Repository fixture", system_family="BRS",
        type_code="mobile", subtype_code=None, maturity_status=None, trl=None, description=None,
        attributes={}, facts=facts, applicability=(), procurement_options=(), runtime_robot=None,
        runtime_blockers=(), capacity_runtime=CapacityRuntimeDTO(
            calculation_readiness_status="CALCULATION_READY", calculation_ready=True,
            calculation_requires_assumptions=False, calculation_profile="TRANSPORT_CYCLE_V1",
            calculation_blockers=(), runtime_catalog_version="fixture-v1",
            calculation_model_fields=("specs.max_speed", "specs.payload"), vendor_facts=facts,
        ),
    )
    projection = model.formula_executability_dto(position_id="position.repository")
    candidate = candidate_from_repository(projection)
    assert candidate.position_id == "position.repository"
    assert {item.field_path for item in candidate.facts} == {"specs.max_speed", "specs.payload"}
    assert "procurement" not in repr(projection).lower()
    assert "price" not in repr(projection).lower()


def test_full_audit_is_golden_exact_ordered_187_223_with_fixed_pool_and_no_bas():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    diff = json.loads(POOL_DIFF.read_text(encoding="utf-8"))
    assert report["counts"] == {
        "candidate_pool_models": 21, "candidate_pool_positions": 24,
        "models": 187, "positions": 223,
    }
    assert report["model_status_counts"] == {
        "CATALOG_EXECUTABLE": 21, "INVALID_FACT": 0, "MISSING_SAFE_FACT": 19,
        "NOT_EQUIPMENT": 4, "UNKNOWN_IDENTITY": 0, "UNSUPPORTED_PROFILE": 143,
    }
    assert report["position_status_counts"]["CATALOG_EXECUTABLE"] == 24
    assert len(report["models"]) == 187 and len(report["positions"]) == 223
    assert [item["model_id"] for item in report["models"]] == sorted(item["model_id"] for item in report["models"])
    assert [item["source_row_number"] for item in report["positions"]] == list(range(2, 225))
    assert diff["added_model_ids"] == diff["removed_model_ids"] == []
    assert diff["added_position_ids"] == diff["removed_position_ids"] == []
    assert len(diff["candidate_model_ids"]) == 21 and len(diff["candidate_position_ids"]) == 24
    assert report["invariants"]["bas_in_candidate_pool"] is False
    assert all(item["system_family"] != "BAS" for item in report["models"] if item["result"]["catalog_status"] == "CATALOG_EXECUTABLE")


def test_generated_c06_artifacts_are_current_and_deterministic():
    command = [sys.executable, str(ROOT / "scripts" / "build_catalog_formula_executability_v3.py"), "--check"]
    first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
