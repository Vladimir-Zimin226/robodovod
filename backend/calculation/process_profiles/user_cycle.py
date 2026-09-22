"""Explicit generic cycle sizing for opt-in REFERENCE_ONLY operations.

This is a user-described operation, never a vendor/SKU capability claim.  It is
kept separate from the C07-C09 physical profiles so K19 mappings remain intact.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Literal

from pydantic import Field, model_validator

from calculation.capacity.quantities import canonical, ceil_exact, operating_hours
from calculation_contracts import (
    DecimalString,
    KnownQuantity,
    NormalizedProcess,
    Provenance,
    QuantityName,
    StrictContractModel,
    VersionBindings,
    semantic_digest,
)

from .router import ProcessRouteDecisionV1, route_process


class UserCycleRequestV1(StrictContractModel):
    schema_version: Literal["user-cycle-request-v1"] = "user-cycle-request-v1"
    run_id: str = Field(min_length=1, max_length=128)
    process: NormalizedProcess
    cycle_time: KnownQuantity
    units_per_cycle: KnownQuantity
    availability: KnownQuantity
    selected_fleet: KnownQuantity | None = None
    versions: VersionBindings
    provenance: list[Provenance]

    @model_validator(mode="after")
    def explicit_user_operation(self) -> "UserCycleRequestV1":
        decision = route_process(self.process, use_user_cycle=True)
        if decision.disposition != "USER_CYCLE":
            raise ValueError("process is not routed to USER_CYCLE")
        if not self.process.active or self.process.schedule is None:
            raise ValueError("active USER_CYCLE requires an explicit schedule")
        expected = (
            (self.cycle_time, QuantityName.CYCLE_TIME),
            (self.units_per_cycle, QuantityName.UNITS_PER_CYCLE),
            (self.availability, QuantityName.AVAILABILITY),
        )
        for quantity, name in expected:
            if quantity.name != name:
                raise ValueError(f"quantity must use {name}")
        by_id = {item.provenance_id: item for item in self.provenance}
        if len(by_id) != len(self.provenance):
            raise ValueError("provenance ids must be unique")
        process_quantities = [self.process.demand, self.process.schedule.shifts_per_day,
                              self.process.schedule.shift_hours, self.process.schedule.days_per_year]
        quantities = [self.cycle_time, self.units_per_cycle, self.availability,
                      self.selected_fleet, *process_quantities]
        for quantity in quantities:
            if quantity is None:
                continue
            if quantity.provenance_ref not in by_id:
                raise ValueError("USER_CYCLE quantity has dangling provenance")
        if self.selected_fleet is not None:
            if self.selected_fleet.name != QuantityName.FLEET_SELECTED:
                raise ValueError("selected fleet must use fleet_selected")
            selected = Decimal(self.selected_fleet.normalized_value)
            if selected < 0 or selected != selected.to_integral_value():
                raise ValueError("selected fleet must be a non-negative integer")
        for quantity in (self.cycle_time, self.units_per_cycle):
            if by_id[quantity.provenance_ref].kind not in {"USER", "FILE"}:
                raise ValueError("cycle and units/cycle must be explicit USER/FILE input")
        return self


class UserCycleCapacityResultV1(StrictContractModel):
    schema_version: Literal["user-cycle-capacity-result-v1"] = "user-cycle-capacity-result-v1"
    engine_version: Literal["user-cycle-capacity-engine-v1"] = "user-cycle-capacity-engine-v1"
    run_id: str
    process_id: str
    status: Literal["WITH_ASSUMPTIONS"] = "WITH_ASSUMPTIONS"
    route: ProcessRouteDecisionV1
    operating_hours_per_day: DecimalString
    required_units_per_hour: DecimalString
    nominal_units_per_hour: DecimalString
    effective_units_per_hour: DecimalString
    recommended_fleet: int = Field(ge=1)
    selected_fleet: int = Field(ge=0)
    coverage: DecimalString
    utilization: DecimalString | None
    overloaded: bool
    formula_ids: list[Literal["F01", "F03", "F04", "F07"]]
    input_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    versions: VersionBindings
    provenance: list[Provenance]


def calculate_user_cycle(request: UserCycleRequestV1) -> UserCycleCapacityResultV1:
    """Size a generic user-specified cycle with exact decimal arithmetic."""
    schedule = request.process.schedule
    assert schedule is not None
    h = operating_hours(Decimal(schedule.shifts_per_day.normalized_value),
                        Decimal(schedule.shift_hours.normalized_value))
    demand = Decimal(request.process.demand.normalized_value)
    cycle = Decimal(request.cycle_time.normalized_value)
    units = Decimal(request.units_per_cycle.normalized_value)
    availability = Decimal(request.availability.normalized_value)
    if cycle <= 0 or units <= 0:
        raise ValueError("cycle time and units/cycle must be positive")
    if not Decimal(0) < availability <= Decimal(1):
        raise ValueError("availability must be in (0, 1]")
    with localcontext() as context:
        context.prec = 28
        nominal = Decimal(3600) * units / cycle
        effective = nominal * availability
        required = demand / h
        recommended = ceil_exact(required / effective)
        selected = recommended if request.selected_fleet is None else int(Decimal(request.selected_fleet.normalized_value))
        total = Decimal(selected) * effective
        coverage = Decimal(0) if selected == 0 else min(total / required, Decimal(1))
        utilization = None if selected == 0 else required / total
    return UserCycleCapacityResultV1(
        run_id=request.run_id,
        process_id=request.process.process_id,
        route=route_process(request.process, use_user_cycle=True),
        operating_hours_per_day=canonical(h),
        required_units_per_hour=canonical(required),
        nominal_units_per_hour=canonical(nominal),
        effective_units_per_hour=canonical(effective),
        recommended_fleet=recommended,
        selected_fleet=selected,
        coverage=canonical(coverage),
        utilization=None if utilization is None else canonical(utilization),
        overloaded=selected == 0 or total < required,
        formula_ids=["F01", "F03", "F04", "F07"],
        input_digest=semantic_digest(request),
        versions=request.versions,
        provenance=request.provenance,
    )


def batch_jobs(
    raw_quantity: Decimal,
    items_per_container: Decimal,
    *,
    raw_kind: str,
    item_kind: str,
    explicit_conversion_factor: Decimal | None = None,
) -> int:
    """Convert raw demand to integral jobs without silently mixing dimensions."""
    if raw_quantity < 0 or items_per_container <= 0:
        raise ValueError("raw quantity must be non-negative and batch denominator positive")
    value = raw_quantity
    if raw_kind != item_kind:
        if explicit_conversion_factor is None or explicit_conversion_factor <= 0:
            raise ValueError("mixed quantity kinds require an explicit positive conversion")
        value *= explicit_conversion_factor
    return ceil_exact(value / items_per_container)
