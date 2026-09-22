from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from catalog_repository import (  # noqa: E402
    CapacityRuntimeDTO,
    CatalogApplicabilityDTO,
    CatalogModelDTO,
    CatalogPositionDTO,
    CatalogSnapshotDTO,
    CatalogVersionDTO,
    ProcurementOptionDTO,
)
from procurement.contracts import (  # noqa: E402
    CommercialMoneyV1,
    ProcurementReportRequestV1,
    ProcurementReportV1,
    PurchaseTermsV1,
    RaasTermsV1,
)
from procurement.resolver import resolve_procurement_report  # noqa: E402

CONTRACTS = ROOT / "contracts"
FIXTURES = CONTRACTS / "fixtures"
DATA = ROOT / "data" / "commercial"
MODEL_ID = "ecd7d582-b342-449a-b43b-66288d159a32"
POSITION_ID = "catalog-v4-row-0020"
OPTION_ID = "price-v4-row-0020"
EVIDENCE_ID = "evidence.price-v4-row-0020"


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _scope(boundary: str = "SCENARIO_BUDGET") -> dict[str, Any]:
    return {
        "model_id": MODEL_ID, "position_id": POSITION_ID,
        "procurement_option_id": OPTION_ID, "region": "RU", "boundary": boundary,
    }


def _money(source_id: str, amount: str, *, kind: str = "ASSUMPTION", zero: bool = False) -> dict[str, Any]:
    return {
        "raw_amount": amount, "currency": "RUB", "tax_basis": "CASH_GROSS_RUB", "vat_rate": None,
        "source": {"kind": kind, "source_id": source_id, "evidence_ids": [], "observed_on": None, "valid_until": None},
        "scope": _scope(), "zero_semantics": "EXCLUDED_BY_SCENARIO" if zero else None,
    }


def _line(line_id: str, category: str, amount: str, basis: str, timing: str, *, zero: bool = False) -> dict[str, Any]:
    return {
        "line_id": line_id, "category": category, "timing": timing,
        "basis": {"kind": basis, "money": _money(f"synthetic.{line_id}", amount, zero=zero)},
        "included_in": [], "excluded_by_scenario": zero,
    }


def build_request() -> ProcurementReportRequestV1:
    purchase_price = {
        "raw_amount": "3000000.00", "currency": "UNKNOWN", "tax_basis": "CASH_GROSS_RUB", "vat_rate": None,
        "source": {
            "kind": "ORGANIZER_DATASET", "source_id": OPTION_ID,
            "evidence_ids": [EVIDENCE_ID], "observed_on": "2026-09-15", "valid_until": None,
        },
        "scope": _scope("BARE_EQUIPMENT"), "zero_semantics": None,
    }
    purchase = {
        "acquisition": "PURCHASE", "primary_price": purchase_price,
        "cost_lines": [
            _line("budget.charger", "CHARGER", "100000", "PER_ROBOT", "CAPITAL_ONCE"),
            _line("budget.integration", "INTEGRATION", "100000", "PER_ROBOT", "CAPITAL_ONCE"),
            _line("budget.infrastructure", "INFRASTRUCTURE", "500000", "FIXED_TOTAL", "CAPITAL_ONCE"),
            _line("budget.delivery", "DELIVERY", "100000", "FIXED_TOTAL", "CAPITAL_ONCE"),
            _line("budget.commissioning", "COMMISSIONING", "100000", "FIXED_TOTAL", "CAPITAL_ONCE"),
            _line("budget.training", "TRAINING", "50000", "FIXED_TOTAL", "CAPITAL_ONCE"),
            _line("budget.service", "SERVICE", "50000", "PER_ROBOT", "ANNUAL"),
            _line("budget.software", "SOFTWARE", "10000", "PER_ROBOT", "ANNUAL"),
            _line("budget.wifi", "OTHER", "0", "FIXED_TOTAL", "CAPITAL_ONCE", zero=True),
            _line("budget.spares", "SPARES", "0", "FIXED_TOTAL", "CAPITAL_ONCE", zero=True),
        ],
        "responsibilities": [
            {"area": "HARDWARE", "responsible_party": "CUSTOMER", "evidence_ids": []},
            {"area": "MAINTENANCE", "responsible_party": "CUSTOMER", "evidence_ids": []},
            {"area": "INFRASTRUCTURE", "responsible_party": "CUSTOMER", "evidence_ids": []},
        ],
    }
    raas = {
        "acquisition": "RAAS",
        "tariff_basis": {"kind": "PERCENT_BASE", "rate": "0.02", "base_line_id": "robot.purchase-price"},
        "billing_basis": "PER_ROBOT_MONTH", "contract_months": 60,
        "renewal": "SAME_TERMS_TO_HORIZON", "deployment_mode": "ALL_FLEET",
        "buyout": _money("synthetic.raas-buyout", "0", zero=True), "cost_lines": [],
        "responsibilities": [
            {"area": "HARDWARE", "responsible_party": "VENDOR", "evidence_ids": []},
            {"area": "INFRASTRUCTURE", "responsible_party": "UNKNOWN", "evidence_ids": []},
        ],
    }
    return ProcurementReportRequestV1.model_validate({
        "model_id": MODEL_ID, "position_id": POSITION_ID, "acquisition": "PURCHASE",
        "evaluation_date": "2026-09-23", "terms": [purchase, raas],
        "currency_assumption": {
            "currency": "RUB", "provenance_id": "assumption.demo-rub-v1",
            "rationale": "Explicit contest demo currency assumption; source currency remains UNKNOWN",
            "applies_to_source_id": OPTION_ID, "confirmation_state": "POLICY_ACCEPTED",
        },
        "assertions": [],
    })


def synthetic_snapshot() -> CatalogSnapshotDTO:
    option = ProcurementOptionDTO(
        mode="PURCHASE", amount=Decimal("3000000.00"), currency=None,
        price_status="NORMALIZED", vat_status="ORGANIZER_ASSUMPTION_INCLUDED",
        included_costs=("VAT_ASSUMED",), excluded_costs=("delivery", "commissioning", "integration"),
        evidence_id=EVIDENCE_ID, id=OPTION_ID, source_row_id=POSITION_ID,
        raw_price="3 000 000,00", observed_on=date(2026, 9, 15),
    )
    model = CatalogModelDTO(
        id=MODEL_ID, source_namespace="organizer", source_record_key=MODEL_ID,
        organizer_id=MODEL_ID, manufacturer="Robowizard", name="MULE",
        system_family="BRS", type_code="Transport", subtype_code=None,
        maturity_status=None, trl=None, description=None, attributes={}, facts=(),
        applicability=(), procurement_options=(option,), runtime_robot=None,
        runtime_blockers=(), capacity_runtime=CapacityRuntimeDTO(
            calculation_readiness_status="CALCULATION_BLOCKED", calculation_ready=False,
            calculation_requires_assumptions=False, calculation_profile=None,
            calculation_blockers=("not-needed-for-c13",), runtime_catalog_version=None,
        ),
    )
    position = CatalogPositionDTO(
        id=POSITION_ID, source_record_key=POSITION_ID, source_row_number=20,
        model=model, applicability=CatalogApplicabilityDTO("warehouse", "transport", "RU", None),
        procurement_option=option, media=None, runtime_robot=None, runtime_blockers=(),
    )
    return CatalogSnapshotDTO(
        version=CatalogVersionDTO(str(uuid.UUID("00000000-0000-0000-0000-000000000013")), "synthetic-commercial-v1", "PUBLISHED", "4"),
        models=(model,), positions=(position,),
    )


def expected_files() -> tuple[tuple[Path, bytes], ...]:
    request = build_request()
    report = resolve_procurement_report(request, synthetic_snapshot())
    schemas = (
        (CONTRACTS / "commercial-money-v1.schema.json", CommercialMoneyV1),
        (CONTRACTS / "purchase-terms-v1.schema.json", PurchaseTermsV1),
        (CONTRACTS / "raas-terms-v1.schema.json", RaasTermsV1),
        (CONTRACTS / "procurement-report-request-v1.schema.json", ProcurementReportRequestV1),
        (CONTRACTS / "procurement-report-v1.schema.json", ProcurementReportV1),
    )
    generated = tuple((path, _bytes(model.model_json_schema())) for path, model in schemas)
    return generated + (
        (DATA / "synthetic-commercial-budget-v1.json", _bytes(request.model_dump(mode="json"))),
        (FIXTURES / "procurement-report-v1.synthetic-golden.json", _bytes(report.model_dump(mode="json"))),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = expected_files()
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, content in expected if not path.is_file() or path.read_bytes() != content]
        if stale:
            raise SystemExit("generated commercial contracts differ: " + ", ".join(stale))
        return 0
    DATA.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for path, content in expected:
        path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
