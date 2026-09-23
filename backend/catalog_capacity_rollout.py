"""C27 contracts and fail-closed gates for the capacity catalog rollout."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from calculation_contracts import Digest, StrictContractModel, semantic_digest
from catalog_repository import CatalogSnapshotDTO


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "contracts" / "capacity-source-activation-policy-v1.json"
POLICY_VERSION = "capacity-runtime-rollout-policy-v1"


class CapacitySourceActivationPolicyV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["capacity-source-activation-policy-v1"]
    policy_version: Literal["capacity-runtime-rollout-policy-v1"]
    catalog_code: Literal["organizer-catalog-v4"]
    capacity_runtime_version: Literal["organizer-catalog-v4-capacity-runtime-v1"]
    catalog_content_digest: Digest
    fallback_mode: Literal["FAIL_CLOSED"]
    activation_requires_approved_report: Literal[True]
    expected_counts: dict[str, Annotated[int, Field(ge=0)]]
    model_ids: list[str]
    position_source_keys: list[str]
    forbidden_system_families: list[str]
    source_digests: dict[str, Digest]
    policy_digest: Digest

    @model_validator(mode="after")
    def validate_policy(self):
        if self.model_ids != sorted(self.model_ids) or len(self.model_ids) != len(set(self.model_ids)):
            raise ValueError("capacity policy model ids must be unique and sorted")
        if self.position_source_keys != sorted(self.position_source_keys) or len(self.position_source_keys) != len(set(self.position_source_keys)):
            raise ValueError("capacity policy position keys must be unique and sorted")
        content = self.model_dump(mode="json")
        actual = content["policy_digest"]
        content["policy_digest"] = "sha256:" + "0" * 64
        if semantic_digest(content) != actual:
            raise ValueError("capacity source policy digest mismatch")
        return self


class CapacityPoolSummaryV1(StrictContractModel):
    models: Annotated[int, Field(ge=0)]
    positions: Annotated[int, Field(ge=0)]
    calculation_pool_models: Annotated[int, Field(ge=0)]
    calculation_pool_positions: Annotated[int, Field(ge=0)]
    calculation_ready_models: Annotated[int, Field(ge=0)]
    calculation_ready_positions: Annotated[int, Field(ge=0)]
    calculation_ready_with_assumptions_models: Annotated[int, Field(ge=0)]
    calculation_ready_with_assumptions_positions: Annotated[int, Field(ge=0)]
    deployment_ready_models: Annotated[int, Field(ge=0)]
    deployment_ready_positions: Annotated[int, Field(ge=0)]
    forbidden_family_models: Annotated[int, Field(ge=0)]


class CapacityRolloutDifferenceV1(StrictContractModel):
    comparison_id: str
    group: Literal["MEMBERSHIP", "PROJECTION", "VERSION_BINDING"]
    classification: Literal["INTENDED_DIFFERENCE", "UNMATCHED_DIFFERENCE"]
    reference: Any
    candidate: Any
    gap_refs: list[Annotated[str, Field(pattern=r"^G[0-9]{2}$")]]
    decision_refs: list[Annotated[str, Field(pattern=r"^K[0-9]{2}$")]]
    reason: str


class CapacityDualRunReportV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["capacity-catalog-dual-run-report-v1"]
    policy_version: Literal["capacity-runtime-rollout-policy-v1"]
    policy_digest: Digest
    reference_catalog_code: str
    candidate_catalog_code: str
    reference_summary: CapacityPoolSummaryV1
    candidate_summary: CapacityPoolSummaryV1
    comparisons: list[CapacityRolloutDifferenceV1]
    comparison_counts: dict[str, Annotated[int, Field(ge=0)]]
    approval_status: Literal["APPROVED", "BLOCKED"]
    blocker_codes: list[str]
    source_digests: dict[str, Digest]
    report_digest: Digest

    @model_validator(mode="after")
    def validate_report(self):
        unmatched = sum(item.classification == "UNMATCHED_DIFFERENCE" for item in self.comparisons)
        intended = sum(item.classification == "INTENDED_DIFFERENCE" for item in self.comparisons)
        if self.comparison_counts.get("UNMATCHED_DIFFERENCE") != unmatched:
            raise ValueError("capacity dual-run unmatched count mismatch")
        if self.comparison_counts.get("INTENDED_DIFFERENCE") != intended:
            raise ValueError("capacity dual-run intended count mismatch")
        if (self.approval_status == "APPROVED") != (not self.blocker_codes and unmatched == 0):
            raise ValueError("capacity dual-run approval status mismatch")
        content = self.model_dump(mode="json")
        actual = content["report_digest"]
        content["report_digest"] = "sha256:" + "0" * 64
        if semantic_digest(content) != actual:
            raise ValueError("capacity dual-run report digest mismatch")
        return self


class CapacitySourceStatusV1(StrictContractModel):
    schema_version: Literal["capacity-source-status-v1"] = "capacity-source-status-v1"
    policy_version: Literal["capacity-runtime-rollout-policy-v1"] = POLICY_VERSION
    status: Literal["ACTIVE", "UNAVAILABLE", "INVALID"]
    reason_code: Literal[
        "ACTIVE_APPROVED_SOURCE", "CAPACITY_SOURCE_NOT_ACTIVE", "CAPACITY_SOURCE_INVALID"
    ]
    catalog_code: str | None
    pool_models: int | None
    pool_positions: int | None
    fallback_mode: Literal["FAIL_CLOSED"] = "FAIL_CLOSED"


class CapacityRolloutPolicyError(ValueError):
    pass


def load_capacity_source_policy(path: Path = POLICY_PATH) -> CapacitySourceActivationPolicyV1:
    try:
        return CapacitySourceActivationPolicyV1.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CapacityRolloutPolicyError("capacity source activation policy is unavailable") from exc


def summarize_capacity_snapshot(snapshot: CatalogSnapshotDTO, policy: CapacitySourceActivationPolicyV1) -> CapacityPoolSummaryV1:
    model_statuses = Counter(item.capacity_runtime.calculation_readiness_status for item in snapshot.models)
    position_statuses = Counter(item.model.capacity_runtime.calculation_readiness_status for item in snapshot.positions)
    forbidden = set(policy.forbidden_system_families)
    return CapacityPoolSummaryV1(
        models=len(snapshot.models), positions=len(snapshot.positions),
        calculation_pool_models=len(snapshot.calculation_ready_models()),
        calculation_pool_positions=len(snapshot.calculation_ready_positions()),
        calculation_ready_models=model_statuses["CALCULATION_READY"],
        calculation_ready_positions=position_statuses["CALCULATION_READY"],
        calculation_ready_with_assumptions_models=model_statuses["CALCULATION_READY_WITH_ASSUMPTIONS"],
        calculation_ready_with_assumptions_positions=position_statuses["CALCULATION_READY_WITH_ASSUMPTIONS"],
        deployment_ready_models=sum(item.capacity_runtime.deployment_readiness_status == "DEPLOYMENT_READY" for item in snapshot.models),
        deployment_ready_positions=sum(item.model.capacity_runtime.deployment_readiness_status == "DEPLOYMENT_READY" for item in snapshot.positions),
        forbidden_family_models=sum(item.system_family in forbidden for item in snapshot.models),
    )


def validate_capacity_source(snapshot: CatalogSnapshotDTO, policy: CapacitySourceActivationPolicyV1 | None = None) -> CapacityPoolSummaryV1:
    policy = policy or load_capacity_source_policy()
    summary = summarize_capacity_snapshot(snapshot, policy)
    model_ids = sorted(item.organizer_id for item in snapshot.calculation_ready_models() if item.organizer_id)
    position_keys = sorted(item.source_record_key for item in snapshot.calculation_ready_positions())
    versions = {item.capacity_runtime.runtime_catalog_version for item in snapshot.calculation_ready_models()}
    if snapshot.version.status != "PUBLISHED":
        raise CapacityRolloutPolicyError("capacity source is not published")
    if snapshot.version.code != policy.catalog_code:
        raise CapacityRolloutPolicyError("capacity source catalog code is not approved")
    if snapshot.version.content_sha256 is None or f"sha256:{snapshot.version.content_sha256}" != policy.catalog_content_digest:
        raise CapacityRolloutPolicyError("capacity source content checksum is not approved")
    if summary.model_dump() != policy.expected_counts:
        raise CapacityRolloutPolicyError("capacity source counts differ from approved policy")
    if model_ids != policy.model_ids or position_keys != policy.position_source_keys:
        raise CapacityRolloutPolicyError("capacity source membership differs from approved policy")
    if versions != {policy.capacity_runtime_version}:
        raise CapacityRolloutPolicyError("capacity runtime version differs from approved policy")
    return summary


def validate_capacity_approval(report: CapacityDualRunReportV1, candidate: CatalogSnapshotDTO, policy: CapacitySourceActivationPolicyV1 | None = None) -> None:
    policy = policy or load_capacity_source_policy()
    candidate_summary = validate_capacity_source(candidate, policy)
    if report.approval_status != "APPROVED" or report.candidate_catalog_code != candidate.version.code:
        raise CapacityRolloutPolicyError("capacity candidate lacks an approved dual-run report")
    if report.policy_digest != policy.policy_digest or report.policy_version != policy.policy_version:
        raise CapacityRolloutPolicyError("capacity approval uses another policy")
    if report.candidate_summary != candidate_summary:
        raise CapacityRolloutPolicyError("capacity approval summary differs from candidate")
    if report.source_digests != policy.source_digests:
        raise CapacityRolloutPolicyError("capacity approval source digests differ from policy")


def _projection(snapshot: CatalogSnapshotDTO) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for position in snapshot.calculation_ready_positions():
        capacity = position.model.capacity_runtime
        values[position.source_record_key] = {
            "model_id": position.model.organizer_id,
            "status": capacity.calculation_readiness_status,
            "profile": capacity.calculation_profile,
            "fields": list(capacity.calculation_model_fields),
            "facts": sorted(
                (
                    fact.code, fact.scope_code, str(fact.value), fact.canonical_unit,
                    fact.resolution_status, fact.evidence_id,
                )
                for fact in capacity.vendor_facts
            ),
            "scenario_assumptions": list(capacity.scenario_assumptions),
            "runtime_version": capacity.runtime_catalog_version,
        }
    return values


def compare_capacity_snapshots(
    reference: CatalogSnapshotDTO,
    candidate: CatalogSnapshotDTO,
    *,
    intended_differences: dict[str, dict[str, Any]] | None = None,
    policy: CapacitySourceActivationPolicyV1 | None = None,
) -> CapacityDualRunReportV1:
    """Compare only capacity projections; legacy Robot/economics are excluded."""

    policy = policy or load_capacity_source_policy()
    intended = intended_differences or {}
    used: set[str] = set()
    differences: list[CapacityRolloutDifferenceV1] = []
    match_count = 0

    def compare(comparison_id: str, group: str, left: Any, right: Any) -> None:
        nonlocal match_count
        if left == right:
            match_count += 1
            return
        expected = intended.get(comparison_id)
        if expected is None:
            classification = "UNMATCHED_DIFFERENCE"
            gap_refs, decision_refs = [], []
            reason = "difference is not approved by the rollout fixture"
        else:
            used.add(comparison_id)
            classification = "INTENDED_DIFFERENCE"
            gap_refs = expected.get("gap_refs", [])
            decision_refs = expected.get("decision_refs", [])
            reason = expected.get("reason", "")
        differences.append(CapacityRolloutDifferenceV1(
            comparison_id=comparison_id, group=group, classification=classification,
            reference=left, candidate=right, gap_refs=gap_refs,
            decision_refs=decision_refs, reason=reason,
        ))

    reference_models = sorted(item.organizer_id for item in reference.calculation_ready_models() if item.organizer_id)
    candidate_models = sorted(item.organizer_id for item in candidate.calculation_ready_models() if item.organizer_id)
    reference_positions = sorted(item.source_record_key for item in reference.calculation_ready_positions())
    candidate_positions = sorted(item.source_record_key for item in candidate.calculation_ready_positions())
    compare("membership.models", "MEMBERSHIP", reference_models, candidate_models)
    compare("membership.positions", "MEMBERSHIP", reference_positions, candidate_positions)
    left_projection, right_projection = _projection(reference), _projection(candidate)
    for key in sorted(set(left_projection) | set(right_projection)):
        compare(f"projection.{key}", "PROJECTION", left_projection.get(key), right_projection.get(key))
    compare(
        "version.capacity-runtime",
        "VERSION_BINDING",
        sorted({value["runtime_version"] for value in left_projection.values()}),
        sorted({value["runtime_version"] for value in right_projection.values()}),
    )

    blockers: list[str] = []
    try:
        validate_capacity_source(candidate, policy)
    except CapacityRolloutPolicyError:
        blockers.append("CANDIDATE_POLICY_MISMATCH")
    if set(intended) - used:
        blockers.append("UNUSED_INTENDED_DIFFERENCE")
    unmatched = sum(item.classification == "UNMATCHED_DIFFERENCE" for item in differences)
    if unmatched:
        blockers.append("UNMATCHED_DIFFERENCE")
    intended_count = sum(item.classification == "INTENDED_DIFFERENCE" for item in differences)
    body = {
        "schema_version": "capacity-catalog-dual-run-report-v1",
        "policy_version": policy.policy_version,
        "policy_digest": policy.policy_digest,
        "reference_catalog_code": reference.version.code,
        "candidate_catalog_code": candidate.version.code,
        "reference_summary": summarize_capacity_snapshot(reference, policy),
        "candidate_summary": summarize_capacity_snapshot(candidate, policy),
        "comparisons": differences,
        "comparison_counts": {
            "MATCH": match_count,
            "INTENDED_DIFFERENCE": intended_count,
            "UNMATCHED_DIFFERENCE": unmatched,
        },
        "approval_status": "APPROVED" if not blockers else "BLOCKED",
        "blocker_codes": blockers,
        "source_digests": policy.source_digests,
        "report_digest": "sha256:" + "0" * 64,
    }
    draft = CapacityDualRunReportV1.model_construct(**body).model_dump(mode="json")
    body["report_digest"] = semantic_digest(draft)
    return CapacityDualRunReportV1.model_validate(body)


__all__ = [
    "CapacityDualRunReportV1", "CapacityRolloutPolicyError",
    "CapacitySourceActivationPolicyV1", "CapacitySourceStatusV1",
    "load_capacity_source_policy", "summarize_capacity_snapshot",
    "compare_capacity_snapshots", "validate_capacity_approval", "validate_capacity_source",
]
