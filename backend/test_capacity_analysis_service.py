from __future__ import annotations

import inspect
import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from calculation.constraints import ConstraintReportV2
from calculation.service import analyze_capacity, capacity_version_bindings
from calculation_contracts import (
    CapacityAnalysisRequest,
    KnownQuantity,
    canonical_json_bytes,
)
from catalog_repository import (
    CapacityRuntimeDTO,
    CatalogApplicabilityDTO,
    CatalogFactDTO,
    CatalogModelDTO,
    CatalogPositionDTO,
    CatalogSnapshotDTO,
    CatalogVersionDTO,
    ProcurementOptionDTO,
)
from persistence_models import AnalysisRun

ROOT = Path(__file__).resolve().parents[1]


def q(name: str, value: str, unit: str, kind: str) -> KnownQuantity:
    return KnownQuantity(name=name, raw_value=value, raw_unit=unit, normalized_value=value,
                         unit=unit, quantity_kind=kind, provenance_ref="prov.user")


def snapshot() -> CatalogSnapshotDTO:
    facts = (
        CatalogFactDTO("max_speed", "GLOBAL", 1, "m/s", "VERIFIED_OFFICIAL", "evidence.speed"),
        CatalogFactDTO("payload", "GLOBAL", 1200, "kg", "VERIFIED_OFFICIAL", "evidence.payload"),
    )
    capacity = CapacityRuntimeDTO(
        calculation_readiness_status="CALCULATION_READY", calculation_ready=True,
        calculation_requires_assumptions=False, calculation_profile="TRANSPORT_CYCLE_V1",
        calculation_blockers=(), runtime_catalog_version="synthetic-capacity-v1",
        calculation_model_fields=("specs.max_speed", "specs.payload"), vendor_facts=facts,
        provenance={"contract_version": "runtime-calculation-readiness-contract-v2"},
        deployment_readiness_status="DEPLOYMENT_REVIEW_REQUIRED",
    )
    model = CatalogModelDTO(
        id="model.synthetic.transport", source_namespace="test", source_record_key="model.synthetic.transport",
        organizer_id=None, manufacturer="Synthetic", name="Synthetic safe transport",
        system_family="BRS", type_code="Transport", subtype_code=None, maturity_status=None,
        trl=None, description=None, attributes={}, facts=facts, applicability=(), procurement_options=(),
        runtime_robot=None, runtime_blockers=("economics",), capacity_runtime=capacity,
    )
    position = CatalogPositionDTO(
        id="position.synthetic.transport", source_record_key="position.synthetic.transport", source_row_number=1,
        model=model, applicability=CatalogApplicabilityDTO("warehouse", "transport", "RU", None),
        procurement_option=ProcurementOptionDTO("PURCHASE", None, None, "UNKNOWN", "UNKNOWN", (), (), None),
        media=None, runtime_robot=None, runtime_blockers=("economics",),
    )
    return CatalogSnapshotDTO(
        version=CatalogVersionDTO(str(uuid.UUID("00000000-0000-0000-0000-000000000011")),
                                  "persistence-test-capacity-v1", "PUBLISHED", "4"),
        models=(model,), positions=(position,),
    )


def request(*, code: str = "warehouse_receiving_shipping") -> CapacityAnalysisRequest:
    process = {
        "process_id": f"process.{code.replace('_', '.')}", "input_revision": "revision.c11.v1",
        "object_kind": "WAREHOUSE", "process_code": code,
        "scope": "TRANSPORT_CYCLE" if code == "warehouse_receiving_shipping" else "REFERENCE_ONLY",
        "active": True, "quantity_kind": "PALLET" if code == "warehouse_receiving_shipping" else "ITEM",
        "demand": q("demand_per_day", "1000", "pallet/day" if code == "warehouse_receiving_shipping" else "item/day", "FLOW").model_dump(),
        "schedule": {
            "shifts_per_day": q("shifts_per_day", "2", "shift", "COUNT").model_dump(),
            "shift_hours": q("shift_hours", "10", "h", "TIME").model_dump(),
            "days_per_year": q("days_per_year", "365", "day", "TIME").model_dump(),
        },
        "role_refs": [],
    }
    if code == "warehouse_receiving_shipping":
        process.update({
            "route_distance": q("one_way_distance", "100", "m", "DISTANCE").model_dump(),
            "exchange": {"mode": "TOTAL", "total_time": q("exchange_total_time", "100", "s", "TIME").model_dump()},
            "explicit_batch": q("units_per_trip", "1", "unit/trip", "RATE").model_dump(),
        })
    return CapacityAnalysisRequest.model_validate({
        "project_id": str(uuid.UUID("00000000-0000-0000-0000-000000000021")),
        "input_revision": "revision.c11.v1", "process": process, "model_id": "model.synthetic.transport",
        "position_id": "position.synthetic.transport", "acquisition": "PURCHASE", "uncertainty": "BASE",
        "provenance": [{"provenance_id": "prov.user", "kind": "USER", "confirmation_revision": "revision.c11.v1"}],
    })


def eligible_constraints(value: CapacityAnalysisRequest, position: CatalogPositionDTO) -> ConstraintReportV2:
    return ConstraintReportV2(
        input_revision=value.input_revision, process_id=value.process.process_id,
        model_id=position.model.id, position_id=position.id, eligibility="ELIGIBLE",
        checks=[], blocker_codes=[], validation_codes=[], warning_codes=[],
    )


def test_transport_service_golden_is_replayable_without_economics():
    result = analyze_capacity(request(), snapshot(), "run.c11.golden", constraint_provider=eligible_constraints)
    assert result.response.capacity.status == "WITH_ASSUMPTIONS"
    assert result.response.capacity.value.recommended_fleet > 0
    assert result.executability.status == "EXECUTABLE"
    payload = result.response.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True)
    assert all(f'"{key}"' not in serialized for key in ("financial", "economics", "scenario_spec", "price"))
    assert all(token not in inspect.getsource(analyze_capacity) for token in ("procurement_option", "runtime_robot"))
    assert canonical_json_bytes(result.response) == canonical_json_bytes(
        analyze_capacity(request(), snapshot(), "run.c11.golden", constraint_provider=eligible_constraints).response
    )
    golden = json.loads((ROOT / "contracts/fixtures/capacity-analysis-v2.synthetic.golden.json").read_text(encoding="utf-8"))
    actual = {
        "status": result.response.capacity.status,
        "recommended_fleet": result.response.capacity.value.recommended_fleet,
        "selected_fleet": result.response.capacity.value.selected_fleet,
        "formula_ids": [item.formula_id for item in result.response.trace.formula_nodes],
        "catalog_version": result.response.trace.versions.catalog_version_id,
    }
    assert actual == golden


def test_default_constraints_fail_closed_but_preserve_same_revision():
    result = analyze_capacity(request(), snapshot(), "run.c11.blocked")
    assert result.constraints.eligibility == "NEEDS_VALIDATION"
    assert result.executability.status == "NEEDS_VALIDATION"
    assert result.response.capacity.status == "BLOCKED"
    assert result.constraints.input_revision == result.response.input_revision == "revision.c11.v1"


def test_confirmed_mass_hard_fail_blocks_new_capacity_run():
    raw = request().model_dump(mode="json")
    raw["process"]["item_mass"] = q("item_mass", "1300", "kg/unit", "RATE").model_dump()
    result = analyze_capacity(CapacityAnalysisRequest.model_validate(raw), snapshot(), "run.c11.overload")
    assert result.constraints.eligibility == "BLOCKED"
    assert "payload" in result.constraints.blocker_codes
    assert next(c for c in result.constraints.checks if c.check_id == "payload").status == "FAIL"
    assert result.response.capacity.status == "BLOCKED"


def test_confirmed_mass_within_safe_payload_is_not_hard_fail():
    raw = request().model_dump(mode="json")
    raw["process"]["item_mass"] = q("item_mass", "800", "kg/unit", "RATE").model_dump()
    result = analyze_capacity(CapacityAnalysisRequest.model_validate(raw), snapshot(), "run.c11.safe-payload")
    assert next(c for c in result.constraints.checks if c.check_id == "payload").status == "PASS"
    assert "payload" not in result.constraints.blocker_codes


def test_research_maturity_cannot_enter_new_capacity_run_even_if_flagged_ready():
    original = snapshot()
    research_model = replace(original.models[0], maturity_status="RND")
    research = replace(original, models=(research_model,),
                       positions=(replace(original.positions[0], model=research_model),))
    with pytest.raises(ValueError, match="research position"):
        analyze_capacity(request(), research, "run.c11.research")


def test_acknowledged_demo_calculates_without_claiming_c05_eligibility():
    raw = request().model_dump(mode="json")
    raw.update(execution_mode="PRELIMINARY_DEMO", demo_assumptions_confirmed=True)
    demo = CapacityAnalysisRequest.model_validate(raw)
    first = analyze_capacity(demo, snapshot(), "run.c11.demo")
    second = analyze_capacity(demo, snapshot(), "run.c11.demo")
    assert first.constraints.eligibility == "NEEDS_VALIDATION"
    assert "passport-availability" in first.constraints.validation_codes
    assert first.executability.status == "PRELIMINARY_EXECUTABLE"
    assert first.response.capacity.status == "WITH_ASSUMPTIONS"
    assert first.response.capacity.value.recommended_fleet > 0
    assert any(x.code == "demo-applicability-unverified" for x in first.response.capacity.warnings)
    assert canonical_json_bytes(first.response) == canonical_json_bytes(second.response)


def test_unacknowledged_demo_request_is_rejected():
    raw = request().model_dump(mode="json")
    raw["execution_mode"] = "PRELIMINARY_DEMO"
    with pytest.raises(ValueError, match="acknowledgement"):
        CapacityAnalysisRequest.model_validate(raw)


def test_demo_never_overrides_known_critical_failure_or_missing_dependency():
    raw = request().model_dump(mode="json")
    raw.update(execution_mode="PRELIMINARY_DEMO", demo_assumptions_confirmed=True)
    demo = CapacityAnalysisRequest.model_validate(raw)

    def failed_constraints(value, position):
        report = eligible_constraints(value, position)
        return report.model_copy(update={"eligibility": "BLOCKED", "blocker_codes": ["payload"]})

    failed = analyze_capacity(demo, snapshot(), "run.c11.demo-failed", constraint_provider=failed_constraints)
    assert failed.executability.status == "BLOCKED"
    assert failed.response.capacity.status == "BLOCKED"

    raw["process"]["exchange"] = None
    missing = analyze_capacity(CapacityAnalysisRequest.model_validate(raw), snapshot(), "run.c11.demo-missing")
    assert missing.executability.status == "NEEDS_VALIDATION"
    assert missing.response.capacity.status == "BLOCKED"


def test_reference_only_and_identity_mismatch_are_explicit():
    result = analyze_capacity(request(code="warehouse_inventory"), snapshot(), "run.c11.reference")
    assert result.route.disposition == "REFERENCE_ONLY"
    assert result.response.capacity.status == "BLOCKED"
    raw = request().model_dump(mode="json")
    raw["position_id"] = "position.missing"
    with pytest.raises(ValueError, match="absent"):
        analyze_capacity(CapacityAnalysisRequest.model_validate(raw), snapshot(), "run.c11.missing")
    unpublished = snapshot()
    unpublished = CatalogSnapshotDTO(
        version=CatalogVersionDTO(unpublished.version.id, unpublished.version.code, "DRAFT", "4"),
        models=unpublished.models, positions=unpublished.positions,
    )
    with pytest.raises(ValueError, match="published"):
        analyze_capacity(request(), unpublished, "run.c11.unpublished")


def test_version_bindings_and_run_kind_invariants_are_explicit():
    first = capacity_version_bindings(snapshot())
    second = capacity_version_bindings(snapshot())
    assert first == second
    assert first.registry_version == "hackathon-calculation-parameter-registry-v1"
    constraints = {item.name: str(item.sqltext) for item in AnalysisRun.__table__.constraints if item.name}
    assert "CAPACITY_ANALYSIS" in constraints["ck_analysis_runs_kind"]
    assert "trace_snapshot IS NOT NULL" in constraints["ck_analysis_runs_state_payload"]
    assert "run_kind = 'FULL_ANALYSIS' AND economics_version IS NOT NULL" in constraints["ck_analysis_runs_versions_nonempty"]
    assert "run_kind = 'CAPACITY_ANALYSIS' AND economics_version IS NULL" in constraints["ck_analysis_runs_versions_nonempty"]


def test_openapi_publishes_v2_contract_and_keeps_legacy_endpoint():
    import main
    schema = main.app.openapi()
    operation = schema["paths"]["/api/v2/capacity-analyses"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert {item["$ref"].rsplit("/", 1)[-1] for item in request_schema["anyOf"]} == {
        "CapacityAnalysisRequest", "CapacityAnalysisRequestV3", "CapacityAnalysisRequestV4",
    }
    assert operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith("CapacityAnalysisResponse")
    assert operation["responses"]["503"]["content"]["application/json"]["schema"]["$ref"].endswith("CapacityAnalysisErrorResponse")
    assert "/api/v2/capacity-analyses/{run_id}" in schema["paths"]
    assert "/api/calculate" in schema["paths"]


def test_capacity_errors_use_the_declared_machine_readable_contract():
    from calculation_contracts import CapacityAnalysisErrorResponse
    from persistence_api import _capacity_error
    response = _capacity_error(503, "CAPACITY_SOURCE_UNAVAILABLE", "capacity source unavailable")
    parsed = CapacityAnalysisErrorResponse.model_validate(json.loads(response.body))
    assert parsed.error_code == "CAPACITY_SOURCE_UNAVAILABLE"
    assert parsed.issues[0].reason == "MISSING_SAFE_FACT"
