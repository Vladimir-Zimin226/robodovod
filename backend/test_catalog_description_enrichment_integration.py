from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from catalog_description_enrichment import import_description_overlay
from catalog_importer import run_catalog_import
from catalog_media import import_catalog_media
from catalog_models import CatalogPositionEnrichment, ResolvedSpecFact
from database import Database, DatabaseSettings
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must point to a disposable PostgreSQL database")
ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"
SOURCE_DIR = ROOT / "Разобрать" / "Материалы от организаторов" / "Датасет"
PDF = SOURCE_DIR / "ФЦ БАС — Каталог внедрения 2008 1247.pdf"
ALEMBIC_CONFIG = Path(__file__).with_name("alembic.ini")


@pytest.mark.skipif(not PDF.is_file(), reason="restricted catalog sources are local-only")
def test_description_import_is_atomic_idempotent_and_not_matching_evidence(tmp_path):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(str(ALEMBIC_CONFIG)), "head")
    engine = create_engine(TEST_DATABASE_URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE catalog_description_imports, catalog_position_enrichments, catalog_media_assets, catalog_position_media, resolved_spec_fact_evidence, resolved_spec_facts, spec_observations, procurement_options, field_evidence, equipment_applicability, catalog_source_rows, equipment_models, manufacturers, catalog_version_sources, import_runs, catalog_activations, source_artifacts, catalog_versions CASCADE"))
    engine.dispose()
    database = Database(DatabaseSettings(url=make_url(TEST_DATABASE_URL)))
    try:
        run_catalog_import(database, BUNDLE, phase="BASE", mode="COMMIT")
        run_catalog_import(database, BUNDLE, phase="ENRICHMENT", mode="COMMIT")
        import_catalog_media(database, catalog_code="organizer-catalog-v4", pdf_path=PDF, storage_root=tmp_path)
        before_facts = 0
        with database.session() as session:
            before_facts = session.scalar(select(func.count()).select_from(ResolvedSpecFact))

        first = import_description_overlay(database, source_dir=SOURCE_DIR, bundle_dir=BUNDLE)
        second = import_description_overlay(database, source_dir=SOURCE_DIR, bundle_dir=BUNDLE)

        assert first["changed"] is True
        assert second["changed"] is False
        with database.session() as session:
            assert session.scalar(select(func.count()).select_from(CatalogPositionEnrichment)) == 223
            assert session.scalar(select(func.count()).select_from(ResolvedSpecFact)) == before_facts
    finally:
        database.dispose()
        monkeypatch.undo()
