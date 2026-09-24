"""Build/check C16 financial schemas and warehouse golden fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.economics.cashflow import FinancialAnalysisRequestV1, FinancialResultV1, calculate_financial_result  # noqa: E402
from calculation.economics.purchase import PurchaseCostLedgerV1  # noqa: E402
from calculation.labour import LabourResultV1  # noqa: E402


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_request() -> FinancialAnalysisRequestV1:
    purchase_raw = json.loads((ROOT / "contracts/fixtures/purchase-cost-ledger-v1.synthetic.golden.json").read_text(encoding="utf-8"))["result"]
    labour_raw = json.loads((ROOT / "contracts/fixtures/role-labour-v1.warehouse.golden.json").read_text(encoding="utf-8"))["result"]
    for raw in (purchase_raw, labour_raw):
        raw.update({"project_id": "project.c16", "tenant_id": "tenant.c16", "input_revision": "revision.c16"})
    purchase_raw["replay"]["labour_trace_digest"] = labour_raw["replay"]["trace_content_digest"]
    purchase_raw["replay"]["capacity_result_digest"] = labour_raw["replay"]["capacity_result_digests"][0]
    purchase = PurchaseCostLedgerV1.model_validate(purchase_raw)
    labour = LabourResultV1.model_validate(labour_raw)
    purchase_json, labour_json = purchase.model_dump(mode="json"), labour.model_dump(mode="json")
    return FinancialAnalysisRequestV1.model_validate({
        "run_id": "run.c16.golden", "project_id": "project.c16", "tenant_id": "tenant.c16", "input_revision": "revision.c16",
        "purchase_ledger": purchase_json, "labour_result": labour_json,
        "purchase_ledger_digest": digest(purchase_json), "labour_result_digest": digest(labour_json),
        "discount_rate": {"value": "0.15", "unit": "1", "source": "POLICY", "provenance_ref": "finance.discount.default-rate"},
        "tax_mode": "NONE",
        "baseline_equipment": {"base_count": 10, "withdrawn_final": 8,
            "annual_cost_per_unit": {"value": "600000", "unit": "RUB/equipment/year", "source": "USER", "provenance_ref": "prov.user.forklift-annual-cost"}},
        "additional_income": {"mode": "EXCLUDED", "provenance_ref": "decision.additional-income-excluded"},
    })


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    request = build_request()
    # The v1 golden is immutable evidence for historical replay.
    result = calculate_financial_result(request, engine_version="full-cashflows-reconciliation-v1")
    corrected = calculate_financial_result(request)
    return {
        ROOT / "contracts/financial-analysis-request-v1.schema.json": encoded(FinancialAnalysisRequestV1.model_json_schema()),
        ROOT / "contracts/financial-result-v1.schema.json": encoded(FinancialResultV1.model_json_schema()),
        ROOT / "contracts/fixtures/financial-result-v1.warehouse.golden.json": encoded({"request": request.model_dump(mode="json"), "result": result.model_dump(mode="json")}),
        ROOT / "contracts/fixtures/financial-result-v2.warehouse.golden.json": encoded({"request": request.model_dump(mode="json"), "result": corrected.model_dump(mode="json")}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift: list[str] = []
    for path, content in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if drift:
        print("C16 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
