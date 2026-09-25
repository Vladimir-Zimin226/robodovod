from __future__ import annotations

import os

import brain_api as brain
import main
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_persistence_integration import (  # noqa: F401
    _create_project,
    _register,
    clean_persistence,
    migrated_database,
)

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="disposable PostgreSQL required")


def test_brain_project_versions_tenant_and_model_failure(monkeypatch):
    def unavailable(_message, _profile):
        raise HTTPException(503, "model unavailable")
    monkeypatch.setattr(brain, "_call_model", unavailable)
    with TestClient(main.app) as first, TestClient(main.app) as second:
        _, headers = _register(first, "brain-a@example.com")
        _, other_headers = _register(second, "brain-b@example.com")
        project = _create_project(first, headers)
        project_id = project["id"]
        assert second.get(f"/api/brain/projects/{project_id}").status_code == 404
        response = first.post(f"/api/brain/projects/{project_id}/turn", headers=headers,
                              json={"expected_version": 0, "message": "Перевозим 220 паллет на 120 м"})
        assert response.status_code == 200, response.text
        assert response.json()["profile"]["utterance"] == "Перевозим 220 паллет на 120 м"
        assert response.json()["profile"]["profile_version"] == 1
        assert response.json()["profile"]["fields"]["avg_distance_m"]["value"] == "120"
        assert not response.json()["profile"]["fields"]["avg_distance_m"]["confirmed_by_user"]
        assert first.get(f"/api/brain/projects/{project_id}").json()["versions"][0]["model_error"] == "model unavailable"
        stale = first.post(f"/api/brain/projects/{project_id}/edit", headers=headers,
                           json={"expected_version": 0, "field": "avg_distance_m", "value": "120"})
        assert stale.status_code == 409
        cross = second.post(f"/api/brain/projects/{project_id}/edit", headers=other_headers,
                            json={"expected_version": 1, "field": "avg_distance_m", "value": "120"})
        assert cross.status_code == 404
        edited = first.post(f"/api/brain/projects/{project_id}/edit", headers=headers,
                            json={"expected_version": 1, "field": "avg_distance_m", "value": "120", "confirmed": True})
        assert edited.status_code == 200, edited.text
        assert edited.json()["profile"]["parent_version"] == 1
        assert first.get(f"/api/brain/projects/{project_id}").json()["versions"][0]["profile_version"] == 1


def test_brain_multi_process_selection_and_turn_limit(monkeypatch):
    monkeypatch.setattr(brain, "_call_model", lambda *_: (_ for _ in ()).throw(HTTPException(503, "model unavailable")))
    with TestClient(main.app) as client:
        _, headers = _register(client, "brain-processes@example.com")
        project_id = _create_project(client, headers)["id"]
        first = client.post(f"/api/brain/projects/{project_id}/turn", headers=headers,
                            json={"expected_version": 0, "message": "На складе перевозим 220 паллет в сутки на 120 м и убираем помещение"})
        assert first.status_code == 200, first.text
        profile = first.json()["profile"]
        assert set(profile["active_processes"]) == {"warehouse_receiving_shipping", "warehouse_cleaning"}
        second = client.post(f"/api/brain/projects/{project_id}/select-process", headers=headers,
                             json={"expected_version": 1, "process_code": "warehouse_cleaning"})
        assert second.status_code == 200, second.text
        selected = second.json()["profile"]
        assert selected["parent_version"] == 1
        assert "operations_per_day" not in selected["fields"]
        assert selected["process_fields"]["warehouse_receiving_shipping"]["operations_per_day"]["value"] == "220"
        third = client.post(f"/api/brain/projects/{project_id}/turn", headers=headers,
                            json={"expected_version": 2, "message": "Убираем 10000 м² в сутки"})
        assert third.status_code == 200, third.text
        assert third.json()["profile"]["fields"]["operations_per_day"]["unit"] == "m2/day"
        assert third.json()["profile"]["fields"]["operations_per_day"]["value"] == "10000"
        assert not third.json()["readiness"]["technical"]["ready"]
        monkeypatch.setattr(brain, "MAX_TURNS", 2)
        capped = client.post(f"/api/brain/projects/{project_id}/turn", headers=headers,
                             json={"expected_version": 3, "message": "Ещё один вопрос"})
        assert capped.status_code == 429
