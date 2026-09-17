from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import catalog_models  # noqa: F401
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from storage_models import Base

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)

ALEMBIC_CONFIG = Path(__file__).with_name("alembic.ini")
CATALOG_TABLES = {
    "catalog_description_imports",
    "catalog_position_enrichments",
    "catalog_media_assets",
    "catalog_position_media",
    "manufacturers",
    "catalog_source_rows",
    "equipment_models",
    "equipment_applicability",
    "field_evidence",
    "spec_observations",
    "resolved_spec_facts",
    "resolved_spec_fact_evidence",
    "procurement_options",
}
MEDIA_TABLES = {"catalog_media_assets", "catalog_position_media"}
APPEND_ONLY_TABLES = MEDIA_TABLES | {"catalog_description_imports", "catalog_position_enrichments"}
MUTABLE_DRAFT_DOMAIN_TABLES = CATALOG_TABLES - APPEND_ONLY_TABLES


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_CONFIG))


@pytest.fixture(scope="module")
def catalog_engine():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL, hide_parameters=True)
    try:
        command.downgrade(_alembic_config(), "0001_storage_control_plane")
        assert CATALOG_TABLES.isdisjoint(inspect(engine).get_table_names())

        command.upgrade(_alembic_config(), "head")
        assert CATALOG_TABLES <= set(inspect(engine).get_table_names())

        command.upgrade(_alembic_config(), "head")
        command.downgrade(_alembic_config(), "0001_storage_control_plane")
        assert CATALOG_TABLES.isdisjoint(inspect(engine).get_table_names())
        command.upgrade(_alembic_config(), "head")
        yield engine
    finally:
        engine.dispose()
        monkeypatch.undo()


@pytest.fixture
def connection(catalog_engine):
    with catalog_engine.connect() as connection:
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


def _insert_version(connection, suffix: str = "") -> uuid.UUID:
    version_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO catalog_versions (id, code, schema_version)
            VALUES (:id, :code, '2')
            """
        ),
        {"id": version_id, "code": f"catalog-{version_id}{suffix}"},
    )
    return version_id


def _insert_artifact(connection, version_id: uuid.UUID, ordinal: int = 0) -> uuid.UUID:
    artifact_id = uuid.uuid4()
    sha256 = artifact_id.hex * 2
    connection.execute(
        text(
            """
            INSERT INTO source_artifacts (
                id, sha256, original_name, media_type, byte_size,
                provenance_status, license_status, observed_at
            ) VALUES (
                :id, :sha256, 'catalog.csv', 'text/csv', 100,
                'VERIFIED', 'PERMITTED', now()
            )
            """
        ),
        {"id": artifact_id, "sha256": sha256},
    )
    connection.execute(
        text(
            """
            INSERT INTO catalog_version_sources (
                catalog_version_id, source_artifact_id, role, ordinal
            ) VALUES (:version_id, :artifact_id, 'BASE', :ordinal)
            """
        ),
        {"version_id": version_id, "artifact_id": artifact_id, "ordinal": ordinal},
    )
    return artifact_id


def _insert_source_row(
    connection,
    version_id: uuid.UUID,
    artifact_id: uuid.UUID,
    row_number: int = 2,
    key: str | None = None,
) -> uuid.UUID:
    row_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO catalog_source_rows (
                id, catalog_version_id, source_artifact_id, source_row_number,
                source_namespace, source_record_key, raw_payload
            ) VALUES (
                :id, :version_id, :artifact_id, :row_number,
                'organizer-v4', :source_key, CAST(:raw_payload AS jsonb)
            )
            """
        ),
        {
            "id": row_id,
            "version_id": version_id,
            "artifact_id": artifact_id,
            "row_number": row_number,
            "source_key": key or f"row-{row_number}-{row_id}",
            "raw_payload": '{"preserved": true}',
        },
    )
    return row_id


def _insert_model(
    connection,
    version_id: uuid.UUID,
    *,
    organizer_id: uuid.UUID | None = None,
    source_key: str | None = None,
) -> uuid.UUID:
    model_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO equipment_models (
                id, catalog_version_id, organizer_id, source_namespace,
                source_record_key, name, system_family, type_code
            ) VALUES (
                :id, :version_id, :organizer_id, 'organizer-v4',
                :source_key, 'Test model', 'MOBILE_ROBOT', 'AMR'
            )
            """
        ),
        {
            "id": model_id,
            "version_id": version_id,
            "organizer_id": organizer_id,
            "source_key": source_key or f"model-{model_id}",
        },
    )
    return model_id


def _insert_evidence(
    connection,
    version_id: uuid.UUID,
    artifact_id: uuid.UUID,
    model_id: uuid.UUID,
    source_row_id: uuid.UUID,
    *,
    status: str = "VERIFIED_OFFICIAL",
) -> uuid.UUID:
    evidence_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO field_evidence (
                id, catalog_version_id, source_artifact_id,
                catalog_source_row_id, equipment_model_id,
                source_namespace, source_record_key, subject_type, subject_key,
                field_path, normalized_value, evidence_status, confidence_score,
                observed_at
            ) VALUES (
                :id, :version_id, :artifact_id,
                :source_row_id, :model_id,
                'external-run-1', :source_key, 'PRODUCT', :subject_key,
                'specs.payload', '1000'::jsonb, :status, 0.950, now()
            )
            """
        ),
        {
            "id": evidence_id,
            "version_id": version_id,
            "artifact_id": artifact_id,
            "source_row_id": source_row_id,
            "model_id": model_id,
            "source_key": f"evidence-{evidence_id}",
            "subject_key": str(model_id),
            "status": status,
        },
    )
    return evidence_id


@pytest.fixture
def graph(connection):
    version_id = _insert_version(connection)
    artifact_id = _insert_artifact(connection, version_id)
    source_row_id = _insert_source_row(connection, version_id, artifact_id)
    model_id = _insert_model(connection, version_id, organizer_id=uuid.uuid4())
    evidence_id = _insert_evidence(
        connection, version_id, artifact_id, model_id, source_row_id
    )
    return {
        "version_id": version_id,
        "artifact_id": artifact_id,
        "source_row_id": source_row_id,
        "model_id": model_id,
        "evidence_id": evidence_id,
    }


def test_upgrade_repeat_downgrade_upgrade_and_view(catalog_engine):
    inspector = inspect(catalog_engine)
    assert CATALOG_TABLES <= set(inspector.get_table_names())
    assert "matching_spec_facts" in inspector.get_view_names()


def test_orm_metadata_matches_catalog_migration(catalog_engine):
    with catalog_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_domain_tables_all_have_draft_only_trigger(connection):
    trigger_tables = set(
        connection.execute(
            text(
                """
                SELECT event_object_table
                FROM information_schema.triggers
                WHERE trigger_name LIKE 'trg_%_draft_only'
                """
            )
        ).scalars()
    )
    assert trigger_tables == MUTABLE_DRAFT_DOMAIN_TABLES


def test_auxiliary_catalog_tables_have_append_only_trigger(connection):
    trigger_tables = set(
        connection.execute(
            text(
                """
                SELECT event_object_table
                FROM information_schema.triggers
                WHERE trigger_name LIKE 'trg_%_append_only'
                """
            )
        ).scalars()
    )
    assert trigger_tables == APPEND_ONLY_TABLES


def test_source_rows_preserve_artifact_row_identity(connection):
    version_id = _insert_version(connection)
    artifact_id = _insert_artifact(connection, version_id)
    _insert_source_row(connection, version_id, artifact_id, row_number=2)
    _expect_integrity_error(
        connection,
        """
        INSERT INTO catalog_source_rows (
            id, catalog_version_id, source_artifact_id, source_row_number,
            source_namespace, source_record_key, raw_payload
        ) VALUES (
            :id, :version_id, :artifact_id, 2,
            'organizer-v4', 'different-key', '{}'::jsonb
        )
        """,
        {"id": uuid.uuid4(), "version_id": version_id, "artifact_id": artifact_id},
    )


def test_organizer_id_is_unique_only_within_catalog_version(connection):
    organizer_id = uuid.uuid4()
    first_version = _insert_version(connection)
    second_version = _insert_version(connection)
    _insert_model(connection, first_version, organizer_id=organizer_id)
    _expect_integrity_error(
        connection,
        """
        INSERT INTO equipment_models (
            id, catalog_version_id, organizer_id, source_namespace,
            source_record_key, name, system_family, type_code
        ) VALUES (
            :id, :version_id, :organizer_id, 'organizer-v4',
            'duplicate-organizer', 'Duplicate', 'MOBILE_ROBOT', 'AMR'
        )
        """,
        {
            "id": uuid.uuid4(),
            "version_id": first_version,
            "organizer_id": organizer_id,
        },
    )
    _insert_model(connection, second_version, organizer_id=organizer_id)


def test_cross_version_relationships_are_rejected(connection):
    first_version = _insert_version(connection)
    first_artifact = _insert_artifact(connection, first_version)
    first_row = _insert_source_row(connection, first_version, first_artifact)
    second_version = _insert_version(connection)
    second_model = _insert_model(connection, second_version)
    _expect_integrity_error(
        connection,
        """
        INSERT INTO equipment_applicability (
            id, catalog_version_id, equipment_model_id, catalog_source_row_id
        ) VALUES (:id, :version_id, :model_id, :source_row_id)
        """,
        {
            "id": uuid.uuid4(),
            "version_id": second_version,
            "model_id": second_model,
            "source_row_id": first_row,
        },
    )


def test_applicability_and_offer_keep_distinct_source_row_identity(connection, graph):
    connection.execute(
        text(
            """
            INSERT INTO equipment_applicability (
                id, catalog_version_id, equipment_model_id, catalog_source_row_id,
                industry, scenario
            ) VALUES (:id, :version_id, :model_id, :source_row_id, 'logistics', 'transport')
            """
        ),
        {"id": uuid.uuid4(), **graph},
    )
    connection.execute(
        text(
            """
            INSERT INTO procurement_options (
                id, catalog_version_id, equipment_model_id, catalog_source_row_id,
                procurement_mode, raw_price, price_status
            ) VALUES (
                :id, :version_id, :model_id, :source_row_id,
                'PURCHASE', 'по запросу', 'QUOTE_REQUIRED'
            )
            """
        ),
        {"id": uuid.uuid4(), **graph},
    )
    for table_name in ("equipment_applicability", "procurement_options"):
        _expect_integrity_error(
            connection,
            f"""
            INSERT INTO {table_name} (
                id, catalog_version_id, equipment_model_id, catalog_source_row_id
                {", procurement_mode, price_status" if table_name == "procurement_options" else ""}
            ) VALUES (
                :id, :version_id, :model_id, :source_row_id
                {", 'PURCHASE', 'UNKNOWN'" if table_name == "procurement_options" else ""}
            )
            """,
            {"id": uuid.uuid4(), **graph},
        )


def test_resolved_fact_requires_exactly_one_typed_value(connection, graph):
    base = {
        "id": uuid.uuid4(),
        **graph,
        "spec_code": "payload_kg",
        "status": "VERIFIED_OFFICIAL",
    }
    statement = """
        INSERT INTO resolved_spec_facts (
            id, catalog_version_id, equipment_model_id, primary_evidence_id,
            spec_code, numeric_value, text_value, canonical_unit,
            resolution_status, usable_for_matching, resolved_at
        ) VALUES (
            :id, :version_id, :model_id, :evidence_id,
            :spec_code, :numeric_value, :text_value, 'kg',
            :status, false, now()
        )
    """
    _expect_integrity_error(
        connection,
        statement,
        {**base, "numeric_value": None, "text_value": None},
    )
    _expect_integrity_error(
        connection,
        statement,
        {**base, "id": uuid.uuid4(), "numeric_value": 1000, "text_value": "1000"},
    )


def test_evidence_gate_and_matching_view(connection, graph):
    unsafe_id = uuid.uuid4()
    _expect_integrity_error(
        connection,
        """
        INSERT INTO resolved_spec_facts (
            id, catalog_version_id, equipment_model_id, primary_evidence_id,
            spec_code, numeric_value, canonical_unit, resolution_status,
            usable_for_matching, resolved_at
        ) VALUES (
            :id, :version_id, :model_id, :evidence_id,
            'payload_kg', 1000, 'kg', 'CONFLICT', true, now()
        )
        """,
        {"id": unsafe_id, **graph},
    )

    connection.execute(
        text(
            """
            INSERT INTO resolved_spec_facts (
                id, catalog_version_id, equipment_model_id, primary_evidence_id,
                spec_code, numeric_value, canonical_unit, resolution_status,
                usable_for_matching, resolved_at
            ) VALUES (
                :id, :version_id, :model_id, :evidence_id,
                'payload_kg', 1000, 'kg', 'VERIFIED_OFFICIAL', true, now()
            )
            """
        ),
        {"id": uuid.uuid4(), **graph},
    )
    connection.execute(
        text(
            """
            INSERT INTO resolved_spec_facts (
                id, catalog_version_id, equipment_model_id, primary_evidence_id,
                spec_code, text_value, canonical_unit, resolution_status,
                usable_for_matching, resolved_at
            ) VALUES (
                :id, :version_id, :model_id, :evidence_id,
                'navigation', 'lidar', '1', 'UNKNOWN', false, now()
            )
            """
        ),
        {"id": uuid.uuid4(), **graph},
    )
    rows = connection.execute(
        text(
            "SELECT spec_code, resolution_status FROM matching_spec_facts WHERE catalog_version_id = :version_id"
        ),
        graph,
    ).all()
    assert rows == [("payload_kg", "VERIFIED_OFFICIAL")]


def test_reviewed_matching_status_requires_review_metadata(connection, graph):
    statement = """
        INSERT INTO resolved_spec_facts (
            id, catalog_version_id, equipment_model_id, primary_evidence_id,
            spec_code, text_value, canonical_unit, resolution_status,
            usable_for_matching, reviewed_by_subject, review_reason, reviewed_at,
            resolved_at
        ) VALUES (
            :id, :version_id, :model_id, :evidence_id,
            :spec_code, 'supported', '1', 'MANUALLY_APPROVED',
            true, :reviewer, :reason, :reviewed_at, now()
        )
    """
    _expect_integrity_error(
        connection,
        statement,
        {
            "id": uuid.uuid4(),
            **graph,
            "spec_code": "integration_wms",
            "reviewer": None,
            "reason": None,
            "reviewed_at": None,
        },
    )
    connection.execute(
        text(statement),
        {
            "id": uuid.uuid4(),
            **graph,
            "spec_code": "integration_wms",
            "reviewer": "reviewer:test",
            "reason": "Exact variant reviewed",
            "reviewed_at": datetime.now(UTC),
        },
    )


def test_procurement_policy_requires_explicit_provenance(connection, graph):
    statement = """
        INSERT INTO procurement_options (
            id, catalog_version_id, equipment_model_id, catalog_source_row_id,
            field_evidence_id, procurement_mode, raw_price, amount, currency,
            currency_provenance, vat_status, vat_rate, vat_provenance,
            price_status
        ) VALUES (
            :id, :version_id, :model_id, :source_row_id,
            :evidence_id, 'PURCHASE', '1000000', 1000000, 'RUB',
            :currency_provenance, 'ORGANIZER_ASSUMPTION_INCLUDED', :vat_rate,
            :vat_provenance, 'NORMALIZED'
        )
    """
    _expect_integrity_error(
        connection,
        statement,
        {
            "id": uuid.uuid4(),
            **graph,
            "currency_provenance": None,
            "vat_rate": None,
            "vat_provenance": "organizer-policy-v1",
        },
    )
    _expect_integrity_error(
        connection,
        statement,
        {
            "id": uuid.uuid4(),
            **graph,
            "currency_provenance": "organizer-v4-product-decision",
            "vat_rate": 0.2,
            "vat_provenance": "organizer-policy-v1",
        },
    )
    connection.execute(
        text(statement),
        {
            "id": uuid.uuid4(),
            **graph,
            "currency_provenance": "organizer-v4-product-decision",
            "vat_rate": None,
            "vat_provenance": "organizer-policy-v1",
        },
    )


def test_equipment_model_has_no_price_columns(catalog_engine):
    columns = {
        column["name"]
        for column in inspect(catalog_engine).get_columns("equipment_models")
    }
    assert {"price", "amount", "currency", "vat_status"}.isdisjoint(columns)


def test_validated_catalog_domain_is_immutable(connection):
    version_id = _insert_version(connection)
    manufacturer_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO manufacturers (
                id, catalog_version_id, source_namespace, source_record_key, name
            ) VALUES (:id, :version_id, 'organizer-v4', 'manufacturer-1', 'Vendor')
            """
        ),
        {"id": manufacturer_id, "version_id": version_id},
    )
    validated_at = datetime.now(UTC) + timedelta(seconds=1)
    connection.execute(
        text(
            """
            UPDATE catalog_versions
            SET status = 'VALIDATED', validated_at = :validated_at,
                updated_at = :validated_at
            WHERE id = :version_id
            """
        ),
        {"version_id": version_id, "validated_at": validated_at},
    )
    _expect_integrity_error(
        connection,
        "UPDATE manufacturers SET name = 'Changed' WHERE id = :id",
        {"id": manufacturer_id},
    )
    _expect_integrity_error(
        connection,
        "DELETE FROM manufacturers WHERE id = :id",
        {"id": manufacturer_id},
    )
    _expect_integrity_error(
        connection,
        """
        INSERT INTO manufacturers (
            id, catalog_version_id, source_namespace, source_record_key, name
        ) VALUES (:id, :version_id, 'manual', 'late-row', 'Late vendor')
        """,
        {"id": uuid.uuid4(), "version_id": version_id},
    )


def test_catalog_version_delete_is_restricted(connection):
    version_id = _insert_version(connection)
    _insert_model(connection, version_id)
    _expect_integrity_error(
        connection,
        "DELETE FROM catalog_versions WHERE id = :version_id",
        {"version_id": version_id},
    )
