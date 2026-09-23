"""C17 RaaS full cash-flow ledger (F32) over immutable C16 inputs."""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from calculation.economics.cashflow import (
    FinancialAnalysisRequestV1,
    FinancialResultV1,
    MetricValueV1,
    TaxLineV1,
    _digest,
    calculate_financial_result,
)
from calculation.economics.metrics import npv, payback
from calculation.economics.purchase import SourcedValueV1
from calculation.economics.tax import illustrative_tax
from calculation.registry import CalculationParameterRegistryV1, load_registry
from calculation_contracts import Digest, StableId, StrictContractModel
from procurement.contracts import ProcurementReportV1, RaasTermsV1

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]
ZERO_DIGEST = "sha256:" + "0" * 64


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _metric(value: Decimal | None) -> str | None:
    return None if value is None else format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _hash(value: object) -> str:
    if isinstance(value, StrictContractModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class RaasAnalysisRequestV1(StrictContractModel):
    schema_version: Literal["raas-analysis-request-v1"] = "raas-analysis-request-v1"
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    procurement: ProcurementReportV1
    purchase_comparator_request: FinancialAnalysisRequestV1
    purchase_comparator_result: FinancialResultV1
    comparator_request_digest: Digest
    comparator_result_digest: Digest
    tariff_base_price: SourcedValueV1 | None = None

    @model_validator(mode="after")
    def bind(self) -> "RaasAnalysisRequestV1":
        if self.procurement.acquisition != "RAAS":
            raise ValueError("C17 requires RAAS procurement report")
        for snapshot in (self.purchase_comparator_request, self.purchase_comparator_result):
            if (snapshot.project_id, snapshot.tenant_id, snapshot.input_revision) != (
                    self.project_id, self.tenant_id, self.input_revision):
                raise ValueError("C16 comparator identity/revision mismatch")
        if self.comparator_request_digest != _hash(self.purchase_comparator_request):
            raise ValueError("C16 request digest mismatch")
        if self.comparator_result_digest != _hash(self.purchase_comparator_result):
            raise ValueError("C16 result digest mismatch")
        if self.purchase_comparator_result.replay.canonical_input_digest != _digest(self.purchase_comparator_request):
            raise ValueError("C16 replay binding mismatch")
        return self


class RaasZeroedLineV1(StrictContractModel):
    line_id: StableId
    area: Literal["HARDWARE", "CHARGING", "INTEGRATION", "MAINTENANCE", "SOFTWARE", "BATTERY", "RESIDUAL"]
    status: Literal["ZEROED", "INCOMPLETE"]
    amount: Literal["0"] | None
    reason_code: Literal["VENDOR_RESPONSIBILITY", "RAAS_NO_OWNED_ASSET", "RESPONSIBILITY_NOT_VENDOR"]
    responsible_party: Literal["CUSTOMER", "VENDOR", "INTEGRATOR", "SHARED", "UNKNOWN"]
    source_refs: list[StableId]


class RaasAnnualLedgerV1(StrictContractModel):
    year: Annotated[int, Field(ge=1, le=15)]
    ramp: DecimalString
    customer_opex: DecimalString | None
    raas_payment: DecimalString | None
    ebitda_base: DecimalString | None
    ebitda_scenario: DecimalString | None
    depreciation: DecimalString | None
    ebit_base: DecimalString | None
    ebit_scenario: DecimalString | None
    severance: DecimalString | None
    primary_cf_base: DecimalString | None
    primary_cf_scenario: DecimalString | None
    differential_cf: DecimalString | None
    tax_base: TaxLineV1 | None
    tax_scenario: TaxLineV1 | None
    supplement_cf_base: DecimalString | None
    supplement_cf_scenario: DecimalString | None
    status: Literal["COMPLETE", "INCOMPLETE"]


class RaasTraceNodeV1(StrictContractModel):
    node_id: StableId
    formula_id: Literal["F32"]
    input_refs: list[str]
    output: StableId
    value: DecimalString | None
    unit: Literal["RUB", "1"]
    reason_code: StableId | None = None


class RaasReplayV1(StrictContractModel):
    canonical_input_digest: Digest
    comparator_request_digest: Digest
    comparator_result_digest: Digest
    procurement_digest: Digest
    capacity_result_digest: Digest
    trace_content_digest: Digest


class RaasFinancialResultV1(StrictContractModel):
    schema_version: Literal["raas-financial-result-v1"] = "raas-financial-result-v1"
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    status: Literal["COMPLETE", "INCOMPLETE"]
    fleet_count: Annotated[int, Field(ge=0)]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    deployment_mode: Literal["ALL_FLEET", "PHASED"] | None
    infrastructure_owner: Literal["CUSTOMER", "VENDOR", "INTEGRATOR", "SHARED", "UNKNOWN"]
    capex_infrastructure_gross: DecimalString | None
    capex_infrastructure_amortizable: DecimalString | None
    initial_primary_cf_scenario: DecimalString | None
    zeroed_lines: list[RaasZeroedLineV1]
    annual_ledgers: list[RaasAnnualLedgerV1]
    npv_base: MetricValueV1
    npv_scenario: MetricValueV1
    npv_project: MetricValueV1
    simple_payback: MetricValueV1
    discounted_payback: MetricValueV1
    cumulative_effect: MetricValueV1
    roi_on_raas_tco: MetricValueV1
    tco_raas: MetricValueV1
    issues: list[StableId]
    trace: list[RaasTraceNodeV1]
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    registry_digest: Digest
    commercial_policy_version: Literal["hackathon-commercial-policy-v1"] = "hackathon-commercial-policy-v1"
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"] = "hackathon-calculation-policy-v1"
    policy_overlay_version: Literal["hackathon-calculation-policy-v1+v2bc-c17"] = "hackathon-calculation-policy-v1+v2bc-c17"
    engine_version: Literal["raas-cashflows-v1"] = "raas-cashflows-v1"
    replay: RaasReplayV1


def _responsibility(request: RaasAnalysisRequestV1, area: str) -> str:
    values = [item.responsible_party for item in request.procurement.responsibilities if item.area == area]
    return values[0] if len(values) == 1 else "UNKNOWN"


def _capital_infrastructure(request: RaasAnalysisRequestV1, owner: str) -> tuple[Decimal | None, Decimal | None]:
    if owner == "VENDOR":
        return Decimal(0), Decimal(0)
    if owner != "CUSTOMER":
        return None, None
    purchase = request.purchase_comparator_request.purchase_ledger
    lines = [line for line in purchase.capital_lines if line.category == "INFRASTRUCTURE"]
    if any(line.amount is None for line in lines):
        return None, None
    base = sum((_d(line.amount or "0") for line in lines if line.status == "COMPLETE"), Decimal(0))
    # Resolve exact reserve by ratio from the complete C15 ledger, never by a hidden default.
    if purchase.capex_amortizable is None or purchase.reserve is None:
        return None, None
    amortizable = _d(purchase.capex_amortizable)
    reserve = _d(purchase.reserve)
    rate = Decimal(0) if amortizable == 0 else reserve / amortizable
    return base * (Decimal(1) + rate), base


def calculate_raas_financials(request: RaasAnalysisRequestV1,
                              registry: CalculationParameterRegistryV1 | None = None) -> RaasFinancialResultV1:
    registry = registry or load_registry()
    c16 = request.purchase_comparator_result
    comparator = request.purchase_comparator_request
    purchase = comparator.purchase_ledger
    terms = request.procurement.terms if isinstance(request.procurement.terms, RaasTermsV1) else None
    issues: set[str] = set()
    owner = _responsibility(request, "INFRASTRUCTURE")
    capex_gross, capex_amortizable = _capital_infrastructure(request, owner)
    if capex_gross is None:
        issues.add("raas-infrastructure-responsibility-incomplete")
    if terms is None:
        issues.add("raas-terms-missing")
    elif terms.renewal != "SAME_TERMS_TO_HORIZON" and terms.contract_months < len(c16.annual_ledgers) * 12:
        issues.add("raas-horizon-not-covered")
    if terms is not None and terms.buyout is not None and _d(terms.buyout.raw_amount) != 0:
        issues.add("raas-nonzero-buyout-outside-policy")

    tariff_monthly: Decimal | None = None
    if terms is not None:
        if terms.tariff_basis.kind == "PERCENT_BASE":
            if request.tariff_base_price is None:
                issues.add("raas-tariff-base-missing")
            else:
                tariff_monthly = _d(request.tariff_base_price.value) * _d(terms.tariff_basis.rate)
        elif terms.tariff_basis.kind in {"FIXED_TOTAL", "PER_ROBOT"}:
            money = terms.tariff_basis.money
            if money.currency == "RUB" and money.tax_basis == "CASH_GROSS_RUB":
                tariff_monthly = _d(money.raw_amount)
            else:
                issues.add("raas-tariff-unresolved")
    fleet = purchase.fleet_count
    zeroed: list[RaasZeroedLineV1] = []
    for line_id, area in (("raas.zero.robot-capex", "HARDWARE"), ("raas.zero.charger-capex", "CHARGING"),
                          ("raas.zero.integration-per-robot", "INTEGRATION"), ("raas.zero.service", "MAINTENANCE"),
                          ("raas.zero.software", "SOFTWARE"), ("raas.zero.battery", "BATTERY")):
        party = _responsibility(request, area)
        valid = party == "VENDOR"
        if not valid:
            issues.add(f"raas-{area.lower()}-responsibility-not-vendor")
        zeroed.append(RaasZeroedLineV1(line_id=line_id, area=area, status="ZEROED" if valid else "INCOMPLETE",
            amount="0" if valid else None, reason_code="VENDOR_RESPONSIBILITY" if valid else "RESPONSIBILITY_NOT_VENDOR",
            responsible_party=party, source_refs=["policy.k21"]))
    zeroed.append(RaasZeroedLineV1(line_id="raas.zero.residual", area="RESIDUAL", status="ZEROED", amount="0",
        reason_code="RAAS_NO_OWNED_ASSET", responsible_party="VENDOR", source_refs=["policy.k21"]))
    trace = [RaasTraceNodeV1(node_id=f"node.f32.{item.line_id}", formula_id="F32", input_refs=item.source_refs,
        output=item.line_id, value=item.amount, unit="RUB", reason_code=item.reason_code.lower().replace("_", "-")) for item in zeroed]

    tax_rate = _d(registry.by_id("finance.tax.illustrative-rate").value)
    carry_years = int(_d(registry.by_id("finance.tax.loss-carry-years").value))
    deduction_cap = _d(registry.by_id("finance.tax.loss-deduction-cap").value)
    base_ebit: list[Decimal] = []
    scenario_ebit: list[Decimal] = []
    intermediate: list[dict] = []
    for index, source in enumerate(c16.annual_ledgers):
        year = source.year
        ramp = _d(source.ramp)
        customer_categories = {"ENERGY", "COMMUNICATION", "CONTROL_OPERATOR"}
        c15 = purchase.annual_ledgers[index]
        selected = [line for line in c15.operating_lines if line.category in customer_categories]
        customer_opex = None if any(line.amount is None for line in selected) else sum((_d(line.amount or "0") for line in selected), Decimal(0))
        if customer_opex is None:
            issues.add("raas-customer-opex-incomplete")
        payment = None
        if tariff_monthly is not None and terms is not None:
            quantity = Decimal(fleet) if terms.billing_basis == "PER_ROBOT_MONTH" else Decimal(1)
            deployment = ramp if terms.deployment_mode == "PHASED" else Decimal(1)
            payment = quantity * tariff_monthly * Decimal(12) * deployment
        base_cost_lines = [line.amount for line in source.base_lines]
        base_cost = None if any(value is None for value in base_cost_lines) else sum((_d(value) for value in base_cost_lines), Decimal(0))
        scenario_non_robot = Decimal(0)
        for line in source.scenario_lines:
            if line.line_id.endswith("scenario-purchase-opex"):
                continue
            if line.amount is None:
                scenario_non_robot = None
                break
            scenario_non_robot += _d(line.amount)
        ebitda_base = None if base_cost is None else -base_cost
        ebitda_scenario = None if scenario_non_robot is None or customer_opex is None or payment is None else -(scenario_non_robot + customer_opex + payment)
        depreciation = None if capex_amortizable is None else (capex_amortizable / Decimal(5) if year <= 5 else Decimal(0))
        ebit_scenario = None if ebitda_scenario is None or depreciation is None else ebitda_scenario - depreciation
        severance = None if source.severance is None else _d(source.severance)
        cf_scenario = None if ebitda_scenario is None or severance is None else ebitda_scenario - severance
        cf_base = None if source.primary_cf_base is None else _d(source.primary_cf_base)
        base_ebit.append(Decimal(0) if ebitda_base is None else ebitda_base)
        scenario_ebit.append(Decimal(0) if ebit_scenario is None else ebit_scenario)
        intermediate.append({"source": source, "customer": customer_opex, "payment": payment, "base": ebitda_base,
            "scenario": ebitda_scenario, "depreciation": depreciation, "ebit_scenario": ebit_scenario,
            "severance": severance, "cf_base": cf_base, "cf_scenario": cf_scenario})
        trace.append(RaasTraceNodeV1(node_id=f"node.f32.payment.year-{year}", formula_id="F32",
            input_refs=["raas.tariff", "fleet_count", f"ramp.year-{year}"], output=f"year.{year}.raas-payment",
            value=None if payment is None else _money(payment), unit="RUB"))

    base_taxes = illustrative_tax(base_ebit, comparator.tax_mode, rate=tax_rate, carry_years=carry_years, deduction_cap=deduction_cap)
    scenario_taxes = illustrative_tax(scenario_ebit, comparator.tax_mode, rate=tax_rate, carry_years=carry_years, deduction_cap=deduction_cap)
    annual: list[RaasAnnualLedgerV1] = []
    for index, row in enumerate(intermediate):
        source = row["source"]
        diff = None if row["cf_base"] is None or row["cf_scenario"] is None else row["cf_scenario"] - row["cf_base"]
        sup_base = None if row["cf_base"] is None else row["cf_base"] - base_taxes[index].tax
        sup_scenario = None if row["cf_scenario"] is None else row["cf_scenario"] - scenario_taxes[index].tax
        complete = all(row[key] is not None for key in ("customer", "payment", "base", "scenario", "depreciation", "ebit_scenario", "severance", "cf_base", "cf_scenario"))
        annual.append(RaasAnnualLedgerV1(year=source.year, ramp=source.ramp,
            customer_opex=None if row["customer"] is None else _money(row["customer"]),
            raas_payment=None if row["payment"] is None else _money(row["payment"]),
            ebitda_base=None if row["base"] is None else _money(row["base"]), ebitda_scenario=None if row["scenario"] is None else _money(row["scenario"]),
            depreciation=None if row["depreciation"] is None else _money(row["depreciation"]),
            ebit_base=None if row["base"] is None else _money(row["base"]), ebit_scenario=None if row["ebit_scenario"] is None else _money(row["ebit_scenario"]),
            severance=None if row["severance"] is None else _money(row["severance"]), primary_cf_base=None if row["cf_base"] is None else _money(row["cf_base"]),
            primary_cf_scenario=None if row["cf_scenario"] is None else _money(row["cf_scenario"]), differential_cf=None if diff is None else _money(diff),
            tax_base=TaxLineV1(tax=_money(base_taxes[index].tax), loss_open=_money(base_taxes[index].loss_open), loss_used=_money(base_taxes[index].loss_used), loss_close=_money(base_taxes[index].loss_close)),
            tax_scenario=TaxLineV1(tax=_money(scenario_taxes[index].tax), loss_open=_money(scenario_taxes[index].loss_open), loss_used=_money(scenario_taxes[index].loss_used), loss_close=_money(scenario_taxes[index].loss_close)),
            supplement_cf_base=None if sup_base is None else _money(sup_base), supplement_cf_scenario=None if sup_scenario is None else _money(sup_scenario),
            status="COMPLETE" if complete else "INCOMPLETE"))

    complete = not issues and all(item.status == "COMPLETE" for item in annual)
    missing = lambda unit: MetricValueV1(status="INCOMPLETE", value=None, unit=unit)
    if complete:
        initial = -(capex_gross or Decimal(0))
        base_flows = [Decimal(0), *[_d(item.primary_cf_base) for item in annual]]
        scenario_flows = [initial, *[_d(item.primary_cf_scenario) for item in annual]]
        diff = [scenario_flows[i] - base_flows[i] for i in range(len(base_flows))]
        discount = _d(comparator.discount_rate.value)
        n_base, n_scenario = npv(base_flows, discount), npv(scenario_flows, discount)
        effect = sum(diff[1:], Decimal(0))
        tco = (capex_gross or Decimal(0)) + sum((_d(item.customer_opex) + _d(item.raas_payment) for item in annual), Decimal(0))
        roi = None if tco == 0 else effect / tco * Decimal(100)
        simple, discounted = payback(diff), payback(diff, discount)
        rub = lambda value: MetricValueV1(status="COMPLETE", value=_money(value), unit="RUB")
        npv_base, npv_scenario, npv_project = rub(n_base), rub(n_scenario), rub(n_scenario - n_base)
        simple_result = MetricValueV1(status="NOT_REACHED" if simple is None else "COMPLETE", value=_metric(simple), unit="YEAR")
        discounted_result = MetricValueV1(status="NOT_REACHED" if discounted is None else "COMPLETE", value=_metric(discounted), unit="YEAR")
        effect_result, tco_result = rub(effect), rub(tco)
        roi_result = MetricValueV1(status="N_A" if roi is None else "COMPLETE", value=_metric(roi), unit="PERCENT")
    else:
        npv_base = npv_scenario = npv_project = effect_result = tco_result = missing("RUB")
        simple_result = discounted_result = missing("YEAR")
        roi_result = missing("PERCENT")

    replay = RaasReplayV1(canonical_input_digest=_hash(request), comparator_request_digest=request.comparator_request_digest,
        comparator_result_digest=request.comparator_result_digest, procurement_digest=_hash(request.procurement),
        capacity_result_digest=c16.replay.capacity_result_digest, trace_content_digest=ZERO_DIGEST)
    result = RaasFinancialResultV1(run_id=request.run_id, project_id=request.project_id, tenant_id=request.tenant_id,
        input_revision=request.input_revision, status="COMPLETE" if complete else "INCOMPLETE", fleet_count=fleet,
        uncertainty=request.uncertainty,
        deployment_mode=None if terms is None else terms.deployment_mode, infrastructure_owner=owner,
        capex_infrastructure_gross=None if capex_gross is None else _money(capex_gross),
        capex_infrastructure_amortizable=None if capex_amortizable is None else _money(capex_amortizable),
        initial_primary_cf_scenario=None if capex_gross is None else _money(-capex_gross), zeroed_lines=zeroed,
        annual_ledgers=annual, npv_base=npv_base, npv_scenario=npv_scenario, npv_project=npv_project,
        simple_payback=simple_result, discounted_payback=discounted_result, cumulative_effect=effect_result,
        roi_on_raas_tco=roi_result, tco_raas=tco_result, issues=sorted(issues), trace=trace,
        registry_version=registry.registry_version, registry_digest=registry.registry_digest, replay=replay)
    payload = result.model_dump(mode="json")
    payload["replay"]["trace_content_digest"] = None
    result.replay.trace_content_digest = _hash(payload)
    return result
