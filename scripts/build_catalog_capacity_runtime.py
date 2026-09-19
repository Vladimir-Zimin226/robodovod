from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from catalog_import_contract import (  # noqa: E402
    CapacityEnrichmentContract,
    CapacityRuntimeContract,
)

BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"
OUTPUT = BUNDLE / "catalog_capacity_runtime.json"
SCHEMA = ROOT / "contracts" / "catalog-capacity-runtime-v1.schema.json"
ENRICHMENT_OUTPUT = BUNDLE / "catalog_capacity_enrichment.json"
ENRICHMENT_SCHEMA = ROOT / "contracts" / "catalog-capacity-enrichment-v1.schema.json"
MANIFEST = BUNDLE / "manifest.json"
CONTRACT = ROOT / "contracts" / "runtime-calculation-readiness-contract-v2.json"
AUDIT = ROOT / "data" / "review" / "catalog-calculation-readiness-audit-v2.json"
PRODUCTS = BUNDLE / "catalog_products.json"
STAGING = (
    ROOT
    / "data"
    / "enrichment"
    / "catalog-official-source-enrichment-v1"
    / "staging-overlay.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _manifest_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _blockers(item: dict[str, Any]) -> list[str]:
    status = item["calculation_status"]
    if status in {"CALCULATION_READY", "CALCULATION_READY_WITH_ASSUMPTIONS"}:
        return []
    blockers = [
        *(f"missing:{field}" for field in item["missing_calculation_fields"]),
        *(f"conflict:{field}" for field in item["conflict_fields"]),
    ]
    if blockers:
        return sorted(set(blockers))
    return [
        {
            "CALCULATION_BLOCKED": "calculation_facts_incomplete",
            "UNSUPPORTED_CAPACITY_PROFILE": "unsupported_capacity_profile",
            "NOT_EQUIPMENT": "not_equipment",
        }[status]
    ]


def build() -> CapacityRuntimeContract:
    audit = _load(AUDIT)
    products = _load(PRODUCTS)["products"]
    product_ids = {str(item["organizer_id"]) for item in products}
    models = []
    for item in sorted(audit["models"], key=lambda value: value["model_id"]):
        status = item["calculation_status"]
        models.append(
            {
                "model_id": item["model_id"],
                "calculation_readiness_status": status,
                "calculation_ready": status
                in {"CALCULATION_READY", "CALCULATION_READY_WITH_ASSUMPTIONS"},
                "calculation_requires_assumptions": status
                == "CALCULATION_READY_WITH_ASSUMPTIONS",
                "calculation_profile": item["capacity_profile"],
                "calculation_model_fields": item["calculation_model_fields"],
                "calculation_blockers": _blockers(item),
                "scenario_assumptions": (
                    item["calculation_assumptions"]
                    if status == "CALCULATION_READY_WITH_ASSUMPTIONS"
                    else []
                ),
                "deployment_readiness_status": item["deployment_status"],
            }
        )
    if {item["model_id"] for item in models} != product_ids:
        raise ValueError("audit and versioned products have different model coverage")
    payload = {
        "schema_version": "catalog-capacity-runtime-v1",
        "runtime_catalog_version": "organizer-catalog-v4-capacity-runtime-v1",
        "catalog_code": "organizer-catalog-v4",
        "contract_version": "runtime-calculation-readiness-contract-v2",
        "source_sha256": {
            "contract": _sha256(CONTRACT),
            "audit": _sha256(AUDIT),
            "products": _sha256(PRODUCTS),
        },
        "counts": {
            "models": 187,
            "positions": 223,
            "calculation_ready_models": 6,
            "calculation_ready_positions": 6,
            "calculation_ready_with_assumptions_models": 15,
            "calculation_ready_with_assumptions_positions": 18,
            "calculation_pool_models": 21,
            "calculation_pool_positions": 24,
            "deployment_ready_models": 0,
            "deployment_ready_positions": 0,
        },
        "deterministic_order": "model_id",
        "models": models,
    }
    return CapacityRuntimeContract.model_validate(payload)


def build_enrichment() -> CapacityEnrichmentContract:
    staging = _load(STAGING)
    payload = {
        "schema_version": "catalog-capacity-enrichment-v1",
        "catalog_code": "organizer-catalog-v4",
        "source_overlay_sha256": _sha256(STAGING),
        "reviewed_by_subject": (
            "catalog-official-source-enrichment-reviewed-decisions-v1"
        ),
        "reviewed_at": "2026-09-19T00:00:00+11:00",
        "deterministic_order": "organizer_id,field_path,decision_id",
        "counts": {
            "facts": 131,
            "matching_facts": 129,
            "evidence_rows": 154,
            "models": 26,
        },
        "facts": sorted(
            staging["facts"],
            key=lambda item: (
                item["organizer_id"],
                item["field_path"],
                item["decision_id"],
            ),
        ),
    }
    return CapacityEnrichmentContract.model_validate(payload)


def _updated_manifest(runtime_bytes: bytes, enrichment_bytes: bytes) -> bytes:
    manifest = _load(MANIFEST)
    digest = hashlib.sha256(runtime_bytes).hexdigest()
    runtime_file_entry = {
        "path": OUTPUT.name,
        "phase": "ENRICHMENT",
        "sha256": digest,
        "size_bytes": len(runtime_bytes),
        "record_kind": "capacity_runtime_models",
        "records": 187,
    }
    runtime_artifact = {
        "artifact_key": f"bundle:{OUTPUT.name}",
        "original_name": OUTPUT.name,
        "sha256": digest,
        "size_bytes": len(runtime_bytes),
        "media_type": "application/json",
        "provenance_status": "VERIFIED",
        "license_status": "PERMITTED",
        "role": "IMPORT_BUNDLE",
        "ordinal": 8,
        "observed_at": "2026-09-19T00:00:00+11:00",
    }
    enrichment_digest = hashlib.sha256(enrichment_bytes).hexdigest()
    enrichment_file_entry = {
        "path": ENRICHMENT_OUTPUT.name,
        "phase": "ENRICHMENT",
        "sha256": enrichment_digest,
        "size_bytes": len(enrichment_bytes),
        "record_kind": "capacity_enrichment_facts",
        "records": 131,
    }
    enrichment_artifact = {
        "artifact_key": f"bundle:{ENRICHMENT_OUTPUT.name}",
        "original_name": ENRICHMENT_OUTPUT.name,
        "sha256": enrichment_digest,
        "size_bytes": len(enrichment_bytes),
        "media_type": "application/json",
        "provenance_status": "VERIFIED",
        "license_status": "PERMITTED",
        "role": "IMPORT_BUNDLE",
        "ordinal": 9,
        "observed_at": "2026-09-19T00:00:00+11:00",
    }
    manifest["expected_counts"].update(
        {
            "capacity_runtime_models": 187,
            "capacity_runtime_pool_models": 21,
            "capacity_runtime_pool_positions": 24,
            "capacity_enrichment_facts": 131,
            "capacity_enrichment_matching_facts": 129,
            "capacity_enrichment_evidence_rows": 154,
            "capacity_enrichment_models": 26,
        }
    )
    manifest["files"] = [
        item
        for item in manifest["files"]
        if item["path"] not in {OUTPUT.name, ENRICHMENT_OUTPUT.name}
    ] + [runtime_file_entry, enrichment_file_entry]
    manifest["source_artifacts"] = [
        item
        for item in manifest["source_artifacts"]
        if item["artifact_key"]
        not in {runtime_artifact["artifact_key"], enrichment_artifact["artifact_key"]}
    ] + [runtime_artifact, enrichment_artifact]
    return _manifest_bytes(manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    runtime_bytes = _bytes(build().model_dump(mode="json"))
    enrichment_bytes = _bytes(build_enrichment().model_dump(mode="json"))
    schema_bytes = _bytes(CapacityRuntimeContract.model_json_schema())
    enrichment_schema_bytes = _bytes(CapacityEnrichmentContract.model_json_schema())
    manifest_bytes = _updated_manifest(runtime_bytes, enrichment_bytes)
    expected = (
        (OUTPUT, runtime_bytes),
        (SCHEMA, schema_bytes),
        (ENRICHMENT_OUTPUT, enrichment_bytes),
        (ENRICHMENT_SCHEMA, enrichment_schema_bytes),
        (MANIFEST, manifest_bytes),
    )
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, value in expected if not path.is_file() or path.read_bytes() != value]
        if stale:
            raise SystemExit("generated capacity runtime files differ: " + ", ".join(stale))
        return 0
    for path, value in expected:
        path.write_bytes(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
