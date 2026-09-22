"""C09 fixed-cell palletizing capacity (F01/F06/F07) with typed trace."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from calculation.constraints import ConstraintReportV2
from calculation.executability import DependencyResolution, RunExecutabilityResult
from calculation_contracts import (
    AssumptionProvenance,
    AssumptionUse,
    CalculationTrace,
    CapacityAnalysisResponse,
    CapacityResult,
    CapacityValues,
    ConstraintEvaluation,
    ContractIssue,
    IntermediateValue,
    KnownQuantity,
    NormalizedProcess,
    PolicyProvenance,
    Provenance,
    QuantityKind,
    QuantityName,
    ReplayBinding,
    RoundingEvent,
    StrictContractModel,
    TraceEnvelope,
    TraceResult,
    Unit,
    UnitConversion,
    UserProvenance,
    VersionBindings,
    semantic_digest,
)

from .quantities import MINUTES_PER_HOUR, actual_fleet_capacity, canonical, decimal, operating_hours, palletizing_capacity
from .trace import finalize_trace, formula_node, result_quantity

ZERO_DIGEST = "sha256:" + "0" * 64
ENGINE_VERSION = "palletizing-capacity-engine-v1"


class PalletizingCapacityRequestV1(StrictContractModel):
    schema_version: Literal["palletizing-capacity-request-v1"] = "palletizing-capacity-request-v1"
    run_id: str = Field(min_length=1, max_length=128)
    acquisition: Literal["PURCHASE", "RAAS"]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    process: NormalizedProcess
    model_id: str = Field(min_length=1)
    position_id: str = Field(min_length=1)
    cell_rate: KnownQuantity | None
    selected_fleet: KnownQuantity | None = None
    executability: RunExecutabilityResult
    constraints: ConstraintReportV2
    versions: VersionBindings
    provenance: list[Provenance]

    @model_validator(mode="after")
    def validate_boundary(self) -> "PalletizingCapacityRequestV1":
        if self.process.scope != "FIXED_CELL" or self.process.quantity_kind != "PALLET":
            raise ValueError("C09 accepts pallet FIXED_CELL processes only")
        if any((self.process.route_distance, self.process.exchange, self.process.item_mass, self.process.explicit_batch)):
            raise ValueError("fixed-cell request cannot carry transport inputs")
        if self.constraints.process_id != self.process.process_id or self.constraints.input_revision != self.process.input_revision:
            raise ValueError("constraint report identity does not match process")
        if self.constraints.model_id != self.model_id or self.constraints.position_id != self.position_id:
            raise ValueError("constraint report candidate identity mismatch")
        if self.executability.model_id != self.model_id or self.executability.position_id != self.position_id:
            raise ValueError("executability candidate identity mismatch")
        if self.executability.status == "EXECUTABLE" and self.executability.profile_id != "PALLETIZING_THROUGHPUT_V1":
            raise ValueError("executable C09 request requires PALLETIZING_THROUGHPUT_V1")
        if self.cell_rate is not None and self.cell_rate.name != QuantityName.CELL_RATE:
            raise ValueError("cell rate requires pick/min cell_rate semantics")
        if self.selected_fleet is not None and self.selected_fleet.name != QuantityName.FLEET_SELECTED:
            raise ValueError("selected fleet has wrong semantics")
        refs = {item.provenance_id for item in self.provenance}
        if len(refs) != len(self.provenance):
            raise ValueError("request provenance ids must be unique")
        if any(item is not None and item.provenance_ref not in refs for item in (self.cell_rate, self.selected_fleet)):
            raise ValueError("request quantity has dangling provenance")
        if self.cell_rate is not None:
            source = next(item for item in self.provenance if item.provenance_id == self.cell_rate.provenance_ref)
            if source.kind not in {"VENDOR_FACT", "ASSUMPTION"}:
                raise ValueError("cell rate requires vendor fact or explicit assumption provenance")
            if source.kind == "VENDOR_FACT" and (source.model_id != self.model_id or source.position_id != self.position_id):
                raise ValueError("cell rate provenance identity mismatch")
            if source.kind == "ASSUMPTION" and not self.model_id.startswith("synthetic."):
                raise ValueError("assumed cell rate is restricted to explicit synthetic scenarios")
        return self


def _dependency(request: PalletizingCapacityRequestV1, requirement_id: str) -> DependencyResolution | None:
    return next((item for item in request.executability.dependencies if item.requirement_id == requirement_id), None)


def _policy(request: PalletizingCapacityRequestV1, requirement_id: str) -> tuple[Decimal, str]:
    item = _dependency(request, requirement_id)
    if item is None or item.status != "RESOLVED_POLICY" or not isinstance(item.value, list):
        raise ValueError(f"{requirement_id} is not pinned by C06")
    ids = item.field_or_path.split(",")
    suffix = request.uncertainty.lower()
    index = next((n for n, parameter_id in enumerate(ids) if f"scenario.{suffix}." in parameter_id), 0)
    return decimal(item.value[index]), ids[index]


def _assert_scenario(request: PalletizingCapacityRequestV1, requirement_id: str, value: Decimal, unit: str) -> None:
    item = _dependency(request, requirement_id)
    if item is None or item.status != "RESOLVED_SCENARIO_INPUT":
        raise ValueError(f"{requirement_id} is not resolved by C06")
    if item.unit != unit or decimal(item.value) != value:
        raise ValueError(f"{requirement_id} differs from the C06 run snapshot")


def _quantity(name: QuantityName, value: Decimal, unit: Unit, kind: QuantityKind, provenance_ref: str) -> KnownQuantity:
    encoded = canonical(value)
    return KnownQuantity(name=name, raw_value=encoded, raw_unit=unit, normalized_value=encoded,
                         unit=unit, quantity_kind=kind, provenance_ref=provenance_ref)


def _issue(code: str, reason: str, message: str) -> ContractIssue:
    return ContractIssue(code=code, reason=reason, severity="BLOCKER",
        field_refs=["process", "cell_rate", "executability", "constraints"],
        decision_refs=["K04", "K26", "K27", "K29"], message=message)


def _terminal(request: PalletizingCapacityRequestV1, *, status: Literal["BLOCKED", "NOT_APPLICABLE"],
              issue: ContractIssue | None = None) -> CapacityAnalysisResponse:
    issues = [issue] if issue else []
    trace = CalculationTrace(
        envelope=TraceEnvelope(engine_version=ENGINE_VERSION, run_id=request.run_id,
            input_revision=request.process.input_revision, acquisition=request.acquisition,
            uncertainty=request.uncertainty, process_id=request.process.process_id,
            model_id=request.model_id, position_id=request.position_id),
        versions=request.versions, provenance=request.provenance, inputs=[], formula_nodes=[],
        results=[TraceResult(result_id="result.capacity", status=status, value=None,
                             capacity_basis="NOT_APPLICABLE")],
        issues=issues, replay=ReplayBinding(canonical_input_digest=semantic_digest(request),
                                           trace_content_digest=ZERO_DIGEST))
    trace = finalize_trace(trace)
    return CapacityAnalysisResponse(run_id=request.run_id, input_revision=request.process.input_revision,
        capacity=CapacityResult(process_id=request.process.process_id, status=status, value=None,
            blockers=issues, trace_ref=f"trace.{request.run_id}"), trace=trace)


def calculate_palletizing_capacity(request: PalletizingCapacityRequestV1) -> CapacityAnalysisResponse:
    if not request.process.active:
        return _terminal(request, status="NOT_APPLICABLE")
    if request.executability.status != "EXECUTABLE":
        if any(code.startswith("fact.") for code in request.executability.blocker_codes):
            reason = "MISSING_SAFE_FACT"
        elif request.executability.status == "UNSUPPORTED_PROFILE":
            reason = "UNSUPPORTED_PROCESS_PROFILE"
        else:
            reason = "MISSING_INPUT"
        return _terminal(request, status="BLOCKED",
            issue=_issue("c09-executability-blocked", reason, "C06 palletizing dependency closure is not executable"))
    if request.constraints.eligibility != "ELIGIBLE":
        return _terminal(request, status="BLOCKED",
            issue=_issue("c09-constraint-blocked", "INVALID_DOMAIN", "C05 constraints are not eligible"))
    try:
        if request.process.schedule is None or not isinstance(request.process.demand, KnownQuantity):
            raise ValueError("active fixed cell requires schedule and pallet demand")
        if request.cell_rate is None:
            raise ValueError("active fixed cell requires explicit safe pick/min rate")
        fact = _dependency(request, "fact.cell-rate")
        rate = decimal(request.cell_rate.normalized_value)
        if fact is None or fact.status != "RESOLVED_SAFE_FACT" or fact.unit != "pick/min" or decimal(fact.value) != rate:
            raise ValueError("cell rate differs from safe C06 pick/min fact")
        demand = decimal(request.process.demand.normalized_value)
        if request.process.demand.unit != Unit.PALLET_PER_DAY:
            raise ValueError("F06 demand must be pallet/day")
        shifts = decimal(request.process.schedule.shifts_per_day.normalized_value)
        hours = decimal(request.process.schedule.shift_hours.normalized_value)
        h = operating_hours(shifts, hours)
        availability, availability_id = _policy(request, "policy.availability")
        boxes_per_pallet, boxes_id = _policy(request, "policy.boxes-per-pallet")
        efficiency, efficiency_id = _policy(request, "policy.cell-efficiency")
        picks_hour, boxes_day, nominal, effective, recommended = palletizing_capacity(
            demand_pallets_day=demand, rate_picks_minute=rate, operating_hours_day=h,
            cell_efficiency=efficiency, boxes_per_pallet=boxes_per_pallet, availability=availability)
        _assert_scenario(request, "input.demand", demand, "pallet/day")
        _assert_scenario(request, "input.shift-hours", hours, "h")
        _assert_scenario(request, "input.shifts-per-day", shifts, "shift")
        selected = int(decimal(request.selected_fleet.normalized_value)) if request.selected_fleet else recommended
        if request.selected_fleet is not None:
            _assert_scenario(request, "input.selected-fleet", Decimal(selected), "robot")
        nominal_fleet, effective_fleet, coverage, raw_load, overloaded = actual_fleet_capacity(
            selected=selected, nominal_per_robot=nominal, effective_per_robot=effective, required=demand)
        utilization = None if raw_load is None else min(raw_load, Decimal(1))
    except (ValueError, ArithmeticError) as exc:
        return _terminal(request, status="BLOCKED", issue=_issue("c09-invalid-domain", "INVALID_DOMAIN", str(exc)))

    normalized_provenance = "prov.normalized-process"
    policy_provenance = "prov.policy.palletizing"
    unit_provenance = "prov.unit.minutes-hour"
    provenance = list(request.provenance)
    known_ids = {item.provenance_id for item in provenance}
    if normalized_provenance not in known_ids:
        provenance.append(UserProvenance(provenance_id=normalized_provenance,
                                         confirmation_revision=request.process.input_revision))
    provenance.append(PolicyProvenance(provenance_id=policy_provenance,
        policy_id="policy.palletizing-f06-f07", policy_version="hackathon-calculation-policy-v1",
        decision_refs=["K04", "K26", "K27", "K29"]))
    provenance.append(PolicyProvenance(provenance_id=unit_provenance,
        policy_id="si-minutes-per-hour", policy_version="si-unit-definitions-v1", decision_refs=[]))

    assumptions: list[AssumptionUse] = []
    rate_source = next(item for item in request.provenance if item.provenance_id == request.cell_rate.provenance_ref)
    status: Literal["COMPLETE", "WITH_ASSUMPTIONS"] = "COMPLETE"
    if isinstance(rate_source, AssumptionProvenance):
        status = "WITH_ASSUMPTIONS"
        assumptions.append(AssumptionUse(assumption_id=rate_source.assumption_id,
            assumption_version=rate_source.assumption_version, provenance_ref=rate_source.provenance_id,
            rationale=rate_source.rationale, permitted_scope=rate_source.permitted_scope, mode="OVERRIDE",
            raw_user_override=request.cell_rate.raw_value, applicable_scenario="ALL",
            confirmation_state=rate_source.confirmation_state))

    inputs = [
        request.process.schedule.shifts_per_day.model_copy(update={"provenance_ref": normalized_provenance}),
        request.process.schedule.shift_hours.model_copy(update={"provenance_ref": normalized_provenance}),
        request.process.demand.model_copy(update={"provenance_ref": normalized_provenance}),
        request.cell_rate,
        _quantity(QuantityName.MINUTES_PER_HOUR, MINUTES_PER_HOUR, Unit.MINUTE_PER_HOUR,
                  QuantityKind.UNIT_DEFINITION, unit_provenance),
        _quantity(QuantityName.BOXES_PER_PALLET, boxes_per_pallet, Unit.BOX_PER_PALLET,
                  QuantityKind.RATE, policy_provenance),
        _quantity(QuantityName.CELL_EFFICIENCY, efficiency, Unit.DIMENSIONLESS,
                  QuantityKind.FRACTION, policy_provenance),
        _quantity(QuantityName.AVAILABILITY, availability, Unit.DIMENSIONLESS,
                  QuantityKind.FRACTION, policy_provenance),
    ]
    if request.selected_fleet is not None:
        inputs.append(request.selected_fleet)
    nodes = [
        formula_node("F01", [], ["shifts_per_day", "shift_hours"], applicability_domain="PALLETIZING_FIXED_CELL"),
        formula_node("F06", ["node.f01"], ["cell_rate", "minutes_per_hour", boxes_id, efficiency_id, availability_id],
                     applicability_domain="PALLETIZING_FIXED_CELL"),
        formula_node("F07", ["node.f06"], ["fleet_selected"], applicability_domain="PALLETIZING_FIXED_CELL"),
    ]
    conversion = UnitConversion(conversion_id="conversion.pick-minute-to-hour", input_ref="cell_rate",
        from_unit=Unit.PICK_PER_MINUTE, to_unit=Unit.PICK_PER_HOUR, exact_factor="60",
        operation="MULTIPLY", before=canonical(rate), after=canonical(picks_hour))
    intermediate_data = [
        ("iv.operating-hours", "node.f01", QuantityName.OPERATING_HOURS_PER_DAY, h, Unit.HOUR, QuantityKind.TIME),
        ("iv.picks-hour", "node.f06", QuantityName.PICKS_PER_HOUR, picks_hour, Unit.PICK_PER_HOUR, QuantityKind.RATE),
        ("iv.boxes-day", "node.f06", QuantityName.BOXES_PER_DAY, boxes_day, Unit.BOX_PER_DAY, QuantityKind.FLOW),
        ("iv.pallets-day", "node.f06", QuantityName.PALLETS_PER_DAY, nominal, Unit.PALLET_PER_DAY, QuantityKind.FLOW),
        ("iv.effective", "node.f06", QuantityName.EFFECTIVE_CAPACITY, effective, Unit.PALLET_PER_DAY, QuantityKind.FLOW),
        ("iv.fleet", "node.f07", QuantityName.FLEET_CAPACITY, effective_fleet, Unit.PALLET_PER_DAY, QuantityKind.FLOW),
    ]
    intermediates = [IntermediateValue(value_id=value_id, node_id=node_id, name=name,
        value=result_quantity(value, unit, kind), parent_refs=[node_id])
        for value_id, node_id, name, value, unit, kind in intermediate_data]
    constraints = [ConstraintEvaluation(evaluation_id=f"constraint.{check.check_id}", check_id=check.check_id,
        check_version=check.rule_version, required_ref=check.required.source_ref if check.required else None,
        available_ref=check.available.source_ref if check.available else None, status=check.status,
        criticality="CRITICAL" if check.severity == "CRITICAL" else "ADVISORY",
        reason_code=check.reason_code, scope=f"{request.process.scope}:{check.check_id}",
        prerequisite_refs=check.source_refs) for check in request.constraints.checks]
    rounding = RoundingEvent(rounding_id="round.palletizing-cell-ceil", node_id="node.f06",
        operation="CEIL", input_value=canonical(demand / effective), output_value=str(recommended),
        precision_policy_version="decimal-context-28-half-even-v1",
        reason="F06 exact fixed-cell ceiling; epsilon forbidden", source_ref="R03:F06")
    values = CapacityValues(recommended_fleet=recommended, selected_fleet=selected,
        nominal_capacity=result_quantity(nominal_fleet, Unit.PALLET_PER_DAY, QuantityKind.FLOW),
        effective_capacity=result_quantity(effective_fleet, Unit.PALLET_PER_DAY, QuantityKind.FLOW),
        coverage=result_quantity(coverage, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        raw_load_ratio=None if raw_load is None else result_quantity(raw_load, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        utilization=None if utilization is None else result_quantity(utilization, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        overloaded=overloaded)
    capacity = CapacityResult(process_id=request.process.process_id, status=status, value=values,
                              trace_ref=f"trace.{request.run_id}")
    trace = CalculationTrace(
        envelope=TraceEnvelope(engine_version=ENGINE_VERSION, run_id=request.run_id,
            input_revision=request.process.input_revision, acquisition=request.acquisition,
            uncertainty=request.uncertainty, process_id=request.process.process_id,
            model_id=request.model_id, position_id=request.position_id),
        versions=request.versions, provenance=provenance, inputs=inputs, formula_nodes=nodes,
        conversions=[conversion], intermediates=intermediates, assumptions=assumptions,
        constraints=constraints, roundings=[rounding], results=[TraceResult(
            result_id="result.effective-palletizing-fleet-capacity", status=status,
            value=values.effective_capacity, supporting_node_ids=["node.f07"], capacity_basis="EFFECTIVE")],
        replay=ReplayBinding(canonical_input_digest=semantic_digest(request), trace_content_digest=ZERO_DIGEST))
    trace = finalize_trace(trace)
    return CapacityAnalysisResponse(run_id=request.run_id, input_revision=request.process.input_revision,
                                    capacity=capacity, trace=trace)
