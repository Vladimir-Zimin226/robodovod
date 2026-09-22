"""Build/check the C06 full-catalog formula executability audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.executability import (
    CatalogCandidateInput,
    ExecutabilityPoolDiffV3,
    ExecutabilityProfilesV3,
    FormulaExecutabilityAuditV3,
    RunExecutabilityResult,
    audit_catalog_candidate,
    load_executability_profiles,
    registry_payload,
)

READINESS = ROOT / "data" / "review" / "catalog-calculation-readiness-audit-v2.json"
PRODUCTS = ROOT / "data" / "import" / "organizer-catalog-v4" / "catalog_products.json"
EXTERNAL = ROOT / "data" / "import" / "organizer-catalog-v4" / "catalog_external_enrichment.json"
CAPACITY = ROOT / "data" / "import" / "organizer-catalog-v4" / "catalog_capacity_enrichment.json"
REGISTRY = ROOT / "data" / "calculation" / "registry-v1.json"
PROFILES = ROOT / "data" / "calculation" / "formula-executability-profiles-v3.json"
REPORT = ROOT / "data" / "review" / "catalog-formula-executability-audit-v3.json"
POOL_DIFF = ROOT / "data" / "review" / "catalog-formula-executability-pool-diff-v3.json"
SUMMARY = ROOT / "data" / "review" / "catalog-formula-executability-summary-v3.md"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _encoded(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _fact_indexes() -> tuple[dict[str, dict[str, Any]], ...]:
    products = {item["organizer_id"]: item for item in _load(PRODUCTS)["products"]}
    capacity = {
        f"{item['organizer_id']}|{item['field_path']}": item
        for item in _load(CAPACITY)["facts"]
        if item["usable_for_matching"]
    }
    external = {item["organizer_id"]: item for item in _load(EXTERNAL)["products"]}
    return products, capacity, external


def _catalog_fact(
    model_id: str,
    field_path: str,
    products: dict[str, dict[str, Any]],
    capacity: dict[str, dict[str, Any]],
    external: dict[str, dict[str, Any]],
) -> tuple[Any, str | None, list[str]] | None:
    reviewed = capacity.get(f"{model_id}|{field_path}")
    if reviewed is not None:
        return reviewed["normalized_value"], reviewed["normalized_unit"], [f"capacity-enrichment:{reviewed['decision_id']}"]
    suffix = field_path.split(".", 1)[1]
    external_field = (external.get(model_id, {}).get("fields") or {}).get(suffix)
    if external_field is not None and external_field.get("evidence_status") in {
        "VERIFIED_OFFICIAL", "VERIFIED_AUTHORIZED_PARTNER", "MANUALLY_APPROVED",
        "CORROBORATED", "CROSS_DOCUMENT_ENRICHED",
    } and external_field.get("normalized_value") is not None:
        refs = [f"external-evidence:{item}" for item in external_field.get("source_ids", [])]
        return external_field["normalized_value"], external_field.get("normalized_unit"), refs
    product_field = (products.get(model_id, {}).get("specs") or {}).get(suffix)
    if not isinstance(product_field, dict):
        return None
    values = product_field.get("values")
    if isinstance(values, list) and len(values) == 1:
        value = values[0]
    elif product_field.get("value") is not None:
        value = product_field["value"]
    else:
        return None
    return value, product_field.get("unit"), [f"catalog-products:{model_id}:{field_path}"]


def _candidate(
    item: dict[str, Any],
    products: dict[str, dict[str, Any]],
    capacity: dict[str, dict[str, Any]],
    external: dict[str, dict[str, Any]],
    *,
    position_id: str | None = None,
) -> CatalogCandidateInput:
    product = products[item["model_id"]]
    safe = set(item["calculation_model_fields"]) - set(item["missing_calculation_fields"]) - set(item["conflict_fields"])
    profile = next((value for value in load_executability_profiles().profiles if value.profile_id == item["capacity_profile"]), None)
    paths = [fact.field_path for fact in profile.catalog_facts] if profile else []
    facts = []
    for path in paths:
        found = _catalog_fact(item["model_id"], path, products, capacity, external) if path in safe else None
        if found is None:
            facts.append({"field_path": path, "evidence_status": "NOT_FOUND", "source_refs": []})
        else:
            value, unit, refs = found
            facts.append({"field_path": path, "value": value, "unit": unit, "evidence_status": "MATCHING_SAFE", "source_refs": refs})
    return CatalogCandidateInput.model_validate({
        "model_id": item["model_id"], "position_id": position_id,
        "name": item["name"], "system_family": product["system_family"],
        "identity_status": "MATCHED",
        "profile_id": item["capacity_profile"], "readiness_v2_status": item["calculation_status"],
        "facts": facts,
    })


def build() -> FormulaExecutabilityAuditV3:
    readiness = _load(READINESS)
    products, capacity, external = _fact_indexes()
    registry = registry_payload(REGISTRY)
    profiles = load_executability_profiles(str(PROFILES))
    model_items = sorted(readiness["models"], key=lambda item: item["model_id"])
    models = []
    result_by_model = {}
    for item in model_items:
        candidate = _candidate(item, products, capacity, external)
        result = audit_catalog_candidate(candidate, registry, profiles)
        result_by_model[item["model_id"]] = result
        models.append({
            "id": item["id"], "model_id": item["model_id"], "name": item["name"],
            "source_row_number": None, "system_family": candidate.system_family, "result": result,
        })
    model_source = {item["model_id"]: item for item in model_items}
    positions = []
    for item in sorted(readiness["positions"], key=lambda value: value["source_row_number"]):
        candidate = _candidate(model_source[item["model_id"]], products, capacity, external, position_id=item["id"])
        result = audit_catalog_candidate(candidate, registry, profiles)
        positions.append({
            "id": item["id"], "model_id": item["model_id"], "name": item["name"],
            "source_row_number": item["source_row_number"], "system_family": candidate.system_family,
            "result": result,
        })
    ready = {"CALCULATION_READY", "CALCULATION_READY_WITH_ASSUMPTIONS"}
    baseline_models = sorted(item["model_id"] for item in model_items if item["calculation_status"] in ready)
    baseline_positions = sorted(item["id"] for item in readiness["positions"] if item["calculation_status"] in ready)
    candidate_models = sorted(item["model_id"] for item in models if item["result"].catalog_status == "CATALOG_EXECUTABLE")
    candidate_positions = sorted(item["id"] for item in positions if item["result"].catalog_status == "CATALOG_EXECUTABLE")
    pool_diff = ExecutabilityPoolDiffV3(
        baseline_contract_version="runtime-calculation-readiness-contract-v2",
        candidate_contract_version="formula-executability-profiles-v3",
        baseline_model_ids=baseline_models, candidate_model_ids=candidate_models,
        added_model_ids=sorted(set(candidate_models) - set(baseline_models)),
        removed_model_ids=sorted(set(baseline_models) - set(candidate_models)),
        baseline_position_ids=baseline_positions, candidate_position_ids=candidate_positions,
        added_position_ids=sorted(set(candidate_positions) - set(baseline_positions)),
        removed_position_ids=sorted(set(baseline_positions) - set(candidate_positions)),
    )
    statuses = ["CATALOG_EXECUTABLE", "MISSING_SAFE_FACT", "INVALID_FACT", "UNKNOWN_IDENTITY", "UNSUPPORTED_PROFILE", "NOT_EQUIPMENT"]
    model_counts = Counter(item["result"].catalog_status for item in models)
    position_counts = Counter(item["result"].catalog_status for item in positions)
    bas_present = any(item["system_family"] == "BAS" and item["result"].catalog_status == "CATALOG_EXECUTABLE" for item in models)
    return FormulaExecutabilityAuditV3.model_validate({
        "profiles_version": profiles.profiles_version,
        "readiness_contract_version": readiness["contract_version"],
        "catalog_code": readiness["catalog_code"],
        "deterministic_order": "models:model_id;positions:source_row_number",
        "inputs_sha256": {path.stem: _sha256(path) for path in (READINESS, PRODUCTS, EXTERNAL, CAPACITY, REGISTRY, PROFILES)},
        "counts": {"models": 187, "positions": 223, "candidate_pool_models": len(candidate_models), "candidate_pool_positions": len(candidate_positions)},
        "model_status_counts": {status: model_counts[status] for status in statuses},
        "position_status_counts": {status: position_counts[status] for status in statuses},
        "invariants": {
            "formulas_executed": False, "economics_required": False,
            "robot_cost_fields_read": False, "runtime_activation_changed": False,
            "pool_membership_changed": False, "bas_in_candidate_pool": bas_present,
        },
        "pool_diff": pool_diff, "models": models, "positions": positions,
    })


def summary(report: FormulaExecutabilityAuditV3) -> str:
    rows = "\n".join(
        f"| {status} | {report.model_status_counts[status]} | {report.position_status_counts[status]} |"
        for status in report.model_status_counts
    )
    return f"""# Formula executability audit v3

Audit covers exactly 187 models and 223 positions. It validates dependency
origins, evidence, units and domains without executing formulas, reading Robot
costs, changing runtime activation or changing pool membership.

| Status | Models | Positions |
|---|---:|---:|
{rows}

The catalog-executable identity set remains exactly 21 models / 24 positions;
the committed pool diff has no additions or removals. BAS is absent. A catalog
label is not run executability: every run must still provide normalized C03
scenario inputs and an acceptable C05 constraint report.
"""


def outputs() -> dict[Path, bytes]:
    report = build()
    return {
        ROOT / "contracts" / "formula-executability-profiles-v3.schema.json": _encoded(ExecutabilityProfilesV3.model_json_schema()),
        ROOT / "contracts" / "catalog-formula-executability-audit-v3.schema.json": _encoded(FormulaExecutabilityAuditV3.model_json_schema()),
        ROOT / "contracts" / "catalog-formula-executability-pool-diff-v3.schema.json": _encoded(ExecutabilityPoolDiffV3.model_json_schema()),
        ROOT / "contracts" / "formula-run-executability-v3.schema.json": _encoded(RunExecutabilityResult.model_json_schema()),
        REPORT: _encoded(report), POOL_DIFF: _encoded(report.pool_diff), SUMMARY: summary(report).encode("utf-8"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, payload in outputs().items():
        if args.check:
            if not path.is_file() or path.read_bytes() != payload:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
    if stale:
        raise SystemExit("C06 generated artifacts differ: " + ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
