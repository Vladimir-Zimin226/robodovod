"""C18 deterministic multiprocess allocation and combined project cash flow.

The engine consumes immutable, process-direct financial projections and one
object-scoped C14 labour result.  It never recalculates capacity, procurement,
purchase, or RaaS snapshots.  Shared capital, role pools, control operators,
and technicians are introduced exactly once at the project boundary.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from typing import Annotated, Literal

from calculation_contracts import Digest, StableId, StrictContractModel
from pydantic import Field, model_validator

from calculation.economics.metrics import npv, payback
from calculation.labour import LabourResultV1
from calculation.registry import CalculationParameterRegistryV1, load_registry

ALLOCATION_ENGINE_VERSION = "multiprocess-allocation-v1"
ALLOCATION_REQUEST_VERSION = "multiprocess-allocation-request-v1"
ALLOCATION_RESULT_VERSION = "multiprocess-allocation-result-v1"
ZERO_DIGEST = "sha256:" + "0" * 64

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]
MoneyString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")]


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _plain(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _digest(value: object) -> str:
    if isinstance(value, StrictContractModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _registry(registry: CalculationParameterRegistryV1, key: str) -> Decimal:
    return _d(registry.by_id(key).value)


class DirectAnnualCashflowV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    baseline_cf: MoneyString
    scenario_cf: MoneyString


class SelectedConfigurationV1(StrictContractModel):
    configuration_id: StableId
    process_id: StableId
    model_id: StableId
    position_id: StableId
    acquisition: Literal["PURCHASE", "RAAS"]
    source_run_id: StableId
    source_result_version: Literal["financial-result-v1", "raas-financial-result-v1"]
    source_result_digest: Digest
    projection_version: Literal["process-direct-financial-projection-v1"] = "process-direct-financial-projection-v1"
    cashflow_basis: Literal["PRIMARY_PRETAX"]
    excludes_object_shared_costs: Literal[True] = True
    direct_capex_cashflow: MoneyString
    allocation_basis_direct_capital: MoneyString
    annual_cashflows: list[DirectAnnualCashflowV1]

    @model_validator(mode="after")
    def validate_projection(self) -> SelectedConfigurationV1:
        if _d(self.direct_capex_cashflow) < 0 or _d(self.allocation_basis_direct_capital) < 0:
            raise ValueError("direct capital amounts cannot be negative")
        years = [item.year for item in self.annual_cashflows]
        if not 5 <= len(years) <= 15 or years != list(range(1, len(years) + 1)):
            raise ValueError("direct annual cashflows must cover consecutive years 1..h, h=5..15")
        if self.acquisition == "PURCHASE" and self.source_result_version != "financial-result-v1":
            raise ValueError("PURCHASE selection requires a C16 financial result projection")
        if self.acquisition == "RAAS" and self.source_result_version != "raas-financial-result-v1":
            raise ValueError("RAAS selection requires a C17 financial result projection")
        return self


class SharedSiteCapitalV1(StrictContractModel):
    capex_gross: MoneyString
    capex_amortizable: MoneyString
    capex_cashflow: MoneyString
    source: Literal["USER", "FILE", "POLICY"]
    provenance_ref: StableId
    scope: Literal["ONE_SITE_EXCLUDED_FROM_PROCESS_PROJECTIONS"] = "ONE_SITE_EXCLUDED_FROM_PROCESS_PROJECTIONS"

    @model_validator(mode="after")
    def non_negative(self) -> SharedSiteCapitalV1:
        values = tuple(map(_d, (self.capex_gross, self.capex_amortizable, self.capex_cashflow)))
        if any(value < 0 for value in values):
            raise ValueError("shared site capital cannot be negative")
        if values[1] > values[0]:
            raise ValueError("shared amortizable CAPEX cannot exceed gross CAPEX")
        return self


class SharedAnnualCostV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    baseline_cost: MoneyString
    scenario_cost: MoneyString
    source: Literal["USER", "FILE", "POLICY"]
    provenance_ref: StableId
    scope: Literal["ONE_SITE_NON_LABOUR_EXCLUDED_FROM_PROCESS_PROJECTIONS"] = "ONE_SITE_NON_LABOUR_EXCLUDED_FROM_PROCESS_PROJECTIONS"

    @model_validator(mode="after")
    def non_negative(self) -> SharedAnnualCostV1:
        if _d(self.baseline_cost) < 0 or _d(self.scenario_cost) < 0:
            raise ValueError("shared annual costs cannot be negative")
        return self


class DiscountRateV1(StrictContractModel):
    value: DecimalString
    unit: Literal["1"] = "1"
    source: Literal["USER", "FILE", "POLICY"]
    provenance_ref: StableId

    @model_validator(mode="after")
    def valid_rate(self) -> DiscountRateV1:
        if not Decimal(0) <= _d(self.value) <= Decimal(1):
            raise ValueError("discount rate must be within 0..1")
        return self


class MultiprocessAllocationRequestV1(StrictContractModel):
    schema_version: Literal["multiprocess-allocation-request-v1"] = ALLOCATION_REQUEST_VERSION
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    object_id: StableId
    cohort_id: StableId
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    configurations: list[SelectedConfigurationV1]
    labour_result: LabourResultV1
    labour_result_digest: Digest
    shared_site_capital: SharedSiteCapitalV1
    shared_annual_costs: list[SharedAnnualCostV1]
    discount_rate: DiscountRateV1

    @model_validator(mode="after")
    def bind_snapshots(self) -> MultiprocessAllocationRequestV1:
        if not self.configurations:
            raise ValueError("at least one selected configuration is required")
        if (self.labour_result.project_id, self.labour_result.tenant_id,
                self.labour_result.input_revision, self.labour_result.object_id) != (
                self.project_id, self.tenant_id, self.input_revision, self.object_id):
            raise ValueError("C14 snapshot identity/revision mismatch")
        if self.labour_result_digest != _digest(self.labour_result):
            raise ValueError("C14 labour result digest mismatch")
        if self.labour_result.finance_status not in ("COMPLETE", "NOT_APPLICABLE"):
            raise ValueError("C18 requires a complete object labour finance snapshot")
        process_ids = [item.process_id for item in self.configurations]
        configuration_ids = [item.configuration_id for item in self.configurations]
        if len(process_ids) != len(set(process_ids)) or len(configuration_ids) != len(set(configuration_ids)):
            raise ValueError("selected process and configuration identities must be unique")
        labour_processes = {
            item.process_id for item in self.labour_result.processes
            if item.status not in ("NOT_APPLICABLE", "NO_FOT_BENEFIT")
        }
        if set(process_ids) != labour_processes:
            raise ValueError("selected configurations must match executable C14 process identities")
        horizons = {len(item.annual_cashflows) for item in self.configurations}
        if len(horizons) != 1:
            raise ValueError("all selected configurations must use one horizon")
        horizon = next(iter(horizons))
        if [item.year for item in self.shared_annual_costs] != list(range(1, horizon + 1)):
            raise ValueError("shared annual costs must cover the same ordered horizon")
        _validate_labour_conservation(self.labour_result)
        self.configurations = sorted(self.configurations, key=lambda item: item.process_id)
        return self


class RoleConservationV1(StrictContractModel):
    role_id: StableId
    headcount: Annotated[int, Field(ge=0)]
    allocated_people: Annotated[int, Field(ge=0)]
    unallocated_people: Annotated[int, Field(ge=0)]
    transferred: Annotated[int, Field(ge=0)]
    released: Annotated[int, Field(ge=0)]
    remaining: Annotated[int, Field(ge=0)]
    conserved: Literal[True] = True


class ProcessAnnualAllocationV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    direct_baseline_cf: MoneyString
    direct_scenario_cf: MoneyString
    allocated_baseline_fot: MoneyString
    allocated_scenario_fot: MoneyString
    allocated_shared_baseline_cost: MoneyString
    allocated_shared_scenario_cost: MoneyString
    combined_baseline_cf: MoneyString
    combined_scenario_cf: MoneyString
    differential_cf: MoneyString


class ProcessAllocationResultV1(StrictContractModel):
    configuration_id: StableId
    process_id: StableId
    model_id: StableId
    position_id: StableId
    acquisition: Literal["PURCHASE", "RAAS"]
    source_run_id: StableId
    source_result_digest: Digest
    capital_allocation_basis: MoneyString
    capital_allocation_method: Literal["DIRECT_CAPITAL_LARGEST_REMAINDER", "EQUAL_ZERO_DENOMINATOR"]
    allocated_shared_capex_cashflow: MoneyString
    combined_capex_cashflow: MoneyString
    allocated_role_people: Annotated[int, Field(ge=0)]
    released_role_people: Annotated[int, Field(ge=0)]
    annual_ledgers: list[ProcessAnnualAllocationV1]


class ProjectAnnualLedgerV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    process_direct_baseline_cf: MoneyString
    process_direct_scenario_cf: MoneyString
    object_baseline_fot: MoneyString
    object_scenario_fot: MoneyString
    shared_baseline_cost: MoneyString
    shared_scenario_cost: MoneyString
    combined_baseline_cf: MoneyString
    combined_scenario_cf: MoneyString
    differential_cf: MoneyString


class AllocationMetricV1(StrictContractModel):
    status: Literal["COMPLETE", "NOT_REACHED"]
    value: MoneyString | DecimalString | None
    unit: Literal["RUB", "YEAR"]


class AllocationTraceNodeV1(StrictContractModel):
    node_id: StableId
    operation: Literal["ALLOCATE_SITE_CAPITAL", "ALLOCATE_OBJECT_FOT", "ALLOCATE_SHARED_COST", "COMBINE_CASHFLOW", "PROJECT_METRIC"]
    input_refs: list[str]
    output_ref: StableId
    value: DecimalString | None
    unit: Literal["RUB", "PERSON", "YEAR"]
    rounding: Literal["NONE", "HALF_EVEN_CENT_LARGEST_REMAINDER"] = "NONE"


class AllocationVersionBindingsV1(StrictContractModel):
    engine_version: Literal["multiprocess-allocation-v1"] = ALLOCATION_ENGINE_VERSION
    request_version: Literal["multiprocess-allocation-request-v1"] = ALLOCATION_REQUEST_VERSION
    result_version: Literal["multiprocess-allocation-result-v1"] = ALLOCATION_RESULT_VERSION
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"] = "hackathon-calculation-policy-v1"
    labour_policy_overlay_version: Literal["hackathon-calculation-policy-v1+v2a-c14"] = "hackathon-calculation-policy-v1+v2a-c14"
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    registry_digest: Digest
    precision_policy_version: Literal["decimal-context-28-half-even-v1"] = "decimal-context-28-half-even-v1"


class AllocationReplayV1(StrictContractModel):
    canonical_input_digest: Digest
    labour_result_digest: Digest
    source_result_digests: list[Digest]
    trace_content_digest: Digest


class MultiprocessAllocationResultV1(StrictContractModel):
    schema_version: Literal["multiprocess-allocation-result-v1"] = ALLOCATION_RESULT_VERSION
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    object_id: StableId
    cohort_id: StableId
    horizon_years: Annotated[int, Field(ge=5, le=15)]
    status: Literal["COMPLETE"] = "COMPLETE"
    processes: list[ProcessAllocationResultV1]
    role_conservation: list[RoleConservationV1]
    unallocated_role_people: Annotated[int, Field(ge=0)]
    total_released_people: Annotated[int, Field(ge=0)]
    control_required_once: Annotated[int, Field(ge=0)]
    technicians_required_once: Annotated[int, Field(ge=0)]
    shared_capex_cashflow: MoneyString
    project_capex_cashflow: MoneyString
    initial_baseline_cf: Literal["0.00"] = "0.00"
    initial_scenario_cf: MoneyString
    annual_ledgers: list[ProjectAnnualLedgerV1]
    npv_base: AllocationMetricV1
    npv_scenario: AllocationMetricV1
    npv_project: AllocationMetricV1
    simple_payback: AllocationMetricV1
    discounted_payback: AllocationMetricV1
    trace: list[AllocationTraceNodeV1]
    versions: AllocationVersionBindingsV1
    replay: AllocationReplayV1


def _validate_labour_conservation(labour: LabourResultV1) -> None:
    allocations: dict[str, int] = {}
    for item in labour.allocations:
        allocations[item.role_id] = allocations.get(item.role_id, 0) + item.allocated_people
    released_by_role: dict[str, int] = {}
    transferred_by_role: dict[str, int] = {}
    for item in labour.processes:
        if item.role_id is not None:
            released_by_role[item.role_id] = released_by_role.get(item.role_id, 0) + (item.released or 0)
            transferred_by_role[item.role_id] = transferred_by_role.get(item.role_id, 0) + (item.transferred or 0)
    for role in labour.roles:
        if allocations.get(role.role_id, 0) != role.allocated_people:
            raise ValueError(f"C14 role allocation is not conserved for {role.role_id}")
        if role.allocated_people + role.unallocated_people != role.headcount:
            raise ValueError(f"C14 role pool is not conserved for {role.role_id}")
        if released_by_role.get(role.role_id, 0) != role.released:
            raise ValueError(f"C14 released people mismatch for {role.role_id}")
        if transferred_by_role.get(role.role_id, 0) != role.transferred:
            raise ValueError(f"C14 transferred people mismatch for {role.role_id}")
        if role.released > role.allocated_people or role.released + role.remaining != role.headcount:
            raise ValueError(f"C14 released/remaining role pool is not conserved for {role.role_id}")
    if sum(role.released for role in labour.roles) != labour.total_released:
        raise ValueError("C14 total released people mismatch")
    if labour.total_transferred != labour.operating_staff.control_transferred + (labour.operating_staff.technicians_transferred or 0):
        raise ValueError("C14 control transfer must be object-scoped exactly once")


def _allocate_cents(amount: Decimal, weights: dict[str, Decimal]) -> dict[str, Decimal]:
    """Allocate a two-decimal amount exactly; ties are stable process IDs."""

    cents = int((amount * 100).to_integral_exact())
    if not weights:
        return {}
    weight_sum = sum(weights.values(), Decimal(0))
    effective = weights if weight_sum > 0 else {key: Decimal(1) for key in weights}
    effective_sum = sum(effective.values(), Decimal(0))
    quotas = {key: Decimal(cents) * value / effective_sum for key, value in effective.items()}
    allocated = {key: int(value.to_integral_value(rounding=ROUND_FLOOR)) for key, value in quotas.items()}
    remainder = cents - sum(allocated.values())
    order = sorted(effective, key=lambda key: (-(quotas[key] - allocated[key]), key))
    for key in order[:remainder]:
        allocated[key] += 1
    return {key: Decimal(value) / 100 for key, value in allocated.items()}


def _annual_object_fot(labour: LabourResultV1, year: int, uncertainty: str,
                       registry: CalculationParameterRegistryV1) -> tuple[Decimal, Decimal]:
    labour_index = _registry(registry, "finance.inflation.labor")
    factor = (Decimal(1) + labour_index) ** (year - 1)
    base = scenario = Decimal(0)
    for role in labour.roles:
        assert role.money is not None
        direct = _d(role.money.annual_direct)
        overhead = _d(role.money.annual_fixed_overhead)
        remaining = role.annual_staffing[year - 1].remaining if year <= len(role.annual_staffing) else role.remaining
        base += Decimal(role.headcount) * (direct + overhead) * factor
        scenario += (Decimal(remaining) * direct + Decimal(role.headcount) * overhead) * factor
    ramp = _registry(registry, f"scenario.{uncertainty.lower()}.ramp.year-{year}") if year <= 5 else Decimal(1)
    staff = labour.operating_staff
    if staff.existing_control_headcount:
        assert staff.control_money is not None
        existing = Decimal(staff.existing_control_headcount) * (
            _d(staff.control_money.annual_direct) + _d(staff.control_money.annual_fixed_overhead)) * factor
        base += existing
        scenario += existing
    if staff.existing_technician_headcount:
        assert staff.technician_money is not None
        existing = Decimal(staff.existing_technician_headcount) * (
            _d(staff.technician_money.annual_direct) + _d(staff.technician_money.annual_fixed_overhead)) * factor
        base += existing
        scenario += existing
    technician_count = staff.technicians_billable if staff.technicians_billable is not None else staff.technicians_required
    if technician_count:
        if staff.technician_contractor_annual_gross is not None:
            scenario += Decimal(technician_count) * _d(staff.technician_contractor_annual_gross) * ramp * factor
        else:
            assert staff.technician_money is not None
            scenario += Decimal(technician_count) * _d(staff.technician_money.annual_direct) * ramp * factor
    if staff.control_additional:
        assert staff.control_money is not None
        scenario += Decimal(staff.control_additional) * _d(staff.control_money.annual_direct) * ramp * factor
    if staff.control_transfer_monthly_supplement_gross is not None:
        scenario += Decimal(staff.control_transferred) * _d(staff.control_transfer_monthly_supplement_gross) * 12 * ramp * factor
    if staff.technician_transfer_monthly_supplement_gross is not None:
        scenario += Decimal(staff.technicians_transferred or 0) * _d(staff.technician_transfer_monthly_supplement_gross) * 12 * ramp * factor
    return base, scenario


def calculate_multiprocess_allocation(
    request: MultiprocessAllocationRequestV1,
    *,
    registry: CalculationParameterRegistryV1 | None = None,
) -> MultiprocessAllocationResultV1:
    """Allocate K17 shared costs and build one order-independent project flow."""

    registry = registry or load_registry()
    if (request.labour_result.versions.registry_version != registry.registry_version
            or request.labour_result.versions.registry_digest != registry.registry_digest):
        raise ValueError("C14 labour result registry binding mismatch")
    for role in request.labour_result.roles:
        for staffing in role.annual_staffing:
            expected = _registry(registry, f"scenario.{request.uncertainty.lower()}.ramp.year-{staffing.year}")
            if _d(staffing.ramp) != expected:
                raise ValueError("C14 labour ramp does not match C18 uncertainty binding")
    configs = sorted(request.configurations, key=lambda item: item.process_id)
    process_ids = [item.process_id for item in configs]
    horizon = len(configs[0].annual_cashflows)
    capital_weights = {item.process_id: _d(item.allocation_basis_direct_capital) for item in configs}
    capital_method = "DIRECT_CAPITAL_LARGEST_REMAINDER" if sum(capital_weights.values(), Decimal(0)) > 0 else "EQUAL_ZERO_DENOMINATOR"
    shared_capex = _d(request.shared_site_capital.capex_cashflow)
    capex_alloc = _allocate_cents(shared_capex, capital_weights)

    allocated_people = {process_id: 0 for process_id in process_ids}
    released_people = {process_id: 0 for process_id in process_ids}
    for item in request.labour_result.allocations:
        allocated_people[item.process_id] += item.allocated_people
    for item in request.labour_result.processes:
        if item.process_id in released_people:
            released_people[item.process_id] += item.released or 0
    fot_weights = {process_id: Decimal(allocated_people[process_id]) for process_id in process_ids}

    process_rows: dict[str, list[ProcessAnnualAllocationV1]] = {process_id: [] for process_id in process_ids}
    project_rows: list[ProjectAnnualLedgerV1] = []
    trace: list[AllocationTraceNodeV1] = []
    shared_by_year = {item.year: item for item in request.shared_annual_costs}
    for config in configs:
        trace.append(AllocationTraceNodeV1(
            node_id=f"allocation.capital.{config.process_id}", operation="ALLOCATE_SITE_CAPITAL",
            input_refs=["shared_site_capital.capex_cashflow", f"configuration.{config.configuration_id}.allocation_basis_direct_capital"],
            output_ref=f"process.{config.process_id}.allocated-shared-capex", value=_money(capex_alloc[config.process_id]),
            unit="RUB", rounding="HALF_EVEN_CENT_LARGEST_REMAINDER",
        ))

    for year in range(1, horizon + 1):
        base_fot, scenario_fot = _annual_object_fot(request.labour_result, year, request.uncertainty, registry)
        base_fot_alloc = _allocate_cents(base_fot.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), fot_weights)
        scenario_fot_alloc = _allocate_cents(scenario_fot.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), fot_weights)
        shared = shared_by_year[year]
        shared_base = _d(shared.baseline_cost)
        shared_scenario = _d(shared.scenario_cost)
        shared_base_alloc = _allocate_cents(shared_base, capital_weights)
        shared_scenario_alloc = _allocate_cents(shared_scenario, capital_weights)
        direct_base = direct_scenario = Decimal(0)
        for config in configs:
            direct = config.annual_cashflows[year - 1]
            db, ds = _d(direct.baseline_cf), _d(direct.scenario_cf)
            direct_base += db
            direct_scenario += ds
            combined_base = db - base_fot_alloc[config.process_id] - shared_base_alloc[config.process_id]
            combined_scenario = ds - scenario_fot_alloc[config.process_id] - shared_scenario_alloc[config.process_id]
            process_rows[config.process_id].append(ProcessAnnualAllocationV1(
                year=year, direct_baseline_cf=_money(db), direct_scenario_cf=_money(ds),
                allocated_baseline_fot=_money(base_fot_alloc[config.process_id]),
                allocated_scenario_fot=_money(scenario_fot_alloc[config.process_id]),
                allocated_shared_baseline_cost=_money(shared_base_alloc[config.process_id]),
                allocated_shared_scenario_cost=_money(shared_scenario_alloc[config.process_id]),
                combined_baseline_cf=_money(combined_base), combined_scenario_cf=_money(combined_scenario),
                differential_cf=_money(combined_scenario - combined_base),
            ))
        combined_base = direct_base - base_fot - shared_base
        combined_scenario = direct_scenario - scenario_fot - shared_scenario
        project_rows.append(ProjectAnnualLedgerV1(
            year=year, process_direct_baseline_cf=_money(direct_base), process_direct_scenario_cf=_money(direct_scenario),
            object_baseline_fot=_money(base_fot), object_scenario_fot=_money(scenario_fot),
            shared_baseline_cost=_money(shared_base), shared_scenario_cost=_money(shared_scenario),
            combined_baseline_cf=_money(combined_base), combined_scenario_cf=_money(combined_scenario),
            differential_cf=_money(combined_scenario - combined_base),
        ))
        for process_id in process_ids:
            trace.extend([
                AllocationTraceNodeV1(node_id=f"allocation.fot.year-{year}.{process_id}", operation="ALLOCATE_OBJECT_FOT",
                    input_refs=[request.labour_result_digest, f"role-allocation.{process_id}"], output_ref=f"process.{process_id}.year-{year}.fot",
                    value=_money(scenario_fot_alloc[process_id]), unit="RUB", rounding="HALF_EVEN_CENT_LARGEST_REMAINDER"),
                AllocationTraceNodeV1(node_id=f"allocation.shared-cost.year-{year}.{process_id}", operation="ALLOCATE_SHARED_COST",
                    input_refs=[shared.provenance_ref, f"allocation.capital.{process_id}"], output_ref=f"process.{process_id}.year-{year}.shared-cost",
                    value=_money(shared_scenario_alloc[process_id]), unit="RUB", rounding="HALF_EVEN_CENT_LARGEST_REMAINDER"),
            ])
        trace.append(AllocationTraceNodeV1(node_id=f"combined.year-{year}", operation="COMBINE_CASHFLOW",
            input_refs=[f"process.{process_id}.year-{year}" for process_id in process_ids] + [request.labour_result_digest, shared.provenance_ref],
            output_ref=f"project.year-{year}.differential-cf", value=_money(combined_scenario - combined_base), unit="RUB"))

    process_results = [ProcessAllocationResultV1(
        configuration_id=item.configuration_id, process_id=item.process_id, model_id=item.model_id,
        position_id=item.position_id, acquisition=item.acquisition, source_run_id=item.source_run_id,
        source_result_digest=item.source_result_digest, capital_allocation_basis=_money(_d(item.allocation_basis_direct_capital)),
        capital_allocation_method=capital_method, allocated_shared_capex_cashflow=_money(capex_alloc[item.process_id]),
        combined_capex_cashflow=_money(_d(item.direct_capex_cashflow) + capex_alloc[item.process_id]),
        allocated_role_people=allocated_people[item.process_id], released_role_people=released_people[item.process_id],
        annual_ledgers=process_rows[item.process_id],
    ) for item in configs]
    role_rows = [RoleConservationV1(
        role_id=role.role_id, headcount=role.headcount, allocated_people=role.allocated_people,
        unallocated_people=role.unallocated_people, transferred=role.transferred,
        released=role.released, remaining=role.remaining,
    ) for role in sorted(request.labour_result.roles, key=lambda item: item.role_id)]

    project_capex = sum((_d(item.direct_capex_cashflow) for item in configs), Decimal(0)) + shared_capex
    initial_scenario = -project_capex
    base_flows = [Decimal(0), *[_d(item.combined_baseline_cf) for item in project_rows]]
    scenario_flows = [initial_scenario, *[_d(item.combined_scenario_cf) for item in project_rows]]
    differential = [scenario_flows[index] - base_flows[index] for index in range(len(base_flows))]
    discount = _d(request.discount_rate.value)
    npv_base_value, npv_scenario_value = npv(base_flows, discount), npv(scenario_flows, discount)
    npv_project_value = npv_scenario_value - npv_base_value
    simple = payback(differential)
    discounted = payback(differential, discount)
    metric_rub = lambda value: AllocationMetricV1(status="COMPLETE", value=_money(value), unit="RUB")
    metric_year = lambda value: AllocationMetricV1(status="NOT_REACHED" if value is None else "COMPLETE", value=None if value is None else _plain(value), unit="YEAR")
    for name, value, unit in (("npv-base", npv_base_value, "RUB"), ("npv-scenario", npv_scenario_value, "RUB"),
                              ("npv-project", npv_project_value, "RUB"), ("simple-payback", simple, "YEAR"),
                              ("discounted-payback", discounted, "YEAR")):
        trace.append(AllocationTraceNodeV1(node_id=f"metric.{name}", operation="PROJECT_METRIC",
            input_refs=["project.initial-scenario-cf", *[f"project.year-{year}.differential-cf" for year in range(1, horizon + 1)]],
            output_ref=name, value=None if value is None else _plain(value), unit=unit))

    replay = AllocationReplayV1(
        canonical_input_digest=_digest(request), labour_result_digest=request.labour_result_digest,
        source_result_digests=sorted(item.source_result_digest for item in configs), trace_content_digest=ZERO_DIGEST,
    )
    result = MultiprocessAllocationResultV1(
        run_id=request.run_id, project_id=request.project_id, tenant_id=request.tenant_id,
        input_revision=request.input_revision, object_id=request.object_id, cohort_id=request.cohort_id,
        horizon_years=horizon, processes=process_results, role_conservation=role_rows,
        unallocated_role_people=sum(item.unallocated_people for item in role_rows),
        total_released_people=request.labour_result.total_released,
        control_required_once=request.labour_result.operating_staff.control_required,
        technicians_required_once=request.labour_result.operating_staff.technicians_required,
        shared_capex_cashflow=_money(shared_capex), project_capex_cashflow=_money(project_capex),
        initial_scenario_cf=_money(initial_scenario), annual_ledgers=project_rows,
        npv_base=metric_rub(npv_base_value), npv_scenario=metric_rub(npv_scenario_value), npv_project=metric_rub(npv_project_value),
        simple_payback=metric_year(simple), discounted_payback=metric_year(discounted), trace=trace,
        versions=AllocationVersionBindingsV1(registry_version=registry.registry_version, registry_digest=registry.registry_digest),
        replay=replay,
    )
    payload = result.model_dump(mode="json")
    payload["replay"]["trace_content_digest"] = None
    result.replay.trace_content_digest = _digest(payload)
    return result


__all__ = [
    "MultiprocessAllocationRequestV1", "MultiprocessAllocationResultV1",
    "SelectedConfigurationV1", "calculate_multiprocess_allocation",
]
