from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError

import main
import catalog_models  # noqa: F401
from database import dispose_database, get_database
from storage_models import Base


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)

ALEMBIC_CONFIG = Path(__file__).with_name("alembic.ini")
CONTROL_PLANE_TABLES = {
    "catalog_versions",
    "source_artifacts",
    "catalog_version_sources",
    "import_runs",
    "catalog_activations",
}
SHA_A = "a" * 64
SHA_B = "b" * 64


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_CONFIG))


def _run_migration(monkeypatch: pytest.MonkeyPatch, direction: str, revision: str) -> None:
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    operation = command.upgrade if direction == "upgrade" else command.downgrade
    operation(_alembic_config(), revision)


@pytest.fixture(scope="module")
def migrated_engine(request):
    monkeypatch = pytest.MonkeyPatch()
    engine = create_engine(TEST_DATABASE_URL, hide_parameters=True)
    try:
        _run_migration(monkeypatch, "downgrade", "base")
        assert CONTROL_PLANE_TABLES.isdisjoint(inspect(engine).get_table_names())

        _run_migration(monkeypatch, "upgrade", "head")
        assert CONTROL_PLANE_TABLES <= set(inspect(engine).get_table_names())

        # A repeated upgrade must be a safe no-op.
        _run_migration(monkeypatch, "upgrade", "head")
        assert CONTROL_PLANE_TABLES <= set(inspect(engine).get_table_names())

        # Downgrade is supported for a disposable development/test database.
        _run_migration(monkeypatch, "downgrade", "base")
        assert CONTROL_PLANE_TABLES.isdisjoint(inspect(engine).get_table_names())
        _run_migration(monkeypatch, "upgrade", "head")
        assert CONTROL_PLANE_TABLES <= set(inspect(engine).get_table_names())
        yield engine
    finally:
        engine.dispose()
        monkeypatch.undo()


@pytest.fixture
def connection(migrated_engine):
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            if transaction.is_active:
                transaction.rollback()


def _expect_integrity_error(connection, statement: str, parameters: dict) -> None:
    savepoint = connection.begin_nested()
    try:
        with pytest.raises(IntegrityError):
            connection.execute(text(statement), parameters)
    finally:
        if savepoint.is_active:
            savepoint.rollback()


def _insert_version(connection, *, code: str | None = None, status: str = "DRAFT") -> uuid.UUID:
    version_id = uuid.uuid4()
    code = code or f"version-{version_id}"
    created_at = datetime.now(UTC) - timedelta(minutes=1)
    values = {
        "id": version_id,
        "code": code,
        "status": status,
        "schema_version": "1",
        "created_at": created_at,
        "updated_at": created_at,
        "validated_at": None,
        "published_at": None,
        "retired_at": None,
    }
    if status in {"VALIDATED", "PUBLISHED", "RETIRED"}:
        values["validated_at"] = created_at + timedelta(seconds=10)
    if status in {"PUBLISHED", "RETIRED"}:
        values["published_at"] = created_at + timedelta(seconds=20)
    if status == "RETIRED":
        values["retired_at"] = created_at + timedelta(seconds=30)

    connection.execute(
        text(
            """
            INSERT INTO catalog_versions (
                id, code, status, schema_version, created_at, updated_at,
                validated_at, published_at, retired_at
            ) VALUES (
                :id, :code, :status, :schema_version, :created_at, :updated_at,
                :validated_at, :published_at, :retired_at
            )
            """
        ),
        values,
    )
    return version_id


def _insert_source(connection, *, sha256: str = SHA_A, byte_size: int = 1) -> uuid.UUID:
    source_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO source_artifacts (
                id, sha256, original_name, media_type, byte_size,
                provenance_status, license_status, observed_at
            ) VALUES (
                :id, :sha256, 'source.csv', 'text/csv', :byte_size,
                'VERIFIED', 'PERMITTED', now()
            )
            """
        ),
        {"id": source_id, "sha256": sha256, "byte_size": byte_size},
    )
    return source_id


def test_clean_upgrade_repeat_and_disposable_downgrade_upgrade(migrated_engine):
    assert CONTROL_PLANE_TABLES <= set(inspect(migrated_engine).get_table_names())


def test_orm_metadata_matches_migration(migrated_engine):
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_catalog_version_code_rejects_empty_and_duplicate(connection):
    _expect_integrity_error(
        connection,
        "INSERT INTO catalog_versions (id, code, schema_version) VALUES (:id, '', '1')",
        {"id": uuid.uuid4()},
    )
    _insert_version(connection, code="unique-code")
    _expect_integrity_error(
        connection,
        "INSERT INTO catalog_versions (id, code, schema_version) VALUES (:id, 'unique-code', '1')",
        {"id": uuid.uuid4()},
    )


def test_source_artifact_rejects_invalid_sha256(connection):
    _expect_integrity_error(
        connection,
        """
        INSERT INTO source_artifacts (
            id, sha256, original_name, media_type, byte_size,
            provenance_status, license_status, observed_at
        ) VALUES (
            :id, 'ABC123', 'source.csv', 'text/csv', 10,
            'VERIFIED', 'PERMITTED', now()
        )
        """,
        {"id": uuid.uuid4()},
    )


def test_source_artifact_rejects_nonpositive_byte_size(connection):
    _expect_integrity_error(
        connection,
        """
        INSERT INTO source_artifacts (
            id, sha256, original_name, media_type, byte_size,
            provenance_status, license_status, observed_at
        ) VALUES (
            :id, :sha256, 'source.csv', 'text/csv', 0,
            'VERIFIED', 'PERMITTED', now()
        )
        """,
        {"id": uuid.uuid4(), "sha256": SHA_A},
    )


def test_catalog_lifecycle_rejects_skipped_and_backward_transitions(connection):
    version_id = _insert_version(connection)
    lifecycle_start = datetime.now(UTC)
    _expect_integrity_error(
        connection,
        """
        UPDATE catalog_versions
        SET status = 'PUBLISHED', validated_at = :validated_at, published_at = :published_at
        WHERE id = :id
        """,
        {
            "id": version_id,
            "validated_at": lifecycle_start,
            "published_at": lifecycle_start + timedelta(seconds=1),
        },
    )

    connection.execute(
        text(
            "UPDATE catalog_versions SET status = 'VALIDATED', validated_at = :at WHERE id = :id"
        ),
        {"id": version_id, "at": lifecycle_start},
    )
    _expect_integrity_error(
        connection,
        "UPDATE catalog_versions SET status = 'DRAFT', validated_at = NULL WHERE id = :id",
        {"id": version_id},
    )


def test_only_one_active_catalog_per_slot(connection):
    first_version = _insert_version(connection, status="PUBLISHED")
    second_version = _insert_version(connection, status="PUBLISHED")
    connection.execute(
        text(
            "INSERT INTO catalog_activations (id, slot, catalog_version_id) VALUES (:id, 'runtime', :version_id)"
        ),
        {"id": uuid.uuid4(), "version_id": first_version},
    )
    _expect_integrity_error(
        connection,
        "INSERT INTO catalog_activations (id, slot, catalog_version_id) VALUES (:id, 'runtime', :version_id)",
        {"id": uuid.uuid4(), "version_id": second_version},
    )


def test_activation_requires_published_version(connection):
    draft_version = _insert_version(connection)
    _expect_integrity_error(
        connection,
        "INSERT INTO catalog_activations (id, slot, catalog_version_id) VALUES (:id, 'runtime', :version_id)",
        {"id": uuid.uuid4(), "version_id": draft_version},
    )


def test_activation_history_allows_only_one_deactivation(connection):
    version_id = _insert_version(connection, status="PUBLISHED")
    activation_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO catalog_activations (id, slot, catalog_version_id) VALUES (:id, 'runtime', :version_id)"
        ),
        {"id": activation_id, "version_id": version_id},
    )
    connection.execute(
        text(
            "UPDATE catalog_activations SET deactivated_at = activated_at + interval '1 second' WHERE id = :id"
        ),
        {"id": activation_id},
    )
    _expect_integrity_error(
        connection,
        "UPDATE catalog_activations SET deactivated_at = deactivated_at + interval '1 second' WHERE id = :id",
        {"id": activation_id},
    )
    _expect_integrity_error(
        connection,
        "DELETE FROM catalog_activations WHERE id = :id",
        {"id": activation_id},
    )


def test_import_status_and_timestamps_must_agree(connection):
    version_id = _insert_version(connection)
    _expect_integrity_error(
        connection,
        """
        INSERT INTO import_runs (
            id, catalog_version_id, phase, mode, status, bundle_sha256, finished_at
        ) VALUES (
            :id, :version_id, 'BASE', 'VALIDATE_ONLY', 'PENDING', :sha256, now()
        )
        """,
        {"id": uuid.uuid4(), "version_id": version_id, "sha256": SHA_A},
    )


def test_successful_commit_is_idempotent_per_version_phase_and_bundle(connection):
    version_id = _insert_version(connection)
    statement = """
        INSERT INTO import_runs (
            id, catalog_version_id, phase, mode, status, bundle_sha256,
            started_at, finished_at
        ) VALUES (
            :id, :version_id, 'BASE', 'COMMIT', 'SUCCEEDED', :sha256,
            now(), now()
        )
    """
    connection.execute(
        text(statement),
        {"id": uuid.uuid4(), "version_id": version_id, "sha256": SHA_A},
    )
    _expect_integrity_error(
        connection,
        statement,
        {"id": uuid.uuid4(), "version_id": version_id, "sha256": SHA_A},
    )


def test_version_and_source_links_use_delete_restrict(connection):
    version_id = _insert_version(connection)
    source_id = _insert_source(connection)
    connection.execute(
        text(
            """
            INSERT INTO catalog_version_sources (
                catalog_version_id, source_artifact_id, role, ordinal
            ) VALUES (:version_id, :source_id, 'BASE', 0)
            """
        ),
        {"version_id": version_id, "source_id": source_id},
    )
    _expect_integrity_error(
        connection,
        "DELETE FROM catalog_versions WHERE id = :id",
        {"id": version_id},
    )
    _expect_integrity_error(
        connection,
        "DELETE FROM source_artifacts WHERE id = :id",
        {"id": source_id},
    )


def test_readiness_succeeds_and_releases_connection(
    migrated_engine, monkeypatch, caplog
):
    dispose_database()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    caplog.set_level(logging.WARNING, logger="robomera.api")
    try:
        with TestClient(main.app) as client:
            response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "available"}
        database = get_database()
        assert database.engine.pool.checkedout() == 0
        assert caplog.text == ""
    finally:
        dispose_database()


def test_session_boundary_releases_connection(monkeypatch):
    dispose_database()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    try:
        database = get_database()
        with database.session() as session:
            assert session.execute(text("SELECT 1")).scalar_one() == 1
            assert database.engine.pool.checkedout() == 1
        assert database.engine.pool.checkedout() == 0
    finally:
        dispose_database()


def test_readiness_failure_redacts_secret_and_full_dsn(monkeypatch, caplog):
    secret = "readiness-secret-marker"
    full_url = URL.create(
        "postgresql+psycopg",
        username="probe",
        password=secret,
        host="127.0.0.1",
        port=1,
        database="unavailable",
        query={"connect_timeout": "1"},
    ).render_as_string(hide_password=False)
    dispose_database()
    monkeypatch.setenv("DATABASE_URL", full_url)
    caplog.set_level(logging.WARNING, logger="robomera.api")
    try:
        with TestClient(main.app) as client:
            response = client.get("/ready")
        combined_output = response.text + caplog.text
        assert response.status_code == 503
        assert response.json() == {"detail": "database unavailable"}
        assert secret not in combined_output
        assert full_url not in combined_output
        database = get_database()
        assert database.engine.pool.checkedout() == 0
    finally:
        dispose_database()
