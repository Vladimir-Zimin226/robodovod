import csv
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth_context, require_csrf
from calculation.object_roles import ObjectRoleInput, analyze_object_roles, object_template
from calculation.warehouse_roles import WarehouseRoleInput, analyze_warehouse_roles, warehouse_template
from database import database_session
from object_roles_api import create_object_roles_router
from test_warehouse_roles import catalog as warehouse_catalog


def catalog():
    return SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test-v2"), positions=[])


def raw(kind):
    template = object_template(kind)
    return {"kind": kind, "general": template["general"],
            "roles": [{key: value for key, value in role.items()
                       if key not in {"label", "salary_basis", "headcount_source"}}
                      for role in template["roles"]]}


@pytest.mark.parametrize("kind,roles,works", [("WAREHOUSE", 8, 8), ("AIRPORT", 11, 13), ("CLINIC", 10, 14)])
def test_all_35_typical_work_rows_have_numeric_both_branches(kind, roles, works):
    result = analyze_object_roles(ObjectRoleInput.model_validate(raw(kind)), catalog())
    assert len(result["roles"]) == roles
    rows = [work for role in result["roles"] for work in role["works"]]
    assert len(rows) == works
    assert all(Decimal(work["target_units_per_day"]) > 0 and work["fleet"] > 0 for work in rows)
    assert all(Decimal(work["potential_fte"]) >= 0 and work["purchase"]["npv_rub"] is not None
               and work["purchase"]["roi_percent"] is not None
               and work["raas"]["npv_rub"] is not None for work in rows)
    assert all(work["raas"]["roi_status"].startswith("N/A") for work in rows)
    assert all(work["selected_position_id"] == "SCENARIO_TYPE" and work["selected_model_name"] is None
               for work in rows)


def test_shared_staff_is_allocated_once_and_labor_share_does_not_change_fleet():
    value = raw("AIRPORT")
    value["roles"] = [role for role in value["roles"] if role["role_code"] == "trolley_operator"]
    role = value["roles"][0]
    assert sum(Decimal(work["allocation_fraction"]) for work in role["works"]) == 1
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert Decimal(result["conditional_total"]["potential_fte"]) <= Decimal("80")
    assert result["conditional_total"]["baseline_annual_labor_rub"] == "99993600.00"
    original_fleet = result["conditional_total"]["fleet"]
    original_npv = Decimal(result["conditional_total"]["purchase"]["npv_rub"])
    role["realizable_labor_share"] = "0"
    zero = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert zero["conditional_total"]["fleet"] == original_fleet
    assert Decimal(zero["conditional_total"]["annual_labor_rub"]) == 0
    role["realizable_labor_share"] = "1"
    full = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert full["conditional_total"]["fleet"] == original_fleet
    assert Decimal(full["conditional_total"]["purchase"]["npv_rub"]) > original_npv
    points = full["roles"][0]["works"][0]["labor_sensitivity"]
    assert [point["labor_share"] for point in points] == ["0.00", "0.50", "1.00"]
    assert Decimal(points[0]["purchase_npv_rub"]) < Decimal(points[2]["purchase_npv_rub"])


def test_safety_totals_are_separate_and_editable():
    value = raw("CLINIC")
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert result["safety_warning"]
    assert result["conditional_total"]["work_count"] == 14
    assert result["base_total"]["work_count"] == 12
    value["include_safety_in_conditional"] = False
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert result["conditional_total"] == result["base_total"]
    assert result["safety_warning"] is None


def test_missing_purchase_price_does_not_block_rent_and_wrong_unit_rejected():
    value = raw("AIRPORT")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"][0]["scenario_purchase_price_rub"] = None
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert result["conditional_total"]["purchase"]["npv_rub"] is None
    assert result["conditional_total"]["raas"]["npv_rub"] is None
    assert result["conditional_total"]["raas"]["missing"] == ["baggage_handler/airport_baggage.scenario_purchase_price_rub"]
    value["roles"][0]["works"][0]["raas_mode"] = "FIXED"
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert result["conditional_total"]["raas"]["npv_rub"] is not None
    assert result["conditional_total"]["purchase"]["missing"] == ["baggage_handler/airport_baggage.scenario_purchase_price_rub"]
    value["roles"][0]["works"][0]["scenario_purchase_price_rub"] = "3000000"
    value["roles"][0]["works"][0]["scenario_raas_monthly_rub"] = None
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert result["conditional_total"]["purchase"]["npv_rub"] is not None
    assert result["conditional_total"]["raas"]["npv_rub"] is None
    value["roles"][0]["works"][0]["unit"] = "kg"
    with pytest.raises(ValueError, match="physical unit"):
        ObjectRoleInput.model_validate(value)


def test_percent_raas_has_visible_price_basis_and_fixed_tariff_works_without_price():
    value = raw("AIRPORT")
    value["roles"] = value["roles"][:1]
    work = value["roles"][0]["works"][0]
    percent = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())["roles"][0]["works"][0]["raas"]
    assert percent["mode"] == "PERCENT"
    assert percent["percent_monthly"] == "2.00"
    assert percent["price_basis_rub"] == "3000000.00"
    assert percent["monthly_per_robot_rub"] == "60000.00"
    work["scenario_purchase_price_rub"] = None
    work["raas_mode"] = "FIXED"
    fixed = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())["roles"][0]["works"][0]["raas"]
    assert fixed["monthly_per_robot_rub"] == "120000.00"
    assert fixed["npv_rub"] is not None


def test_safety_warning_cannot_be_removed_by_client_and_catalog_choice_must_match_function():
    value = raw("AIRPORT")
    value["roles"] = [role for role in value["roles"] if role["role_code"] == "perron_cleaner"]
    value["roles"][0]["works"][0]["safety_conditions"] = ""
    with pytest.raises(ValueError, match="immutable evidence"):
        ObjectRoleInput.model_validate(value)
    value = raw("AIRPORT")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"][0]["selected_position_id"] = "random-model"
    with pytest.raises(ValueError, match="functional candidate"):
        analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())


def test_gross_salary_is_converted_once_to_employer_cost():
    value = raw("CLINIC")
    value["roles"] = value["roles"][:1]
    employer = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    value["roles"][0]["salary_basis"] = "GROSS"
    value["roles"][0]["monthly_employer_cost_rub"] = str(Decimal(value["roles"][0]["monthly_employer_cost_rub"]) / Decimal("1.302"))
    gross = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    assert gross["roles"][0]["salary_basis"] == "GROSS"
    assert gross["conditional_total"]["annual_labor_rub"] == employer["conditional_total"]["annual_labor_rub"]
    assert gross["conditional_total"]["baseline_annual_labor_rub"] == employer["conditional_total"]["baseline_annual_labor_rub"]


def test_purchase_roi_uses_entire_horizon_and_rent_uses_same_fleet():
    value = raw("AIRPORT")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"] = value["roles"][0]["works"][:1]
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    work = result["roles"][0]["works"][0]
    capex = Decimal(work["purchase"]["capex_rub"])
    annual_net = Decimal(work["purchase"]["annual_net_rub"])
    years = result["general"]["horizon_years"]
    expected_roi = ((annual_net * years - capex) / capex * 100).quantize(Decimal("0.01"))
    assert Decimal(work["purchase"]["roi_percent"]) == expected_roi
    assert work["fleet"] == result["conditional_total"]["fleet"]
    assert Decimal(work["raas"]["annual_cost_rub"]) == (
        Decimal(work["raas"]["monthly_per_robot_rub"]) * 12
        + Decimal(result["general"]["raas_customer_annual_rub"])) * work["fleet"]


def test_reference_rows_have_explicit_subtasks_and_safety_rows_have_conditions():
    rows = [work for kind in ("WAREHOUSE", "AIRPORT", "CLINIC") for role in object_template(kind)["roles"] for work in role["works"]]
    assert sum(work["calculation_status"] == "REFERENCE_ONLY" for work in rows) == 12
    assert sum(bool(work["safety_conditions"]) for work in rows) == 3
    assert all(work["technical_task"] and work["rate_source"].startswith("ASSUMPTION") for work in rows)
    coverage = Path(__file__).resolve().parents[1] / "data/role-work/role-coverage-v2.csv"
    with coverage.open(encoding="utf-8", newline="") as file:
        entries = list(csv.DictReader(file, delimiter=";"))
    assert len(entries) == 35
    assert all(entry["technical_task"] and entry["demand_units_per_day"] and entry["unit"] for entry in entries)


def test_warehouse_purchase_rent_and_role_labor_coefficient():
    template = warehouse_template()
    sample = {"general": template["general"], "roles": [{key: row[key] for key in
        ("role_code", "headcount", "monthly_employer_cost_rub", "daily_volume",
         "manual_units_per_person_shift", "robotizable_share", "source", "basis")}
        for row in template["roles"][:2]]}
    sample["roles"][0]["realizable_labor_share"] = "0"
    sample["overrides"] = [{"role_code": "forklift_driver", "position_id": "transport", "raas_monthly_rub": "120000"}]
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(sample), warehouse_catalog())
    chosen = result["roles"][0]["candidates"][0]
    assert chosen["fleet"] > 0
    assert chosen["fte_equivalent"] == "0.00"
    assert chosen["purchase_roi_percent"] is not None
    assert chosen["raas_npv_rub"] is not None
    assert chosen["raas_roi_percent"] is None
    assert len(chosen["labor_sensitivity"]) == 3


def test_warehouse_typical_eight_rows_have_both_numeric_branches():
    template = warehouse_template()
    sample = {"general": template["general"], "roles": [{key: row[key] for key in
        ("role_code", "headcount", "monthly_employer_cost_rub", "daily_volume",
         "manual_units_per_person_shift", "robotizable_share", "source", "basis")}
        for row in template["roles"]]}
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(sample), warehouse_catalog())
    assert len(result["roles"]) == 8
    assert all(role["selected_position_id"] and next(candidate for candidate in role["candidates"]
               if candidate["position_id"] == role["selected_position_id"])["npv_rub"] is not None
               for role in result["roles"])
    assert result["portfolio"]["raas_npv_rub"] is not None
    assert result["portfolio"]["purchase_roi_percent"] is not None


def test_owner_bound_save_reopen_and_optimistic_conflict():
    project_id, user_id = uuid.uuid4(), uuid.uuid4()
    project = SimpleNamespace(id=project_id, owner_id=user_id, status="ACTIVE", profile={})

    class Session:
        def scalar(self, _query):
            return project

        def add(self, _row):
            pass

        def commit(self):
            pass

    context = SimpleNamespace(user=SimpleNamespace(id=user_id))
    app = FastAPI()
    app.include_router(create_object_roles_router(catalog))
    app.dependency_overrides[require_csrf] = lambda: context
    app.dependency_overrides[require_auth_context] = lambda: context
    app.dependency_overrides[database_session] = lambda: Session()
    client = TestClient(app)
    payload = raw("CLINIC")
    preview = client.post(f"/api/v2/projects/{project_id}/object-roles/CLINIC/preview", json=payload)
    assert preview.status_code == 200
    saved = client.post(f"/api/v2/projects/{project_id}/object-roles/CLINIC", json={
        "expected_version": 0, "expected_catalog_version": "test-v2", "input": payload})
    assert saved.status_code == 200
    reopened = client.get(f"/api/v2/projects/{project_id}/object-roles/CLINIC")
    assert reopened.json()["latest"]["result_snapshot"] == preview.json()
    conflict = client.post(f"/api/v2/projects/{project_id}/object-roles/CLINIC", json={
        "expected_version": 0, "expected_catalog_version": "test-v2", "input": payload})
    assert conflict.status_code == 409
