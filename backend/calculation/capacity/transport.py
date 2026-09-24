"""C07 transport/delivery capacity (F01-F04/F07) with deterministic trace.

The engine consumes only a C03 normalized process, C05/C06 eligibility results,
safe catalog facts, and immutable registry bindings.  It has no Robot pricing or
legacy commercial fallback and is not wired into production endpoints.
"""

from __future__ import annotations

import re
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
    DerivedProvenance,
    ExchangeTime,
    IntermediateValue,
    KnownQuantity,
    NormalizedProcess,
    PolicyProvenance,
    ProcessQuantityKind,
    Provenance,
    QuantityKind,
    QuantityName,
    ReplayBinding,
    RoundingEvent,
    StrictContractModel,
    TraceEnvelope,
    TraceResult,
    Unit,
    UserProvenance,
    VersionBindings,
    semantic_digest,
)

from .quantities import (
    actual_fleet_capacity,
    canonical,
    cycle_time,
    decimal,
    nominal_capacity,
    operating_hours,
    resolve_batch,
    size_fleet,
)
from .trace import finalize_trace, formula_node, result_quantity

ZERO_DIGEST = "sha256:" + "0" * 64
ENGINE_VERSION = "transport-capacity-engine-v1"


class BatchLimitsV1(StrictContractModel):
    explicit: KnownQuantity | None = None
    passport: KnownQuantity | None = None
    geometry: KnownQuantity | None = None

    @model_validator(mode="after")
    def names_are_typed(self) -> "BatchLimitsV1":
        expected = (
            (self.explicit, QuantityName.HANDLING_BATCH_LIMIT),
            (self.passport, QuantityName.PASSPORT_BATCH_LIMIT),
            (self.geometry, QuantityName.GEOMETRY_BATCH_LIMIT),
        )
        for value, name in expected:
            if value is not None and value.name != name:
                raise ValueError(f"batch limit must use {name}")
        return self


class TransportCapacityRequestV1(StrictContractModel):
    schema_version: Literal["transport-capacity-request-v1"] = "transport-capacity-request-v1"
    run_id: str = Field(min_length=1, max_length=128)
    acquisition: Literal["PURCHASE", "RAAS"]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    process: NormalizedProcess
    model_id: str = Field(min_length=1)
    position_id: str = Field(min_length=1)
    exchange: ExchangeTime | None = None
    operating_speed: KnownQuantity | None = None
    item_mass: KnownQuantity | None = None
    batch_limits: BatchLimitsV1 = Field(default_factory=BatchLimitsV1)
    selected_fleet: KnownQuantity | None = None
    executability: RunExecutabilityResult
    constraints: ConstraintReportV2
    versions: VersionBindings
    provenance: list[Provenance]
    fact_provenance: dict[str, str]

    @model_validator(mode="after")
    def identity_and_provenance(self) -> "TransportCapacityRequestV1":
        if self.process.scope not in {"TRANSPORT_CYCLE", "DELIVERY_CYCLE"}:
            raise ValueError("C07 accepts transport/delivery cycle processes only")
        if self.constraints.process_id != self.process.process_id or self.constraints.input_revision != self.process.input_revision:
            raise ValueError("constraint report identity does not match process")
        if self.constraints.model_id != self.model_id or self.constraints.position_id != self.position_id:
            raise ValueError("constraint report candidate identity mismatch")
        if self.executability.model_id != self.model_id or self.executability.position_id != self.position_id:
            raise ValueError("executability candidate identity mismatch")
        refs = {item.provenance_id for item in self.provenance}
        if len(refs) != len(self.provenance):
            raise ValueError("request provenance ids must be unique")
        quantities = [self.operating_speed, self.item_mass, self.selected_fleet,
                      self.batch_limits.explicit, self.batch_limits.passport, self.batch_limits.geometry]
        if self.exchange is not None:
            quantities.extend([self.exchange.total_time] if self.exchange.mode == "TOTAL" else [self.exchange.load_time, self.exchange.unload_time])
        if any(item is not None and item.provenance_ref not in refs for item in quantities):
            raise ValueError("request quantity has dangling provenance")
        if self.operating_speed is not None and self.operating_speed.name != QuantityName.OPERATING_SPEED:
            raise ValueError("operating speed has wrong semantics")
        if self.item_mass is not None and self.item_mass.name != QuantityName.ITEM_MASS:
            raise ValueError("item mass has wrong semantics")
        if self.selected_fleet is not None and self.selected_fleet.name != QuantityName.FLEET_SELECTED:
            raise ValueError("selected fleet has wrong semantics")
        by_id = {item.provenance_id: item for item in self.provenance}
        for requirement_id in ("fact.max-speed", "fact.payload"):
            ref = self.fact_provenance.get(requirement_id)
            source = by_id.get(ref) if ref else None
            if source is None or source.kind != "VENDOR_FACT":
                raise ValueError(f"{requirement_id} requires VENDOR_FACT provenance")
            if source.model_id != self.model_id or source.position_id != self.position_id:
                raise ValueError(f"{requirement_id} provenance identity mismatch")
        return self


def _dep(request: TransportCapacityRequestV1, requirement_id: str) -> DependencyResolution | None:
    return next((item for item in request.executability.dependencies if item.requirement_id == requirement_id), None)


def _safe_fact(request: TransportCapacityRequestV1, requirement_id: str) -> tuple[Decimal, str, str]:
    item = _dep(request, requirement_id)
    if item is None or item.status != "RESOLVED_SAFE_FACT" or item.value is None or item.unit is None:
        raise ValueError(f"{requirement_id} is not a safe resolved fact")
    provenance_ref = request.fact_provenance.get(requirement_id)
    if provenance_ref is None or provenance_ref not in {item.provenance_id for item in request.provenance}:
        raise ValueError(f"{requirement_id} lacks explicit safe provenance")
    return decimal(item.value), item.unit, provenance_ref


def _policy(request: TransportCapacityRequestV1, requirement_id: str) -> tuple[Decimal, str]:
    item = _dep(request, requirement_id)
    if item is None or item.status != "RESOLVED_POLICY" or not isinstance(item.value, list):
        raise ValueError(f"{requirement_id} is not pinned by C06")
    ids = item.field_or_path.split(",")
    suffix = request.uncertainty.lower()
    index = next((n for n, parameter_id in enumerate(ids) if f"scenario.{suffix}." in parameter_id), 0)
    return decimal(item.value[index]), ids[index]


def _assert_scenario_binding(
    request: TransportCapacityRequestV1, requirement_id: str, value: Decimal, unit: str
) -> None:
    item = _dep(request, requirement_id)
    if item is None or item.status != "RESOLVED_SCENARIO_INPUT":
        raise ValueError(f"{requirement_id} is not resolved by C06")
    if item.unit != unit or decimal(item.value) != value:
        raise ValueError(f"{requirement_id} differs from the C06 run snapshot")


def _q(name: QuantityName, value: Decimal, unit: Unit, kind: QuantityKind, provenance_ref: str) -> KnownQuantity:
    encoded = canonical(value)
    return KnownQuantity(name=name, raw_value=encoded, raw_unit=unit, normalized_value=encoded,
                         unit=unit, quantity_kind=kind, provenance_ref=provenance_ref)


def _blocked(request: TransportCapacityRequestV1, code: str, message: str) -> CapacityAnalysisResponse:
    reason = "MISSING_SAFE_FACT" if request.executability.status != "EXECUTABLE" else "INVALID_DOMAIN"
    issue = ContractIssue(code=code, reason=reason, severity="BLOCKER",
                          field_refs=["executability", "constraints"], decision_refs=["K02", "K03", "K04"], message=message)
    trace_ref = f"trace.{request.run_id}"
    provenance = list(request.provenance)
    trace = CalculationTrace(
        envelope=TraceEnvelope(engine_version=ENGINE_VERSION, run_id=request.run_id,
            input_revision=request.process.input_revision, acquisition=request.acquisition,
            uncertainty=request.uncertainty, process_id=request.process.process_id,
            model_id=request.model_id, position_id=request.position_id),
        versions=request.versions, provenance=provenance, inputs=[], formula_nodes=[], results=[
            TraceResult(result_id="result.capacity", status="BLOCKED", value=None, capacity_basis="NOT_APPLICABLE")],
        issues=[issue], replay=ReplayBinding(canonical_input_digest=semantic_digest(request), trace_content_digest=ZERO_DIGEST))
    trace = finalize_trace(trace)
    capacity = CapacityResult(process_id=request.process.process_id, status="BLOCKED", value=None,
                              blockers=[issue], trace_ref=trace_ref)
    return CapacityAnalysisResponse(run_id=request.run_id, input_revision=request.process.input_revision,
                                    capacity=capacity, trace=trace)


def calculate_transport_capacity(request: TransportCapacityRequestV1) -> CapacityAnalysisResponse:
    """Evaluate F01-F04/F07 once, retaining unrounded Decimal intermediates."""
    if not request.process.active:
        trace = CalculationTrace(
            envelope=TraceEnvelope(engine_version=ENGINE_VERSION, run_id=request.run_id,
                input_revision=request.process.input_revision, acquisition=request.acquisition,
                uncertainty=request.uncertainty, process_id=request.process.process_id,
                model_id=request.model_id, position_id=request.position_id),
            versions=request.versions, provenance=request.provenance, inputs=[], formula_nodes=[], results=[
                TraceResult(result_id="result.capacity", status="NOT_APPLICABLE", value=None, capacity_basis="NOT_APPLICABLE")],
            replay=ReplayBinding(canonical_input_digest=semantic_digest(request), trace_content_digest=ZERO_DIGEST))
        trace = finalize_trace(trace)
        return CapacityAnalysisResponse(run_id=request.run_id, input_revision=request.process.input_revision,
            capacity=CapacityResult(process_id=request.process.process_id, status="NOT_APPLICABLE", value=None,
                                    trace_ref=f"trace.{request.run_id}"), trace=trace)
    preliminary = (
        request.executability.status == "PRELIMINARY_EXECUTABLE"
        and request.constraints.eligibility == "NEEDS_VALIDATION"
    )
    if request.executability.status not in {"EXECUTABLE", "PRELIMINARY_EXECUTABLE"}:
        return _blocked(request, "c07-executability-blocked", "C06 dependency closure is not executable")
    if request.constraints.eligibility != "ELIGIBLE" and not preliminary:
        return _blocked(request, "c07-constraint-blocked", "C05 constraints are not eligible")
    try:
        if request.process.schedule is None or not isinstance(request.process.demand, KnownQuantity):
            raise ValueError("active cycle requires schedule and demand")
        if not isinstance(request.process.route_distance, KnownQuantity):
            raise ValueError("active cycle requires one-way distance")
        exchange = request.exchange or request.process.exchange
        if exchange is None:
            raise ValueError("active cycle requires total or split exchange")

        max_speed, speed_unit, speed_prov = _safe_fact(request, "fact.max-speed")
        payload, payload_unit, payload_prov = _safe_fact(request, "fact.payload")
        if speed_unit != "m/s" or payload_unit != "kg":
            raise ValueError("resolved fact units changed after C06")
        if request.operating_speed is not None:
            speed = decimal(request.operating_speed.normalized_value)
            if speed <= 0 or speed > max_speed:
                raise ValueError("USER operating speed must be positive and <= safe maximum")
            speed_input = request.operating_speed
            proxy = False
        else:
            speed = max_speed
            speed_input = _q(QuantityName.OPERATING_SPEED, speed, Unit.METER_PER_SECOND, QuantityKind.SPEED, speed_prov)
            proxy = True

        ex_inputs = [exchange.total_time] if exchange.mode == "TOTAL" else [exchange.load_time, exchange.unload_time]
        exchange_seconds = sum((decimal(item.normalized_value) for item in ex_inputs), Decimal(0))
        shifts = decimal(request.process.schedule.shifts_per_day.normalized_value)
        hours = decimal(request.process.schedule.shift_hours.normalized_value)
        demand = decimal(request.process.demand.normalized_value)
        distance = decimal(request.process.route_distance.normalized_value)
        h = operating_hours(shifts, hours)
        cycle = cycle_time(distance, speed, exchange_seconds)
        if cycle <= 0:
            raise ValueError("cycle time must be positive")

        item_mass_q = request.item_mass or (request.process.item_mass if isinstance(request.process.item_mass, KnownQuantity) else None)
        explicit_q = request.batch_limits.explicit or (request.process.explicit_batch if isinstance(request.process.explicit_batch, KnownQuantity) else None)
        batch, mass_limit = resolve_batch(
            box_mode=request.process.quantity_kind == ProcessQuantityKind.BOX, payload_kg=payload,
            item_mass_kg=decimal(item_mass_q.normalized_value) if item_mass_q else None,
            explicit_limit=decimal(explicit_q.normalized_value) if explicit_q else None,
            passport_limit=decimal(request.batch_limits.passport.normalized_value) if request.batch_limits.passport else None,
            geometry_limit=decimal(request.batch_limits.geometry.normalized_value) if request.batch_limits.geometry else None)
        _assert_scenario_binding(request, "input.demand", demand, str(request.process.demand.unit))
        _assert_scenario_binding(request, "input.exchange-total", exchange_seconds, "s")
        _assert_scenario_binding(request, "input.one-way-distance", distance, "m")
        _assert_scenario_binding(request, "input.shift-hours", hours, "h")
        _assert_scenario_binding(request, "input.shifts-per-day", shifts, "shift")
        _assert_scenario_binding(request, "input.units-per-trip", batch, "unit/trip")
        availability, availability_id = _policy(request, "policy.availability")
        intraday_peak, peak_id = _policy(request, "policy.intraday-peak")
        reserve, reserve_id = _policy(request, "policy.peak-reserve")
        seconds_per_hour, seconds_id = _policy(request, "policy.seconds-per-hour")
        if not (Decimal(0) < availability <= Decimal(1)) or intraday_peak < 0 or reserve < 0:
            raise ValueError("registry policy parameter is outside formula domain")
        trips, nominal = nominal_capacity(seconds_per_hour, cycle, batch)
        average, peak_factor, required, effective, recommended = size_fleet(
            demand_per_day=demand, operating_hours_per_day=h, intraday_peak=intraday_peak,
            reserve_share=reserve, nominal_units_per_hour=nominal, availability=availability)
        selected = (int(decimal(request.selected_fleet.normalized_value)) if request.selected_fleet else recommended)
        if request.selected_fleet is not None:
            _assert_scenario_binding(request, "input.selected-fleet", Decimal(selected), "robot")
        nominal_fleet, effective_fleet, coverage, raw_load, overloaded = actual_fleet_capacity(
            selected=selected, nominal_per_robot=nominal,
            effective_per_robot=effective, required=required)
        utilization = None if raw_load is None else min(raw_load, Decimal(1))
    except (ValueError, ArithmeticError) as exc:
        return _blocked(request, "c07-invalid-domain", str(exc))

    normalized_prov = "prov.normalized-process"
    policy_prov = "prov.policy.capacity"
    provenance = list(request.provenance)
    if normalized_prov not in {item.provenance_id for item in provenance}:
        provenance.append(UserProvenance(provenance_id=normalized_prov, confirmation_revision=request.process.input_revision))
    if policy_prov not in {item.provenance_id for item in provenance}:
        provenance.append(PolicyProvenance(provenance_id=policy_prov, policy_id="policy.capacity-k02-k04",
                                           policy_version="hackathon-calculation-policy-v1", decision_refs=["K02", "K03", "K04"]))
    trace_provenance_ids = {item.provenance_id for item in provenance}

    def trace_input(item: KnownQuantity) -> KnownQuantity:
        if item.provenance_ref in trace_provenance_ids:
            return item
        # C01 conversion nodes belong to the preceding normalization response,
        # not to the C11 trace's provenance graph. Bind their values to the
        # existing normalized-process source; leave the original ref in the
        # immutable request snapshot for replay and audit.
        if re.fullmatch(r"conversion\.\d{4,}", item.provenance_ref):
            return item.model_copy(update={"provenance_ref": normalized_prov})
        raise ValueError("C11 input provenance is not registered")

    if explicit_q is not None and batch == decimal(explicit_q.normalized_value):
        batch_prov = trace_input(explicit_q).provenance_ref
    elif request.process.quantity_kind == ProcessQuantityKind.BOX:
        batch_prov = "prov.derived.batch"
        provenance.append(DerivedProvenance(provenance_id=batch_prov, parent_node_ids=["node.f03"]))
    else:
        batch_prov = policy_prov
    assumptions: list[AssumptionUse] = []
    warnings: list[ContractIssue] = []
    if preliminary:
        assumption_prov = AssumptionProvenance(
            provenance_id="prov.assumption.preliminary-applicability",
            assumption_id="preliminary-applicability-unverified",
            assumption_version="demo-v1",
            rationale="C05 critical unknowns remain; numerical result is an acknowledged demo estimate, not deployment eligibility",
            permitted_scope=str(request.process.scope), confirmation_state="USER_CONFIRMED",
        )
        provenance.append(assumption_prov)
        assumptions.append(AssumptionUse(
            assumption_id=assumption_prov.assumption_id,
            assumption_version=assumption_prov.assumption_version,
            provenance_ref=assumption_prov.provenance_id,
            rationale=assumption_prov.rationale,
            permitted_scope=assumption_prov.permitted_scope,
            mode="DEFAULT", raw_user_override=None, applicable_scenario="ALL",
            confirmation_state="USER_CONFIRMED",
        ))
        warnings.append(ContractIssue(
            code="demo-applicability-unverified", reason="MISSING_SAFE_FACT", severity="WARNING",
            field_refs=["constraints.validation_codes"], decision_refs=["K15"],
            message="Preliminary calculation only; critical C05 checks need validation before procurement or deployment",
        ))
    if proxy:
        assumption_prov = AssumptionProvenance(provenance_id="prov.assumption.speed-proxy",
            assumption_id="safe-max-speed-optimistic-proxy", assumption_version="K02-v1",
            rationale="No USER operating speed; safe maximum is a disclosed optimistic proxy",
            permitted_scope=str(request.process.scope), confirmation_state="POLICY_ACCEPTED")
        if assumption_prov.provenance_id not in {item.provenance_id for item in provenance}:
            provenance.append(assumption_prov)
        assumptions.append(AssumptionUse(assumption_id=assumption_prov.assumption_id,
            assumption_version=assumption_prov.assumption_version, provenance_ref=assumption_prov.provenance_id,
            rationale=assumption_prov.rationale, permitted_scope=assumption_prov.permitted_scope,
            mode="DEFAULT", raw_user_override=None, applicable_scenario="ALL", confirmation_state="POLICY_ACCEPTED"))
        warnings.append(ContractIssue(code="speed-safe-max-proxy", reason="UNAPPROVED_ASSUMPTION", severity="WARNING",
            field_refs=["operating_speed"], decision_refs=["K02"], message="Safe maximum used as disclosed optimistic speed proxy"))

    inputs = [
        request.process.schedule.shifts_per_day.model_copy(update={"provenance_ref": normalized_prov}),
        request.process.schedule.shift_hours.model_copy(update={"provenance_ref": normalized_prov}),
        request.process.demand.model_copy(update={"provenance_ref": normalized_prov}),
        request.process.route_distance.model_copy(update={"provenance_ref": normalized_prov}),
        *(trace_input(item) for item in ex_inputs),
        trace_input(speed_input),
        _q(QuantityName.SAFE_MAX_SPEED, max_speed, Unit.METER_PER_SECOND, QuantityKind.SPEED, speed_prov),
        _q(QuantityName.PAYLOAD, payload, Unit.KILOGRAM, QuantityKind.MASS, payload_prov),
        _q(QuantityName.UNITS_PER_TRIP, batch, Unit.UNIT_PER_TRIP, QuantityKind.RATE, batch_prov),
        _q(QuantityName.AVAILABILITY, availability, Unit.DIMENSIONLESS, QuantityKind.FRACTION, policy_prov),
        _q(QuantityName.PEAK_FACTOR, intraday_peak, Unit.DIMENSIONLESS, QuantityKind.FRACTION, policy_prov),
        _q(QuantityName.RESERVE_SHARE, reserve, Unit.DIMENSIONLESS, QuantityKind.FRACTION, policy_prov),
        _q(QuantityName.SECONDS_PER_HOUR, seconds_per_hour, Unit.SECOND_PER_HOUR, QuantityKind.UNIT_DEFINITION, policy_prov),
    ]
    for optional in (item_mass_q, explicit_q, request.batch_limits.passport, request.batch_limits.geometry, request.selected_fleet):
        if optional is not None:
            bound = trace_input(optional)
            if bound not in inputs:
                inputs.append(bound)

    nodes = [
        formula_node("F01", [], ["shifts_per_day", "shift_hours"], applicability_domain="TRANSPORT_OR_DELIVERY_CYCLE"),
        formula_node("F02", [], ["one_way_distance", "operating_speed", exchange.mode.lower()], applicability_domain="TRANSPORT_OR_DELIVERY_CYCLE"),
        formula_node("F03", ["node.f02"], ["units_per_trip", seconds_id], applicability_domain="TRANSPORT_OR_DELIVERY_CYCLE"),
        formula_node("F04", ["node.f01", "node.f03"], ["demand_per_day", availability_id, peak_id, reserve_id], applicability_domain="TRANSPORT_OR_DELIVERY_CYCLE"),
        formula_node("F07", ["node.f04"], ["fleet_selected"], applicability_domain="TRANSPORT_OR_DELIVERY_CYCLE"),
    ]
    intermediate_data = [
        ("iv.operating-hours", "node.f01", QuantityName.OPERATING_HOURS_PER_DAY, h, Unit.HOUR, QuantityKind.TIME),
        ("iv.cycle-time", "node.f02", QuantityName.CYCLE_TIME, cycle, Unit.SECOND, QuantityKind.TIME),
        ("iv.trips-hour", "node.f03", QuantityName.TRIPS_PER_HOUR, trips, Unit.TRIP_PER_HOUR, QuantityKind.RATE),
        ("iv.nominal", "node.f03", QuantityName.NOMINAL_CAPACITY, nominal, Unit.UNIT_PER_HOUR, QuantityKind.RATE),
        ("iv.effective", "node.f04", QuantityName.EFFECTIVE_CAPACITY, effective, Unit.UNIT_PER_HOUR, QuantityKind.RATE),
        ("iv.required", "node.f04", QuantityName.REQUIRED_CAPACITY, required, Unit.UNIT_PER_HOUR, QuantityKind.RATE),
        ("iv.fleet", "node.f07", QuantityName.FLEET_CAPACITY, effective_fleet, Unit.UNIT_PER_HOUR, QuantityKind.RATE),
    ]
    intermediates = [IntermediateValue(value_id=i, node_id=n, name=name, value=result_quantity(v, unit, kind), parent_refs=[n])
                     for i, n, name, v, unit, kind in intermediate_data]
    roundings = [RoundingEvent(rounding_id="round.fleet-ceil", node_id="node.f04", operation="CEIL",
        input_value=canonical(required / effective), output_value=str(recommended),
        precision_policy_version="decimal-context-28-half-even-v1", reason="K04 exact fleet ceiling; epsilon forbidden",
        source_ref="POLICY_V1:K04")]
    if mass_limit is not None:
        roundings.insert(0, RoundingEvent(rounding_id="round.box-mass-floor", node_id="node.f03", operation="FLOOR",
            input_value=canonical(payload / decimal(item_mass_q.normalized_value)), output_value=str(mass_limit),
            precision_policy_version="decimal-context-28-half-even-v1", reason="K03 payload/item mass box floor",
            source_ref="POLICY_V1:K03"))
    constraint_evaluations = [ConstraintEvaluation(evaluation_id=f"constraint.{check.check_id}", check_id=check.check_id,
        check_version=check.rule_version, required_ref=check.required.source_ref if check.required else None,
        available_ref=check.available.source_ref if check.available else None, status=check.status,
        criticality="CRITICAL" if check.severity == "CRITICAL" else "ADVISORY", reason_code=check.reason_code,
        scope=semantic_digest(check.scope), prerequisite_refs=check.source_refs) for check in request.constraints.checks]
    if request.process.quantity_kind == ProcessQuantityKind.BOX and request.batch_limits.geometry is None:
        warnings.append(ContractIssue(code="box-geometry-limit-unknown", reason="MISSING_SAFE_FACT", severity="WARNING",
            field_refs=["batch_limits.geometry"], decision_refs=["K03"],
            message="Geometry batch limit is unknown and was excluded from the minimum"))
    status = "WITH_ASSUMPTIONS" if assumptions else "COMPLETE"
    values = CapacityValues(recommended_fleet=recommended, selected_fleet=selected,
        nominal_capacity=result_quantity(nominal_fleet, Unit.UNIT_PER_HOUR, QuantityKind.RATE),
        effective_capacity=result_quantity(effective_fleet, Unit.UNIT_PER_HOUR, QuantityKind.RATE),
        coverage=result_quantity(coverage, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        raw_load_ratio=None if raw_load is None else result_quantity(raw_load, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        utilization=None if utilization is None else result_quantity(utilization, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        overloaded=overloaded)
    capacity = CapacityResult(process_id=request.process.process_id, status=status, value=values,
                              warnings=warnings, trace_ref=f"trace.{request.run_id}")
    trace = CalculationTrace(
        envelope=TraceEnvelope(engine_version=ENGINE_VERSION, run_id=request.run_id,
            input_revision=request.process.input_revision, acquisition=request.acquisition,
            uncertainty=request.uncertainty, process_id=request.process.process_id,
            model_id=request.model_id, position_id=request.position_id),
        versions=request.versions, provenance=provenance, inputs=inputs, formula_nodes=nodes,
        intermediates=intermediates, assumptions=assumptions, constraints=constraint_evaluations,
        roundings=roundings, results=[TraceResult(result_id="result.effective-fleet-capacity", status=status,
            value=values.effective_capacity, supporting_node_ids=["node.f07"], capacity_basis="EFFECTIVE")],
        issues=warnings, replay=ReplayBinding(canonical_input_digest=semantic_digest(request), trace_content_digest=ZERO_DIGEST))
    trace = finalize_trace(trace)
    return CapacityAnalysisResponse(run_id=request.run_id, input_revision=request.process.input_revision,
                                    capacity=capacity, trace=trace)
