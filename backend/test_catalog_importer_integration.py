from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from catalog_importer import CatalogImportError, run_catalog_import
from catalog_models import (
    CatalogSourceRow,
    EquipmentApplicability,
    EquipmentModel,
    FieldEvidence,
    ProcurementOption,
    ResolvedSpecFact,
    SpecObservation,
)
from database import Database, DatabaseSettings
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from storage_models import CatalogVersion, ImportRun, SourceArtifact

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
ALEMBIC_CONFIG = Path(__file__).with_name("alembic.ini")
BUNDLE = (
    Path(__file__).resolve().parents[1] / "data" / "import" / "organizer-catalog-v4"
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
def importer_database(migrated_database):
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


def _scalar(database: Database, statement):
    with database.session() as session:
        return session.scalar(statement)


def _copy_bundle(tmp_path: Path) -> Path:
    target = tmp_path / "bundle"
    shutil.copytree(BUNDLE, target)
    return target


def _rewrite_manifest_file_hash(bundle: Path, file_name: str) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = (bundle / file_name).read_bytes()
    for entry in manifest["files"]:
        if entry["path"] == file_name:
            entry["sha256"] = hashlib.sha256(payload).hexdigest()
            entry["size_bytes"] = len(payload)
            break
    for artifact in manifest["source_artifacts"]:
        if artifact["artifact_key"] == f"bundle:{file_name}":
            artifact["sha256"] = hashlib.sha256(payload).hexdigest()
            artifact["size_bytes"] = len(payload)
            break
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_validate_only_records_run_without_domain_rows(importer_database):
    result = run_catalog_import(
        importer_database, BUNDLE, phase="BASE", mode="VALIDATE_ONLY"
    )
    assert result.status == "SUCCEEDED"
    assert result.counts["products"] == 187
    assert (
        _scalar(importer_database, select(func.count()).select_from(EquipmentModel))
        == 0
    )
    assert _scalar(importer_database, select(func.count()).select_from(ImportRun)) == 1


def test_base_commit_reconciles_counts_policy_and_is_idempotent(importer_database):
    result = run_catalog_import(
        importer_database,
        BUNDLE,
        phase="BASE",
        mode="COMMIT",
        request_key="base-commit-1",
    )
    assert result.counts == {
        "manufacturers": result.counts["manufacturers"],
        "equipment_models": 187,
        "catalog_source_rows": 223,
        "equipment_applicability": 223,
        "field_evidence": 3635,
        "spec_observations": 65,
        "resolved_spec_facts": 65,
        "procurement_options": 223,
    }
    with importer_database.session() as session:
        assert session.scalar(select(func.count()).select_from(EquipmentModel)) == 187
        assert session.scalar(select(func.count()).select_from(CatalogSourceRow)) == 223
        assert (
            session.scalar(select(func.count()).select_from(EquipmentApplicability))
            == 223
        )
        assert (
            session.scalar(select(func.count()).select_from(ProcurementOption)) == 223
        )
        assert session.scalar(select(func.count()).select_from(FieldEvidence)) == 3635
        assert session.scalar(select(func.count()).select_from(SpecObservation)) == 65
        assert session.scalar(select(func.count()).select_from(ResolvedSpecFact)) == 65
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProcurementOption)
                .where(
                    ProcurementOption.currency == "RUB",
                    ProcurementOption.currency_provenance
                    == "product-decision:organizer-catalog-v4-rub-v1",
                    ProcurementOption.vat_status == "ORGANIZER_ASSUMPTION_INCLUDED",
                    ProcurementOption.vat_rate.is_(None),
                )
            )
            == 223
        )
        excluded = session.scalar(select(ProcurementOption.excluded_costs).limit(1))
        assert excluded == ["delivery", "commissioning/start-up", "deep IT integration"]
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceArtifact)
                .where(
                    SourceArtifact.sha256
                    == "9567641d3a3a7bed9d2e470240b17cefacba047257b5f0b4a5311c159c580369"
                )
            )
            == 1
        )

    repeated = run_catalog_import(
        importer_database, BUNDLE, phase="BASE", mode="COMMIT"
    )
    assert repeated.idempotent is True
    assert repeated.run_id == result.run_id
    assert (
        _scalar(importer_database, select(func.count()).select_from(EquipmentModel))
        == 187
    )


def test_enrichment_requires_base_then_preserves_unsafe_observations(importer_database):
    with pytest.raises(CatalogImportError, match="requires successful BASE"):
        run_catalog_import(importer_database, BUNDLE, phase="ENRICHMENT", mode="COMMIT")
    failed_runs = _scalar(
        importer_database,
        select(func.count()).select_from(ImportRun).where(ImportRun.status == "FAILED"),
    )
    assert failed_runs == 1

    run_catalog_import(importer_database, BUNDLE, phase="BASE", mode="COMMIT")
    validated = run_catalog_import(
        importer_database, BUNDLE, phase="ENRICHMENT", mode="VALIDATE_ONLY"
    )
    assert validated.counts["overlay_fields"] == 140
    assert validated.counts["capacity_runtime_models"] == 187
    assert validated.counts["capacity_runtime_pool_models"] == 21
    assert validated.counts["capacity_runtime_pool_positions"] == 24
    assert validated.counts["capacity_enrichment_facts"] == 131
    assert validated.counts["capacity_enrichment_matching_facts"] == 129
    assert validated.counts["capacity_enrichment_evidence_rows"] == 154
    assert validated.counts["capacity_enrichment_models"] == 26
    assert (
        _scalar(importer_database, select(func.count()).select_from(SpecObservation))
        == 65
    )

    result = run_catalog_import(
        importer_database, BUNDLE, phase="ENRICHMENT", mode="COMMIT"
    )
    assert result.counts == {
        "field_evidence": 310,
        "spec_observations": 271,
        "resolved_spec_facts": 204,
        "resolved_spec_fact_updates": 0,
        "capacity_enrichment_models": 26,
        "capacity_runtime_models": 187,
        "capacity_runtime_pool_models": 21,
        "capacity_runtime_pool_positions": 24,
    }
    with importer_database.session() as session:
        assert session.scalar(select(func.count()).select_from(FieldEvidence)) == 3945
        assert session.scalar(select(func.count()).select_from(SpecObservation)) == 336
        assert session.scalar(select(func.count()).select_from(ResolvedSpecFact)) == 269
        unsafe_observations = session.scalar(
            select(func.count())
            .select_from(SpecObservation)
            .where(
                SpecObservation.observation_status.in_(
                    ("CONFLICT", "AMBIGUOUS_MODEL_MATCH", "NOT_FOUND", "UNKNOWN")
                )
            )
        )
        assert unsafe_observations == 65
        unsafe_facts = session.scalar(
            select(func.count())
            .select_from(ResolvedSpecFact)
            .where(
                ResolvedSpecFact.resolution_status.in_(
                    ("CONFLICT", "AMBIGUOUS_MODEL_MATCH", "NOT_FOUND", "UNKNOWN")
                )
            )
        )
        assert unsafe_facts == 0
        matching_count = session.scalar(
            text("SELECT count(*) FROM matching_spec_facts")
        )
        assert matching_count == 269
        reviewed_count = session.scalar(
            select(func.count())
            .select_from(ResolvedSpecFact)
            .where(ResolvedSpecFact.resolution_status == "MANUALLY_APPROVED")
        )
        assert reviewed_count == 13
        version = session.scalar(select(CatalogVersion))
        assert version is not None and version.status == "DRAFT"
        assert version.content_sha256 is not None

    repeated = run_catalog_import(
        importer_database, BUNDLE, phase="ENRICHMENT", mode="COMMIT"
    )
    assert repeated.idempotent is True
    assert repeated.run_id == result.run_id


def test_checksum_failure_leaves_failed_run_and_no_domain_rows(
    importer_database, tmp_path
):
    bundle = _copy_bundle(tmp_path)
    with (bundle / "catalog_prices.csv").open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(CatalogImportError, match="size mismatch"):
        run_catalog_import(importer_database, bundle, phase="BASE", mode="COMMIT")
    with importer_database.session() as session:
        run = session.scalar(select(ImportRun))
        assert run is not None and run.status == "FAILED"
        assert run.diagnostics["error_code"] == "BUNDLE_VALIDATION_FAILED"
        assert session.scalar(select(func.count()).select_from(EquipmentModel)) == 0


def test_database_failure_rolls_back_complete_phase(importer_database, tmp_path):
    bundle = _copy_bundle(tmp_path)
    products_path = bundle / "catalog_products.json"
    products = json.loads(products_path.read_text(encoding="utf-8"))
    runtime = json.loads(
        (bundle / "catalog_capacity_runtime.json").read_text(encoding="utf-8")
    )
    ready_ids = {
        item["model_id"] for item in runtime["models"] if item["calculation_ready"]
    }
    non_runtime_product = next(
        item
        for item in products["products"]
        if item["organizer_id"] not in ready_ids
    )
    non_runtime_product["system_family"] = ""
    products_path.write_text(
        json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _rewrite_manifest_file_hash(bundle, products_path.name)

    with pytest.raises(CatalogImportError, match="database constraint"):
        run_catalog_import(importer_database, bundle, phase="BASE", mode="COMMIT")
    with importer_database.session() as session:
        run = session.scalar(select(ImportRun))
        assert run is not None and run.status == "FAILED"
        assert run.diagnostics["error_code"] == "DATABASE_CONSTRAINT_FAILED"
        for table in DOMAIN_TABLES:
            assert session.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        assert session.scalar(select(func.count()).select_from(SourceArtifact)) == 0


def test_request_key_cannot_be_reused_for_another_operation(importer_database):
    first = run_catalog_import(
        importer_database,
        BUNDLE,
        phase="BASE",
        mode="VALIDATE_ONLY",
        request_key="stable-request-key",
    )
    repeated = run_catalog_import(
        importer_database,
        BUNDLE,
        phase="BASE",
        mode="VALIDATE_ONLY",
        request_key="stable-request-key",
    )
    assert repeated.idempotent is True
    assert repeated.run_id == first.run_id

    with pytest.raises(CatalogImportError, match="another import"):
        run_catalog_import(
            importer_database,
            BUNDLE,
            phase="ENRICHMENT",
            mode="VALIDATE_ONLY",
            request_key="stable-request-key",
        )


def test_import_rejects_non_draft_version(importer_database):
    validated = run_catalog_import(
        importer_database, BUNDLE, phase="BASE", mode="VALIDATE_ONLY"
    )
    with importer_database.session() as session:
        session.execute(
            text(
                """
                UPDATE catalog_versions
                SET status = 'VALIDATED', validated_at = now(), updated_at = now()
                WHERE id = :version_id
                """
            ),
            {"version_id": validated.catalog_version_id},
        )
        session.commit()

    with pytest.raises(CatalogImportError, match="requires a DRAFT"):
        run_catalog_import(
            importer_database,
            BUNDLE,
            phase="BASE",
            mode="COMMIT",
        )
    with importer_database.session() as session:
        assert session.scalar(select(func.count()).select_from(EquipmentModel)) == 0
        failed = session.scalar(
            select(ImportRun).where(ImportRun.status == "FAILED")
        )
        assert failed is not None
