"""Build/check C15 purchase-ledger schemas and synthetic golden fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.economics.purchase import PurchaseCostLedgerV1, PurchaseLedgerRequestV1, calculate_purchase_ledger  # noqa: E402
from procurement.contracts import ProcurementReportV1  # noqa: E402

DIGEST = "sha256:" + "2" * 64


def sourced(value: str, unit: str, ref: str, source: str = "USER") -> dict:
    result = {"value": value, "unit": unit, "source": source, "provenance_ref": ref}
    if source == "VENDOR_FACT":
        result.update({"evidence_ids": [f"evidence.{ref}"], "evidence_status": "VERIFIED_OFFICIAL"})
    return result


def build_request(*, fleet: int = 21, equipment_class: str = "AMR", horizon: int = 5) -> PurchaseLedgerRequestV1:
    report = ProcurementReportV1.model_validate_json((ROOT / "contracts/fixtures/procurement-report-v1.synthetic-golden.json").read_text(encoding="utf-8"))
    return PurchaseLedgerRequestV1.model_validate({
        "run_id": "run.c15.golden", "project_id": "project.c15", "tenant_id": "tenant.c15",
        "input_revision": "revision.c15", "fleet_count": fleet, "uncertainty": "BASE",
        "horizon_years": horizon, "equipment_class": equipment_class, "procurement": report.model_dump(mode="json"),
        "operating": {
            "operating_hours_per_day": sourced("22", "h/day", "prov.capacity.hours", "POLICY"),
            "days_per_year": sourced("365", "day/year", "prov.capacity.days", "FILE"),
            "availability": sourced("0.7", "1", "prov.capacity.availability", "POLICY"),
            "capacity_result_digest": "sha256:" + "3" * 64,
        },
        "labour_trace_digest": DIGEST,
        "labour_opex": {
            "technicians_required": 0 if fleet == 0 else (fleet + 19) // 20,
            "technician_annual_direct": "600000", "additional_control_required": 1 if fleet else 0,
            "control_annual_direct": "500000", "source_result_digest": DIGEST,
        },
        "charger_ratio": sourced("0.3", "charger/robot", "prov.user.charger-ratio"),
        "warranty_years": sourced("3", "year", "prov.vendor.warranty", "VENDOR_FACT"),
        "energy_path": {"kind": "POWER", "average_power_w": sourced("1000", "W", "prov.vendor.power", "VENDOR_FACT")},
        "initial_battery": {"mode": "INCLUDED_IN_ROBOT_PRICE", "provenance_ref": "prov.commercial.battery-included"},
        "battery_lifecycle": {
            "mode": "SEPARATE_REPLACEMENTS", "autonomy_hours": sourced("8", "h", "prov.vendor.autonomy", "VENDOR_FACT"),
            "resource_cycles": sourced("3000", "cycle", "prov.vendor.battery-resource", "VENDOR_FACT"),
            "replacement_unit_price": sourced("500000", "RUB/battery", "prov.user.battery-price"),
        },
    })


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    request = build_request()
    result = calculate_purchase_ledger(request)
    return {
        ROOT / "contracts/purchase-cost-ledger-request-v1.schema.json": encoded(PurchaseLedgerRequestV1.model_json_schema()),
        ROOT / "contracts/purchase-cost-ledger-v1.schema.json": encoded(PurchaseCostLedgerV1.model_json_schema()),
        ROOT / "contracts/fixtures/purchase-cost-ledger-v1.synthetic.golden.json": encoded({"request": request.model_dump(mode="json"), "result": result.model_dump(mode="json")}),
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
        print("C15 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
