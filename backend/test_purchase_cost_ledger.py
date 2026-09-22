from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.economics.purchase import PurchaseCostLedgerV1, PurchaseLedgerRequestV1, calculate_purchase_ledger
from calculation.service import analyze_purchase_costs

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> dict:
    return json.loads((ROOT / "contracts/fixtures/purchase-cost-ledger-v1.synthetic.golden.json").read_text(encoding="utf-8"))


def request() -> PurchaseLedgerRequestV1:
    return PurchaseLedgerRequestV1.model_validate(fixture()["request"])


def line(result: PurchaseCostLedgerV1, line_id: str, year: int = 0):
    rows = result.capital_lines if year == 0 else result.annual_ledgers[year - 1].operating_lines
    return next(item for item in rows if item.line_id == line_id)


def test_golden_is_strict_replayable_and_sums_exactly():
    data = fixture()
    first = analyze_purchase_costs(PurchaseLedgerRequestV1.model_validate(data["request"]))
    second = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(data["request"]))
    assert first.model_dump(mode="json") == data["result"] == second.model_dump(mode="json")
    assert first.status == "COMPLETE"
    assert first.capex_gross == first.capex_cashflow
    assert Decimal(first.capex_gross) == Decimal(first.capex_amortizable) + Decimal(first.reserve)
    for annual in first.annual_ledgers:
        assert Decimal(annual.operating_total) == sum(Decimal(item.amount or "0") for item in annual.operating_lines)
    assert first.replay.capacity_result_digest == data["request"]["operating"]["capacity_result_digest"]


def test_charger_ceil_and_repair_use_equipment_base_only():
    result = calculate_purchase_ledger(request())
    charger = line(result, "capital.budget.charger")
    assert charger.amount == "700000"  # ceil(21 × .3) = 7
    equipment = Decimal(result.equipment_capex)
    repair = line(result, "year.1.repair", 1)
    assert Decimal(repair.amount) == equipment * Decimal("0.01") * Decimal("0.5")
    assert Decimal(repair.amount) != equipment * Decimal("0.01") * Decimal("0.5") * 21


@pytest.mark.parametrize(("warranty", "year", "zero"), [("0", 1, False), ("3", 3, True), ("3", 4, False)])
def test_service_warranty_boundaries(warranty: str, year: int, zero: bool):
    raw = request().model_dump(mode="json")
    raw["warranty_years"]["value"] = warranty
    result = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    assert (Decimal(line(result, f"year.{year}.service", year).amount) == 0) is zero


def test_technician_20_21_binding_and_missing_salary_are_explicit():
    raw = request().model_dump(mode="json")
    raw["fleet_count"] = 20
    raw["labour_opex"]["technicians_required"] = 1
    assert PurchaseLedgerRequestV1.model_validate(raw).labour_opex.technicians_required == 1
    raw["fleet_count"] = 21
    with pytest.raises(ValidationError, match=r"ceil\(fleet/20\)"):
        PurchaseLedgerRequestV1.model_validate(raw)
    raw["labour_opex"]["technicians_required"] = 2
    raw["labour_opex"]["technician_annual_direct"] = None
    result = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    assert result.status == "INCOMPLETE"
    assert "technicians-salary-missing" in result.issues


def test_power_energy_path_converts_w_to_kw_once_and_missing_path_is_incomplete():
    result = calculate_purchase_ledger(request())
    expected_kwh = Decimal(21) * Decimal("1") * 22 * Decimal("0.7") * 365 / Decimal("0.85")
    expected = expected_kwh * Decimal("8") * Decimal("0.5")
    assert Decimal(line(result, "year.1.energy", 1).amount) == expected
    raw = request().model_dump(mode="json")
    raw["energy_path"] = None
    incomplete = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    assert incomplete.status == "INCOMPLETE"
    assert line(incomplete, "year.1.energy", 1).amount is None


def test_battery_events_use_cumulative_ramp_and_no_second_ramp():
    result = calculate_purchase_ledger(request())
    events = [item.events_per_robot for item in result.battery_events]
    assert events == [0, 0, 0, 0, 1]
    event = result.battery_events[-1]
    expected = Decimal(21) * Decimal("500000") * (Decimal("1.05") ** 4)
    assert Decimal(event.amount) == expected


@pytest.mark.parametrize(("equipment_class", "horizon", "share"), [("AMR", 5, "0.30"), ("FORKLIFT", 7, "0.18"), ("FIXED_CELL", 5, "0.15")])
def test_residual_policy_percentages(equipment_class: str, horizon: int, share: str):
    raw = request().model_dump(mode="json")
    raw["equipment_class"] = equipment_class
    raw["horizon_years"] = horizon
    result = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    robots = Decimal(line(result, "capital.robots").amount)
    assert Decimal(result.terminal_residual) == robots * Decimal(share)


def test_missing_commercial_and_lifecycle_inputs_never_become_zero():
    raw = request().model_dump(mode="json")
    raw["warranty_years"] = None
    raw["battery_lifecycle"] = None
    raw["charger_ratio"] = None
    result = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    assert result.status == "INCOMPLETE"
    assert line(result, "capital.budget.charger").amount is None
    assert line(result, "year.1.service", 1).amount is None
    assert line(result, "year.1.battery-replacement", 1).amount is None
    assert result.capex_gross is None


def test_fleet_zero_and_separate_initial_battery_are_supported_without_hidden_defaults():
    raw = request().model_dump(mode="json")
    raw["fleet_count"] = 0
    raw["labour_opex"].update({"technicians_required": 0, "additional_control_required": 0})
    result = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    assert line(result, "capital.robots").amount == "0"
    assert line(result, "capital.budget.charger").amount == "0"
    raw = request().model_dump(mode="json")
    raw["initial_battery"] = {"mode": "SEPARATE_CAPEX", "provenance_ref": "prov.battery.separate", "separate_unit_price": {"value": "100000", "unit": "RUB/battery", "source": "USER", "provenance_ref": "prov.battery.price"}}
    separate = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    assert line(separate, "capital.initial-batteries").amount == "2100000"


def test_included_cost_line_is_not_counted_twice():
    raw = request().model_dump(mode="json")
    charger = next(item for item in raw["procurement"]["terms"]["cost_lines"] if item["category"] == "CHARGER")
    charger["included_in"] = ["capital.robots"]
    result = calculate_purchase_ledger(PurchaseLedgerRequestV1.model_validate(raw))
    included = line(result, "capital.budget.charger")
    assert included.status == "EXCLUDED" and included.amount == "0"
    assert included.reason_code == "included-in-another-line"


def test_generated_schemas_are_strict():
    for name in ("purchase-cost-ledger-request-v1.schema.json", "purchase-cost-ledger-v1.schema.json"):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False


def test_vendor_technical_fact_requires_matching_safe_evidence():
    raw = request().model_dump(mode="json")
    raw["energy_path"]["average_power_w"]["evidence_ids"] = []
    raw["energy_path"]["average_power_w"]["evidence_status"] = None
    with pytest.raises(ValidationError, match="matching-safe evidence"):
        PurchaseLedgerRequestV1.model_validate(raw)
