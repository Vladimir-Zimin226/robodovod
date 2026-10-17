from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from facility_layout_api import FacilityLayout, SaveLayout, create_facility_layout_router


def plan():
    return {"schema_version": "facility-layout-v1", "source": "DRAWN", "width_m": 60,
            "depth_m": 36, "robot_width_m": 1, "items": [
                {"id": "pickup", "kind": "pickup", "x": 4, "y": 17, "width_m": 1,
                 "depth_m": 1, "provenance": "DRAWN"},
                {"id": "dropoff", "kind": "dropoff", "x": 53, "y": 17, "width_m": 1,
                 "depth_m": 1, "provenance": "DRAWN"},
            ]}


def test_plan_contract_rejects_off_floor_geometry_and_unverified_image_payload():
    FacilityLayout.model_validate(plan())
    with pytest.raises(ValidationError, match="facility bounds"):
        FacilityLayout.model_validate({**plan(), "items": [
            plan()["items"][0], {**plan()["items"][1], "x": 60}]})
    with pytest.raises(ValidationError, match="Extra inputs"):
        FacilityLayout.model_validate({**plan(), "imageData": "data:image/png;base64,huge"})


def test_saved_plan_is_immutable_and_bound_to_the_capacity_input():
    project_id, run_id, owner = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    project = SimpleNamespace(id=project_id, owner_id=owner, status="ACTIVE", profile={})
    run = SimpleNamespace(id=run_id, project_id=project_id, run_kind="CAPACITY_ANALYSIS", status="SUCCEEDED",
                          input_snapshot={"process": {"process_id": "zone.main.transport",
                                                      "route_distance": {"normalized_value": "52"}}},
                          input_sha256="a" * 64, result_sha256="b" * 64)

    class Database:
        def __init__(self):
            self.calls = 0
            self.commits = 0

        def scalar(self, _query):
            self.calls += 1
            return project if self.calls % 2 else run

        def commit(self):
            self.commits += 1

    db = Database()
    context = SimpleNamespace(user=SimpleNamespace(id=owner))
    router = create_facility_layout_router()
    save = next(route.endpoint for route in router.routes if "POST" in route.methods)
    read = next(route.endpoint for route in router.routes if "GET" in route.methods)
    payload = SaveLayout.model_validate({"layout": plan(), "process_id": "zone.main.transport",
                                         "applied_distance_m": "52"})
    saved = save(project_id, run_id, payload, context, db)["snapshot"]
    assert saved["capacity_input_sha256"] == run.input_sha256
    assert saved["status"] == "USER_ROUTE_ESTIMATE_GEOMETRY_UNVERIFIED"
    assert read(project_id, run_id, context, db)["snapshot"] == saved
    assert save(project_id, run_id, payload, context, db)["snapshot"] == saved
    assert db.commits == 1
    with pytest.raises(HTTPException) as mismatch:
        save(project_id, run_id, payload.model_copy(update={"applied_distance_m": 55}), context, db)
    assert mismatch.value.status_code == 422
    changed = SaveLayout.model_validate({"layout": {**plan(), "items": [
        plan()["items"][0], {**plan()["items"][1], "x": 52}]},
        "process_id": "zone.main.transport", "applied_distance_m": "52"})
    with pytest.raises(HTTPException) as immutable:
        save(project_id, run_id, changed, context, db)
    assert immutable.value.status_code == 409
