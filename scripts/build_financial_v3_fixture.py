"""Create only the additive C16 v3 evidence; leave historical data untouched."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.economics.cashflow import FinancialAnalysisRequestV1  # noqa: E402
from calculation.service import analyze_financials  # noqa: E402

TARGET = ROOT / "contracts/fixtures/financial-result-v3.additional-income.golden.json"


def build() -> dict:
    historical = json.loads((ROOT / "contracts/fixtures/financial-result-v2.warehouse.golden.json").read_text(encoding="utf-8"))
    raw = historical["request"]
    raw["run_id"] = "run.c16.v3.additional-income"
    raw["additional_income"] = {"mode": "INCLUDED", "annual_amount": {
        "value": "1000000", "unit": "RUB/year", "source": "USER",
        "provenance_ref": "prov.user.additional-income"}}
    request = FinancialAnalysisRequestV1.model_validate(raw)
    result = analyze_financials(request, engine_version="full-cashflows-reconciliation-v3")
    return {"request": request.model_dump(mode="json"), "result": result.model_dump(mode="json")}


if __name__ == "__main__":
    content = json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        raise SystemExit(0 if TARGET.read_text(encoding="utf-8") == content else 1)
    TARGET.write_text(content, encoding="utf-8", newline="\n")
