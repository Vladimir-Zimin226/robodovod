"""C11 orchestration over one immutable catalog and policy snapshot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable

from catalog_repository import CatalogPositionDTO, CatalogSnapshotDTO
from catalog_selection import numeric_fact, SAFE_FACT_STATUSES
from calculation.capacity.cleaning import DirectCleaningAreaV1, CleaningCapacityRequestV1, calculate_cleaning_capacity
from calculation.capacity.palletizing import PalletizingCapacityRequestV1, calculate_palletizing_capacity
from calculation.capacity.trace import finalize_trace
from calculation.capacity.transport import BatchLimitsV1, TransportCapacityRequestV1, calculate_transport_capacity
from calculation.constraints import (
    CandidateConstraintFacts,
    ConstraintEvaluationRequest,
    ConstraintReportV2,
    ObjectConstraintContext,
    evaluate_constraints,
)
from calculation.executability import (
    RunExecutabilityResult,
    ScenarioValue,
    candidate_from_repository,
    evaluate_run_executability,
    registry_payload,
)
from calculation.labour import LabourAnalysisRequestV1, LabourResultV1, calculate_role_labour
from calculation.economics.allocation import (
    MultiprocessAllocationRequestV1,
    MultiprocessAllocationResultV1,
    calculate_multiprocess_allocation,
)
from calculation.economics.cashflow import FinancialAnalysisRequestV1, FinancialResultV1, calculate_financial_result
from calculation.economics.purchase import PurchaseCostLedgerV1, PurchaseLedgerRequestV1, calculate_purchase_ledger
from calculation.economics.raas import RaasAnalysisRequestV1, RaasFinancialResultV1, calculate_raas_financials
from calculation.economics.sensitivity import SensitivityRequestV1, SensitivityResultV1, calculate_sensitivity
from calculation.process_profiles.router import ProcessRouteDecisionV1, route_process
from calculation.ranking import RankingRequestV2, RankingResultV2, calculate_ranking
from calculation_contracts import (
    AssumptionProvenance,
    CalculationTrace,
    CapacityAnalysisRequest,
    CapacityAnalysisResponse,
    CapacityResult,
    ContractIssue,
    KnownQuantity,
    Provenance,
    ReplayBinding,
    TraceEnvelope,
    TraceResult,
    VersionBindings,
    semantic_digest,
)

ROOT = Path(__file__).resolve().parents[2]
ENGINE_VERSION = "capacity-analysis-service-v2"
ZERO_DIGEST = "sha256:" + "0" * 64
ConstraintProvider = Callable[[CapacityAnalysisRequest, CatalogPositionDTO], ConstraintReportV2]


@dataclass(frozen=True)
class CapacityExecutionSnapshotV2:
    response: CapacityAnalysisResponse
    route: ProcessRouteDecisionV1
    constraints: ConstraintReportV2
    executability: RunExecutabilityResult


def capacity_version_bindings(snapshot: CatalogSnapshotDTO) -> VersionBindings:
    manifest = json.loads((ROOT / "data/calculation/registry-v1.manifest.json").read_text(encoding="utf-8"))
    process_coverage = json.loads((ROOT / "data/review/process-profile-coverage-v1.json").read_text(encoding="utf-8"))
    projection = [
        {
            "position_id": item.id,
            "model_id": item.model.id,
            "capacity_runtime": {
                "status": item.model.capacity_runtime.calculation_readiness_status,
                "profile": item.model.capacity_runtime.calculation_profile,
                "fields": list(item.model.capacity_runtime.calculation_model_fields),
                "facts": [
                    {
                        "code": fact.code,
                        "scope_code": fact.scope_code,
                        "value": str(fact.value),
                        "unit": fact.canonical_unit,
                        "resolution_status": fact.resolution_status,
                        "evidence_id": fact.evidence_id,
                    }
                    for fact in item.model.capacity_runtime.vendor_facts
                ],
            },
        }
        for item in snapshot.positions
    ]
    return VersionBindings(
        catalog_version_id=snapshot.version.code,
        catalog_content_digest=semantic_digest({
            "id": snapshot.version.id,
            "code": snapshot.version.code,
            "status": snapshot.version.status,
            "content_sha256": snapshot.version.content_sha256,
            "process_catalog_digest": process_coverage["catalog_digest"],
        }),
        capacity_projection_version="formula-executability-profiles-v3",
        capacity_projection_digest=semantic_digest(projection),
        registry_version="hackathon-calculation-parameter-registry-v1",
        registry_digest=manifest["registry_semantic_digest"],
        process_catalog_version="calculation-process-catalog-v1",
        formula_bundle_version="calculation-formulas-v1",
        constraint_rules_version="calculation-constraint-rules-v2",
        commercial_policy_version="hackathon-commercial-policy-v1",
        precision_policy_version="decimal-context-28-half-even-v1",
        calculation_policy_version="hackathon-calculation-policy-v1",
    )


def _position(request: CapacityAnalysisRequest, snapshot: CatalogSnapshotDTO) -> CatalogPositionDTO:
    if snapshot.version.status != "PUBLISHED":
        raise ValueError("capacity source must be an immutable published snapshot")
    position = next((item for item in snapshot.positions if item.id == request.position_id), None)
    if position is None or position.model.id != request.model_id:
        raise ValueError("model/position is absent from the published capacity snapshot")
    if not position.model.capacity_runtime.calculation_ready:
        raise ValueError("selected capacity source is not calculation-ready")
    if position.model.maturity_status == "RND":
        raise ValueError("research position cannot enter a capacity calculation")
    return position


def conservative_constraints(request: CapacityAnalysisRequest, position: CatalogPositionDTO) -> ConstraintReportV2:
    """Run C05 without inventing passport/environment facts.

    K19/profile identity is safe metadata. Missing physical evidence remains
    UNKNOWN, so production execution fails closed until the relevant gate.
    """
    source = f"catalog-capacity-profile:{position.id}"
    payload, payload_ref = numeric_fact({"facts": [
        {"code": fact.code, "value": fact.value, "unit": fact.canonical_unit,
         "status": fact.resolution_status, "evidence_id": fact.evidence_id}
        for fact in position.model.facts
    ]}, "payload")
    mass = request.process.item_mass
    context = ObjectConstraintContext(
        object_kind=request.process.object_kind,
        max_payload_kg=mass.normalized_value if isinstance(mass, KnownQuantity) else None,
    )
    evidence = {
        "supported_object_kinds": {"evidence_status": "MATCHING_SAFE", "source_ref": source},
        "supported_process_scopes": {"evidence_status": "MATCHING_SAFE", "source_ref": source},
    }
    if payload_ref:
        evidence["payload_kg"] = {"evidence_status": "MATCHING_SAFE", "source_ref": payload_ref}
    capabilities = {
        "supported_object_kinds": [request.process.object_kind],
        "supported_process_scopes": [request.process.scope],
    }
    if (request.process.scope == "DELIVERY_CYCLE" and
            position.model.capacity_runtime.calculation_profile == "TRANSPORT_CYCLE_V1"):
        # A generic physical cycle does not establish clinical suitability.
        for field in capabilities:
            capabilities[field] = None
            evidence.pop(field, None)
            fact = next((f for f in position.model.facts if f.code == field and
                         f.evidence_id and f.resolution_status in SAFE_FACT_STATUSES), None)
            if fact is not None:
                try:
                    CandidateConstraintFacts(model_id=position.model.id, position_id=position.id, **{field: fact.value})
                except ValueError:
                    continue
                capabilities[field] = fact.value
                evidence[field] = {"evidence_status": "MATCHING_SAFE", "source_ref": fact.evidence_id}
    candidate = CandidateConstraintFacts(
        model_id=position.model.id,
        position_id=position.id,
        **capabilities,
        payload_kg=format(payload, "f") if payload is not None else None,
        evidence=evidence,
    )
    return evaluate_constraints(ConstraintEvaluationRequest(
        input_revision=request.input_revision,
        process_id=request.process.process_id,
        process_code=request.process.process_code,
        process_scope=request.process.scope,
        context=context,
        candidate=candidate,
    ))


def _scenario_values(request: CapacityAnalysisRequest) -> list[ScenarioValue]:
    process = request.process
    values: list[ScenarioValue] = []
    if isinstance(process.demand, KnownQuantity) and process.scope != "CLEANING_AREA":
        values.append(ScenarioValue(input_path="process.demand_per_day", value=process.demand.normalized_value,
                                    unit=str(process.demand.unit), source_ref=process.demand.provenance_ref))
    if process.schedule is not None:
        values.extend([
            ScenarioValue(input_path="process.shift_hours", value=process.schedule.shift_hours.normalized_value,
                          unit="h", source_ref=process.schedule.shift_hours.provenance_ref),
            ScenarioValue(input_path="process.shifts_per_day", value=process.schedule.shifts_per_day.normalized_value,
                          unit="shift", source_ref=process.schedule.shifts_per_day.provenance_ref),
        ])
    if isinstance(process.route_distance, KnownQuantity):
        values.append(ScenarioValue(input_path="process.one_way_distance_m", value=process.route_distance.normalized_value,
                                    unit="m", source_ref=process.route_distance.provenance_ref))
    if process.exchange is not None:
        parts = [process.exchange.total_time] if process.exchange.mode == "TOTAL" else [process.exchange.load_time, process.exchange.unload_time]
        total = sum((Decimal(item.normalized_value) for item in parts), Decimal(0))
        values.append(ScenarioValue(input_path="process.exchange_total_time_s", value=format(total, "f"), unit="s",
                                    source_ref=parts[0].provenance_ref))
    if isinstance(process.explicit_batch, KnownQuantity):
        values.append(ScenarioValue(input_path="process.units_per_trip", value=process.explicit_batch.normalized_value,
                                    unit="unit/trip", source_ref=process.explicit_batch.provenance_ref))
    if request.cleaning_area is not None:
        values.append(ScenarioValue(input_path="process.cleaning_area_m2", value=request.cleaning_area.normalized_value,
                                    unit="m2", source_ref=request.cleaning_area.provenance_ref))
    if request.cleaning_frequency is not None:
        values.append(ScenarioValue(input_path="process.cleaning_frequency_per_day", value=request.cleaning_frequency.normalized_value,
                                    unit="1/day", source_ref=request.cleaning_frequency.provenance_ref))
    if request.selected_fleet is not None:
        values.append(ScenarioValue(input_path="run.selected_fleet_units", value=request.selected_fleet.normalized_value,
                                    unit="robot", source_ref=request.selected_fleet.provenance_ref))
    return sorted(values, key=lambda item: item.input_path)


def _vendor_provenance(position: CatalogPositionDTO) -> tuple[list[Provenance], dict[str, str]]:
    path_by_code = {field.rsplit(".", 1)[-1]: field for field in position.model.capacity_runtime.calculation_model_fields}
    requirement_by_path = {
        "specs.max_speed": "fact.max-speed", "specs.payload": "fact.payload",
        "capacity.cleaning_rate_m2_h": "fact.cleaning-rate", "specs.throughput": "fact.cell-rate",
    }
    provenance: list[Provenance] = []
    refs: dict[str, str] = {}
    for fact in position.model.capacity_runtime.vendor_facts:
        path = path_by_code.get(fact.code)
        requirement = requirement_by_path.get(path or "")
        if requirement is None:
            continue
        provenance_id = f"prov.vendor.{requirement.replace('.', '-')}"
        provenance.append({
            "provenance_id": provenance_id,
            "kind": "VENDOR_FACT",
            "fact_id": f"catalog.fact.{fact.code.replace('_', '-')}",
            "model_id": position.model.id,
            "position_id": position.id,
            "scope": fact.scope_code,
            "evidence_ids": [fact.evidence_id],
            "evidence_status": fact.resolution_status,
            "permitted_for_matching": True,
        })
        refs[requirement] = provenance_id
    return provenance, refs


def _terminal_response(request: CapacityAnalysisRequest, run_id: str, versions: VersionBindings,
                       code: str, message: str, *, reason: str = "UNSUPPORTED_PROCESS_PROFILE",
                       not_applicable: bool = False) -> CapacityAnalysisResponse:
    status = "NOT_APPLICABLE" if not_applicable else "BLOCKED"
    issue = None if not_applicable else ContractIssue(
        code=code, reason=reason, severity="BLOCKER",
        field_refs=["process", "model_id", "position_id"], decision_refs=["K19"], message=message,
    )
    trace = CalculationTrace(
        envelope=TraceEnvelope(engine_version=ENGINE_VERSION, run_id=run_id,
            input_revision=request.input_revision, acquisition=request.acquisition,
            uncertainty=request.uncertainty, process_id=request.process.process_id,
            model_id=request.model_id, position_id=request.position_id),
        versions=versions, provenance=request.provenance, inputs=[], formula_nodes=[],
        results=[TraceResult(result_id="result.capacity", status=status, value=None,
                             capacity_basis="NOT_APPLICABLE")],
        issues=[] if issue is None else [issue],
        replay=ReplayBinding(canonical_input_digest=semantic_digest(request), trace_content_digest=ZERO_DIGEST),
    )
    trace = finalize_trace(trace)
    capacity = CapacityResult(process_id=request.process.process_id, status=status, value=None,
                              blockers=[] if issue is None else [issue], trace_ref=f"trace.{run_id}")
    return CapacityAnalysisResponse(run_id=run_id, input_revision=request.input_revision,
                                    capacity=capacity, trace=trace)


def analyze_capacity(
    request: CapacityAnalysisRequest,
    snapshot: CatalogSnapshotDTO,
    run_id: str,
    *,
    constraint_provider: ConstraintProvider = conservative_constraints,
) -> CapacityExecutionSnapshotV2:
    position = _position(request, snapshot)
    versions = capacity_version_bindings(snapshot)
    route = route_process(request.process)
    constraints = constraint_provider(request, position)
    candidate = candidate_from_repository(position.formula_executability_dto())
    # The approved catalog stores generic transport profiles. Delivery uses the
    # same cycle equations and vendor facts, with its own units of demand.
    # Bind that typed profile only to this explicitly acknowledged preliminary
    # request; the catalog, membership and evidence-backed suitability stay intact.
    preliminary_delivery = (
        request.process.scope == "DELIVERY_CYCLE"
        and candidate.profile_id == "TRANSPORT_CYCLE_V1"
        and request.execution_mode == "PRELIMINARY_DEMO"
        and request.demo_assumptions_confirmed
    )
    if preliminary_delivery:
        candidate = candidate.model_copy(update={"profile_id": "DELIVERY_CYCLE_V1"})
    executability = evaluate_run_executability(
        candidate, _scenario_values(request), constraints.eligibility, registry_payload(),
        allow_preliminary=request.execution_mode == "PRELIMINARY_DEMO",
    )
    if route.disposition in {"REFERENCE_ONLY", "CONSTRAINT_ONLY", "NOT_APPLICABLE"}:
        response = _terminal_response(
            request, run_id, versions, route.reason_code,
            "Process has no accepted physical fleet-sizing profile",
            not_applicable=route.disposition == "NOT_APPLICABLE",
        )
        return CapacityExecutionSnapshotV2(response, route, constraints, executability)

    vendor_provenance, fact_refs = _vendor_provenance(position)
    provenance = [*request.provenance, *vendor_provenance]
    if preliminary_delivery:
        provenance.append(AssumptionProvenance.model_validate({
            "provenance_id": "prov.delivery-profile.confirmation", "kind": "ASSUMPTION",
            "assumption_id": "generic-transport-for-preliminary-delivery", "assumption_version": "v1",
            "rationale": "Общий транспортный профиль применён к явно заданной доставке; оснастка, масса партии и пригодность в клинике требуют отдельной проверки",
            "permitted_scope": "DELIVERY_CYCLE", "confirmation_state": "USER_CONFIRMED",
        }))
    if route.disposition == "TRANSPORT":
        engine_request = TransportCapacityRequestV1(
            run_id=run_id, acquisition=request.acquisition, uncertainty=request.uncertainty,
            process=request.process, model_id=request.model_id, position_id=request.position_id,
            operating_speed=request.operating_speed, item_mass=None, batch_limits=BatchLimitsV1(),
            selected_fleet=request.selected_fleet, operations=request.operations, executability=executability,
            constraints=constraints, versions=versions, provenance=provenance,
            fact_provenance=fact_refs,
        )
        response = calculate_transport_capacity(engine_request)
    elif route.disposition == "CLEANING":
        if request.cleaning_area is None:
            response = _terminal_response(request, run_id, versions, "c11-cleaning-area-missing",
                                          "Cleaning area must be explicit", reason="MISSING_INPUT")
        else:
            response = calculate_cleaning_capacity(CleaningCapacityRequestV1(
                run_id=run_id, acquisition=request.acquisition, uncertainty=request.uncertainty,
                process=request.process, model_id=request.model_id, position_id=request.position_id,
                area_source=DirectCleaningAreaV1(area=request.cleaning_area),
                frequency=request.cleaning_frequency, selected_fleet=request.selected_fleet, operations=request.operations,
                executability=executability, constraints=constraints, versions=versions,
                provenance=provenance, fact_provenance=fact_refs,
            ))
    elif route.disposition == "PALLETIZING":
        fact = next((item for item in executability.dependencies if item.requirement_id == "fact.cell-rate"), None)
        cell_rate = None if fact is None or fact.value is None else KnownQuantity(
            name="cell_rate", raw_value=str(fact.value), raw_unit=fact.unit,
            normalized_value=str(fact.value), unit=fact.unit, quantity_kind="RATE",
            provenance_ref=fact_refs["fact.cell-rate"],
        )
        response = calculate_palletizing_capacity(PalletizingCapacityRequestV1(
            run_id=run_id, acquisition=request.acquisition, uncertainty=request.uncertainty,
            process=request.process, model_id=request.model_id, position_id=request.position_id,
            cell_rate=cell_rate, selected_fleet=request.selected_fleet,
            executability=executability, constraints=constraints, versions=versions,
            provenance=provenance,
        ))
    else:
        response = _terminal_response(request, run_id, versions, "c11-route-unsupported",
                                      "USER_CYCLE requires its dedicated explicit contract")
    return CapacityExecutionSnapshotV2(response, route, constraints, executability)


def analyze_role_labour(request: LabourAnalysisRequestV1) -> LabourResultV1:
    """Versioned C14 boundary; supplied C07-C11 projections stay read-only."""

    return calculate_role_labour(request)


def analyze_purchase_costs(request: PurchaseLedgerRequestV1) -> PurchaseCostLedgerV1:
    """Versioned C15 boundary; C13/C14 snapshots remain immutable inputs."""

    return calculate_purchase_ledger(request)


def analyze_financials(request: FinancialAnalysisRequestV1) -> FinancialResultV1:
    """Versioned C16 boundary over immutable C14/C15 snapshots."""

    return calculate_financial_result(request)


def analyze_raas_financials(request: RaasAnalysisRequestV1) -> RaasFinancialResultV1:
    """Versioned C17 RaaS boundary; C13-C16 snapshots stay immutable."""

    return calculate_raas_financials(request)


def analyze_multiprocess_allocation(request: MultiprocessAllocationRequestV1) -> MultiprocessAllocationResultV1:
    """Versioned C18 boundary over immutable C14 and C16/C17 projections."""

    return calculate_multiprocess_allocation(request)


def analyze_ranking(request: RankingRequestV2) -> RankingResultV2:
    """Versioned C19 boundary over C05/C06 and frozen C18 cohort bindings."""

    return calculate_ranking(request)


def analyze_sensitivity(request: SensitivityRequestV1) -> SensitivityResultV1:
    """Versioned C20 boundary over immutable C18/C19 bindings."""

    return calculate_sensitivity(request)
