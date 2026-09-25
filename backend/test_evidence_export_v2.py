from __future__ import annotations

import hashlib
import io
import json
import zipfile

import jsonschema
import pytest
from pypdf import PdfReader

from calculation.evidence_export import (
    ENTRYPOINT_FILENAME,
    GUIDE_FILENAME,
    READABLE_REPORT_FILENAME,
    TECHNICAL_REPORT_FILENAME,
    EvidenceExportIntegrityError,
    EvidenceExportManifestV2,
    EvidenceRunSnapshotV1,
    build_evidence_export_v2,
)
from calculation.readable_report import build_readable_report
from scripts.build_evidence_export_contract import ROOT, _checksum, golden_run
from test_readable_report import _full_runs


def _pdf_text(payload: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages)


def test_v2_archive_starts_with_readable_navigation_and_verifies_every_member(tmp_path):
    first = build_evidence_export_v2(golden_run())
    second = build_evidence_export_v2(golden_run())
    assert first.archive == second.archive
    assert first.manifest == second.manifest
    assert first.manifest.schema_version == "calculation-evidence-export-manifest-v2"
    assert first.manifest.entrypoint_filename == ENTRYPOINT_FILENAME
    assert first.manifest.report_filename == READABLE_REPORT_FILENAME
    assert first.files["CashFlow.csv"] == (
        ROOT / "contracts/fixtures/calculation-evidence-export-v1.cashflow.golden.csv"
    ).read_bytes()
    with zipfile.ZipFile(io.BytesIO(first.archive)) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {item.filename for item in first.manifest.artifacts} | {"manifest.json"}
        assert len(archive.namelist()) == len(set(archive.namelist()))
        for artifact in first.manifest.artifacts:
            payload = archive.read(artifact.filename)
            assert artifact.byte_size == len(payload)
            assert artifact.sha256 == "sha256:" + hashlib.sha256(payload).hexdigest()
        manifest = EvidenceExportManifestV2.model_validate(json.loads(archive.read("manifest.json")))
        assert manifest == first.manifest
        archive.extractall(tmp_path)
    assert (tmp_path / ENTRYPOINT_FILENAME).is_file()
    assert (tmp_path / READABLE_REPORT_FILENAME).is_file()
    assert (tmp_path / GUIDE_FILENAME).is_file()
    assert (tmp_path / TECHNICAL_REPORT_FILENAME).is_file()
    entry = first.files[ENTRYPOINT_FILENAME].decode("utf-8")
    guide = first.files[GUIDE_FILENAME].decode("utf-8")
    assert "отчёт №" in entry.lower() and golden_run().run_id in entry
    assert first.manifest.source_snapshot_digests["result"] in entry
    assert "manifest.json" in entry and "Snapshot.json" in entry
    assert "NOT_AVAILABLE" in entry and "C23" in entry
    assert "не является подтверждением" in entry
    for name in ("Inputs", "Selection", "Scenarios", "CashFlow", "Sensitivity",
                 "Sources", "Trace", "Simulation", "Versions", "Snapshot.json"):
        assert name in guide
    assert "Что проверяет" in guide and "Что смотреть" in guide and "Откуда взято" in guide
    readable = _pdf_text(first.files[READABLE_REPORT_FILENAME])
    assert "РОБОДОВОД" in readable and golden_run().run_id in readable
    assert "ROBOMERA CALCULATION EVIDENCE EXPORT" not in readable
    assert "ROBOMERA CALCULATION EVIDENCE EXPORT" in _pdf_text(first.files[TECHNICAL_REPORT_FILENAME])


def test_linked_capacity_pdf_matches_standalone_and_source_binding_is_explicit():
    run, linked = _full_runs()
    package = build_evidence_export_v2(run, linked)
    standalone, source_digest = build_readable_report(run, linked)
    assert package.files[READABLE_REPORT_FILENAME] == standalone
    assert package.manifest.source_snapshot_digests["result"] == source_digest
    assert package.manifest.linked_capacity_run_id == linked.run_id
    assert package.manifest.linked_capacity_snapshot_digests["result"] == "sha256:" + linked.checksums["result"]
    linked_snapshot = json.loads(package.files["C11_Snapshot.json"])
    assert linked_snapshot["run_id"] == linked.run_id
    assert linked_snapshot["source_snapshot_digests"]["result"] == package.manifest.linked_capacity_snapshot_digests["result"]
    assert "1 000 паллет/день" in _pdf_text(standalone)
    raw = linked.model_dump(mode="json")
    raw["result_snapshot"]["capacity"]["value"]["selected_fleet"] = 999
    with pytest.raises(EvidenceExportIntegrityError):
        build_evidence_export_v2(run, EvidenceRunSnapshotV1.model_validate(raw))


def test_missing_sections_and_partial_finance_are_explained_without_false_npv():
    source = golden_run().model_dump(mode="json")
    source["run_kind"] = "CAPACITY_ANALYSIS"
    source["versions"]["economics"] = None
    source["result_snapshot"] = {"schema_version": "capacity-analysis-response-v2", "capacity": {"required": "42.00"}}
    source["scenario_spec_snapshot"] = None
    source["trace_snapshot"] = {"schema_version": "calculation-trace-v1", "results": []}
    source["checksums"]["result"] = _checksum(source["result_snapshot"])
    source["checksums"]["scenario_spec"] = None
    source["checksums"]["trace"] = _checksum(source["trace_snapshot"])
    package = build_evidence_export_v2(EvidenceRunSnapshotV1.model_validate(source))
    sections = {item.name: item for item in package.manifest.sections}
    assert sections["CashFlow"].status == "NOT_AVAILABLE"
    assert sections["CashFlow"].record_count == 0
    assert "CashFlow" in package.files[ENTRYPOINT_FILENAME].decode("utf-8")
    assert "нет данных для оценки" in _pdf_text(package.files[READABLE_REPORT_FILENAME])


def test_partial_zip_keeps_exact_saved_values_and_identifies_result_type():
    run, linked = _full_runs()
    raw = run.model_dump(mode="json")
    raw["result_snapshot"] = {
        "schema_version": "economics-partial-result-v1", "input_revision": "revision.report.v1",
        "branches": {"purchase": {"status": "CALCULATED"}, "raas": {"status": "NOT_CALCULATED", "required_fields": ["raas_monthly_per_robot_gross"]}},
        "scenarios": [{"acquisition": "PURCHASE", "uncertainty": "BASE", "financial": {"status": "COMPLETE", "npv_project": {"status": "COMPLETE", "value": "12345.678901", "unit": "RUB"}}}],
    }
    raw["checksums"]["result"] = _checksum(raw["result_snapshot"])
    package = build_evidence_export_v2(EvidenceRunSnapshotV1.model_validate(raw), linked)
    assert "Вид результата: Частичная экономика" in package.files[ENTRYPOINT_FILENAME].decode("utf-8")
    assert "12 345,68 ₽" in _pdf_text(package.files[READABLE_REPORT_FILENAME])
    assert json.loads(package.files["Snapshot.json"])["result_snapshot"]["scenarios"][0]["financial"]["npv_project"]["value"] == "12345.678901"
    assert package.manifest.linked_capacity_run_id == linked.run_id


def test_v2_contract_and_golden_are_current_and_v1_is_unchanged():
    from scripts.build_evidence_export_contract import expected_outputs

    assert all(path.read_bytes() == payload for path, payload in expected_outputs().items())
    schema = json.loads((ROOT / "contracts/calculation-evidence-export-manifest-v2.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(build_evidence_export_v2(golden_run()).manifest.model_dump(mode="json"))
