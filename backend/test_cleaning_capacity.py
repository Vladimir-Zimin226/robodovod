from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.capacity.cleaning import CleaningCapacityRequestV1, calculate_cleaning_capacity
from calculation.capacity.quantities import cleaning_capacity
from calculation.constraints import ConstraintReportV2
from calculation.executability import CatalogCandidateInput, ScenarioValue, evaluate_run_executability, registry_payload
from calculation_contracts import KnownQuantity, NormalizedProcess, VendorFactProvenance, VersionBindings, canonical_json_bytes, semantic_digest

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "contracts/fixtures/cleaning-capacity-v1.airport.golden.json"
AUDIT = ROOT / "data/review/catalog-formula-executability-audit-v3.json"


def q(name: str, value: str, unit: str, kind: str, provenance: str = "prov.user") -> KnownQuantity:
    return KnownQuantity(name=name, raw_value=value, raw_unit=unit, normalized_value=value,
                         unit=unit, quantity_kind=kind, provenance_ref=provenance)


def candidate(*, model_id: str = "model.synthetic.cleaning", position_id: str = "position.synthetic.cleaning",
              rate: str = "1000", status: str = "MATCHING_SAFE", source_refs: list[str] | None = None) -> CatalogCandidateInput:
    return CatalogCandidateInput.model_validate({
        "model_id": model_id, "position_id": position_id, "name": "Cleaning fixture",
        "system_family": "SYNTHETIC_TEST_ONLY", "identity_status": "MATCHED",
        "profile_id": "CLEANING_AREA_V1", "readiness_v2_status": "CALCULATION_READY",
        "facts": [{"field_path": "capacity.cleaning_rate_m2_h", "value": rate, "unit": "m2/h",
                   "evidence_status": status, "source_refs": source_refs or ["fixture:cleaning-rate"]}],
    })


def scenario(*, area: str = "51000", frequency: str | None = "1", selected: int | None = None) -> list[ScenarioValue]:
    raw = [
        ("process.cleaning_area_m2", area, "m2"),
        ("process.shift_hours", "8", "h"),
        ("process.shifts_per_day", "3", "shift"),
    ]
    if frequency is not None:
        raw.append(("process.cleaning_frequency_per_day", frequency, "1/day"))
    if selected is not None:
        raw.append(("run.selected_fleet_units", str(selected), "robot"))
    return [ScenarioValue(input_path=path, value=value, unit=unit, source_ref=f"fixture:{path}")
            for path, value, unit in raw]


def process(*, demand: str = "51000", active: bool = True) -> NormalizedProcess:
    return NormalizedProcess.model_validate({
        "process_id": "process.airport.terminal-cleaning", "input_revision": "revision.airport.cleaning.v1",
        "object_kind": "AIRPORT", "process_code": "airport_terminal_cleaning", "scope": "CLEANING_AREA",
        "active": active, "quantity_kind": "SQUARE_METER",
        "demand": q("demand_per_day", demand, "m2/day", "FLOW").model_dump(),
        "schedule": {
            "shifts_per_day": q("shifts_per_day", "3", "shift", "COUNT").model_dump(),
            "shift_hours": q("shift_hours", "8", "h", "TIME").model_dump(),
            "days_per_year": q("days_per_year", "365", "day", "TIME").model_dump(),
        },
    })


def versions(candidate_value: CatalogCandidateInput) -> VersionBindings:
    manifest = json.loads((ROOT / "data/calculation/registry-v1.manifest.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "data/calculation/formula-executability-profiles-v3.json").read_text(encoding="utf-8"))
    synthetic = candidate_value.model_id.startswith("model.synthetic.")
    if synthetic:
        catalog_version = "synthetic-cleaning-catalog-v1"
        catalog_digest = semantic_digest(candidate_value)
    else:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        catalog_version = audit["catalog_code"]
        catalog_digest = f"sha256:{audit['inputs_sha256']['catalog_products']}"
    return VersionBindings(
        catalog_version_id=catalog_version, catalog_content_digest=catalog_digest,
        capacity_projection_version="formula-executability-profiles-v3",
        capacity_projection_digest=semantic_digest(profiles),
        registry_version="hackathon-calculation-parameter-registry-v1",
        registry_digest=manifest["registry_semantic_digest"],
        process_catalog_version="calculation-process-catalog-v1",
        formula_bundle_version="calculation-formulas-v1",
        constraint_rules_version="calculation-constraint-rules-v2",
        commercial_policy_version="hackathon-commercial-policy-v1",
        precision_policy_version="decimal-context-28-half-even-v1",
        calculation_policy_version="hackathon-calculation-policy-v1",
    )


def request(*, area: str = "51000", total_area: str | None = "85000", share: str = "0.6",
            frequency: str | None = "1", selected: int | None = None, rate: str = "1000",
            unsafe: bool = False, model_id: str = "model.synthetic.cleaning",
            position_id: str = "position.synthetic.cleaning", source_refs: list[str] | None = None) -> CleaningCapacityRequestV1:
    candidate_value = candidate(model_id=model_id, position_id=position_id, rate=rate,
                                status="CONFLICT" if unsafe else "MATCHING_SAFE", source_refs=source_refs)
    run = evaluate_run_executability(candidate_value, scenario(area=area, frequency=frequency, selected=selected),
                                     "ELIGIBLE", registry_payload())
    computed_daily = Decimal(0) if frequency is None else Decimal(area) * Decimal(frequency)
    daily = str(computed_daily) if computed_daily > 0 else "1"
    proc = process(demand=daily)
    provenance = [
        {"provenance_id": "prov.user", "kind": "USER", "confirmation_revision": proc.input_revision},
        VendorFactProvenance(provenance_id="prov.fact.cleaning-rate", fact_id="fact.cleaning-rate",
            model_id=model_id, position_id=position_id, scope="CLEANING_AREA",
            evidence_ids=["evidence.cleaning-rate"], evidence_status="VERIFIED_OFFICIAL", permitted_for_matching=True),
    ]
    area_source = ({"mode": "DIRECT", "area": q("cleaning_area", area, "m2", "AREA")}
                   if total_area is None else
                   {"mode": "SHARE_OF_TOTAL", "total_area": q("total_area", total_area, "m2", "AREA"),
                    "cleaning_share": q("cleaning_area_share", share, "1", "FRACTION")})
    return CleaningCapacityRequestV1(
        run_id=f"run.cleaning.{model_id}.{selected if selected is not None else 'recommended'}",
        acquisition="PURCHASE", uncertainty="BASE", process=proc, model_id=model_id, position_id=position_id,
        area_source=area_source,
        frequency=None if frequency is None else q("cleaning_frequency", frequency, "1/day", "RATE"),
        selected_fleet=None if selected is None else q("fleet_selected", str(selected), "robot", "COUNT"),
        executability=run,
        constraints=ConstraintReportV2(input_revision=proc.input_revision, process_id=proc.process_id,
            model_id=model_id, position_id=position_id, eligibility="ELIGIBLE", checks=[],
            blocker_codes=[], validation_codes=[], warning_codes=[]),
        versions=versions(candidate_value), provenance=provenance,
        fact_provenance={"fact.cleaning-rate": "prov.fact.cleaning-rate"},
    )


def test_golden_airport_area_derivation_and_byte_stable_replay():
    result = calculate_cleaning_capacity(request())
    assert result.capacity.status == "COMPLETE"
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = {
        "derived_area_m2": next(x for x in result.trace.intermediates if x.name == "cleaning_area").value.value,
        "required_area_m2_day": next(x for x in result.trace.intermediates if x.name == "cleaning_area_per_day").value.value,
        "nominal_m2_day": next(x for x in result.trace.intermediates if x.name == "nominal_capacity").value.value,
        "effective_m2_day": next(x for x in result.trace.intermediates if x.name == "effective_capacity").value.value,
        "recommended_fleet": result.capacity.value.recommended_fleet,
        "formula_ids": [node.formula_id for node in result.trace.formula_nodes],
        "input_units": sorted({str(item.unit) for item in result.trace.inputs}),
    }
    assert actual == expected
    assert canonical_json_bytes(result) == canonical_json_bytes(calculate_cleaning_capacity(request()))


def test_preliminary_cleaning_retains_unverified_constraints_and_trace_warning():
    candidate_value = candidate()
    run = evaluate_run_executability(
        candidate_value, scenario(), "NEEDS_VALIDATION", registry_payload(),
        allow_preliminary=True,
    )
    value = request().model_copy(deep=True)
    value.executability = run
    value.constraints = value.constraints.model_copy(update={
        "eligibility": "NEEDS_VALIDATION", "validation_codes": ["passport-availability"],
    })
    result = calculate_cleaning_capacity(value)
    assert result.capacity.status == "WITH_ASSUMPTIONS"
    assert result.capacity.value.recommended_fleet == 4
    assert result.trace.assumptions[0].assumption_id == "preliminary-applicability-unverified"
    assert result.trace.issues[0].code == "demo-applicability-unverified"


@pytest.mark.parametrize("selected,coverage,overloaded", [
    (3, "0.9882352941176470588235294118", True), (4, "1", False), (5, "1", False)])
def test_manual_cleaning_fleet_uses_actual_daily_capacity(selected, coverage, overloaded):
    value = calculate_cleaning_capacity(request(selected=selected)).capacity.value
    assert value.coverage.value == coverage
    assert value.overloaded is overloaded


@pytest.mark.parametrize("area", ["0", "-1"])
def test_zero_or_negative_area_is_blocked(area):
    result = calculate_cleaning_capacity(request(area=area, total_area=None))
    assert result.capacity.status == "BLOCKED"


@pytest.mark.parametrize("frequency", [None, "0"])
def test_missing_or_zero_frequency_is_blocked(frequency):
    result = calculate_cleaning_capacity(request(frequency=frequency))
    assert result.capacity.status == "BLOCKED"


def test_h24_exact_ceil_boundaries_and_inactive_zero_policy():
    required, nominal, effective, fleet = cleaning_capacity(
        area_m2=Decimal("51000"), frequency_per_day=Decimal(1), rate_m2_hour=Decimal(1000),
        operating_hours_per_day=Decimal(24), availability=Decimal("0.70"))
    assert (required, nominal, effective, fleet) == (Decimal(51000), Decimal(24000), Decimal(16800), 4)
    assert cleaning_capacity(area_m2=Decimal(16800), frequency_per_day=Decimal(1),
        rate_m2_hour=Decimal(1000), operating_hours_per_day=Decimal(24), availability=Decimal("0.70"))[-1] == 1
    inactive_request = request()
    inactive_request.process.active = False
    assert calculate_cleaning_capacity(inactive_request).capacity.status == "NOT_APPLICABLE"
    zero = calculate_cleaning_capacity(request(selected=0)).capacity.value
    assert zero.effective_capacity.value == zero.coverage.value == "0"
    assert zero.utilization is None and zero.overloaded is True


def test_direct_area_and_f05_monotonicity():
    direct = calculate_cleaning_capacity(request(total_area=None))
    assert direct.capacity.value.recommended_fleet == 4
    fleet = lambda area, rate, availability: cleaning_capacity(
        area_m2=Decimal(area), frequency_per_day=Decimal(1), rate_m2_hour=Decimal(rate),
        operating_hours_per_day=Decimal(24), availability=Decimal(availability))[-1]
    assert fleet("50000", "1000", ".7") <= fleet("51000", "1000", ".7")
    assert fleet("51000", "600", ".7") >= fleet("51000", "1000", ".7")
    assert fleet("51000", "1000", ".55") >= fleet("51000", "1000", ".8")


def test_no_transport_peak_batch_payload_or_finance_semantics():
    result = calculate_cleaning_capacity(request())
    names = {str(item.name) for item in result.trace.inputs}
    assert not names.intersection({"peak_factor", "reserve_share", "payload", "units_per_trip", "item_mass"})
    assert all("pallet" not in str(item.unit) for item in result.trace.inputs)
    payload = result.model_dump(mode="json")
    assert "financial" not in payload and "salary" not in repr(payload).lower()


def test_unsafe_cleaning_rate_is_rejected_before_formula_execution():
    result = calculate_cleaning_capacity(request(unsafe=True))
    assert result.capacity.status == "BLOCKED"
    assert result.trace.formula_nodes == []


def test_all_six_ready_cleaning_position_dtos_execute_without_cost_or_autonomy():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    ready = [item for item in audit["positions"]
             if item["result"]["profile_id"] == "CLEANING_AREA_V1"
             and item["result"]["catalog_status"] == "CATALOG_EXECUTABLE"]
    expected = {
        "catalog-v4-row-0021": 4, "catalog-v4-row-0022": 6, "catalog-v4-row-0023": 2,
        "catalog-v4-row-0024": 5, "catalog-v4-row-0025": 4, "catalog-v4-row-0106": 2,
    }
    assert len(ready) == 6
    actual = {}
    for item in ready:
        fact = item["result"]["available_facts"][0]
        response = calculate_cleaning_capacity(request(
            model_id=item["model_id"], position_id=item["id"], rate=str(fact["value"]),
            source_refs=fact["source_refs"]))
        assert response.capacity.status == "COMPLETE"
        actual[item["id"]] = response.capacity.value.recommended_fleet
    assert actual == expected


def test_strict_area_source_and_trace_provenance():
    with pytest.raises(ValidationError):
        request(share="1.01")
    trace = calculate_cleaning_capacity(request()).trace
    provenance_ids = {item.provenance_id for item in trace.provenance}
    assert all(item.provenance_ref in provenance_ids and item.unit and item.raw_unit for item in trace.inputs)
