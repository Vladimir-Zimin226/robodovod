from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

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


def test_brain_retry_reuses_saved_message_and_reports_fallback(monkeypatch):
    messages = []

    def model(message, _profile):
        messages.append(message)
        if len(messages) == 1:
            raise brain.BrainModelFailure("TIMEOUT", "timeout")
        return brain.BrainTurn(message="Готово", field_updates=[], process_updates=[],
                               next_action="ask", question=None), {"input": 12, "output": 20}

    monkeypatch.setattr(brain, "_call_model", model)
    with TestClient(main.app) as client:
        _, headers = _register(client, "brain-retry@example.com")
        project_id = _create_project(client, headers)["id"]
        first = client.post(f"/api/brain/projects/{project_id}/turn", headers=headers,
                            json={"expected_version": 0, "message": "На складе 220 паллет в сутки на 120 м"})
        assert first.status_code == 200
        assert first.json()["model_status"] == "TIMEOUT"
        assert first.json()["profile"]["model_failure_kind"] == "TIMEOUT"
        assert client.get(f"/api/brain/projects/{project_id}").json()["profile"]["utterance"] == messages[0]
        stale = client.post(f"/api/brain/projects/{project_id}/retry", headers=headers,
                            json={"expected_version": 0})
        assert stale.status_code == 409, stale.text
        retry = client.post(f"/api/brain/projects/{project_id}/retry", headers=headers,
                            json={"expected_version": 1})
        assert retry.status_code == 200, retry.text
        assert retry.json()["model_status"] == "MODEL"
        assert messages == ["На складе 220 паллет в сутки на 120 м"] * 2
        assert retry.json()["profile"]["profile_version"] == 1
        assert retry.json()["usage"]["turns"] == 1


def test_brain_late_model_reply_does_not_overwrite_manual_edit(monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def slow_model(_message, _profile):
        entered.set()
        assert release.wait(10)
        return brain.BrainTurn(message="Старый ответ", field_updates=[], process_updates=[],
                               next_action="ask", question=None), {"input": 1, "output": 1}

    monkeypatch.setattr(brain, "_call_model", slow_model)
    with TestClient(main.app) as client:
        _, headers = _register(client, "brain-stale@example.com")
        project_id = _create_project(client, headers)["id"]
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(client.post, f"/api/brain/projects/{project_id}/turn", headers=headers,
                                  json={"expected_version": 0, "message": "220 паллет в сутки"})
            assert entered.wait(5)
            reloaded = client.get(f"/api/brain/projects/{project_id}")
            assert reloaded.status_code == 200
            assert reloaded.json()["profile"]["model_status"] == "PENDING"
            edited = client.post(f"/api/brain/projects/{project_id}/edit", headers=headers,
                                 json={"expected_version": 1, "field": "avg_distance_m", "value": "120"})
            assert edited.status_code == 200, edited.text
            release.set()
            assert pending.result(timeout=10).status_code == 409
        latest = client.get(f"/api/brain/projects/{project_id}").json()["profile"]
        assert latest["profile_version"] == 2
        assert latest["fields"]["avg_distance_m"]["value"] == "120"
        assert latest.get("model_message") != "Старый ответ"
