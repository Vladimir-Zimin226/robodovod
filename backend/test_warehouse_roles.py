from decimal import Decimal
from io import BytesIO
from copy import deepcopy
from unittest.mock import patch
from types import SimpleNamespace
import uuid

import pytest
from pypdf import PdfReader
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth_context, require_csrf
from calculation.warehouse_roles import WarehouseRoleInput, analyze_warehouse_roles, warehouse_template
from database import database_session
from warehouse_roles_api import create_warehouse_roles_router


def position(identity, name, profile=None, price=None):
    model = SimpleNamespace(id=identity, name=name, manufacturer="Тест", description="", type_code="AMR",
                            maturity_status="OPERATION", facts=(),
                            capacity_runtime=SimpleNamespace(calculation_profile=profile,
                                                             calculation_ready=bool(profile)))
    return SimpleNamespace(id=identity, model=model,
                           applicability=SimpleNamespace(scenario="", case_text=""),
                           procurement_option=SimpleNamespace(amount=price, currency="RUB",
                                                              evidence_id="catalog-test"))


def sample():
    template = warehouse_template()
    roles = [{key: row[key] for key in ("role_code", "headcount", "monthly_employer_cost_rub",
              "daily_volume", "manual_units_per_person_shift", "robotizable_share", "source", "basis")}
             for row in template["roles"]]
    return {"general": deepcopy(template["general"]), "roles": roles}


def catalog():
    items = [position("transport", "Паллетный AMR", "TRANSPORT_CYCLE_V1", Decimal("3000000")),
             position("storage", "Шаттл хранения"),
             position("picking", "G2P picking robot"),
             position("sorting", "Робот сортировки"),
             position("palletizing", "Робот паллетизации", "PALLETIZING_THROUGHPUT_V1"),
             position("cleaning", "Робот уборки", "CLEANING_AREA_V1"),
             position("inventory", "Робот инвентаризации")]
    return SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test-v1"), positions=items)


def test_every_warehouse_role_is_evaluated_with_a_numeric_fleet():
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(sample()), catalog())
    assert len(result["roles"]) == 8
    assert all(role["candidates"] for role in result["roles"])
    assert all(candidate["fleet"] >= 1 for role in result["roles"] for candidate in role["candidates"])
    assert all(role["catalog_checked"] == 7 for role in result["roles"])
    assert result["portfolio"]["selected_roles"] == 8


def test_payload_fail_cannot_be_selected_for_warehouse_transport():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "forklift_driver"]
    raw["roles"][0]["task_payload_kg"] = "2500"
    robot = position("transport", "Паллетный AMR", "TRANSPORT_CYCLE_V1", Decimal("3000000"))
    robot.model.facts = (SimpleNamespace(code="payload_kg", value="500", canonical_unit="kg",
        resolution_status="VERIFIED_OFFICIAL", evidence_id="source-1"),)
    scoped_catalog = SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test-v1"), positions=[robot])
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), scoped_catalog)
    assert result["roles"][0]["candidates"][0]["physical_fit"] == "FAIL"
    assert result["roles"][0]["candidates"][0]["fleet"] == 0
    assert Decimal(result["roles"][0]["candidates"][0]["npv_rub"]) == 0
    assert result["roles"][0]["selected_position_id"] is None
    assert result["portfolio"]["selected_roles"] == 0
    raw["selected_positions"] = {"forklift_driver": "transport"}
    with pytest.raises(ValueError, match="payload is below"):
        analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), scoped_catalog)
    raw["roles"][0]["task_payload_kg"] = "250"
    assert analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), scoped_catalog)["roles"][0]["candidates"][0]["physical_fit"] == "PASS"


def test_verified_payload_precedes_unknown_without_rejecting_extra_capacity():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "forklift_driver"]
    raw["roles"][0]["task_payload_kg"] = "500"
    unknown = position("unknown", "Паллетный AMR неизвестной грузоподъёмности", "TRANSPORT_CYCLE_V1", Decimal("1000000"))
    unknown.model.facts = ()
    verified = position("verified", "Паллетный AMR 2500", "TRANSPORT_CYCLE_V1", Decimal("3000000"))
    verified.model.facts = (SimpleNamespace(code="payload_kg", value="2500", canonical_unit="kg",
        resolution_status="VERIFIED_OFFICIAL", evidence_id="passport-2500"),)
    scoped_catalog = SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test-v1"), positions=[unknown, verified])
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), scoped_catalog)
    candidates = result["roles"][0]["candidates"]
    assert [candidate["position_id"] for candidate in candidates] == ["verified", "unknown"]
    assert candidates[0]["match_status"] == "PHYSICAL_CHECK_PASSED"
    assert candidates[1]["match_status"] == "NEEDS_VERIFICATION"
    assert result["roles"][0]["selected_position_id"] == "verified"


def test_scene_route_changes_warehouse_fleet_and_money():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "forklift_driver"]
    raw["roles"][0]["daily_volume"] = "700"
    raw["roles"][0]["robotizable_share"] = "1"
    raw["general"]["fleet_reserve_share"] = "0"
    simulation = {"scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
                  "pickup_service_s": 30, "dropoff_service_s": 30, "turn_delay_s": 5,
                  "units_per_cycle": 1}
    raw["roles"][0]["simulation"] = simulation
    base = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())["roles"][0]["candidates"][0]
    raw["roles"][0]["simulation"] = {**simulation, "extra_obstacles": [{"x": 25, "y": 34, "width": 2, "height": 2}]}
    detour = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())["roles"][0]["candidates"][0]
    assert base["fleet"] < detour["fleet"]
    assert Decimal(base["npv_rub"]) > Decimal(detour["npv_rub"])
    raw["roles"][0]["simulation"] = {**simulation, "extra_obstacles": [{"x": 30, "y": 20, "width": 1, "height": 40}]}
    blocked = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    selected = blocked["roles"][0]["candidates"][0]
    assert selected["simulation"]["status"] == "NO_ROUTE"
    assert selected["fleet"] == 0 and selected["fte_equivalent"] == "0.00"
    assert Decimal(blocked["portfolio"]["npv_rub"]) == 0


def test_what_if_volume_and_speed_recompute_warehouse_cycle_and_fleet():
    value = sample()
    value["roles"] = [role for role in value["roles"] if role["role_code"] == "forklift_driver"]
    value["roles"][0]["daily_volume"] = "700"
    value["roles"][0]["robotizable_share"] = "1"
    value["general"]["fleet_reserve_share"] = "0"
    value["roles"][0]["simulation"] = {
        "scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
        "pickup_service_s": 30, "dropoff_service_s": 30, "turn_delay_s": 5,
        "units_per_cycle": 1,
    }
    original = deepcopy(value)
    base = analyze_warehouse_roles(WarehouseRoleInput.model_validate(value), catalog())
    branch_input = deepcopy(value)
    branch_input["roles"][0]["daily_volume"] = "980"
    branch_input["roles"][0]["simulation"]["speed_loaded_mps"] = "0.8"
    branch_input["roles"][0]["simulation"]["speed_empty_mps"] = "0.8"
    branch = analyze_warehouse_roles(WarehouseRoleInput.model_validate(branch_input), catalog())
    before = base["roles"][0]["candidates"][0]
    after = branch["roles"][0]["candidates"][0]
    assert value == original
    assert before["simulation"]["status"] == after["simulation"]["status"] == "MODELED"
    assert after["simulation"]["cycle_s"] > before["simulation"]["cycle_s"]
    assert after["fleet"] > before["fleet"]
    assert branch["portfolio"]["npv_rub"] != base["portfolio"]["npv_rub"]


def test_what_if_horizon_uses_same_warehouse_cashflows_for_purchase_and_rent():
    value = sample()
    value["roles"] = [role for role in value["roles"] if role["role_code"] == "forklift_driver"]
    value["selected_positions"] = {"forklift_driver": "transport"}
    results = {}
    for years in (5, 10):
        branch = deepcopy(value)
        branch["general"]["horizon_years"] = years
        results[years] = analyze_warehouse_roles(WarehouseRoleInput.model_validate(branch), catalog())
    assert value["general"]["horizon_years"] == 5
    assert results[5]["portfolio"]["selected_robot_allocations"] == results[10]["portfolio"]["selected_robot_allocations"]
    for years, report in results.items():
        discount = Decimal(str(report["general"]["discount_rate"]))
        factor = sum((Decimal(1) / (1 + discount) ** year for year in range(1, years + 1)), Decimal(0))
        money = report["portfolio"]
        for capex_key, net_key, npv_key in (
            ("capex_rub", "annual_net_rub", "npv_rub"),
            ("raas_capex_rub", "raas_annual_net_rub", "raas_npv_rub"),
        ):
            expected = (Decimal(money[net_key]) * factor - Decimal(money[capex_key])).quantize(Decimal("0.01"))
            assert Decimal(money[npv_key]) == expected


def test_warehouse_guest_route_preview_and_pdf_share_simulation_values():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "forklift_driver"]
    raw["roles"][0]["daily_volume"] = "700"
    raw["roles"][0]["robotizable_share"] = "1"
    raw["roles"][0]["simulation"] = {
        "scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
        "pickup_service_s": 30, "dropoff_service_s": 30, "turn_delay_s": 5,
        "units_per_cycle": 1,
    }
    app = FastAPI()
    app.include_router(create_warehouse_roles_router(catalog))
    client = TestClient(app)
    preview = client.post("/api/v2/warehouse-roles/preview", json=raw)
    assert preview.status_code == 200
    result = preview.json()
    candidate = result["roles"][0]["candidates"][0]
    assert candidate["simulation"]["status"] == "MODELED"
    pdf = client.post("/api/v2/warehouse-roles/report.pdf", json={
        "expected_catalog_version": "test-v1", "input": raw})
    assert pdf.status_code == 200
    pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert result["portfolio"]["npv_rub"] in pdf_text
    assert "Маршрут: маршрут рассчитан" in pdf_text


def test_warehouse_preview_missing_scene_returns_safe_503():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "forklift_driver"]
    raw["roles"][0]["simulation"] = {
        "scene_revision": 1, "speed_loaded_mps": 1, "speed_empty_mps": 1,
        "pickup_service_s": 30, "dropoff_service_s": 30,
        "turn_delay_s": 5, "units_per_cycle": 1,
    }
    app = FastAPI()
    app.include_router(create_warehouse_roles_router(catalog))
    with patch("calculation.warehouse_roles.load_scene", side_effect=FileNotFoundError("/private/path")):
        response = TestClient(app).post("/api/v2/warehouse-roles/preview", json=raw)
    assert response.status_code == 503
    assert "/private/path" not in response.text
    assert "Сцена симуляции" in response.json()["detail"]


def test_portfolio_uses_selected_positions_and_marks_scenario_price():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] in {"picker", "forklift_driver"}]
    raw["selected_positions"] = {"picker": "picking", "forklift_driver": "transport"}
    value = WarehouseRoleInput.model_validate(raw)
    result = analyze_warehouse_roles(value, catalog())
    assert result["portfolio"]["selected_roles"] == 2
    assert result["portfolio"]["capex_rub"] is not None
    assert Decimal(result["portfolio"]["purchase_payback_years"]) == (
        Decimal(result["portfolio"]["capex_rub"]) / Decimal(result["portfolio"]["annual_net_rub"])).quantize(Decimal("0.01"))
    picker = next(role for role in result["roles"] if role["role_code"] == "picker")
    assert picker["candidates"][0]["price_source"] == "SCENARIO_ASSUMPTION"
    raw["overrides"] = [{"role_code": "picker", "position_id": "picking",
                         "units_per_hour": "250", "price_rub": "4000000"}]
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    assert result["portfolio"]["capex_rub"] is not None
    assert result["portfolio"]["npv_rub"] is not None
    picker = next(role for role in result["roles"] if role["role_code"] == "picker")
    chosen = next(item for item in picker["candidates"] if item["position_id"] == "picking")
    assert chosen["rate_source"] == "USER"


def test_missing_price_in_modified_project_leaves_other_branch_numeric():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "picker"]
    raw["selected_positions"] = {"picker": "picking"}
    raw["overrides"] = [{"role_code": "picker", "position_id": "picking", "omit_purchase_price": True,
                          "raas_mode": "FIXED"}]
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    assert result["portfolio"]["capex_rub"] is None
    assert result["portfolio"]["raas_npv_rub"] is not None
    raw["overrides"][0]["raas_mode"] = "PERCENT"
    percent = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    assert percent["portfolio"]["raas_npv_rub"] is None
    assert percent["portfolio"]["missing_raas"] == ["picker/picking.price_rub"]


def test_percent_raas_and_59_picker_fleet_explain_their_inputs():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "picker"]
    raw["roles"][0].update(headcount="30", daily_volume="100000", manual_units_per_person_shift="1250", robotizable_share="0.5")
    raw["general"]["shifts_per_day"] = 1
    raw["selected_positions"] = {"picker": "picking"}
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    chosen = result["roles"][0]["candidates"][0]
    assert chosen["fleet"] == 59
    assert chosen["manual_capacity_units_per_day"] == "37500.00"
    assert chosen["demand_warning"]
    assert chosen["fleet_formula"]["target_units_per_day"] == "50000.00"
    assert chosen["raas_mode"] == "PERCENT"
    assert chosen["raas_percent_monthly"] == "2.00"
    assert Decimal(chosen["raas_monthly_rub"]) == Decimal(chosen["price_rub"]) * Decimal("0.02")
    raw["general"]["shifts_per_day"] = 2
    two_shifts = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    assert two_shifts["roles"][0]["candidates"][0]["fleet"] == 30


def test_duplicate_role_and_unrelated_selection_rejected():
    raw = sample()
    raw["roles"][1] = raw["roles"][0]
    with pytest.raises(ValueError, match="duplicate role"):
        WarehouseRoleInput.model_validate(raw)
    raw = sample()
    raw["selected_positions"] = {"picker": "inventory"}
    with pytest.raises(ValueError, match="not a candidate"):
        analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())


def test_verified_catalog_throughput_replaces_fallback_assumption():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "cleaner"]
    item = position("cleaning", "Робот уборки", "CLEANING_AREA_V1")
    item.model.facts = (SimpleNamespace(code="cleaning_rate_m2_h", value="500", canonical_unit="m2/h",
                                        resolution_status="VERIFIED_OFFICIAL", evidence_id="vendor-rate-1"),)
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw),
                                     SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test"),
                                                     positions=[item]))
    candidate = result["roles"][0]["candidates"][0]
    assert candidate["robot_units_per_hour"] == "500.00"
    assert candidate["rate_source"] == "CATALOG_VERIFIED"
    assert candidate["rate_evidence_ref"] == "vendor-rate-1"


def test_explicitly_removed_robot_is_not_automatically_reselected():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "picker"]
    raw["selected_positions"] = {"picker": "NONE"}
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    assert result["roles"][0]["candidates"]
    assert result["roles"][0]["selected_position_id"] is None
    assert result["portfolio"]["selected_roles"] == 0


def test_broad_sorting_catalog_tag_does_not_recommend_storage_as_sorting_robot():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] in {"picker", "sorter"}]
    storage = position("storage", "AS-RS B")
    storage.applicability.scenario = "Сортировка грузов"
    storage.model.description = "Автоматическая система хранения. Подача груза по принципу товар к человеку."
    voice = position("voice", "Pick by Voice")
    voice.applicability.scenario = "Сортировка грузов"
    voice.model.description = "Система голосового управления складскими операциями."
    picking = position("picking", "Ronavi M")
    picking.model.description = "Робот для транспортировки стеллажей к станции комплектации."
    sorting = position("sorting", "Ronavi SR")
    sorting.model.description = "Автономный мобильный робот-сортировщик для сортировки посылок."
    snapshot = SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test"),
                               positions=[storage, voice, picking, sorting])
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), snapshot)
    by_role = {role["role_code"]: role for role in result["roles"]}
    assert [item["name"] for item in by_role["picker"]["candidates"]] == ["Ronavi M"]
    assert [item["name"] for item in by_role["sorter"]["candidates"]] == ["Ronavi SR"]
    assert by_role["picker"]["selected_position_id"] == "picking"
    assert by_role["sorter"]["selected_position_id"] == "sorting"
    assert by_role["picker"]["candidates"][0]["work_scope"] == "DELIVERY_TO_PICKING_STATION"


def test_pallet_roles_do_not_treat_every_transport_robot_as_a_pallet_robot():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] in {"loader", "forklift_driver"}]
    light_amr = position("small", "AMR 100", "TRANSPORT_CYCLE_V1")
    light_amr.model.description = "Робот для перевозки мелких коробок."
    pallet_amr = position("pallet", "AK-2000-2", "TRANSPORT_CYCLE_V1")
    pallet_amr.model.description = "Беспилотная перевозка паллетных грузов."
    snapshot = SimpleNamespace(version=SimpleNamespace(status="PUBLISHED", code="test"),
                               positions=[light_amr, pallet_amr])
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), snapshot)
    assert all([item["position_id"] for item in role["candidates"]] == ["pallet"]
               for role in result["roles"])
    loader = next(role for role in result["roles"] if role["role_code"] == "loader")
    assert loader["candidates"][0]["work_scope"] == "PALLET_TRANSPORT_ONLY"


def test_owner_bound_preview_save_and_reopen_use_the_same_scenario():
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project = SimpleNamespace(id=project_id, owner_id=user_id, status="ACTIVE", profile={})

    class FakeSession:
        def scalar(self, _query):
            return project

        def add(self, _row):
            pass

        def commit(self):
            pass

    context = SimpleNamespace(user=SimpleNamespace(id=user_id))
    app = FastAPI()
    app.include_router(create_warehouse_roles_router(catalog))
    app.dependency_overrides[require_csrf] = lambda: context
    app.dependency_overrides[require_auth_context] = lambda: context
    app.dependency_overrides[database_session] = lambda: FakeSession()
    client = TestClient(app)
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] == "picker"]
    preview = client.post(f"/api/v2/projects/{project_id}/warehouse-roles/preview", json=raw)
    assert preview.status_code == 200
    guest = client.post("/api/v2/warehouse-roles/preview", json=raw)
    assert guest.status_code == 200
    assert guest.json() == preview.json()
    assert preview.json()["portfolio"]["selected_roles"] == 1
    saved = client.post(f"/api/v2/projects/{project_id}/warehouse-roles", json={
        "expected_version": 0, "expected_catalog_version": "test-v1", "input": raw,
    })
    assert saved.status_code == 200
    assert saved.json()["latest"]["result_snapshot"] == preview.json()
    reopened = client.get(f"/api/v2/projects/{project_id}/warehouse-roles")
    assert reopened.status_code == 200
    assert reopened.json()["latest"]["result_snapshot"] == preview.json()


def test_guest_warehouse_preview_requires_no_project_or_auth():
    app = FastAPI()
    app.include_router(create_warehouse_roles_router(catalog))
    raw = sample()
    raw["roles"] = raw["roles"][:1]
    result = TestClient(app).post("/api/v2/warehouse-roles/preview", json=raw)
    assert result.status_code == 200
    assert result.json()["schema_version"] == "warehouse-role-analysis-v2"
    report = TestClient(app).post("/api/v2/warehouse-roles/report.pdf", json={
        "expected_catalog_version": "test-v1", "input": raw})
    assert report.status_code == 200
    pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(report.content)).pages)
    assert "Сценарная оценка роботизации" in pdf_text
    assert result.json()["portfolio"]["npv_rub"] in pdf_text
