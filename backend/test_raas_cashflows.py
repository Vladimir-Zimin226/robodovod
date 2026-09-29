from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.economics.raas import RaasAnalysisRequestV1, calculate_raas_financials
from calculation.service import analyze_raas_financials

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> dict:
    return json.loads((ROOT / "contracts/fixtures/raas-financial-result-v1.warehouse.golden.json").read_text(encoding="utf-8"))


def request() -> RaasAnalysisRequestV1:
    return RaasAnalysisRequestV1.model_validate(fixture()["request"])


def redigest(raw: dict) -> None:
    from calculation.economics.raas import _hash
    raw["comparator_request_digest"] = _hash(raw["purchase_comparator_request"])
    raw["comparator_result_digest"] = _hash(raw["purchase_comparator_result"])


def test_golden_is_strict_replayable_and_complete():
    data = fixture()
    first = analyze_raas_financials(RaasAnalysisRequestV1.model_validate(data["request"]))
    second = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(data["request"]))
    assert first.model_dump(mode="json") == data["result"] == second.model_dump(mode="json")
    assert first.status == "COMPLETE" and not first.issues
    assert first.infrastructure_owner == "CUSTOMER"
    assert first.fleet_count == data["request"]["purchase_comparator_request"]["purchase_ledger"]["fleet_count"]


@pytest.mark.parametrize("uncertainty", ["PESSIMISTIC", "BASE", "OPTIMISTIC"])
@pytest.mark.parametrize("mode", ["ALL_FLEET", "PHASED"])
def test_three_uncertainties_and_both_deployment_modes(uncertainty: str, mode: str):
    raw = request().model_dump(mode="json")
    raw["uncertainty"] = uncertainty
    raw["procurement"]["terms"]["deployment_mode"] = mode
    result = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    assert result.status == "COMPLETE"
    full = Decimal(21) * Decimal(3000000) * Decimal("0.02") * 12
    expected = full if mode == "ALL_FLEET" else full * Decimal(result.annual_ledgers[0].ramp)
    assert Decimal(result.annual_ledgers[0].raas_payment) == expected


def test_payment_is_a_separate_line_and_counted_once_in_tco():
    result = calculate_raas_financials(request())
    payments = sum((Decimal(item.raas_payment) for item in result.annual_ledgers), Decimal(0))
    customer = sum((Decimal(item.customer_opex) for item in result.annual_ledgers), Decimal(0))
    capex = Decimal(result.capex_infrastructure_gross)
    assert Decimal(result.tco_raas.value) == capex + customer + payments


def test_raas_inherits_indexed_additional_income_from_v3_comparator():
    from calculation.economics.cashflow import FinancialAnalysisRequestV1, calculate_financial_result

    raw = request().model_dump(mode="json")
    comparator = raw["purchase_comparator_request"]
    excluded_c16 = calculate_financial_result(FinancialAnalysisRequestV1.model_validate(comparator), engine_version="full-cashflows-reconciliation-v3")
    raw["purchase_comparator_result"] = excluded_c16.model_dump(mode="json")
    redigest(raw)
    excluded = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    comparator["additional_income"] = {"mode": "INCLUDED", "annual_amount": {"value": "1000000", "unit": "RUB/year", "source": "USER", "provenance_ref": "prov.user.additional-income"}}
    c16_request = FinancialAnalysisRequestV1.model_validate(comparator)
    raw["purchase_comparator_request"] = c16_request.model_dump(mode="json")
    c16 = calculate_financial_result(c16_request, engine_version="full-cashflows-reconciliation-v3")
    raw["purchase_comparator_result"] = c16.model_dump(mode="json")
    redigest(raw)
    import jsonschema
    jsonschema.validate(raw, json.loads((ROOT / 'contracts/raas-analysis-request-v1.schema.json').read_text(encoding='utf-8')))
    included = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    assert included.status == "COMPLETE"
    for year, (old, new) in enumerate(zip(excluded.annual_ledgers, included.annual_ledgers), start=1):
        expected = Decimal("1000000") * Decimal("1.05") ** (year - 1)
        assert Decimal(new.ebitda_scenario) - Decimal(old.ebitda_scenario) == expected


def test_raas_zeroes_purchase_assets_battery_and_residual_explicitly():
    result = calculate_raas_financials(request())
    assert {item.area for item in result.zeroed_lines} == {"HARDWARE", "CHARGING", "INTEGRATION", "MAINTENANCE", "SOFTWARE", "BATTERY", "RESIDUAL"}
    assert all(item.amount == "0" and item.status == "ZEROED" and item.responsible_party == "VENDOR" for item in result.zeroed_lines)
    assert not any(hasattr(item, "residual") for item in result.annual_ledgers)


def test_warranty_is_irrelevant_to_raas_service_zeroing():
    req = request()
    service = [line for ledger in req.purchase_comparator_request.purchase_ledger.annual_ledgers
               for line in ledger.operating_lines if line.category == "SERVICE"]
    assert any(Decimal(line.amount or "0") > 0 for line in service)
    result = calculate_raas_financials(req)
    assert result.status == "COMPLETE"
    assert next(item for item in result.zeroed_lines if item.area == "MAINTENANCE").amount == "0"


def test_vendor_infrastructure_is_zero_customer_is_retained_unknown_is_incomplete():
    raw = request().model_dump(mode="json")
    infra = next(item for item in raw["procurement"]["responsibilities"] if item["area"] == "INFRASTRUCTURE")
    infra["responsible_party"] = "VENDOR"
    vendor = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    assert vendor.capex_infrastructure_gross == "0.00" and vendor.status == "COMPLETE"
    infra["responsible_party"] = "UNKNOWN"
    unknown = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    assert unknown.status == "INCOMPLETE" and unknown.capex_infrastructure_gross is None


def test_unknown_vendor_responsibility_never_zeroes_customer_cost():
    raw = request().model_dump(mode="json")
    maintenance = next(item for item in raw["procurement"]["responsibilities"] if item["area"] == "MAINTENANCE")
    maintenance["responsible_party"] = "UNKNOWN"
    result = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    line = next(item for item in result.zeroed_lines if item.area == "MAINTENANCE")
    assert result.status == "INCOMPLETE"
    assert line.status == "INCOMPLETE" and line.amount is None


def test_missing_terms_and_tariff_base_are_incomplete_not_zero():
    raw = request().model_dump(mode="json")
    raw["procurement"]["terms"] = None
    missing = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    assert missing.status == "INCOMPLETE"
    assert all(item.raas_payment is None for item in missing.annual_ledgers)
    raw = request().model_dump(mode="json")
    raw["tariff_base_price"] = None
    missing = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    assert "raas-tariff-base-missing" in missing.issues


def test_buyout_is_explicit_zero_and_not_silently_added():
    req = request()
    assert req.procurement.terms.buyout.raw_amount == "0"
    assert req.procurement.terms.buyout.zero_semantics == "EXCLUDED_BY_SCENARIO"
    result = calculate_raas_financials(req)
    assert result.initial_primary_cf_scenario == f"-{result.capex_infrastructure_gross}"


def test_nonzero_buyout_is_outside_k21_and_makes_metrics_incomplete():
    raw = request().model_dump(mode="json")
    raw["procurement"]["terms"]["buyout"]["raw_amount"] = "1000000"
    raw["procurement"]["terms"]["buyout"]["zero_semantics"] = None
    result = calculate_raas_financials(RaasAnalysisRequestV1.model_validate(raw))
    assert result.status == "INCOMPLETE"
    assert "raas-nonzero-buyout-outside-policy" in result.issues
    assert result.npv_project.status == "INCOMPLETE"


def test_tenant_revision_and_comparator_digests_are_bound():
    raw = request().model_dump(mode="json")
    raw["tenant_id"] = "tenant.other"
    with pytest.raises(ValidationError, match="identity/revision"):
        RaasAnalysisRequestV1.model_validate(raw)
    raw = request().model_dump(mode="json")
    raw["comparator_result_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="result digest"):
        RaasAnalysisRequestV1.model_validate(raw)


def test_generated_schemas_are_strict():
    for name in ("raas-analysis-request-v1.schema.json", "raas-financial-result-v1.schema.json"):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
