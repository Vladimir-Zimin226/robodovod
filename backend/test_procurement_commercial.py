from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from procurement.contracts import CommercialMoneyV1, ProcurementReportRequestV1, ProcurementReportV1
from procurement.resolver import resolve_procurement_report

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_commercial_contracts import (  # noqa: E402
    EVIDENCE_ID,
    MODEL_ID,
    OPTION_ID,
    POSITION_ID,
    build_request,
    expected_files,
    synthetic_snapshot,
)


def scope(model_id: str = MODEL_ID, position_id: str = POSITION_ID) -> dict:
    return {
        "model_id": model_id, "position_id": position_id,
        "procurement_option_id": OPTION_ID, "region": "RU", "boundary": "SCENARIO_BUDGET",
    }


def money(
    *, amount: str = "100", currency: str = "RUB", tax_basis: str = "CASH_GROSS_RUB",
    vat_rate: str | None = None, kind: str = "USER", valid_until: str | None = None,
    money_scope: dict | None = None, zero_semantics: str | None = None,
) -> dict:
    return {
        "raw_amount": amount, "currency": currency, "tax_basis": tax_basis,
        "vat_rate": vat_rate,
        "source": {
            "kind": kind, "source_id": "quote.test" if kind == "VENDOR_QUOTE" else "user.budget",
            "evidence_ids": [EVIDENCE_ID] if kind == "VENDOR_QUOTE" else [],
            "observed_on": "2026-09-01", "valid_until": valid_until,
        },
        "scope": money_scope or scope(), "zero_semantics": zero_semantics,
    }


def purchase_terms(value: dict) -> dict:
    return {
        "acquisition": "PURCHASE", "primary_price": value,
        "cost_lines": [],
        "responsibilities": [{"area": "MAINTENANCE", "responsible_party": "CUSTOMER", "evidence_ids": []}],
    }


def request_with(*terms: dict, assertions: list[dict] | None = None) -> ProcurementReportRequestV1:
    return ProcurementReportRequestV1.model_validate({
        "model_id": MODEL_ID, "position_id": POSITION_ID, "acquisition": "PURCHASE",
        "evaluation_date": "2026-09-23", "terms": list(terms),
        "currency_assumption": None, "assertions": assertions or [],
    })


def assertion(kind: str, *, state: str = "CONFIRMED", valid_until: str | None = "2026-12-31", risk: str | None = None) -> dict:
    return {
        "assertion_id": f"assertion.{kind.lower()}", "kind": kind, "state": state,
        "scope": scope(), "evidence_ids": [EVIDENCE_ID], "valid_until": valid_until,
        "risk_level": risk, "reason_code": f"evidence-{kind.lower()}",
    }


def trusted_snapshot(*assertions: dict, vendor_quote: dict | None = None):
    snapshot = synthetic_snapshot()
    position = snapshot.positions[0]
    option = replace(
        position.procurement_option,
        verified_quotes=() if vendor_quote is None else (vendor_quote,),
        procurement_assertions=tuple(assertions),
    )
    model = replace(position.model, procurement_options=(option,))
    position = replace(position, model=model, procurement_option=option)
    return replace(snapshot, models=(model,), positions=(position,))


def test_generated_contracts_budget_and_golden_report_are_exact():
    stale = [str(path.relative_to(ROOT)) for path, expected in expected_files() if not path.is_file() or path.read_bytes() != expected]
    assert stale == []
    raw_request = json.loads((ROOT / "data/commercial/synthetic-commercial-budget-v1.json").read_text(encoding="utf-8"))
    parsed_request = ProcurementReportRequestV1.model_validate(raw_request)
    assert {item.acquisition for item in parsed_request.terms} == {"PURCHASE", "RAAS"}
    raas = next(item for item in parsed_request.terms if item.acquisition == "RAAS")
    assert raas.tariff_basis.kind == "PERCENT_BASE" and raas.tariff_basis.rate == "0.02"
    raw_report = json.loads((ROOT / "contracts/fixtures/procurement-report-v1.synthetic-golden.json").read_text(encoding="utf-8"))
    report = ProcurementReportV1.model_validate(raw_report)
    assert report.money.raw_money.currency == "UNKNOWN"
    assert report.money.cash_gross_rub == "3000000.00"
    assert report.money.operation == "IDENTITY"
    assert report.procurement_status == "UNVERIFIED" and not report.procurement_ready


def test_net_money_requires_explicit_vat_and_never_guesses_a_rate():
    resolved = resolve_procurement_report(
        request_with(purchase_terms(money(tax_basis="NET_RUB", vat_rate="0.20"))),
        synthetic_snapshot(),
    )
    assert resolved.money.cash_gross_rub == "120.00"
    assert resolved.money.operation == "APPLY_EXPLICIT_VAT"
    blocked = resolve_procurement_report(
        request_with(purchase_terms(money(tax_basis="NET_RUB"))), synthetic_snapshot(),
    )
    assert blocked.money.status == "BLOCKED"
    assert "EXPLICIT_VAT_RATE_REQUIRED" in blocked.blockers


def test_wrong_currency_scope_and_ambiguous_sources_fail_closed():
    wrong_currency = resolve_procurement_report(
        request_with(purchase_terms(money(currency="USD"))), synthetic_snapshot(),
    )
    assert "UNSUPPORTED_CURRENCY" in wrong_currency.blockers
    mismatch = resolve_procurement_report(
        request_with(purchase_terms(money(money_scope=scope(model_id="model.other")))), synthetic_snapshot(),
    )
    assert "COMMERCIAL_SCOPE_MISMATCH" in mismatch.blockers
    ambiguous = resolve_procurement_report(
        request_with(purchase_terms(money(amount="100")), purchase_terms(money(amount="200"))),
        synthetic_snapshot(),
    )
    assert "AMBIGUOUS_COMMERCIAL_SOURCE" in ambiguous.blockers
    assert ambiguous.money.cash_gross_rub is None
    forged_organizer = build_request().model_dump(mode="json")
    purchase = next(item for item in forged_organizer["terms"] if item["acquisition"] == "PURCHASE")
    purchase["primary_price"]["raw_amount"] = "1"
    report = resolve_procurement_report(
        ProcurementReportRequestV1.model_validate(forged_organizer), synthetic_snapshot(),
    )
    assert "ORGANIZER_PRICE_MISMATCH" in report.blockers
    purchase["primary_price"]["raw_amount"] = "3000000.00"
    purchase["cost_lines"][0]["basis"]["money"]["scope"]["position_id"] = "position.other"
    report = resolve_procurement_report(
        ProcurementReportRequestV1.model_validate(forged_organizer), synthetic_snapshot(),
    )
    assert "COMMERCIAL_LINE_SCOPE_MISMATCH" in report.blockers


def test_quote_validity_identity_and_user_budget_do_not_fabricate_readiness():
    order = assertion("ORDER_AVAILABLE")
    current_quote = money(kind="VENDOR_QUOTE", valid_until="2026-12-31")
    current = resolve_procurement_report(
        request_with(purchase_terms(current_quote), assertions=[order]),
        trusted_snapshot(order, vendor_quote=current_quote),
    )
    assert current.procurement_status == "CONFIRMED_AVAILABLE" and current.procurement_ready
    stale_quote = money(kind="VENDOR_QUOTE", valid_until="2026-09-01")
    stale = resolve_procurement_report(
        request_with(purchase_terms(stale_quote), assertions=[order]),
        trusted_snapshot(order, vendor_quote=stale_quote),
    )
    assert stale.procurement_status == "UNVERIFIED"
    assert "STALE_QUOTE" in stale.warnings
    user_budget = resolve_procurement_report(
        request_with(purchase_terms(money(kind="USER")), assertions=[order]), synthetic_snapshot(),
    )
    assert user_budget.money.status == "RESOLVED"
    assert user_budget.procurement_status == "UNVERIFIED" and not user_budget.procurement_ready
    forged = resolve_procurement_report(
        request_with(purchase_terms(money(kind="VENDOR_QUOTE", valid_until="2026-12-31")), assertions=[order]),
        synthetic_snapshot(),
    )
    assert forged.money.status == "BLOCKED"
    assert "UNVERIFIED_VENDOR_QUOTE" in forged.blockers
    assert "UNVERIFIED_PROCUREMENT_ASSERTION" in forged.blockers
    changed_quote = copy.deepcopy(current_quote)
    changed_quote["raw_amount"] = "101"
    changed = resolve_procurement_report(
        request_with(purchase_terms(changed_quote), assertions=[order]),
        trusted_snapshot(order, vendor_quote=current_quote),
    )
    assert "UNVERIFIED_VENDOR_QUOTE" in changed.blockers


@pytest.mark.parametrize(
    ("signals", "expected", "risk"),
    [
        ([assertion("DISCONTINUED")], "DISCONTINUED", "UNKNOWN"),
        ([assertion("SUPPLY_RISK", risk="HIGH")], "SUPPLY_RISK", "HIGH"),
        ([assertion("QUOTE_REQUIRED")], "QUOTE_REQUIRED", "UNKNOWN"),
        ([assertion("SALES_CHANNEL")], "LIKELY_AVAILABLE", "UNKNOWN"),
    ],
)
def test_procurement_status_policy_order_is_explicit(signals, expected, risk):
    report = resolve_procurement_report(
        request_with(purchase_terms(money()), assertions=signals), trusted_snapshot(*signals),
    )
    assert report.procurement_status == expected
    assert report.supply_risk == risk
    assert not report.procurement_ready


def test_zero_semantics_and_new_service_basis_are_strict():
    invalid_zero = money(amount="0")
    with pytest.raises(ValidationError, match="explicit semantics"):
        CommercialMoneyV1.model_validate(invalid_zero)
    explicit_zero = resolve_procurement_report(
        request_with(purchase_terms(money(amount="0", zero_semantics="EXCLUDED_BY_SCENARIO"))),
        synthetic_snapshot(),
    )
    assert explicit_zero.money.cash_gross_rub == "0"
    duplicated_service = build_request().model_dump(mode="json")
    purchase = next(item for item in duplicated_service["terms"] if item["acquisition"] == "PURCHASE")
    service = next(item for item in purchase["cost_lines"] if item["category"] == "SERVICE")
    duplicate = copy.deepcopy(service)
    duplicate["line_id"] = "budget.service-percent"
    duplicate["basis"] = {"kind": "PERCENT_BASE", "rate": "0.01", "base_line_id": "robot.purchase-price"}
    purchase["cost_lines"].append(duplicate)
    with pytest.raises(ValidationError, match="multiple service bases"):
        ProcurementReportRequestV1.model_validate(duplicated_service)


def test_api_publishes_and_resolves_golden_contract(monkeypatch):
    import main

    class CommercialSource:
        def load_discovery(self):
            return synthetic_snapshot()

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", CommercialSource())
    with TestClient(main.app) as client:
        response = client.post(
            "/api/v2/procurement-reports", json=build_request().model_dump(mode="json"),
        )
    assert response.status_code == 200, response.text
    assert response.json() == json.loads(
        (ROOT / "contracts/fixtures/procurement-report-v1.synthetic-golden.json").read_text(encoding="utf-8")
    )
    schema = main.app.openapi()
    operation = schema["paths"]["/api/v2/procurement-reports"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("ProcurementReportRequestV1")
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("ProcurementReportV1")
