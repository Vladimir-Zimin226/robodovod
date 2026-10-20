from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from robcraft_scene_api import PROFILE_KEY, SaveRobCraftScene, create_robcraft_scene_router


def document():
    base = {"config": {"template": "warehouse", "seed": "SAVED", "editorStart": "empty"}}
    return {"engine": "robcraft", "documentVersion": 1, "base": base,
            "scenePatch": {"format": "robcraft-scene-patch-v1", "base": base,
                           "objects": {}, "created": [], "deleted": [], "robots": {}},
            "inventory": {"slots": ["pallet_rack", *([None] * 8)], "active": 0}}


def endpoint(router, method, suffix):
    return next(route.endpoint for route in router.routes if method in route.methods and route.path.endswith(suffix))


def test_scene_contract_rejects_untrusted_and_oversized_documents():
    SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": document()})
    with pytest.raises(ValidationError, match="unknown RobCraft document fields"):
        SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": {**document(), "payload": "unexpected"}})
    invalid = document()
    invalid["scenePatch"]["created"] = [{"id": "same"}, {"id": "same"}]
    with pytest.raises(ValidationError, match="unique strings"):
        SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": invalid})
    invalid = document()
    invalid["scenePatch"]["created"] = [{"id": str(index), "kind": "decor", "editorId": str(index),
                                           "editorKind": "decor", "type": "decor", "position": [index, 0.5, 0],
                                           "scale": [1, 1, 1], "meta": {"label": "X" * 1000}}
                                          for index in range(400)]
    with pytest.raises(ValidationError, match="size limit"):
        SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": invalid})


def test_robot_assignment_payload_speed_and_duplicate_are_validated():
    scene = document()
    assignment = {"robot_id": "user:pallet_amr:1", "charge_id": "user:charger:2",
                  "work_id": "zone:3", "dropoff_id": "user:station:4", "payload_kg": 500, "speed_mps": 1.2}
    scene["scenePatch"]["assignments"] = [assignment]
    SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": scene})
    scene["scenePatch"]["assignments"] = [assignment, assignment]
    with pytest.raises(ValidationError, match="duplicate robot assignment"):
        SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": scene})
    scene["scenePatch"]["assignments"] = [{**assignment, "speed_mps": 9}]
    with pytest.raises(ValidationError, match="speed_mps"):
        SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": scene})


def test_live_economics_inputs_round_trip_and_reject_unknown_fields():
    scene = document()
    scene["scenePatch"]["economics"] = {"staff_count": 3, "monthly_employer_cost": 50_000,
                                         "realization_share": .5, "discount_rate": .1}
    assert SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": scene}).document == scene
    scene["scenePatch"]["economics"]["discount_rate"] = 2
    with pytest.raises(ValidationError, match="live economics value"):
        SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": scene})


def test_cad_provenance_round_trip_and_reject_invalid_scale():
    scene = document()
    scene["scenePatch"]["cad"] = {"file_name": "warehouse.dxf", "unit_meters": 1,
                                  "wall_height_m": 3, "wall_layers": ["WALLS"],
                                  "obstacle_layers": ["RACKS"], "unsupported_entities": 0,
                                  "malformed_entities": 0}
    assert SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": scene}).document == scene
    scene["scenePatch"]["cad"]["unit_meters"] = 0
    with pytest.raises(ValidationError, match="invalid CAD scale"):
        SaveRobCraftScene.model_validate({"expected_revision": 0, "name": "Склад", "document": scene})


def test_visual_zone_is_bounded_and_versioned_with_scene_document():
    scene = document()
    scene["base"]["config"].update(width=48, depth=38)
    scene["scenePatch"]["zones"] = [{"id": f"zone:{uuid.uuid4()}", "name": "Приёмка",
                                      "points": [[0, 0], [5, 0], [5, 4], [0, 4]]}]
    assert SaveRobCraftScene(expected_revision=0, name="Склад", document=scene).document == scene
    invalid = document()
    invalid["base"]["config"].update(width=48, depth=38)
    invalid["scenePatch"]["zones"] = [{"id": f"zone:{uuid.uuid4()}", "name": "Снаружи",
                                        "points": [[0, 0], [50, 0], [50, 4]]}]
    with pytest.raises(ValidationError, match="outside the scene"):
        SaveRobCraftScene(expected_revision=0, name="Склад", document=invalid)
    crossing = document()
    crossing["base"]["config"].update(width=48, depth=38)
    crossing["scenePatch"]["zones"] = [{"id": f"zone:{uuid.uuid4()}", "name": "Пересечение",
                                         "points": [[0, 0], [6, 4], [0, 4], [6, 0], [8, 6]]}]
    with pytest.raises(ValidationError, match="crossing edges"):
        SaveRobCraftScene(expected_revision=0, name="Склад", document=crossing)


def test_room_polygon_requires_linked_walls_in_project_document():
    scene = document()
    scene["base"]["config"].update(width=48, depth=38)
    points = [[-6, -4], [6, -4], [6, 4], [-6, 4]]
    wall_ids = [f"user:wall:{uuid.uuid4()}" for _ in points]
    scene["scenePatch"]["created"] = [{"id": wall_id, "instance_id": str(uuid.uuid4()), "kind": "wall",
                                           "editorId": wall_id, "editorKind": "wall", "type": "wall",
                                           "position": [0, 1.5, 0], "scale": [4, 3, .3], "yaw": 0,
                                           "color": [.7, .8, .7], "meta": {"label": "Стена"}, "solid": True}
                                          for wall_id in wall_ids]
    scene["scenePatch"]["rooms"] = [{"id": f"room:{uuid.uuid4()}", "name": "Комната",
                                      "points": points, "wall_ids": wall_ids}]
    assert SaveRobCraftScene(expected_revision=0, name="Склад", document=scene).document == scene
    right_wall = {**scene["scenePatch"]["created"][0], "id": f"user:wall:{uuid.uuid4()}",
                  "instance_id": str(uuid.uuid4())}
    right_wall["editorId"] = right_wall["id"]
    frame = {**right_wall, "id": f"user:door_frame:{uuid.uuid4()}", "instance_id": str(uuid.uuid4()),
             "kind": "door_frame", "editorKind": "door_frame", "type": "decor", "solid": False}
    frame["editorId"] = frame["id"]
    scene["scenePatch"]["created"].extend([right_wall, frame])
    scene["scenePatch"]["rooms"][0]["doors"] = [{"edge": 0, "right_wall_id": right_wall["id"], "frame_id": frame["id"]}]
    assert SaveRobCraftScene(expected_revision=0, name="Склад", document=scene).document == scene
    scene["scenePatch"]["rooms"][0]["doors"][0]["edge"] = 99
    with pytest.raises(ValidationError, match="room door edge"):
        SaveRobCraftScene(expected_revision=0, name="Склад", document=scene)
    scene["scenePatch"]["rooms"][0]["doors"][0]["edge"] = 0
    scene["scenePatch"]["objects"][wall_ids[0]] = {"position": [1, 1.5, 0]}
    with pytest.raises(ValidationError, match="room wall changed separately"):
        SaveRobCraftScene(expected_revision=0, name="Склад", document=scene)
    scene["scenePatch"]["objects"].clear()
    scene["scenePatch"]["rooms"][0]["wall_ids"][0] = "missing-wall"
    with pytest.raises(ValidationError, match="room wall references"):
        SaveRobCraftScene(expected_revision=0, name="Склад", document=scene)


def test_operational_roles_are_saved_only_on_compatible_assets_and_work_zones():
    scene = document()
    scene["base"]["config"].update(width=48, depth=38)
    asset_id = f"user:charger:{uuid.uuid4()}"
    scene["scenePatch"]["created"] = [{"id": asset_id, "instance_id": str(uuid.uuid4()), "kind": "charger",
                                           "editorId": asset_id, "editorKind": "charger", "type": "charger",
                                           "position": [0, .08, 0], "scale": [1, .16, 1.2], "yaw": 0,
                                           "color": [.1, .7, .5], "meta": {"label": "Зарядка"}, "solid": False,
                                           "operational_role": "CHARGE"}]
    scene["scenePatch"]["zones"] = [{"id": f"zone:{uuid.uuid4()}", "name": "Работа",
                                      "points": [[-4, -4], [4, -4], [4, 4], [-4, 4]], "operational_role": "WORK"}]
    assert SaveRobCraftScene(expected_revision=0, name="Склад", document=scene).document == scene
    scene["scenePatch"]["created"][0]["operational_role"] = "WORK"
    with pytest.raises(ValidationError, match="object operational role"):
        SaveRobCraftScene(expected_revision=0, name="Склад", document=scene)
    scene["scenePatch"]["created"][0]["operational_role"] = "CHARGE"
    scene["scenePatch"]["zones"][0]["operational_role"] = "DROPOFF"
    with pytest.raises(ValidationError, match="zone operational role"):
        SaveRobCraftScene(expected_revision=0, name="Склад", document=scene)


def test_owner_only_roundtrip_versions_and_optimistic_conflict():
    project_id, owner_id = uuid.uuid4(), uuid.uuid4()
    project = SimpleNamespace(id=project_id, owner_id=owner_id, status="ACTIVE", profile={})

    class Database:
        commits = 0

        def scalar(self, _query):
            return project if self.owner == owner_id else None

        def commit(self):
            self.commits += 1

    db = Database()
    db.owner = owner_id
    context = SimpleNamespace(user=SimpleNamespace(id=owner_id))
    router = create_robcraft_scene_router()
    save = endpoint(router, "PUT", "/robcraft-scene")
    read = endpoint(router, "GET", "/robcraft-scene")
    version = endpoint(router, "GET", "/versions/{revision}")
    first = SaveRobCraftScene(expected_revision=0, name="Склад", document=document())
    assert save(project_id, first, context, db)["revision"] == 1
    assert read(project_id, context, db)["document"] == document()
    assert version(project_id, 1, context, db)["document"] == document()
    second = SaveRobCraftScene(expected_revision=1, name="Склад 2", document=document())
    assert save(project_id, second, context, db)["revision"] == 2
    assert len(project.profile[PROFILE_KEY]["versions"]) == 2
    assert db.commits == 2
    with pytest.raises(HTTPException) as stale:
        save(project_id, first, context, db)
    assert stale.value.status_code == 409
    assert stale.value.detail["current_revision"] == 2
    db.owner = uuid.uuid4()
    with pytest.raises(HTTPException) as hidden:
        read(project_id, SimpleNamespace(user=SimpleNamespace(id=db.owner)), db)
    assert hidden.value.status_code == 404


def test_router_requires_csrf_for_save_and_auth_for_reads():
    router = create_robcraft_scene_router()
    save_route = next(route for route in router.routes if "PUT" in route.methods)
    read_route = next(route for route in router.routes if "GET" in route.methods)
    assert any(dependency.call.__name__ == "require_csrf" for dependency in save_route.dependant.dependencies)
    assert any(dependency.call.__name__ == "require_auth_context" for dependency in read_route.dependant.dependencies)


def test_save_as_creates_independent_project_and_scenarios_atomically():
    owner_id, source_id = uuid.uuid4(), uuid.uuid4()
    source = SimpleNamespace(id=source_id, owner_id=owner_id, status="ACTIVE", profile={})

    class Database:
        def __init__(self):
            self.items = []
            self.commits = 0

        def scalar(self, _query):
            return source

        def add(self, item):
            self.items.append(item)

        def commit(self):
            self.commits += 1

    db = Database()
    context = SimpleNamespace(user=SimpleNamespace(id=owner_id))
    router = create_robcraft_scene_router()
    save_as = endpoint(router, "POST", "/robcraft-scene/save-as")
    payload = SaveRobCraftScene(expected_revision=0, name="  Новый склад  ", document=document())
    result = save_as(source_id, payload, context, db)
    assert result["revision"] == 1
    assert result["name"] == "Новый склад"
    assert db.commits == 1
    assert len(db.items) == 4
    project, *scenarios = db.items
    assert project.id == result["project_id"]
    assert project.copied_from_project_id == source_id
    assert project.profile[PROFILE_KEY]["versions"][0]["document"] == document()
    assert {item.slot for item in scenarios} == {"BASE", "OPTIMISTIC", "PESSIMISTIC"}
    assert all(item.project_id == project.id for item in scenarios)
    assert source.profile == {}
    source.profile = {PROFILE_KEY: {"revision": 1, "versions": []}}
    with pytest.raises(HTTPException) as conflict:
        save_as(source_id, payload, context, db)
    assert conflict.value.status_code == 409
    assert db.commits == 1
    assert len(db.items) == 4


def test_save_as_requires_csrf():
    router = create_robcraft_scene_router()
    route = next(route for route in router.routes if "POST" in route.methods)
    assert any(dependency.call.__name__ == "require_csrf" for dependency in route.dependant.dependencies)
