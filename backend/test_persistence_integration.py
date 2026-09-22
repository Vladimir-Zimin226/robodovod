from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

import catalog_models  # noqa: F401
import main
import persistence_models  # noqa: F401
from auth import SESSION_COOKIE
from bootstrap_admin import BootstrapError, bootstrap_admin
from database import dispose_database, get_database
from persistence_api import purge_expired_tombstones
from persistence_models import AnalysisRun, AuditEntry, ProjectFile, ProjectFileImport, Scenario, User
from project_file_intake import build_csv_template
from storage_models import Base, CatalogVersion
from test_capacity_analysis_service import request as capacity_request, snapshot as capacity_snapshot


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
PASSWORD_A = "correct horse battery staple"
PASSWORD_B = "another secure passphrase"


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
        assert TABLES_0003 | TABLES_0006 <= set(inspect(engine).get_table_names())
        command.upgrade(_config(), "head")
        yield engine
    finally:
        dispose_database()
        engine.dispose()
        monkeypatch.undo()


@pytest.fixture(autouse=True)
def clean_persistence(migrated_database, tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FILE_STORAGE_ROOT", str(tmp_path / "uploads"))
    with migrated_database.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, audit_entries, project_deletion_jobs "
                "RESTART IDENTITY CASCADE"
            )
        )
        connection.execute(
            text("DELETE FROM catalog_versions WHERE code LIKE 'persistence-test-%'")
        )
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
    assert TABLES_0003 | TABLES_0006 <= set(inspect(migrated_database).get_table_names())
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
        second_response = client.post(
            f"/api/projects/{project['id']}/analysis-runs/{first['id']}/rerun",
            headers=headers,
        )
        assert second_response.status_code == 201, second_response.text
        second = second_response.json()
        assert second["id"] != first["id"]
        assert second["parent_run_id"] == first["id"]
        assert second["input_snapshot"] == first["input_snapshot"]


def test_capacity_run_is_independent_immutable_and_tenant_scoped(monkeypatch, migrated_database):
    catalog = capacity_snapshot()

    class CapacitySource:
        def load_discovery(self):
            return catalog

        def load_runtime(self):
            raise AssertionError("C11 must not read the legacy economics runtime")

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", CapacitySource())
    now = datetime.now(timezone.utc)
    with get_database().session() as db:
        db.add(CatalogVersion(
            id=uuid.UUID(catalog.version.id), code=catalog.version.code,
            status="PUBLISHED", schema_version="4", content_sha256="a" * 64,
            validated_at=now, published_at=now,
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


def test_capacity_endpoint_returns_503_without_published_source(monkeypatch):
    class MissingCapacitySource:
        def load_discovery(self):
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
