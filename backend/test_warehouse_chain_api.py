from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest
from auth import require_auth_context, require_csrf
from database import database_session
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from warehouse_chain_api import (
    SaveChain,
    WarehouseChainSnapshot,
    capability_matrix,
    confirmed_conversion,
    create_warehouse_chain_router,
    default_chain,
    resource_ledger,
    validate_chain,
)


def payload(chain):
    return SaveChain(expected_version=chain["version"], flows=chain["flows"],
                     resources=chain["resources"], conversions=chain["conversions"])


def test_published_schema_accepts_default_and_saved_warehouse_chains():
    schema_path = Path(__file__).resolve().parents[1] / "contracts" / "warehouse-chain-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema == WarehouseChainSnapshot.model_json_schema()
    project_id = uuid.uuid4()
    default = default_chain(project_id)
    jsonschema.validate(default, schema)
    saved = WarehouseChainSnapshot(
        schema_version="warehouse-chain-v1", project_id=project_id, version=1,
        flows=default["flows"], resources=default["resources"], conversions=[],
    ).model_dump(mode="json")
    jsonschema.validate(saved, schema)


def test_warehouse_flows_keep_100000_picking_lines_separate_from_2000_pallets():
    chain = default_chain(uuid.uuid4())
    by_code = {item["code"]: item for item in chain["flows"]}
    by_code["picking_lines"].update(value="100000", source="USER", confirmed=True)
    by_code["receiving_putaway"].update(value="2000", source="EXPERT_ASSUMPTION", source_ref="Типовой склад организаторов", confirmed=True)
    validate_chain(payload(chain))
    assert confirmed_conversion(chain, "picking_lines", "shipping") is None
    assert by_code["shipping"]["value"] is None
    assert by_code["picking_items"]["value"] is None
    chain["conversions"] = [{"from_code": "picking_lines", "to_code": "shipping", "factor": "50",
                             "source": "USER", "source_ref": "Замер потока склада", "confirmed": False}]
    validate_chain(payload(chain))
    assert confirmed_conversion(chain, "picking_lines", "shipping") is None
    chain["conversions"][0]["confirmed"] = True
    assert confirmed_conversion(chain, "picking_lines", "shipping") == 50
    chain["conversions"].append(deepcopy(chain["conversions"][0]))
    with pytest.raises(HTTPException, match="duplicate warehouse unit conversion"):
        validate_chain(payload(chain))


def test_distinct_roles_and_shared_driver_resource_are_not_summed():
    chain = default_chain(uuid.uuid4())
    by_code = {item["code"]: item for item in chain["flows"]}
    assert by_code["receiving_putaway"]["resource_ids"] == by_code["shipping"]["resource_ids"]
    assert by_code["packaging"]["role_code"] == "packaging_line_operator"
    assert by_code["palletizing"]["role_code"] == "packer"
    assert by_code["packaging"]["resource_ids"] != by_code["palletizing"]["resource_ids"]
    resources = {item["resource_id"]: item for item in chain["resources"]}
    resources["staff.packaging_line_operator"].update(amount="4", monthly_gross_salary_rub=None,
                                                       source="USER", confirmed=True)
    resources["staff.packer"].update(amount="3", monthly_gross_salary_rub="75000",
                                      source="USER", confirmed=True)
    validate_chain(payload(chain))
    assert resources["staff.packaging_line_operator"]["monthly_gross_salary_rub"] is None
    ledger = resource_ledger(chain)
    assert ledger["total_status"] == "UNKNOWN"
    assert ledger["rows"][0]["linked_operations"] == ["receiving_putaway", "shipping"]
    assert next(item for item in ledger["rows"] if item["role_code"] == "packer")["annual_gross_fot_rub"] == "2700000"
    bad = deepcopy(chain)
    next(item for item in bad["flows"] if item["code"] == "packaging")["role_code"] = "packer"
    with pytest.raises(HTTPException):
        validate_chain(payload(bad))


def test_picking_physics_needs_all_sourced_fields_and_does_not_enable_formula():
    chain = default_chain(uuid.uuid4())
    pick = next(item for item in chain["flows"] if item["code"] == "picking_lines")
    pick["physical_profile"] = {"picks_per_hour": "100"}
    pick["physical_profile_source"] = "USER"
    pick["physical_profile_confirmed"] = True
    with pytest.raises(HTTPException):
        validate_chain(payload(chain))
    pick["physical_profile_confirmed"] = False
    validate_chain(payload(chain))
    assert capability_matrix(None, chain)["rows"][1]["status"] == "CATALOG_UNAVAILABLE"


def test_project_fot_counts_shared_driver_once():
    chain = default_chain(uuid.uuid4())
    for item in chain["resources"]:
        item.update(amount="2", monthly_gross_salary_rub="100000", source="USER", confirmed=True)
    validate_chain(payload(chain))
    ledger = resource_ledger(chain)
    assert ledger["total_status"] == "KNOWN"
    assert ledger["total_annual_gross_fot_rub"] == str(len(chain["resources"]) * 2 * 100000 * 12)
    driver = next(item for item in ledger["rows"] if item["role_code"] == "forklift_driver")
    assert driver["annual_gross_fot_rub"] == "2400000"
    assert driver["linked_operations"] == ["receiving_putaway", "shipping"]


def test_active_catalog_matrix_never_calls_picking_calculable():
    chain = default_chain(uuid.uuid4())
    def position(pid, name, profile, ready, maturity="OPERATION", family="BRS"):
        model = SimpleNamespace(name=name, type_code=name, description="", applicability=[],
                                system_family=family, maturity_status=maturity,
                                capacity_runtime=SimpleNamespace(calculation_profile=profile, calculation_ready=ready))
        return SimpleNamespace(id=pid, model=model)
    snapshot = SimpleNamespace(version=SimpleNamespace(code="active-v1"), positions=(
        position("transport", "Паллетный транспорт", "TRANSPORT_CYCLE_V1", True),
        position("g2p", "G2P picking", "PICKING_V1", True),
        position("mobile", "Робот-комплектовщик", "PICKING_V1", False, maturity="RND"),
        position("shelf", "Ronavi M: транспортировка стеллажей к станции комплектации", "TRANSPORT_CYCLE_V1", True),
        position("voice", "Pick by Voice", "PICKING_V1", False),
        position("arm", "Роборука", "PICKING_V1", False),
        position("industrial", "Промышленный манипулятор", "PICKING_V1", False),
        position("palletizer", "Паллетизатор", "PALLETIZING_CELL_V1", False, family="fixed_cell"),
        position("rnd-cell", "Паллетизатор RND", "PALLETIZING_THROUGHPUT_V1", True,
                 maturity="RND", family="fixed_cell"),
    ))
    rows = {item["code"]: item for item in capability_matrix(snapshot, chain)["rows"]}
    assert rows["receiving_putaway"]["status"] == "CALCULABLE"
    assert rows["shipping"]["status"] == "CALCULABLE"
    assert rows["picking_lines"]["status"] == "COMPARE_ONLY"
    assert next(item for item in rows["picking_lines"]["candidates"] if item["position_id"] == "g2p")["solution_family"] == "ASRS_G2P"
    assert next(item for item in rows["picking_lines"]["candidates"] if item["position_id"] == "mobile")["solution_family"] == "MOBILE_PICKER"
    assert next(item for item in rows["picking_lines"]["candidates"] if item["position_id"] == "shelf")["solution_family"] == "ASRS_G2P"
    assert next(item for item in rows["picking_lines"]["candidates"] if item["position_id"] == "voice")["solution_family"] == "PICK_ASSIST"
    assert next(item for item in rows["picking_lines"]["candidates"] if item["position_id"] == "arm")["solution_family"] == "ROBOT_ARM"
    assert all(item["position_id"] != "industrial" for item in rows["picking_lines"]["candidates"])
    assert rows["picking_lines"]["calculation_ready_count"] == 0
    assert rows["palletizing"]["status"] == "COMPARE_ONLY"
    assert rows["palletizing"]["calculation_ready_count"] == 0
    assert rows["packaging"]["status"] == "INSUFFICIENT_DATA"
    rnd_only = SimpleNamespace(version=SimpleNamespace(code="rnd-v1"), positions=(
        position("rnd-cell", "Паллетизатор RND", "PALLETIZING_THROUGHPUT_V1", True,
                 maturity="RND", family="fixed_cell"),
    ))
    assert {item["code"]: item for item in capability_matrix(rnd_only, chain)["rows"]}["palletizing"]["status"] == "RESEARCH"


def test_save_creates_child_version_and_rejects_stale_write_without_touching_prior_snapshot():
    project_id = uuid.uuid4()
    owner = uuid.uuid4()
    project = SimpleNamespace(id=project_id, owner_id=owner, status="ACTIVE", profile={"existing": {"keep": True}})
    class Session:
        def scalar(self, _query):
            return project
        def commit(self):
            pass
    catalog = SimpleNamespace(version=SimpleNamespace(code="active-v1"), positions=())
    router = create_warehouse_chain_router(lambda: catalog)
    save = next(route.endpoint for route in router.routes if route.path.endswith("/versions"))
    context = SimpleNamespace(user=SimpleNamespace(id=owner))
    first = default_chain(project_id)
    by_code = {item["code"]: item for item in first["flows"]}
    by_code["picking_lines"].update(value="100000", source="USER", confirmed=True)
    saved = save(project_id, payload(first), context, Session())
    assert saved["chain"]["version"] == 1
    assert project.profile["existing"] == {"keep": True}
    second = deepcopy(saved["chain"])
    next(item for item in second["flows"] if item["code"] == "picking_lines")["value"] = "120000"
    changed = save(project_id, payload(second), context, Session())
    assert changed["chain"]["parent_version"] == 1
    assert project.profile["warehouse_chain_v1"]["versions"][0]["flows"][1]["value"] == "100000"
    with pytest.raises(HTTPException) as error:
        save(project_id, payload(second), context, Session())
    assert error.value.status_code == 409


def test_http_contract_returns_matrix_and_versions_without_mutating_existing_profile():
    project_id = uuid.uuid4()
    project = SimpleNamespace(id=project_id, profile={"existing": {"keep": True}})
    class Session:
        def scalar(self, _query):
            return project
        def commit(self):
            pass
    snapshot = SimpleNamespace(version=SimpleNamespace(code="active-v1"), positions=())
    app = FastAPI()
    app.include_router(create_warehouse_chain_router(lambda: snapshot))
    app.dependency_overrides[require_auth_context] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    app.dependency_overrides[require_csrf] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    app.dependency_overrides[database_session] = lambda: Session()
    with TestClient(app) as client:
        url = f"/api/warehouse-chain/projects/{project_id}"
        first = client.get(url)
        assert first.status_code == 200
        assert len(first.json()["capabilities"]["rows"]) == 7
        assert first.json()["chain"]["version"] == 0
        saved = client.post(f"{url}/versions", json={"expected_version": 0, "flows": first.json()["chain"]["flows"],
                                                       "resources": first.json()["chain"]["resources"], "conversions": []})
        assert saved.status_code == 200, saved.text
        assert saved.json()["chain"]["version"] == 1
        assert client.get(url).json()["versions"] == [1]
        assert project.profile["existing"] == {"keep": True}
