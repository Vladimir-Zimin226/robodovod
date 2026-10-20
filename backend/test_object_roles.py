import csv
from copy import deepcopy
from io import BytesIO
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from pypdf import PdfReader
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth_context, require_csrf
from calculation.object_roles import ObjectRoleInput, analyze_object_roles, object_template
from calculation.warehouse_roles import WarehouseRoleInput, analyze_warehouse_roles, warehouse_template
from calculation.role_report import role_report_pdf
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


def test_verified_payload_blocks_under_capacity_model_and_auto_selection():
    value = raw("AIRPORT")
    value["roles"] = [role for role in value["roles"] if role["role_code"] == "baggage_handler"]
    value["roles"][0]["works"][0]["task_payload_kg"] = "2500"
    position = SimpleNamespace(id="baggage-500", model=SimpleNamespace(
        name="Робот для багажа", description="Перевозит багаж", manufacturer="Example",
        maturity_status="SERIAL", facts=(SimpleNamespace(code="payload_kg", value="500",
            canonical_unit="kg", resolution_status="VERIFIED_OFFICIAL", evidence_id="source-1"),)))
    scoped_catalog = SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test-v2"), positions=[position])
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), scoped_catalog)
    work = result["roles"][0]["works"][0]
    assert work["candidates"][0]["physical_fit"] == "FAIL"
    assert work["selected_position_id"] == "SCENARIO_TYPE"
    value["roles"][0]["works"][0]["selected_position_id"] = "baggage-500"
    with pytest.raises(ValueError, match="payload is below"):
        analyze_object_roles(ObjectRoleInput.model_validate(value), scoped_catalog)
    value["roles"][0]["works"][0]["task_payload_kg"] = "250"
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), scoped_catalog)
    assert result["roles"][0]["works"][0]["candidates"][0]["physical_fit"] == "PASS"


def test_cleaning_candidate_does_not_require_cargo_mass():
    value = raw("AIRPORT")
    value["roles"] = [role for role in value["roles"] if role["role_code"] == "terminal_cleaner"]
    position = SimpleNamespace(id="cleaner", model=SimpleNamespace(
        name="Робот для уборки", description="Уборка терминала", manufacturer="Example",
        maturity_status="SERIAL", facts=()))
    scoped_catalog = SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test-v2"), positions=[position])
    result = analyze_object_roles(ObjectRoleInput.model_validate(value), scoped_catalog)
    assert result["roles"][0]["works"][0]["candidates"][0]["physical_fit"] == "NOT_APPLICABLE"


def test_scene_route_changes_object_fleet_and_money_and_no_route_zeroes_effect():
    value = raw("WAREHOUSE")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"] = value["roles"][0]["works"][:1]
    work = value["roles"][0]["works"][0]
    work["daily_volume"] = "875"
    value["general"]["fleet_reserve_share"] = "0"
    simulation = {"scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
                  "pickup_service_s": 30, "dropoff_service_s": 30, "turn_delay_s": 5,
                  "units_per_cycle": 1}
    work["simulation"] = simulation
    baseline = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())["roles"][0]["works"][0]
    work["simulation"] = {**simulation, "extra_obstacles": [{"x": 25, "y": 34, "width": 2, "height": 2}]}
    detour = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())["roles"][0]["works"][0]
    assert baseline["simulation"]["status"] == detour["simulation"]["status"] == "MODELED"
    assert "ROBOT_TTH_NOT_VERIFIED" in baseline["simulation"]["flags"]
    assert baseline["fleet"] < detour["fleet"]
    assert Decimal(baseline["purchase"]["npv_rub"]) > Decimal(detour["purchase"]["npv_rub"])
    work["simulation"] = {**simulation, "arrival_burst_size": 4}
    queued = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())["roles"][0]["works"][0]
    assert queued["simulation"]["time_wait_s"] > 0
    assert queued["fleet"] > baseline["fleet"]
    assert Decimal(queued["purchase"]["npv_rub"]) < Decimal(baseline["purchase"]["npv_rub"])
    work["simulation"] = {**simulation, "shared_lane": {"x": 30, "y": 34, "width": 30, "height": 2}}
    lane = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())["roles"][0]["works"][0]
    assert lane["simulation"]["shared_lane"]["mean_wait_s"] > 0
    assert lane["fleet"] > baseline["fleet"]
    assert Decimal(lane["purchase"]["npv_rub"]) < Decimal(baseline["purchase"]["npv_rub"])
    lane_result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    lane_pdf = "\n".join(page.extract_text() for page in PdfReader(BytesIO(role_report_pdf(lane_result))).pages)
    assert "Узкий участок" in lane_pdf
    assert str(lane["simulation"]["shared_lane"]["mean_wait_s"]) in lane_pdf
    work["simulation"] = {**simulation, "extra_obstacles": [{"x": 30, "y": 20, "width": 1, "height": 40}]}
    no_route = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())["roles"][0]["works"][0]
    assert no_route["simulation"]["status"] == "NO_ROUTE"
    assert no_route["fleet"] == 0 and no_route["annual_labor_rub"] == "0.00"
    assert Decimal(no_route["purchase"]["npv_rub"]) == 0
    full_result = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(role_report_pdf(full_result))).pages)
    assert "NO_ROUTE" in pdf_text
    assert full_result["base_total"]["purchase"]["npv_rub"] in pdf_text


def test_what_if_volume_and_speed_recompute_object_cycle_fleet_and_money():
    value = raw("WAREHOUSE")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"] = value["roles"][0]["works"][:1]
    work = value["roles"][0]["works"][0]
    work["daily_volume"] = "875"
    value["general"]["fleet_reserve_share"] = "0"
    work["simulation"] = {
        "scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
        "pickup_service_s": 30, "dropoff_service_s": 30, "turn_delay_s": 5,
        "units_per_cycle": 1,
    }
    original = deepcopy(value)
    base = analyze_object_roles(ObjectRoleInput.model_validate(value), catalog())
    branch_input = deepcopy(value)
    branch_work = branch_input["roles"][0]["works"][0]
    branch_work["daily_volume"] = "1225"
    branch_work["simulation"]["speed_loaded_mps"] = "0.8"
    branch_work["simulation"]["speed_empty_mps"] = "0.8"
    branch = analyze_object_roles(ObjectRoleInput.model_validate(branch_input), catalog())
    before = base["roles"][0]["works"][0]
    after = branch["roles"][0]["works"][0]
    assert value == original
    assert before["simulation"]["status"] == after["simulation"]["status"] == "MODELED"
    assert after["simulation"]["cycle_s"] > before["simulation"]["cycle_s"]
    assert after["fleet"] > before["fleet"]
    assert branch["base_total"]["purchase"]["npv_rub"] != base["base_total"]["purchase"]["npv_rub"]


def test_what_if_horizon_uses_same_object_cashflows_for_purchase_and_rent():
    value = raw("AIRPORT")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"] = value["roles"][0]["works"][:1]
    results = {}
    for years in (5, 10):
        branch = deepcopy(value)
        branch["general"]["horizon_years"] = years
        results[years] = analyze_object_roles(ObjectRoleInput.model_validate(branch), catalog())
    assert value["general"]["horizon_years"] == 5
    assert results[5]["base_total"]["fleet"] == results[10]["base_total"]["fleet"]
    for years, report in results.items():
        discount = Decimal(str(report["general"]["discount_rate"]))
        factor = sum((Decimal(1) / (1 + discount) ** year for year in range(1, years + 1)), Decimal(0))
        for mode in ("purchase", "raas"):
            money = report["base_total"][mode]
            expected = (Decimal(money["annual_net_rub"]) * factor - Decimal(money["capex_rub"])).quantize(Decimal("0.01"))
            assert Decimal(money["npv_rub"]) == expected


def test_guest_route_preview_and_pdf_recompute_the_same_simulated_result():
    value = raw("WAREHOUSE")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"] = value["roles"][0]["works"][:1]
    value["roles"][0]["works"][0]["daily_volume"] = "875"
    value["roles"][0]["works"][0]["simulation"] = {
        "scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
        "pickup_service_s": 30, "dropoff_service_s": 30, "turn_delay_s": 5,
        "units_per_cycle": 1,
    }
    app = FastAPI()
    app.include_router(create_object_roles_router(catalog))
    client = TestClient(app)
    preview = client.post("/api/v2/object-roles/WAREHOUSE/preview", json=value)
    assert preview.status_code == 200
    result = preview.json()
    assert result["roles"][0]["works"][0]["simulation"]["status"] == "MODELED"
    pdf = client.post("/api/v2/object-roles/WAREHOUSE/report.pdf", json={
        "expected_catalog_version": "test-v2", "input": value})
    assert pdf.status_code == 200
    pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert result["base_total"]["purchase"]["npv_rub"] in pdf_text
    assert "Маршрут: MODELED" in pdf_text
    value["roles"][0]["works"][0]["simulation"]["scene_revision"] = 2
    assert client.post("/api/v2/object-roles/WAREHOUSE/preview", json=value).status_code == 422


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
    assert Decimal(result["conditional_total"]["purchase"]["payback_years"]) == (
        capex / annual_net).quantize(Decimal("0.01"))
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
    guest = client.post("/api/v2/object-roles/CLINIC/preview", json=payload)
    assert guest.status_code == 200
    assert guest.json() == preview.json()
    saved = client.post(f"/api/v2/projects/{project_id}/object-roles/CLINIC", json={
        "expected_version": 0, "expected_catalog_version": "test-v2", "input": payload})
    assert saved.status_code == 200
    reopened = client.get(f"/api/v2/projects/{project_id}/object-roles/CLINIC")
    assert reopened.json()["latest"]["result_snapshot"] == preview.json()
    conflict = client.post(f"/api/v2/projects/{project_id}/object-roles/CLINIC", json={
        "expected_version": 0, "expected_catalog_version": "test-v2", "input": payload})
    assert conflict.status_code == 409


@pytest.mark.parametrize("kind", ["WAREHOUSE", "AIRPORT", "CLINIC"])
def test_guest_preview_has_no_project_and_rejects_kind_mismatch(kind):
    app = FastAPI()
    app.include_router(create_object_roles_router(catalog))
    app.dependency_overrides[database_session] = lambda: None
    client = TestClient(app)
    result = client.post(f"/api/v2/object-roles/{kind}/preview", json=raw(kind))
    assert result.status_code == 200
    assert result.json()["kind"] == kind
    report = client.post(f"/api/v2/object-roles/{kind}/report.pdf", json={
        "expected_catalog_version": "test-v2", "input": raw(kind)})
    assert report.status_code == 200
    assert report.content.startswith(b"%PDF-")
    pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(report.content)).pages)
    assert "Сценарная оценка роботизации" in pdf_text
    assert result.json()["base_total"]["purchase"]["npv_rub"] in pdf_text
    assert client.post(f"/api/v2/object-roles/{kind}/report.pdf", json={
        "expected_catalog_version": "old", "input": raw(kind)}).status_code == 409
    assert client.post("/api/v2/object-roles/CLINIC/preview", json=raw(kind if kind != "CLINIC" else "AIRPORT")).status_code == 422
    assert client.post(f"/api/v2/projects/{uuid.uuid4()}/object-roles/{kind}", json={}).status_code in (401, 403)
