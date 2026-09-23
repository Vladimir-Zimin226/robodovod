from __future__ import annotations

import io
import json
import uuid
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from auth import require_auth_context
from calculation.evidence_export import (
    EvidenceExportIntegrityError,
    EvidenceRunSnapshotV1,
    build_evidence_export,
)
from database import database_session
from evidence_export_api import create_evidence_export_router
from scripts.build_evidence_export_contract import golden_run


def test_golden_bundle_is_deterministic_complete_and_self_verifying():
    first = build_evidence_export(golden_run())
    second = build_evidence_export(golden_run())
    assert first.archive == second.archive
    assert first.manifest == second.manifest
    assert first.files["CashFlow.csv"] == (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "contracts/fixtures/calculation-evidence-export-v1.cashflow.golden.csv"
    ).read_bytes()
    assert b"-3000000.00" in first.files["CashFlow.csv"]
    assert b"trace.node.cashflow.0" in first.files["CashFlow.csv"]

    with zipfile.ZipFile(io.BytesIO(first.archive)) as archive:
        assert set(archive.namelist()) == {item.filename for item in first.manifest.artifacts} | {"manifest.json"}
        assert json.loads(archive.read("manifest.json"))["manifest_digest"] == first.manifest.manifest_digest
        for artifact in first.manifest.artifacts:
            import hashlib
            assert "sha256:" + hashlib.sha256(archive.read(artifact.filename)).hexdigest() == artifact.sha256

    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(first.files["Report.pdf"])).pages)
    assert "ROBOMERA CALCULATION EVIDENCE EXPORT" in text
    assert "SECTION CashFlow: AVAILABLE" in text
    assert "SECTION Simulation: AVAILABLE" in text
    assert "report.golden.c26" in text
    assert "snapshot-only-no-live-price-refresh" in text
    assert "PRELIMINARY ANALYSIS; NOT ENGINEERING CERTIFICATION" in text


def test_old_capacity_only_run_exports_missing_finance_as_not_available():
    source = golden_run().model_dump()
    source["run_kind"] = "CAPACITY_ANALYSIS"
    source["versions"]["economics"] = None
    source["result_snapshot"] = {"schema_version": "capacity-analysis-response-v2", "capacity": {"required": "42.00"}}
    source["scenario_spec_snapshot"] = None
    source["trace_snapshot"] = {"schema_version": "calculation-trace-v1", "results": []}
    from scripts.build_evidence_export_contract import _checksum
    source["checksums"]["result"] = _checksum(source["result_snapshot"])
    source["checksums"]["scenario_spec"] = None
    source["checksums"]["trace"] = _checksum(source["trace_snapshot"])
    package = build_evidence_export(EvidenceRunSnapshotV1.model_validate(source))
    states = {section.name: section.status for section in package.manifest.sections}
    assert states["CashFlow"] == "NOT_AVAILABLE"
    assert states["Simulation"] == "NOT_AVAILABLE"
    assert b"NOT_AVAILABLE" in package.files["CashFlow.csv"]


def test_csv_cells_neutralize_formulas_but_preserve_negative_decimal_amounts():
    package = build_evidence_export(golden_run())
    inputs = package.files["Inputs.csv"].decode("utf-8-sig")
    cashflow = package.files["CashFlow.csv"].decode("utf-8-sig")
    assert "'=untrusted spreadsheet value" in inputs
    assert "'  @untrusted command" in inputs
    assert "'+untrusted formula" in inputs
    assert "'-untrusted formula" in inputs
    assert "-3000000.00" in cashflow
    assert "'-3000000.00" not in cashflow


def test_snapshot_tampering_is_rejected_before_export():
    source = golden_run().model_dump()
    source["result_snapshot"]["selection"]["required_fleet"] = 99
    with pytest.raises(EvidenceExportIntegrityError, match="result snapshot checksum mismatch"):
        build_evidence_export(EvidenceRunSnapshotV1.model_validate(source))


def test_legacy_and_v2_version_bindings_export_without_recalculation():
    legacy = golden_run()
    legacy_package = build_evidence_export(legacy)
    source = legacy.model_dump(mode="json")
    source["versions"]["economics"] = "economics-runtime-v2"
    v2 = EvidenceRunSnapshotV1.model_validate(source)
    v2_package = build_evidence_export(v2)
    assert legacy_package.manifest.versions["economics"] == legacy.versions["economics"]
    assert v2_package.manifest.versions["economics"] == "economics-runtime-v2"
    assert v2_package.manifest.source_snapshot_digests == legacy_package.manifest.source_snapshot_digests


def test_api_is_owner_scoped_and_binds_bundle_to_manifest_digest():
    owner = uuid.uuid4()
    project = uuid.UUID(golden_run().project_id)
    run_id = uuid.UUID(golden_run().run_id)
    calls = []

    def loader(_db, candidate_project, candidate_run, candidate_owner):
        calls.append((candidate_project, candidate_run, candidate_owner))
        return golden_run() if candidate_owner == owner else None

    app = FastAPI()
    app.include_router(create_evidence_export_router(loader))
    context = SimpleNamespace(user=SimpleNamespace(id=owner))
    app.dependency_overrides[require_auth_context] = lambda: context
    app.dependency_overrides[database_session] = lambda: object()
    client = TestClient(app)
    base = f"/api/projects/{project}/analysis-runs/{run_id}/exports"
    manifest_response = client.get(f"{base}/manifest")
    assert manifest_response.status_code == 200
    bundle_response = client.get(f"{base}/evidence.zip")
    assert bundle_response.status_code == 200
    assert bundle_response.headers["x-export-manifest-digest"] == manifest_response.json()["manifest_digest"]
    assert bundle_response.headers["content-type"] == "application/zip"
    assert all(item[:2] == (project, run_id) for item in calls)

    app.dependency_overrides[require_auth_context] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    assert client.get(f"{base}/manifest").status_code == 404


def test_manifest_rejects_unknown_version_and_extra_fields():
    body = build_evidence_export(golden_run()).manifest.model_dump(mode="json")
    with pytest.raises(Exception):
        type(build_evidence_export(golden_run()).manifest).model_validate({**body, "schema_version": "calculation-evidence-export-manifest-v2"})
    with pytest.raises(Exception):
        type(build_evidence_export(golden_run()).manifest).model_validate({**body, "client_total": "1.00"})


def test_generated_contract_and_golden_capture_are_current():
    from scripts.build_evidence_export_contract import expected_outputs
    assert all(path.read_bytes() == payload for path, payload in expected_outputs().items())
