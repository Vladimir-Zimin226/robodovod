from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_runtime_eligibility import (
    AuditError,
    AuditReport,
    DEFAULT_BUNDLE,
    DEFAULT_CONTRACT,
    DEFAULT_CONTRACT_SCHEMA,
    DEFAULT_REPORT,
    DEFAULT_REPORT_SCHEMA,
    DEFAULT_SUMMARY,
    RuntimeEligibilityContract,
    build_report,
    load_contract,
    report_bytes,
    schema_bytes,
    summary_text,
)


def test_contract_and_report_validate_with_exact_counts_and_ordering():
    contract = load_contract()
    report = build_report()

    assert contract.schema_version == "runtime-eligibility-contract-v1"
    assert report.counts == {"models": 187, "positions": 223}
    assert report.model_status_counts == {
        "RUNTIME_READY": 0,
        "NEEDS_FACTS": 36,
        "CONFLICT_REVIEW": 5,
        "UNSUPPORTED_CAPACITY_PROFILE": 142,
        "NOT_EQUIPMENT": 4,
    }
    assert report.position_status_counts == {
        "RUNTIME_READY": 0,
        "NEEDS_FACTS": 38,
        "CONFLICT_REVIEW": 6,
        "UNSUPPORTED_CAPACITY_PROFILE": 175,
        "NOT_EQUIPMENT": 4,
    }
    assert [item.id for item in report.models] == sorted(
        item.id for item in report.models
    )
    assert [item.source_row_number for item in report.positions] == list(
        range(2, 225)
    )
    assert len({item.id for item in report.positions}) == 223
    assert len({item.model_id for item in report.positions}) == 187
    AuditReport.model_validate(report.model_dump(mode="json"))


def test_every_item_exposes_local_fields_sources_gaps_and_recommendation():
    report = build_report()

    assert all(item.source_files for item in report.models)
    assert all(item.source_files for item in report.positions)
    assert all(item.recommendation for item in (*report.models, *report.positions))
    assert all(
        assessment.sources
        for item in report.models
        for assessment in item.present_fields
        if assessment.availability != "MISSING"
    )
    unsupported_with_specs = next(
        item
        for item in report.models
        if item.status == "UNSUPPORTED_CAPACITY_PROFILE" and item.present_fields
    )
    assert unsupported_with_specs.required_fields == []
    assert unsupported_with_specs.missing_fields == []
    assert report.model_coverage.required_field_checks == 509
    assert report.model_coverage.matching_safe_field_checks == 58
    assert report.position_coverage.required_field_checks == 548


def test_generated_artifacts_are_idempotent_and_schema_is_committed():
    report = build_report()

    assert DEFAULT_REPORT.read_bytes() == report_bytes(report)
    assert DEFAULT_SUMMARY.read_text(encoding="utf-8") == summary_text(report)
    assert DEFAULT_CONTRACT_SCHEMA.read_bytes() == schema_bytes(
        RuntimeEligibilityContract
    )
    assert DEFAULT_REPORT_SCHEMA.read_bytes() == schema_bytes(AuditReport)
    assert report_bytes(build_report()) == report_bytes(build_report())


def test_description_overlay_is_accounted_for_but_never_runtime_eligible():
    report = build_report()
    description_input = next(
        item
        for item in report.inputs
        if item.path.endswith("catalog_description_overlay.json")
    )

    assert description_input.runtime_eligible is False
    assert any("presentation-only" in value for value in report.exclusions)


def test_contract_rejects_unknown_or_ambiguous_class_mapping(tmp_path: Path):
    contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    contract["equipment_classes"][1]["selectors"] = contract["equipment_classes"][0][
        "selectors"
    ]
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(AuditError, match="ambiguous equipment class"):
        build_report(DEFAULT_BUNDLE, path)


def test_contract_schema_rejects_extra_fields(tmp_path: Path):
    contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    contract["unexpected"] = True
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(AuditError, match="contract validation failed"):
        load_contract(path)
