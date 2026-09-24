from __future__ import annotations

import json
import io
import os
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import catalog_models  # noqa: F401
import main
import persistence_models  # noqa: F401
from auth import SESSION_COOKIE
from bootstrap_admin import BootstrapError, bootstrap_admin
from database import dispose_database, get_database
from economics_route_activation import (
    activate_economics_route,
    resolve_active_economics_version,
    rollback_economics_route,
)
from economics_runtime_migration import EconomicsDualRunReportV1, EconomicsV2ExecutionV1
from persistence_api import create_persistence_router, purge_expired_tombstones
from persistence_models import (
    AnalysisRun,
    AnalysisRunEconomicsVersion,
    AuditEntry,
    Project,
    ProjectFile,
    ProjectFileImport,
    Scenario,
    User,
)
from project_file_intake import build_csv_template
from storage_models import Base, CatalogVersion
from test_capacity_analysis_service import request as capacity_request, snapshot as capacity_snapshot
from test_economics_orchestrator import (
    _capacity_request as economics_capacity_request,
    _inputs as economics_inputs,
    _snapshot as economics_snapshot,
)
from test_robot_fixtures import synthetic_snapshot


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
ALEMBIC_CONFIG = Path(__file__).with_name("alembic.ini")
TABLES_0003 = {
    "users",
    "user_sessions",
    "projects",
    "project_files",
    "scenarios",
    "analysis_runs",
    "audit_entries",
    "project_deletion_jobs",
}
TABLES_0006 = {"project_file_imports"}
TABLES_0010 = {"analysis_run_economics_versions", "economics_route_activations"}
PASSWORD_A = "correct horse battery staple"
PASSWORD_B = "another secure passphrase"
TEST_RUNTIME_CATALOG_ID = uuid.UUID("00000000-0000-0000-0000-000000000029")


def _config() -> Config:
    return Config(str(ALEMBIC_CONFIG))


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    engine = create_engine(TEST_DATABASE_URL, hide_parameters=True)
    dispose_database()
    try:
        command.downgrade(_config(), "base")
        command.upgrade(_config(), "head")
        assert TABLES_0003 | TABLES_0006 | TABLES_0010 <= set(inspect(engine).get_table_names())
        command.upgrade(_config(), "head")
        yield engine
    finally:
        dispose_database()
        engine.dispose()
        monkeypatch.undo()


@pytest.fixture(autouse=True)
def clean_persistence(migrated_database, tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FILE_STORAGE_ROOT", str(tmp_path / "uploads"))

    class LegacyRuntimeSource:
        def load_runtime(self):
            snapshot = synthetic_snapshot()
            return replace(
                snapshot,
                version=replace(
                    snapshot.version,
                    id=str(TEST_RUNTIME_CATALOG_ID),
                    code="c29-test-runtime-v1",
                    status="PUBLISHED",
                ),
            )

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", LegacyRuntimeSource())
    with migrated_database.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, audit_entries, project_deletion_jobs "
                ", economics_route_activations "
                "RESTART IDENTITY CASCADE"
            )
        )
        connection.execute(text(
            "DELETE FROM catalog_versions WHERE code LIKE 'persistence-test-%' "
            "OR code IN ('economics-c28-test', 'c29-test-runtime-v1', 'orchestrator-test-v1')"
        ))
        connection.execute(text(
            "INSERT INTO catalog_versions "
            "(id, code, status, schema_version, content_sha256, created_at, updated_at, validated_at, published_at) "
            "VALUES (:id, 'c29-test-runtime-v1', 'PUBLISHED', 'test-only-v1', :sha, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"id": TEST_RUNTIME_CATALOG_ID, "sha": "c" * 64})
    dispose_database()
    yield
    dispose_database()


def _register(client: TestClient, email: str, password: str = PASSWORD_A):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": "Тест Пользователь"},
    )
    assert response.status_code == 201, response.text
    return response.json(), {"X-CSRF-Token": response.json()["csrf_token"]}


def _create_project(client: TestClient, headers: dict[str, str]):
    response = client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Склад Север", "description": "Тестовый проект"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _analysis_input() -> dict:
    fixture = Path(__file__).with_name("fixtures") / "economics-warehouse-v1.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["input"]


def test_0003_upgrade_and_orm_metadata_match(migrated_database):
    assert TABLES_0003 | TABLES_0006 | TABLES_0010 <= set(inspect(migrated_database).get_table_names())
    with migrated_database.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_registration_session_csrf_and_three_scenarios():
    with TestClient(main.app) as client:
        public_admin = client.post(
            "/api/auth/register",
            json={
                "email": "forbidden-admin@example.com",
                "password": PASSWORD_A,
                "role": "ADMIN",
            },
        )
        assert public_admin.status_code == 422
        auth, headers = _register(client, " Owner@Example.COM ")
        assert auth["user"]["email"] == "owner@example.com"
        assert auth["user"]["role"] == "USER"
        assert SESSION_COOKIE in client.cookies
        assert client.post("/api/projects", json={"name": "No CSRF"}).status_code == 403
        project = _create_project(client, headers)
        assert {item["slot"] for item in project["scenarios"]} == {
            "BASE",
            "OPTIMISTIC",
            "PESSIMISTIC",
        }
        renamed = client.patch(
            f"/api/projects/{project['id']}",
            headers=headers,
            json={"name": "Склад Север — версия 2"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Склад Север — версия 2"
        copied = client.post(f"/api/projects/{project['id']}/copy", headers=headers)
        assert copied.status_code == 201
        assert copied.json()["copied_from_project_id"] == project["id"]
        assert len(copied.json()["scenarios"]) == 3
        logout = client.post("/api/auth/logout", headers=headers)
        assert logout.status_code == 204
        assert client.get("/api/auth/me").status_code == 401

    with get_database().session() as db:
        user = db.scalar(select(User).where(User.email_normalized == "owner@example.com"))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD_A not in user.password_hash


def test_owner_predicate_hides_projects_and_runs_from_another_user():
    with TestClient(main.app) as owner:
        _, owner_headers = _register(owner, "owner@example.com")
        project = _create_project(owner, owner_headers)
        base = next(item for item in project["scenarios"] if item["slot"] == "BASE")
        run_response = owner.post(
            f"/api/projects/{project['id']}/analysis-runs",
            headers=owner_headers,
            json={"scenario_id": base["id"], "input": _analysis_input()},
        )
        assert run_response.status_code == 201, run_response.text
        run = run_response.json()
        assert run["status"] == "SUCCEEDED"

    with TestClient(main.app) as intruder:
        _, intruder_headers = _register(intruder, "intruder@example.com", PASSWORD_B)
        assert intruder.get(f"/api/projects/{project['id']}").status_code == 404
        assert intruder.patch(
            f"/api/projects/{project['id']}",
            headers=intruder_headers,
            json={"name": "Украден"},
        ).status_code == 404
        assert intruder.get(
            f"/api/projects/{project['id']}/analysis-runs/{run['id']}"
        ).status_code == 404
        assert intruder.get(
            f"/api/projects/{project['id']}/analysis-runs/{run['id']}/legacy-replay"
        ).status_code == 404


def test_run_snapshot_is_immutable_and_survives_new_catalog_version(migrated_database):
    with TestClient(main.app) as client:
        _, headers = _register(client, "runner@example.com")
        project = _create_project(client, headers)
        scenario = next(item for item in project["scenarios"] if item["slot"] == "BASE")
        created = client.post(
            f"/api/projects/{project['id']}/analysis-runs",
            headers=headers,
            json={"scenario_id": scenario["id"], "input": _analysis_input()},
        )
        assert created.status_code == 201, created.text
        assert created.headers["deprecation"] == "true"
        assert "successor-version" in created.headers["link"]
        snapshot = created.json()
        readiness = snapshot["result_snapshot"]["readiness_report"]
        assert readiness["schema_version"] == "readiness-report-v1"
        assert readiness["rules_version"] == "readiness-rules-v1"
        assert snapshot["versions"]["rules"] == (
            "legacy-calculation-rules-v1+readiness-rules-v1"
        )

        with migrated_database.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO catalog_versions (id, code, schema_version) "
                    "VALUES (:id, :code, '1')"
                ),
                {"id": uuid.uuid4(), "code": f"persistence-test-{uuid.uuid4()}"},
            )
        reopened = client.get(
            f"/api/projects/{project['id']}/analysis-runs/{snapshot['id']}"
        )
        assert reopened.status_code == 200
        assert reopened.json()["result_snapshot"] == snapshot["result_snapshot"]
        assert reopened.json()["checksums"] == snapshot["checksums"]
        assert reopened.json()["economics_runtime"]["replay_mode"] == "SAVED_SNAPSHOT_ONLY"
        replay = client.get(
            f"/api/projects/{project['id']}/analysis-runs/{snapshot['id']}/legacy-replay"
        )
        assert replay.status_code == 200
        assert replay.json()["result_snapshot"] == snapshot["result_snapshot"]
        assert replay.json()["result_sha256"] == snapshot["checksums"]["result"]
        assert replay.json()["route"]["mutates_source_run"] is False

    with migrated_database.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "UPDATE analysis_runs SET result_snapshot = '{\"changed\": true}'::jsonb "
                        "WHERE id = :id"
                    ),
                    {"id": snapshot["id"]},
                )
        finally:
            transaction.rollback()
    with get_database().session() as db:
        mapping = db.get(AnalysisRunEconomicsVersion, uuid.UUID(snapshot["id"]))
        assert mapping is not None
        assert mapping.fte_basis_status == "UNKNOWN_LEGACY_BASIS"
    with migrated_database.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(SQLAlchemyError):
                connection.execute(
                    text(
                        "UPDATE analysis_run_economics_versions "
                        "SET viewer_version = 'commercial-scenarios-viewer-v2' WHERE run_id = :id"
                    ),
                    {"id": snapshot["id"]},
                )
        finally:
            transaction.rollback()


def test_rerun_creates_a_new_record_from_stored_input():
    with TestClient(main.app) as client:
        _, headers = _register(client, "rerun@example.com")
        project = _create_project(client, headers)
        scenario = next(item for item in project["scenarios"] if item["slot"] == "BASE")
        first = client.post(
            f"/api/projects/{project['id']}/analysis-runs",
            headers=headers,
            json={"scenario_id": scenario["id"], "input": _analysis_input()},
        ).json()
        assert client.post(
            f"/api/projects/{project['id']}/analysis-runs/{first['id']}/rerun"
        ).status_code == 403
        second_response = client.post(
            f"/api/projects/{project['id']}/analysis-runs/{first['id']}/rerun",
            headers=headers,
        )
        assert second_response.status_code == 201, second_response.text
        assert second_response.headers["deprecation"] == "true"
        second = second_response.json()
        assert second["id"] != first["id"]
        assert second["parent_run_id"] == first["id"]
        assert second["input_snapshot"] == first["input_snapshot"]


def test_economics_route_activation_and_rollback_change_no_run_data(migrated_database):
    report = EconomicsDualRunReportV1.model_validate_json(
        (Path(__file__).resolve().parents[1] / "contracts/fixtures/economics-dual-run-report-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )
    activated = activate_economics_route(get_database(), report, actor_subject="c28-test")
    assert activated.economics_version == "economics-runtime-v2"
    assert resolve_active_economics_version(get_database()) == "economics-runtime-v2"
    assert activated.rollback_economics_version == "legacy-economics-v1"
    rolled_back = rollback_economics_route(get_database(), actor_subject="c28-test")
    assert rolled_back.economics_version == "legacy-economics-v1"
    assert resolve_active_economics_version(get_database()) == "legacy-economics-v1"
    with migrated_database.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM analysis_runs")) == 0
        history = connection.scalar(text("SELECT count(*) FROM economics_route_activations"))
        assert history == 2


def test_v2_new_run_is_server_computed_csrf_scoped_and_version_mapped():
    catalog_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    with get_database().session() as db:
        db.add(CatalogVersion(
            id=catalog_id, code="economics-c28-test", status="PUBLISHED",
            schema_version="test", content_sha256="b" * 64,
            created_at=now, updated_at=now, validated_at=now, published_at=now,
        ))
        db.commit()
    report = EconomicsDualRunReportV1.model_validate_json(
        (Path(__file__).resolve().parents[1] / "contracts/fixtures/economics-dual-run-report-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )
    activate_economics_route(get_database(), report, actor_subject="c28-api-test")
    commercial = json.loads(
        (Path(__file__).resolve().parents[1] / "frontend/tests/fixtures/commercial-scenarios-v2.golden.json").read_text(
            encoding="utf-8"
        )
    )
    scenario_spec = json.loads(
        (Path(__file__).resolve().parents[1] / "contracts/fixtures/scenario-spec-v2.capacity-only-cleaner.golden.json").read_text(
            encoding="utf-8"
        )
    )

    def execute_v2(input_snapshot, _catalog):
        assert "fte_cost_rub" not in input_snapshot
        return EconomicsV2ExecutionV1(
            result_snapshot=commercial,
            scenario_spec_snapshot=scenario_spec,
            revision_id=scenario_spec["revision_id"],
            rules_version="economics-rules-v2",
            object_profile_version="calculation-intake-v2",
            application_version="c28-test",
            diagnostics={"route": "ECONOMICS_V2"},
        )

    test_app = FastAPI()
    test_app.include_router(create_persistence_router(
        lambda _: (_ for _ in ()).throw(AssertionError("legacy executor called")),
        resolve_catalog=lambda: SimpleNamespace(
            version=SimpleNamespace(id=str(catalog_id), code="economics-c28-test")
        ),
        resolve_economics_version=lambda: resolve_active_economics_version(get_database()),
        calculate_economics_v2=execute_v2,
    ))
    with TestClient(test_app) as client:
        _, headers = _register(client, "v2-owner@example.com")
        project = _create_project(client, headers)
        scenario = next(item for item in project["scenarios"] if item["slot"] == "BASE")
        endpoint = f"/api/v2/projects/{project['id']}/economics-runs"
        payload = {
            "scenario_id": scenario["id"],
            "input": {"roles": [{"monthly_gross_salary": {"status": "KNOWN", "value": "100000"}}]},
        }
        assert client.post(endpoint, json=payload).status_code == 403
        rejected = client.post(
            endpoint, headers=headers,
            json={"scenario_id": scenario["id"], "input": {"fte_cost_rub": 1200000}},
        )
        assert rejected.status_code == 422
        created = client.post(endpoint, headers=headers, json=payload)
        assert created.status_code == 201, created.text
        run = created.json()
        assert run["versions"]["economics"] == "economics-runtime-v2"
        assert run["economics_runtime"]["viewer_version"] == "commercial-scenarios-viewer-v2"
        assert run["economics_runtime"]["fte_basis_status"] == "EXPLICIT_GROSS"
        reopened = client.get(f"/api/projects/{project['id']}/analysis-runs/{run['id']}")
        assert reopened.status_code == 200
        assert reopened.json()["result_snapshot"] == commercial


def test_capacity_run_is_independent_immutable_and_tenant_scoped(monkeypatch, migrated_database):
    catalog = capacity_snapshot()

    class CapacitySource:
        def load_capacity(self):
            return catalog

        def load_runtime(self):
            raise AssertionError("C11 must not read the legacy economics runtime")

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", CapacitySource())
    now = datetime.now(timezone.utc)
    with get_database().session() as db:
        db.add(CatalogVersion(
            id=uuid.UUID(catalog.version.id), code=catalog.version.code,
            status="PUBLISHED", schema_version="4", content_sha256="a" * 64,
            created_at=now, updated_at=now, validated_at=now, published_at=now,
        ))
        db.commit()
    with TestClient(main.app) as owner:
        _, headers = _register(owner, "capacity-owner@example.com")
        project = _create_project(owner, headers)
        payload = capacity_request().model_dump(mode="json")
        payload["project_id"] = project["id"]
        assert owner.post("/api/v2/capacity-analyses", json=payload).status_code == 403
        created = owner.post("/api/v2/capacity-analyses", headers=headers, json=payload)
        assert created.status_code == 201, created.text
        result = created.json()
        assert result["capacity"]["status"] == "BLOCKED"
        reopened = owner.get(f"/api/v2/capacity-analyses/{result['run_id']}")
        assert reopened.status_code == 200
        assert reopened.json() == result
        wrong_rerun = owner.post(
            f"/api/projects/{project['id']}/analysis-runs/{result['run_id']}/rerun",
            headers=headers,
        )
        assert wrong_rerun.status_code == 409

    with get_database().session() as db:
        run = db.get(AnalysisRun, uuid.UUID(result["run_id"]))
        assert run.run_kind == "CAPACITY_ANALYSIS"
        assert run.economics_version is None and run.scenario_spec_snapshot is None
        assert run.trace_snapshot == result["trace"]
        assert run.version_bindings_snapshot == result["trace"]["versions"]

    with TestClient(main.app) as intruder:
        _register(intruder, "capacity-intruder@example.com", PASSWORD_B)
        assert intruder.get(f"/api/v2/capacity-analyses/{result['run_id']}").status_code == 404

    with migrated_database.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text("UPDATE analysis_runs SET trace_snapshot = '{}'::jsonb WHERE id = :id"),
                    {"id": result["run_id"]},
                )
        finally:
            transaction.rollback()


def test_preliminary_capacity_run_requires_csrf_and_reopens_with_c05_unknowns(monkeypatch):
    catalog = capacity_snapshot()

    class CapacitySource:
        def load_capacity(self):
            return catalog

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", CapacitySource())
    now = datetime.now(timezone.utc)
    with get_database().session() as db:
        db.add(CatalogVersion(
            id=uuid.UUID(catalog.version.id), code=catalog.version.code,
            status="PUBLISHED", schema_version="4", content_sha256="a" * 64,
            created_at=now, updated_at=now, validated_at=now, published_at=now,
        ))
        db.commit()
    with TestClient(main.app) as owner:
        _, headers = _register(owner, "demo-capacity-owner@example.com")
        project = _create_project(owner, headers)
        payload = capacity_request().model_dump(mode="json")
        payload.update(project_id=project["id"], execution_mode="PRELIMINARY_DEMO",
                       demo_assumptions_confirmed=True)
        assert owner.post("/api/v2/capacity-analyses", json=payload).status_code == 403
        created = owner.post("/api/v2/capacity-analyses", headers=headers, json=payload)
        assert created.status_code == 201, created.text
        result = created.json()
        assert result["capacity"]["status"] == "WITH_ASSUMPTIONS"
        assert result["capacity"]["value"]["recommended_fleet"] > 0
        assert any(check["status"] == "UNKNOWN" for check in result["trace"]["constraints"])
        assert owner.get(f"/api/v2/capacity-analyses/{result['run_id']}").json() == result
    with TestClient(main.app) as intruder:
        _register(intruder, "demo-capacity-intruder@example.com", PASSWORD_B)
        assert intruder.get(f"/api/v2/capacity-analyses/{result['run_id']}").status_code == 404


def test_production_c11_to_c21_run_replay_rerun_export_and_tenant_isolation(
    monkeypatch,
):
    catalog = economics_snapshot()

    class ProductionCapacitySource:
        def load_capacity(self):
            return catalog

        def load_runtime(self):
            raise AssertionError("production economics v2 must not use legacy runtime")

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", ProductionCapacitySource())
    now = datetime.now(timezone.utc)
    with get_database().session() as db:
        db.add(
            CatalogVersion(
                id=uuid.UUID(catalog.version.id),
                code=catalog.version.code,
                status="PUBLISHED",
                schema_version="4",
                content_sha256="d" * 64,
                created_at=now,
                updated_at=now,
                validated_at=now,
                published_at=now,
            )
        )
        db.commit()
    report = EconomicsDualRunReportV1.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "contracts/fixtures/economics-dual-run-report-v1.golden.json"
        ).read_text(encoding="utf-8")
    )
    activate_economics_route(
        get_database(), report, actor_subject="production-orchestrator-api-test"
    )

    with TestClient(main.app) as owner:
        _, headers = _register(owner, "production-flow-owner@example.com")
        project = _create_project(owner, headers)
        scenario = next(item for item in project["scenarios"] if item["slot"] == "BASE")
        capacity_payload = economics_capacity_request().model_dump(mode="json")
        capacity_payload["project_id"] = project["id"]
        capacity_created = owner.post(
            "/api/v2/capacity-analyses", headers=headers, json=capacity_payload
        )
        assert capacity_created.status_code == 201, capacity_created.text
        capacity = capacity_created.json()
        assert capacity["capacity"]["status"] == "WITH_ASSUMPTIONS"

        endpoint = f"/api/v2/projects/{project['id']}/economics-runs"
        economics_payload = {
            "scenario_id": scenario["id"],
            "capacity_run_id": capacity["run_id"],
            "input": economics_inputs(),
        }
        assert owner.post(endpoint, json=economics_payload).status_code == 403
        created_response = owner.post(
            endpoint, headers=headers, json=economics_payload
        )
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()
        assert created["status"] == "SUCCEEDED"
        assert created["parent_run_id"] == capacity["run_id"]
        assert created["result_snapshot"]["schema_version"] == "commercial-scenarios-bundle-v2"
        assert len(created["result_snapshot"]["scenarios"]) == 6
        assert all(
            item["procurement"]["procurement_status"] == "UNVERIFIED"
            for item in created["result_snapshot"]["scenarios"]
        )

        partial_input = economics_inputs()
        partial_input["schema_version"] = "economics-explicit-inputs-v2"
        partial_input["raas_monthly_per_robot_gross"] = None
        partial_response = owner.post(endpoint, headers=headers, json={
            "scenario_id": scenario["id"], "capacity_run_id": capacity["run_id"],
            "input": partial_input,
        })
        assert partial_response.status_code == 201, partial_response.text
        partial = partial_response.json()
        assert partial["input_snapshot"]["schema_version"] == "economics-run-input-v3"
        assert partial["result_snapshot"]["schema_version"] == "economics-partial-result-v1"
        assert partial["result_snapshot"]["branches"]["purchase"]["status"] == "CALCULATED"
        assert partial["result_snapshot"]["branches"]["raas"]["status"] == "NOT_CALCULATED"
        assert len(partial["result_snapshot"]["scenarios"]) == 3
        assert owner.get(f"/api/projects/{project['id']}/analysis-runs/{partial['id']}").json()["checksums"] == partial["checksums"]
        partial_replay = owner.post(f"{endpoint}/{partial['id']}/replay", headers=headers)
        assert partial_replay.status_code == 200, partial_replay.text
        assert partial_replay.json()["status"] == "MATCH"

        reopened = owner.get(
            f"/api/projects/{project['id']}/analysis-runs/{created['id']}"
        )
        assert reopened.status_code == 200
        assert reopened.json()["checksums"] == created["checksums"]
        assert reopened.json()["result_snapshot"] == created["result_snapshot"]

        replay_endpoint = f"{endpoint}/{created['id']}/replay"
        assert owner.post(replay_endpoint).status_code == 403
        replay = owner.post(replay_endpoint, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["status"] == "MATCH"
        assert replay.json()["result_sha256"] == created["checksums"]["result"]

        rerun_payload = {
            **economics_payload,
            "source_run_id": created["id"],
        }
        rerun_response = owner.post(endpoint, headers=headers, json=rerun_payload)
        assert rerun_response.status_code == 201, rerun_response.text
        rerun = rerun_response.json()
        assert rerun["id"] != created["id"]
        assert rerun["parent_run_id"] == created["id"]
        assert rerun["input_snapshot"]["economics"] == created["input_snapshot"]["economics"]

        manifest = owner.get(
            f"/api/projects/{project['id']}/analysis-runs/{created['id']}/exports/manifest"
        )
        archive = owner.get(
            f"/api/projects/{project['id']}/analysis-runs/{created['id']}/exports/evidence.zip"
        )
        assert manifest.status_code == 200, manifest.text
        assert archive.status_code == 200
        assert archive.headers["x-export-manifest-digest"] == manifest.json()["manifest_digest"]

    with TestClient(main.app) as intruder:
        _, intruder_headers = _register(
            intruder, "production-flow-intruder@example.com", PASSWORD_B
        )
        intruder_project = _create_project(intruder, intruder_headers)
        intruder_scenario = next(
            item for item in intruder_project["scenarios"] if item["slot"] == "BASE"
        )
        cross_tenant = intruder.post(
            f"/api/v2/projects/{intruder_project['id']}/economics-runs",
            headers=intruder_headers,
            json={
                **economics_payload,
                "scenario_id": intruder_scenario["id"],
            },
        )
        assert cross_tenant.status_code == 404
        assert intruder.post(
            f"/api/v2/projects/{project['id']}/economics-runs/{created['id']}/replay",
            headers=intruder_headers,
        ).status_code == 404
        assert intruder.get(
            f"/api/projects/{project['id']}/analysis-runs/{created['id']}/exports/manifest"
        ).status_code == 404


def test_capacity_endpoint_returns_503_without_published_source(monkeypatch):
    class MissingCapacitySource:
        def load_capacity(self):
            from catalog_runtime import CatalogRuntimeConfigurationError
            raise CatalogRuntimeConfigurationError("missing")

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", MissingCapacitySource())
    with TestClient(main.app) as client:
        _, headers = _register(client, "capacity-missing@example.com")
        project = _create_project(client, headers)
        payload = capacity_request().model_dump(mode="json")
        payload["project_id"] = project["id"]
        response = client.post("/api/v2/capacity-analyses", headers=headers, json=payload)
        assert response.status_code == 503


def test_admin_bootstrap_is_idempotent_parallel_and_does_not_promote_collision(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "first-admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", PASSWORD_A)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_NAME", "Первый администратор")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(lambda _: bootstrap_admin(), range(2)))
    assert results == ["already_initialized", "created"]
    with get_database().session() as db:
        admin = db.scalar(select(User).where(User.email_normalized == "first-admin@example.com"))
        assert admin is not None and admin.role == "ADMIN"
        original_hash = admin.password_hash
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", PASSWORD_B)
    assert bootstrap_admin() == "already_initialized"
    with get_database().session() as db:
        assert db.get(User, admin.id).password_hash == original_hash

    with migrated_database_transaction() as connection:
        connection.execute(text("TRUNCATE users, audit_entries RESTART IDENTITY CASCADE"))
        connection.execute(
            text(
                "INSERT INTO users (id, email_normalized, password_hash) "
                "VALUES (:id, 'first-admin@example.com', 'existing-hash')"
            ),
            {"id": uuid.uuid4()},
        )
    with pytest.raises(BootstrapError, match="existing non-admin"):
        bootstrap_admin()


class migrated_database_transaction:
    """Tiny context wrapper that uses the configured singleton engine."""

    def __enter__(self):
        self._context = get_database().engine.begin()
        return self._context.__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self._context.__exit__(exc_type, exc, tb)


def test_bootstrap_requires_environment_without_disclosing_secret(monkeypatch, capsys):
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    with pytest.raises(BootstrapError, match="not configured"):
        bootstrap_admin()
    assert PASSWORD_A not in capsys.readouterr().err


def test_admin_user_crud_password_reset_and_last_admin_guard():
    with TestClient(main.app) as admin_client:
        _, admin_headers = _register(admin_client, "admin@example.com")
        with get_database().session() as db:
            admin = db.scalar(select(User).where(User.email_normalized == "admin@example.com"))
            admin.role = "ADMIN"
            db.commit()

        created = admin_client.post(
            "/api/admin/users",
            headers=admin_headers,
            json={
                "email": "managed@example.com",
                "password": PASSWORD_B,
                "name": "Managed",
                "role": "USER",
            },
        )
        assert created.status_code == 201, created.text
        managed_id = created.json()["id"]
        victim = admin_client.post(
            "/api/admin/users",
            headers=admin_headers,
            json={
                "email": "delete-me@example.com",
                "password": PASSWORD_B,
                "role": "USER",
            },
        )
        assert victim.status_code == 201
        removed = admin_client.delete(
            f"/api/admin/users/{victim.json()['id']}", headers=admin_headers
        )
        assert removed.status_code == 204
        promoted = admin_client.patch(
            f"/api/admin/users/{managed_id}",
            headers=admin_headers,
            json={"role": "ADMIN"},
        )
        assert promoted.status_code == 200
        reset = admin_client.post(
            f"/api/admin/users/{managed_id}/reset-password",
            headers=admin_headers,
            json={"password": PASSWORD_A},
        )
        assert reset.status_code == 204
        demoted = admin_client.patch(
            f"/api/admin/users/{admin.id}",
            headers=admin_headers,
            json={"role": "USER"},
        )
        assert demoted.status_code == 200

    with TestClient(main.app) as last_admin:
        login = last_admin.post(
            "/api/auth/login",
            json={"email": "managed@example.com", "password": PASSWORD_A},
        )
        assert login.status_code == 200
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        refused = last_admin.patch(
            f"/api/admin/users/{managed_id}",
            headers=headers,
            json={"role": "USER"},
        )
        assert refused.status_code == 409


def test_project_delete_removes_files_and_payload_then_purges_tombstone(tmp_path, monkeypatch):
    storage_root = tmp_path / "uploads-delete"
    monkeypatch.setenv("PROJECT_FILE_STORAGE_ROOT", str(storage_root))
    with TestClient(main.app) as client:
        _, headers = _register(client, "delete@example.com")
        project = _create_project(client, headers)
        scenario = next(item for item in project["scenarios"] if item["slot"] == "BASE")
        run = client.post(
            f"/api/projects/{project['id']}/analysis-runs",
            headers=headers,
            json={"scenario_id": scenario["id"], "input": _analysis_input()},
        )
        assert run.status_code == 201
        storage_key = f"{project['id']}/input.csv"
        file_path = storage_root / storage_key
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(b"safe test content")
        with get_database().session() as db:
            db.add(
                ProjectFile(
                    id=uuid.uuid4(),
                    project_id=uuid.UUID(project["id"]),
                    original_name="sensitive.csv",
                    media_type="text/csv",
                    byte_size=file_path.stat().st_size,
                    sha256="a" * 64,
                    storage_key=storage_key,
                )
            )
            db.commit()

        deleted = client.delete(f"/api/projects/{project['id']}", headers=headers)
        assert deleted.status_code == 204, deleted.text
        assert not file_path.exists()
        assert client.get(f"/api/projects/{project['id']}").status_code == 404

    with get_database().session() as db:
        assert db.get(AnalysisRunEconomicsVersion, uuid.UUID(run.json()["id"])) is None
        tombstone = db.scalar(
            select(AuditEntry).where(
                AuditEntry.event_type == "PROJECT_DELETED",
                AuditEntry.project_subject_id == uuid.UUID(project["id"]),
            )
        )
        assert tombstone is not None
        assert tombstone.aggregate == {"scenario_count": 3, "run_count": 1, "file_count": 1}
        serialized = json.dumps(tombstone.aggregate)
        assert "sensitive.csv" not in serialized
        assert storage_key not in serialized
        audit_count = db.scalar(
            text(
                "SELECT count(*) FROM audit_entries "
                "WHERE project_subject_id = :project_id"
            ),
            {"project_id": project["id"]},
        )
        outbox_count = db.scalar(
            text(
                "SELECT count(*) FROM project_deletion_jobs "
                "WHERE project_subject_id = :project_id"
            ),
            {"project_id": project["id"]},
        )
        assert audit_count == 1
        assert outbox_count == 0
        boundary = tombstone.retention_until
        assert purge_expired_tombstones(db, now=boundary - timedelta(microseconds=1)) == 0
        assert purge_expired_tombstones(db, now=boundary) == 1


def test_project_file_preview_apply_download_and_invalid_atomicity():
    filename, valid_csv = build_csv_template("warehouse")
    invalid_csv = (
        "profile_code,parameter_code,value,unit\n"
        "warehouse,obschaya_ploschad_sklada,-1,wrong\n"
    ).encode()
    with TestClient(main.app) as client:
        _, headers = _register(client, "intake@example.com")
        project = _create_project(client, headers)
        scenario = next(item for item in project["scenarios"] if item["slot"] == "BASE")
        endpoint = f"/api/projects/{project['id']}/files"

        preview = client.post(
            f"{endpoint}/preview",
            data={"profile_code": "warehouse"},
            files={"file": ("invalid.csv", invalid_csv, "text/csv")},
        )
        assert preview.status_code == 200
        assert preview.json()["valid"] is False

        rejected = client.post(
            f"{endpoint}/apply",
            headers=headers,
            data={"profile_code": "warehouse", "scenario_id": scenario["id"]},
            files={"file": ("invalid.csv", invalid_csv, "text/csv")},
        )
        assert rejected.status_code == 422
        unchanged = client.get(f"/api/projects/{project['id']}").json()
        unchanged_scenario = next(item for item in unchanged["scenarios"] if item["slot"] == "BASE")
        assert unchanged_scenario["inputs"] == {}
        assert client.get(endpoint).json()["items"] == []

        valid_preview = client.post(
            f"{endpoint}/preview",
            data={"profile_code": "warehouse"},
            files={"file": (filename, valid_csv, "text/csv")},
        )
        assert valid_preview.status_code == 200
        assert valid_preview.json()["valid"] is True
        applied = client.post(
            f"{endpoint}/apply",
            headers=headers,
            data={"profile_code": "warehouse", "scenario_id": scenario["id"]},
            files={"file": (filename, valid_csv, "text/csv")},
        )
        assert applied.status_code == 201, applied.text
        item = applied.json()
        assert item["sha256"] == valid_preview.json()["file"]["sha256"]
        assert item["import"]["validation_report"]["accepted_count"] == 42
        assert len(item["import"]["parameter_values"]) == 42
        assert len(item["import"]["parameter_provenance"]) == 42
        assert item["import"]["normalized_input"] == valid_preview.json()["normalized_input"]
        assert item["import"]["provenance"]["area_m2"]["kind"] == "FILE"
        assert client.get(endpoint).json()["items"][0]["id"] == item["id"]
        downloaded = client.get(f"{endpoint}/{item['id']}")
        assert downloaded.status_code == 200
        assert downloaded.content == valid_csv

    with get_database().session() as db:
        assert db.scalar(select(func.count()).select_from(ProjectFile)) == 1
        assert db.scalar(select(func.count()).select_from(ProjectFileImport)) == 1
        saved = db.scalar(select(Scenario).where(Scenario.id == uuid.UUID(scenario["id"])))
        assert saved.inputs == item["import"]["normalized_input"]


def test_project_file_routes_hide_other_users_project():
    filename, payload = build_csv_template("warehouse")
    with TestClient(main.app) as owner:
        _, owner_headers = _register(owner, "file-owner@example.com")
        project = _create_project(owner, owner_headers)
    with TestClient(main.app) as stranger:
        _register(stranger, "file-stranger@example.com")
        response = stranger.post(
            f"/api/projects/{project['id']}/files/preview",
            data={"profile_code": "warehouse"},
            files={"file": (filename, payload, "text/csv")},
        )
        assert response.status_code == 404


def test_admin_diagnostic_zip_requires_role_and_csrf_and_omits_credentials():
    endpoint = "/api/admin/diagnostics/export"
    with TestClient(main.app) as client:
        assert client.post(endpoint).status_code == 401
        _, headers = _register(client, "diagnostic-admin@example.com")
        assert client.post(endpoint, headers=headers).status_code == 403
        project = _create_project(client, headers)
        with get_database().session() as db:
            admin = db.scalar(select(User).where(User.email_normalized == "diagnostic-admin@example.com"))
            admin.role = "ADMIN"
            stored_project = db.get(Project, uuid.UUID(project["id"]))
            stored_project.profile = {"api_key": "do-not-export-this-value", "label": "warehouse"}
            db.commit()
        assert client.post(endpoint).status_code == 403
        response = client.post(endpoint, headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/zip"
        assert response.headers["cache-control"] == "no-store, private"
        assert "attachment" in response.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            assert "manifest.json" in names
            assert "database/projects.jsonl" in names
            assert "database/analysis_runs.jsonl" in names
            assert "logs/backend-requests.jsonl" in names
            assert "database/user_sessions.jsonl" not in names
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["schema_version"] == "diagnostic-bundle-v1"
            assert manifest["members"]["database/projects.jsonl"]["rows"] == 1
            users = archive.read("database/users.jsonl")
            projects = archive.read("database/projects.jsonl")
            assert b"password_hash" not in users
            assert PASSWORD_A.encode() not in response.content
            assert b"do-not-export-this-value" not in projects
            assert b"<redacted>" in projects
        with get_database().session() as db:
            assert db.scalar(select(func.count()).select_from(AuditEntry).where(
                AuditEntry.event_type == "DIAGNOSTIC_BUNDLE_EXPORTED"
            )) == 1
