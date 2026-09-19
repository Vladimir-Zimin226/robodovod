"""Build a review-only official-source staging overlay and eligibility projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from catalog_runtime_eligibility import (  # noqa: E402
    AuditItem,
    AuditReport,
    Conflict,
    FieldAssessment,
    InputFile,
    SourceReference,
    _coverage,
    _recommendation,
    build_report,
    report_bytes,
    schema_bytes,
    summary_text,
)
from scripts.review_catalog_deep_research_returns import build_resolution

REVIEW = ROOT / "data" / "review" / "catalog-official-source-enrichment-review-v1.json"
LEDGER = ROOT / "data" / "review" / "catalog-official-source-enrichment-reviewed-decisions-v1.json"
RESOLUTION = ROOT / "data" / "review" / "catalog-official-source-enrichment-resolution-v1.json"
CONTRACT = ROOT / "contracts" / "runtime-eligibility-contract-v1.json"
STAGING_DIR = ROOT / "data" / "enrichment" / "catalog-official-source-enrichment-v1"
STAGING = STAGING_DIR / "staging-overlay.json"
STAGING_SCHEMA = ROOT / "contracts" / "catalog-official-source-enrichment-staging-v1.schema.json"
STAGING_SUMMARY = STAGING_DIR / "README.md"
POST_REPORT = ROOT / "data" / "review" / "catalog-runtime-eligibility-post-enrichment-v1.json"
POST_SUMMARY = ROOT / "data" / "review" / "catalog-runtime-eligibility-post-enrichment-v1.md"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StagingEvidence(StrictModel):
    raw_value: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https?://")
    source_title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    publication_or_update_date: str | None = Field(
        default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
    )
    accessed_at: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class StagingFact(StrictModel):
    decision_id: str = Field(pattern=r"^[AR][0-9]{3}$")
    organizer_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    field_path: str = Field(pattern=r"^(specs|capacity)\.")
    normalized_value: Any
    normalized_unit: str | None
    resolution_status: Literal["VERIFIED_OFFICIAL", "MANUALLY_APPROVED"]
    usable_for_matching: bool
    applicability_note: str = Field(min_length=1)
    evidence: list[StagingEvidence] = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_value(self) -> "StagingFact":
        if self.normalized_value is None:
            raise ValueError("staging fact must have a normalized value")
        json.dumps(self.normalized_value, ensure_ascii=False, sort_keys=True)
        return self


class DeferredField(StrictModel):
    decision_id: str = Field(pattern=r"^R[0-9]{3}$")
    organizer_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    field_path: str = Field(pattern=r"^(specs|capacity)\.")
    decision: str = Field(pattern=r"^DEFER")
    reason: str = Field(min_length=1)
    evidence: list[StagingEvidence]


class MissingField(StrictModel):
    batch_id: str = Field(min_length=1)
    organizer_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    field_path: str = Field(pattern=r"^(specs|capacity)\.")
    notes: str = Field(min_length=1)


class StagingCounts(StrictModel):
    accepted_fields: int = Field(ge=0)
    matching_usable_fields: int = Field(ge=0)
    review_only_fields: int = Field(ge=0)
    deferred_fields: int = Field(ge=0)
    remains_missing_fields: int = Field(ge=0)
    target_fields: int = Field(ge=0)
    models_with_accepted_facts: int = Field(ge=0)


class StagingPolicy(StrictModel):
    mode: Literal["STAGING_ONLY"]
    writes_database: Literal[False]
    activates_catalog_or_runtime: Literal[False]
    base_observations_immutable: Literal[True]
    review_only_facts_are_matching_safe: Literal[False]


class StagingInputs(StrictModel):
    review: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_ledger: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolution: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_contract: str = Field(pattern=r"^[0-9a-f]{64}$")


class StagingOverlay(StrictModel):
    schema_version: Literal["catalog-official-source-enrichment-staging-v1"]
    catalog_code: Literal["organizer-catalog-v4"]
    decision_cutoff_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    deterministic_order: Literal[
        "facts:organizer_id,field_path;deferred:organizer_id,field_path;missing:organizer_id,field_path"
    ]
    policy: StagingPolicy
    input_sha256: StagingInputs
    counts: StagingCounts
    facts: list[StagingFact]
    deferred: list[DeferredField]
    remains_missing: list[MissingField]

    @model_validator(mode="after")
    def validate_exact_partition(self) -> "StagingOverlay":
        facts = [(row.organizer_id, row.field_path) for row in self.facts]
        deferred = [(row.organizer_id, row.field_path) for row in self.deferred]
        missing = [(row.organizer_id, row.field_path) for row in self.remains_missing]
        if facts != sorted(facts) or deferred != sorted(deferred) or missing != sorted(missing):
            raise ValueError("staging collections are not deterministically ordered")
        if any(
            len(rows) != len(set(rows)) for rows in (facts, deferred, missing)
        ):
            raise ValueError("duplicate field within staging partition")
        if set(facts) & set(deferred) or set(facts) & set(missing) or set(deferred) & set(missing):
            raise ValueError("field occurs in more than one staging partition")
        expected = {
            "accepted_fields": len(self.facts),
            "matching_usable_fields": sum(row.usable_for_matching for row in self.facts),
            "review_only_fields": sum(not row.usable_for_matching for row in self.facts),
            "deferred_fields": len(self.deferred),
            "remains_missing_fields": len(self.remains_missing),
            "target_fields": len(self.facts) + len(self.deferred) + len(self.remains_missing),
            "models_with_accepted_facts": len({row.organizer_id for row in self.facts}),
        }
        if self.counts.model_dump() != expected:
            raise ValueError(f"staging counts differ: {self.counts.model_dump()} != {expected}")
        if expected["target_fields"] != 456:
            raise ValueError("staging must partition exactly 456 research targets")
        return self


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _review_rows(review: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (model["organizer_id"], field["field_path"]): field
        for batch in review["batches"]
        for model in batch["models"]
        for field in model["field_reviews"]
    }


def _evidence(
    selected: dict[str, Any] | list[dict[str, Any]] | None,
    review_field: dict[str, Any],
    decided_at: str,
) -> list[dict[str, Any]]:
    selected_rows = selected if isinstance(selected, list) else ([selected] if selected else [])
    review_evidence = review_field.get("evidence", [])
    result = []
    for row in selected_rows:
        match = next(
            (
                candidate
                for candidate in review_evidence
                if candidate["source_url"] == row.get("source_url")
                and candidate["raw_value"] == row.get("raw_value")
            ),
            None,
        )
        source = dict(match or row)
        source.setdefault("publisher", "Publisher recorded in reviewed decision")
        source.setdefault("source_type", "OFFICIAL_SOURCE")
        source.setdefault("source_locator", "Locator recorded in reviewed decision")
        source.setdefault("publication_or_update_date", None)
        source.setdefault("accessed_at", decided_at)
        result.append({key: source[key] for key in StagingEvidence.model_fields})
    unique = {_canonical(row): row for row in result}
    return [unique[key] for key in sorted(unique)]


def build_staging(
    review_path: Path = REVIEW,
    ledger_path: Path = LEDGER,
    resolution_path: Path = RESOLUTION,
    contract_path: Path = CONTRACT,
) -> StagingOverlay:
    review = _load(review_path)
    ledger = _load(ledger_path)
    resolution = _load(resolution_path)
    rebuilt = build_resolution(review, ledger)
    rebuilt["input_sha256"] = {
        "review": _sha256(review_path),
        "decision_ledger": _sha256(ledger_path),
    }
    if _canonical(rebuilt) != _canonical(resolution):
        raise ValueError("resolution differs from reviewed decisions")
    fields = _review_rows(review)
    facts = []
    for decision in resolution["accepted"]:
        key = (decision["organizer_id"], decision["field_path"])
        review_field = fields[key]
        decision_id = decision["decision_id"]
        review_only = decision_id in {"R005", "R013"}
        if decision_id == "R013":
            applicability = "Current official revision only; organizer revision remains unconfirmed."
        elif decision_id == "R005":
            applicability = "Only the published maximum temperature is resolved; lower bound remains unknown."
        else:
            applicability = "Applies to the reviewed exact model identity and field scope."
        facts.append(
            {
                "decision_id": decision_id,
                "organizer_id": decision["organizer_id"],
                "model_name": decision["model_name"],
                "field_path": decision["field_path"],
                "normalized_value": decision["selected_value"],
                "normalized_unit": decision.get("selected_unit"),
                "resolution_status": (
                    "VERIFIED_OFFICIAL" if decision_id.startswith("A") else "MANUALLY_APPROVED"
                ),
                "usable_for_matching": not review_only,
                "applicability_note": applicability,
                "evidence": _evidence(
                    decision.get("selected_evidence"),
                    review_field,
                    decision.get("decided_at", "2026-09-19"),
                ),
                "rationale": decision.get(
                    "rationale", "Accepted exact reviewed official-source candidate."
                ),
            }
        )
    deferred = []
    for decision in resolution["deferred"]:
        key = (decision["organizer_id"], decision["field_path"])
        review_field = fields[key]
        deferred.append(
            {
                "decision_id": decision["decision_id"],
                "organizer_id": decision["organizer_id"],
                "model_name": decision["model_name"],
                "field_path": decision["field_path"],
                "decision": decision["decision"],
                "reason": decision["rationale"],
                "evidence": _evidence(
                    review_field.get("evidence"), review_field, decision.get("decided_at", "2026-09-19")
                ),
            }
        )
    missing = resolution["remains_missing"]
    facts.sort(key=lambda row: (row["organizer_id"], row["field_path"]))
    deferred.sort(key=lambda row: (row["organizer_id"], row["field_path"]))
    missing.sort(key=lambda row: (row["organizer_id"], row["field_path"]))
    counts = {
        "accepted_fields": len(facts),
        "matching_usable_fields": sum(row["usable_for_matching"] for row in facts),
        "review_only_fields": sum(not row["usable_for_matching"] for row in facts),
        "deferred_fields": len(deferred),
        "remains_missing_fields": len(missing),
        "target_fields": len(facts) + len(deferred) + len(missing),
        "models_with_accepted_facts": len({row["organizer_id"] for row in facts}),
    }
    return StagingOverlay.model_validate(
        {
            "schema_version": "catalog-official-source-enrichment-staging-v1",
            "catalog_code": "organizer-catalog-v4",
            "decision_cutoff_date": "2026-09-19",
            "deterministic_order": "facts:organizer_id,field_path;deferred:organizer_id,field_path;missing:organizer_id,field_path",
            "policy": {
                "mode": "STAGING_ONLY",
                "writes_database": False,
                "activates_catalog_or_runtime": False,
                "base_observations_immutable": True,
                "review_only_facts_are_matching_safe": False,
            },
            "input_sha256": {
                "review": _sha256(review_path),
                "decision_ledger": _sha256(ledger_path),
                "resolution": _sha256(resolution_path),
                "runtime_contract": _sha256(contract_path),
            },
            "counts": counts,
            "facts": facts,
            "deferred": deferred,
            "remains_missing": missing,
        }
    )


def _fact_source(fact: StagingFact, index: int) -> SourceReference:
    evidence = fact.evidence[index]
    return SourceReference(
        source_id=f"staging:{fact.decision_id}:{index + 1}",
        source_file="staging-overlay.json",
        evidence_status=fact.resolution_status,
        locator=f"{fact.organizer_id}:{fact.field_path}:{evidence.source_locator}",
    )


def project_eligibility(staging: StagingOverlay, staging_path: Path = STAGING) -> AuditReport:
    base = build_report()
    facts_by_model: dict[str, list[StagingFact]] = {}
    deferred_by_model: dict[str, list[DeferredField]] = {}
    for fact in staging.facts:
        facts_by_model.setdefault(fact.organizer_id, []).append(fact)
    for item in staging.deferred:
        deferred_by_model.setdefault(item.organizer_id, []).append(item)
    researched_ids = set(facts_by_model) | set(deferred_by_model)
    models = []
    for original in base.models:
        if original.model_id not in researched_ids:
            models.append(original)
            continue
        assessments = {item.field: item for item in original.present_fields}
        for field in original.missing_fields:
            assessments.setdefault(field, FieldAssessment(field=field, availability="MISSING", sources=[]))
        for fact in facts_by_model.get(original.model_id, []):
            assessments[fact.field_path] = FieldAssessment(
                field=fact.field_path,
                availability="MATCHING_SAFE" if fact.usable_for_matching else "LOCAL_CANDIDATE",
                sources=[_fact_source(fact, index) for index in range(len(fact.evidence))],
            )
        for deferred in deferred_by_model.get(original.model_id, []):
            assessments[deferred.field_path] = FieldAssessment(
                field=deferred.field_path,
                availability="CONFLICT",
                sources=[
                    SourceReference(
                        source_id=f"staging:{deferred.decision_id}:{index + 1}",
                        source_file="staging-overlay.json",
                        evidence_status="CONFLICT",
                        locator=f"{deferred.organizer_id}:{deferred.field_path}:{evidence.source_locator}",
                    )
                    for index, evidence in enumerate(deferred.evidence)
                ],
            )
        ordered = [assessments[key] for key in sorted(assessments)]
        conflicts = [
            Conflict(
                field=item.field,
                reason=next(
                    (
                        row.reason
                        for row in deferred_by_model.get(original.model_id, [])
                        if row.field_path == item.field
                    ),
                    "Field remains deferred after official-source review.",
                ),
                sources=item.sources,
            )
            for item in ordered
            if item.availability == "CONFLICT"
        ]
        retained_identity = [
            fact
            for fact in facts_by_model.get(original.model_id, [])
            if fact.decision_id == "R013"
        ]
        identity_deferred = any(
            row.decision == "DEFER_IDENTITY"
            for row in deferred_by_model.get(original.model_id, [])
        )
        if retained_identity or identity_deferred:
            sources = sorted(
                {
                    (source.source_id, source.source_file, source.evidence_status, source.locator): source
                    for item in ordered
                    for source in item.sources
                }.values(),
                key=lambda source: (source.source_id, source.locator),
            )
            conflicts.append(
                Conflict(
                    field="model_identity_or_revision",
                    reason=(
                        "Organizer revision remains unconfirmed after review; current official revision facts are not matching-safe."
                        if retained_identity
                        else "Current official AMR100 150 kg revision is not proven applicable to organizer AMR 100 100 kg identity."
                    ),
                    sources=sources,
                )
            )
        required_assessments = [item for item in ordered if item.field in original.required_fields]
        if original.status == "NOT_EQUIPMENT":
            status = "NOT_EQUIPMENT"
        elif conflicts:
            status = "CONFLICT_REVIEW"
        elif original.equipment_class is None:
            status = "UNSUPPORTED_CAPACITY_PROFILE"
        elif all(item.availability == "MATCHING_SAFE" for item in required_assessments):
            status = "RUNTIME_READY"
        else:
            status = "NEEDS_FACTS"
        missing = sorted(
            item.field
            for item in required_assessments
            if item.availability in {"MISSING", "LOCAL_CANDIDATE"}
        )
        models.append(
            original.model_copy(
                update={
                    "status": status,
                    "recommendation": _recommendation(status, required_assessments),
                    "present_fields": [item for item in ordered if item.availability != "MISSING"],
                    "missing_fields": missing,
                    "conflicts": sorted(conflicts, key=lambda item: (item.field, item.reason)),
                    "source_files": sorted(set(original.source_files) | {"staging-overlay.json"}),
                },
                deep=True,
            )
        )
    models.sort(key=lambda item: item.id)
    model_by_id = {item.model_id: item for item in models}
    positions = [
        model_by_id[item.model_id].model_copy(
            update={
                "id": item.id,
                "source_row_number": item.source_row_number,
                "source_files": sorted(
                    set(model_by_id[item.model_id].source_files) | set(item.source_files)
                ),
            },
            deep=True,
        )
        for item in base.positions
    ]
    statuses = [
        "RUNTIME_READY",
        "NEEDS_FACTS",
        "CONFLICT_REVIEW",
        "UNSUPPORTED_CAPACITY_PROFILE",
        "NOT_EQUIPMENT",
    ]
    recommendations = ["LOCAL_ADAPTER", "DEEP_RESEARCH", "HYBRID", "NO_ACTION"]
    model_status = Counter(item.status for item in models)
    position_status = Counter(item.status for item in positions)
    model_recommendations = Counter(item.recommendation for item in models)
    position_recommendations = Counter(item.recommendation for item in positions)
    stage_inputs = [
        (staging_path, "OVERLAY", True),
        (RESOLUTION, "PROVENANCE", False),
        (LEDGER, "PROVENANCE", False),
        (REVIEW, "PROVENANCE", False),
    ]
    inputs = list(base.inputs)
    for path, role, eligible in stage_inputs:
        inputs.append(
            InputFile(
                path=path.relative_to(ROOT).as_posix(),
                sha256=_sha256(path),
                size_bytes=path.stat().st_size,
                role=role,
                runtime_eligible=eligible,
            )
        )
    report = base.model_copy(
        update={
            "inputs": sorted(inputs, key=lambda item: item.path),
            "model_status_counts": {key: model_status[key] for key in statuses},
            "position_status_counts": {key: position_status[key] for key in statuses},
            "recommendation_counts": {
                "models": {key: model_recommendations[key] for key in recommendations},
                "positions": {key: position_recommendations[key] for key in recommendations},
            },
            "model_coverage": _coverage(models),
            "position_coverage": _coverage(positions),
            "exclusions": [
                "staging overlay is review-only and has not been imported into PostgreSQL",
                "two accepted-but-qualified fields are not matching-safe",
                "catalog runtime remains on backend/fleet",
                "capacity formulas, economics, procurement, and activation are outside this projection",
            ],
            "models": models,
            "positions": positions,
        },
        deep=True,
    )
    return AuditReport.model_validate(report.model_dump(mode="json"))


def staging_bytes(staging: StagingOverlay) -> bytes:
    return (
        json.dumps(staging.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def staging_summary(staging: StagingOverlay) -> str:
    counts = staging.counts
    return f"""# Official-source enrichment staging v1

Этот overlay создан только для review/validation. Он не импортирован в PostgreSQL, не опубликован и не активирован в runtime.

## Покрытие

- Принято полей: {counts.accepted_fields}.
- Matching-safe после review: {counts.matching_usable_fields}.
- Принято только для справки/неподтверждённой применимости: {counts.review_only_fields}.
- Отложено: {counts.deferred_fields}.
- Не найдено: {counts.remains_missing_fields}.
- Всего target fields: {counts.target_fields}.
- Моделей с принятыми фактами: {counts.models_with_accepted_facts}.

`R005` сохраняет только верхнюю температурную границу, а `R013` относится только к текущей официальной ревизии Ronavi H1500. Поэтому оба поля не допущены к matching.
"""


def post_summary(report: AuditReport) -> str:
    text = summary_text(report)
    marker = "## Decision gate"
    prefix = text.split(marker, 1)[0]
    return prefix + """## Decision gate

Это post-enrichment projection поверх versioned staging overlay. База данных и runtime не изменены. Следующий шаг — адаптировать 129 matching-safe facts в новый immutable ENRICHMENT bundle/version, выполнить validate-only import и повторить audit по фактически импортированному DRAFT. До этого capacity formulas и runtime activation запрещены.
"""


def _check(path: Path, expected: bytes) -> None:
    if not path.is_file() or path.read_bytes() != expected:
        raise ValueError(f"generated artifact differs: {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    staging = build_staging()
    staging_payload = staging_bytes(staging)
    schema_payload = schema_bytes(StagingOverlay)
    stage_summary_payload = staging_summary(staging).encode("utf-8")
    if args.write:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        STAGING.write_bytes(staging_payload)
        STAGING_SCHEMA.write_bytes(schema_payload)
        STAGING_SUMMARY.write_bytes(stage_summary_payload)
    else:
        _check(STAGING, staging_payload)
        _check(STAGING_SCHEMA, schema_payload)
        _check(STAGING_SUMMARY, stage_summary_payload)
    report = project_eligibility(staging)
    report_payload = report_bytes(report)
    summary_payload = post_summary(report).encode("utf-8")
    if args.write:
        POST_REPORT.write_bytes(report_payload)
        POST_SUMMARY.write_bytes(summary_payload)
    else:
        _check(POST_REPORT, report_payload)
        _check(POST_SUMMARY, summary_payload)
    print(
        json.dumps(
            {
                "staging_counts": staging.counts.model_dump(),
                "model_status_counts": report.model_status_counts,
                "position_status_counts": report.position_status_counts,
                "model_coverage": report.model_coverage.model_dump(),
                "position_coverage": report.position_coverage.model_dump(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
