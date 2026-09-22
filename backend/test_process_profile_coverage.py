from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.intake import PROCESS_DEFINITIONS
from calculation.process_profiles.catalog import load_process_profile_catalog
from calculation.process_profiles.router import route_process
from calculation.process_profiles.user_cycle import UserCycleRequestV1, batch_jobs, calculate_user_cycle
from calculation_contracts import KnownQuantity, NormalizedProcess, ProcessCode, VersionBindings, canonical_json_bytes, semantic_digest

ROOT = Path(__file__).resolve().parents[1]


def q(name: str, value: str, unit: str, kind: str, provenance: str = "prov.user") -> KnownQuantity:
    return KnownQuantity(name=name, raw_value=value, raw_unit=unit, normalized_value=value,
                         unit=unit, quantity_kind=kind, provenance_ref=provenance)


def process(code: str, *, active: bool = True, kind: str | None = None) -> NormalizedProcess:
    definition = PROCESS_DEFINITIONS[ProcessCode(code)]
    quantity_kind = kind or str(definition.allowed_kinds[0])
    unit_by_kind = {
        "PALLET": "pallet/day", "BOX": "box/day", "CASE": "case/day", "CART": "cart/day",
        "DELIVERY": "delivery/day", "PORTION": "portion/day", "KILOGRAM": "kg/day",
        "SAMPLE": "sample/day", "SET": "set/day", "BIN": "bin/day", "ITEM": "item/day",
        "SQUARE_METER": "m2/day", "PICK": "pick/day", "DIGITAL_FLOW": "item/day",
    }
    return NormalizedProcess.model_validate({
        "process_id": f"process.{code.replace('_', '.')}", "input_revision": "revision.c10.v1",
        "object_kind": definition.object_kind, "process_code": code, "scope": definition.scope,
        "active": active, "quantity_kind": quantity_kind,
        "demand": q("demand_per_day", "1000", unit_by_kind[quantity_kind], "FLOW").model_dump(),
        "schedule": {
            "shifts_per_day": q("shifts_per_day", "2", "shift", "COUNT").model_dump(),
            "shift_hours": q("shift_hours", "10", "h", "TIME").model_dump(),
            "days_per_year": q("days_per_year", "365", "day", "TIME").model_dump(),
        },
        "role_refs": [],
    })


def versions() -> VersionBindings:
    digest = semantic_digest({"fixture": "c10"})
    return VersionBindings(
        catalog_version_id="c10-synthetic", catalog_content_digest=digest,
        capacity_projection_version="calculation-process-projection-v2", capacity_projection_digest=digest,
        registry_version="hackathon-calculation-parameter-registry-v1", registry_digest=digest,
        process_catalog_version="calculation-process-catalog-v1", formula_bundle_version="calculation-formulas-v1",
        constraint_rules_version="calculation-constraint-rules-v2",
        commercial_policy_version="hackathon-commercial-policy-v1",
        precision_policy_version="decimal-context-28-half-even-v1",
        calculation_policy_version="hackathon-calculation-policy-v1",
    )


def user_cycle_request(code: str = "warehouse_inventory") -> UserCycleRequestV1:
    return UserCycleRequestV1(
        run_id="run.c10.user-cycle", process=process(code),
        cycle_time=q("cycle_time", "120", "s", "TIME"),
        units_per_cycle=q("units_per_cycle", "2", "unit/cycle", "RATE"),
        availability=q("availability", "0.8", "1", "FRACTION", "prov.assumption.availability"),
        selected_fleet=q("fleet_selected", "1", "robot", "COUNT"), versions=versions(), provenance=[
            {"provenance_id": "prov.user", "kind": "USER", "confirmation_revision": "revision.c10.v1"},
            {"provenance_id": "prov.assumption.availability", "kind": "ASSUMPTION",
             "assumption_id": "availability", "assumption_version": "policy-v1",
             "rationale": "Explicit C10 availability fixture", "permitted_scope": "USER_CYCLE",
             "confirmation_state": "POLICY_ACCEPTED"},
        ])


def test_exact_28_rows_match_c03_mapping_and_all_enums():
    catalog = load_process_profile_catalog()
    assert len(catalog.profiles) == len(ProcessCode) == 28
    assert [row.microstage_id for row in catalog.profiles] == [f"C10.{i:02d}" for i in range(1, 29)]
    assert {row.process_code for row in catalog.profiles} == set(ProcessCode)
    for row in catalog.profiles:
        definition = PROCESS_DEFINITIONS[row.process_code]
        assert row.object_kind == definition.object_kind
        assert row.scope == definition.scope
        assert tuple(row.default_role_codes) == definition.roles
        assert tuple(row.allowed_quantity_kinds) == definition.allowed_kinds
        assert row.has_fot_savings is bool(definition.roles)
        assert "POLICY_V1:K19" in row.source_refs


def test_formula_routing_reference_reasons_and_constraint_checks():
    formula_handlers = {
        "TRANSPORT": 14, "CLEANING": 4, "PALLETIZING": 1, "NONE": 9,
    }
    catalog = load_process_profile_catalog()
    rules = json.loads((ROOT / "data/calculation/constraint-rules-v2.json").read_text(encoding="utf-8"))
    known_checks = {item["rule_id"] for item in rules["rules"]}
    assert {key: sum(row.capacity_handler == key for row in catalog.profiles)
            for key in formula_handlers} == formula_handlers
    for row in catalog.profiles:
        assert set(row.applicable_checks) <= known_checks
        decision = route_process(process(str(row.process_code)))
        if row.capacity_handler == "NONE":
            assert decision.engine is None and decision.reason_code == row.unsupported_reason_code
            assert row.required_inputs in (["DISCOVERY_INPUTS"], ["CONSTRAINT_CONTEXT"])
        else:
            assert decision.engine is not None and decision.formula_ids == row.formula_ids
    safety = catalog.by_code("clinic_safety_requirements")
    assert safety.default_role_codes == [] and safety.has_fot_savings is False
    assert {"class-b-containment", "sanitization", "access-protocols"} <= set(safety.applicable_checks)


def test_digital_results_inactive_and_user_cycle_routing_are_explicit():
    assert route_process(process("clinic_results", kind="DIGITAL_FLOW")).reason_code == "digital-flow-has-no-physical-fleet"
    assert route_process(process("warehouse_cleaning", active=False)).disposition == "NOT_APPLICABLE"
    decision = route_process(process("warehouse_inventory"), use_user_cycle=True)
    assert decision.disposition == "USER_CYCLE" and decision.engine == "C10_USER_CYCLE"
    with pytest.raises(ValueError, match="REFERENCE_ONLY"):
        route_process(process("warehouse_cleaning"), use_user_cycle=True)


def test_user_cycle_dimensional_golden_and_replay_stability():
    result = calculate_user_cycle(user_cycle_request())
    golden = json.loads((ROOT / "contracts/fixtures/user-cycle-capacity-v1.synthetic.golden.json").read_text(encoding="utf-8"))
    actual = {key: getattr(result, key) for key in golden}
    assert actual == golden
    assert canonical_json_bytes(result) == canonical_json_bytes(calculate_user_cycle(user_cycle_request()))


def test_user_cycle_rejects_vendor_fact_and_non_reference_profile():
    raw = user_cycle_request().model_dump(mode="json")
    raw["provenance"][0] = {
        "provenance_id": "prov.user", "kind": "VENDOR_FACT", "fact_id": "bad.generic-cycle",
        "model_id": "bad-model", "position_id": "bad-position", "scope": "generic-cycle",
        "evidence_ids": ["bad-evidence"], "evidence_status": "VERIFIED_OFFICIAL",
        "permitted_for_matching": True,
    }
    with pytest.raises(ValidationError, match="USER/FILE"):
        UserCycleRequestV1.model_validate(raw)
    raw = user_cycle_request().model_dump(mode="json")
    raw["process"] = process("warehouse_cleaning").model_dump(mode="json")
    with pytest.raises(ValidationError, match="REFERENCE_ONLY"):
        UserCycleRequestV1.model_validate(raw)


def test_batch_conversion_requires_dimension_match_or_explicit_conversion():
    assert batch_jobs(Decimal(101), Decimal(20), raw_kind="ITEM", item_kind="ITEM") == 6
    assert batch_jobs(Decimal(100), Decimal(25), raw_kind="ITEM", item_kind="ITEM") == 4
    assert batch_jobs(Decimal(100), Decimal(20), raw_kind="KILOGRAM", item_kind="ITEM",
                      explicit_conversion_factor=Decimal("0.5")) == 3
    with pytest.raises(ValueError, match="mixed quantity kinds"):
        batch_jobs(Decimal(100), Decimal(20), raw_kind="KILOGRAM", item_kind="ITEM")
    with pytest.raises(ValueError, match="denominator"):
        batch_jobs(Decimal(1), Decimal(0), raw_kind="ITEM", item_kind="ITEM")


def test_catalog_is_ui_metadata_only_and_pool_is_unchanged():
    catalog = load_process_profile_catalog()
    assert (catalog.candidate_pool_models, catalog.candidate_pool_positions, catalog.pool_membership_changed) == (21, 24, False)
    payload = json.loads((ROOT / "data/calculation/process-profile-catalog-v1.json").read_text(encoding="utf-8"))
    forbidden = {"price", "capex", "opex", "salary", "model_ids", "position_ids", "vendor"}
    assert not forbidden.intersection(payload)
    for row in catalog.profiles:
        assert row.ui.show_capacity_action is (row.capacity_handler != "NONE")


def test_warehouse_full_flow_has_all_accepted_dispositions():
    expected = {
        "warehouse_receiving_shipping": "TRANSPORT",
        "warehouse_storage": "REFERENCE_ONLY",
        "warehouse_picking": "REFERENCE_ONLY",
        "warehouse_palletizing": "PALLETIZING",
        "warehouse_cleaning": "CLEANING",
        "warehouse_inventory": "REFERENCE_ONLY",
    }
    assert {code: route_process(process(code)).disposition for code in expected} == expected


def test_generated_artifacts_are_current():
    from scripts.build_process_profile_catalog_v1 import expected_files
    for path, expected in expected_files():
        assert path.read_bytes() == expected
