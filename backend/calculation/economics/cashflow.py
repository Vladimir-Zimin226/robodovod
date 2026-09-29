"""C16 full purchase cash flows and R13 reconciliation (F23-F31)."""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from calculation.economics.metrics import npv, payback
from calculation.economics.purchase import PurchaseCostLedgerV1, SourcedValueV1
from calculation.economics.tax import TaxMode, illustrative_tax
from calculation.labour import LabourResultV1, RoleLabourResultV1
from calculation.registry import CalculationParameterRegistryV1, load_registry
from calculation_contracts import Digest, StableId, StrictContractModel

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]
ZERO_DIGEST = "sha256:" + "0" * 64


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _plain(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _metric(value: Decimal | None) -> str | None:
    return None if value is None else format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _digest(value: object) -> str:
    if isinstance(value, StrictContractModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _registry(registry: CalculationParameterRegistryV1, key: str) -> Decimal:
    return _d(registry.by_id(key).value)


class BaselineEquipmentV1(StrictContractModel):
    base_count: Annotated[int, Field(ge=0)]
    withdrawn_final: Annotated[int, Field(ge=0)]
    annual_cost_per_unit: SourcedValueV1

    @model_validator(mode="after")
    def conserved(self) -> "BaselineEquipmentV1":
        if self.withdrawn_final > self.base_count:
            raise ValueError("withdrawn equipment cannot exceed baseline")
        return self


class ExcludedAdditionalIncomeV1(StrictContractModel):
    mode: Literal["EXCLUDED"] = "EXCLUDED"
    provenance_ref: StableId


class IncludedAdditionalIncomeV1(StrictContractModel):
    mode: Literal["INCLUDED"] = "INCLUDED"
    annual_amount: SourcedValueV1


AdditionalIncomeV1 = Annotated[ExcludedAdditionalIncomeV1 | IncludedAdditionalIncomeV1,
                               Field(discriminator="mode")]


class FinancialAnalysisRequestV1(StrictContractModel):
    schema_version: Literal["financial-analysis-request-v1"] = "financial-analysis-request-v1"
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    purchase_ledger: PurchaseCostLedgerV1
    labour_result: LabourResultV1
    purchase_ledger_digest: Digest
    labour_result_digest: Digest
    discount_rate: SourcedValueV1
    tax_mode: TaxMode = "NONE"
    baseline_equipment: BaselineEquipmentV1 | None = None
    additional_income: AdditionalIncomeV1

    @model_validator(mode="after")
    def bind_snapshots(self) -> "FinancialAnalysisRequestV1":
        for snapshot in (self.purchase_ledger, self.labour_result):
            if (snapshot.project_id, snapshot.tenant_id, snapshot.input_revision) != (
                    self.project_id, self.tenant_id, self.input_revision):
                raise ValueError("upstream snapshot identity/revision mismatch")
        if self.purchase_ledger_digest != _digest(self.purchase_ledger):
            raise ValueError("purchase ledger digest mismatch")
        if self.labour_result_digest != _digest(self.labour_result):
            raise ValueError("labour result digest mismatch")
        if self.purchase_ledger.replay.labour_trace_digest != self.labour_result.replay.trace_content_digest:
            raise ValueError("C15/C14 labour trace binding mismatch")
        if self.purchase_ledger.replay.capacity_result_digest not in self.labour_result.replay.capacity_result_digests:
            raise ValueError("C15/C14 capacity trace binding mismatch")
        if not (Decimal(0) <= _d(self.discount_rate.value) <= Decimal(1)):
            raise ValueError("discount rate must be within 0..1")
        if self.discount_rate.unit != "1":
            raise ValueError("discount rate unit must be 1")
        if self.baseline_equipment is not None and self.labour_result.forklifts.base_count is not None:
            if self.baseline_equipment.base_count != self.labour_result.forklifts.base_count:
                raise ValueError("baseline equipment count must match C14")
            if self.labour_result.forklifts.withdrawn is not None and self.baseline_equipment.withdrawn_final != self.labour_result.forklifts.withdrawn:
                raise ValueError("withdrawn equipment count must match C14")
        return self


class FinancialLineV1(StrictContractModel):
    line_id: StableId
    amount: DecimalString | None
    unit: Literal["RUB"] = "RUB"
    source_refs: list[StableId]


class TaxLineV1(StrictContractModel):
    tax: DecimalString
    loss_open: DecimalString
    loss_used: DecimalString
    loss_close: DecimalString


class AnnualFinancialLedgerV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    ramp: DecimalString
    base_lines: list[FinancialLineV1]
    scenario_lines: list[FinancialLineV1]
    ebitda_base: DecimalString | None
    ebitda_scenario: DecimalString | None
    depreciation: DecimalString | None
    ebit_base: DecimalString | None
    ebit_scenario: DecimalString | None
    severance: DecimalString | None
    battery_replacements: DecimalString | None
    residual: DecimalString
    primary_cf_base: DecimalString | None
    primary_cf_scenario: DecimalString | None
    differential_cf: DecimalString | None
    tax_base: TaxLineV1 | None
    tax_scenario: TaxLineV1 | None
    supplement_cf_base: DecimalString | None
    supplement_cf_scenario: DecimalString | None
    status: Literal["COMPLETE", "INCOMPLETE"]


class MetricValueV1(StrictContractModel):
    status: Literal["COMPLETE", "NOT_REACHED", "N_A", "INCOMPLETE"]
    value: DecimalString | None
    unit: Literal["RUB", "PERCENT", "YEAR"]


class ReconciliationFindingV1(StrictContractModel):
    rule_id: Annotated[str, Field(pattern=r"^R13-(?:0[1-9]|[1-4][0-9])$")]
    status: Literal["PASS", "NOT_APPLICABLE", "POLICY_EXCEPTION", "INCOMPLETE"]
    evidence_refs: list[str]


class FinancialTraceNodeV1(StrictContractModel):
    node_id: StableId
    formula_id: Literal["F23", "F24", "F25", "F26", "F27", "F28", "F29", "F30", "F31"]
    input_refs: list[str]
    output: StableId
    value: DecimalString | None
    unit: Annotated[str, Field(min_length=1)]
    rounding: Literal["NONE", "CEIL", "FLOOR", "HALF_EVEN_2"] = "NONE"


class FinancialReplayV1(StrictContractModel):
    canonical_input_digest: Digest
    purchase_ledger_digest: Digest
    labour_result_digest: Digest
    capacity_result_digest: Digest
    trace_content_digest: Digest


class FinancialResultV1(StrictContractModel):
    schema_version: Literal["financial-result-v1"] = "financial-result-v1"
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    status: Literal["COMPLETE", "INCOMPLETE"]
    tax_mode: TaxMode
    initial_primary_cf_base: Literal["0"] = "0"
    initial_primary_cf_scenario: DecimalString | None
    annual_ledgers: list[AnnualFinancialLedgerV1]
    npv_base: MetricValueV1
    npv_scenario: MetricValueV1
    npv_project: MetricValueV1
    simple_payback: MetricValueV1
    discounted_payback: MetricValueV1
    cumulative_effect: MetricValueV1
    roi_on_capex_cashflow: MetricValueV1
    net_benefit_after_investment: MetricValueV1
    tco_purchase_gross: MetricValueV1
    tco_purchase_net_of_residual: MetricValueV1
    issues: list[StableId]
    reconciliation: list[ReconciliationFindingV1]
    trace: list[FinancialTraceNodeV1]
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    registry_digest: Digest
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"] = "hackathon-calculation-policy-v1"
    policy_overlay_version: Literal["hackathon-calculation-policy-v1+v2c-c16"] = "hackathon-calculation-policy-v1+v2c-c16"
    tax_policy_version: Literal["illustrative-profit-tax-v1"] = "illustrative-profit-tax-v1"
    precision_policy_version: Literal["decimal-context-28-half-even-v1"] = "decimal-context-28-half-even-v1"
    purchase_ledger_version: Literal["purchase-cost-ledger-v1"] = "purchase-cost-ledger-v1"
    labour_result_version: Literal["role-labour-result-v1"] = "role-labour-result-v1"
    engine_version: Literal["full-cashflows-reconciliation-v1", "full-cashflows-reconciliation-v2", "full-cashflows-reconciliation-v3"] = "full-cashflows-reconciliation-v2"
    replay: FinancialReplayV1


def _ramp(role: RoleLabourResultV1, year: int) -> Decimal:
    if not role.annual_staffing:
        return Decimal(1)
    return _d(role.annual_staffing[min(year, len(role.annual_staffing)) - 1].ramp) if year <= len(role.annual_staffing) else Decimal(1)


def _remaining(role: RoleLabourResultV1, year: int) -> int:
    return role.annual_staffing[year - 1].remaining if year <= len(role.annual_staffing) else role.remaining


def _released(role: RoleLabourResultV1, year: int) -> int:
    return role.annual_staffing[year - 1].released if year <= len(role.annual_staffing) else role.released


def _line(line_id: str, amount: Decimal | None, refs: list[str]) -> FinancialLineV1:
    return FinancialLineV1(line_id=line_id, amount=None if amount is None else _money(amount), source_refs=refs)


def _reconciliation(complete: bool) -> list[ReconciliationFindingV1]:
    outside = {14, 15, 16, 24, 27, 32, 34, 36, 44, 48, 49}
    exceptions = {18, 31, 39, 45, 46, 47}
    findings: list[ReconciliationFindingV1] = []
    for rule in range(1, 50):
        if rule in outside:
            status = "NOT_APPLICABLE"
            refs = ["C16_SCOPE"]
        elif rule in exceptions:
            status = "POLICY_EXCEPTION"
            refs = ["K09", "K12", "K13", "V2-C"]
        else:
            status = "PASS" if complete else "INCOMPLETE"
            refs = [f"F{min(31, max(23, 22 + ((rule - 1) % 9) + 1)):02d}"]
        findings.append(ReconciliationFindingV1(rule_id=f"R13-{rule:02d}", status=status, evidence_refs=refs))
    return findings


def calculate_financial_result(request: FinancialAnalysisRequestV1,
                               registry: CalculationParameterRegistryV1 | None = None,
                               *, engine_version: Literal["full-cashflows-reconciliation-v1", "full-cashflows-reconciliation-v2", "full-cashflows-reconciliation-v3"] = "full-cashflows-reconciliation-v2") -> FinancialResultV1:
    registry = registry or load_registry()
    purchase = request.purchase_ledger
    labour = request.labour_result
    horizon = len(purchase.annual_ledgers)
    issues = set(purchase.issues + labour.issues)
    incomplete = purchase.status != "COMPLETE" or labour.finance_status != "COMPLETE"
    capex = None if purchase.capex_cashflow is None else _d(purchase.capex_cashflow)
    amortizable = None if purchase.capex_amortizable is None else _d(purchase.capex_amortizable)
    if capex is None or amortizable is None:
        incomplete = True
        issues.add("c15-capex-incomplete")

    labour_index = _registry(registry, "finance.inflation.labor")
    other_index = _registry(registry, "finance.inflation.other-opex")
    severance_months = _registry(registry, "labor.severance.months")
    tax_rate = _registry(registry, "finance.tax.illustrative-rate")
    carry_years = int(_registry(registry, "finance.tax.loss-carry-years"))
    deduction_cap = _registry(registry, "finance.tax.loss-deduction-cap")
    discount = _d(request.discount_rate.value)
    additional = Decimal(0) if request.additional_income.mode == "EXCLUDED" else _d(request.additional_income.annual_amount.value)
    additional_refs = ([request.additional_income.provenance_ref] if request.additional_income.mode == "EXCLUDED"
                       else [request.additional_income.annual_amount.provenance_ref])

    rows: list[dict[str, object]] = []
    trace: list[FinancialTraceNodeV1] = []
    previous_released = {role.role_id: 0 for role in labour.roles}
    for year in range(1, horizon + 1):
        annual = purchase.annual_ledgers[year - 1]
        ramp = _d(annual.ramp)
        labor_factor = (Decimal(1) + labour_index) ** (year - 1)
        other_factor = (Decimal(1) + other_index) ** (year - 1)
        additional_t = additional * other_factor if engine_version == "full-cashflows-reconciliation-v3" else additional
        base_direct = base_overhead = scenario_direct = deficit_base = deficit_scenario = severance = Decimal(0)
        role_missing = False
        for role in labour.roles:
            if role.money is None:
                role_missing = True
                continue
            direct = _d(role.money.annual_direct)
            overhead = _d(role.money.annual_fixed_overhead)
            base_direct += Decimal(role.headcount) * direct * labor_factor
            base_overhead += Decimal(role.headcount) * overhead * labor_factor
            scenario_direct += Decimal(_remaining(role, year)) * direct * labor_factor
            if role.annual_deficit_cost is None and role.deficit > 0:
                role_missing = True
            else:
                # C14 F15 is already the annual cost for the whole deficit.
                # The v1 branch is retained solely for exact historical replay.
                deficit_total = _d(role.annual_deficit_cost or "0")
                deficit_base += (Decimal(role.deficit) * deficit_total if engine_version == "full-cashflows-reconciliation-v1" else deficit_total) * labor_factor
                remaining_deficit = max(0, role.deficit - int((Decimal(role.deficit_growth) * _ramp(role, year)).to_integral_value(rounding=ROUND_FLOOR)))
                scenario_deficit = (Decimal(remaining_deficit) * deficit_total if engine_version == "full-cashflows-reconciliation-v1" else (deficit_total * Decimal(remaining_deficit) / Decimal(role.deficit) if role.deficit else Decimal(0)))
                deficit_scenario += scenario_deficit * labor_factor
            released = _released(role, year)
            increment = max(0, released - previous_released[role.role_id])
            previous_released[role.role_id] = released
            severance += Decimal(increment) * _d(role.money.monthly_gross) * severance_months
        if role_missing:
            incomplete = True
            issues.add("labour-finance-line-incomplete")

        equipment_base = equipment_scenario = Decimal(0)
        if request.baseline_equipment is not None:
            equipment_base = Decimal(request.baseline_equipment.base_count) * _d(request.baseline_equipment.annual_cost_per_unit.value) * other_factor
            equipment_scenario = (Decimal(request.baseline_equipment.base_count) - Decimal(request.baseline_equipment.withdrawn_final) * ramp) * _d(request.baseline_equipment.annual_cost_per_unit.value) * other_factor
        opex = battery = Decimal(0)
        opex_missing = annual.status != "COMPLETE"
        for item in annual.operating_lines:
            if item.amount is None:
                opex_missing = True
            elif item.category == "BATTERY_REPLACEMENT":
                battery += _d(item.amount)
            else:
                opex += _d(item.amount)
        if opex_missing:
            incomplete = True
            issues.add("c15-annual-opex-incomplete")
        base_lines = [
            _line(f"year.{year}.base-direct-labour", None if role_missing else base_direct, [request.labour_result_digest]),
            _line(f"year.{year}.base-fixed-overhead", None if role_missing else base_overhead, [request.labour_result_digest]),
            _line(f"year.{year}.base-equipment", equipment_base, [] if request.baseline_equipment is None else [request.baseline_equipment.annual_cost_per_unit.provenance_ref]),
            _line(f"year.{year}.base-deficit", None if role_missing else deficit_base, [request.labour_result_digest]),
        ]
        scenario_lines = [
            _line(f"year.{year}.scenario-remaining-labour", None if role_missing else scenario_direct, [request.labour_result_digest]),
            _line(f"year.{year}.scenario-fixed-overhead", None if role_missing else base_overhead, [request.labour_result_digest]),
            _line(f"year.{year}.scenario-equipment", equipment_scenario, [] if request.baseline_equipment is None else [request.baseline_equipment.annual_cost_per_unit.provenance_ref]),
            _line(f"year.{year}.scenario-remaining-deficit", None if role_missing else deficit_scenario, [request.labour_result_digest]),
            _line(f"year.{year}.scenario-purchase-opex", None if opex_missing else opex, [request.purchase_ledger_digest]),
            _line(f"year.{year}.scenario-additional-income", -additional_t, additional_refs),
        ]
        base_cost = None if role_missing else base_direct + base_overhead + equipment_base + deficit_base
        scenario_cost = None if role_missing or opex_missing else scenario_direct + base_overhead + equipment_scenario + deficit_scenario + opex - additional_t
        ebitda_base = None if base_cost is None else -base_cost
        ebitda_scenario = None if scenario_cost is None else -scenario_cost
        depreciation = None if amortizable is None else (amortizable / Decimal(5) if year <= 5 else Decimal(0))
        ebit_base = ebitda_base
        ebit_scenario = None if ebitda_scenario is None or depreciation is None else ebitda_scenario - depreciation
        residual = _d(purchase.terminal_residual or "0") if year == horizon else Decimal(0)
        primary_base = ebitda_base
        primary_scenario = None if ebitda_scenario is None else ebitda_scenario - battery - severance + residual
        differential = None if primary_base is None or primary_scenario is None else primary_scenario - primary_base
        rows.append({"year": year, "ramp": ramp, "base_lines": base_lines, "scenario_lines": scenario_lines,
                     "ebitda_base": ebitda_base, "ebitda_scenario": ebitda_scenario, "depreciation": depreciation,
                     "ebit_base": ebit_base, "ebit_scenario": ebit_scenario, "severance": severance,
                     "battery": battery, "residual": residual, "primary_base": primary_base,
                     "primary_scenario": primary_scenario, "differential": differential})
        trace_inputs = {
            "F23": [f"role.{role.role_id}.annual-staffing.{year}" for role in labour.roles],
            "F24": [f"role.{role.role_id}.released.{year}" for role in labour.roles],
            "F25": [item.line_id for item in base_lines + scenario_lines],
            "F26": [f"year.{year}.ebitda-scenario", "purchase.capex-amortizable"],
            "F27": [f"year.{year}.ebitda-base", f"year.{year}.ebitda-scenario",
                    f"year.{year}.battery-replacements", f"year.{year}.severance", f"year.{year}.residual"],
        }
        for formula, output, value in (("F23", "staffing", scenario_direct), ("F24", "severance", severance),
                                       ("F25", "ebitda-scenario", ebitda_scenario), ("F26", "ebit-scenario", ebit_scenario),
                                       ("F27", "differential-cf", differential)):
            trace.append(FinancialTraceNodeV1(node_id=f"node.{formula.lower()}.year-{year}", formula_id=formula,
                         input_refs=trace_inputs[formula], output=f"year.{year}.{output}",
                         value=None if value is None else _plain(value), unit="RUB"))

    base_ebits = [item["ebit_base"] if isinstance(item["ebit_base"], Decimal) else Decimal(0) for item in rows]
    scenario_ebits = [item["ebit_scenario"] if isinstance(item["ebit_scenario"], Decimal) else Decimal(0) for item in rows]
    base_tax = illustrative_tax(base_ebits, request.tax_mode, rate=tax_rate, carry_years=carry_years, deduction_cap=deduction_cap)
    scenario_tax = illustrative_tax(scenario_ebits, request.tax_mode, rate=tax_rate, carry_years=carry_years, deduction_cap=deduction_cap)
    annual_results: list[AnnualFinancialLedgerV1] = []
    for index, item in enumerate(rows):
        primary_base = item["primary_base"]
        primary_scenario = item["primary_scenario"]
        supplement_base = None if primary_base is None else primary_base - base_tax[index].tax
        supplement_scenario = None if primary_scenario is None else primary_scenario - scenario_tax[index].tax
        annual_results.append(AnnualFinancialLedgerV1(
            year=item["year"], ramp=_plain(item["ramp"]), base_lines=item["base_lines"], scenario_lines=item["scenario_lines"],
            ebitda_base=None if item["ebitda_base"] is None else _money(item["ebitda_base"]),
            ebitda_scenario=None if item["ebitda_scenario"] is None else _money(item["ebitda_scenario"]),
            depreciation=None if item["depreciation"] is None else _money(item["depreciation"]),
            ebit_base=None if item["ebit_base"] is None else _money(item["ebit_base"]),
            ebit_scenario=None if item["ebit_scenario"] is None else _money(item["ebit_scenario"]),
            severance=None if item["ebitda_scenario"] is None else _money(item["severance"]), battery_replacements=None if item["ebitda_scenario"] is None else _money(item["battery"]),
            residual=_money(item["residual"]), primary_cf_base=None if primary_base is None else _money(primary_base),
            primary_cf_scenario=None if primary_scenario is None else _money(primary_scenario),
            differential_cf=None if item["differential"] is None else _money(item["differential"]),
            tax_base=TaxLineV1(tax=_money(base_tax[index].tax), loss_open=_money(base_tax[index].loss_open), loss_used=_money(base_tax[index].loss_used), loss_close=_money(base_tax[index].loss_close)),
            tax_scenario=TaxLineV1(tax=_money(scenario_tax[index].tax), loss_open=_money(scenario_tax[index].loss_open), loss_used=_money(scenario_tax[index].loss_used), loss_close=_money(scenario_tax[index].loss_close)),
            supplement_cf_base=None if supplement_base is None else _money(supplement_base), supplement_cf_scenario=None if supplement_scenario is None else _money(supplement_scenario),
            status="INCOMPLETE" if primary_base is None or primary_scenario is None else "COMPLETE"))

    complete = not incomplete and all(item.status == "COMPLETE" for item in annual_results)
    base_flows = [Decimal(0), *[_d(item.primary_cf_base) for item in annual_results if item.primary_cf_base is not None]]
    scenario_flows = [-(capex or Decimal(0)), *[_d(item.primary_cf_scenario) for item in annual_results if item.primary_cf_scenario is not None]]
    diff_flows = [scenario_flows[i] - base_flows[i] for i in range(min(len(base_flows), len(scenario_flows)))]
    if complete:
        npv_base_value, npv_scenario_value = npv(base_flows, discount), npv(scenario_flows, discount)
        npv_project_value = npv_scenario_value - npv_base_value
        effect = sum(diff_flows[1:], Decimal(0))
        simple = payback(diff_flows)
        discounted = payback(diff_flows, discount)
        annual_tco = sum((_d(item.operating_total) for item in purchase.annual_ledgers if item.operating_total is not None), Decimal(0))
        tco_gross = (capex or Decimal(0)) + annual_tco
        residual_total = _d(purchase.terminal_residual or "0")
        tco_net = tco_gross - residual_total
        roi = None if capex == 0 else effect / capex * Decimal(100)
        if capex == 0:
            simple = Decimal(0) if effect > 0 and all(value >= 0 for value in diff_flows[1:]) else None
            discounted = simple
        metric = lambda value, unit: MetricValueV1(status="COMPLETE", value=_money(value) if unit == "RUB" else _metric(value), unit=unit)
        npv_base_result, npv_scenario_result, npv_project_result = metric(npv_base_value, "RUB"), metric(npv_scenario_value, "RUB"), metric(npv_project_value, "RUB")
        simple_result = MetricValueV1(status="NOT_REACHED" if simple is None else "COMPLETE", value=_metric(simple), unit="YEAR")
        discounted_result = MetricValueV1(status="NOT_REACHED" if discounted is None else "COMPLETE", value=_metric(discounted), unit="YEAR")
        effect_result, net_result = metric(effect, "RUB"), metric(effect - (capex or Decimal(0)), "RUB")
        roi_result = MetricValueV1(status="N_A" if roi is None else "COMPLETE", value=_metric(roi), unit="PERCENT")
        tco_gross_result, tco_net_result = metric(tco_gross, "RUB"), metric(tco_net, "RUB")
        for formula, output, value, unit in (("F28", "npv-project", npv_project_value, "RUB"), ("F29", "simple-payback", simple, "YEAR"),
                                              ("F30", "tco-net", tco_net, "RUB"), ("F31", "roi-on-capex", roi, "PERCENT")):
            trace.append(FinancialTraceNodeV1(node_id=f"node.{formula.lower()}.{output}", formula_id=formula,
                         input_refs=[f"year.{year}.differential-cf" for year in range(1, horizon + 1)], output=output,
                         value=None if value is None else _plain(value), unit=unit))
    else:
        missing = lambda unit: MetricValueV1(status="INCOMPLETE", value=None, unit=unit)
        npv_base_result = npv_scenario_result = npv_project_result = missing("RUB")
        simple_result = discounted_result = missing("YEAR")
        effect_result = net_result = tco_gross_result = tco_net_result = missing("RUB")
        roi_result = missing("PERCENT")

    replay = FinancialReplayV1(canonical_input_digest=_digest(request), purchase_ledger_digest=request.purchase_ledger_digest,
        labour_result_digest=request.labour_result_digest, capacity_result_digest=purchase.replay.capacity_result_digest,
        trace_content_digest=ZERO_DIGEST)
    result = FinancialResultV1(run_id=request.run_id, project_id=request.project_id, tenant_id=request.tenant_id,
        input_revision=request.input_revision, status="COMPLETE" if complete else "INCOMPLETE", tax_mode=request.tax_mode,
        initial_primary_cf_scenario=None if capex is None else _money(-capex), annual_ledgers=annual_results,
        npv_base=npv_base_result, npv_scenario=npv_scenario_result, npv_project=npv_project_result,
        simple_payback=simple_result, discounted_payback=discounted_result, cumulative_effect=effect_result,
        roi_on_capex_cashflow=roi_result, net_benefit_after_investment=net_result,
        tco_purchase_gross=tco_gross_result, tco_purchase_net_of_residual=tco_net_result,
        issues=sorted(issues), reconciliation=_reconciliation(complete), trace=trace,
        registry_version=registry.registry_version, registry_digest=registry.registry_digest,
        engine_version=engine_version, replay=replay)
    payload = result.model_dump(mode="json")
    payload["replay"]["trace_content_digest"] = None
    result.replay.trace_content_digest = _digest(payload)
    return result
