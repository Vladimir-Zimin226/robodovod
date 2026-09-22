from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from calculation.capacity.quantities import ceil_exact, cycle_time, operating_hours, resolve_batch, size_fleet
from calculation.capacity.transport import TransportCapacityRequestV1, calculate_transport_capacity
from calculation.constraints import ConstraintReportV2
from calculation.executability import CatalogCandidateInput, ScenarioValue, evaluate_run_executability, registry_payload
from calculation_contracts import (
    KnownQuantity,
    NormalizedProcess,
    VendorFactProvenance,
    VersionBindings,
    canonical_json_bytes,
    semantic_digest,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "fixtures" / "transport-capacity-v1.golden.json"


def q(name: str, value: str, unit: str, kind: str, provenance: str = "prov.user") -> KnownQuantity:
    return KnownQuantity(name=name, raw_value=value, raw_unit=unit, normalized_value=value,
                         unit=unit, quantity_kind=kind, provenance_ref=provenance)


def candidate(status: str = "MATCHING_SAFE", profile: str = "TRANSPORT_CYCLE_V1") -> CatalogCandidateInput:
    return CatalogCandidateInput.model_validate({
        "model_id": "model.synthetic.transport", "position_id": "position.synthetic.transport",
        "name": "Synthetic transport", "system_family": "SYNTHETIC_TEST_ONLY",
        "identity_status": "MATCHED", "profile_id": profile,
        "readiness_v2_status": "CALCULATION_READY", "facts": [
            {"field_path": "specs.max_speed", "value": "1", "unit": "m/s", "evidence_status": status, "source_refs": ["fixture:speed"]},
            {"field_path": "specs.payload", "value": "1000", "unit": "kg", "evidence_status": "MATCHING_SAFE", "source_refs": ["fixture:payload"]},
        ]})


def scenario(batch: str = "1", selected: str | None = None, demand_unit: str = "pallet/day") -> list[ScenarioValue]:
    values = [
        ("process.demand_per_day", "2000", demand_unit),
        ("process.exchange_total_time_s", "90", "s"),
        ("process.one_way_distance_m", "120", "m"),
        ("process.shift_hours", "11", "h"),
        ("process.shifts_per_day", "2", "shift"),
        ("process.units_per_trip", batch, "unit/trip"),
    ]
    if selected is not None:
        values.append(("run.selected_fleet_units", selected, "robot"))
    return [ScenarioValue(input_path=path, value=value, unit=unit, source_ref=f"fixture:{path}")
            for path, value, unit in values]


def process(*, quantity_kind: str = "PALLET", exchange_mode: str = "TOTAL", active: bool = True,
            delivery: bool = False) -> NormalizedProcess:
    exchange = ({"mode": "TOTAL", "total_time": q("exchange_total_time", "90", "s", "TIME").model_dump()}
                if exchange_mode == "TOTAL" else
                {"mode": "SPLIT", "load_time": q("load_time", "45", "s", "TIME").model_dump(),
                 "unload_time": q("unload_time", "45", "s", "TIME").model_dump()})
    demand_unit = "delivery/day" if delivery else ("box/day" if quantity_kind == "BOX" else "pallet/day")
    return NormalizedProcess.model_validate({
        "process_id": "process.synthetic.delivery" if delivery else "process.synthetic.transport", "input_revision": "revision.synthetic.v1",
        "object_kind": "CLINIC" if delivery else "WAREHOUSE",
        "process_code": "clinic_medicines" if delivery else "warehouse_receiving_shipping",
        "scope": "DELIVERY_CYCLE" if delivery else "TRANSPORT_CYCLE", "active": active, "quantity_kind": quantity_kind,
        "demand": q("demand_per_day", "2000", demand_unit, "FLOW").model_dump(),
        "schedule": {"shifts_per_day": q("shifts_per_day", "2", "shift", "COUNT").model_dump(),
                     "shift_hours": q("shift_hours", "11", "h", "TIME").model_dump(),
                     "days_per_year": q("days_per_year", "250", "day", "TIME").model_dump()},
        "route_distance": q("one_way_distance", "120", "m", "DISTANCE").model_dump(),
        "exchange": exchange,
        "explicit_batch": q("units_per_trip", "1", "unit/trip", "RATE").model_dump(),
    })


def request(*, selected: int | None = None, exchange_mode: str = "TOTAL",
            quantity_kind: str = "PALLET", unsafe: bool = False,
            operating_speed: str | None = None, delivery: bool = False) -> TransportCapacityRequestV1:
    selected_text = None if selected is None else str(selected)
    profile = "DELIVERY_CYCLE_V1" if delivery else "TRANSPORT_CYCLE_V1"
    demand_unit = "delivery/day" if delivery else ("box/day" if quantity_kind == "BOX" else "pallet/day")
    scenario_batch = "16" if quantity_kind == "BOX" else "1"
    run = evaluate_run_executability(candidate("CONFLICT" if unsafe else "MATCHING_SAFE", profile),
                                     scenario(batch=scenario_batch, selected=selected_text, demand_unit=demand_unit), "ELIGIBLE", registry_payload())
    proc = process(quantity_kind=quantity_kind, exchange_mode=exchange_mode, delivery=delivery)
    if quantity_kind == "BOX":
        proc.explicit_batch = None
    provenance_scope = "DELIVERY_CYCLE" if delivery else "TRANSPORT_CYCLE"
    provenance = [
        {"provenance_id": "prov.user", "kind": "USER", "confirmation_revision": proc.input_revision},
        VendorFactProvenance(provenance_id="prov.fact.speed", fact_id="fact.max-speed",
            model_id="model.synthetic.transport", position_id="position.synthetic.transport",
            scope=provenance_scope, evidence_ids=["evidence.speed"], evidence_status="VERIFIED_OFFICIAL",
            permitted_for_matching=True),
        VendorFactProvenance(provenance_id="prov.fact.payload", fact_id="fact.payload",
            model_id="model.synthetic.transport", position_id="position.synthetic.transport",
            scope=provenance_scope, evidence_ids=["evidence.payload"], evidence_status="VERIFIED_OFFICIAL",
            permitted_for_matching=True),
    ]
    manifest = json.loads((ROOT / "data/calculation/registry-v1.manifest.json").read_text(encoding="utf-8"))
    versions = VersionBindings(
        catalog_version_id="synthetic-catalog-v1", catalog_content_digest=semantic_digest(candidate()),
        capacity_projection_version="formula-executability-profiles-v3",
        capacity_projection_digest=semantic_digest(json.loads((ROOT / "data/calculation/formula-executability-profiles-v3.json").read_text(encoding="utf-8"))),
        registry_version="hackathon-calculation-parameter-registry-v1",
        registry_digest=manifest["registry_semantic_digest"], process_catalog_version="calculation-process-catalog-v1",
        formula_bundle_version="calculation-formulas-v1", constraint_rules_version="calculation-constraint-rules-v2",
        commercial_policy_version="hackathon-commercial-policy-v1",
        precision_policy_version="decimal-context-28-half-even-v1",
        calculation_policy_version="hackathon-calculation-policy-v1")
    return TransportCapacityRequestV1(
        run_id=f"run.synthetic.{selected_text or 'recommended'}.{exchange_mode.lower()}", acquisition="PURCHASE",
        uncertainty="BASE", process=proc, model_id="model.synthetic.transport",
        position_id="position.synthetic.transport", exchange=proc.exchange,
        operating_speed=None if operating_speed is None else q("operating_speed", operating_speed, "m/s", "SPEED"),
        item_mass=q("item_mass", "60", "kg/unit", "RATE") if quantity_kind == "BOX" else None,
        selected_fleet=None if selected is None else q("fleet_selected", selected_text, "robot", "COUNT"),
        executability=run, constraints=ConstraintReportV2(input_revision=proc.input_revision,
            process_id=proc.process_id, model_id="model.synthetic.transport", position_id="position.synthetic.transport",
            eligibility="ELIGIBLE", checks=[], blocker_codes=[], validation_codes=[], warning_codes=[]),
        versions=versions, provenance=provenance,
        fact_provenance={"fact.max-speed": "prov.fact.speed", "fact.payload": "prov.fact.payload"})


def test_golden_transport_synthetic_and_byte_stable_replay():
    result = calculate_transport_capacity(request())
    assert result.capacity.value.recommended_fleet == 18
    assert next(item for item in result.trace.intermediates if item.name == "cycle_time").value.value == "330"
    assert next(item for item in result.trace.intermediates if item.name == "nominal_capacity").value.value == "10.90909090909090909090909091"
    assert canonical_json_bytes(result) == canonical_json_bytes(calculate_transport_capacity(request()))
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = {
        "recommended_fleet": result.capacity.value.recommended_fleet,
        "cycle_time_s": next(item for item in result.trace.intermediates if item.name == "cycle_time").value.value,
        "nominal_units_per_hour": next(item for item in result.trace.intermediates if item.name == "nominal_capacity").value.value,
        "effective_units_per_hour": next(item for item in result.trace.intermediates if item.name == "effective_capacity").value.value,
        "required_units_per_hour": next(item for item in result.trace.intermediates if item.name == "required_capacity").value.value,
        "formula_ids": [item.formula_id for item in result.trace.formula_nodes],
        "decision_refs": result.trace.provenance[-2].decision_refs,
        "registry_version": result.trace.versions.registry_version,
        "precision_policy_version": result.trace.versions.precision_policy_version,
    }
    assert actual == expected


@pytest.mark.parametrize("selected,coverage,overloaded", [
    (17, "0.952", True), (18, "1", False), (19, "1", False)])
def test_manual_fleet_17_18_19_uses_actual_capacity(selected, coverage, overloaded):
    value = calculate_transport_capacity(request(selected=selected)).capacity.value
    assert Decimal(value.coverage.value).quantize(Decimal("0.001")) == Decimal(coverage)
    assert value.overloaded is overloaded
    assert value.raw_load_ratio is not None


def test_selected_zero_and_inactive_block_semantics():
    zero = calculate_transport_capacity(request(selected=0)).capacity.value
    assert zero.nominal_capacity.value == zero.effective_capacity.value == zero.coverage.value == "0"
    assert zero.raw_load_ratio is None and zero.utilization is None and zero.overloaded is True
    inactive_request = request()
    inactive_request.process.active = False
    inactive = calculate_transport_capacity(inactive_request)
    assert inactive.capacity.status == "NOT_APPLICABLE" and inactive.capacity.value is None


def test_total_and_split_exchange_are_equivalent_but_trace_the_source_shape():
    total = calculate_transport_capacity(request(exchange_mode="TOTAL"))
    split = calculate_transport_capacity(request(exchange_mode="SPLIT"))
    assert total.capacity.value.recommended_fleet == split.capacity.value.recommended_fleet == 18
    assert len([item for item in total.trace.inputs if item.name in {"exchange_total_time", "load_time", "unload_time"}]) == 1
    assert len([item for item in split.trace.inputs if item.name in {"exchange_total_time", "load_time", "unload_time"}]) == 2


def test_delivery_uses_same_typed_cycle_math_without_catalog_pool_expansion():
    result = calculate_transport_capacity(request(quantity_kind="DELIVERY", delivery=True))
    assert result.capacity.value.recommended_fleet == 18
    assert result.trace.envelope.process_id == "process.synthetic.delivery"
    assert result.trace.formula_nodes[1].applicability_domain == "TRANSPORT_OR_DELIVERY_CYCLE"


def test_box_floor_and_override_above_mass_limit_is_blocked():
    assert resolve_batch(box_mode=True, payload_kg=Decimal("100"), item_mass_kg=Decimal("6"),
                         explicit_limit=None) == (Decimal("16"), 16)
    with pytest.raises(ValueError, match="exceeds"):
        resolve_batch(box_mode=True, payload_kg=Decimal("100"), item_mass_kg=Decimal("6"),
                      explicit_limit=Decimal("17"))
    result = calculate_transport_capacity(request(quantity_kind="BOX"))
    assert result.capacity.status == "WITH_ASSUMPTIONS"
    assert next(item for item in result.trace.inputs if item.name == "units_per_trip").normalized_value == "16"
    assert [item.operation for item in result.trace.roundings] == ["FLOOR", "CEIL"]
    assert any(issue.code == "box-geometry-limit-unknown" for issue in result.capacity.warnings)


def test_exact_ceil_boundaries_and_monotonicity():
    assert ceil_exact(Decimal("18")) == 18
    assert ceil_exact(Decimal("18.00000000000000000000000001")) == 19
    assert operating_hours(Decimal(2), Decimal(11)) == 22
    with pytest.raises(ValueError, match="without clamp"):
        operating_hours(Decimal(3), Decimal(11))
    assert cycle_time(Decimal(120), Decimal(2), Decimal(90)) < cycle_time(Decimal(120), Decimal(1), Decimal(90))
    fleet = lambda demand: size_fleet(demand_per_day=Decimal(demand), operating_hours_per_day=Decimal(22),
        intraday_peak=Decimal("1.25"), reserve_share=Decimal("0.20"),
        nominal_units_per_hour=Decimal(120) / Decimal(11), availability=Decimal("0.70"))[-1]
    assert fleet("1000") <= fleet("2000") <= fleet("3000")
    with pytest.raises(ValueError, match="without clamp"):
        operating_hours(Decimal(0), Decimal(11))
    with pytest.raises(ValueError, match="non-negative"):
        cycle_time(Decimal(-1), Decimal(1), Decimal(90))


@pytest.mark.parametrize("speed", ["0", "1.01"])
def test_zero_or_unsafe_user_speed_is_blocked(speed):
    result = calculate_transport_capacity(request(operating_speed=speed))
    assert result.capacity.status == "BLOCKED"
    assert result.capacity.value is None


def test_user_operating_speed_origin_is_used_without_proxy_assumption():
    result = calculate_transport_capacity(request(operating_speed="0.8"))
    speed = next(item for item in result.trace.inputs if item.name == "operating_speed")
    assert result.capacity.status == "COMPLETE"
    assert speed.provenance_ref == "prov.user"
    assert result.trace.assumptions == []


def test_c06_rejects_unsafe_fact_before_formula_execution():
    result = calculate_transport_capacity(request(unsafe=True))
    assert result.capacity.status == "BLOCKED"
    assert result.trace.formula_nodes == []


def test_no_hidden_target_utilization_constant():
    source = (ROOT / "backend/calculation/capacity/transport.py").read_text(encoding="utf-8")
    assert "0.90" not in source and "target_util" not in source


def test_every_trace_numeric_input_has_unit_and_resolved_provenance():
    trace = calculate_transport_capacity(request()).trace
    provenance_ids = {item.provenance_id for item in trace.provenance}
    assert trace.inputs
    assert all(item.unit and item.raw_unit and item.provenance_ref in provenance_ids for item in trace.inputs)


def test_stale_c06_scenario_snapshot_is_blocked():
    stale = request()
    stale.process.demand.normalized_value = "2001"
    result = calculate_transport_capacity(stale)
    assert result.capacity.status == "BLOCKED"
    assert "differs from the C06 run snapshot" in result.capacity.blockers[0].message
