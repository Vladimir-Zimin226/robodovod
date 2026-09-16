from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from catalog_dual_run import load_dual_run_fixture, run_dual_run
from catalog_importer import run_catalog_import
from catalog_models import (
    SAFE_AUTOMATIC_STATUSES,
    FieldEvidence,
    EquipmentModel,
    ResolvedSpecFact,
)
from catalog_repository import (
    LegacyFleetCatalogRepository,
    PostgresCatalogRepository,
)
from database import Database, DatabaseSettings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from storage_models import CatalogVersion, CatalogVersionSource, SourceArtifact


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
ALEMBIC_CONFIG = Path(__file__).with_name("alembic.ini")
BUNDLE = (
    Path(__file__).resolve().parents[1] / "data" / "import" / "organizer-catalog-v4"
)
DUAL_RUN_FIXTURE = (
    Path(__file__).with_name("fixtures") / "catalog-dual-run-warehouse-v1.json"
)
DOMAIN_TABLES = (
    "resolved_spec_fact_evidence",
    "resolved_spec_facts",
    "spec_observations",
    "procurement_options",
    "field_evidence",
    "equipment_applicability",
    "catalog_source_rows",
    "equipment_models",
    "manufacturers",
)


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(str(ALEMBIC_CONFIG)), "head")
    yield
    monkeypatch.undo()


@pytest.fixture
def repository_database(migrated_database):
    engine = create_engine(TEST_DATABASE_URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE "
                + ", ".join(
                    (
                        *DOMAIN_TABLES,
                        "catalog_version_sources",
                        "import_runs",
                        "catalog_activations",
                        "source_artifacts",
                        "catalog_versions",
                    )
                )
                + " CASCADE"
            )
        )
    engine.dispose()
    database = Database(DatabaseSettings(url=make_url(TEST_DATABASE_URL)))
    try:
        yield database
    finally:
        database.dispose()


def _seed_runtime_mirror(database: Database) -> str:
    legacy_snapshot = LegacyFleetCatalogRepository().load()
    legacy_model = legacy_snapshot.by_source_key()["amr_heavy_1350"]
    robot = legacy_model.runtime_dict()
    assert robot is not None

    version_id = uuid.uuid4()
    model_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    observed_at = datetime(2026, 9, 16, tzinfo=UTC)
    facts = (
        ("payload", Decimal(str(robot["specs"]["payload_kg"])), None, "kg"),
        (
            "max_speed",
            Decimal(str(robot["specs"]["max_speed_m_s"])),
            None,
            "m/s",
        ),
        (
            "min_aisle_width",
            Decimal(str(robot["specs"]["min_aisle_width_m"])),
            None,
            "m",
        ),
        (
            "autonomy",
            Decimal(str(robot["specs"]["autonomy_hours"])),
            None,
            "h",
        ),
        ("navigation", None, robot["specs"]["navigation_type"], "1"),
    )

    with database.session() as session:
        session.add(
            CatalogVersion(
                id=version_id,
                code="dual-run-runtime-mirror",
                status="DRAFT",
                schema_version="2",
            )
        )
        session.add(
            SourceArtifact(
                id=artifact_id,
                sha256="a" * 64,
                original_name="dual-run-fixture.json",
                media_type="application/json",
                byte_size=1,
                provenance_status="VERIFIED",
                license_status="PERMITTED",
                observed_at=observed_at,
            )
        )
        session.flush()
        session.add(
            CatalogVersionSource(
                catalog_version_id=version_id,
                source_artifact_id=artifact_id,
                role="REFERENCE",
                ordinal=0,
            )
        )
        session.add(
            EquipmentModel(
                id=model_id,
                catalog_version_id=version_id,
                source_namespace="dual-run-fixture",
                source_record_key=robot["id"],
                name=robot["name"],
                system_family=robot["category"],
                type_code=robot["type_label"],
                description=robot["description"],
                attributes={"runtime_projection": robot},
            )
        )
        session.flush()
        for index, (code, numeric_value, text_value, unit) in enumerate(facts):
            evidence_id = uuid.uuid4()
            session.add(
                FieldEvidence(
                    id=evidence_id,
                    catalog_version_id=version_id,
                    source_artifact_id=artifact_id,
                    equipment_model_id=model_id,
                    source_namespace="dual-run-fixture",
                    source_record_key=f"evidence-{index}",
                    subject_type="PRODUCT",
                    subject_key=robot["id"],
                    field_path=f"specs.{code}",
                    raw_value=str(numeric_value or text_value),
                    evidence_status="VERIFIED_OFFICIAL",
                    observed_at=observed_at,
                )
            )
            session.flush()
            session.add(
                ResolvedSpecFact(
                    id=uuid.uuid4(),
                    catalog_version_id=version_id,
                    equipment_model_id=model_id,
                    primary_evidence_id=evidence_id,
                    spec_code=code,
                    scope_code="GLOBAL",
                    numeric_value=numeric_value,
                    text_value=text_value,
                    canonical_unit=unit,
                    resolution_status="VERIFIED_OFFICIAL",
                    usable_for_matching=True,
                    resolved_at=observed_at,
                )
            )
        session.commit()
    return "dual-run-runtime-mirror"


def test_postgres_adapter_and_dual_run_match_safe_runtime_mirror(
    repository_database, monkeypatch
):
    code = _seed_runtime_mirror(repository_database)
    repository = PostgresCatalogRepository(repository_database, code)
    snapshot = repository.load()
    candidate = snapshot.models[0]

    assert snapshot.version.code == code
    assert candidate.runtime_robot is not None
    assert candidate.runtime_blockers == ()
    assert not hasattr(candidate, "_sa_instance_state")
    assert {fact.resolution_status for fact in candidate.facts} == {
        "VERIFIED_OFFICIAL"
    }

    loaded_fixture = load_dual_run_fixture(DUAL_RUN_FIXTURE)
    fixture_payload = loaded_fixture.model_dump(mode="json")
    fixture_payload["model_pairs"] = [
        {
            "reference_id": "amr_heavy_1350",
            "candidate_id": "amr_heavy_1350",
        }
    ]
    fixture_payload["expected_differences"] = []
    fixture = type(loaded_fixture).model_validate(fixture_payload)
    monkeypatch.setenv("CATALOG_DUAL_RUN_ENABLED", "true")
    report = run_dual_run(
        LegacyFleetCatalogRepository(), repository, fixture
    )

    assert report["summary"]["DEFECT"] == 0
    assert report["summary"]["BLOCKED_BY_EVIDENCE"] == 0
    assert report["summary"]["MATCH"] == 13


def test_official_catalog_exposes_only_safe_facts_and_reports_blockers(
    repository_database, monkeypatch
):
    run_catalog_import(repository_database, BUNDLE, phase="BASE", mode="COMMIT")
    run_catalog_import(
        repository_database, BUNDLE, phase="ENRICHMENT", mode="COMMIT"
    )
    repository = PostgresCatalogRepository(
        repository_database, "organizer-catalog-v4"
    )
    snapshot = repository.load()

    assert len(snapshot.models) == 187
    assert all(
        fact.resolution_status in SAFE_AUTOMATIC_STATUSES
        for model in snapshot.models
        for fact in model.facts
    )
    candidate = snapshot.by_source_key()[
        "org-5760e938-9a43-45a7-b8e8-f4f2e6383930"
    ]
    assert candidate.runtime_robot is None
    assert candidate.runtime_blockers == ("runtime_projection",)

    fixture = load_dual_run_fixture(DUAL_RUN_FIXTURE)
    monkeypatch.setenv("CATALOG_DUAL_RUN_ENABLED", "true")
    report = run_dual_run(
        LegacyFleetCatalogRepository(), repository, fixture
    )

    assert report["summary"] == {
        "MATCH": 0,
        "EXPECTED_DIFFERENCE": 1,
        "DEFECT": 0,
        "BLOCKED_BY_EVIDENCE": 12,
    }
    assert report["unused_expectations"] == []
    assert all(
        item["reason"]
        for item in report["comparisons"]
        if item["classification"] != "MATCH"
    )
