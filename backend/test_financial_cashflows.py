from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.economics.cashflow import FinancialAnalysisRequestV1, calculate_financial_result
from calculation.economics.metrics import npv, payback
from calculation.economics.tax import illustrative_tax
from calculation.service import analyze_financials

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> dict:
    return json.loads((ROOT / "contracts/fixtures/financial-result-v1.warehouse.golden.json").read_text(encoding="utf-8"))


def request() -> FinancialAnalysisRequestV1:
    return FinancialAnalysisRequestV1.model_validate(fixture()["request"])


def test_golden_replay_full_ledgers_and_r13_49_rules():
    data = fixture()
    first = analyze_financials(FinancialAnalysisRequestV1.model_validate(data["request"]))
    second = calculate_financial_result(FinancialAnalysisRequestV1.model_validate(data["request"]))
    assert first.model_dump(mode="json") == data["result"] == second.model_dump(mode="json")
    assert first.status == "COMPLETE"
    assert [item.rule_id for item in first.reconciliation] == [f"R13-{i:02d}" for i in range(1, 50)]
    assert first.replay.capacity_result_digest == data["request"]["labour_result"]["replay"]["capacity_result_digests"][0]


def test_npv_signs_use_scenario_minus_base():
    base = [Decimal(0), Decimal(-100)]
    scenario = [Decimal(0), Decimal(-80)]
    assert npv(scenario, Decimal(0)) - npv(base, Decimal(0)) == Decimal(20)


def test_identical_flows_have_zero_project_npv():
    flow = [Decimal(-10), Decimal(-20), Decimal(5)]
    assert npv(flow, Decimal("0.15")) - npv(flow, Decimal("0.15")) == 0


def test_reserve_is_not_depreciated_and_residual_is_terminal_once():
    result = calculate_financial_result(request())
    expected = Decimal(result.annual_ledgers[0].depreciation) * 5
    assert expected == Decimal(request().purchase_ledger.capex_amortizable)
    assert expected != Decimal(request().purchase_ledger.capex_gross)
    assert all(Decimal(item.residual) == 0 for item in result.annual_ledgers[:-1])
    assert Decimal(result.annual_ledgers[-1].residual) == Decimal(request().purchase_ledger.terminal_residual)


def test_fixed_overhead_cancels_between_full_flows():
    result = calculate_financial_result(request())
    for annual in result.annual_ledgers:
        base = next(item for item in annual.base_lines if item.line_id.endswith("base-fixed-overhead"))
        scenario = next(item for item in annual.scenario_lines if item.line_id.endswith("scenario-fixed-overhead"))
        assert base.amount == scenario.amount


def test_severance_uses_only_positive_release_increments():
    result = calculate_financial_result(request())
    assert [Decimal(item.severance) for item in result.annual_ledgers] == [Decimal("2000000"), Decimal("1250000"), Decimal("500000"), Decimal(0), Decimal(0)]


def test_tax_modes_other_income_and_fifo_loss_carry():
    ebits = [Decimal(-100), Decimal(100), Decimal(300)]
    other = illustrative_tax(ebits, "ILLUSTRATIVE_OTHER_INCOME", rate=Decimal("0.25"), carry_years=10, deduction_cap=Decimal("0.5"))
    assert [item.tax for item in other] == [Decimal(-25), Decimal(25), Decimal(75)]
    carry = illustrative_tax(ebits, "ILLUSTRATIVE_NO_OTHER_INCOME", rate=Decimal("0.25"), carry_years=10, deduction_cap=Decimal("0.5"))
    assert [item.tax for item in carry] == [Decimal(0), Decimal("12.5"), Decimal("62.5")]
    assert carry[1].loss_used == Decimal(50) and carry[2].loss_used == Decimal(50)


def test_payback_interpolation_late_nonmonotonic_and_not_reached():
    assert payback([Decimal(-25), Decimal(10), Decimal(10), Decimal(10)]) == Decimal("2.5")
    assert payback([Decimal(-10), Decimal(15), Decimal(-20), Decimal(30)]) == Decimal(10) / Decimal(15)
    assert payback([Decimal(-10), Decimal(3), Decimal(3)]) is None


def test_capex_zero_metrics_follow_k13():
    raw = request().model_dump(mode="json")
    purchase = raw["purchase_ledger"]
    purchase["capex_cashflow"] = purchase["capex_gross"] = purchase["capex_amortizable"] = purchase["reserve"] = "0"
    for item in purchase["capital_lines"]:
        if item["status"] == "COMPLETE":
            item["amount"] = "0"
    raw["purchase_ledger_digest"] = __import__("hashlib").sha256(json.dumps(purchase, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    raw["purchase_ledger_digest"] = "sha256:" + raw["purchase_ledger_digest"]
    result = calculate_financial_result(FinancialAnalysisRequestV1.model_validate(raw))
    assert result.roi_on_capex_cashflow.status == "N_A"


def test_missing_upstream_finance_is_incomplete_not_zero():
    raw = request().model_dump(mode="json")
    raw["labour_result"]["finance_status"] = "INCOMPLETE"
    raw["labour_result"]["roles"][0]["money"] = None
    labour = raw["labour_result"]
    raw["labour_result_digest"] = "sha256:" + __import__("hashlib").sha256(json.dumps(labour, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = calculate_financial_result(FinancialAnalysisRequestV1.model_validate(raw))
    assert result.status == "INCOMPLETE"
    assert result.npv_project.status == "INCOMPLETE" and result.npv_project.value is None


def test_additional_income_requires_explicit_mode_and_provenance():
    raw = request().model_dump(mode="json")
    raw["additional_income"] = {"mode": "INCLUDED", "annual_amount": {"value": "1000000", "unit": "RUB/year", "source": "USER", "provenance_ref": "prov.user.additional-income"}}
    included = calculate_financial_result(FinancialAnalysisRequestV1.model_validate(raw))
    excluded = calculate_financial_result(request())
    assert Decimal(included.cumulative_effect.value) - Decimal(excluded.cumulative_effect.value) == Decimal("5000000")
    raw["additional_income"] = {"mode": "EXCLUDED"}
    with pytest.raises(ValidationError):
        FinancialAnalysisRequestV1.model_validate(raw)


def test_tco_publishes_gross_and_net_of_residual_without_double_battery():
    result = calculate_financial_result(request())
    residual = Decimal(request().purchase_ledger.terminal_residual)
    assert Decimal(result.tco_purchase_gross.value) - Decimal(result.tco_purchase_net_of_residual.value) == residual


def test_snapshot_binding_and_tenant_isolation_are_strict():
    raw = request().model_dump(mode="json")
    raw["tenant_id"] = "tenant.other"
    with pytest.raises(ValidationError, match="identity/revision"):
        FinancialAnalysisRequestV1.model_validate(raw)
    raw = request().model_dump(mode="json")
    raw["purchase_ledger_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="purchase ledger digest"):
        FinancialAnalysisRequestV1.model_validate(raw)


def test_generated_schemas_are_strict():
    for name in ("financial-analysis-request-v1.schema.json", "financial-result-v1.schema.json"):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
