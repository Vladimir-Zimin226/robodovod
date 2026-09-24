"""Production C13-C21 orchestration over an immutable C11 snapshot.

The module deliberately accepts only explicit user commercial inputs plus the
server-owned capacity run and activated catalog snapshot.  It never imports a
fixture bundle and never promotes organizer prices or demo assumptions to a
vendor quote, passport fact, or procurement-ready assertion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from calculation.economics.allocation import (
    DirectAnnualCashflowV1,
    DiscountRateV1,
    MultiprocessAllocationRequestV1,
    MultiprocessAllocationResultV1,
    SelectedConfigurationV1,
    SharedAnnualCostV1,
    SharedSiteCapitalV1,
)
from calculation.economics.cashflow import (
    ExcludedAdditionalIncomeV1,
    FinancialAnalysisRequestV1,
    FinancialResultV1,
)
from calculation.economics.purchase import (
    IncludedBatteryLifecycleV1,
    InitialBatteryPolicyV1,
    LabourOpexProjectionV1,
    OperatingBasisV1,
    PowerEnergyPathV1,
    PurchaseCostLedgerV1,
    PurchaseLedgerRequestV1,
    SourcedValueV1,
)
from calculation.economics.raas import RaasAnalysisRequestV1, RaasFinancialResultV1
from calculation.economics.sensitivity import (
    CapacitySensitivityBindingV1,
    SensitivityOverrideV1,
    SensitivityRequestV1,
    SensitivityResultV1,
    SensitivityVariantInputV1,
)
from calculation.labour import (
    CapacityLabourProjectionV1,
    LabourAnalysisRequestV1,
    LabourResultV1,
    ManualProductivityInputV1,
    ProcessLabourInputV1,
    SalarySourceBindingV1,
)
from calculation.ranking import (
    DATA_FIELDS,
    CohortAllocationBindingV1,
    DataFieldStatusV1,
    IntegrationCoverageV1,
    PenaltyContextV1,
    RankingCandidateV2,
    RankingRequestV2,
    RankingResultV2,
    TrlFactV1,
)
from calculation.service import (
    analyze_capacity,
    analyze_financials,
    analyze_multiprocess_allocation,
    analyze_purchase_costs,
    analyze_raas_financials,
    analyze_ranking,
    analyze_role_labour,
    analyze_sensitivity,
)
from calculation_contracts import (
    CapacityAnalysisRequest,
    CapacityAnalysisResponse,
    DecimalString,
    KnownQuantity,
    MissingQuantity,
    QuantityKind,
    ResultQuantity,
    RoleEntry,
    RolePool,
    StableId,
    StrictContractModel,
    semantic_digest,
)
from catalog_repository import CatalogPositionDTO, CatalogSnapshotDTO
from economics_runtime_migration import EconomicsV2ExecutionV1
from procurement.contracts import (
    CommercialCostLineV1,
    CommercialMoneyV1,
    CommercialScopeV1,
    CommercialSourceV1,
    FixedTotalBasisV1,
    PerRobotBasisV1,
    ProcurementReportRequestV1,
    PurchaseTermsV1,
    RaasTermsV1,
    ServiceResponsibilityV1,
)
from procurement.resolver import catalog_commercial_money, resolve_procurement_report
from pydantic import Field, model_validator
from scenario_spec_v2 import (
    ScenarioAssumptionV2,
    ScenarioBatchV2,
    ScenarioOperatingWindowV2,
    ScenarioRouteBindingV2,
    ScenarioZoneV2,
    build_scenario_spec_v2,
)

ORCHESTRATOR_VERSION = "production-economics-orchestrator-v2"
RULES_VERSION = "calculation-rules-c13-c21-v1"
UNCERTAINTIES = ("PESSIMISTIC", "BASE", "OPTIMISTIC")
ACQUISITIONS = ("PURCHASE", "RAAS")


class EconomicsExplicitInputsV1(StrictContractModel):
    """Inputs that cannot be inferred safely from C11 or the catalog."""

    schema_version: Literal["economics-explicit-inputs-v1"] = (
        "economics-explicit-inputs-v1"
    )
    input_revision: StableId
    evaluation_date: date
    horizon_years: Annotated[int, Field(ge=5, le=15)]
    discount_rate: DecimalString
    primary_role_id: StableId | None = None
    manual_units_per_shift: DecimalString | None = None
    role_salaries_confirmed_as_monthly_gross: bool
    control_headcount: Annotated[int, Field(ge=0)]
    control_monthly_gross: DecimalString
    technician_headcount: Annotated[int, Field(ge=0)]
    technician_monthly_gross: DecimalString
    organizer_price_currency_rub_confirmed: bool
    implementation_cost_total_gross: DecimalString
    annual_service_per_robot_gross: DecimalString
    warranty_years: Annotated[int, Field(ge=0, le=15)]
    average_power_w: DecimalString
    initial_battery_in_robot_price_confirmed: bool
    battery_replacements_in_service_confirmed: bool
    shared_site_capital_gross: DecimalString
    shared_annual_cost_gross: DecimalString
    raas_monthly_per_robot_gross: DecimalString
    raas_contract_months: Annotated[int, Field(gt=0, le=180)]
    raas_infrastructure_owner: Literal["CUSTOMER", "VENDOR"]
    raas_vendor_scope_confirmed: bool
    start_seconds_from_midnight: Annotated[int, Field(ge=0, lt=86400)] = 0
    timezone: Annotated[str, Field(min_length=1, max_length=64)] = "Europe/Moscow"

    @model_validator(mode="after")
    def validate_explicit_inputs(self) -> EconomicsExplicitInputsV1:
        non_negative = (
            "control_monthly_gross",
            "technician_monthly_gross",
            "implementation_cost_total_gross",
            "annual_service_per_robot_gross",
            "shared_site_capital_gross",
            "shared_annual_cost_gross",
            "raas_monthly_per_robot_gross",
        )
        if any(Decimal(getattr(self, name)) < 0 for name in non_negative):
            raise ValueError("commercial and labour money inputs cannot be negative")
        if not Decimal(0) <= Decimal(self.discount_rate) <= Decimal(1):
            raise ValueError("discount_rate must be within 0..1")
        if Decimal(self.average_power_w) <= 0:
            raise ValueError("average_power_w must be positive")
        if (
            self.manual_units_per_shift is not None
            and Decimal(self.manual_units_per_shift) <= 0
        ):
            raise ValueError("manual_units_per_shift must be positive")
        required_confirmations = (
            self.role_salaries_confirmed_as_monthly_gross,
            self.organizer_price_currency_rub_confirmed,
            self.initial_battery_in_robot_price_confirmed,
            self.battery_replacements_in_service_confirmed,
            self.raas_vendor_scope_confirmed,
        )
        if not all(required_confirmations):
            raise ValueError("all commercial basis confirmations are required")
        if self.raas_contract_months < self.horizon_years * 12:
            raise ValueError(
                "RaaS contract must explicitly cover the calculation horizon"
            )
        return self


@dataclass(frozen=True)
class EconomicsExecutionContextV1:
    run_id: str
    project_id: str
    tenant_id: str
    capacity_request: CapacityAnalysisRequest
    capacity_response: CapacityAnalysisResponse
    constraint_report: dict[str, Any]
    executability: dict[str, Any]


@dataclass(frozen=True)
class ScenarioArtifacts:
    acquisition: str
    uncertainty: str
    procurement: Any
    labour: LabourResultV1
    purchase: PurchaseCostLedgerV1
    purchase_financial: FinancialResultV1
    financial: FinancialResultV1 | RaasFinancialResultV1
    allocation_request: MultiprocessAllocationRequestV1
    allocation: MultiprocessAllocationResultV1


def _position(
    snapshot: CatalogSnapshotDTO, request: CapacityAnalysisRequest
) -> CatalogPositionDTO:
    if snapshot.version.status != "PUBLISHED":
        raise ValueError("economics requires an immutable published catalog snapshot")
    match = next(
        (item for item in snapshot.positions if item.id == request.position_id), None
    )
    if match is None or match.model.id != request.model_id:
        raise ValueError(
            "capacity model/position is absent from the economics catalog snapshot"
        )
    return match


def _money(value: str) -> str:
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def _user_money(
    value: str,
    *,
    source_id: str,
    request: CapacityAnalysisRequest,
    boundary: str,
) -> CommercialMoneyV1:
    amount = Decimal(value)
    return CommercialMoneyV1(
        raw_amount=_money(value),
        currency="RUB",
        tax_basis="CASH_GROSS_RUB",
        source=CommercialSourceV1(kind="USER", source_id=source_id),
        scope=CommercialScopeV1(
            model_id=request.model_id,
            position_id=request.position_id,
            boundary=boundary,
        ),
        zero_semantics="ZERO_PRICE_CONFIRMED" if amount == 0 else None,
    )


def _sourced(value: str, unit: str, provenance: str) -> SourcedValueV1:
    return SourcedValueV1(
        value=value, unit=unit, source="USER", provenance_ref=provenance
    )


def _known(
    name: str, value: str, unit: str, kind: str, provenance: str
) -> KnownQuantity:
    return KnownQuantity(
        name=name,
        raw_value=value,
        raw_unit=unit,
        normalized_value=value,
        unit=unit,
        quantity_kind=kind,
        provenance_ref=provenance,
    )


def _role_with_salary(role: RoleEntry, value: str | None = None) -> RoleEntry:
    if value is None:
        if isinstance(role.monthly_gross_salary, MissingQuantity):
            raise ValueError(f"monthly gross salary is missing for role {role.role_id}")
        return role
    raw = role.model_dump(mode="json")
    raw["monthly_gross_salary"] = _known(
        "monthly_gross_salary",
        value,
        "RUB/person/month",
        "MONEY",
        f"input.economics.salary.{role.role_id}",
    ).model_dump(mode="json")
    raw["zero_cost_marker"] = "ZERO_COST_ROLE" if Decimal(value) == 0 else None
    return RoleEntry.model_validate(raw)


def _site_role(
    code: str, role_id: str, headcount: int, salary: str, object_kind: str
) -> RoleEntry:
    return RoleEntry(
        role_id=role_id,
        object_scope="SITE",
        role_code=code,
        headcount=_known(
            "role_headcount",
            str(headcount),
            "person",
            "COUNT",
            f"input.economics.{role_id}.headcount",
        ),
        monthly_gross_salary=_known(
            "monthly_gross_salary",
            salary,
            "RUB/person/month",
            "MONEY",
            f"input.economics.{role_id}.salary",
        ),
        zero_cost_marker="ZERO_COST_ROLE" if Decimal(salary) == 0 else None,
        process_ids=[],
    )


def _role_pool(
    request: CapacityAnalysisRequest, inputs: EconomicsExplicitInputsV1
) -> RolePool:
    if request.role_pool is None:
        raise ValueError("C13-C21 requires the immutable C11 role pool")
    roles = [_role_with_salary(item) for item in request.role_pool.roles]
    roles = [
        item
        for item in roles
        if item.role_code not in {"control_operator", "tech_support"}
    ]
    roles.extend(
        [
            _site_role(
                "control_operator",
                "role.site.control",
                inputs.control_headcount,
                inputs.control_monthly_gross,
                str(request.process.object_kind),
            ),
            _site_role(
                "tech_support",
                "role.site.technical",
                inputs.technician_headcount,
                inputs.technician_monthly_gross,
                str(request.process.object_kind),
            ),
        ]
    )
    return RolePool(
        pool_id=request.role_pool.pool_id,
        object_kind=request.role_pool.object_kind,
        roles=roles,
    )


def _primary_role(
    request: CapacityAnalysisRequest, inputs: EconomicsExplicitInputsV1
) -> str | None:
    refs = request.process.role_refs
    if not refs:
        return None
    if inputs.primary_role_id is not None:
        if inputs.primary_role_id not in refs:
            raise ValueError("primary_role_id is outside the C11 process role_refs")
        return inputs.primary_role_id
    if len(refs) != 1:
        raise ValueError(
            "primary_role_id is required when a process has multiple roles"
        )
    return refs[0]


def _manual_productivity(
    request: CapacityAnalysisRequest, inputs: EconomicsExplicitInputsV1
) -> ManualProductivityInputV1 | None:
    if request.process.scope == "CLEANING_AREA":
        return None
    if inputs.manual_units_per_shift is None:
        raise ValueError("manual_units_per_shift is required for this process")
    unit = f"{str(request.process.quantity_kind).lower()}/shift"
    return ManualProductivityInputV1(
        value=inputs.manual_units_per_shift,
        unit=unit,
        source="USER",
        provenance_ref="input.economics.manual-productivity",
    )


def _labour(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    uncertainty: str,
    *,
    capacity_response: CapacityAnalysisResponse | None = None,
    role_pool: RolePool | None = None,
    run_suffix: str = "",
) -> LabourResultV1:
    request = context.capacity_request
    response = capacity_response or context.capacity_response
    if response.capacity.value is None:
        raise ValueError("economics requires an executable C11 capacity result")
    pool = role_pool or _role_pool(request, inputs)
    capacity_digest = semantic_digest(response.capacity)
    projection = CapacityLabourProjectionV1(
        process_id=request.process.process_id,
        input_revision=request.input_revision,
        capacity_run_id=response.run_id,
        capacity_status=response.capacity.status,
        selected_fleet=response.capacity.value.selected_fleet,
        coverage=response.capacity.value.coverage.value,
        capacity_result_digest=capacity_digest,
    )
    labour_request = LabourAnalysisRequestV1(
        run_id=f"{context.run_id}.labour.{uncertainty.lower()}{run_suffix}",
        project_id=context.project_id,
        tenant_id=context.tenant_id,
        input_revision=request.input_revision,
        object_id=f"object.{context.project_id}",
        object_kind=request.process.object_kind,
        uncertainty=uncertainty,
        role_pool=pool,
        processes=[
            ProcessLabourInputV1(
                process=request.process,
                capacity=projection,
                role_id=_primary_role(request, inputs),
                manual_units_per_shift=_manual_productivity(request, inputs),
            )
        ],
        salary_sources=[
            SalarySourceBindingV1(
                role_id=item.role_id,
                provenance_ref=item.monthly_gross_salary.provenance_ref,
                source="USER",
            )
            for item in pool.roles
            if isinstance(item.monthly_gross_salary, KnownQuantity)
        ],
    )
    result = analyze_role_labour(labour_request)
    if result.finance_status != "COMPLETE":
        raise ValueError("C14 finance is incomplete: " + ", ".join(result.issues))
    return result


def _purchase_report(
    request: CapacityAnalysisRequest,
    inputs: EconomicsExplicitInputsV1,
    snapshot: CatalogSnapshotDTO,
    *,
    primary_price_override: str | None = None,
) -> Any:
    position = _position(snapshot, request)
    catalog_money = catalog_commercial_money(position)
    if catalog_money is None:
        raise ValueError("selected catalog position has no usable organizer price")
    primary_money = (
        catalog_money
        if primary_price_override is None
        else _user_money(
            primary_price_override,
            source_id="input.economics.sensitivity.equipment-price",
            request=request,
            boundary="BARE_EQUIPMENT",
        )
    )
    implementation = _user_money(
        inputs.implementation_cost_total_gross,
        source_id="input.economics.implementation-cost",
        request=request,
        boundary="TURNKEY_SOLUTION",
    )
    service = _user_money(
        inputs.annual_service_per_robot_gross,
        source_id="input.economics.annual-service",
        request=request,
        boundary="SERVICE_TARIFF",
    )
    terms = PurchaseTermsV1(
        primary_price=primary_money,
        cost_lines=[
            CommercialCostLineV1(
                line_id="implementation",
                category="INTEGRATION",
                timing="CAPITAL_ONCE",
                basis=FixedTotalBasisV1(money=implementation),
                excluded_by_scenario=Decimal(inputs.implementation_cost_total_gross)
                == 0,
            ),
            CommercialCostLineV1(
                line_id="annual-service",
                category="SERVICE",
                timing="ANNUAL",
                basis=PerRobotBasisV1(money=service),
                excluded_by_scenario=Decimal(inputs.annual_service_per_robot_gross)
                == 0,
            ),
        ],
        responsibilities=[
            ServiceResponsibilityV1(area=area, responsible_party="UNKNOWN")
            for area in (
                "HARDWARE",
                "BATTERY",
                "CHARGING",
                "MAINTENANCE",
                "SOFTWARE",
                "INTEGRATION",
                "INFRASTRUCTURE",
            )
        ],
    )
    currency_assumption = None
    if primary_money.currency == "UNKNOWN":
        currency_assumption = {
            "currency": "RUB",
            "provenance_id": "input.economics.catalog-currency-rub",
            "rationale": "User confirmed RUB only for this preliminary scenario",
            "applies_to_source_id": primary_money.source.source_id,
            "confirmation_state": "USER_CONFIRMED",
        }
    return resolve_procurement_report(
        ProcurementReportRequestV1(
            model_id=request.model_id,
            position_id=request.position_id,
            acquisition="PURCHASE",
            evaluation_date=inputs.evaluation_date,
            terms=[terms],
            currency_assumption=currency_assumption,
        ),
        snapshot,
    )


def _raas_report(
    request: CapacityAnalysisRequest,
    inputs: EconomicsExplicitInputsV1,
    snapshot: CatalogSnapshotDTO,
) -> Any:
    tariff = _user_money(
        inputs.raas_monthly_per_robot_gross,
        source_id="input.economics.raas-monthly",
        request=request,
        boundary="SERVICE_TARIFF",
    )
    responsibilities = [
        ServiceResponsibilityV1(area=area, responsible_party="VENDOR")
        for area in (
            "HARDWARE",
            "BATTERY",
            "CHARGING",
            "MAINTENANCE",
            "SOFTWARE",
            "INTEGRATION",
        )
    ]
    responsibilities.append(
        ServiceResponsibilityV1(
            area="INFRASTRUCTURE",
            responsible_party=inputs.raas_infrastructure_owner,
        )
    )
    terms = RaasTermsV1(
        tariff_basis=PerRobotBasisV1(money=tariff),
        billing_basis="PER_ROBOT_MONTH",
        contract_months=inputs.raas_contract_months,
        renewal="SAME_TERMS_TO_HORIZON",
        deployment_mode="ALL_FLEET",
        responsibilities=responsibilities,
    )
    return resolve_procurement_report(
        ProcurementReportRequestV1(
            model_id=request.model_id,
            position_id=request.position_id,
            acquisition="RAAS",
            evaluation_date=inputs.evaluation_date,
            terms=[terms],
        ),
        snapshot,
    )


def _trace_value(response: CapacityAnalysisResponse, name: str) -> KnownQuantity:
    value = next(
        (item for item in response.trace.inputs if str(item.name) == name), None
    )
    if not isinstance(value, KnownQuantity):
        raise ValueError(f"C11 trace is missing required {name}")
    return value


def _equipment_class(position: CatalogPositionDTO) -> str:
    profile = position.model.capacity_runtime.calculation_profile
    if profile == "CLEANING_AREA_V1":
        return "CLEANER"
    if profile == "PALLETIZING_CELL_V1":
        return "FIXED_CELL"
    return "AMR"


def _purchase_ledger(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    position: CatalogPositionDTO,
    procurement: Any,
    labour: LabourResultV1,
    uncertainty: str,
    *,
    response: CapacityAnalysisResponse | None = None,
    run_suffix: str = "",
) -> PurchaseCostLedgerV1:
    response = response or context.capacity_response
    request = context.capacity_request
    assert response.capacity.value is not None and request.process.schedule is not None
    availability = _trace_value(response, "availability")
    schedule = request.process.schedule
    hours = Decimal(schedule.shifts_per_day.normalized_value) * Decimal(
        schedule.shift_hours.normalized_value
    )
    staff = labour.operating_staff
    ledger_request = PurchaseLedgerRequestV1(
        run_id=f"{context.run_id}.purchase.{uncertainty.lower()}{run_suffix}",
        project_id=context.project_id,
        tenant_id=context.tenant_id,
        input_revision=request.input_revision,
        fleet_count=response.capacity.value.selected_fleet,
        uncertainty=uncertainty,
        horizon_years=inputs.horizon_years,
        equipment_class=_equipment_class(position),
        procurement=procurement,
        operating=OperatingBasisV1(
            operating_hours_per_day=_sourced(
                format(hours, "f"), "h/day", "capacity.schedule.operating-hours"
            ),
            days_per_year=_sourced(
                schedule.days_per_year.normalized_value,
                "day/year",
                schedule.days_per_year.provenance_ref,
            ),
            availability=_sourced(
                availability.normalized_value, "1", availability.provenance_ref
            ),
            capacity_result_digest=semantic_digest(response.capacity),
        ),
        labour_trace_digest=labour.replay.trace_content_digest,
        labour_opex=LabourOpexProjectionV1(
            technicians_required=staff.technicians_required,
            technician_annual_direct=None
            if staff.technician_money is None
            else staff.technician_money.annual_direct,
            additional_control_required=staff.control_additional,
            control_annual_direct=None
            if staff.control_money is None
            else staff.control_money.annual_direct,
            source_result_digest=labour.replay.trace_content_digest,
        ),
        warranty_years=_sourced(
            str(inputs.warranty_years), "year", "input.economics.warranty-years"
        ),
        energy_path=PowerEnergyPathV1(
            average_power_w=_sourced(
                inputs.average_power_w, "W", "input.economics.average-power-w"
            ),
        ),
        initial_battery=InitialBatteryPolicyV1(
            mode="INCLUDED_IN_ROBOT_PRICE",
            provenance_ref="input.economics.initial-battery-included",
        ),
        battery_lifecycle=IncludedBatteryLifecycleV1(
            provenance_ref="input.economics.battery-replacements-in-service",
        ),
    )
    result = analyze_purchase_costs(ledger_request)
    if result.status != "COMPLETE":
        raise ValueError(
            "C15 purchase ledger is incomplete: " + ", ".join(result.issues)
        )
    return result


def _purchase_financial(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    purchase: PurchaseCostLedgerV1,
    labour: LabourResultV1,
    uncertainty: str,
    *,
    run_suffix: str = "",
) -> tuple[FinancialAnalysisRequestV1, FinancialResultV1]:
    request = FinancialAnalysisRequestV1(
        run_id=f"{context.run_id}.finance.{uncertainty.lower()}{run_suffix}",
        project_id=context.project_id,
        tenant_id=context.tenant_id,
        input_revision=context.capacity_request.input_revision,
        purchase_ledger=purchase,
        labour_result=labour,
        purchase_ledger_digest=semantic_digest(purchase),
        labour_result_digest=semantic_digest(labour),
        discount_rate=_sourced(
            inputs.discount_rate, "1", "input.economics.discount-rate"
        ),
        tax_mode="NONE",
        additional_income=ExcludedAdditionalIncomeV1(
            provenance_ref="input.economics.additional-income-excluded"
        ),
    )
    result = analyze_financials(request)
    if result.status != "COMPLETE":
        raise ValueError(
            "C16 financial result is incomplete: " + ", ".join(result.issues)
        )
    return request, result


def _allocation(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    labour: LabourResultV1,
    purchase: PurchaseCostLedgerV1,
    financial: FinancialResultV1 | RaasFinancialResultV1,
    acquisition: str,
    uncertainty: str,
    position: CatalogPositionDTO,
    *,
    run_suffix: str = "",
    allocation_run_id: str | None = None,
) -> tuple[MultiprocessAllocationRequestV1, MultiprocessAllocationResultV1]:
    request = context.capacity_request
    if acquisition == "PURCHASE":
        direct_capex = (
            purchase.capex_cashflow
            if isinstance(financial, FinancialResultV1)
            else None
        )
        annual = [
            DirectAnnualCashflowV1(
                year=item.year,
                baseline_cf="0.00",
                scenario_cf=_money(
                    str(
                        -Decimal(purchase.annual_ledgers[item.year - 1].operating_total)
                    )
                ),
            )
            for item in financial.annual_ledgers
        ]
        source_version = "financial-result-v1"
        allocation_basis = purchase.equipment_capex
    else:
        assert isinstance(financial, RaasFinancialResultV1)
        direct_capex = financial.capex_infrastructure_gross
        annual = [
            DirectAnnualCashflowV1(
                year=item.year,
                baseline_cf="0.00",
                scenario_cf=_money(
                    str(-(Decimal(item.customer_opex) + Decimal(item.raas_payment)))
                ),
            )
            for item in financial.annual_ledgers
        ]
        source_version = "raas-financial-result-v1"
        allocation_basis = financial.capex_infrastructure_amortizable
    if direct_capex is None or allocation_basis is None:
        raise ValueError(f"C18 {acquisition} direct projection is incomplete")
    run_id = (
        allocation_run_id
        or f"{context.run_id}.allocation.{acquisition.lower()}.{uncertainty.lower()}{run_suffix}"
    )
    config = SelectedConfigurationV1(
        configuration_id=f"configuration.{acquisition.lower()}.{request.process.process_id}",
        process_id=request.process.process_id,
        model_id=request.model_id,
        position_id=request.position_id,
        acquisition=acquisition,
        source_run_id=financial.run_id,
        source_result_version=source_version,
        source_result_digest=semantic_digest(financial),
        cashflow_basis="PRIMARY_PRETAX",
        direct_capex_cashflow=direct_capex,
        allocation_basis_direct_capital=allocation_basis,
        annual_cashflows=annual,
    )
    allocation_request = MultiprocessAllocationRequestV1(
        run_id=run_id,
        project_id=context.project_id,
        tenant_id=context.tenant_id,
        input_revision=request.input_revision,
        object_id=f"object.{context.project_id}",
        cohort_id=f"cohort.{context.run_id}.{acquisition.lower()}",
        uncertainty=uncertainty,
        configurations=[config],
        labour_result=labour,
        labour_result_digest=semantic_digest(labour),
        shared_site_capital=SharedSiteCapitalV1(
            capex_gross=_money(inputs.shared_site_capital_gross),
            capex_amortizable=_money(inputs.shared_site_capital_gross),
            capex_cashflow=_money(inputs.shared_site_capital_gross),
            source="USER",
            provenance_ref="input.economics.shared-site-capital",
        ),
        shared_annual_costs=[
            SharedAnnualCostV1(
                year=year,
                baseline_cost="0.00",
                scenario_cost=_money(inputs.shared_annual_cost_gross),
                source="USER",
                provenance_ref="input.economics.shared-annual-cost",
            )
            for year in range(1, inputs.horizon_years + 1)
        ],
        discount_rate=DiscountRateV1(
            value=inputs.discount_rate,
            source="USER",
            provenance_ref="input.economics.discount-rate",
        ),
    )
    return allocation_request, analyze_multiprocess_allocation(allocation_request)


def _scenario_artifacts(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    snapshot: CatalogSnapshotDTO,
    acquisition: str,
    uncertainty: str,
    *,
    primary_price_override: str | None = None,
    role_pool: RolePool | None = None,
    allocation_run_id: str | None = None,
) -> ScenarioArtifacts:
    request = context.capacity_request
    position = _position(snapshot, request)
    labour = _labour(context, inputs, uncertainty, role_pool=role_pool)
    purchase_procurement = _purchase_report(
        request,
        inputs,
        snapshot,
        primary_price_override=primary_price_override,
    )
    purchase = _purchase_ledger(
        context, inputs, position, purchase_procurement, labour, uncertainty
    )
    comparator_request, purchase_financial = _purchase_financial(
        context, inputs, purchase, labour, uncertainty
    )
    if acquisition == "PURCHASE":
        procurement = purchase_procurement
        financial: FinancialResultV1 | RaasFinancialResultV1 = purchase_financial
    else:
        procurement = _raas_report(request, inputs, snapshot)
        raas_request = RaasAnalysisRequestV1(
            run_id=f"{context.run_id}.raas.{uncertainty.lower()}",
            project_id=context.project_id,
            tenant_id=context.tenant_id,
            input_revision=request.input_revision,
            uncertainty=uncertainty,
            procurement=procurement,
            purchase_comparator_request=comparator_request,
            purchase_comparator_result=purchase_financial,
            comparator_request_digest=semantic_digest(comparator_request),
            comparator_result_digest=semantic_digest(purchase_financial),
        )
        financial = analyze_raas_financials(raas_request)
        if financial.status != "COMPLETE":
            raise ValueError(
                "C17 RaaS result is incomplete: " + ", ".join(financial.issues)
            )
    allocation_request, allocation = _allocation(
        context,
        inputs,
        labour,
        purchase,
        financial,
        acquisition,
        uncertainty,
        position,
        allocation_run_id=allocation_run_id,
    )
    return ScenarioArtifacts(
        acquisition,
        uncertainty,
        procurement,
        labour,
        purchase,
        purchase_financial,
        financial,
        allocation_request,
        allocation,
    )


def _quantity_kind(value: str) -> str:
    return {"KILOGRAM": "KG", "SQUARE_METER": "M2"}.get(value, value)


def _ranking(
    context: EconomicsExecutionContextV1,
    position: CatalogPositionDTO,
    base: ScenarioArtifacts,
) -> RankingResultV2:
    request = context.capacity_request
    allocation_digest = semantic_digest(base.allocation)
    candidate_id = f"candidate.{request.position_id}"
    fields = [
        DataFieldStatusV1(
            field_id=field_id,
            importance=importance,
            status="MISSING",
            matching_safe=False,
            provenance_ref=None,
        )
        for field_id, importance in DATA_FIELDS.items()
    ]
    ranking_request = RankingRequestV2(
        run_id=f"{context.run_id}.ranking",
        project_id=context.project_id,
        tenant_id=context.tenant_id,
        input_revision=request.input_revision,
        process_id=request.process.process_id,
        cohort=CohortAllocationBindingV1(
            cohort_id=base.allocation.cohort_id,
            allocation_run_id=base.allocation.run_id,
            allocation_result_digest=allocation_digest,
            anchor_configuration_id=base.allocation.processes[0].configuration_id,
        ),
        candidates=[
            RankingCandidateV2(
                candidate_id=candidate_id,
                configuration_id=base.allocation.processes[0].configuration_id,
                model_id=request.model_id,
                position_id=request.position_id,
                constraint_report=context.constraint_report,
                constraint_report_digest=semantic_digest(context.constraint_report),
                executability=context.executability,
                executability_digest=semantic_digest(context.executability),
                trl=TrlFactV1(status="UNKNOWN", value=None, matching_safe=False),
                integrations=IntegrationCoverageV1(
                    required_ids=[],
                    supported_matching_safe_ids=[],
                    unknown_ids=[],
                    provenance_refs=[],
                ),
                data_fields=fields,
                penalty_context=PenaltyContextV1(
                    equipment_class=_equipment_class(position),
                    quantity_kind=_quantity_kind(str(request.process.quantity_kind)),
                    demand_per_day=request.process.demand.normalized_value,
                    demand_provenance_ref=request.process.demand.provenance_ref,
                ),
                finance_status="COMPLETE",
                npv_project=base.allocation.npv_project.value,
                allocation_result_digest=allocation_digest,
            )
        ],
    )
    return analyze_ranking(ranking_request)


def _capacity_binding(
    response: CapacityAnalysisResponse, request: CapacityAnalysisRequest
) -> CapacitySensitivityBindingV1:
    assert response.capacity.value is not None
    return CapacitySensitivityBindingV1(
        process_id=request.process.process_id,
        result_version=response.schema_version,
        result_digest=semantic_digest(response),
        selected_fleet=response.capacity.value.selected_fleet,
        demand_value=request.process.demand.normalized_value,
        demand_unit=str(request.process.demand.unit),
        provenance_ref=request.process.demand.provenance_ref,
    )


def _sensitivity(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    snapshot: CatalogSnapshotDTO,
    base: ScenarioArtifacts,
    ranking: RankingResultV2,
) -> SensitivityResultV1:
    request = context.capacity_request
    binding = _capacity_binding(context.capacity_response, request)
    role_id = _primary_role(request, inputs)
    role = next((item for item in base.labour.roles if item.role_id == role_id), None)
    if role is None or role.money is None:
        raise ValueError("C20 salary sensitivity requires complete primary role salary")
    base_price = base.procurement.money.cash_gross_rub
    assert base_price is not None
    bases = {
        "EQUIPMENT_PRICE": (base_price, "RUB/robot", request.position_id),
        "OPERATION_VOLUME": (
            request.process.demand.normalized_value,
            "unit/day",
            request.process.process_id,
        ),
        "ROLE_SALARY": (role.money.monthly_gross, "RUB/person/month", role.role_id),
    }
    variants: list[SensitivityVariantInputV1] = []
    for parameter in ("EQUIPMENT_PRICE", "OPERATION_VOLUME", "ROLE_SALARY"):
        base_value, unit, scope = bases[parameter]
        for direction, delta in (
            ("LOWER", Decimal("-0.10")),
            ("UPPER", Decimal("0.10")),
        ):
            variant_value = _money(str(Decimal(base_value) * (Decimal(1) + delta)))
            override = SensitivityOverrideV1(
                parameter_id=parameter,
                direction=direction,
                delta_fraction=format(delta, "f"),
                scope_id=scope,
                base_value=base_value,
                variant_value=variant_value,
                unit=unit,
                provenance_ref=f"input.economics.sensitivity.{parameter.lower()}.{direction.lower()}",
            )
            variant_id = f"variant.{parameter.lower()}.{direction.lower()}"
            derived_run_id = (
                f"{context.run_id}.sensitivity.{parameter.lower()}.{direction.lower()}"
            )
            variant_context = context
            variant_pool = None
            primary_price = None
            engines: list[str]
            if parameter == "EQUIPMENT_PRICE":
                primary_price = variant_value
                engines = [
                    "purchase-cost-ledger-v1",
                    "full-cashflows-reconciliation-v2",
                    "multiprocess-allocation-v1",
                ]
            elif parameter == "ROLE_SALARY":
                pool = _role_pool(request, inputs)
                variant_pool = RolePool(
                    pool_id=pool.pool_id,
                    object_kind=pool.object_kind,
                    roles=[
                        _role_with_salary(item, variant_value)
                        if item.role_id == role.role_id
                        else item
                        for item in pool.roles
                    ],
                )
                engines = [
                    "role-labour-baseline-v1",
                    "purchase-cost-ledger-v1",
                    "full-cashflows-reconciliation-v2",
                    "multiprocess-allocation-v1",
                ]
            else:
                raw_request = request.model_dump(mode="json")
                raw_request["process"]["demand"]["raw_value"] = variant_value
                raw_request["process"]["demand"]["normalized_value"] = variant_value
                variant_request = CapacityAnalysisRequest.model_validate(raw_request)
                capacity_execution = analyze_capacity(
                    variant_request,
                    snapshot,
                    f"{context.run_id}.capacity-volume.{direction.lower()}",
                )
                if capacity_execution.response.capacity.value is None:
                    raise ValueError("C20 volume variant capacity is blocked")
                variant_context = EconomicsExecutionContextV1(
                    run_id=context.run_id,
                    project_id=context.project_id,
                    tenant_id=context.tenant_id,
                    capacity_request=variant_request,
                    capacity_response=capacity_execution.response,
                    constraint_report=capacity_execution.constraints.model_dump(
                        mode="json"
                    ),
                    executability=capacity_execution.executability.model_dump(
                        mode="json"
                    ),
                )
                engines = [
                    "capacity-analysis-service-v2",
                    "role-labour-baseline-v1",
                    "purchase-cost-ledger-v1",
                    "full-cashflows-reconciliation-v2",
                    "multiprocess-allocation-v1",
                ]
            artifact = _scenario_artifacts(
                variant_context,
                inputs,
                snapshot,
                "PURCHASE",
                "BASE",
                primary_price_override=primary_price,
                role_pool=variant_pool,
                allocation_run_id=derived_run_id,
            )
            capacity = _capacity_binding(
                variant_context.capacity_response,
                variant_context.capacity_request,
            )
            variants.append(
                SensitivityVariantInputV1(
                    variant_id=variant_id,
                    derived_run_id=derived_run_id,
                    status="EXECUTABLE",
                    override=override,
                    capacity_bindings=[capacity],
                    rerun_engines=engines,
                    allocation_request=artifact.allocation_request,
                )
            )
    sensitivity_request = SensitivityRequestV1(
        run_id=f"{context.run_id}.sensitivity",
        parent_run_id=base.allocation.run_id,
        project_id=context.project_id,
        tenant_id=context.tenant_id,
        object_id=base.allocation.object_id,
        baseline_allocation_request=base.allocation_request,
        baseline_allocation_result=base.allocation,
        baseline_allocation_result_digest=semantic_digest(base.allocation),
        ranking_result_digest=semantic_digest(ranking),
        selected_candidate_id=ranking.candidates[0].candidate_id,
        selected_configuration_id=base.allocation.processes[0].configuration_id,
        baseline_capacity_bindings=[binding],
        variants=variants,
    )
    return analyze_sensitivity(sensitivity_request)


def _metric(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json")


def _procurement_projection(report: Any) -> dict[str, Any]:
    raw = report.money.raw_money
    return {
        "source_schema_version": report.schema_version,
        "source_digest": semantic_digest(report),
        "acquisition": report.acquisition,
        "procurement_status": report.procurement_status,
        "procurement_ready": report.procurement_ready,
        "blockers": report.blockers,
        "supply_risk": report.supply_risk,
        "money": {
            "status": report.money.status,
            "cash_gross_rub": report.money.cash_gross_rub,
            "raw_money": None
            if raw is None
            else {
                "raw_amount": raw.raw_amount,
                "currency": raw.currency,
                "tax_basis": raw.tax_basis,
                "vat_rate": raw.vat_rate,
                "source": {"source_id": raw.source.source_id},
            },
        },
    }


def _financial_projection(
    result: FinancialResultV1 | RaasFinancialResultV1,
) -> dict[str, Any]:
    return {
        "source_schema_version": result.schema_version,
        "source_digest": semantic_digest(result),
        "project_id": result.project_id,
        "tenant_id": result.tenant_id,
        "input_revision": result.input_revision,
        "status": result.status,
        "npv_project": _metric(result.npv_project),
        "simple_payback": _metric(result.simple_payback),
        "discounted_payback": _metric(result.discounted_payback),
        "annual_ledgers": [
            {
                "year": item.year,
                "primary_cf_base": item.primary_cf_base,
                "primary_cf_scenario": item.primary_cf_scenario,
                "differential_cf": item.differential_cf,
                "status": item.status,
                "source_refs": [f"{result.run_id}.year-{item.year}"],
            }
            for item in result.annual_ledgers
        ],
    }


def _allocation_projection(result: MultiprocessAllocationResultV1) -> dict[str, Any]:
    return {
        "source_schema_version": result.schema_version,
        "source_digest": semantic_digest(result),
        "project_id": result.project_id,
        "tenant_id": result.tenant_id,
        "input_revision": result.input_revision,
        "role_conservation": [
            {
                "role_id": item.role_id,
                "headcount": item.headcount,
                "released": item.released,
                "remaining": item.remaining,
            }
            for item in result.role_conservation
        ],
        "control_required_once": result.control_required_once,
        "technicians_required_once": result.technicians_required_once,
    }


def _expenses(artifact: ScenarioArtifacts) -> list[dict[str, Any]]:
    if artifact.acquisition == "PURCHASE":
        equipment = artifact.purchase.equipment_capex
        service = next(
            (
                line.amount
                for line in artifact.purchase.annual_ledgers[0].operating_lines
                if line.category == "SERVICE"
            ),
            None,
        )
        label = "Сервис"
    else:
        assert isinstance(artifact.financial, RaasFinancialResultV1)
        equipment = artifact.financial.capex_infrastructure_gross
        service = artifact.financial.annual_ledgers[0].raas_payment
        label = "RaaS payment"
    role_amount = artifact.allocation.annual_ledgers[0].object_scenario_fot
    return [
        {
            "line_id": "equipment",
            "label": "Оборудование/инфраструктура",
            "amount": equipment,
            "status": "COMPLETE",
            "source_ref": artifact.financial.run_id,
        },
        {
            "line_id": "service",
            "label": label,
            "amount": service,
            "status": "COMPLETE",
            "source_ref": artifact.financial.run_id,
        },
        {
            "line_id": "roles",
            "label": "Object FOT",
            "amount": role_amount,
            "status": "COMPLETE",
            "source_ref": artifact.allocation.run_id,
        },
    ]


def _bundle(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    artifacts: list[ScenarioArtifacts],
    ranking: RankingResultV2,
    sensitivity: SensitivityResultV1,
) -> dict[str, Any]:
    role_pool = _role_pool(context.capacity_request, inputs)
    roles = [
        {
            "role_id": item.role_id,
            "role_code": str(item.role_code),
            "headcount": item.headcount.normalized_value,
            "monthly_gross_salary": {
                "status": "KNOWN",
                "value": item.monthly_gross_salary.normalized_value,
                "unit": "RUB/person/month",
                "source": "USER",
                "provenance_ref": item.monthly_gross_salary.provenance_ref,
            },
        }
        for item in role_pool.roles
    ]
    scenarios = []
    selected = ranking.financial_recommendation.candidate_id
    for item in artifacts:
        candidate = ranking.candidates[0].candidate_id
        ready = item.procurement.procurement_ready and selected == candidate
        scenarios.append(
            {
                "scenario_id": f"scenario.{item.acquisition.lower()}.{item.uncertainty.lower()}",
                "acquisition": item.acquisition,
                "uncertainty": item.uncertainty,
                "procurement": _procurement_projection(item.procurement),
                "financial": _financial_projection(item.financial),
                "allocation": _allocation_projection(item.allocation),
                "recommendation": {
                    "status": "RECOMMENDED" if ready else "ALTERNATIVE",
                    "candidate_id": candidate if ready else None,
                    "reason_codes": [] if ready else ["procurement-not-confirmed"],
                },
                "expenses": _expenses(item),
                "assumptions": [
                    {
                        "assumption_id": "discount",
                        "label": "Discount rate",
                        "value": inputs.discount_rate,
                        "unit": "1",
                        "provenance_ref": "input.economics.discount-rate",
                    },
                    {
                        "assumption_id": "uncertainty",
                        "label": "Uncertainty profile",
                        "value": item.uncertainty,
                        "unit": "profile",
                        "provenance_ref": f"scenario.{item.uncertainty.lower()}",
                    },
                ],
                "source_refs": ["R03:F23-F32", item.financial.run_id],
            }
        )
    return {
        "schema_version": "commercial-scenarios-bundle-v2",
        "run_id": context.run_id,
        "project_id": context.project_id,
        "tenant_id": context.tenant_id,
        "input_revision": context.capacity_request.input_revision,
        "roles": roles,
        "scenarios": scenarios,
        "sensitivity": {
            "source_schema_version": sensitivity.schema_version,
            "source_digest": semantic_digest(sensitivity),
            "project_id": sensitivity.project_id,
            "tenant_id": sensitivity.tenant_id,
            "variants": [
                {
                    "variant_id": item.variant_id,
                    "override": {
                        "parameter_id": item.override.parameter_id,
                        "direction": item.override.direction,
                    },
                    "status": item.status,
                    "npv_project": {
                        "delta_value": item.npv_project.delta_value,
                        "unit": "RUB",
                    },
                    "step_reasons": item.step_reasons,
                }
                for item in sensitivity.variants
            ],
        },
        "ranking": {
            "source_schema_version": ranking.schema_version,
            "source_digest": semantic_digest(ranking),
            "technical_recommendation": ranking.technical_recommendation.model_dump(
                mode="json"
            ),
            "financial_recommendation": ranking.financial_recommendation.model_dump(
                mode="json"
            ),
        },
        "versions": {
            "orchestrator": ORCHESTRATOR_VERSION,
            "procurement": "procurement-report-v1",
            "finance_purchase": "financial-result-v1",
            "finance_raas": "raas-financial-result-v1",
            "allocation": "multiprocess-allocation-result-v1",
            "ranking": "ranking-result-v2",
            "sensitivity": "sensitivity-result-v1",
        },
        "limitations": [
            "Это предварительный расчёт, не коммерческое предложение и не рекомендация к закупке.",
            "Цена организаторов и пользовательские условия не подтверждают availability или procurement readiness.",
            "Авторский demo-профиль не является техпаспортом; C05 NEEDS_VALIDATION сохраняется.",
            "Нулевые и включённые статьи приняты только по явным подтверждениям этого run.",
        ],
    }


def _scenario_spec(
    context: EconomicsExecutionContextV1,
    inputs: EconomicsExplicitInputsV1,
    finance: MultiprocessAllocationResultV1,
) -> dict[str, Any]:
    request = context.capacity_request
    schedule = request.process.schedule
    if schedule is None:
        raise ValueError("ScenarioSpec v2 requires the C11 process schedule")
    hours = Decimal(schedule.shifts_per_day.normalized_value) * Decimal(
        schedule.shift_hours.normalized_value
    )
    assumption_ref = "assumption.synthetic-geometry"
    zone = ScenarioZoneV2(
        zone_id=f"zone.{request.process.process_id}",
        label=str(request.process.process_code),
        geometry_source="SYNTHETIC",
        assumption_ref=assumption_ref,
    )
    if isinstance(request.process.route_distance, KnownQuantity):
        route = ScenarioRouteBindingV2(
            route_id=f"route.{request.process.process_id}",
            geometry_source="SYNTHETIC",
            one_way_distance=ResultQuantity(
                value=request.process.route_distance.normalized_value,
                unit="m",
                quantity_kind=QuantityKind.DISTANCE,
            ),
            assumption_ref=assumption_ref,
        )
    else:
        route = ScenarioRouteBindingV2(
            route_id=f"route.{request.process.process_id}",
            geometry_source="NOT_APPLICABLE",
        )
    batch_source = request.process.explicit_batch
    if isinstance(batch_source, KnownQuantity):
        batch = ScenarioBatchV2(
            semantics="PHYSICAL_BATCH",
            units_per_cycle=ResultQuantity(
                value=batch_source.normalized_value,
                unit="unit/cycle",
                quantity_kind="RATE",
            ),
            provenance_ref=batch_source.provenance_ref,
        )
    else:
        batch = ScenarioBatchV2(
            semantics="AREA_MICROTASK"
            if request.process.scope == "CLEANING_AREA"
            else "ONE_OUTPUT_UNIT",
            units_per_cycle=ResultQuantity(
                value="1", unit="unit/cycle", quantity_kind="RATE"
            ),
            provenance_ref=assumption_ref,
        )
    spec = build_scenario_spec_v2(
        request,
        context.capacity_response,
        tenant_id=context.tenant_id,
        operating_windows=[
            ScenarioOperatingWindowV2(
                window_id="window.primary",
                start_time=ResultQuantity(
                    value=str(inputs.start_seconds_from_midnight),
                    unit="s",
                    quantity_kind="TIME",
                ),
                duration=ResultQuantity(
                    value=format(hours, "f"), unit="h", quantity_kind="TIME"
                ),
                timezone=inputs.timezone,
                source="USER",
                provenance_ref="input.economics.operating-window",
            )
        ],
        zone=zone,
        route=route,
        batch=batch,
        finance=finance,
        assumptions=[
            ScenarioAssumptionV2(
                assumption_id=assumption_ref,
                version="v1",
                provenance_ref=assumption_ref,
                scope="VISUALIZATION_ONLY",
                message="Геометрия синтетическая и не изменяет аналитический маршрут или экономику",
            )
        ],
        warnings=[
            "Предварительный demo: неподтверждённые C05 checks не являются PASS.",
            "ScenarioSpec не является инженерным цифровым двойником.",
        ],
    )
    return spec.model_dump(mode="json")


def execute_economics_v2(
    raw_inputs: dict[str, Any] | EconomicsExplicitInputsV1,
    snapshot: CatalogSnapshotDTO,
    context: EconomicsExecutionContextV1,
) -> EconomicsV2ExecutionV1:
    """Execute the accepted C13-C21 engines and return immutable snapshots."""

    inputs = (
        raw_inputs
        if isinstance(raw_inputs, EconomicsExplicitInputsV1)
        else EconomicsExplicitInputsV1.model_validate(raw_inputs)
    )
    request = context.capacity_request
    if inputs.input_revision != request.input_revision:
        raise ValueError("economics input_revision does not match the C11 snapshot")
    if context.capacity_response.capacity.status not in {
        "COMPLETE",
        "WITH_ASSUMPTIONS",
    }:
        raise ValueError("economics cannot run from a blocked C11 snapshot")
    if (
        context.capacity_response.run_id
        != context.capacity_response.trace.envelope.run_id
    ):
        raise ValueError("capacity run/trace identity mismatch")
    position = _position(snapshot, request)
    artifacts = [
        _scenario_artifacts(context, inputs, snapshot, acquisition, uncertainty)
        for acquisition in ACQUISITIONS
        for uncertainty in UNCERTAINTIES
    ]
    base = next(
        item
        for item in artifacts
        if item.acquisition == "PURCHASE" and item.uncertainty == "BASE"
    )
    ranking = _ranking(context, position, base)
    sensitivity = _sensitivity(context, inputs, snapshot, base, ranking)
    bundle = _bundle(context, inputs, artifacts, ranking, sensitivity)
    scenario = _scenario_spec(context, inputs, base.allocation)
    return EconomicsV2ExecutionV1(
        result_snapshot=bundle,
        scenario_spec_snapshot=scenario,
        revision_id=scenario["revision_id"],
        rules_version=RULES_VERSION,
        object_profile_version="calculation-intake-normalization-v2",
        application_version=ORCHESTRATOR_VERSION,
        diagnostics={
            "route": "ECONOMICS_V2",
            "capacity_run_id": context.capacity_response.run_id,
            "catalog_version": snapshot.version.code,
            "constraint_eligibility": context.constraint_report.get("eligibility"),
            "executability_status": context.executability.get("status"),
            "procurement_ready": False,
            "limitations": bundle["limitations"],
        },
    )


__all__ = [
    "ORCHESTRATOR_VERSION",
    "EconomicsExecutionContextV1",
    "EconomicsExplicitInputsV1",
    "execute_economics_v2",
]
