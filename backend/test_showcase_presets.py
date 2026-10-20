"""Versioned locked examples use the existing object-role API and engine."""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from object_roles_api import create_object_roles_router
from test_object_roles import catalog


PRESETS = json.loads((Path(__file__).resolve().parents[1] / "frontend/src/showcasePresets.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("object_type", ["retail", "airport", "clinic"])
def test_locked_showcase_fixture_is_complete_and_api_compatible(object_type):
    preset = PRESETS[object_type]
    value = preset["input"]
    assert preset["mode"] == "DEMO_LOCKED" and preset["revision"] == 1
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == preset["input_sha256"]
    assert len(value["roles"]) == len(value["roles"][0]["works"]) == 1
    role, work = value["roles"][0], value["roles"][0]["works"][0]
    assert work["selected_position_id"] == "SCENARIO_TYPE"
    assert all(value["general"][key] not in (None, "") for key in (
        "shifts_per_day", "hours_per_shift", "days_per_year", "robot_availability",
        "fleet_reserve_share", "discount_rate", "horizon_years"))
    assert all(role[key] not in (None, "") for key in (
        "headcount", "monthly_employer_cost_rub", "realizable_labor_share", "headcount_source", "salary_source"))
    assert all(work[key] not in (None, "") for key in (
        "daily_volume", "task_payload_kg", "robotizable_share", "manual_units_per_person_shift",
        "scenario_purchase_price_rub", "raas_mode", "basis", "evidence_ref"))
    assert all(work["simulation"][key] is not None for key in (
        "scene_revision", "pickup_xy_m", "dropoff_xy_m", "speed_loaded_mps", "speed_empty_mps",
        "pickup_service_s", "dropoff_service_s", "turn_delay_s", "units_per_cycle"))

    app = FastAPI()
    app.include_router(create_object_roles_router(catalog))
    client = TestClient(app)
    kind = value["kind"]
    preview = client.post(f"/api/v2/object-roles/{kind}/preview", json=value)
    assert preview.status_code == 200, preview.text
    report = preview.json()
    assert report["roles"][0]["works"][0]["simulation"]["status"] == "MODELED"
    assert report["roles"][0]["works"][0]["selected_model_name"] is None
    route = client.post(f"/api/v2/object-roles/{kind}/route-preview", json={
        "input": value, "role_index": 0, "work_index": 0})
    assert route.status_code == 200, route.text
    assert len(route.json()["simulation"]["timestep_pose_samples"]) > 1
    pdf = client.post(f"/api/v2/object-roles/{kind}/report.pdf", json={
        "expected_catalog_version": report["catalog_version"], "input": value})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
