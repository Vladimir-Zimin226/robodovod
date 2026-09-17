from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_catalog_description_review.py"
BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"


def _module():
    spec = importlib.util.spec_from_file_location("build_catalog_description_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_artifacts_resolve_all_approved_case_preservation_patterns():
    module = _module()
    rows = module.load_review_rows(BUNDLE)
    decisions = module.auto_review_decisions(rows)
    remaining = module.remaining_review_rows(rows)
    report = module.render_report(remaining)
    decision_document = module.render_decisions(decisions)

    assert len(rows) == 108
    assert len(decisions) == 108
    assert remaining == []
    assert "Реально осталось проверить: 0" in report
    assert "НЕ ВЫБРАНО" not in report
    assert decision_document.count('"decision":"KEEP_EXISTING_DESCRIPTION"') == 108
    assert decision_document.count('"review_status":"RESOLVED"') == 108
    assert decision_document.count('"case_relation":"PDF_SUBSET_OF_CASE"') == 3
    truncated_pdf_decisions = {
        row["source_record_key"]: row["name"]
        for row in decisions
        if row["case_relation"] == "PDF_SUBSET_OF_CASE"
    }
    assert truncated_pdf_decisions == {
        "catalog-v4-row-0009": "AMR 800 (грузоподъемность до 800 кг)",
        "catalog-v4-row-0010": "AMR 1500 (грузоподъемность до 1 500 кг)",
        "catalog-v4-row-0188": "EVOCARGO N1",
    }
    assert '"decision_policy":"user-approved-case-preservation-v3"' in (
        decision_document
    )
    assert decision_document.count('"case_relation":"CASE_EXACT"') == 94
    assert decision_document.count(
        '"case_relation":"PDF_SCENARIO_PLUS_CASE"'
    ) == 5
    assert decision_document.count(
        '"case_relation":"PDF_REORDERS_CASE_ITEMS"'
    ) == 3
    assert decision_document.count(
        '"case_relation":"PDF_COLLAPSED_CASE_LIST"'
    ) == 3
    assert "KEEP_EXISTING_DESCRIPTION" in report
    assert "USE_TRANSCRIPT_DESCRIPTION" in report
