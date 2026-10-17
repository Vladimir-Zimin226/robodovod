from economics_partial import execute_partial_economics_v2
from project_portfolio import calculate_project_portfolio
from test_economics_partial import _context
from test_evgeny_project import project_input


def test_one_model_portfolio_replays_one_process_without_duplicate_site_cost():
    snapshot, context = _context()
    raw = project_input()
    executed = execute_partial_economics_v2(raw, snapshot, context)
    result = executed.result_snapshot
    assert result["scenarios"]
    combined = calculate_project_portfolio(
        [(context, raw, result)], snapshot, project_id=context.project_id,
        tenant_id=context.tenant_id, run_id="run.project.portfolio.1")
    assert combined["status"] == "CALCULATED"
    assert len(combined["rows"]) == 1
    purchase_base = next(item for item in result["scenarios"]
                         if item["acquisition"] == "PURCHASE" and item["uncertainty"] == "BASE")
    assert combined["project_capex_rub"] == purchase_base["report_facts"]["project_capex_cashflow"]


def test_two_different_models_keep_prices_and_energy_on_their_own_rows():
    snapshot, first = _context()
    first_raw = {**project_input(), "salary_basis": "EMPLOYER_COST", "energy_power_basis": "AVERAGE",
                 "shared_site_capital_gross": "500000", "shared_annual_cost_gross": "75000",
                 "charger_power_kw": "5", "charging_simultaneity_fraction": "0.5"}
    first_result = execute_partial_economics_v2(first_raw, snapshot, first).result_snapshot
    original = snapshot.positions[0]
    second_price = replace(original.procurement_option, id="price.demo.second", amount=Decimal("5500000"))
    second_model = replace(original.model, id="model.demo.second", organizer_id="model.demo.second",
                           procurement_options=(second_price,))
    second_position = replace(original, id="position.demo.second", model=second_model,
                              procurement_option=second_price, source_record_key="position.demo.second",
                              source_row_number=2)
    snapshot = replace(snapshot, models=(*snapshot.models, second_model),
                       positions=(*snapshot.positions, second_position))
    second_input = first.capacity_request.model_dump(mode="json")
    second_input["process"]["process_id"] = "process.second"
    second_input["role_pool"]["roles"][0]["process_ids"] = ["process.second"]
    second_input["model_id"] = second_model.id
    second_input["position_id"] = second_position.id
    request = CapacityAnalysisRequest.model_validate(second_input)
    calculated = analyze_capacity(request, snapshot, "run.capacity.second")
    second = EconomicsExecutionContextV1(
        run_id="run.economics.second", project_id=first.project_id, tenant_id=first.tenant_id,
        capacity_request=request, capacity_response=calculated.response,
        constraint_report=calculated.constraints.model_dump(mode="json"),
        executability=calculated.executability.model_dump(mode="json"))
    second_raw = {**first_raw, "average_power_w": "1700", "energy_power_basis": "MAX_UPPER_BOUND",
                  "charger_power_kw": "10", "charging_simultaneity_fraction": "0.6"}
    second_result = execute_partial_economics_v2(second_raw, snapshot, second).result_snapshot
    report = calculate_project_portfolio(
        [(first, first_raw, first_result), (second, second_raw, second_result)], snapshot,
        project_id=first.project_id, tenant_id=first.tenant_id, run_id="run.project.portfolio.2")
    rows = {row["model_id"]: row for row in report["rows"]}
    assert len(rows) == 2
    assert rows[second_model.id]["power_w_per_robot"] == "1700"
    assert rows[second_model.id]["energy_power_basis"] == "MAX_UPPER_BOUND"
    assert Decimal(report["project_capex_rub"]) == sum(Decimal(row["direct_capex_rub"]) for row in rows.values()) + Decimal(first_raw["shared_site_capital_gross"])
    assert Decimal(report["first_year_energy_rub"]) == sum(Decimal(row["first_year_energy_rub"]) for row in rows.values())
    expected_roi = (sum(Decimal(row["differential_cf"]) for row in report["annual_ledgers"])
                    - Decimal(report["project_capex_rub"])) / Decimal(report["project_capex_rub"]) * 100
    assert Decimal(report["project_net_roi_percent"]) == expected_roi.quantize(Decimal("0.01"))
    assert Decimal(report["peak_charging_power_kw"]) == sum(
        Decimal(row["charger_power_kw"]) * Decimal(row["charging_simultaneity_fraction"]) * row["fleet"]
        for row in rows.values())


def test_project_portfolio_rejects_conflicting_site_assumptions():
    snapshot, context = _context()
    raw = project_input()
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    with pytest.raises(ValueError, match="share revision, site assumptions"):
        calculate_project_portfolio(
            [(context, raw, result), (context, {**raw, "discount_rate": "0.25"}, result)], snapshot,
            project_id=context.project_id, tenant_id=context.tenant_id, run_id="run.project.portfolio.3")


def test_purchase_only_advanced_input_can_enter_project_without_raas_contract():
    snapshot, context = _context()
    raw = {**project_input(), "calculation_depth": "ADVANCED", "salary_basis": "EMPLOYER_COST",
           "raas_monthly_per_robot_gross": None, "raas_contract_months": None,
           "raas_vendor_scope_confirmed": False, "staffing_raas": None}
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["schema_version"] == "economics-partial-result-v1"
    assert result["branches"]["purchase"]["status"] == "CALCULATED"
    report = calculate_project_portfolio(
        [(context, raw, result)], snapshot, project_id=context.project_id,
        tenant_id=context.tenant_id, run_id="run.project.portfolio.4")
    assert report["status"] == "CALCULATED"
    assert Decimal(report["project_capex_rub"]) > 0

from dataclasses import replace
from decimal import Decimal

import pytest

from calculation.service import analyze_capacity
from calculation_contracts import CapacityAnalysisRequest
from economics_orchestrator import EconomicsExecutionContextV1
