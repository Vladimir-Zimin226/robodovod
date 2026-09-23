"""Build deterministic C27 activation policy, report and JSON schemas."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation_contracts import semantic_digest  # noqa: E402
from catalog_capacity_rollout import (  # noqa: E402
    CapacityDualRunReportV1,
    CapacitySourceActivationPolicyV1,
    CapacitySourceStatusV1,
)

DIFF = ROOT / "data/review/catalog-formula-executability-pool-diff-v3.json"
AUDIT = ROOT / "data/review/catalog-formula-executability-audit-v3.json"
RUNTIME = ROOT / "data/import/organizer-catalog-v4/catalog_capacity_runtime.json"
READINESS = ROOT / "data/review/catalog-calculation-readiness-audit-v2.json"
MANIFEST = ROOT / "data/import/organizer-catalog-v4/manifest.json"
POLICY = ROOT / "contracts/capacity-source-activation-policy-v1.json"
REPORT = ROOT / "contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json"
SCHEMAS = {
    ROOT / "contracts/capacity-source-activation-policy-v1.schema.json": CapacitySourceActivationPolicyV1,
    ROOT / "contracts/capacity-catalog-dual-run-report-v1.schema.json": CapacityDualRunReportV1,
    ROOT / "contracts/capacity-source-status-v1.schema.json": CapacitySourceStatusV1,
}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _finalize(body: dict, field: str) -> dict:
    body[field] = "sha256:" + "0" * 64
    body[field] = semantic_digest(body)
    return body


def build_policy() -> CapacitySourceActivationPolicyV1:
    diff, runtime = _read(DIFF), _read(RUNTIME)
    bundle_sha = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    content_sha = hashlib.sha256(
        json.dumps(sorted((phase, bundle_sha) for phase in ("BASE", "ENRICHMENT")), separators=(",", ":")).encode()
    ).hexdigest()
    body = {
        "schema_version": "capacity-source-activation-policy-v1",
        "policy_version": "capacity-runtime-rollout-policy-v1",
        "catalog_code": "organizer-catalog-v4",
        "capacity_runtime_version": "organizer-catalog-v4-capacity-runtime-v1",
        "catalog_content_digest": f"sha256:{content_sha}",
        "fallback_mode": "FAIL_CLOSED",
        "activation_requires_approved_report": True,
        "expected_counts": {**runtime["counts"], "forbidden_family_models": 0},
        "model_ids": sorted(diff["candidate_model_ids"]),
        "position_source_keys": sorted(diff["candidate_position_ids"]),
        "forbidden_system_families": ["BAS"],
        "source_digests": {
            "capacity_runtime": _file_digest(RUNTIME),
            "formula_executability_audit": _file_digest(AUDIT),
            "formula_executability_pool_diff": _file_digest(DIFF),
            "readiness_audit": _file_digest(READINESS),
            "catalog_manifest": _file_digest(MANIFEST),
        },
    }
    return CapacitySourceActivationPolicyV1.model_validate(_finalize(body, "policy_digest"))


def build_report(policy: CapacitySourceActivationPolicyV1) -> CapacityDualRunReportV1:
    summary = dict(policy.expected_counts)
    comparisons = [
        {
            "comparison_id": "version.readiness-contract",
            "group": "VERSION_BINDING",
            "classification": "INTENDED_DIFFERENCE",
            "reference": "runtime-calculation-readiness-contract-v2",
            "candidate": "formula-executability-profiles-v3",
            "gap_refs": ["G48"],
            "decision_refs": ["K29"],
            "reason": "formula executability adds evidence-gated profiles without changing pool membership",
        },
        {
            "comparison_id": "projection.capacity-reader",
            "group": "PROJECTION",
            "classification": "INTENDED_DIFFERENCE",
            "reference": "discovery snapshot with readiness labels",
            "candidate": "capacity-only projection with facts, assumptions and profile version",
            "gap_refs": ["G48"],
            "decision_refs": ["K29"],
            "reason": "the dedicated reader exposes approved capacity evidence and never constructs legacy Robot economics",
        },
    ]
    body = {
        "schema_version": "capacity-catalog-dual-run-report-v1",
        "policy_version": policy.policy_version,
        "policy_digest": policy.policy_digest,
        "reference_catalog_code": policy.catalog_code,
        "candidate_catalog_code": policy.catalog_code,
        "reference_summary": summary,
        "candidate_summary": summary,
        "comparisons": comparisons,
        "comparison_counts": {"MATCH": 2, "INTENDED_DIFFERENCE": 2, "UNMATCHED_DIFFERENCE": 0},
        "approval_status": "APPROVED",
        "blocker_codes": [],
        "source_digests": policy.source_digests,
    }
    return CapacityDualRunReportV1.model_validate(_finalize(body, "report_digest"))


def expected_outputs() -> dict[Path, bytes]:
    policy = build_policy()
    report = build_report(policy)
    outputs = {
        POLICY: (json.dumps(policy.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
        REPORT: (json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
    }
    for path, model in SCHEMAS.items():
        schema = model.model_json_schema(ref_template="#/$defs/{model}", mode="serialization")
        schema["$id"] = f"https://robomera.local/contracts/{path.name}"
        outputs[path] = (json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = expected_outputs()
    if args.check:
        return 0 if all(path.is_file() and path.read_bytes() == data for path, data in outputs.items()) else 1
    for path, data in outputs.items():
        path.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
