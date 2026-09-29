"""C14 role labour baseline v1.

The engine is deliberately pure.  It consumes C03 normalized processes and
role pool plus a small immutable projection of already calculated C07-C11
capacity.  It never calls a capacity engine and never mutates an old run.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import Field, model_serializer, model_validator

from calculation.registry import CalculationParameterRegistryV1, load_registry
from calculation.process_profiles.catalog import load_process_profile_catalog
from calculation_contracts import (
    Digest,
    KnownQuantity,
    MissingQuantity,
    NormalizedProcess,
    ObjectKind,
    RoleCode,
    RoleEntry,
    RolePool,
    StableId,
    StrictContractModel,
)


LABOUR_SCHEMA_VERSION = "role-labour-analysis-v1"
LABOUR_RESULT_VERSION = "role-labour-result-v1"
LABOUR_ENGINE_VERSION = "role-labour-baseline-v1"
V2A_POLICY_VERSION = "hackathon-calculation-policy-v1+v2a-c14"

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _canonical(value: str | int | Decimal) -> str:
    number = _d(value)
    if number == 0:
        return "0"
    rendered = format(number, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _floor(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _digest(value: object) -> str:
    if isinstance(value, StrictContractModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CapacityLabourProjectionV1(StrictContractModel):
    """Read-only projection of a C07-C11 result; no capacity arithmetic here."""

    schema_version: Literal["capacity-labour-projection-v1"] = "capacity-labour-projection-v1"
    process_id: StableId
    input_revision: StableId
    capacity_run_id: StableId
    capacity_status: Literal["COMPLETE", "WITH_ASSUMPTIONS", "BLOCKED", "NOT_APPLICABLE"]
    selected_fleet: Annotated[int, Field(ge=0)] | None
    coverage: DecimalString | None
    capacity_result_digest: Digest

    @model_validator(mode="after")
    def validate_projection(self) -> "CapacityLabourProjectionV1":
        if self.capacity_status in ("COMPLETE", "WITH_ASSUMPTIONS"):
            if self.selected_fleet is None or self.coverage is None:
                raise ValueError("executed capacity requires selected_fleet and coverage")
            if not (Decimal("0") <= _d(self.coverage) <= Decimal("1")):
                raise ValueError("coverage must be within 0..1")
            if self.selected_fleet == 0 and _d(self.coverage) != 0:
                raise ValueError("fleet 0 requires coverage 0")
        elif self.selected_fleet is not None or self.coverage is not None:
            raise ValueError("blocked/not-applicable capacity has no numerical projection")
        return self


class ManualProductivityInputV1(StrictContractModel):
    value: DecimalString
    unit: Annotated[str, Field(min_length=1, max_length=32)]
    source: Literal["USER", "FILE"]
    provenance_ref: StableId

    @model_validator(mode="after")
    def positive(self) -> "ManualProductivityInputV1":
        if _d(self.value) <= 0:
            raise ValueError("manual productivity must be positive")
        return self


class ProcessLabourInputV1(StrictContractModel):
    process: NormalizedProcess
    capacity: CapacityLabourProjectionV1
    role_id: StableId | None = None
    manual_units_per_shift: ManualProductivityInputV1 | None = None

    @model_validator(mode="after")
    def same_snapshot(self) -> "ProcessLabourInputV1":
        if self.capacity.process_id != self.process.process_id:
            raise ValueError("capacity/process identity mismatch")
        if self.capacity.input_revision != self.process.input_revision:
            raise ValueError("capacity/process revision mismatch")
        if self.role_id is not None and self.role_id not in self.process.role_refs:
            raise ValueError("labour role must be an explicit C03 role_ref")
        return self


class RoleAllocationInputV1(StrictContractModel):
    role_id: StableId
    shares: dict[StableId, DecimalString]
    source: Literal["USER", "FILE"]
    provenance_ref: StableId

    @model_validator(mode="after")
    def valid_shares(self) -> "RoleAllocationInputV1":
        if not self.shares:
            raise ValueError("explicit allocation shares cannot be empty")
        values = [_d(item) for item in self.shares.values()]
        if any(item < 0 or item > 1 for item in values) or sum(values) > 1:
            raise ValueError("allocation shares must be within 0..1 and sum <= 1")
        return self


class DeficitCostInputV1(StrictContractModel):
    role_id: StableId
    annual_cost_per_person: DecimalString
    unit: Literal["RUB/person/year"] = "RUB/person/year"
    semantics: Literal["MONETIZE", "DEFICIT_NOT_MONETIZED"]
    source: Literal["USER", "FILE"]
    provenance_ref: StableId

    @model_validator(mode="after")
    def valid_cost(self) -> "DeficitCostInputV1":
        amount = _d(self.annual_cost_per_person)
        if amount < 0:
            raise ValueError("deficit cost cannot be negative")
        if (amount == 0) != (self.semantics == "DEFICIT_NOT_MONETIZED"):
            raise ValueError("zero deficit cost requires explicit disabled semantics")
        return self


class SalarySourceBindingV1(StrictContractModel):
    role_id: StableId
    provenance_ref: StableId
    source: Literal["USER", "FILE"]


class StaffingDecisionV1(StrictContractModel):
    """Explicit coverage of the C14 requirement for a newly saved run."""

    control_mode: Literal["TRANSFER", "HIRE", "EXISTING"]
    technician_mode: Literal["TRANSFER", "HIRE", "EXISTING", "CONTRACTOR", "VENDOR"]
    technician_qualification_confirmed: bool = False
    control_transfer_monthly_supplement_gross: DecimalString = "0"
    technician_transfer_monthly_supplement_gross: DecimalString = "0"
    technician_contractor_annual_gross: DecimalString | None = None
    source: Literal["USER", "FILE"] = "USER"
    provenance_ref: StableId = "input.economics.staffing-decision"

    @model_validator(mode="after")
    def validate_decision(self) -> "StaffingDecisionV1":
        for value in (self.control_transfer_monthly_supplement_gross,
                      self.technician_transfer_monthly_supplement_gross):
            if _d(value) < 0:
                raise ValueError("staffing supplement cannot be negative")
        if self.technician_mode == "TRANSFER" and not self.technician_qualification_confirmed:
            raise ValueError("technician transfer requires qualification confirmation")
        if self.technician_mode == "CONTRACTOR" and (self.technician_contractor_annual_gross is None
                or _d(self.technician_contractor_annual_gross) < 0):
            raise ValueError("technician contractor needs an annual gross price")
        return self


from calculation.operating_policy import StaffingPolicyV2, WorkShareV1


class LabourAnalysisRequestV1(StrictContractModel):
    schema_version: Literal["role-labour-analysis-v1"] = LABOUR_SCHEMA_VERSION
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    object_id: StableId
    object_kind: ObjectKind
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"] = "BASE"
    role_pool: RolePool
    processes: list[ProcessLabourInputV1]
    allocations: list[RoleAllocationInputV1] = Field(default_factory=list)
    deficit_costs: list[DeficitCostInputV1] = Field(default_factory=list)
    salary_sources: list[SalarySourceBindingV1] = Field(default_factory=list)
    replacement_limit: DecimalString = "1"
    allow_surplus_replacement: bool = False
    base_forklift_count: Annotated[int, Field(ge=0)] | None = None
    staffing_decision: StaffingDecisionV1 | None = None
    staffing_policy: StaffingPolicyV2 | None = None
    work_share: WorkShareV1 | None = None

    @model_serializer(mode="wrap")
    def serialize_optional_decision(self, handler):
        payload = handler(self)
        if self.staffing_decision is None:
            payload.pop("staffing_decision", None)
        if self.staffing_policy is None:
            payload.pop("staffing_policy", None)
        if self.work_share is None:
            payload.pop("work_share", None)
        return payload

    @model_validator(mode="after")
    def validate_request(self) -> "LabourAnalysisRequestV1":
        if self.role_pool.object_kind != self.object_kind:
            raise ValueError("role pool object mismatch")
        if not (Decimal("0") <= _d(self.replacement_limit) <= Decimal("1")):
            raise ValueError("replacement_limit must be within 0..1")
        ids = [item.process.process_id for item in self.processes]
        if len(ids) != len(set(ids)):
            raise ValueError("process labour inputs must be unique")
        if any(item.process.input_revision != self.input_revision for item in self.processes):
            raise ValueError("all processes must use request input_revision")
        if any(item.process.object_kind != self.object_kind for item in self.processes):
            raise ValueError("all processes must use request object kind")
        role_ids = {item.role_id for item in self.role_pool.roles}
        for item in self.processes:
            if item.role_id is not None and item.role_id not in role_ids:
                raise ValueError("process references a role outside role_pool")
        allocation_roles = [item.role_id for item in self.allocations]
        deficit_roles = [item.role_id for item in self.deficit_costs]
        salary_roles = [item.role_id for item in self.salary_sources]
        if (len(allocation_roles) != len(set(allocation_roles))
                or len(deficit_roles) != len(set(deficit_roles))
                or len(salary_roles) != len(set(salary_roles))):
            raise ValueError("role-scoped inputs must be unique")
        if set(allocation_roles + deficit_roles + salary_roles) - role_ids:
            raise ValueError("role-scoped input references unknown role")
        known_processes = set(ids)
        if any(set(item.shares) - known_processes for item in self.allocations):
            raise ValueError("allocation references unknown process")
        salary_by_role = {item.role_id: item for item in self.salary_sources}
        for role in self.role_pool.roles:
            if isinstance(role.monthly_gross_salary, KnownQuantity):
                binding = salary_by_role.get(role.role_id)
                if binding is None or binding.provenance_ref != role.monthly_gross_salary.provenance_ref:
                    raise ValueError("known salary requires matching USER/FILE source binding")
            elif role.role_id in salary_by_role:
                raise ValueError("missing salary cannot have a source binding")
        return self


class MoneyBreakdownV1(StrictContractModel):
    monthly_gross: DecimalString
    annual_gross: DecimalString
    annual_direct: DecimalString
    annual_full: DecimalString
    annual_fixed_overhead: DecimalString
    unit: Literal["RUB/person/year"] = "RUB/person/year"
    salary_provenance_ref: StableId
    zero_cost_role: bool


class AllocationResultV1(StrictContractModel):
    role_id: StableId
    process_id: StableId
    allocated_people: Annotated[int, Field(ge=0)]
    method: Literal["EXPLICIT_LARGEST_REMAINDER", "PERSON_SHIFTS_LARGEST_REMAINDER"]
    weight: DecimalString
    provenance_ref: StableId


class ProcessLabourResultV1(StrictContractModel):
    process_id: StableId
    role_id: StableId | None
    status: Literal["COMPLETE", "INCOMPLETE", "NO_FOT_BENEFIT", "NOT_APPLICABLE"]
    reason_codes: list[StableId] = Field(default_factory=list)
    operating_hours_per_day: DecimalString | None = None
    manual_units_per_shift: DecimalString | None = None
    manual_unit: str | None = None
    person_shifts: Annotated[int, Field(ge=0)] | None = None
    rotation_factor: DecimalString | None = None
    required_people: Annotated[int, Field(ge=0)] | None = None
    allocated_people: Annotated[int, Field(ge=0)] | None = None
    capacity_coverage: DecimalString | None = None
    robot_people: Annotated[int, Field(ge=0)] | None = None
    robot_replacement: Annotated[int, Field(ge=0)] | None = None
    deficit_growth: Annotated[int, Field(ge=0)] | None = None
    applied: Annotated[int, Field(ge=0)] | None = None
    transferred: Annotated[int, Field(ge=0)] | None = None
    released: Annotated[int, Field(ge=0)] | None = None


class AnnualRoleStaffingV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=5)]
    ramp: DecimalString
    released: Annotated[int, Field(ge=0)]
    remaining: Annotated[int, Field(ge=0)]


class RoleLabourResultV1(StrictContractModel):
    role_id: StableId
    role_code: RoleCode
    status: Literal["COMPLETE", "INCOMPLETE"]
    headcount: Annotated[int, Field(ge=0)]
    required_people: Annotated[int, Field(ge=0)]
    deficit: Annotated[int, Field(ge=0)]
    surplus: Annotated[int, Field(ge=0)]
    allocated_people: Annotated[int, Field(ge=0)]
    unallocated_people: Annotated[int, Field(ge=0)]
    transferred: Annotated[int, Field(ge=0)]
    released: Annotated[int, Field(ge=0)]
    remaining: Annotated[int, Field(ge=0)]
    deficit_growth: Annotated[int, Field(ge=0)]
    money: MoneyBreakdownV1 | None
    deficit_cost_source: Literal["EXPLICIT", "DEFAULT_ANNUAL_DIRECT", "DISABLED", "INCOMPLETE"]
    annual_deficit_cost: DecimalString | None
    annual_staffing: list[AnnualRoleStaffingV1]
    reason_codes: list[StableId] = Field(default_factory=list)


class SiteOperatingStaffV1(StrictContractModel):
    requirement_details: dict | None = None
    total_selected_fleet: Annotated[int, Field(ge=0)]
    simultaneous_shifts: Annotated[int, Field(ge=0)]
    control_required: Annotated[int, Field(ge=0)]
    control_transferred: Annotated[int, Field(ge=0)]
    control_additional: Annotated[int, Field(ge=0)]
    technicians_required: Annotated[int, Field(ge=0)]
    technicians_billable: Annotated[int, Field(ge=0)] | None = None
    technicians_transferred: Annotated[int, Field(ge=0)] | None = None
    existing_control_headcount: Annotated[int, Field(ge=0)] | None = None
    existing_technician_headcount: Annotated[int, Field(ge=0)] | None = None
    technician_contractor_annual_gross: DecimalString | None = None
    control_transfer_monthly_supplement_gross: DecimalString | None = None
    technician_transfer_monthly_supplement_gross: DecimalString | None = None
    control_money: MoneyBreakdownV1 | None
    technician_money: MoneyBreakdownV1 | None
    status: Literal["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    reason_codes: list[StableId] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_optional_staffing(self, handler):
        payload = handler(self)
        if self.requirement_details is None:
            payload.pop("requirement_details", None)
        for field in ("technicians_billable", "technicians_transferred", "existing_control_headcount",
                      "existing_technician_headcount", "technician_contractor_annual_gross",
                      "control_transfer_monthly_supplement_gross",
                      "technician_transfer_monthly_supplement_gross"):
            if getattr(self, field) is None:
                payload.pop(field, None)
        return payload


class ForkliftLedgerV1(StrictContractModel):
    status: Literal["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    base_count: Annotated[int, Field(ge=0)] | None
    withdrawn: Annotated[int, Field(ge=0)] | None
    remaining: Annotated[int, Field(ge=0)] | None
    source: Literal["USER", "ROLE_DERIVED", "UNKNOWN", "NOT_APPLICABLE"]


class LabourTraceNodeV1(StrictContractModel):
    node_id: StableId
    formula_id: Literal["F08", "F09", "F10", "F11", "F12", "F13", "F14", "F15"]
    formula_version: Literal["calculation-formulas-v1"] = "calculation-formulas-v1"
    source_refs: list[Literal["R03", "POLICY_V1", "POLICY_V2A"]]
    input_refs: list[str]
    output_name: StableId
    output_value: DecimalString | None
    unit: Annotated[str, Field(min_length=1)]
    rounding: Literal["NONE", "FLOOR", "CEIL"] = "NONE"
    provenance_refs: list[StableId] = Field(default_factory=list)


class LabourVersionBindingsV1(StrictContractModel):
    engine_version: Literal["role-labour-baseline-v1"] = LABOUR_ENGINE_VERSION
    schema_version: Literal["role-labour-result-v1"] = LABOUR_RESULT_VERSION
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"] = "hackathon-calculation-policy-v1"
    v2a_policy_overlay_version: Literal["hackathon-calculation-policy-v1+v2a-c14"] = V2A_POLICY_VERSION
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    registry_digest: Digest
    process_catalog_version: Literal["calculation-process-catalog-v1"] = "calculation-process-catalog-v1"
    intake_version: Literal["calculation-intake-normalization-v2"] = "calculation-intake-normalization-v2"
    capacity_projection_version: Literal["capacity-labour-projection-v1"] = "capacity-labour-projection-v1"
    precision_policy_version: Literal["decimal-context-28-half-even-v1"] = "decimal-context-28-half-even-v1"


class LabourReplayV1(StrictContractModel):
    canonical_input_digest: Digest
    capacity_result_digests: list[Digest]
    trace_content_digest: Digest


class LabourResultV1(StrictContractModel):
    schema_version: Literal["role-labour-result-v1"] = LABOUR_RESULT_VERSION
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    object_id: StableId
    object_kind: ObjectKind
    labour_status: Literal["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    finance_status: Literal["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    processes: list[ProcessLabourResultV1]
    roles: list[RoleLabourResultV1]
    allocations: list[AllocationResultV1]
    operating_staff: SiteOperatingStaffV1
    forklifts: ForkliftLedgerV1
    total_deficit: Annotated[int, Field(ge=0)]
    total_surplus: Annotated[int, Field(ge=0)]
    total_released: Annotated[int, Field(ge=0)]
    total_transferred: Annotated[int, Field(ge=0)]
    total_additional_control: Annotated[int, Field(ge=0)]
    trace: list[LabourTraceNodeV1]
    issues: list[StableId]
    versions: LabourVersionBindingsV1
    replay: LabourReplayV1


def _registry_value(registry: CalculationParameterRegistryV1, parameter_id: str) -> Decimal:
    return _d(registry.by_id(parameter_id).value)


def _role_headcount(role: RoleEntry) -> int:
    if isinstance(role.headcount, MissingQuantity):
        raise ValueError(f"role {role.role_id} has missing headcount")
    value = _d(role.headcount.normalized_value)
    if value < 0 or value != value.to_integral_value():
        raise ValueError("role headcount must be a non-negative integer")
    return int(value)


def _money(role: RoleEntry, registry: CalculationParameterRegistryV1) -> MoneyBreakdownV1 | None:
    if isinstance(role.monthly_gross_salary, MissingQuantity):
        return None
    monthly = _d(role.monthly_gross_salary.normalized_value)
    annual = monthly * 12
    return MoneyBreakdownV1(
        monthly_gross=_canonical(monthly),
        annual_gross=_canonical(annual),
        annual_direct=_canonical(annual * _registry_value(registry, "labor.cost.direct-multiplier")),
        annual_full=_canonical(annual * _registry_value(registry, "labor.cost.full-multiplier")),
        annual_fixed_overhead=_canonical(annual * _registry_value(registry, "labor.cost.fixed-overhead-multiplier")),
        salary_provenance_ref=role.monthly_gross_salary.provenance_ref,
        zero_cost_role=monthly == 0,
    )


def _largest_remainder(total: int, weights: dict[str, Decimal]) -> dict[str, int]:
    if total == 0 or not weights:
        return {key: 0 for key in weights}
    weight_sum = sum(weights.values(), Decimal("0"))
    if weight_sum <= 0:
        weights = {key: Decimal("1") for key in weights}
        weight_sum = Decimal(len(weights))
    quotas = {key: Decimal(total) * value / weight_sum for key, value in weights.items()}
    result = {key: _floor(value) for key, value in quotas.items()}
    remaining = total - sum(result.values())
    ordered = sorted(weights, key=lambda key: (-(quotas[key] - result[key]), key))
    for key in ordered[:remaining]:
        result[key] += 1
    return result


def _allocate_role(
    role_id: str,
    headcount: int,
    process_ids: list[str],
    person_shifts: dict[str, int],
    explicit: RoleAllocationInputV1 | None,
) -> tuple[dict[str, int], list[AllocationResultV1], int]:
    if explicit is not None:
        weights = {process_id: _d(explicit.shares.get(process_id, "0")) for process_id in process_ids}
        target = _floor(Decimal(headcount) * sum(weights.values(), Decimal("0")))
        allocation = _largest_remainder(target, weights)
        method = "EXPLICIT_LARGEST_REMAINDER"
        provenance = explicit.provenance_ref
    else:
        weights = {process_id: Decimal(person_shifts[process_id]) for process_id in process_ids}
        allocation = _largest_remainder(headcount, weights)
        method = "PERSON_SHIFTS_LARGEST_REMAINDER"
        provenance = "policy.k17.person-shifts"
    rows = [AllocationResultV1(
        role_id=role_id, process_id=process_id, allocated_people=allocation[process_id],
        method=method, weight=_canonical(weights[process_id]), provenance_ref=provenance,
    ) for process_id in sorted(process_ids)]
    return allocation, rows, headcount - sum(allocation.values())


def _manual_shift_capacity(item: ProcessLabourInputV1, registry: CalculationParameterRegistryV1) -> tuple[Decimal, str, list[str]]:
    process = item.process
    if process.schedule is None or isinstance(process.demand, MissingQuantity):
        raise ValueError("active labour process requires normalized C03 demand and schedule")
    hours = _d(process.schedule.shift_hours.normalized_value)
    if item.manual_units_per_shift is not None:
        return _d(item.manual_units_per_shift.value), item.manual_units_per_shift.unit, [item.manual_units_per_shift.provenance_ref]
    if process.scope == "CLEANING_AREA":
        rate = _registry_value(registry, "labor.cleaning.mechanized-baseline-rate")
        useful = _registry_value(registry, "labor.cleaning.useful-time-share")
        return rate * hours * useful, "m2/shift", ["registry.labor.cleaning.mechanized-baseline-rate", "registry.labor.cleaning.useful-time-share"]
    kind = str(process.quantity_kind).lower()
    if process.route_distance is not None and kind in {"pallet", "box", "case", "cart", "delivery"}:
        distance = _d(process.route_distance.normalized_value)
        speed = _registry_value(registry, f"labor.manual-speed.{kind}")
        exchange = _registry_value(registry, f"labor.manual-exchange.{kind}")
        useful = _registry_value(registry, f"labor.useful-time.shift-{_canonical(hours)}h")
        batch = Decimal("1")
        if isinstance(process.explicit_batch, KnownQuantity):
            batch = _d(process.explicit_batch.normalized_value)
        cycle = Decimal("2") * distance / speed + exchange
        return Decimal("3600") / cycle * hours * useful * batch, f"{kind}/shift", [
            process.route_distance.provenance_ref, f"registry.labor.manual-speed.{kind}",
            f"registry.labor.manual-exchange.{kind}", f"registry.labor.useful-time.shift-{_canonical(hours)}h",
        ]
    fallback_id = f"labor.manual-shift-rate.{kind}"
    try:
        return _registry_value(registry, fallback_id), f"{kind}/shift", [f"registry.{fallback_id}"]
    except KeyError as exc:
        raise ValueError("manual_units_per_shift is required for this quantity kind") from exc


def manual_productivity_estimate(process: NormalizedProcess, *, registry: CalculationParameterRegistryV1 | None = None) -> dict[str, object]:
    """Expose the existing F08 registry calculation without a user norm."""
    registry = registry or load_registry()
    projection = CapacityLabourProjectionV1(
        process_id=process.process_id, input_revision=process.input_revision,
        capacity_run_id="preview.manual-productivity", capacity_status="NOT_APPLICABLE",
        selected_fleet=None, coverage=None, capacity_result_digest="sha256:" + "0" * 64,
    )
    try:
        value, unit, refs = _manual_shift_capacity(
            ProcessLabourInputV1(process=process, capacity=projection), registry)
    except (ValueError, KeyError):
        return {"status": "UNSUPPORTED", "value": None, "unit": None,
                "formula": None, "source_refs": []}
    kind = str(process.quantity_kind).lower()
    if process.scope == "CLEANING_AREA":
        formula = "F08: mechanized baseline rate × shift hours × useful-time share"
    elif process.route_distance is not None and kind in {"pallet", "box", "case", "cart", "delivery"}:
        formula = "F08: 3600 / (2 × one-way distance / manual speed + manual exchange) × shift hours × useful-time share × units per trip"
    else:
        formula = "F08: approved registry manual shift rate"
    inputs: dict[str, object] = {
        "distance_m": process.route_distance.normalized_value if isinstance(process.route_distance, KnownQuantity) else None,
        "shift_hours": process.schedule.shift_hours.normalized_value if process.schedule else None,
        "shifts_per_day": process.schedule.shifts_per_day.normalized_value if process.schedule else None,
        "demand_per_day": process.demand.normalized_value if isinstance(process.demand, KnownQuantity) else None,
        "role_refs": process.role_refs,
    }
    if process.scope == "CLEANING_AREA":
        inputs.update(mechanized_rate_m2_h=_canonical(_registry_value(registry, "labor.cleaning.mechanized-baseline-rate")),
                      useful_time_share=_canonical(_registry_value(registry, "labor.cleaning.useful-time-share")))
    elif process.route_distance is not None and kind in {"pallet", "box", "case", "cart", "delivery"}:
        hours = _d(process.schedule.shift_hours.normalized_value)
        inputs.update(manual_speed_m_s=_canonical(_registry_value(registry, f"labor.manual-speed.{kind}")),
                      manual_exchange_s=_canonical(_registry_value(registry, f"labor.manual-exchange.{kind}")),
                      useful_time_share=_canonical(_registry_value(registry, f"labor.useful-time.shift-{_canonical(hours)}h")),
                      units_per_trip=process.explicit_batch.normalized_value if isinstance(process.explicit_batch, KnownQuantity) else "1")
        if isinstance(process.explicit_batch, KnownQuantity):
            refs = [*refs, process.explicit_batch.provenance_ref]
    return {"status": "ESTIMATE", "value": _canonical(value), "unit": unit,
            "formula": formula, "source_refs": refs, "inputs": inputs}


def calculate_role_labour(
    request: LabourAnalysisRequestV1,
    *,
    registry: CalculationParameterRegistryV1 | None = None,
) -> LabourResultV1:
    """Calculate F08-F15 without invoking or altering capacity results."""

    registry = registry or load_registry()
    catalog = load_process_profile_catalog()
    role_by_id = {role.role_id: role for role in request.role_pool.roles}
    explicit_allocations = {item.role_id: item for item in request.allocations}
    deficit_inputs = {item.role_id: item for item in request.deficit_costs}
    process_work: dict[str, dict[str, object]] = {}
    process_results: list[ProcessLabourResultV1] = []
    trace: list[LabourTraceNodeV1] = []
    issues: set[str] = set()

    loss = _registry_value(registry, f"labor.nonproductive-loss.{str(request.object_kind).lower()}")
    vacation = _registry_value(registry, "labor.staffing.vacation-factor")

    for item in sorted(request.processes, key=lambda row: row.process.process_id):
        process = item.process
        profile = catalog.by_code(process.process_code)
        if not process.active:
            process_results.append(ProcessLabourResultV1(process_id=process.process_id, role_id=item.role_id, status="NOT_APPLICABLE", reason_codes=["process-inactive-or-not-applicable"]))
            continue
        if not profile.has_fot_savings:
            process_results.append(ProcessLabourResultV1(process_id=process.process_id, role_id=None, status="NO_FOT_BENEFIT", reason_codes=["no-fot-benefit"]))
            continue
        if item.capacity.capacity_status == "NOT_APPLICABLE":
            process_results.append(ProcessLabourResultV1(process_id=process.process_id, role_id=item.role_id, status="NOT_APPLICABLE", reason_codes=["capacity-not-applicable"]))
            continue
        if item.role_id is None:
            issues.add("labour-role-required")
            process_results.append(ProcessLabourResultV1(process_id=process.process_id, role_id=None, status="INCOMPLETE", reason_codes=["labour-role-required"]))
            continue
        if item.capacity.capacity_status == "BLOCKED":
            issues.add("capacity-projection-blocked")
            process_results.append(ProcessLabourResultV1(process_id=process.process_id, role_id=item.role_id, status="INCOMPLETE", reason_codes=["capacity-projection-blocked"]))
            continue
        try:
            manual, manual_unit, manual_provenance = _manual_shift_capacity(item, registry)
        except ValueError:
            issues.add("manual-productivity-required")
            process_results.append(ProcessLabourResultV1(process_id=process.process_id, role_id=item.role_id, status="INCOMPLETE", reason_codes=["manual-productivity-required"]))
            continue
        schedule = process.schedule
        assert schedule is not None and isinstance(process.demand, KnownQuantity)
        shifts = int(_d(schedule.shifts_per_day.normalized_value))
        hours = _d(schedule.shift_hours.normalized_value)
        days = _d(schedule.days_per_year.normalized_value)
        operating_hours = Decimal(shifts) * hours
        demand = _d(process.demand.normalized_value)
        person_shifts = max(shifts, _ceil(demand / manual))
        schedule_factor = Decimal("7") * days / Decimal("365") / (Decimal("40") / hours)
        rotation = max(Decimal("1"), schedule_factor * vacation) * (Decimal("1") + loss)
        required = _ceil(Decimal(person_shifts) * rotation)
        coverage = _d(item.capacity.coverage or "0")
        process_work[process.process_id] = {
            "item": item, "role_id": item.role_id, "shifts": shifts, "hours": hours,
            "person_shifts": person_shifts, "rotation": rotation, "required": required,
            "coverage": coverage, "manual": manual, "manual_unit": manual_unit,
        }
        process_results.append(ProcessLabourResultV1(
            process_id=process.process_id,
            role_id=item.role_id,
            status="INCOMPLETE",
        ))
        trace.extend([
            LabourTraceNodeV1(node_id=f"{process.process_id}.f08", formula_id="F08", source_refs=["R03", "POLICY_V1"], input_refs=["process.demand", "process.schedule", "process.route_distance"], output_name="manual_units_per_shift", output_value=_canonical(manual), unit=manual_unit, provenance_refs=manual_provenance),
            LabourTraceNodeV1(node_id=f"{process.process_id}.f09", formula_id="F09", source_refs=["R03", "POLICY_V1"], input_refs=[f"{process.process_id}.f08", "process.schedule"], output_name="required_people", output_value=str(required), unit="person", rounding="CEIL", provenance_refs=["registry.labor.staffing.vacation-factor", f"registry.labor.nonproductive-loss.{str(request.object_kind).lower()}"]),
        ])

    allocations: list[AllocationResultV1] = []
    allocation_by_process: dict[str, int] = {}
    unallocated_by_role: dict[str, int] = {}
    for role_id, role in sorted(role_by_id.items()):
        linked = sorted(process_id for process_id, work in process_work.items() if work["role_id"] == role_id)
        if not linked:
            continue
        headcount = _role_headcount(role)
        allocation, rows, unallocated = _allocate_role(
            role_id, headcount, linked,
            {process_id: int(process_work[process_id]["person_shifts"]) for process_id in linked},
            explicit_allocations.get(role_id),
        )
        allocation_by_process.update(allocation)
        allocations.extend(rows)
        unallocated_by_role[role_id] = unallocated

    replacement_limit = _d(request.replacement_limit)
    for result in process_results:
        work = process_work.get(result.process_id)
        if work is None:
            continue
        allocated = allocation_by_process[result.process_id]
        required = int(work["required"])
        coverage = work["coverage"]
        target = allocated if request.allow_surplus_replacement else min(required, allocated)
        robot_people = _floor(Decimal(required) * coverage)
        replaceable_capacity = _floor(Decimal(target) * coverage) if request.allow_surplus_replacement else robot_people
        replacement = min(replaceable_capacity, target)
        growth = min(max(0, robot_people - replacement), max(0, required - allocated))
        applied = _floor(Decimal(replacement) * replacement_limit)
        if request.work_share is not None:
            applied = min(applied, _floor(Decimal(allocated) * coverage * _d(request.work_share.fraction)))
        result.status = "COMPLETE"
        result.operating_hours_per_day = _canonical(Decimal(int(work["shifts"])) * work["hours"])
        result.manual_units_per_shift = _canonical(work["manual"])
        result.manual_unit = str(work["manual_unit"])
        result.person_shifts = int(work["person_shifts"])
        result.rotation_factor = _canonical(work["rotation"])
        result.required_people = required
        result.allocated_people = allocated
        result.capacity_coverage = _canonical(coverage)
        result.robot_people = robot_people
        result.robot_replacement = replacement
        result.deficit_growth = growth
        result.applied = applied
        result.transferred = 0
        result.released = applied
        trace.append(LabourTraceNodeV1(node_id=f"{result.process_id}.f11", formula_id="F11", source_refs=["R03", "POLICY_V1", "POLICY_V2A"], input_refs=[f"{result.process_id}.f09", "capacity.coverage", "role.allocation"], output_name="robot_replacement", output_value=str(replacement), unit="person", rounding="FLOOR", provenance_refs=[work["item"].capacity.capacity_run_id]))
        trace.append(LabourTraceNodeV1(node_id=f"{result.process_id}.f12", formula_id="F12", source_refs=["R03", "POLICY_V1"], input_refs=[f"{result.process_id}.f11", "replacement_limit"], output_name="applied", output_value=str(applied), unit="person", rounding="FLOOR", provenance_refs=["policy.k06.replacement-limit"]))

    applied_total = sum(item.applied or 0 for item in process_results)
    total_fleet = sum(item.capacity.selected_fleet or 0 for item in request.processes if item.capacity.capacity_status in ("COMPLETE", "WITH_ASSUMPTIONS"))
    simultaneous_shifts = max((int(work["shifts"]) for work in process_work.values()), default=0)
    supervision = _registry_value(registry, f"scenario.{request.uncertainty.lower()}.supervision-share")
    minimum_control = int(_registry_value(registry, "labor.control.minimum-per-shift"))
    control_required = 0 if total_fleet == 0 else max(_floor(Decimal(applied_total) * supervision), simultaneous_shifts * minimum_control)
    requirements = None
    if request.staffing_policy is not None:
        requirements = request.staffing_policy.requirement(total_fleet, simultaneous_shifts)
        control_required = requirements['control_fte']
    decision = request.staffing_decision
    existing_control = next((int(_d(role.headcount.normalized_value)) for role in request.role_pool.roles
                             if role.role_code == RoleCode.CONTROL_OPERATOR and isinstance(role.headcount, KnownQuantity)), 0)
    if decision is None:
        control_transferred = min(applied_total, control_required)
        control_additional = control_required - control_transferred
    else:
        uncovered_control = max(0, control_required - existing_control)
        if decision.control_mode == "EXISTING" and uncovered_control:
            raise ValueError("existing control staff does not cover C14 requirement")
        control_transferred = min(applied_total, uncovered_control) if decision.control_mode == "TRANSFER" else 0
        control_additional = uncovered_control - control_transferred
    tech_rate = int(_registry_value(registry, "labor.technical.robots-per-fte"))
    technicians = 0 if total_fleet == 0 else _ceil(Decimal(total_fleet) / Decimal(tech_rate))
    if requirements is not None:
        technicians = requirements['technician_fte']
    existing_tech = next((int(_d(role.headcount.normalized_value)) for role in request.role_pool.roles
                          if role.role_code == RoleCode.TECH_SUPPORT and isinstance(role.headcount, KnownQuantity)), 0)
    technicians_transferred = 0
    technicians_billable = technicians
    if decision is not None:
        uncovered_tech = max(0, technicians - existing_tech)
        if decision.technician_mode == "EXISTING" and uncovered_tech:
            raise ValueError("existing technicians do not cover C14 requirement")
        if decision.technician_mode == "TRANSFER":
            technicians_transferred = min(max(0, applied_total - control_transferred), uncovered_tech)
            if technicians_transferred < uncovered_tech:
                raise ValueError("released qualified staff do not cover C14 technician requirement")
        technicians_billable = uncovered_tech if decision.technician_mode in {"HIRE", "CONTRACTOR"} else 0
    released_total = applied_total - control_transferred - technicians_transferred
    transfer_distribution = _largest_remainder(control_transferred + technicians_transferred, {item.process_id: Decimal(item.applied or 0) for item in process_results if item.applied is not None})
    for item in process_results:
        if item.applied is not None:
            item.transferred = transfer_distribution.get(item.process_id, 0)
            item.released = item.applied - item.transferred
    trace.append(LabourTraceNodeV1(node_id="site.f13.control", formula_id="F13", source_refs=["R03", "POLICY_V1", "POLICY_V2A"], input_refs=["process.applied", "scenario.supervision-share", "schedule.simultaneous-shifts"], output_name="control_required", output_value=str(control_required), unit="person", rounding="FLOOR", provenance_refs=[f"registry.scenario.{request.uncertainty.lower()}.supervision-share", "registry.labor.control.minimum-per-shift"]))

    released_by_role: dict[str, int] = {}
    transferred_by_role: dict[str, int] = {}
    growth_by_role: dict[str, int] = {}
    required_by_role: dict[str, int] = {}
    for item in process_results:
        if item.role_id is None:
            continue
        released_by_role[item.role_id] = released_by_role.get(item.role_id, 0) + (item.released or 0)
        transferred_by_role[item.role_id] = transferred_by_role.get(item.role_id, 0) + (item.transferred or 0)
        growth_by_role[item.role_id] = growth_by_role.get(item.role_id, 0) + (item.deficit_growth or 0)
        required_by_role[item.role_id] = required_by_role.get(item.role_id, 0) + (item.required_people or 0)

    role_results: list[RoleLabourResultV1] = []
    ramp_values = [_registry_value(registry, f"scenario.{request.uncertainty.lower()}.ramp.year-{year}") for year in range(1, 6)]
    for role_id in sorted(required_by_role):
        role = role_by_id[role_id]
        headcount = _role_headcount(role)
        required = required_by_role[role_id]
        deficit = max(0, required - headcount)
        surplus = max(0, headcount - required)
        released = released_by_role.get(role_id, 0)
        transferred = transferred_by_role.get(role_id, 0)
        money = _money(role, registry)
        reason_codes: list[str] = []
        if money is None:
            reason_codes.append("salary-missing")
            issues.add("salary-missing")
        deficit_input = deficit_inputs.get(role_id)
        if deficit_input is not None and deficit_input.semantics == "DEFICIT_NOT_MONETIZED":
            deficit_source = "DISABLED"
            deficit_cost = Decimal("0")
        elif deficit_input is not None:
            deficit_source = "EXPLICIT"
            deficit_cost = _d(deficit_input.annual_cost_per_person)
        elif money is not None:
            deficit_source = "DEFAULT_ANNUAL_DIRECT"
            deficit_cost = _d(money.annual_direct)
        else:
            deficit_source = "INCOMPLETE"
            deficit_cost = None
        annual_deficit = None if deficit_cost is None else _canonical(Decimal(deficit) * deficit_cost)
        annual_staffing = [AnnualRoleStaffingV1(
            year=year, ramp=_canonical(ramp), released=min(released, _ceil(Decimal(released) * ramp)),
            remaining=headcount - min(released, _ceil(Decimal(released) * ramp)),
        ) for year, ramp in enumerate(ramp_values, 1)]
        role_results.append(RoleLabourResultV1(
            role_id=role_id, role_code=role.role_code, status="COMPLETE" if money is not None else "INCOMPLETE",
            headcount=headcount, required_people=required, deficit=deficit, surplus=surplus,
            allocated_people=headcount - unallocated_by_role.get(role_id, 0), unallocated_people=unallocated_by_role.get(role_id, 0),
            transferred=transferred, released=released, remaining=headcount - released,
            deficit_growth=growth_by_role.get(role_id, 0), money=money,
            deficit_cost_source=deficit_source, annual_deficit_cost=annual_deficit,
            annual_staffing=annual_staffing, reason_codes=reason_codes,
        ))
        trace.append(LabourTraceNodeV1(node_id=f"{role_id}.f10", formula_id="F10", source_refs=["R03", "POLICY_V1"], input_refs=["role.monthly_gross_salary"], output_name="annual_direct", output_value=None if money is None else money.annual_direct, unit="RUB/person/year", provenance_refs=[] if money is None else [money.salary_provenance_ref]))
        trace.append(LabourTraceNodeV1(node_id=f"{role_id}.f15", formula_id="F15", source_refs=["R03", "POLICY_V1", "POLICY_V2A"], input_refs=["role.required_people", "role.headcount", "role.deficit_cost"], output_name="annual_deficit_cost", output_value=annual_deficit, unit="RUB/year", provenance_refs=[] if deficit_input is None else [deficit_input.provenance_ref]))

    control_role = next((role for role in request.role_pool.roles if role.role_code == RoleCode.CONTROL_OPERATOR), None)
    tech_role = next((role for role in request.role_pool.roles if role.role_code == RoleCode.TECH_SUPPORT), None)
    staff_reasons: list[str] = []
    control_money = _money(control_role, registry) if control_role else None
    tech_money = _money(tech_role, registry) if tech_role else None
    if control_additional > 0 and control_money is None:
        staff_reasons.append("control-salary-missing")
        issues.add("control-salary-missing")
    if technicians_billable > 0 and tech_money is None and (decision is None or decision.technician_mode != "CONTRACTOR"):
        staff_reasons.append("technician-salary-missing")
        issues.add("technician-salary-missing")
    operating_status = "NOT_APPLICABLE" if total_fleet == 0 else ("INCOMPLETE" if staff_reasons else "COMPLETE")
    operating = SiteOperatingStaffV1(
        requirement_details=requirements,
        total_selected_fleet=total_fleet, simultaneous_shifts=simultaneous_shifts,
        control_required=control_required, control_transferred=control_transferred,
        control_additional=control_additional, technicians_required=technicians,
        technicians_billable=technicians_billable if decision is not None else None,
        technicians_transferred=technicians_transferred if decision is not None else None,
        existing_control_headcount=existing_control if decision is not None else None,
        existing_technician_headcount=existing_tech if decision is not None else None,
        technician_contractor_annual_gross=decision.technician_contractor_annual_gross if decision is not None and decision.technician_mode == "CONTRACTOR" else None,
        control_transfer_monthly_supplement_gross=decision.control_transfer_monthly_supplement_gross if decision is not None else None,
        technician_transfer_monthly_supplement_gross=decision.technician_transfer_monthly_supplement_gross if decision is not None else None,
        control_money=control_money, technician_money=tech_money, status=operating_status,
        reason_codes=staff_reasons,
    )
    trace.append(LabourTraceNodeV1(
        node_id="site.f13.technicians", formula_id="F13",
        source_refs=["R03", "POLICY_V1", "POLICY_V2A"],
        input_refs=["capacity.selected_fleet", "labor.technical.robots-per-fte"],
        output_name="technicians_required", output_value=str(technicians),
        unit="person", rounding="CEIL",
        provenance_refs=["registry.labor.technical.robots-per-fte"],
    ))

    driver = next((role for role in request.role_pool.roles if role.role_code == RoleCode.FORKLIFT_DRIVER), None)
    if not any(item.process.quantity_kind == "PALLET" for item in request.processes):
        forklifts = ForkliftLedgerV1(status="NOT_APPLICABLE", base_count=None, withdrawn=None, remaining=None, source="NOT_APPLICABLE")
    elif request.base_forklift_count is not None:
        base = request.base_forklift_count
        released_driver = released_by_role.get(driver.role_id, 0) if driver else 0
        withdrawn = min(base, _ceil(Decimal(released_driver) / max(1, simultaneous_shifts))) if driver else min(base, _ceil(Decimal(released_total) * _registry_value(registry, "labor.forklift-driver-fallback-share") / max(1, simultaneous_shifts)))
        forklifts = ForkliftLedgerV1(status="COMPLETE", base_count=base, withdrawn=withdrawn, remaining=base - withdrawn, source="USER")
    elif driver is not None:
        base = _ceil(Decimal(_role_headcount(driver)) / max(1, simultaneous_shifts))
        withdrawn = min(base, _ceil(Decimal(released_by_role.get(driver.role_id, 0)) / max(1, simultaneous_shifts)))
        forklifts = ForkliftLedgerV1(status="COMPLETE", base_count=base, withdrawn=withdrawn, remaining=base - withdrawn, source="ROLE_DERIVED")
    else:
        forklifts = ForkliftLedgerV1(status="INCOMPLETE", base_count=None, withdrawn=None, remaining=None, source="UNKNOWN")
        issues.add("forklift-base-unknown")
    trace.append(LabourTraceNodeV1(node_id="site.f14.forklifts", formula_id="F14", source_refs=["R03", "POLICY_V1"], input_refs=["base_forklift_count", "role.forklift_driver.released", "schedule.simultaneous_shifts"], output_name="forklifts_withdrawn", output_value=None if forklifts.withdrawn is None else str(forklifts.withdrawn), unit="unit", rounding="CEIL", provenance_refs=["policy.k08"]))

    numerical_processes = [item for item in process_results if item.status not in ("NOT_APPLICABLE", "NO_FOT_BENEFIT")]
    if not numerical_processes and all(item.status in ("NOT_APPLICABLE", "NO_FOT_BENEFIT") for item in process_results):
        labour_status = "NOT_APPLICABLE"
        finance_status = "NOT_APPLICABLE"
    else:
        labour_status = "INCOMPLETE" if any(item.status == "INCOMPLETE" for item in process_results) or any(item.status == "INCOMPLETE" for item in role_results) else "COMPLETE"
        finance_status = "INCOMPLETE" if labour_status == "INCOMPLETE" or operating.status == "INCOMPLETE" else "COMPLETE"

    versions = LabourVersionBindingsV1(
        registry_version=registry.registry_version,
        registry_digest=registry.registry_digest,
    )
    replay = LabourReplayV1(
        canonical_input_digest=_digest(request),
        capacity_result_digests=[item.capacity.capacity_result_digest for item in sorted(request.processes, key=lambda row: row.process.process_id)],
        trace_content_digest="sha256:" + "0" * 64,
    )
    result = LabourResultV1(
        run_id=request.run_id, project_id=request.project_id, tenant_id=request.tenant_id,
        input_revision=request.input_revision, object_id=request.object_id, object_kind=request.object_kind,
        labour_status=labour_status, finance_status=finance_status,
        processes=process_results, roles=role_results, allocations=allocations,
        operating_staff=operating, forklifts=forklifts,
        total_deficit=sum(item.deficit for item in role_results), total_surplus=sum(item.surplus for item in role_results),
        total_released=released_total, total_transferred=control_transferred + technicians_transferred,
        total_additional_control=control_additional, trace=trace, issues=sorted(issues),
        versions=versions, replay=replay,
    )
    trace_payload = result.model_dump(mode="json")
    trace_payload["replay"]["trace_content_digest"] = None
    result.replay.trace_content_digest = _digest(trace_payload)
    return result


__all__ = [
    "CapacityLabourProjectionV1", "DeficitCostInputV1", "LabourAnalysisRequestV1",
    "LabourResultV1", "ManualProductivityInputV1", "ProcessLabourInputV1",
    "RoleAllocationInputV1", "SalarySourceBindingV1", "calculate_role_labour",
]
