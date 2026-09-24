from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError

from auth import require_auth_context, require_csrf
from calculation.scheduling import SimulationRequestV1
from calculation_contracts import semantic_digest
from database import dispose_database, get_database
from persistence_models import AnalysisRun, Project, SimulationArtifact, User
from simulation_api import create_simulation_router
from simulation_artifacts import load_artifact


pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="disposable PostgreSQL is required")
ROOT = Path(__file__).resolve().parents[1]


def _seed():
    owner_id, other_id, project_id, run_id = (uuid.uuid4() for _ in range(4))
    raw = json.loads((ROOT / "contracts/fixtures/simulation-request-v1.capacity-only.golden.json").read_text(encoding="utf-8"))
    raw["tenant_id"] = raw["scenario_spec"]["analysis"]["tenant_id"] = str(owner_id)
    raw["project_id"] = raw["scenario_spec"]["analysis"]["project_id"] = str(project_id)
    spec = raw["scenario_spec"]
    spec["revision_id"] = "calc_" + semantic_digest({key: value for key, value in spec.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
    raw["request_id"] = f"request.{run_id}"
    request = SimulationRequestV1.model_validate(raw)
    now = datetime.now(timezone.utc)
    with get_database().session() as db:
        db.add_all([
            User(id=owner_id, email_normalized=f"owner-{owner_id}@example.test", password_hash="test-hash"),
            User(id=other_id, email_normalized=f"other-{other_id}@example.test", password_hash="test-hash"),
        ])
        db.flush()
        db.add(Project(id=project_id, owner_id=owner_id, name="Disposable C23 evidence"))
        db.flush()
        db.add(AnalysisRun(
            id=run_id, project_id=project_id, run_kind="FULL_ANALYSIS", status="SUCCEEDED",
            input_snapshot={}, input_sha256=semantic_digest({}).removeprefix("sha256:"),
            result_snapshot={}, result_sha256=semantic_digest({}).removeprefix("sha256:"),
            scenario_spec_snapshot=request.scenario_spec.model_dump(mode="json"),
            scenario_spec_sha256=semantic_digest(request.scenario_spec).removeprefix("sha256:"),
            revision_id=request.scenario_spec.revision_id,
            catalog_version_code="disposable-test", rules_version="disposable-test",
            economics_version="economics-runtime-v2", object_profile_version="disposable-test",
            application_version="production-economics-orchestrator-v2", diagnostics={},
            started_at=now, finished_at=now,
        ))
        db.commit()
    return owner_id, other_id, project_id, run_id, request


@pytest.fixture
def seeded(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    dispose_database()
    values = _seed()
    yield values
    owner_id, other_id, project_id, run_id, _ = values
    with get_database().session() as db:
        db.execute(delete(SimulationArtifact).where(SimulationArtifact.analysis_run_id == run_id))
        db.execute(delete(AnalysisRun).where(AnalysisRun.id == run_id))
        db.execute(delete(Project).where(Project.id == project_id))
        db.execute(delete(User).where(User.id.in_([owner_id, other_id])))
        db.commit()
    dispose_database()


def _client(owner_id: uuid.UUID) -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(create_simulation_router())
    context = SimpleNamespace(user=SimpleNamespace(id=owner_id))
    app.dependency_overrides[require_auth_context] = lambda: context
    client = TestClient(app)
    return app, client


def test_saved_c23_evidence_survives_router_restart_and_denies_other_tenant(seeded):
    owner_id, other_id, project_id, run_id, request = seeded
    app, client = _client(owner_id)
    base = f"/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}"
    assert client.post(base, json=request.model_dump(mode="json")).status_code == 403
    app.dependency_overrides[require_csrf] = lambda: SimpleNamespace(user=SimpleNamespace(id=owner_id))
    started = client.post(base, json=request.model_dump(mode="json"))
    assert started.status_code == 202, started.text
    for _ in range(200):
        state = client.get(f"{base}/{request.request_id}")
        if state.json().get("state") in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.02)
    assert state.status_code == 200 and state.json()["state"] == "SUCCEEDED", state.text
    report = state.json()["report"]
    assert report["schema_version"] == "simulation-report-v2"
    evidence = client.get(f"{base}/{request.request_id}/evidence.json")
    assert evidence.status_code == 200
    assert evidence.json()["analysis_run_id"] == str(run_id)
    assert evidence.json()["scenario_spec_digest"] == semantic_digest(request.scenario_spec)
    assert evidence.headers["x-simulation-report-digest"] == semantic_digest(report)
    with get_database().session() as db:
        stored = load_artifact(db, owner_id, project_id, run_id, request.request_id)
        assert stored is not None and stored.report_digest == semantic_digest(report)
        assert load_artifact(db, other_id, project_id, run_id, request.request_id) is None
        assert db.scalar(select(SimulationArtifact).where(SimulationArtifact.analysis_run_id == run_id)) is not None

    reopened_app, reopened = _client(owner_id)
    assert reopened.get(f"{base}/{request.request_id}").json()["state"] == "SUCCEEDED"
    assert reopened.post(base, json=request.model_dump(mode="json")).status_code == 403
    reopened_app.dependency_overrides[require_csrf] = lambda: SimpleNamespace(user=SimpleNamespace(id=owner_id))
    assert reopened.post(base, json=request.model_dump(mode="json")).json()["state"] == "SUCCEEDED"
    with get_database().session() as db:
        with pytest.raises(DBAPIError, match="immutable"):
            db.execute(text("UPDATE simulation_artifacts SET request_id = request_id WHERE analysis_run_id = :run_id"), {"run_id": run_id})
        db.rollback()
        assert load_artifact(db, owner_id, project_id, run_id, request.request_id) is not None
    app.dependency_overrides[require_auth_context] = lambda: SimpleNamespace(user=SimpleNamespace(id=other_id))
    assert client.get(f"{base}/{request.request_id}").status_code == 404
    assert client.get(f"{base}/{request.request_id}/evidence.json").status_code == 404


def test_saved_c23_rejects_mismatched_scenario_spec_without_writing(seeded):
    owner_id, _, project_id, run_id, request = seeded
    app, client = _client(owner_id)
    app.dependency_overrides[require_csrf] = lambda: SimpleNamespace(user=SimpleNamespace(id=owner_id))
    raw = request.model_dump(mode="json")
    raw["scenario_spec"]["tasks"][0]["demand"]["value"] = "100"
    spec = raw["scenario_spec"]
    spec["revision_id"] = "calc_" + semantic_digest({key: value for key, value in spec.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
    changed = SimulationRequestV1.model_validate(raw)
    base = f"/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}"
    assert client.post(base, json=changed.model_dump(mode="json")).status_code == 409
    with get_database().session() as db:
        assert db.scalar(select(SimulationArtifact).where(SimulationArtifact.analysis_run_id == run_id)) is None
