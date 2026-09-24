from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import catalog_models  # noqa: F401
import persistence_models  # noqa: F401
import pytest
from alembic import command
from alembic.config import Config
from catalog_activation import (
    CatalogActivationError,
    activate_catalog_version,
    catalog_activation_status,
    deactivate_catalog_slot,
    publish_catalog_version,
    validate_catalog_version,
)
from catalog_importer import run_catalog_import
from catalog_capacity_rollout import CapacityDualRunReportV1, validate_capacity_source
from catalog_repository import ActivatedCatalogRepository
from database import Database, DatabaseSettings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from storage_models import CatalogActivation, CatalogVersion

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


@pytest.fixture(scope="module")
def activation_database():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(str(ALEMBIC_CONFIG)), "head")
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
        monkeypatch.undo()


def test_publish_activate_discovery_and_safe_runtime_gate(activation_database):
    run_catalog_import(activation_database, BUNDLE, phase="BASE", mode="COMMIT")
    run_catalog_import(activation_database, BUNDLE, phase="ENRICHMENT", mode="COMMIT")

    validated = validate_catalog_version(
        activation_database, "organizer-catalog-v4", BUNDLE
    )
    assert validated.status == "VALIDATED"
    assert validated.checks["object_profile_counts"] == {
        "warehouse": 42,
        "airport": 39,
        "medical_facility": 57,
    }
    published = publish_catalog_version(
        activation_database, "organizer-catalog-v4", BUNDLE
    )
    assert published.status == "PUBLISHED"
    assert (
        publish_catalog_version(
            activation_database, "organizer-catalog-v4", BUNDLE
        ).status
        == "PUBLISHED"
    )

    activated = activate_catalog_version(
        activation_database,
        "organizer-catalog-v4",
        slot="discovery",
        actor_subject="integration-test",
    )
    assert activated.changed is True
    assert activated.runtime_ready_models == 0
    repeated = activate_catalog_version(
        activation_database,
        "organizer-catalog-v4",
        slot="discovery",
        actor_subject="integration-test",
    )
    assert repeated.changed is False
    assert repeated.activation_id == activated.activation_id

    assert (
        deactivate_catalog_slot(activation_database, slot="discovery").changed is True
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent = list(
            executor.map(
                lambda index: activate_catalog_version(
                    activation_database,
                    "organizer-catalog-v4",
                    slot="discovery",
                    actor_subject=f"integration-test-{index}",
                ),
                range(2),
            )
        )
    assert sorted(result.changed for result in concurrent) == [False, True]
    assert len({result.activation_id for result in concurrent}) == 1

    snapshot = ActivatedCatalogRepository(activation_database, "discovery").load()
    assert snapshot.version.status == "PUBLISHED"
    assert len(snapshot.models) == 187
    assert len(snapshot.positions) == 223
    assert snapshot.runtime_robots() == []
    assert len(snapshot.calculation_ready_models()) == 21
    assert len(snapshot.calculation_ready_positions()) == 24
    assert all(
        position.model.system_family == "BRS"
        for position in snapshot.calculation_ready_positions()
    )
    assert catalog_activation_status(activation_database)["history_count"] == 2

    import main

    with TestClient(main.app) as client:
        status_response = client.get("/api/catalog/status")
        assert status_response.status_code == 200
        assert status_response.json()["runtime"] == {
            "source": "unavailable",
            "catalog_code": None,
            "catalog_status": None,
            "selectable_count": 0,
        }
        assert status_response.json()["capacity"]["status"] == "UNAVAILABLE"
        assert status_response.json()["capacity"]["fallback_mode"] == "FAIL_CLOSED"
        assert status_response.json()["discovery"] == {
            "source": "activated",
            "catalog_code": "organizer-catalog-v4",
            "catalog_status": "PUBLISHED",
            "model_count": 187,
            "position_count": 223,
            "selectable_count": 0,
            "calculation_ready_model_count": 21,
            "calculation_ready_position_count": 24,
        }
        search = client.get(
            "/api/catalog/models",
            params={"q": "Ronavi", "system_family": "BRS", "sort": "type"},
        )
        assert search.status_code == 200
        payload = search.json()
        assert 0 < payload["total"] < 223
        assert payload["model_count"] == 187
        assert payload["position_count"] == 223
        assert payload["catalog"]["source"] == "activated"
        assert all(item["system_family"] == "BRS" for item in payload["items"])
        assert all(item["selectable"] is False for item in payload["items"])
        assert all(item["position_id"] != item["model_id"] for item in payload["items"])
        assert payload["calculation_ready_model_count"] == 21
        assert payload["calculation_ready_position_count"] == 24
        assert payload["calculation_readiness_counts"]["CALCULATION_READY"] == {
            "models": 6,
            "positions": 6,
        }
        assert payload["calculation_readiness_counts"][
            "CALCULATION_READY_WITH_ASSUMPTIONS"
        ] == {"models": 15, "positions": 18}

        participating = client.get(
            "/api/catalog/models",
            params={"calculation_participation": "participating"},
        ).json()
        assert participating["total"] == 24
        assert all(item["calculation_ready"] is True for item in participating["items"])
        assert all(item["system_family"] == "BRS" for item in participating["items"])
        assert all(item["selectable"] is False for item in participating["items"])
        assert all(item["runtime_catalog_version"] for item in participating["items"])
        mule = next(
            item for item in participating["items"]
            if item["organizer_id"] == "ecd7d582-b342-449a-b43b-66288d159a32"
        )
        assert mule["model_id"] != mule["organizer_id"]
        assert mule["calculation_profile"] == "TRANSPORT_CYCLE_V1"

        requires_data = client.get(
            "/api/catalog/models",
            params={"calculation_participation": "requires_data"},
        ).json()
        assert requires_data["total"] == 199
        assert all(item["calculation_ready"] is False for item in requires_data["items"])

        combined = client.get(
            "/api/catalog/models",
            params={
                "calculation_participation": "participating",
                "q": "Ronavi",
                "system_family": "BRS",
                "manufacturer": 'ООО "Ронави Роботикс"',
                "sort": "manufacturer",
            },
        ).json()
        assert 0 < combined["total"] < 24
        assert all(item["calculation_ready"] is True for item in combined["items"])

    with pytest.raises(CatalogActivationError, match="evidence-backed"):
        activate_catalog_version(
            activation_database,
            "organizer-catalog-v4",
            slot="runtime",
            actor_subject="integration-test",
        )

    deactivated = deactivate_catalog_slot(activation_database, slot="discovery")
    assert deactivated.changed is True
    assert catalog_activation_status(activation_database)["active"] == []
    assert catalog_activation_status(activation_database)["history_count"] == 2
    assert (
        deactivate_catalog_slot(activation_database, slot="discovery").changed is False
    )

    with activation_database.session() as session:
        version = session.scalar(
            select(CatalogVersion).where(CatalogVersion.code == "organizer-catalog-v4")
        )
        activations = session.scalars(select(CatalogActivation)).all()
        assert version is not None and version.published_at is not None
        assert len(activations) == 2
        assert all(activation.deactivated_at is not None for activation in activations)


def test_capacity_activation_requires_approval_and_persists_rollback(activation_database):
    with pytest.raises(CatalogActivationError, match="approved dual-run"):
        activate_catalog_version(
            activation_database, "organizer-catalog-v4",
            slot="capacity", actor_subject="integration-test",
        )
    report = CapacityDualRunReportV1.model_validate_json(
        (Path(__file__).resolve().parents[1] / "contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json").read_text(encoding="utf-8")
    )
    activated = activate_catalog_version(
        activation_database, "organizer-catalog-v4",
        slot="capacity", actor_subject="integration-test",
        capacity_approval=report,
    )
    assert activated.changed is True
    assert activated.approval_report_digest == report.report_digest
    assert activated.rollback_mode == "DEACTIVATE"
    assert activated.rollback_catalog_code is None
    snapshot = ActivatedCatalogRepository(activation_database, "capacity").load()
    summary = validate_capacity_source(snapshot)
    assert summary.calculation_pool_models == 21
    status = next(item for item in catalog_activation_status(activation_database)["active"] if item["slot"] == "capacity")
    assert status["approval_report_digest"] == report.report_digest
    assert status["rollback_mode"] == "DEACTIVATE"
    assert status["rollback_catalog_code"] is None
    assert deactivate_catalog_slot(activation_database, slot="capacity").changed is True
