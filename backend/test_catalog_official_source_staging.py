from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_catalog_official_source_staging import (  # noqa: E402
    POST_REPORT,
    POST_SUMMARY,
    STAGING,
    STAGING_SCHEMA,
    STAGING_SUMMARY,
    StagingOverlay,
    build_staging,
    post_summary,
    project_eligibility,
    schema_bytes,
    staging_bytes,
    staging_summary,
)
from catalog_runtime_eligibility import AuditReport, report_bytes  # noqa: E402


def test_staging_partitions_all_research_targets_and_preserves_review_limits():
    staging = build_staging()

    assert staging.counts.model_dump() == {
        "accepted_fields": 131,
        "matching_usable_fields": 129,
        "review_only_fields": 2,
        "deferred_fields": 7,
        "remains_missing_fields": 318,
        "target_fields": 456,
        "models_with_accepted_facts": 26,
    }
    assert [(row.organizer_id, row.field_path) for row in staging.facts] == sorted(
        (row.organizer_id, row.field_path) for row in staging.facts
    )
    assert {row.decision_id for row in staging.facts if not row.usable_for_matching} == {
        "R005",
        "R013",
    }
    assert {row.decision for row in staging.deferred} == {
        "DEFER",
        "DEFER_IDENTITY",
    }
    assert staging.policy.writes_database is False
    assert staging.policy.activates_catalog_or_runtime is False


def test_post_enrichment_projection_has_exact_catalog_coverage_and_counts():
    report = project_eligibility(build_staging())

    assert report.counts == {"models": 187, "positions": 223}
    assert report.model_status_counts == {
        "RUNTIME_READY": 0,
        "NEEDS_FACTS": 37,
        "CONFLICT_REVIEW": 3,
        "UNSUPPORTED_CAPACITY_PROFILE": 143,
        "NOT_EQUIPMENT": 4,
    }
    assert report.position_status_counts == {
        "RUNTIME_READY": 0,
        "NEEDS_FACTS": 39,
        "CONFLICT_REVIEW": 4,
        "UNSUPPORTED_CAPACITY_PROFILE": 176,
        "NOT_EQUIPMENT": 4,
    }
    assert report.model_coverage.model_dump() == {
        "required_field_checks": 509,
        "matching_safe_field_checks": 184,
        "local_candidate_field_checks": 2,
        "conflict_field_checks": 6,
        "missing_field_checks": 317,
        "matching_safe_percent": 36.15,
    }
    assert report.position_coverage.model_dump() == {
        "required_field_checks": 548,
        "matching_safe_field_checks": 210,
        "local_candidate_field_checks": 3,
        "conflict_field_checks": 6,
        "missing_field_checks": 329,
        "matching_safe_percent": 38.32,
    }
    assert [row.id for row in report.models] == sorted(row.id for row in report.models)
    assert [row.source_row_number for row in report.positions] == list(range(2, 225))
    AuditReport.model_validate(report.model_dump(mode="json"))


def test_staging_and_projection_artifacts_are_schema_valid_and_idempotent():
    staging = build_staging()
    report = project_eligibility(staging)

    assert STAGING.read_bytes() == staging_bytes(staging)
    assert STAGING_SCHEMA.read_bytes() == schema_bytes(StagingOverlay)
    assert STAGING_SUMMARY.read_text(encoding="utf-8") == staging_summary(staging)
    assert POST_REPORT.read_bytes() == report_bytes(report)
    assert POST_SUMMARY.read_text(encoding="utf-8") == post_summary(report)
    StagingOverlay.model_validate(json.loads(STAGING.read_text(encoding="utf-8")))
    assert staging_bytes(build_staging()) == staging_bytes(build_staging())
    assert report_bytes(project_eligibility(build_staging())) == report_bytes(
        project_eligibility(build_staging())
    )
