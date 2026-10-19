from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest
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
    return {"general": template["general"], "roles": roles}


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


def test_portfolio_uses_selected_positions_and_marks_scenario_price():
    raw = sample()
    raw["roles"] = [role for role in raw["roles"] if role["role_code"] in {"picker", "forklift_driver"}]
    raw["selected_positions"] = {"picker": "picking", "forklift_driver": "transport"}
    value = WarehouseRoleInput.model_validate(raw)
    result = analyze_warehouse_roles(value, catalog())
    assert result["portfolio"]["selected_roles"] == 2
    assert result["portfolio"]["capex_rub"] is not None
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
    raw["overrides"] = [{"role_code": "picker", "position_id": "picking", "omit_purchase_price": True}]
    result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(raw), catalog())
    assert result["portfolio"]["capex_rub"] is None
    assert result["portfolio"]["raas_npv_rub"] is not None


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
    assert preview.json()["portfolio"]["selected_roles"] == 1
    saved = client.post(f"/api/v2/projects/{project_id}/warehouse-roles", json={
        "expected_version": 0, "expected_catalog_version": "test-v1", "input": raw,
    })
    assert saved.status_code == 200
    assert saved.json()["latest"]["result_snapshot"] == preview.json()
    reopened = client.get(f"/api/v2/projects/{project_id}/warehouse-roles")
    assert reopened.status_code == 200
    assert reopened.json()["latest"]["result_snapshot"] == preview.json()
