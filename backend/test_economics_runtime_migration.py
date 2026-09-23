from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from economics_runtime_migration import (
    EconomicsDualRunReportV1,
    EconomicsMigrationError,
    EconomicsRuntimePolicyV1,
    historical_mapping,
    load_policy,
    route_operation,
    validate_activation,
    verify_snapshot,
)
from persistence_models import AnalysisRunEconomicsVersion, EconomicsRouteActivation
from persistence_api import EconomicsV2CreateRequest


ROOT = Path(__file__).resolve().parents[1]


def _report() -> EconomicsDualRunReportV1:
    return EconomicsDualRunReportV1.model_validate_json(
        (ROOT / "contracts/fixtures/economics-dual-run-report-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )


def test_policy_and_old_new_goldens_are_digest_bound_and_approved():
    policy = load_policy()
    report = _report()
    assert report.approval_status == "APPROVED"
    assert report.legacy_fixture_digest == "sha256:" + hashlib.sha256(
        (ROOT / "backend/fixtures/economics-warehouse-v2.json").read_bytes()
    ).hexdigest()
    assert report.candidate_fixture_digest == "sha256:" + hashlib.sha256(
        (ROOT / "frontend/tests/fixtures/commercial-scenarios-v2.golden.json").read_bytes()
    ).hexdigest()
    assert {ref for item in report.differences for ref in item.gap_refs} == set(
        policy.required_gap_refs
    )
    assert all(not item.comparable_basis and item.numeric_delta is None for item in report.differences)
    validate_activation(report, policy)
    for name, instance in (
        ("economics-runtime-migration-policy-v1.schema.json", policy.model_dump(mode="json")),
        ("economics-dual-run-report-v1.schema.json", report.model_dump(mode="json")),
        ("analysis-run-economics-version-v1.schema.json", historical_mapping(
            "legacy-economics-v1", {"fte_cost_rub": 1}
        ).model_dump(mode="json")),
    ):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(instance)
        assert set(instance) <= set(schema["properties"])


def test_invalid_approval_and_unknown_contract_fail_closed():
    raw = json.loads(
        (ROOT / "contracts/fixtures/economics-dual-run-report-v1.golden.json").read_text(
            encoding="utf-8"
        )
    )
    raw["approval_status"] = "BLOCKED"
    with pytest.raises(ValidationError):
        EconomicsDualRunReportV1.model_validate(raw)
    policy = json.loads(
        (ROOT / "contracts/economics-runtime-migration-policy-v1.json").read_text(
            encoding="utf-8"
        )
    )
    policy["client_override"] = True
    with pytest.raises(ValidationError):
        EconomicsRuntimePolicyV1.model_validate(policy)
    with pytest.raises(EconomicsMigrationError, match="approved"):
        validate_activation(_report().model_copy(update={"approval_status": "BLOCKED"}))
    with pytest.raises(EconomicsMigrationError, match="not approved"):
        route_operation("NEW_RUN", active_version="legacy-economics-v1")


def test_historical_mapping_never_converts_legacy_fte_and_routes_replay_to_snapshot():
    source = {"fte_cost_rub": 1800000, "fte_count": 4}
    unchanged = json.loads(json.dumps(source))
    mapping = historical_mapping("legacy-economics-v1", source)
    assert source == unchanged
    assert mapping.fte_basis_status == "UNKNOWN_LEGACY_BASIS"
    assert "explicit monthly gross" in mapping.migration_notice
    view = route_operation("HISTORICAL_VIEW", source=mapping)
    replay = route_operation("LEGACY_REPLAY", source=mapping)
    assert view.route == replay.route == "SAVED_SNAPSHOT"
    assert not view.creates_new_run and not replay.mutates_source_run
    rerun = route_operation("RERUN", source=mapping, active_version="economics-runtime-v2")
    assert rerun.route == "ECONOMICS_V2" and rerun.creates_new_run

    v2 = historical_mapping(
        "economics-runtime-v2",
        {"roles": [{"monthly_gross_salary": {"status": "KNOWN", "value": "100000"}}]},
    )
    assert v2.fte_basis_status == "EXPLICIT_GROSS"


def test_v2_new_run_contract_rejects_legacy_fte_cost_at_any_depth():
    with pytest.raises(ValidationError, match="fte_cost_rub"):
        EconomicsV2CreateRequest.model_validate(
            {
                "scenario_id": "00000000-0000-0000-0000-000000000001",
                "input": {"legacy": {"fte_cost_rub": 1200000}},
            }
        )


def test_snapshot_replay_is_deterministic_and_detects_tampering():
    snapshot = {"b": [2, 1], "a": "same"}
    digest = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert verify_snapshot(snapshot, digest) is snapshot
    with pytest.raises(EconomicsMigrationError, match="checksum"):
        verify_snapshot({**snapshot, "a": "changed"}, digest)


def test_additive_models_and_migration_preserve_history_and_have_no_activation_seed():
    assert AnalysisRunEconomicsVersion.__table__.primary_key.columns.keys() == ["run_id"]
    assert "approval_report_sha256" in EconomicsRouteActivation.__table__.columns
    migration = (ROOT / "backend/alembic/versions/0010_economics_runtime_migration.py").read_text(
        encoding="utf-8"
    )
    assert "UPDATE analysis_runs" not in migration
    assert "DELETE FROM analysis_runs" not in migration
    assert "Deliberately no activation seed" in migration
    assert "cannot downgrade while economics rollout history exists" in migration


def test_api_contract_exposes_v2_route_and_marks_legacy_mutations_deprecated():
    import main

    paths = main.app.openapi()["paths"]
    assert paths["/api/projects/{project_id}/analysis-runs"]["post"]["deprecated"] is True
    assert paths["/api/projects/{project_id}/analysis-runs/{run_id}/rerun"]["post"]["deprecated"] is True
    assert "/api/v2/projects/{project_id}/economics-runs" in paths
    assert "/api/projects/{project_id}/analysis-runs/{run_id}/legacy-replay" in paths
