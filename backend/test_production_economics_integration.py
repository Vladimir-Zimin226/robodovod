from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import main
import pytest
from pypdf import PdfReader
from alembic import command
from alembic.config import Config
from catalog_activation import activate_catalog_version, publish_catalog_version
from catalog_capacity_rollout import CapacityDualRunReportV1
from catalog_importer import run_catalog_import
from catalog_repository import ActivatedCatalogRepository
from database import Database, DatabaseSettings, dispose_database
from economics_route_activation import activate_economics_route
from economics_runtime_migration import EconomicsDualRunReportV1
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_economics_orchestrator import (
    _capacity_request,
    _inputs,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/import/organizer-catalog-v4"
ALEMBIC_CONFIG = Path(__file__).with_name("alembic.ini")
MULE_ORGANIZER_ID = "ecd7d582-b342-449a-b43b-66288d159a32"
PASSWORD = "production acceptance test passphrase"


@pytest.fixture(scope="module", autouse=True)
def activated_actual_catalog():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    dispose_database()
    command.upgrade(Config(str(ALEMBIC_CONFIG)), "head")
    engine = create_engine(TEST_DATABASE_URL, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, audit_entries, catalog_versions, "
                "economics_route_activations RESTART IDENTITY CASCADE"
            )
        )
    database = Database(DatabaseSettings(url=make_url(TEST_DATABASE_URL)))
    run_catalog_import(database, BUNDLE, phase="BASE", mode="COMMIT")
    run_catalog_import(database, BUNDLE, phase="ENRICHMENT", mode="COMMIT")
    publish_catalog_version(database, "organizer-catalog-v4", BUNDLE)
    capacity_approval = CapacityDualRunReportV1.model_validate_json(
        (
            ROOT / "contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json"
        ).read_text(encoding="utf-8")
    )
    activate_catalog_version(
        database,
        "organizer-catalog-v4",
        slot="capacity",
        actor_subject="production-acceptance",
        capacity_approval=capacity_approval,
    )
    activate_catalog_version(
        database,
        "organizer-catalog-v4",
        slot="discovery",
        actor_subject="production-acceptance",
    )
    economics_approval = EconomicsDualRunReportV1.model_validate_json(
        (
            ROOT / "contracts/fixtures/economics-dual-run-report-v1.golden.json"
        ).read_text(encoding="utf-8")
    )
    activate_economics_route(
        database, economics_approval, actor_subject="production-acceptance"
    )
    try:
        yield database
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE users, audit_entries, catalog_versions, "
                    "economics_route_activations RESTART IDENTITY CASCADE"
                )
            )
        database.dispose()
        engine.dispose()
        dispose_database()
        monkeypatch.undo()


def _register(client: TestClient) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "actual-catalog-acceptance@example.com",
            "password": PASSWORD,
            "name": "Production acceptance",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload, {"X-CSRF-Token": payload["csrf_token"]}


def test_actual_catalog_http_api_c11_c21_reopen_replay_and_export(
    activated_actual_catalog,
):
    snapshot = ActivatedCatalogRepository(activated_actual_catalog, "capacity").load()
    position = next(
        item
        for item in snapshot.positions
        if item.model.organizer_id == MULE_ORGANIZER_ID
        and item.model.capacity_runtime is not None
        and item.model.capacity_runtime.calculation_ready
        and item.procurement_option.amount is not None
    )
    assert snapshot.version.code == "organizer-catalog-v4"
    assert position.procurement_option.amount > 0

    with TestClient(main.app) as client:
        _, headers = _register(client)
        project_response = client.post(
            "/api/projects", headers=headers, json={"name": "Actual catalog flow"}
        )
        assert project_response.status_code == 201, project_response.text
        project = project_response.json()
        scenario = next(item for item in project["scenarios"] if item["slot"] == "BASE")

        capacity_input = _capacity_request().model_dump(mode="json")
        capacity_input.update(
            project_id=project["id"],
            model_id=position.model.id,
            position_id=position.id,
        )
        # C01 emits conversion refs; the browser preserves them in the C11
        # request rather than inventing provenance entries in its payload.
        capacity_input["process"]["demand"]["provenance_ref"] = "conversion.0001"
        capacity_input["process"]["schedule"]["shifts_per_day"]["provenance_ref"] = "conversion.0002"
        capacity_input["process"]["schedule"]["shift_hours"]["provenance_ref"] = "conversion.0003"
        capacity_input["process"]["route_distance"]["provenance_ref"] = "conversion.0005"
        capacity_input["process"]["explicit_batch"]["provenance_ref"] = "conversion.0006"
        capacity_response = client.post(
            "/api/v2/capacity-analyses", headers=headers, json=capacity_input
        )
        assert capacity_response.status_code == 201, capacity_response.text
        capacity = capacity_response.json()
        assert capacity["capacity"]["status"] == "WITH_ASSUMPTIONS"
        assert capacity["trace"]["replay"]["canonical_input_digest"]
        assert all(
            item["provenance_ref"] in {node["provenance_id"] for node in capacity["trace"]["provenance"]}
            for item in capacity["trace"]["inputs"]
        )
        capacity_reopened = client.get(f"/api/v2/capacity-analyses/{capacity['run_id']}")
        assert capacity_reopened.status_code == 200
        assert capacity_reopened.json()["trace"]["replay"] == capacity["trace"]["replay"]
        capacity_record = client.get(
            f"/api/projects/{project['id']}/analysis-runs/{capacity['run_id']}"
        )
        assert capacity_record.status_code == 200
        assert (
            capacity_record.json()["input_snapshot"]["process"]["explicit_batch"]["provenance_ref"]
            == "conversion.0006"
        )
        assert any(
            check["status"] in {"UNKNOWN", "ASSUMED"}
            for check in capacity["trace"]["constraints"]
        )

        economics_endpoint = f"/api/v2/projects/{project['id']}/economics-runs"
        economics_response = client.post(
            economics_endpoint,
            headers=headers,
            json={
                "scenario_id": scenario["id"],
                "capacity_run_id": capacity["run_id"],
                "input": _inputs(),
            },
        )
        assert economics_response.status_code == 201, economics_response.text
        run = economics_response.json()
        assert run["versions"]["catalog"] == "organizer-catalog-v4"
        assert run["input_snapshot"]["capacity_run_id"] == capacity["run_id"]
        assert len(run["result_snapshot"]["scenarios"]) == 6
        assert all(
            item["procurement"]["procurement_ready"] is False
            and item["recommendation"]["status"] != "RECOMMENDED"
            for item in run["result_snapshot"]["scenarios"]
        )
        assert any(
            "не является техпаспортом" in item
            for item in run["result_snapshot"]["limitations"]
        )

        reopened = client.get(
            f"/api/projects/{project['id']}/analysis-runs/{run['id']}"
        )
        assert reopened.status_code == 200
        assert reopened.json()["checksums"] == run["checksums"]
        replay = client.post(
            f"{economics_endpoint}/{run['id']}/replay", headers=headers
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["status"] == "MATCH"

        manifest = client.get(
            f"/api/projects/{project['id']}/analysis-runs/{run['id']}/exports/manifest"
        )
        archive = client.get(
            f"/api/projects/{project['id']}/analysis-runs/{run['id']}/exports/evidence.zip"
        )
        assert manifest.status_code == 200, manifest.text
        assert archive.status_code == 200
        assert (
            archive.headers["x-export-manifest-digest"]
            == manifest.json()["manifest_digest"]
        )
        with zipfile.ZipFile(io.BytesIO(archive.content)) as evidence:
            assert json.loads(evidence.read("manifest.json")) == manifest.json()
            for artifact in manifest.json()["artifacts"]:
                assert (
                    "sha256:" + hashlib.sha256(evidence.read(artifact["filename"])).hexdigest()
                    == artifact["sha256"]
                )
        report = client.get(
            f"/api/projects/{project['id']}/analysis-runs/{run['id']}/exports/report.pdf"
        )
        assert report.status_code == 200
        assert report.headers["x-report-source-digest"] == "sha256:" + run["checksums"]["result"]
        report_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(report.content)).pages)
        assert "NEEDS_VALIDATION" in report_text
        assert "UNVERIFIED" in report_text
