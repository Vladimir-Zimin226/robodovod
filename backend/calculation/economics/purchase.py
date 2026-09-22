"""C15 purchase cost ledger F16-F22.

No cash flow, tax, NPV, ROI or RaaS arithmetic belongs in this module.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_CEILING, Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from calculation.registry import CalculationParameterRegistryV1, load_registry
from calculation_contracts import Digest, StableId, StrictContractModel
from procurement.contracts import CommercialCostLineV1, CommercialMoneyV1, ProcurementReportV1, PurchaseTermsV1

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]
ZERO_DIGEST = "sha256:" + "0" * 64


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _c(value: str | int | Decimal) -> str:
    number = _d(value)
    if number == 0:
        return "0"
    rendered = format(number, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _digest(value: object) -> str:
    if isinstance(value, StrictContractModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SourcedValueV1(StrictContractModel):
    value: DecimalString
    unit: Annotated[str, Field(min_length=1, max_length=32)]
    source: Literal["USER", "FILE", "VENDOR_FACT", "POLICY"]
    provenance_ref: StableId
    evidence_ids: list[StableId] = Field(default_factory=list)
    evidence_status: Literal["VERIFIED_OFFICIAL", "VERIFIED_AUTHORIZED_PARTNER", "MANUALLY_APPROVED", "CORROBORATED"] | None = None

    @model_validator(mode="after")
    def non_negative(self) -> "SourcedValueV1":
        if _d(self.value) < 0:
            raise ValueError("sourced value cannot be negative")
        if self.source == "VENDOR_FACT" and (not self.evidence_ids or self.evidence_status is None):
            raise ValueError("vendor fact requires matching-safe evidence")
        if self.source != "VENDOR_FACT" and (self.evidence_ids or self.evidence_status is not None):
            raise ValueError("evidence status is only valid for vendor facts")
        return self


class OperatingBasisV1(StrictContractModel):
    operating_hours_per_day: SourcedValueV1
    days_per_year: SourcedValueV1
    availability: SourcedValueV1
    capacity_result_digest: Digest

    @model_validator(mode="after")
    def validate_basis(self) -> "OperatingBasisV1":
        hours = _d(self.operating_hours_per_day.value)
        days = _d(self.days_per_year.value)
        availability = _d(self.availability.value)
        if not (0 < hours <= 24):
            raise ValueError("operating hours must be within (0,24]")
        if days < 1 or days > 366 or days != days.to_integral_value():
            raise ValueError("days must be an integer in 1..366")
        if not (0 < availability <= 1):
            raise ValueError("availability must be within (0,1]")
        return self


class PowerEnergyPathV1(StrictContractModel):
    kind: Literal["POWER"] = "POWER"
    average_power_w: SourcedValueV1


class BatteryEnergyPathV1(StrictContractModel):
    kind: Literal["BATTERY_AUTONOMY"] = "BATTERY_AUTONOMY"
    battery_kwh: SourcedValueV1
    autonomy_hours: SourcedValueV1

    @model_validator(mode="after")
    def positive(self) -> "BatteryEnergyPathV1":
        if _d(self.battery_kwh.value) <= 0 or _d(self.autonomy_hours.value) <= 0:
            raise ValueError("battery energy path denominators must be positive")
        return self


EnergyPathV1 = Annotated[PowerEnergyPathV1 | BatteryEnergyPathV1, Field(discriminator="kind")]


class InitialBatteryPolicyV1(StrictContractModel):
    mode: Literal["INCLUDED_IN_ROBOT_PRICE", "SEPARATE_CAPEX"]
    provenance_ref: StableId
    separate_unit_price: SourcedValueV1 | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> "InitialBatteryPolicyV1":
        if (self.mode == "SEPARATE_CAPEX") != (self.separate_unit_price is not None):
            raise ValueError("separate initial battery requires an explicit unit price")
        return self


class SeparateBatteryLifecycleV1(StrictContractModel):
    mode: Literal["SEPARATE_REPLACEMENTS"] = "SEPARATE_REPLACEMENTS"
    autonomy_hours: SourcedValueV1
    resource_cycles: SourcedValueV1
    replacement_unit_price: SourcedValueV1

    @model_validator(mode="after")
    def positive(self) -> "SeparateBatteryLifecycleV1":
        if _d(self.autonomy_hours.value) <= 0 or _d(self.resource_cycles.value) <= 0:
            raise ValueError("battery lifecycle denominators must be positive")
        return self


class IncludedBatteryLifecycleV1(StrictContractModel):
    mode: Literal["INCLUDED_IN_SERVICE"] = "INCLUDED_IN_SERVICE"
    provenance_ref: StableId


BatteryLifecycleV1 = Annotated[SeparateBatteryLifecycleV1 | IncludedBatteryLifecycleV1, Field(discriminator="mode")]


class ResidualOverrideV1(StrictContractModel):
    life_years: SourcedValueV1
    liquidity_share: SourcedValueV1

    @model_validator(mode="after")
    def valid(self) -> "ResidualOverrideV1":
        if _d(self.life_years.value) <= 0 or not (0 <= _d(self.liquidity_share.value) <= 1):
            raise ValueError("invalid residual override")
        return self


class LabourOpexProjectionV1(StrictContractModel):
    technicians_required: Annotated[int, Field(ge=0)]
    technician_annual_direct: DecimalString | None = None
    additional_control_required: Annotated[int, Field(ge=0)]
    control_annual_direct: DecimalString | None = None
    source_result_digest: Digest

    @model_validator(mode="after")
    def costs_non_negative(self) -> "LabourOpexProjectionV1":
        for value in (self.technician_annual_direct, self.control_annual_direct):
            if value is not None and _d(value) < 0:
                raise ValueError("labour OPEX unit cost cannot be negative")
        return self


class PurchaseLedgerRequestV1(StrictContractModel):
    schema_version: Literal["purchase-cost-ledger-request-v1"] = "purchase-cost-ledger-request-v1"
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    fleet_count: Annotated[int, Field(ge=0)]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"] = "BASE"
    horizon_years: Annotated[int, Field(ge=5, le=15)]
    equipment_class: Literal["AMR", "FORKLIFT", "SHUTTLE", "FIXED_CELL", "MANIPULATOR", "CLEANER", "OTHER"]
    procurement: ProcurementReportV1
    operating: OperatingBasisV1
    labour_trace_digest: Digest
    labour_opex: LabourOpexProjectionV1
    charger_ratio: SourcedValueV1 | None = None
    warranty_years: SourcedValueV1 | None = None
    energy_path: EnergyPathV1 | None = None
    initial_battery: InitialBatteryPolicyV1
    battery_lifecycle: BatteryLifecycleV1 | None = None
    residual_override: ResidualOverrideV1 | None = None

    @model_validator(mode="after")
    def validate_purchase(self) -> "PurchaseLedgerRequestV1":
        if self.procurement.acquisition != "PURCHASE" or not isinstance(self.procurement.terms, PurchaseTermsV1):
            raise ValueError("C15 purchase ledger requires resolved PURCHASE terms")
        if self.procurement.money.status != "RESOLVED" or self.procurement.money.cash_gross_rub is None:
            raise ValueError("primary robot price must be resolved by C13")
        if self.charger_ratio is not None and _d(self.charger_ratio.value) < 0:
            raise ValueError("charger ratio cannot be negative")
        if self.warranty_years is not None:
            value = _d(self.warranty_years.value)
            if value < 0 or value != value.to_integral_value():
                raise ValueError("warranty years must be a non-negative integer")
        expected_technicians = 0 if self.fleet_count == 0 else _ceil(Decimal(self.fleet_count) / Decimal("20"))
        if self.labour_opex.technicians_required != expected_technicians:
            raise ValueError("C14 technician count must equal ceil(fleet/20)")
        if self.labour_opex.source_result_digest != self.labour_trace_digest:
            raise ValueError("C14 labour projection digest mismatch")
        return self


class CostLineV1(StrictContractModel):
    line_id: StableId
    formula_id: Literal["F16", "F17", "F18", "F19", "F20", "F21", "F22"]
    category: Annotated[str, Field(min_length=1)]
    timing: Literal["CAPITAL_ONCE", "ANNUAL", "TERMINAL"]
    year: Annotated[int, Field(ge=0, le=15)]
    status: Literal["COMPLETE", "INCOMPLETE", "EXCLUDED", "NOT_APPLICABLE"]
    amount: DecimalString | None
    unit: Literal["RUB"] = "RUB"
    basis: Annotated[str, Field(min_length=1)]
    source_refs: list[StableId] = Field(default_factory=list)
    ownership: Literal["CUSTOMER", "VENDOR", "INTEGRATOR", "SHARED", "UNKNOWN"]
    reason_code: StableId | None = None


class BatteryEventV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    events_per_robot: Annotated[int, Field(ge=0)]
    cumulative_cycles: DecimalString
    amount: DecimalString


class AnnualCostLedgerV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    ramp: DecimalString
    deployment_share: Literal["1"] = "1"
    operating_lines: list[CostLineV1]
    operating_total: DecimalString | None
    status: Literal["COMPLETE", "INCOMPLETE"]


class PurchaseTraceNodeV1(StrictContractModel):
    node_id: StableId
    formula_id: Literal["F16", "F17", "F18", "F19", "F20", "F21", "F22"]
    inputs: list[str]
    output: StableId
    value: DecimalString | None
    unit: Annotated[str, Field(min_length=1)]
    source_refs: list[StableId]
    rounding: Literal["NONE", "CEIL"] = "NONE"


class PurchaseLedgerReplayV1(StrictContractModel):
    canonical_input_digest: Digest
    capacity_result_digest: Digest
    labour_trace_digest: Digest
    trace_content_digest: Digest


class PurchaseCostLedgerV1(StrictContractModel):
    schema_version: Literal["purchase-cost-ledger-v1"] = "purchase-cost-ledger-v1"
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    status: Literal["COMPLETE", "INCOMPLETE"]
    fleet_count: Annotated[int, Field(ge=0)]
    capital_lines: list[CostLineV1]
    annual_ledgers: list[AnnualCostLedgerV1]
    battery_events: list[BatteryEventV1]
    capex_gross: DecimalString | None
    capex_amortizable: DecimalString | None
    capex_cashflow: DecimalString | None
    equipment_capex: DecimalString | None
    reserve: DecimalString | None
    terminal_residual: DecimalString | None
    issues: list[StableId]
    trace: list[PurchaseTraceNodeV1]
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    registry_digest: Digest
    commercial_policy_version: Literal["hackathon-commercial-policy-v1"]
    policy_overlay_version: Literal["hackathon-calculation-policy-v1+v2b-c15"] = "hackathon-calculation-policy-v1+v2b-c15"
    engine_version: Literal["purchase-cost-ledger-v1"] = "purchase-cost-ledger-v1"
    replay: PurchaseLedgerReplayV1


def _registry(registry: CalculationParameterRegistryV1, key: str) -> Decimal:
    return _d(registry.by_id(key).value)


def _money(value: CommercialMoneyV1) -> Decimal | None:
    if value.currency != "RUB":
        return None
    amount = _d(value.raw_amount)
    if value.tax_basis == "CASH_GROSS_RUB":
        return amount
    if value.tax_basis == "NET_RUB" and value.vat_rate is not None:
        return amount * (Decimal("1") + _d(value.vat_rate))
    return None


def _line_money(line: CommercialCostLineV1) -> tuple[Decimal | None, str, list[str]]:
    if line.basis.kind == "PERCENT_BASE":
        return _d(line.basis.rate), f"PERCENT_BASE:{line.basis.base_line_id}", [line.basis.base_line_id]
    resolved = _money(line.basis.money)
    return resolved, line.basis.kind, [line.basis.money.source.source_id, *line.basis.money.source.evidence_ids]


def _cost_owner(terms: PurchaseTermsV1, category: str) -> str:
    mapping = {"ROBOT": "HARDWARE", "CHARGER": "CHARGING", "SERVICE": "MAINTENANCE", "SOFTWARE": "SOFTWARE", "INFRASTRUCTURE": "INFRASTRUCTURE"}
    area = mapping.get(category)
    match = next((item for item in terms.responsibilities if item.area == area), None)
    return match.responsible_party if match else "UNKNOWN"


def _ramp(registry: CalculationParameterRegistryV1, uncertainty: str, year: int) -> Decimal:
    suffix = f"year-{year}" if year <= 5 else "year-6-plus"
    return _registry(registry, f"scenario.{uncertainty.lower()}.ramp.{suffix}")


def calculate_purchase_ledger(request: PurchaseLedgerRequestV1, *, registry: CalculationParameterRegistryV1 | None = None) -> PurchaseCostLedgerV1:
    registry = registry or load_registry()
    terms = request.procurement.terms
    assert isinstance(terms, PurchaseTermsV1)
    fleet = request.fleet_count
    hw = _registry(registry, f"scenario.{request.uncertainty.lower()}.capex-multiplier")
    reserve_share = _registry(registry, f"scenario.{request.uncertainty.lower()}.capex-reserve")
    primary_price = _d(request.procurement.money.cash_gross_rub or "0")
    issues: set[str] = set()
    trace: list[PurchaseTraceNodeV1] = []
    capital: list[CostLineV1] = []
    robot_pre_hw = Decimal(fleet) * primary_price
    robot_total = robot_pre_hw * hw
    capital.append(CostLineV1(line_id="capital.robots", formula_id="F16", category="ROBOT", timing="CAPITAL_ONCE", year=0, status="COMPLETE", amount=_c(robot_total), basis="fleet × C13 resolved price × hardware multiplier", source_refs=request.procurement.money.provenance_refs, ownership=_cost_owner(terms, "ROBOT")))
    trace.append(PurchaseTraceNodeV1(node_id="node.f16.robots", formula_id="F16", inputs=["fleet_count", "procurement.money.cash_gross_rub", "scenario.capex_multiplier"], output="capital.robots", value=_c(robot_total), unit="RUB", source_refs=request.procurement.money.provenance_refs))

    equipment = robot_total
    for line in terms.cost_lines:
        if line.timing != "CAPITAL_ONCE":
            continue
        value, basis, refs = _line_money(line)
        if line.excluded_by_scenario or line.included_in or (value == 0 and getattr(line.basis, "money", None) is not None):
            reason = "included-in-another-line" if line.included_in else "explicitly-excluded"
            capital.append(CostLineV1(line_id=f"capital.{line.line_id}", formula_id="F17", category=line.category, timing="CAPITAL_ONCE", year=0, status="EXCLUDED", amount="0", basis=basis, source_refs=refs + line.included_in, ownership=_cost_owner(terms, line.category), reason_code=reason))
            continue
        if value is None:
            issues.add("commercial-line-unresolved")
            capital.append(CostLineV1(line_id=f"capital.{line.line_id}", formula_id="F17", category=line.category, timing="CAPITAL_ONCE", year=0, status="INCOMPLETE", amount=None, basis=basis, source_refs=refs, ownership=_cost_owner(terms, line.category), reason_code="commercial-line-unresolved"))
            continue
        if line.category == "CHARGER":
            if request.charger_ratio is None:
                issues.add("charger-ratio-missing")
                capital.append(CostLineV1(line_id=f"capital.{line.line_id}", formula_id="F16", category=line.category, timing="CAPITAL_ONCE", year=0, status="INCOMPLETE", amount=None, basis=basis, source_refs=refs, ownership=_cost_owner(terms, line.category), reason_code="charger-ratio-missing"))
                continue
            count = _ceil(Decimal(fleet) * _d(request.charger_ratio.value))
            amount = Decimal(count) * value * hw
            equipment += amount
            formula = "F16"
            basis_text = f"ceil(fleet × charger_ratio)={count} × unit price × hardware multiplier"
            rounding = "CEIL"
        elif line.category == "INTEGRATION" and line.basis.kind == "PER_ROBOT":
            amount = Decimal(fleet) * value * hw
            formula = "F16"
            basis_text = "fleet × per-robot integration × hardware multiplier"
            rounding = "NONE"
        elif line.category == "INFRASTRUCTURE":
            amount = (value if line.basis.kind == "FIXED_TOTAL" else Decimal(fleet) * value) * hw
            formula = "F16"
            basis_text = f"{basis} × hardware multiplier"
            rounding = "NONE"
        elif line.basis.kind == "FIXED_TOTAL":
            amount = value
            formula = "F17"
            basis_text = basis
            rounding = "NONE"
        elif line.basis.kind == "PER_ROBOT":
            amount = Decimal(fleet) * value
            formula = "F17"
            basis_text = basis
            rounding = "NONE"
        else:
            amount = robot_pre_hw * value
            formula = "F17"
            basis_text = basis
            rounding = "NONE"
        capital.append(CostLineV1(line_id=f"capital.{line.line_id}", formula_id=formula, category=line.category, timing="CAPITAL_ONCE", year=0, status="COMPLETE", amount=_c(amount), basis=basis_text, source_refs=refs, ownership=_cost_owner(terms, line.category)))
        trace.append(PurchaseTraceNodeV1(node_id=f"node.{formula.lower()}.{line.line_id}", formula_id=formula, inputs=[line.line_id, "fleet_count"], output=f"capital.{line.line_id}", value=_c(amount), unit="RUB", source_refs=refs, rounding=rounding))

    if request.initial_battery.mode == "SEPARATE_CAPEX":
        battery_price = _d(request.initial_battery.separate_unit_price.value)  # type: ignore[union-attr]
        initial_battery = Decimal(fleet) * battery_price * hw
        equipment += initial_battery
        capital.append(CostLineV1(line_id="capital.initial-batteries", formula_id="F16", category="BATTERY", timing="CAPITAL_ONCE", year=0, status="COMPLETE", amount=_c(initial_battery), basis="explicit separate battery price × fleet × hardware multiplier", source_refs=[request.initial_battery.provenance_ref, request.initial_battery.separate_unit_price.provenance_ref], ownership="CUSTOMER"))  # type: ignore[union-attr]

    complete_capital = [item for item in capital if item.status in ("COMPLETE", "EXCLUDED")]
    capital_incomplete = any(item.status == "INCOMPLETE" for item in capital)
    capital_subtotal = sum((_d(item.amount or "0") for item in complete_capital), Decimal("0"))
    reserve = capital_subtotal * reserve_share
    capital.append(CostLineV1(line_id="capital.reserve", formula_id="F17", category="RESERVE", timing="CAPITAL_ONCE", year=0, status="INCOMPLETE" if capital_incomplete else "COMPLETE", amount=None if capital_incomplete else _c(reserve), basis="all resolved capital lines × scenario reserve", source_refs=[f"scenario.{request.uncertainty.lower()}.capex-reserve"], ownership="CUSTOMER", reason_code="capital-base-incomplete" if capital_incomplete else None))
    trace.append(PurchaseTraceNodeV1(node_id="node.f17.reserve", formula_id="F17", inputs=[item.line_id for item in capital if item.line_id != "capital.reserve"], output="capital.reserve", value=None if capital_incomplete else _c(reserve), unit="RUB", source_refs=[f"scenario.{request.uncertainty.lower()}.capex-reserve"]))
    capex_gross = None if capital_incomplete else capital_subtotal + reserve

    annual: list[AnnualCostLedgerV1] = []
    battery_events: list[BatteryEventV1] = []
    cumulative_cycles = Decimal("0")
    previous_events = 0
    hours = _d(request.operating.operating_hours_per_day.value)
    days = _d(request.operating.days_per_year.value)
    availability = _d(request.operating.availability.value)
    efficiency = _registry(registry, "finance.energy.charging-efficiency")
    energy_inflation = _registry(registry, "finance.inflation.electricity")
    other_inflation = _registry(registry, "finance.inflation.other-opex")
    tariff = _registry(registry, "finance.electricity-tariff")
    service_mult = _registry(registry, f"scenario.{request.uncertainty.lower()}.service-multiplier")
    service_line = next((item for item in terms.cost_lines if item.category == "SERVICE" and item.timing == "ANNUAL"), None)
    software_lines = [item for item in terms.cost_lines if item.category == "SOFTWARE" and item.timing in ("ANNUAL", "MONTHLY")]

    for year in range(1, request.horizon_years + 1):
        ramp = _ramp(registry, request.uncertainty, year)
        lines: list[CostLineV1] = []
        for category, share_id in (("INSURANCE", "finance.insurance-share"), ("CONSUMABLES", "finance.consumables-share"), ("REPAIR", "finance.repair-share")):
            amount = equipment * _registry(registry, share_id) * ramp * (Decimal("1") + other_inflation) ** (year - 1)
            lines.append(CostLineV1(line_id=f"year.{year}.{category.lower()}", formula_id="F18", category=category, timing="ANNUAL", year=year, status="COMPLETE", amount=_c(amount), basis="equipment CAPEX only × share × utilization ramp × other OPEX index", source_refs=[share_id], ownership="CUSTOMER"))
        if service_line is None:
            issues.add("annual-service-line-missing")
            lines.append(CostLineV1(line_id=f"year.{year}.service", formula_id="F19", category="SERVICE", timing="ANNUAL", year=year, status="INCOMPLETE", amount=None, basis="required annual service", source_refs=[], ownership=_cost_owner(terms, "SERVICE"), reason_code="annual-service-line-missing"))
        elif request.warranty_years is None:
            issues.add("warranty-years-missing")
            lines.append(CostLineV1(line_id=f"year.{year}.service", formula_id="F19", category="SERVICE", timing="ANNUAL", year=year, status="INCOMPLETE", amount=None, basis="service after explicit warranty", source_refs=[], ownership=_cost_owner(terms, "SERVICE"), reason_code="warranty-years-missing"))
        else:
            unit, basis, refs = _line_money(service_line)
            if unit is None:
                issues.add("annual-service-line-unresolved")
                amount = None
            elif year <= int(_d(request.warranty_years.value)):
                amount = Decimal("0")
            else:
                base = unit if service_line.basis.kind == "FIXED_TOTAL" else Decimal(fleet) * unit
                amount = base * service_mult * ramp * (Decimal("1") + other_inflation) ** (year - 1)
            lines.append(CostLineV1(line_id=f"year.{year}.service", formula_id="F19", category="SERVICE", timing="ANNUAL", year=year, status="COMPLETE" if amount is not None else "INCOMPLETE", amount=None if amount is None else _c(amount), basis=basis, source_refs=refs, ownership=_cost_owner(terms, "SERVICE"), reason_code=None if amount is not None else "annual-service-line-unresolved"))
        for source in software_lines:
            unit, basis, refs = _line_money(source)
            amount = None if unit is None else (unit if source.basis.kind == "FIXED_TOTAL" else Decimal(fleet) * unit)
            if amount is not None:
                if source.timing == "MONTHLY":
                    amount *= 12
                amount *= ramp * (Decimal("1") + other_inflation) ** (year - 1)
            lines.append(CostLineV1(line_id=f"year.{year}.{source.line_id}", formula_id="F19", category="SOFTWARE", timing="ANNUAL", year=year, status="COMPLETE" if amount is not None else "INCOMPLETE", amount=None if amount is None else _c(amount), basis=basis, source_refs=refs, ownership=_cost_owner(terms, "SOFTWARE"), reason_code=None if amount is not None else "software-line-unresolved"))
        comm = Decimal(fleet) * _registry(registry, "finance.communication.monthly-per-robot") * 12 * ramp * (Decimal("1") + other_inflation) ** (year - 1)
        lines.append(CostLineV1(line_id=f"year.{year}.communication", formula_id="F19", category="COMMUNICATION", timing="ANNUAL", year=year, status="COMPLETE", amount=_c(comm), basis="fleet × monthly communication × 12 × ramp × index", source_refs=["finance.communication.monthly-per-robot"], ownership="CUSTOMER"))
        for category, count, unit_cost in (
            ("TECHNICIANS", request.labour_opex.technicians_required, request.labour_opex.technician_annual_direct),
            ("CONTROL_OPERATORS", request.labour_opex.additional_control_required, request.labour_opex.control_annual_direct),
        ):
            category_id = category.lower().replace("_", "-")
            if count == 0:
                lines.append(CostLineV1(line_id=f"year.{year}.{category_id}", formula_id="F19", category=category, timing="ANNUAL", year=year, status="NOT_APPLICABLE", amount="0", basis="C14 required count is zero", source_refs=[request.labour_trace_digest], ownership="CUSTOMER"))
            elif unit_cost is None:
                issues.add(f"{category_id}-salary-missing")
                lines.append(CostLineV1(line_id=f"year.{year}.{category_id}", formula_id="F19", category=category, timing="ANNUAL", year=year, status="INCOMPLETE", amount=None, basis="C14 count × annual direct labour × ramp × labour index", source_refs=[request.labour_trace_digest], ownership="CUSTOMER", reason_code=f"{category_id}-salary-missing"))
            else:
                labor_index = _registry(registry, "finance.inflation.labor")
                labor_amount = Decimal(count) * _d(unit_cost) * ramp * (Decimal("1") + labor_index) ** (year - 1)
                lines.append(CostLineV1(line_id=f"year.{year}.{category_id}", formula_id="F19", category=category, timing="ANNUAL", year=year, status="COMPLETE", amount=_c(labor_amount), basis="C14 count × annual direct labour × ramp × labour index", source_refs=[request.labour_trace_digest, "finance.inflation.labor"], ownership="CUSTOMER"))
        if request.energy_path is None:
            issues.add("energy-path-missing")
            lines.append(CostLineV1(line_id=f"year.{year}.energy", formula_id="F20", category="ENERGY", timing="ANNUAL", year=year, status="INCOMPLETE", amount=None, basis="exactly one explicit energy path", source_refs=[], ownership="CUSTOMER", reason_code="energy-path-missing"))
        else:
            if request.energy_path.kind == "POWER":
                kwh = Decimal(fleet) * (_d(request.energy_path.average_power_w.value) / 1000) * hours * availability * days / efficiency
                refs = [request.energy_path.average_power_w.provenance_ref]
                basis = "power W→kW × H × availability × days / efficiency"
            else:
                kwh = Decimal(fleet) * hours * availability / _d(request.energy_path.autonomy_hours.value) * _d(request.energy_path.battery_kwh.value) * days / efficiency
                refs = [request.energy_path.battery_kwh.provenance_ref, request.energy_path.autonomy_hours.provenance_ref]
                basis = "battery cycles × battery kWh × days / efficiency"
            amount = kwh * tariff * ramp * (Decimal("1") + energy_inflation) ** (year - 1)
            lines.append(CostLineV1(line_id=f"year.{year}.energy", formula_id="F20", category="ENERGY", timing="ANNUAL", year=year, status="COMPLETE", amount=_c(amount), basis=basis, source_refs=refs + ["finance.electricity-tariff", "finance.energy.charging-efficiency"], ownership="CUSTOMER"))
        if request.battery_lifecycle is None:
            issues.add("battery-lifecycle-missing")
            lines.append(CostLineV1(line_id=f"year.{year}.battery-replacement", formula_id="F21", category="BATTERY_REPLACEMENT", timing="ANNUAL", year=year, status="INCOMPLETE", amount=None, basis="explicit replacement lifecycle", source_refs=[], ownership="CUSTOMER", reason_code="battery-lifecycle-missing"))
        elif request.battery_lifecycle.mode == "INCLUDED_IN_SERVICE":
            lines.append(CostLineV1(line_id=f"year.{year}.battery-replacement", formula_id="F21", category="BATTERY_REPLACEMENT", timing="ANNUAL", year=year, status="EXCLUDED", amount="0", basis="explicitly included in service", source_refs=[request.battery_lifecycle.provenance_ref], ownership="VENDOR", reason_code="included-in-service"))
        else:
            annual_cycles = hours * days * availability / _d(request.battery_lifecycle.autonomy_hours.value)
            cumulative_cycles += annual_cycles * ramp
            resource = _d(request.battery_lifecycle.resource_cycles.value)
            total_events = max(0, _ceil(cumulative_cycles / resource) - 1) if cumulative_cycles % resource == 0 else int(cumulative_cycles // resource)
            new_events = max(0, total_events - previous_events)
            previous_events = total_events
            battery_amount = Decimal(new_events * fleet) * _d(request.battery_lifecycle.replacement_unit_price.value) * hw * (Decimal("1") + other_inflation) ** (year - 1)
            lines.append(CostLineV1(line_id=f"year.{year}.battery-replacement", formula_id="F21", category="BATTERY_REPLACEMENT", timing="ANNUAL", year=year, status="COMPLETE", amount=_c(battery_amount), basis="new cumulative cycle crossings × fleet × price × hw × index", source_refs=[request.battery_lifecycle.autonomy_hours.provenance_ref, request.battery_lifecycle.resource_cycles.provenance_ref, request.battery_lifecycle.replacement_unit_price.provenance_ref], ownership="CUSTOMER"))
            battery_events.append(BatteryEventV1(year=year, events_per_robot=new_events, cumulative_cycles=_c(cumulative_cycles), amount=_c(battery_amount)))
        year_incomplete = any(item.status == "INCOMPLETE" for item in lines)
        total = None if year_incomplete else sum((_d(item.amount or "0") for item in lines), Decimal("0"))
        for formula_id in ("F18", "F19", "F20", "F21"):
            formula_lines = [item for item in lines if item.formula_id == formula_id]
            formula_incomplete = any(item.status == "INCOMPLETE" for item in formula_lines)
            formula_total = None if formula_incomplete else sum((_d(item.amount or "0") for item in formula_lines), Decimal("0"))
            trace.append(PurchaseTraceNodeV1(
                node_id=f"node.{formula_id.lower()}.year-{year}", formula_id=formula_id,
                inputs=[item.line_id for item in formula_lines], output=f"year.{year}.{formula_id.lower()}-total",
                value=None if formula_total is None else _c(formula_total), unit="RUB",
                source_refs=sorted({ref for item in formula_lines for ref in item.source_refs}),
            ))
        annual.append(AnnualCostLedgerV1(year=year, ramp=_c(ramp), operating_lines=lines, operating_total=None if total is None else _c(total), status="INCOMPLETE" if year_incomplete else "COMPLETE"))

    asset_key = {"AMR": "amr", "FORKLIFT": "forklift", "SHUTTLE": "shuttle", "FIXED_CELL": "fixed-cell", "MANIPULATOR": "manipulator"}.get(request.equipment_class)
    if request.residual_override is not None:
        life = _d(request.residual_override.life_years.value)
        liquidity = _d(request.residual_override.liquidity_share.value)
        residual_refs = [request.residual_override.life_years.provenance_ref, request.residual_override.liquidity_share.provenance_ref]
    elif asset_key is not None:
        life = _registry(registry, f"finance.asset-life.{asset_key}")
        liquidity = _registry(registry, f"finance.asset-liquidity.{asset_key}")
        residual_refs = [f"finance.asset-life.{asset_key}", f"finance.asset-liquidity.{asset_key}"]
    else:
        life, liquidity = Decimal("1"), Decimal("0")
        residual_refs = ["policy.k11.conservative-zero-residual"]
    residual = robot_total * max(Decimal("0"), Decimal("1") - Decimal(request.horizon_years) / life) * liquidity
    trace.append(PurchaseTraceNodeV1(node_id="node.f22.residual", formula_id="F22", inputs=["capital.robots", "horizon", "asset.life", "asset.liquidity"], output="terminal.residual", value=_c(residual), unit="RUB", source_refs=residual_refs))

    status = "INCOMPLETE" if capital_incomplete or any(item.status == "INCOMPLETE" for item in annual) else "COMPLETE"
    replay = PurchaseLedgerReplayV1(canonical_input_digest=_digest(request), capacity_result_digest=request.operating.capacity_result_digest, labour_trace_digest=request.labour_trace_digest, trace_content_digest=ZERO_DIGEST)
    result = PurchaseCostLedgerV1(
        run_id=request.run_id, project_id=request.project_id, tenant_id=request.tenant_id, input_revision=request.input_revision,
        status=status, fleet_count=fleet, capital_lines=capital, annual_ledgers=annual, battery_events=battery_events,
        capex_gross=None if capex_gross is None else _c(capex_gross), capex_amortizable=None if capital_incomplete else _c(capital_subtotal),
        capex_cashflow=None if capex_gross is None else _c(capex_gross), equipment_capex=_c(equipment),
        reserve=None if capital_incomplete else _c(reserve), terminal_residual=_c(residual), issues=sorted(issues), trace=trace,
        registry_version=registry.registry_version, registry_digest=registry.registry_digest,
        commercial_policy_version=request.procurement.commercial_policy_version, replay=replay,
    )
    payload = result.model_dump(mode="json")
    payload["replay"]["trace_content_digest"] = None
    result.replay.trace_content_digest = _digest(payload)
    return result


__all__ = ["PurchaseCostLedgerV1", "PurchaseLedgerRequestV1", "calculate_purchase_ledger"]
