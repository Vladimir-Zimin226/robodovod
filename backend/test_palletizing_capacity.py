from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.capacity.palletizing import PalletizingCapacityRequestV1, calculate_palletizing_capacity
from calculation.capacity.quantities import palletizing_capacity
from calculation.constraints import ConstraintReportV2
from calculation.executability import (
    CatalogCandidateInput,
    RunExecutabilityResult,
    ScenarioValue,
    evaluate_run_executability,
    registry_payload,
)
from calculation_contracts import KnownQuantity, NormalizedProcess, VersionBindings, canonical_json_bytes, semantic_digest

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "contracts/fixtures/palletizing-capacity-v1.synthetic.golden.json"
AUDIT = ROOT / "data/review/catalog-formula-executability-audit-v3.json"


def q(name: str, value: str, unit: str, kind: str, provenance: str = "prov.user") -> KnownQuantity:
    return KnownQuantity(name=name, raw_value=value, raw_unit=unit, normalized_value=value,
                         unit=unit, quantity_kind=kind, provenance_ref=provenance)


def candidate(status: str = "MATCHING_SAFE") -> CatalogCandidateInput:
    return CatalogCandidateInput.model_validate({
        "model_id": "synthetic.palletizing.cell", "position_id": "synthetic.palletizing.position",
        "name": "Explicit synthetic palletizing cell", "system_family": "SYNTHETIC_TEST_ONLY",
        "identity_status": "MATCHED", "profile_id": "PALLETIZING_THROUGHPUT_V1",
        "readiness_v2_status": "CALCULATION_READY", "facts": [{
            "field_path": "specs.throughput", "value": "10", "unit": "pick/min",
            "evidence_status": status, "source_refs": ["synthetic-assumption:pick-rate"],
        }],
    })


def scenario(selected: int | None = None) -> list[ScenarioValue]:
    raw = [
        ("process.demand_per_day", "2000", "pallet/day"),
        ("process.shift_hours", "11", "h"),
        ("process.shifts_per_day", "2", "shift"),
    ]
    if selected is not None:
        raw.append(("run.selected_fleet_units", str(selected), "robot"))
    return [ScenarioValue(input_path=path, value=value, unit=unit, source_ref=f"fixture:{path}")
            for path, value, unit in raw]


def process(active: bool = True) -> NormalizedProcess:
    return NormalizedProcess.model_validate({
        "process_id": "process.warehouse.palletizing", "input_revision": "revision.palletizing.v1",
        "object_kind": "WAREHOUSE", "process_code": "warehouse_palletizing", "scope": "FIXED_CELL",
        "active": active, "quantity_kind": "PALLET",
        "demand": q("demand_per_day", "2000", "pallet/day", "FLOW").model_dump(),
        "schedule": {
            "shifts_per_day": q("shifts_per_day", "2", "shift", "COUNT").model_dump(),
            "shift_hours": q("shift_hours", "11", "h", "TIME").model_dump(),
            "days_per_year": q("days_per_year", "365", "day", "TIME").model_dump(),
        },
    })


def versions(candidate_value: CatalogCandidateInput) -> VersionBindings:
    manifest = json.loads((ROOT / "data/calculation/registry-v1.manifest.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "data/calculation/formula-executability-profiles-v3.json").read_text(encoding="utf-8"))
    return VersionBindings(
        catalog_version_id="synthetic-palletizing-catalog-v1", catalog_content_digest=semantic_digest(candidate_value),
        capacity_projection_version="formula-executability-profiles-v3", capacity_projection_digest=semantic_digest(profiles),
        registry_version="hackathon-calculation-parameter-registry-v1",
        registry_digest=manifest["registry_semantic_digest"],
        process_catalog_version="calculation-process-catalog-v1", formula_bundle_version="calculation-formulas-v1",
        constraint_rules_version="calculation-constraint-rules-v2",
        commercial_policy_version="hackathon-commercial-policy-v1",
        precision_policy_version="decimal-context-28-half-even-v1",
        calculation_policy_version="hackathon-calculation-policy-v1",
    )


def request(*, selected: int | None = None, unsafe: bool = False, missing_rate: bool = False,
            unsupported: bool = False) -> PalletizingCapacityRequestV1:
    candidate_value = candidate("UNKNOWN" if unsafe else "MATCHING_SAFE")
    if unsupported:
        run = RunExecutabilityResult(model_id=candidate_value.model_id, position_id=candidate_value.position_id,
            profile_id=None, status="UNSUPPORTED_PROFILE", dependencies=[], blocker_codes=["unsupported-profile"])
    else:
        run = evaluate_run_executability(candidate_value, scenario(selected), "ELIGIBLE", registry_payload())
    proc = process()
    provenance = [
        {"provenance_id": "prov.user", "kind": "USER", "confirmation_revision": proc.input_revision},
        {"provenance_id": "prov.assumption.pick-rate", "kind": "ASSUMPTION",
         "assumption_id": "synthetic-pick-rate", "assumption_version": "fixture-v1",
         "rationale": "Explicit synthetic pick/min rate; not a catalog vendor fact",
         "permitted_scope": "PALLETIZING_THROUGHPUT_V1", "confirmation_state": "USER_CONFIRMED"},
    ]
    return PalletizingCapacityRequestV1(
        run_id=f"run.synthetic.palletizing.{selected if selected is not None else 'recommended'}",
        acquisition="PURCHASE", uncertainty="BASE", process=proc,
        model_id=candidate_value.model_id, position_id=candidate_value.position_id,
        cell_rate=None if missing_rate else q("cell_rate", "10", "pick/min", "RATE", "prov.assumption.pick-rate"),
        selected_fleet=None if selected is None else q("fleet_selected", str(selected), "robot", "COUNT"),
        executability=run,
        constraints=ConstraintReportV2(input_revision=proc.input_revision, process_id=proc.process_id,
            model_id=candidate_value.model_id, position_id=candidate_value.position_id,
            eligibility="ELIGIBLE", checks=[], blocker_codes=[], validation_codes=[], warning_codes=[]),
        versions=versions(candidate_value), provenance=provenance,
    )


def test_golden_dimensional_chain_and_byte_stable_replay():
    result = calculate_palletizing_capacity(request())
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = {
        "picks_per_hour": next(x for x in result.trace.intermediates if x.name == "picks_per_hour").value.value,
        "boxes_per_day": next(x for x in result.trace.intermediates if x.name == "boxes_per_day").value.value,
        "nominal_pallets_per_day": next(x for x in result.trace.intermediates if x.name == "pallets_per_day").value.value,
        "effective_pallets_per_day": next(x for x in result.trace.intermediates if x.name == "effective_capacity").value.value,
        "recommended_cells": result.capacity.value.recommended_fleet,
        "formula_ids": [node.formula_id for node in result.trace.formula_nodes],
        "conversion": result.trace.conversions[0].model_dump(mode="json"),
    }
    assert result.capacity.status == "WITH_ASSUMPTIONS"
    assert actual == expected
    assert canonical_json_bytes(result) == canonical_json_bytes(calculate_palletizing_capacity(request()))


def test_output_20_boxes_per_pallet_is_not_receiving_33():
    args = dict(demand_pallets_day=Decimal(2000), rate_picks_minute=Decimal(10),
                operating_hours_day=Decimal(22), cell_efficiency=Decimal("0.65"), availability=Decimal("0.70"))
    output_20 = palletizing_capacity(boxes_per_pallet=Decimal(20), **args)
    receiving_33 = palletizing_capacity(boxes_per_pallet=Decimal(33), **args)
    assert output_20[2:] == (Decimal(429), Decimal("300.30"), 7)
    assert receiving_33[-1] == 11
    trace_input = next(x for x in calculate_palletizing_capacity(request()).trace.inputs if x.name == "boxes_per_pallet")
    assert trace_input.normalized_value == "20" and trace_input.unit == "box/pallet"


def test_zero_denominator_and_wrong_rate_unit_are_rejected():
    with pytest.raises(ValueError, match="denominator"):
        palletizing_capacity(demand_pallets_day=Decimal(1), rate_picks_minute=Decimal(10),
            operating_hours_day=Decimal(1), cell_efficiency=Decimal(1),
            boxes_per_pallet=Decimal(0), availability=Decimal(1))
    with pytest.raises(ValidationError):
        q("cell_rate", "10", "unit/min", "RATE", "prov.assumption.pick-rate")
    raw = request().model_dump(mode="json")
    raw["process"]["quantity_kind"] = "CASE"
    raw["process"]["demand"]["raw_unit"] = "case/day"
    raw["process"]["demand"]["unit"] = "case/day"
    with pytest.raises(ValidationError, match="pallet FIXED_CELL"):
        PalletizingCapacityRequestV1.model_validate(raw)


@pytest.mark.parametrize("selected,coverage,overloaded", [
    (6, "0.9009", True), (7, "1", False), (8, "1", False)])
def test_manual_cells_use_actual_capacity(selected, coverage, overloaded):
    value = calculate_palletizing_capacity(request(selected=selected)).capacity.value
    assert value.coverage.value == coverage
    assert value.overloaded is overloaded


def test_unknown_or_missing_rate_and_unsupported_profile_are_blocked():
    for item in (request(unsafe=True), request(missing_rate=True), request(unsupported=True)):
        result = calculate_palletizing_capacity(item)
        assert result.capacity.status == "BLOCKED"
        assert result.trace.formula_nodes == []


def test_resolver_integration_and_no_catalog_pool_admission():
    run = request().executability
    assert run.status == "EXECUTABLE"
    assert {item.requirement_id for item in run.dependencies} >= {
        "fact.cell-rate", "policy.boxes-per-pallet", "policy.cell-efficiency", "policy.availability"
    }
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    models = [x for x in audit["models"] if x["result"]["profile_id"] == "PALLETIZING_THROUGHPUT_V1"
              and x["result"]["catalog_status"] == "CATALOG_EXECUTABLE"]
    positions = [x for x in audit["positions"] if x["result"]["profile_id"] == "PALLETIZING_THROUGHPUT_V1"
                 and x["result"]["catalog_status"] == "CATALOG_EXECUTABLE"]
    assert models == positions == []


def test_inactive_zero_and_no_transport_or_finance_semantics():
    inactive = request()
    inactive.process.active = False
    assert calculate_palletizing_capacity(inactive).capacity.status == "NOT_APPLICABLE"
    zero = calculate_palletizing_capacity(request(selected=0)).capacity.value
    assert zero.effective_capacity.value == zero.coverage.value == "0"
    assert zero.utilization is None and zero.overloaded is True
    response = calculate_palletizing_capacity(request())
    names = {str(item.name) for item in response.trace.inputs}
    assert not names.intersection({"peak_factor", "reserve_share", "payload", "units_per_trip"})
    assert all(item.provenance_ref in {p.provenance_id for p in response.trace.provenance}
               for item in response.trace.inputs)
    assert "financial" not in response.model_dump(mode="json")


def test_monotonicity_and_efficiency_applied_once():
    fleet = lambda demand, rate, availability: palletizing_capacity(
        demand_pallets_day=Decimal(demand), rate_picks_minute=Decimal(rate),
        operating_hours_day=Decimal(22), cell_efficiency=Decimal("0.65"),
        boxes_per_pallet=Decimal(20), availability=Decimal(availability))[-1]
    assert fleet(1000, 10, ".7") <= fleet(2000, 10, ".7")
    assert fleet(2000, 8, ".7") >= fleet(2000, 10, ".7")
    assert fleet(2000, 10, ".55") >= fleet(2000, 10, ".8")
    result = palletizing_capacity(demand_pallets_day=Decimal(2000), rate_picks_minute=Decimal(10),
        operating_hours_day=Decimal(22), cell_efficiency=Decimal("0.65"),
        boxes_per_pallet=Decimal(20), availability=Decimal("0.70"))
    assert result[1] == Decimal(10) * Decimal(60) * Decimal(22) * Decimal("0.65")
