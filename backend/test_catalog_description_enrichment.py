from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_description_enrichment import (
    PART1_NAME,
    PART2_NAME,
    build_overlay,
    parse_field_oriented,
    parse_page_oriented,
    verify_sources,
)
from catalog_repository import (
    CatalogApplicabilityDTO,
    CatalogEnrichmentDTO,
    CatalogModelDTO,
    CatalogPositionDTO,
    ProcurementOptionDTO,
)
from main import _discovery_position

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "Разобрать" / "Материалы от организаторов" / "Датасет"
BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"


def test_committed_overlay_has_complete_unique_position_contract():
    overlay = json.loads((BUNDLE / "catalog_description_overlay.json").read_text(encoding="utf-8"))
    report = json.loads((BUNDLE / "catalog_description_report.json").read_text(encoding="utf-8"))
    entries = overlay["entries"]

    assert len(entries) == 223
    assert len({entry["source_record_key"] for entry in entries}) == 223
    assert len({(entry["source_page"], entry["source_slot"]) for entry in entries}) == 223
    assert all(len(entry["media_sha256"]) == 64 for entry in entries)
    assert report["mapped"] == 223
    assert report["unresolved"] == 0
    assert report["description_status_counts"] == {
        "ENRICHED": 115,
        "REVIEW_REQUIRED": 108,
    }
    assert report["runtime_facts_created"] == 0


@pytest.mark.skipif(not (SOURCE_DIR / PART1_NAME).is_file(), reason="local restricted transcription is unavailable")
def test_strict_adapters_cover_both_transcription_formats():
    verify_sources(SOURCE_DIR)
    first = parse_page_oriented((SOURCE_DIR / PART1_NAME).read_text(encoding="utf-8-sig"))
    second = parse_field_oriented((SOURCE_DIR / PART2_NAME).read_text(encoding="utf-8-sig"))

    assert len(first) == 110
    assert len(second) == 113
    assert (first[0].source_page, first[0].source_slot) == (6, 1)
    assert (first[-1].source_page, first[-1].source_slot) == (46, 3)
    assert (second[0].source_page, second[0].source_slot) == (47, 1)
    assert (second[-1].source_page, second[-1].source_slot) == (91, 3)
    assert sum(card.type_raw is None for card in second) == 14
    assert sum(card.source_url is not None for card in first) == 54


@pytest.mark.skipif(not (SOURCE_DIR / PART1_NAME).is_file(), reason="local restricted transcription is unavailable")
def test_overlay_is_deterministic_complete_and_preserves_conflicts():
    first, report = build_overlay(SOURCE_DIR, BUNDLE)
    second, second_report = build_overlay(SOURCE_DIR, BUNDLE)

    assert first == second
    assert report == second_report
    assert report["mapped"] == 223
    assert report["unresolved"] == 0
    assert report["description_status_counts"] == {
        "ENRICHED": 115,
        "REVIEW_REQUIRED": 108,
    }
    assert report["runtime_facts_created"] == 0
    assert report["missing_type_by_adapter"]["field-oriented-v1"] == 14
    assert len(report["anchor_conflicts"]) == 1
    assert report["anchor_conflicts"][0]["source_row_number"] == 210
    committed = json.loads((BUNDLE / "catalog_description_overlay.json").read_text(encoding="utf-8"))
    assert committed == first


def test_api_uses_enrichment_only_for_previously_empty_description():
    model = CatalogModelDTO(
        id="model", source_namespace="test", source_record_key="model", organizer_id=None,
        manufacturer="Org", name="Robot", system_family="BRS", type_code="AMR",
        subtype_code=None, maturity_status=None, trl=None, description=None,
        attributes={}, facts=(), applicability=(), procurement_options=(),
        runtime_robot=None, runtime_blockers=("blocked",),
    )
    enrichment = CatalogEnrichmentDTO(
        description_raw="New", description_normalized="New", existing_description=None,
        description_status="ENRICHED", mapping_status="VERIFIED", source_page=6,
        source_slot=1, transcript_sha256="a" * 64, media_sha256="b" * 64,
        adapter="page-oriented-v1", fields={"trl": 8}, limitation="unknown OCR",
    )
    position = CatalogPositionDTO(
        id="position", source_record_key="row", source_row_number=2, model=model,
        applicability=CatalogApplicabilityDTO(None, None, None, None),
        procurement_option=ProcurementOptionDTO("PURCHASE", None, None, "UNKNOWN", "UNKNOWN", (), (), None),
        media=None, runtime_robot=None, runtime_blockers=("blocked",), enrichment=enrichment,
    )

    payload = _discovery_position(position, "catalog")

    assert payload["description"] == "New"
    assert payload["enrichment"]["fields"]["trl"] == 8
    assert payload["facts"] == []

    conflict_model = model.__class__(**{**model.__dict__, "description": "Existing"})
    conflict = enrichment.__class__(**{
        **enrichment.__dict__,
        "existing_description": "Existing",
        "description_status": "REVIEW_REQUIRED",
    })
    conflict_position = position.__class__(**{**position.__dict__, "model": conflict_model, "enrichment": conflict})
    assert _discovery_position(conflict_position, "catalog")["description"] == "Existing"
