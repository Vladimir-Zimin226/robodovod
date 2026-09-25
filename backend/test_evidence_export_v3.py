from __future__ import annotations

import hashlib
import io
import json
import zipfile

import jsonschema
from pypdf import PdfReader

from calculation.evidence_export import (
    ENTRYPOINT_FILENAME, GUIDE_FILENAME, READABLE_REPORT_FILENAME,
    EvidenceExportManifestV3, EvidenceRunSnapshotV1, build_evidence_export_v2,
    build_evidence_export_v3,
)
from calculation.readable_report import build_readable_report
from scripts.build_evidence_export_contract import _checksum, golden_run
from scripts.build_evidence_export_contract import ROOT
from test_readable_report import _full_runs


def pdf_text(payload: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages)


def test_v3_readable_archive_is_bound_and_old_export_is_unchanged():
    run, linked = _full_runs()
    old = build_evidence_export_v2(run, linked)
    first = build_evidence_export_v3(run, linked)
    second = build_evidence_export_v3(run, linked)
    assert first.archive == second.archive
    assert first.manifest.schema_version == "calculation-evidence-export-manifest-v3"
    assert first.manifest.presentation_version == "readable-presentation-v2"
    schema = json.loads((ROOT / "contracts/calculation-evidence-export-manifest-v3.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(first.manifest.model_dump(mode="json"))
    assert first.files["Snapshot.json"] == old.files["Snapshot.json"]
    assert first.files["CashFlow.csv"] == old.files["CashFlow.csv"]
    assert first.files["C11_Snapshot.json"] == old.files["C11_Snapshot.json"]
    pdf, source_digest = build_readable_report(run, linked, presentation_version="readable-presentation-v2")
    assert first.files[READABLE_REPORT_FILENAME] == pdf
    assert first.manifest.source_snapshot_digests["result"] == source_digest
    readable = pdf_text(pdf)
    before_technical = readable.split("Технические подробности", 1)[0]
    assert run.run_id not in before_technical and linked.run_id not in before_technical
    assert "C11" not in before_technical and "C05" not in before_technical
    assert "Сохранённый расчёт" in before_technical
    assert "отбор коробок и упаковка не рассчитаны" in before_technical
    assert run.run_id in readable
    entry = first.files[ENTRYPOINT_FILENAME].decode()
    assert "отбор коробок и упаковка не рассчитаны" in entry
    guide = first.files[GUIDE_FILENAME].decode()
    assert "C11" not in entry.split("## Технические подробности")[0]
    assert run.run_id not in entry.split("## Технические подробности")[0]
    assert "Исходные данные" in guide and "Денежные потоки" in guide
    with zipfile.ZipFile(io.BytesIO(first.archive)) as archive:
        assert archive.testzip() is None
        assert EvidenceExportManifestV3.model_validate(json.loads(archive.read("manifest.json"))) == first.manifest
        for artifact in first.manifest.artifacts:
            assert artifact.sha256 == "sha256:" + hashlib.sha256(archive.read(artifact.filename)).hexdigest()


def test_v3_partial_report_names_missing_fields_and_actions():
    run, linked = _full_runs()
    raw = run.model_dump(mode="json")
    raw["result_snapshot"] = {
        "schema_version": "economics-partial-result-v1",
        "input_revision": linked.input_snapshot["input_revision"],
        "branches": {
            "purchase": {"status": "NOT_CALCULATED", "reason_code": "MISSING_INPUT", "required_fields": [
                "role_salaries_confirmed_as_monthly_gross", "organizer_price_currency_rub_confirmed",
                "initial_battery_in_robot_price_confirmed", "battery_replacements_in_service_confirmed",
            ]},
            "raas": {"status": "NOT_CALCULATED", "reason_code": "MISSING_INPUT", "required_fields": [
                "raas_vendor_scope_confirmed", "raas_monthly_per_robot_gross",
            ]},
        },
    }
    raw["checksums"]["result"] = _checksum(raw["result_snapshot"])
    package = build_evidence_export_v3(EvidenceRunSnapshotV1.model_validate(raw), linked)
    body = pdf_text(package.files[READABLE_REPORT_FILENAME]).split("Технические подробности", 1)[0]
    assert "месячный тариф аренды одного робота" in body
    assert "Введите тариф" in body
    for expected in ("подтверждение месячных зарплат до удержаний", "подтверждение валюты цены каталога",
                     "начальная батарея в цене робота", "замена батарей в сервисе", "состав тарифа аренды"):
        assert expected in body
    assert "Подтвердите" in body
    assert "raas_monthly_per_robot_gross" not in body
    assert "MISSING_INPUT" not in body
    assert "_confirmed" not in body
