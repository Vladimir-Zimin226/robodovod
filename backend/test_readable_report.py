from __future__ import annotations

import io

from pypdf import PdfReader

from calculation.evidence_export import EvidenceRunSnapshotV1
from calculation.readable_report import build_readable_report
from scripts.build_evidence_export_contract import _checksum, golden_run


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)


def test_standalone_russian_pdf_has_six_snapshot_scenarios_and_source_digests():
    raw = golden_run().model_dump(mode="json")
    raw["versions"]["application"] = "production-economics-orchestrator-v2"
    raw["diagnostics"]["constraint_eligibility"] = "NEEDS_VALIDATION"
    raw["input_snapshot"]["economics"] = {"discount_rate": "0.15", "horizon_years": 5}
    raw["checksums"]["input"] = _checksum(raw["input_snapshot"])
    scenarios = []
    for acquisition in ("PURCHASE", "RAAS"):
        for uncertainty in ("PESSIMISTIC", "BASE", "OPTIMISTIC"):
            scenarios.append({
                "scenario_id": f"scenario.{acquisition.lower()}.{uncertainty.lower()}",
                "acquisition": acquisition, "uncertainty": uncertainty,
                "procurement": {"procurement_status": "UNVERIFIED"},
                "recommendation": {"status": "ALTERNATIVE"},
                "financial": {
                    "status": "COMPLETE", "source_digest": "sha256:" + "a" * 64,
                    "npv_project": {"value": "12345.67"}, "simple_payback": {"value": "2.50"},
                    "annual_ledgers": [{"year": 1, "primary_cf_base": "-100.00", "primary_cf_scenario": "-70.00", "differential_cf": "30.00"}],
                },
            })
    raw["result_snapshot"] = {"schema_version": "commercial-scenarios-bundle-v2", "scenarios": scenarios}
    raw["checksums"]["result"] = _checksum(raw["result_snapshot"])
    run = EvidenceRunSnapshotV1.model_validate(raw)
    first, source = build_readable_report(run)
    second, _ = build_readable_report(run)
    assert first == second and first.startswith(b"%PDF-")
    text = _text(first)
    assert text.count("NPV: 12345.67") == 6
    assert "РОБОДОВОД" in text and "C05: NEEDS_VALIDATION" in text
    assert "Закупка: UNVERIFIED" in text and "ALTERNATIVE" in text
    assert "Год 1: база -100.00 ₽; сценарий -70.00 ₽; разница 30.00 ₽." in text
    assert source in text and "Snapshot.json" in text
    assert "Источники и проверка" in text


def test_historical_and_partial_runs_keep_limits_and_unknown_basis_visible():
    raw = golden_run().model_dump(mode="json")
    raw["versions"]["application"] = "production-economics-orchestrator-v1"
    raw["input_snapshot"]["fte_cost_rub"] = "100000"
    raw["checksums"]["input"] = _checksum(raw["input_snapshot"])
    pdf, _ = build_readable_report(EvidenceRunSnapshotV1.model_validate(raw))
    text = _text(pdf)
    assert "C16 v1" in text
    assert "база неизвестна" in text
    assert "Сценарии и финансовые показатели: NOT_AVAILABLE" not in text
    assert "Денежный поток: NOT_AVAILABLE" in text
