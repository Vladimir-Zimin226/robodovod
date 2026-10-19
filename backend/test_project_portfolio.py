from dataclasses import replace
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import jsonschema
import pytest

from calculation.service import analyze_capacity
from calculation_contracts import CapacityAnalysisRequest
from economics_orchestrator import EconomicsExecutionContextV1
from economics_final import execute_economics_v5
from economics_partial import execute_partial_economics_v2
from project_portfolio import calculate_project_portfolio
from test_economics_partial import _context
from test_evgeny_project import project_input


def test_shared_role_uses_explicit_fractions_across_saved_processes():
    snapshot, original = _context()
    base = original.capacity_request.model_dump(mode="json")
    process_ids = [base["process"]["process_id"], "process.second.shared"]
    rows = []
    for index, (process_id, fraction) in enumerate(zip(process_ids, ("0.4", "0.6"))):
        payload = deepcopy(base)
        payload["process"]["process_id"] = process_id
        payload["role_pool"]["roles"][0]["process_ids"] = process_ids
        request = CapacityAnalysisRequest.model_validate(payload)
        calculated = analyze_capacity(request, snapshot, f"run.capacity.shared.{index}")
        context = EconomicsExecutionContextV1(
            run_id=f"run.economics.shared.{index}", project_id=original.project_id,
            tenant_id=original.tenant_id, capacity_request=request,
            capacity_response=calculated.response,
            constraint_report=calculated.constraints.model_dump(mode="json"),
            executability=calculated.executability.model_dump(mode="json"))
        raw = project_input()
        raw["role_work_profiles"] = [{
            "role_id": "role.driver", "robotizable_fraction": "0.5",
            "manual_units_per_shift": "100", "process_allocation_fraction": fraction,
            "residual_operations": "Manual inspection remains", "source": "ASSUMPTION",
            "basis": "Documented scenario allocation", "confirmed": True,
        }]
        result = execute_partial_economics_v2(raw, snapshot, context, full_engine=execute_economics_v5).result_snapshot
        assert result["role_labour"]["roles"][0]["allocated_people"] == (8 if index == 0 else 12)
        schema = json.loads((Path(__file__).resolve().parents[1] / "contracts" /
                             f"{result['schema_version']}.schema.json").read_text(encoding="utf-8"))
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(result))
        assert not errors, [(error.message, list(error.path)) for error in errors[:3]]
        rows.append((context, raw, result))
    report = calculate_project_portfolio(
        rows, snapshot, project_id=original.project_id,
        tenant_id=original.tenant_id, run_id="run.project.shared")
    assert report["status"] == "CALCULATED"
    assert report["total_released_people"] <= 20
    missing = deepcopy(rows[0][1])
    del missing["role_work_profiles"][0]["process_allocation_fraction"]
    partial = execute_partial_economics_v2(missing, snapshot, rows[0][0]).result_snapshot
    assert partial["schema_version"] == "economics-partial-result-v1"
    assert partial["branches"]["labour"]["status"] != "CALCULATED"
    rows[1][1]["role_work_profiles"][0]["process_allocation_fraction"] = "0.7"
    with pytest.raises(ValueError, match="allocation fractions exceed one"):
        calculate_project_portfolio(
            rows, snapshot, project_id=original.project_id,
            tenant_id=original.tenant_id, run_id="run.project.shared.excess")


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


def test_second_selected_role_is_visible_as_unassessed_in_project_economics():
    snapshot, original = _context()
    payload = original.capacity_request.model_dump(mode="json")
    payload["process"]["role_refs"].append("role.loader")
    loader = {**payload["role_pool"]["roles"][0], "role_id": "role.loader",
              "role_code": "loader"}
    payload["role_pool"]["roles"].append(loader)
    request = CapacityAnalysisRequest.model_validate(payload)
    calculated = analyze_capacity(request, snapshot, "run.capacity.two.roles")
    context = EconomicsExecutionContextV1(
        run_id="run.economics.two.roles", project_id=original.project_id,
        tenant_id=original.tenant_id, capacity_request=request,
        capacity_response=calculated.response,
        constraint_report=calculated.constraints.model_dump(mode="json"),
        executability=calculated.executability.model_dump(mode="json"))
    raw = {**project_input(), "primary_role_id": "role.driver"}
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    report = calculate_project_portfolio(
        [(context, raw, result)], snapshot, project_id=context.project_id,
        tenant_id=context.tenant_id, run_id="run.project.two.roles")
    assert report["schema_version"] == "project-portfolio-economics-v2"
    assert report["status"] == "PARTIAL"
    roles = {item["role_code"]: item for item in report["role_effects"]}
    assert roles["forklift_driver"]["status"] == "CALCULATED"
    assert roles["loader"]["status"] == "NOT_CALCULATED"
    assert roles["loader"]["released"] is None
    assert report["unassessed_roles"] == [roles["loader"]]


def test_blocked_operation_roles_remain_visible_in_project_economics():
    snapshot, context = _context()
    raw = project_input()
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    report = calculate_project_portfolio(
        [(context, raw, result)], snapshot, project_id=context.project_id,
        tenant_id=context.tenant_id, run_id="run.project.blocked.roles",
        excluded_operations=[
            {"process_id": "process.blocked.driver", "role_refs": ["role.driver"]},
            {"process_id": "process.blocked.picker", "role_refs": ["role.picker"]},
        ])
    roles = {item["role_id"]: item for item in report["role_effects"]}
    assert report["status"] == "PARTIAL"
    assert roles["role.driver"]["status"] == "PARTIAL"
    assert roles["role.driver"]["released"] is not None
    assert roles["role.driver"]["excluded_process_ids"] == ["process.blocked.driver"]
    assert roles["role.picker"]["status"] == "NOT_CALCULATED"
    assert roles["role.picker"]["released"] is None
    assert {item["role_id"] for item in report["unassessed_roles"]} == {"role.driver", "role.picker"}
