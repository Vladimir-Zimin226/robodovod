from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import catalog_capacity_rollout
from calculation_contracts import semantic_digest
from catalog_activation import _expected_content_sha
from catalog_capacity_rollout import (
    CapacityDualRunReportV1,
    CapacityRolloutPolicyError,
    compare_capacity_snapshots,
    load_capacity_source_policy,
    validate_capacity_approval,
    validate_capacity_source,
)
from catalog_import_contract import load_catalog_bundle
from storage_models import CatalogActivation
from test_capacity_analysis_service import snapshot as capacity_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_generated_policy_and_golden_report_are_current_and_exact():
    from scripts.build_capacity_rollout_contracts import expected_outputs

    assert all(path.read_bytes() == payload for path, payload in expected_outputs().items())
    policy = load_capacity_source_policy()
    assert policy.expected_counts == {
        "models": 187,
        "positions": 223,
        "calculation_pool_models": 21,
        "calculation_pool_positions": 24,
        "calculation_ready_models": 6,
        "calculation_ready_positions": 6,
        "calculation_ready_with_assumptions_models": 15,
        "calculation_ready_with_assumptions_positions": 18,
        "deployment_ready_models": 0,
        "deployment_ready_positions": 0,
        "forbidden_family_models": 0,
    }
    assert len(policy.model_ids) == 21
    assert len(policy.position_source_keys) == 24
    assert policy.forbidden_system_families == ["BAS"]
    bundle = load_catalog_bundle(ROOT / "data/import/organizer-catalog-v4")
    assert policy.catalog_content_digest == (
        "sha256:" + _expected_content_sha(bundle.bundle_sha256)
    )
    report = CapacityDualRunReportV1.model_validate_json(
        (ROOT / "contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json").read_text(encoding="utf-8")
    )
    assert report.approval_status == "APPROVED"
    assert report.comparison_counts["INTENDED_DIFFERENCE"] == 2
    assert report.comparison_counts["UNMATCHED_DIFFERENCE"] == 0
    assert all(item.gap_refs == ["G48"] for item in report.comparisons)
    assert all(item.decision_refs == ["K29"] for item in report.comparisons)


def test_policy_rejects_partial_or_fictitious_pool_and_has_no_fallback():
    with pytest.raises(CapacityRolloutPolicyError, match="not approved|counts"):
        validate_capacity_source(capacity_snapshot())


def test_capacity_dual_run_blocks_unmatched_and_requires_gxx_kxx_for_intended_changes():
    reference = capacity_snapshot()
    candidate = capacity_snapshot()
    same = compare_capacity_snapshots(reference, candidate)
    assert same.approval_status == "BLOCKED"
    assert same.comparison_counts["UNMATCHED_DIFFERENCE"] == 0
    assert same.blocker_codes == ["CANDIDATE_POLICY_MISMATCH"]

    changed_model = candidate.models[0]
    changed = type(candidate)(
        version=candidate.version,
        models=(type(changed_model)(**{**changed_model.__dict__, "organizer_id": "changed-model"}),),
        positions=candidate.positions,
    )
    blocked = compare_capacity_snapshots(reference, changed)
    assert blocked.comparison_counts["UNMATCHED_DIFFERENCE"] > 0
    assert "UNMATCHED_DIFFERENCE" in blocked.blocker_codes
    intended = compare_capacity_snapshots(
        reference,
        changed,
        intended_differences={
            "membership.models": {
                "gap_refs": ["G48"],
                "decision_refs": ["K29"],
                "reason": "explicit test-only identity delta",
            }
        },
    )
    item = next(value for value in intended.comparisons if value.comparison_id == "membership.models")
    assert item.classification == "INTENDED_DIFFERENCE"
    assert item.gap_refs == ["G48"] and item.decision_refs == ["K29"]


def test_unknown_contract_version_and_extra_fields_are_rejected():
    raw = json.loads((ROOT / "contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        CapacityDualRunReportV1.model_validate({**raw, "schema_version": "capacity-catalog-dual-run-report-v2"})
    with pytest.raises(ValidationError):
        CapacityDualRunReportV1.model_validate({**raw, "client_approval": True})


def test_approval_rejects_source_digests_not_bound_to_policy(monkeypatch):
    raw = json.loads(
        (ROOT / "contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )
    raw["source_digests"]["capacity_runtime"] = "sha256:" + "0" * 64
    raw["report_digest"] = "sha256:" + "0" * 64
    raw["report_digest"] = semantic_digest(raw)
    report = CapacityDualRunReportV1.model_validate(raw)
    monkeypatch.setattr(
        catalog_capacity_rollout,
        "validate_capacity_source",
        lambda candidate, policy: report.candidate_summary,
    )
    candidate = capacity_snapshot()
    candidate = replace(
        candidate,
        version=replace(candidate.version, code="organizer-catalog-v4"),
    )
    with pytest.raises(CapacityRolloutPolicyError, match="source digests"):
        validate_capacity_approval(report, candidate)


def test_activation_model_persists_policy_report_and_rollback_binding():
    columns = CatalogActivation.__table__.columns
    assert {
        "rollout_policy_version", "approval_report_sha256", "rollback_mode",
        "rollback_catalog_version_id",
    }.issubset(columns.keys())
    constraints = {item.name: str(item.sqltext) for item in CatalogActivation.__table__.constraints if item.name}
    assert "slot = 'capacity'" in constraints["ck_catalog_activations_capacity_approval"]


def test_capacity_migration_never_deletes_activation_history_implicitly():
    migration = (
        ROOT / "backend/alembic/versions/0009_capacity_catalog_rollout.py"
    ).read_text(encoding="utf-8")
    assert "DELETE FROM catalog_activations" not in migration
    assert "cannot downgrade while capacity activation history exists" in migration
