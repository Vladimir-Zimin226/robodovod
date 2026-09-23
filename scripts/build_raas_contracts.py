"""Build/check C17 RaaS schemas and warehouse golden fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_commercial_contracts import build_request as commercial_request, synthetic_snapshot  # noqa: E402
from calculation.economics.cashflow import FinancialAnalysisRequestV1, FinancialResultV1  # noqa: E402
from calculation.economics.raas import RaasAnalysisRequestV1, RaasFinancialResultV1, calculate_raas_financials  # noqa: E402
from procurement.contracts import ProcurementReportRequestV1  # noqa: E402
from procurement.resolver import resolve_procurement_report  # noqa: E402


def digest(value: object) -> str:
    from calculation.economics.raas import _hash
    return _hash(value)


def build_request(*, deployment_mode: str = "ALL_FLEET", uncertainty: str = "BASE") -> RaasAnalysisRequestV1:
    commercial = commercial_request().model_dump(mode="json")
    commercial["acquisition"] = "RAAS"
    raas_terms = next(item for item in commercial["terms"] if item["acquisition"] == "RAAS")
    raas_terms["deployment_mode"] = deployment_mode
    raas_terms["responsibilities"] = [
        {"area": "HARDWARE", "responsible_party": "VENDOR", "evidence_ids": []},
        {"area": "CHARGING", "responsible_party": "VENDOR", "evidence_ids": []},
        {"area": "MAINTENANCE", "responsible_party": "VENDOR", "evidence_ids": []},
        {"area": "BATTERY", "responsible_party": "VENDOR", "evidence_ids": []},
        {"area": "SOFTWARE", "responsible_party": "VENDOR", "evidence_ids": []},
        {"area": "INTEGRATION", "responsible_party": "VENDOR", "evidence_ids": []},
        {"area": "INFRASTRUCTURE", "responsible_party": "CUSTOMER", "evidence_ids": []},
        {"area": "CONNECTIVITY", "responsible_party": "CUSTOMER", "evidence_ids": []},
    ]
    report = resolve_procurement_report(ProcurementReportRequestV1.model_validate(commercial), synthetic_snapshot())
    c16 = json.loads((ROOT / "contracts/fixtures/financial-result-v1.warehouse.golden.json").read_text(encoding="utf-8"))
    comparator_request = FinancialAnalysisRequestV1.model_validate(c16["request"])
    comparator_result = FinancialResultV1.model_validate(c16["result"])
    return RaasAnalysisRequestV1.model_validate({
        "run_id": "run.c17.golden", "project_id": comparator_result.project_id,
        "tenant_id": comparator_result.tenant_id, "input_revision": comparator_result.input_revision,
        "uncertainty": uncertainty, "procurement": report.model_dump(mode="json"),
        "purchase_comparator_request": comparator_request.model_dump(mode="json"),
        "purchase_comparator_result": comparator_result.model_dump(mode="json"),
        "comparator_request_digest": digest(comparator_request), "comparator_result_digest": digest(comparator_result),
        "tariff_base_price": {"value": "3000000", "unit": "RUB/robot", "source": "POLICY", "provenance_ref": "synthetic.robot-purchase-price"},
    })


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    request = build_request()
    result = calculate_raas_financials(request)
    return {
        ROOT / "contracts/raas-analysis-request-v1.schema.json": encoded(RaasAnalysisRequestV1.model_json_schema()),
        ROOT / "contracts/raas-financial-result-v1.schema.json": encoded(RaasFinancialResultV1.model_json_schema()),
        ROOT / "contracts/fixtures/raas-financial-result-v1.warehouse.golden.json": encoded({"request": request.model_dump(mode="json"), "result": result.model_dump(mode="json")}),
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
        print("C17 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
