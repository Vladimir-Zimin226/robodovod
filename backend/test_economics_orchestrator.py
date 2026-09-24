from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest
from calculation.scheduling import SimulationErrorV1, SimulationReportV1, SimulationRequestV1, run_simulation
from calculation.service import analyze_capacity
from calculation_contracts import (
    CapacityAnalysisRequest,
    KnownQuantity,
    semantic_digest,
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
from economics_orchestrator import EconomicsExecutionContextV1, execute_economics_v2


def _q(name: str, value: str, unit: str, kind: str) -> dict:
    return KnownQuantity(
        name=name,
        raw_value=value,
        raw_unit=unit,
        normalized_value=value,
        unit=unit,
        quantity_kind=kind,
        provenance_ref="prov.user",
    ).model_dump(mode="json")


def _snapshot() -> CatalogSnapshotDTO:
    facts = (
        CatalogFactDTO(
            "max_speed", "GLOBAL", 1, "m/s", "VERIFIED_OFFICIAL", "evidence.speed"
        ),
        CatalogFactDTO(
            "payload", "GLOBAL", 1500, "kg", "VERIFIED_OFFICIAL", "evidence.payload"
        ),
    )
    capacity = CapacityRuntimeDTO(
        calculation_readiness_status="CALCULATION_READY_WITH_ASSUMPTIONS",
        calculation_ready=True,
        calculation_requires_assumptions=True,
        calculation_profile="TRANSPORT_CYCLE_V1",
        calculation_blockers=(),
        runtime_catalog_version="orchestrator-test-v1",
        calculation_model_fields=("specs.max_speed", "specs.payload"),
        vendor_facts=facts,
        scenario_assumptions=(),
        provenance={"contract_version": "runtime-calculation-readiness-contract-v2"},
        deployment_readiness_status="DEPLOYMENT_REVIEW_REQUIRED",
    )
    option = ProcurementOptionDTO(
        mode="PURCHASE",
        amount=Decimal(3000000),
        currency="UNKNOWN",
        price_status="ORGANIZER_RAW_PRICE_NORMALIZED; CURRENCY_NOT_EXPLICIT_IN_ATTACHED_SOURCE",
        vat_status="ORGANIZER_ASSUMPTION_INCLUDED",
        included_costs=(),
        excluded_costs=(),
        evidence_id=None,
        id="price.organizer.demo",
        raw_price="3 000 000,00",
    )
    model = CatalogModelDTO(
        id="model.demo.mule",
        source_namespace="test",
        source_record_key="model.demo.mule",
        organizer_id="model.demo.mule",
        manufacturer="Demo",
        name="Demo MULE",
        system_family="BRS",
        type_code="Transport",
        subtype_code=None,
        maturity_status=None,
        trl=None,
        description=None,
        attributes={},
        facts=facts,
        applicability=(),
        procurement_options=(option,),
        runtime_robot=None,
        runtime_blockers=("economics",),
        capacity_runtime=capacity,
    )
    position = CatalogPositionDTO(
        id="position.demo.mule",
        source_record_key="position.demo.mule",
        source_row_number=1,
        model=model,
        applicability=CatalogApplicabilityDTO("warehouse", "transport", "RU", None),
        procurement_option=option,
        media=None,
        runtime_robot=None,
        runtime_blockers=("economics",),
    )
    return CatalogSnapshotDTO(
        version=CatalogVersionDTO(
            str(uuid.UUID("00000000-0000-0000-0000-000000000031")),
            "orchestrator-test-v1",
            "PUBLISHED",
            "4",
        ),
        models=(model,),
        positions=(position,),
    )


def _capacity_request() -> CapacityAnalysisRequest:
    process_id = "process.receiving"
    return CapacityAnalysisRequest.model_validate(
        {
            "project_id": str(uuid.UUID("00000000-0000-0000-0000-000000000041")),
            "input_revision": "revision.orchestrator.v1",
            "process": {
                "process_id": process_id,
                "input_revision": "revision.orchestrator.v1",
                "object_kind": "WAREHOUSE",
                "process_code": "warehouse_receiving_shipping",
                "scope": "TRANSPORT_CYCLE",
                "active": True,
                "quantity_kind": "PALLET",
                "demand": _q("demand_per_day", "1000", "pallet/day", "FLOW"),
                "schedule": {
                    "shifts_per_day": _q("shifts_per_day", "2", "shift", "COUNT"),
                    "shift_hours": _q("shift_hours", "10", "h", "TIME"),
                    "days_per_year": _q("days_per_year", "365", "day", "TIME"),
                },
                "route_distance": _q("one_way_distance", "120", "m", "DISTANCE"),
                "exchange": {
                    "mode": "TOTAL",
                    "total_time": _q("exchange_total_time", "90", "s", "TIME"),
                },
                "explicit_batch": _q("units_per_trip", "1", "unit/trip", "RATE"),
                "role_refs": ["role.driver"],
            },
            "role_pool": {
                "pool_id": "pool.warehouse",
                "object_kind": "WAREHOUSE",
                "roles": [
                    {
                        "role_id": "role.driver",
                        "object_scope": "WAREHOUSE",
                        "role_code": "forklift_driver",
                        "headcount": _q("role_headcount", "20", "person", "COUNT"),
                        "monthly_gross_salary": _q(
                            "monthly_gross_salary",
                            "100000",
                            "RUB/person/month",
                            "MONEY",
                        ),
                        "process_ids": [process_id],
                    }
                ],
            },
            "model_id": "model.demo.mule",
            "position_id": "position.demo.mule",
            "acquisition": "PURCHASE",
            "uncertainty": "BASE",
            "execution_mode": "PRELIMINARY_DEMO",
            "demo_assumptions_confirmed": True,
            "provenance": [
                {
                    "provenance_id": "prov.user",
                    "kind": "USER",
                    "confirmation_revision": "revision.orchestrator.v1",
                }
            ],
        }
    )


def _inputs() -> dict:
    return {
        "schema_version": "economics-explicit-inputs-v1",
        "input_revision": "revision.orchestrator.v1",
        "evaluation_date": date(2026, 9, 24).isoformat(),
        "horizon_years": 5,
        "discount_rate": "0.15",
        "primary_role_id": "role.driver",
        "manual_units_per_shift": "100",
        "role_salaries_confirmed_as_monthly_gross": True,
        "control_headcount": 0,
        "control_monthly_gross": "100000",
        "technician_headcount": 0,
        "technician_monthly_gross": "120000",
        "organizer_price_currency_rub_confirmed": True,
        "implementation_cost_total_gross": "500000",
        "annual_service_per_robot_gross": "120000",
        "warranty_years": 1,
        "average_power_w": "1000",
        "initial_battery_in_robot_price_confirmed": True,
        "battery_replacements_in_service_confirmed": True,
        "shared_site_capital_gross": "0",
        "shared_annual_cost_gross": "0",
        "raas_monthly_per_robot_gross": "180000",
        "raas_contract_months": 60,
        "raas_infrastructure_owner": "VENDOR",
        "raas_vendor_scope_confirmed": True,
        "start_seconds_from_midnight": 0,
        "timezone": "Europe/Moscow",
    }


def test_normalized_c01_conversion_refs_do_not_dangle_in_c11_trace():
    """The browser sends C01 quantities with conversion IDs, not C11 provenance IDs."""

    raw = _capacity_request().model_dump(mode="json")
    process = raw["process"]
    process["demand"]["provenance_ref"] = "conversion.0001"
    process["schedule"]["shifts_per_day"]["provenance_ref"] = "conversion.0002"
    process["schedule"]["shift_hours"]["provenance_ref"] = "conversion.0003"
    process["route_distance"]["provenance_ref"] = "conversion.0005"
    process["explicit_batch"]["provenance_ref"] = "conversion.0006"
    request = CapacityAnalysisRequest.model_validate(raw)

    execution = analyze_capacity(request, _snapshot(), "run.c01-to-c11.demo")
    assert execution.response.capacity.status == "WITH_ASSUMPTIONS"
    trace = execution.response.trace
    known = {item.provenance_id for item in trace.provenance}
    assert all(item.provenance_ref in known for item in trace.inputs)
    assert any(item.name == "units_per_trip" for item in trace.inputs)


def test_unregistered_non_c01_input_provenance_fails_closed():
    raw = _capacity_request().model_dump(mode="json")
    raw["process"]["explicit_batch"]["provenance_ref"] = "prov.unregistered"
    request = CapacityAnalysisRequest.model_validate(raw)

    with pytest.raises(ValueError, match="C11 input provenance is not registered"):
        analyze_capacity(request, _snapshot(), "run.unknown-provenance")


def test_production_orchestrator_uses_capacity_and_catalog_without_fixture_bundle():
    snapshot = _snapshot()
    capacity_request = _capacity_request()
    capacity = analyze_capacity(capacity_request, snapshot, "run.capacity.demo")
    assert capacity.response.capacity.status == "WITH_ASSUMPTIONS"
    context = EconomicsExecutionContextV1(
        run_id="run.economics.demo",
        project_id=capacity_request.project_id,
        tenant_id="tenant.demo",
        capacity_request=capacity_request,
        capacity_response=capacity.response,
        constraint_report=capacity.constraints.model_dump(mode="json"),
        executability=capacity.executability.model_dump(mode="json"),
    )
    first = execute_economics_v2(_inputs(), snapshot, context)
    second = execute_economics_v2(_inputs(), snapshot, context)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    bundle = first.result_snapshot
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "contracts/commercial-scenarios-bundle-v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(bundle)
    assert bundle["schema_version"] == "commercial-scenarios-bundle-v2"
    assert len(bundle["scenarios"]) == 6
    assert {
        item["procurement"]["procurement_status"] for item in bundle["scenarios"]
    } == {"UNVERIFIED"}
    assert all(
        item["recommendation"]["status"] != "RECOMMENDED"
        for item in bundle["scenarios"]
    )
    assert (
        first.scenario_spec_snapshot["finance"]["source_schema_version"]
        == "multiprocess-allocation-result-v1"
    )
    assert len(bundle["sensitivity"]["variants"]) == 6
    assert {item["status"] for item in bundle["sensitivity"]["variants"]} == {
        "COMPLETE"
    }
    assert "fixture" not in str(first.diagnostics).lower()
    projection = {
        "schema_version": "production-economics-orchestrator-acceptance-v1",
        "execution_digest": semantic_digest(first),
        "result_digest": semantic_digest(bundle),
        "scenario_spec_digest": semantic_digest(first.scenario_spec_snapshot),
        "application_version": first.application_version,
        "rules_version": first.rules_version,
        "scenario_keys": [
            f"{item['acquisition']}:{item['uncertainty']}"
            for item in bundle["scenarios"]
        ],
        "procurement_statuses": [
            item["procurement"]["procurement_status"] for item in bundle["scenarios"]
        ],
        "recommendation_statuses": [
            item["recommendation"]["status"] for item in bundle["scenarios"]
        ],
        "sensitivity": [
            {
                "variant_id": item["variant_id"],
                "status": item["status"],
                "delta_value": item["npv_project"]["delta_value"],
            }
            for item in bundle["sensitivity"]["variants"]
        ],
        "limitations": bundle["limitations"],
    }
    assert projection == json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "contracts/fixtures/production-economics-orchestrator-v1.golden.json"
        ).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("daily_demand,shift_hours", [("1000", "10"), ("2000", "11")])
def test_saved_economics_scenario_can_run_c23_without_invented_sla_or_resources(daily_demand, shift_hours):
    snapshot = _snapshot()
    raw = _capacity_request().model_dump(mode="json")
    raw["process"]["demand"]["raw_value"] = daily_demand
    raw["process"]["demand"]["normalized_value"] = daily_demand
    raw["process"]["schedule"]["shift_hours"]["raw_value"] = shift_hours
    raw["process"]["schedule"]["shift_hours"]["normalized_value"] = shift_hours
    request = CapacityAnalysisRequest.model_validate(raw)
    capacity = analyze_capacity(request, snapshot, "run.capacity.visualization")
    context = EconomicsExecutionContextV1(
        run_id="run.economics.visualization",
        project_id=request.project_id,
        tenant_id="tenant.demo",
        capacity_request=request,
        capacity_response=capacity.response,
        constraint_report=capacity.constraints.model_dump(mode="json"),
        executability=capacity.executability.model_dump(mode="json"),
    )
    execution = execute_economics_v2(_inputs(), snapshot, context)
    simulation_request = SimulationRequestV1.model_validate({
        "schema_version": "simulation-request-v1",
        "request_id": "simulation.run.economics.visualization",
        "tenant_id": execution.result_snapshot["tenant_id"],
        "project_id": execution.result_snapshot["project_id"],
        "scenario_spec": execution.scenario_spec_snapshot,
        "mode": "DAILY",
        "peak_factor": None,
        "sla": None,
        "resources": [],
        "limits": {
            "max_jobs_per_day": 10000,
            "max_fleet": 100,
            "max_runtime_seconds": 60,
            "progress_event_batch": 1000,
        },
    })
    report = run_simulation(simulation_request)
    assert isinstance(report, SimulationReportV1), (
        simulation_request.scenario_spec.tasks[0].demand.unit,
        simulation_request.scenario_spec.tasks[0].batch.units_per_cycle.unit,
        simulation_request.scenario_spec.fleet[0].nominal_capacity.unit,
    )
    assert report.scenario_revision_id == execution.scenario_spec_snapshot["revision_id"]
    assert report.sla.verdict == "NOT_EVALUATED"
    assert report.engineering_claim == "PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION"

    mismatched = simulation_request.model_dump(mode="json")
    spec = mismatched["scenario_spec"]
    spec["profile"]["quantity_kind"] = "BOX"
    spec["revision_id"] = "calc_" + semantic_digest(
        {key: value for key, value in spec.items() if key != "revision_id"}
    ).removeprefix("sha256:")[:16]
    invalid = run_simulation(SimulationRequestV1.model_validate(mismatched))
    assert isinstance(invalid, SimulationErrorV1)
    assert invalid.code == "INVALID_SCENARIO"
