"""C08 cleaning-area capacity (F01/F05/F07) with reproducible trace."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, TypeAlias

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
    IntermediateValue,
    KnownQuantity,
    OperatingAvailabilityV1,
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
    UserProvenance,
    VersionBindings,
    semantic_digest,
)

from .quantities import actual_fleet_capacity, canonical, cleaning_capacity, decimal, operating_hours
from .trace import finalize_trace, formula_node, result_quantity

ZERO_DIGEST = "sha256:" + "0" * 64
ENGINE_VERSION = "cleaning-capacity-engine-v1"


class DirectCleaningAreaV1(StrictContractModel):
    mode: Literal["DIRECT"] = "DIRECT"
    area: KnownQuantity

    @model_validator(mode="after")
    def typed_area(self) -> "DirectCleaningAreaV1":
        if self.area.name != QuantityName.CLEANING_AREA:
            raise ValueError("direct cleaning area requires cleaning_area semantics")
        return self


class ShareCleaningAreaV1(StrictContractModel):
    mode: Literal["SHARE_OF_TOTAL"] = "SHARE_OF_TOTAL"
    total_area: KnownQuantity
    cleaning_share: KnownQuantity

    @model_validator(mode="after")
    def typed_derivation(self) -> "ShareCleaningAreaV1":
        if self.total_area.name != QuantityName.TOTAL_AREA:
            raise ValueError("share derivation requires total_area semantics")
        if self.cleaning_share.name != QuantityName.CLEANING_AREA_SHARE:
            raise ValueError("share derivation requires cleaning_area_share semantics")
        share = decimal(self.cleaning_share.normalized_value)
        if share <= 0 or share > 1:
            raise ValueError("cleaning area share must be in (0, 1]")
        return self


CleaningAreaSourceV1: TypeAlias = Annotated[
    DirectCleaningAreaV1 | ShareCleaningAreaV1, Field(discriminator="mode")
]


class CleaningCapacityRequestV1(StrictContractModel):
    schema_version: Literal["cleaning-capacity-request-v1"] = "cleaning-capacity-request-v1"
    run_id: str = Field(min_length=1, max_length=128)
    acquisition: Literal["PURCHASE", "RAAS"]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    process: NormalizedProcess
    model_id: str = Field(min_length=1)
    position_id: str = Field(min_length=1)
    area_source: CleaningAreaSourceV1
    frequency: KnownQuantity | None
    selected_fleet: KnownQuantity | None = None
    executability: RunExecutabilityResult
    constraints: ConstraintReportV2
    versions: VersionBindings
    provenance: list[Provenance]
    fact_provenance: dict[str, str]
    operations: OperatingAvailabilityV1 | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def validate_boundary(self) -> "CleaningCapacityRequestV1":
        if self.process.scope != "CLEANING_AREA" or self.process.quantity_kind != "SQUARE_METER":
            raise ValueError("C08 accepts square-meter CLEANING_AREA processes only")
        if any((self.process.route_distance, self.process.exchange, self.process.item_mass, self.process.explicit_batch)):
            raise ValueError("cleaning request cannot carry transport route/payload/batch inputs")
        if self.constraints.process_id != self.process.process_id or self.constraints.input_revision != self.process.input_revision:
            raise ValueError("constraint report identity does not match process")
        if self.constraints.model_id != self.model_id or self.constraints.position_id != self.position_id:
            raise ValueError("constraint report candidate identity mismatch")
        if self.executability.model_id != self.model_id or self.executability.position_id != self.position_id:
            raise ValueError("executability candidate identity mismatch")
        if self.executability.profile_id != "CLEANING_AREA_V1":
            raise ValueError("C08 requires CLEANING_AREA_V1 dependency profile")
        if self.frequency is not None and self.frequency.name != QuantityName.CLEANING_FREQUENCY:
            raise ValueError("frequency requires cleaning_frequency semantics")
        if self.selected_fleet is not None and self.selected_fleet.name != QuantityName.FLEET_SELECTED:
            raise ValueError("selected fleet has wrong semantics")
        refs = {item.provenance_id for item in self.provenance}
        if len(refs) != len(self.provenance):
            raise ValueError("request provenance ids must be unique")
        quantities = (
            [self.area_source.area]
            if self.area_source.mode == "DIRECT"
            else [self.area_source.total_area, self.area_source.cleaning_share]
        )
        quantities.extend([self.frequency, self.selected_fleet])
        if any(item is not None and item.provenance_ref not in refs for item in quantities):
            raise ValueError("request quantity has dangling provenance")
        by_id = {item.provenance_id: item for item in self.provenance}
        fact_ref = self.fact_provenance.get("fact.cleaning-rate")
        fact_source = by_id.get(fact_ref) if fact_ref else None
        if fact_source is None or fact_source.kind != "VENDOR_FACT":
            raise ValueError("cleaning rate requires VENDOR_FACT provenance")
        if fact_source.model_id != self.model_id or fact_source.position_id != self.position_id:
            raise ValueError("cleaning rate provenance identity mismatch")
        return self


def _dependency(request: CleaningCapacityRequestV1, requirement_id: str) -> DependencyResolution | None:
    return next((item for item in request.executability.dependencies if item.requirement_id == requirement_id), None)


def _safe_rate(request: CleaningCapacityRequestV1) -> tuple[Decimal, str]:
    item = _dependency(request, "fact.cleaning-rate")
    if item is None or item.status != "RESOLVED_SAFE_FACT" or item.unit != "m2/h":
        raise ValueError("cleaning rate is not a safe resolved m2/h fact")
    provenance_ref = request.fact_provenance["fact.cleaning-rate"]
    return decimal(item.value), provenance_ref


def _availability(request: CleaningCapacityRequestV1) -> tuple[Decimal, str]:
    item = _dependency(request, "policy.availability")
    if item is None or item.status != "RESOLVED_POLICY" or not isinstance(item.value, list):
        raise ValueError("availability is not pinned by C06")
    ids = item.field_or_path.split(",")
    suffix = request.uncertainty.lower()
    index = next((n for n, parameter_id in enumerate(ids) if f"scenario.{suffix}." in parameter_id), 0)
    return decimal(item.value[index]), ids[index]


def _assert_scenario(
    request: CleaningCapacityRequestV1, requirement_id: str, value: Decimal, unit: str
) -> None:
    item = _dependency(request, requirement_id)
    if item is None or item.status != "RESOLVED_SCENARIO_INPUT":
        raise ValueError(f"{requirement_id} is not resolved by C06")
    if item.unit != unit or decimal(item.value) != value:
        raise ValueError(f"{requirement_id} differs from the C06 run snapshot")


def _quantity(
    name: QuantityName, value: Decimal, unit: Unit, kind: QuantityKind, provenance_ref: str
) -> KnownQuantity:
    encoded = canonical(value)
    return KnownQuantity(
        name=name,
        raw_value=encoded,
        raw_unit=unit,
        normalized_value=encoded,
        unit=unit,
        quantity_kind=kind,
        provenance_ref=provenance_ref,
    )


def _issue(code: str, reason: str, message: str) -> ContractIssue:
    return ContractIssue(
        code=code,
        reason=reason,
        severity="BLOCKER",
        field_refs=["process", "executability", "constraints"],
        decision_refs=["K04"],
        message=message,
    )


def _terminal(
    request: CleaningCapacityRequestV1,
    *,
    status: Literal["BLOCKED", "NOT_APPLICABLE"],
    issue: ContractIssue | None = None,
) -> CapacityAnalysisResponse:
    issues = [issue] if issue else []
    trace = CalculationTrace(
        envelope=TraceEnvelope(
            engine_version=ENGINE_VERSION,
            run_id=request.run_id,
            input_revision=request.process.input_revision,
            acquisition=request.acquisition,
            uncertainty=request.uncertainty,
            process_id=request.process.process_id,
            model_id=request.model_id,
            position_id=request.position_id,
        ),
        versions=request.versions,
        provenance=request.provenance,
        inputs=[],
        formula_nodes=[],
        results=[TraceResult(result_id="result.capacity", status=status, value=None, capacity_basis="NOT_APPLICABLE")],
        issues=issues,
        replay=ReplayBinding(
            canonical_input_digest=semantic_digest(request), trace_content_digest=ZERO_DIGEST
        ),
    )
    trace = finalize_trace(trace)
    capacity = CapacityResult(
        process_id=request.process.process_id,
        status=status,
        value=None,
        blockers=issues,
        trace_ref=f"trace.{request.run_id}",
    )
    return CapacityAnalysisResponse(
        run_id=request.run_id,
        input_revision=request.process.input_revision,
        capacity=capacity,
        trace=trace,
    )


def calculate_cleaning_capacity(request: CleaningCapacityRequestV1) -> CapacityAnalysisResponse:
    if not request.process.active:
        return _terminal(request, status="NOT_APPLICABLE")
    preliminary = (
        request.executability.status == "PRELIMINARY_EXECUTABLE"
        and request.constraints.eligibility == "NEEDS_VALIDATION"
    )
    if request.executability.status not in {"EXECUTABLE", "PRELIMINARY_EXECUTABLE"}:
        blocker_reason = (
            "MISSING_SAFE_FACT"
            if any(code.startswith("fact.") for code in request.executability.blocker_codes)
            else "MISSING_INPUT"
        )
        return _terminal(
            request,
            status="BLOCKED",
            issue=_issue("c08-executability-blocked", blocker_reason, "C06 cleaning dependency closure is not executable"),
        )
    if request.constraints.eligibility != "ELIGIBLE" and not preliminary:
        return _terminal(
            request,
            status="BLOCKED",
            issue=_issue("c08-constraint-blocked", "INVALID_DOMAIN", "C05 constraints are not eligible"),
        )
    try:
        if request.process.schedule is None or not isinstance(request.process.demand, KnownQuantity):
            raise ValueError("active cleaning process requires schedule and daily area demand")
        if request.frequency is None:
            raise ValueError("active cleaning process requires frequency")
        shifts = decimal(request.process.schedule.shifts_per_day.normalized_value)
        hours = decimal(request.process.schedule.shift_hours.normalized_value)
        h = operating_hours(shifts, hours)
        frequency = decimal(request.frequency.normalized_value)
        if request.area_source.mode == "DIRECT":
            area = decimal(request.area_source.area.normalized_value)
            area_inputs = [request.area_source.area]
            area_mode = "direct"
        else:
            total_area = decimal(request.area_source.total_area.normalized_value)
            share = decimal(request.area_source.cleaning_share.normalized_value)
            area = total_area * share
            area_inputs = [request.area_source.total_area, request.area_source.cleaning_share]
            area_mode = "share-of-total"
        rate, rate_provenance = _safe_rate(request)
        availability, availability_id = _availability(request)
        if request.operations is not None:
            availability = request.operations.practical_fraction(h)
            availability_id = 'input.operations.practical-availability'
        required, nominal, effective, recommended = cleaning_capacity(
            area_m2=area,
            frequency_per_day=frequency,
            rate_m2_hour=rate,
            operating_hours_per_day=h,
            availability=availability,
        )
        demand = decimal(request.process.demand.normalized_value)
        if request.process.demand.unit != Unit.SQUARE_METER_PER_DAY or demand != required:
            raise ValueError("C03 cleaning demand must equal area × frequency in m2/day")
        _assert_scenario(request, "input.cleaning-area", area, "m2")
        _assert_scenario(request, "input.cleaning-frequency", frequency, "1/day")
        _assert_scenario(request, "input.shift-hours", hours, "h")
        _assert_scenario(request, "input.shifts-per-day", shifts, "shift")
        selected = int(decimal(request.selected_fleet.normalized_value)) if request.selected_fleet else recommended
        if request.selected_fleet is not None:
            _assert_scenario(request, "input.selected-fleet", Decimal(selected), "robot")
        nominal_fleet, effective_fleet, coverage, raw_load, overloaded = actual_fleet_capacity(
            selected=selected,
            nominal_per_robot=nominal,
            effective_per_robot=effective,
            required=required,
        )
        utilization = None if raw_load is None else min(raw_load, Decimal(1))
    except (ValueError, ArithmeticError) as exc:
        return _terminal(
            request,
            status="BLOCKED",
            issue=_issue("c08-invalid-domain", "INVALID_DOMAIN", str(exc)),
        )

    normalized_provenance = "prov.normalized-process"
    policy_provenance = "prov.policy.cleaning"
    provenance = list(request.provenance)
    if normalized_provenance not in {item.provenance_id for item in provenance}:
        provenance.append(
            UserProvenance(
                provenance_id=normalized_provenance,
                confirmation_revision=request.process.input_revision,
            )
        )
    if policy_provenance not in {item.provenance_id for item in provenance}:
        provenance.append(
            PolicyProvenance(
                provenance_id=policy_provenance,
                policy_id="policy.cleaning-f05-f07",
                policy_version="hackathon-calculation-policy-v1",
                decision_refs=["K04", "K27"],
            )
        )
    demo_assumptions = []
    demo_warnings = []
    if preliminary:
        demo_provenance = AssumptionProvenance(
            provenance_id="prov.assumption.preliminary-applicability",
            assumption_id="preliminary-applicability-unverified",
            assumption_version="demo-v1",
            rationale="C05 critical unknowns remain; numerical result is an acknowledged demo estimate, not deployment eligibility",
            permitted_scope=str(request.process.scope), confirmation_state="USER_CONFIRMED",
        )
        provenance.append(demo_provenance)
        demo_assumptions.append(AssumptionUse(
            assumption_id=demo_provenance.assumption_id,
            assumption_version=demo_provenance.assumption_version,
            provenance_ref=demo_provenance.provenance_id,
            rationale=demo_provenance.rationale,
            permitted_scope=demo_provenance.permitted_scope,
            mode="DEFAULT", raw_user_override=None, applicable_scenario="ALL",
            confirmation_state="USER_CONFIRMED",
        ))
        demo_warnings.append(ContractIssue(
            code="demo-applicability-unverified", reason="MISSING_SAFE_FACT", severity="WARNING",
            field_refs=["constraints.validation_codes"], decision_refs=["K15"],
            message="Preliminary calculation only; critical C05 checks need validation before procurement or deployment",
        ))
    area_provenance = area_inputs[0].provenance_ref
    if request.area_source.mode == "SHARE_OF_TOTAL":
        area_provenance = "prov.derived.cleaning-area"
        provenance.append(
            DerivedProvenance(
                provenance_id=area_provenance,
                parent_node_ids=["node.f05"],
            )
        )

    inputs = [
        request.process.schedule.shifts_per_day.model_copy(update={"provenance_ref": normalized_provenance}),
        request.process.schedule.shift_hours.model_copy(update={"provenance_ref": normalized_provenance}),
        request.process.demand.model_copy(update={"provenance_ref": normalized_provenance}),
        *area_inputs,
        request.frequency,
        _quantity(QuantityName.CLEANING_RATE, rate, Unit.SQUARE_METER_PER_HOUR, QuantityKind.RATE, rate_provenance),
        _quantity(QuantityName.AVAILABILITY, availability, Unit.DIMENSIONLESS, QuantityKind.FRACTION, policy_provenance),
    ]
    if request.selected_fleet is not None:
        inputs.append(request.selected_fleet)

    nodes = [
        formula_node("F01", [], ["shifts_per_day", "shift_hours"], applicability_domain="CLEANING_AREA"),
        formula_node(
            "F05",
            ["node.f01"],
            [area_mode, "cleaning_frequency", "cleaning_rate", availability_id],
            applicability_domain="CLEANING_AREA",
        ),
        formula_node("F07", ["node.f05"], ["fleet_selected"], applicability_domain="CLEANING_AREA"),
    ]
    intermediate_data = [
        ("iv.operating-hours", "node.f01", QuantityName.OPERATING_HOURS_PER_DAY, h, Unit.HOUR, QuantityKind.TIME),
        ("iv.cleaning-area", "node.f05", QuantityName.CLEANING_AREA, area, Unit.SQUARE_METER, QuantityKind.AREA),
        ("iv.required-area", "node.f05", QuantityName.CLEANING_AREA_PER_DAY, required, Unit.SQUARE_METER_PER_DAY, QuantityKind.FLOW),
        ("iv.nominal", "node.f05", QuantityName.NOMINAL_CAPACITY, nominal, Unit.SQUARE_METER_PER_DAY, QuantityKind.FLOW),
        ("iv.effective", "node.f05", QuantityName.EFFECTIVE_CAPACITY, effective, Unit.SQUARE_METER_PER_DAY, QuantityKind.FLOW),
        ("iv.fleet", "node.f07", QuantityName.FLEET_CAPACITY, effective_fleet, Unit.SQUARE_METER_PER_DAY, QuantityKind.FLOW),
    ]
    intermediates = [
        IntermediateValue(
            value_id=value_id,
            node_id=node_id,
            name=name,
            value=result_quantity(value, unit, kind),
            parent_refs=[area_provenance] if name == QuantityName.CLEANING_AREA else [node_id],
        )
        for value_id, node_id, name, value, unit, kind in intermediate_data
    ]
    constraints = [
        ConstraintEvaluation(
            evaluation_id=f"constraint.{check.check_id}",
            check_id=check.check_id,
            check_version=check.rule_version,
            required_ref=check.required.source_ref if check.required else None,
            available_ref=check.available.source_ref if check.available else None,
            status=check.status,
            criticality="CRITICAL" if check.severity == "CRITICAL" else "ADVISORY",
            reason_code=check.reason_code,
            scope=f"{request.process.scope}:{check.check_id}",
            prerequisite_refs=check.source_refs,
        )
        for check in request.constraints.checks
    ]
    rounding = RoundingEvent(
        rounding_id="round.cleaning-fleet-ceil",
        node_id="node.f05",
        operation="CEIL",
        input_value=canonical(required / effective),
        output_value=str(recommended),
        precision_policy_version="decimal-context-28-half-even-v1",
        reason="F05 exact cleaning fleet ceiling; epsilon forbidden",
        source_ref="R03:F05",
    )
    values = CapacityValues(
        recommended_fleet=recommended,
        selected_fleet=selected,
        nominal_capacity=result_quantity(nominal_fleet, Unit.SQUARE_METER_PER_DAY, QuantityKind.FLOW),
        effective_capacity=result_quantity(effective_fleet, Unit.SQUARE_METER_PER_DAY, QuantityKind.FLOW),
        coverage=result_quantity(coverage, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        raw_load_ratio=None if raw_load is None else result_quantity(raw_load, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        utilization=None if utilization is None else result_quantity(utilization, Unit.DIMENSIONLESS, QuantityKind.FRACTION),
        overloaded=overloaded,
    )
    capacity = CapacityResult(
        process_id=request.process.process_id,
        status="WITH_ASSUMPTIONS" if preliminary else "COMPLETE",
        value=values,
        warnings=demo_warnings,
        trace_ref=f"trace.{request.run_id}",
    )
    trace = CalculationTrace(
        envelope=TraceEnvelope(
            engine_version=ENGINE_VERSION,
            run_id=request.run_id,
            input_revision=request.process.input_revision,
            acquisition=request.acquisition,
            uncertainty=request.uncertainty,
            process_id=request.process.process_id,
            model_id=request.model_id,
            position_id=request.position_id,
        ),
        versions=request.versions,
        provenance=provenance,
        inputs=inputs,
        formula_nodes=nodes,
        intermediates=intermediates,
        assumptions=demo_assumptions,
        constraints=constraints,
        roundings=[rounding],
        results=[
            TraceResult(
                result_id="result.effective-cleaning-fleet-capacity",
                status="WITH_ASSUMPTIONS" if preliminary else "COMPLETE",
                value=values.effective_capacity,
                supporting_node_ids=["node.f07"],
                capacity_basis="EFFECTIVE",
            )
        ],
        issues=demo_warnings,
        replay=ReplayBinding(
            canonical_input_digest=semantic_digest(request), trace_content_digest=ZERO_DIGEST
        ),
    )
    trace = finalize_trace(trace)
    return CapacityAnalysisResponse(
        run_id=request.run_id,
        input_revision=request.process.input_revision,
        capacity=capacity,
        trace=trace,
    )
