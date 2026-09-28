"""C28 version routing and compatibility rules for economics runs.

This module deliberately contains no economics formulas.  It decides which
version may execute, describes immutable historical snapshots, and validates
the evidence required before an operator can activate a route.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from calculation_contracts import Digest, StrictContractModel, semantic_digest


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "contracts" / "economics-runtime-migration-policy-v1.json"
LEGACY_VERSION = "legacy-economics-v1"
V2_VERSION = "economics-runtime-v2"
POLICY_VERSION = "economics-runtime-migration-policy-v1"


class EconomicsRuntimePolicyV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["economics-runtime-migration-policy-v1"]
    policy_version: Literal["economics-runtime-migration-policy-v1"]
    new_run_route: Literal["economics-runtime-v2"]
    legacy_version: Literal["legacy-economics-v1"]
    fallback_mode: Literal["FAIL_CLOSED"]
    activation_requires_approved_dual_run: Literal[True]
    historical_view_mode: Literal["SAVED_SNAPSHOT_ONLY"]
    legacy_replay_mode: Literal["SAVED_SNAPSHOT_ONLY"]
    rerun_mode: Literal["CREATE_NEW_RUN_ON_ACTIVE_ROUTE"]
    unknown_fte_basis_action: Literal["REQUIRE_EXPLICIT_GROSS_INPUT"]
    rollback_mode: Literal["ROUTE_CONFIGURATION_ONLY"]
    deprecated_routes: list[str]
    required_gap_refs: list[str]
    policy_digest: Digest

    @model_validator(mode="after")
    def validate_digest(self) -> "EconomicsRuntimePolicyV1":
        body = self.model_dump(mode="json")
        actual = body["policy_digest"]
        body["policy_digest"] = "sha256:" + "0" * 64
        if semantic_digest(body) != actual:
            raise ValueError("economics runtime policy digest mismatch")
        if self.required_gap_refs != sorted(set(self.required_gap_refs)):
            raise ValueError("required gap refs must be unique and sorted")
        return self


class EconomicsVersionMappingV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["analysis-run-economics-version-v1"] = (
        "analysis-run-economics-version-v1"
    )
    execution_route: Literal["LEGACY_V1", "ECONOMICS_V2"]
    economics_version: Literal["legacy-economics-v1", "economics-runtime-v2"]
    viewer_version: Literal["legacy-snapshot-viewer-v1", "commercial-scenarios-viewer-v2"]
    replay_mode: Literal["SAVED_SNAPSHOT_ONLY", "DETERMINISTIC_V2"]
    rerun_mode: Literal["CREATE_NEW_RUN_ON_ACTIVE_ROUTE"] = (
        "CREATE_NEW_RUN_ON_ACTIVE_ROUTE"
    )
    fte_basis_status: Literal[
        "NOT_APPLICABLE", "UNKNOWN_LEGACY_BASIS", "EXPLICIT_GROSS", "MISSING_GROSS"
    ]
    migration_notice: str


class EconomicsRouteDecisionV1(StrictContractModel):
    schema_version: Literal["economics-route-decision-v1"] = "economics-route-decision-v1"
    operation: Literal["NEW_RUN", "RERUN", "HISTORICAL_VIEW", "LEGACY_REPLAY"]
    route: Literal["LEGACY_V1", "ECONOMICS_V2", "SAVED_SNAPSHOT"]
    economics_version: Literal["legacy-economics-v1", "economics-runtime-v2"]
    creates_new_run: bool
    mutates_source_run: Literal[False] = False
    reason_code: str


class EconomicsV2ExecutionV1(StrictContractModel):
    """Server-owned result handed from the C13-C21 orchestrator to persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    result_snapshot: dict[str, Any]
    scenario_spec_snapshot: dict[str, Any]
    revision_id: str
    rules_version: str
    object_profile_version: str
    application_version: str
    diagnostics: dict[str, Any]

    @model_validator(mode="after")
    def validate_versions(self) -> "EconomicsV2ExecutionV1":
        versions = (
            self.result_snapshot.get("schema_version"),
            self.scenario_spec_snapshot.get("schema_version"),
        )
        if versions not in {
            ("commercial-scenarios-bundle-v2", "scenario-spec-v2"),
            ("commercial-scenarios-bundle-v3", "scenario-spec-v2"),
            ("economics-partial-result-v1", "scenario-spec-partial-v1"),
            ("economics-partial-result-v1", "scenario-spec-v2"),
        }:
            raise ValueError("v2 execution requires a matching result/scenario-spec version")
        return self


class EconomicsDifferenceV1(StrictContractModel):
    comparison_id: str
    classification: Literal["INTENDED_DIFFERENCE", "UNMATCHED_DIFFERENCE"]
    legacy_value: Any
    candidate_value: Any
    comparable_basis: bool
    numeric_delta: str | None
    gap_refs: list[Annotated[str, Field(pattern=r"^G[0-9]{2}$")]]
    reason: Annotated[str, Field(min_length=1)]


class EconomicsDualRunReportV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["economics-dual-run-report-v1"]
    policy_version: Literal["economics-runtime-migration-policy-v1"]
    policy_digest: Digest
    legacy_fixture_digest: Digest
    candidate_fixture_digest: Digest
    differences: list[EconomicsDifferenceV1]
    comparison_counts: dict[str, int]
    approval_status: Literal["APPROVED", "BLOCKED"]
    blocker_codes: list[str]
    report_digest: Digest

    @model_validator(mode="after")
    def validate_report(self) -> "EconomicsDualRunReportV1":
        intended = sum(x.classification == "INTENDED_DIFFERENCE" for x in self.differences)
        unmatched = sum(x.classification == "UNMATCHED_DIFFERENCE" for x in self.differences)
        if self.comparison_counts != {
            "INTENDED_DIFFERENCE": intended,
            "UNMATCHED_DIFFERENCE": unmatched,
        }:
            raise ValueError("economics comparison counts mismatch")
        approved = unmatched == 0 and not self.blocker_codes
        if (self.approval_status == "APPROVED") != approved:
            raise ValueError("economics approval status mismatch")
        for item in self.differences:
            if item.classification == "INTENDED_DIFFERENCE" and not item.gap_refs:
                raise ValueError("intended economics difference requires Gxx references")
            if not item.comparable_basis and item.numeric_delta is not None:
                raise ValueError("numeric delta is forbidden for incomparable bases")
        body = self.model_dump(mode="json")
        actual = body["report_digest"]
        body["report_digest"] = "sha256:" + "0" * 64
        if semantic_digest(body) != actual:
            raise ValueError("economics dual-run report digest mismatch")
        return self


class EconomicsMigrationError(ValueError):
    pass


def load_policy(path: Path = POLICY_PATH) -> EconomicsRuntimePolicyV1:
    try:
        return EconomicsRuntimePolicyV1.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EconomicsMigrationError("economics migration policy is unavailable") from exc


def historical_mapping(
    economics_version: str | None, input_snapshot: dict[str, Any]
) -> EconomicsVersionMappingV1:
    """Map a stored run without changing either its inputs or its result."""

    if economics_version == LEGACY_VERSION:
        unknown_basis = "fte_cost_rub" in input_snapshot
        return EconomicsVersionMappingV1(
            execution_route="LEGACY_V1",
            economics_version=LEGACY_VERSION,
            viewer_version="legacy-snapshot-viewer-v1",
            replay_mode="SAVED_SNAPSHOT_ONLY",
            fte_basis_status=("UNKNOWN_LEGACY_BASIS" if unknown_basis else "NOT_APPLICABLE"),
            migration_notice=(
                "Legacy result is preserved exactly. Re-run requires explicit monthly gross "
                "and payroll basis; fte_cost_rub is not converted."
                if unknown_basis
                else "Legacy result is preserved exactly; re-run creates a new v2 run."
            ),
        )
    if economics_version == V2_VERSION:
        def contains_gross(value: Any) -> bool:
            if isinstance(value, dict):
                return any(
                    (child is not None and (key in {"monthly_gross", "monthly_gross_salary"}
                    or key.endswith("_monthly_gross")))
                    or contains_gross(child)
                    for key, child in value.items()
                )
            if isinstance(value, list):
                return any(contains_gross(child) for child in value)
            return False

        economics_input = input_snapshot.get("economics", {})
        partial_basis_complete = (
            input_snapshot.get("schema_version") not in {"economics-run-input-v3", "economics-run-input-v4", "economics-run-input-v5", "economics-run-input-v6", "economics-run-input-v7"}
            or (
                isinstance(economics_input, dict)
                and economics_input.get("role_salaries_confirmed_as_monthly_gross") is True
                and (economics_input.get("control_monthly_gross") is not None
                     or economics_input.get("schema_version") in {"economics-explicit-inputs-v5", "economics-explicit-inputs-v6"})
                and (economics_input.get("technician_monthly_gross") is not None
                     or economics_input.get("schema_version") in {"economics-explicit-inputs-v5", "economics-explicit-inputs-v6"})
                and input_snapshot.get("capacity_role_salaries_complete") is True
            )
        )
        return EconomicsVersionMappingV1(
            execution_route="ECONOMICS_V2",
            economics_version=V2_VERSION,
            viewer_version="commercial-scenarios-viewer-v2",
            replay_mode="DETERMINISTIC_V2",
            fte_basis_status=("EXPLICIT_GROSS" if partial_basis_complete and contains_gross(input_snapshot) else "MISSING_GROSS"),
            migration_notice="This run already uses the versioned economics runtime.",
        )
    raise EconomicsMigrationError("unsupported economics version")


def route_operation(
    operation: Literal["NEW_RUN", "RERUN", "HISTORICAL_VIEW", "LEGACY_REPLAY"],
    *,
    source: EconomicsVersionMappingV1 | None = None,
    active_version: str | None = None,
) -> EconomicsRouteDecisionV1:
    if operation in {"HISTORICAL_VIEW", "LEGACY_REPLAY"}:
        if source is None:
            raise EconomicsMigrationError("historical operation requires source mapping")
        return EconomicsRouteDecisionV1(
            operation=operation,
            route="SAVED_SNAPSHOT",
            economics_version=source.economics_version,
            creates_new_run=False,
            reason_code=("IMMUTABLE_HISTORICAL_VIEW" if operation == "HISTORICAL_VIEW" else "EXPLICIT_LEGACY_REPLAY"),
        )
    if active_version != V2_VERSION:
        raise EconomicsMigrationError("active economics route is not approved")
    if operation == "RERUN" and source is None:
        raise EconomicsMigrationError("rerun requires source mapping")
    return EconomicsRouteDecisionV1(
        operation=operation,
        route="ECONOMICS_V2",
        economics_version=V2_VERSION,
        creates_new_run=True,
        reason_code=("ACTIVE_ROUTE_NEW_RUN" if operation == "NEW_RUN" else "ACTIVE_ROUTE_EXPLICIT_RERUN"),
    )


def verify_snapshot(snapshot: dict[str, Any] | None, stored_sha256: str | None) -> dict[str, Any]:
    if snapshot is None or stored_sha256 is None:
        raise EconomicsMigrationError("saved result snapshot is unavailable")
    actual = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if actual != stored_sha256:
        raise EconomicsMigrationError("saved result snapshot checksum mismatch")
    return snapshot


def validate_activation(
    report: EconomicsDualRunReportV1, policy: EconomicsRuntimePolicyV1 | None = None
) -> None:
    policy = policy or load_policy()
    if report.approval_status != "APPROVED":
        raise EconomicsMigrationError("economics route requires an approved dual-run report")
    if report.policy_version != policy.policy_version or report.policy_digest != policy.policy_digest:
        raise EconomicsMigrationError("economics approval uses another policy")
    covered = {ref for item in report.differences for ref in item.gap_refs}
    if set(policy.required_gap_refs) - covered:
        raise EconomicsMigrationError("economics approval does not explain every required Gxx gap")
