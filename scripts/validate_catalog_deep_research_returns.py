"""Validate ChatGPT Deep Research returns before any evidence review/import."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "data" / "research" / "catalog-runtime-eligibility-v1"
FORBIDDEN_INLINE_MARKERS = ("\ue200cite", "\ue200filecite", "sandbox:/")
SEARCH_RESULT_HOSTS = {"bing.com", "google.com", "yandex.com", "yandex.ru"}


class ReturnValidationError(ValueError):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Evidence(StrictModel):
    raw_value: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    source_type: Literal[
        "OFFICIAL_MODEL_PAGE",
        "OFFICIAL_DATASHEET",
        "OFFICIAL_MANUAL",
        "OFFICIAL_CATALOG",
        "AUTHORIZED_PARTNER_PAGE",
    ]
    source_locator: str = Field(min_length=1)
    publication_or_update_date: date | None
    accessed_at: date


class FieldResult(StrictModel):
    field_path: str = Field(min_length=1)
    evidence_status: Literal[
        "VERIFIED_OFFICIAL",
        "VERIFIED_AUTHORIZED_PARTNER",
        "CONFLICT",
        "AMBIGUOUS_MODEL_MATCH",
        "NOT_FOUND",
    ]
    normalized_value: Any
    normalized_unit: str | None
    evidence: list[Evidence]
    confidence: float = Field(ge=0, le=1)
    notes: str


class ModelResult(StrictModel):
    organizer_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    identity_status: Literal[
        "EXACT_MODEL_MATCH",
        "EXACT_MODEL_MATCH_WITH_CONFLICTS",
        "AMBIGUOUS_MODEL_MATCH",
        "MODEL_NOT_FOUND",
    ]
    matched_manufacturer: str | None
    matched_model: str | None
    field_results: list[FieldResult]
    unresolved_issues: list[str]


class ResearchReturn(StrictModel):
    schema_version: Literal["catalog-official-source-research-return-v1"]
    batch_id: str = Field(min_length=1)
    research_completed_at: datetime
    results: list[ModelResult]


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReturnValidationError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ReturnValidationError(f"JSON root must be an object: {path.name}")
    return value


def _reject_forbidden_inline_markers(value: Any, location: str) -> None:
    if isinstance(value, str):
        marker = next((item for item in FORBIDDEN_INLINE_MARKERS if item in value), None)
        if marker:
            raise ReturnValidationError(
                f"forbidden inline citation/download marker {marker!r}: {location}"
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_inline_markers(item, f"{location}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_forbidden_inline_markers(item, f"{location}.{key}")


def validate_return(batch_path: Path, result_path: Path) -> dict[str, Any]:
    batch = _load(batch_path)
    raw_result = _load(result_path)
    _reject_forbidden_inline_markers(raw_result, result_path.name)
    try:
        result = ResearchReturn.model_validate_json(result_path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise ReturnValidationError(f"return schema validation failed: {result_path.name}") from exc
    batch_id = str(batch["batch_id"])
    if result.batch_id != batch_id or result_path.name != f"{batch_id}.result.json":
        raise ReturnValidationError(f"batch identity mismatch: {result_path.name}")
    if result.research_completed_at.tzinfo is None:
        raise ReturnValidationError(
            f"research_completed_at must include timezone: {result_path.name}"
        )
    expected = {row["organizer_id"]: row for row in batch["models"]}
    actual_ids = [row.organizer_id for row in result.results]
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected):
        raise ReturnValidationError(f"model coverage mismatch: {batch_id}")
    statuses: dict[str, int] = {}
    evidence_count = 0
    for model in result.results:
        target_fields = set(expected[model.organizer_id]["research_targets"])
        actual_fields = [row.field_path for row in model.field_results]
        if len(actual_fields) != len(set(actual_fields)) or set(actual_fields) != target_fields:
            raise ReturnValidationError(
                f"target field coverage mismatch: {batch_id}/{model.organizer_id}"
            )
        field_statuses = {field.evidence_status for field in model.field_results}
        if model.identity_status.startswith("EXACT_MODEL_MATCH") and (
            not model.matched_manufacturer or not model.matched_model
        ):
            raise ReturnValidationError(
                f"exact identity requires matched names: {model.organizer_id}"
            )
        if model.identity_status == "MODEL_NOT_FOUND" and (
            model.matched_model is not None
            or field_statuses != {"NOT_FOUND"}
        ):
            raise ReturnValidationError(
                f"MODEL_NOT_FOUND must contain only NOT_FOUND fields: {model.organizer_id}"
            )
        if (
            model.identity_status == "AMBIGUOUS_MODEL_MATCH"
            and "AMBIGUOUS_MODEL_MATCH" not in field_statuses
        ):
            raise ReturnValidationError(
                f"ambiguous identity requires ambiguous field evidence: {model.organizer_id}"
            )
        if (
            model.identity_status == "EXACT_MODEL_MATCH_WITH_CONFLICTS"
            and "CONFLICT" not in field_statuses
        ):
            raise ReturnValidationError(
                f"conflicting identity requires a CONFLICT field: {model.organizer_id}"
            )
        if model.identity_status == "EXACT_MODEL_MATCH" and "CONFLICT" in field_statuses:
            raise ReturnValidationError(
                f"EXACT_MODEL_MATCH cannot contain CONFLICT fields: {model.organizer_id}"
            )
        if model.identity_status.startswith("EXACT_MODEL_MATCH") and (
            "AMBIGUOUS_MODEL_MATCH" in field_statuses
        ):
            raise ReturnValidationError(
                f"exact identity cannot contain ambiguous fields: {model.organizer_id}"
            )
        for field in model.field_results:
            statuses[field.evidence_status] = statuses.get(field.evidence_status, 0) + 1
            evidence_count += len(field.evidence)
            if field.evidence_status == "NOT_FOUND":
                if field.evidence or field.normalized_value is not None or field.normalized_unit is not None:
                    raise ReturnValidationError(
                        f"NOT_FOUND must not contain evidence/value: {model.organizer_id}/{field.field_path}"
                    )
                continue
            if field.evidence_status.startswith("VERIFIED_") and field.normalized_value is None:
                raise ReturnValidationError(
                    f"verified field requires a value: {model.organizer_id}/{field.field_path}"
                )
            if field.evidence_status in {"CONFLICT", "AMBIGUOUS_MODEL_MATCH"} and (
                field.normalized_value is not None or field.normalized_unit is not None
            ):
                raise ReturnValidationError(
                    f"unresolved field must not choose a value: {model.organizer_id}/{field.field_path}"
                )
            minimum = 2 if field.evidence_status == "CONFLICT" else 1
            if len(field.evidence) < minimum:
                raise ReturnValidationError(
                    f"insufficient evidence: {model.organizer_id}/{field.field_path}"
                )
            evidence_keys = [
                (
                    evidence.source_url,
                    evidence.source_locator,
                    evidence.raw_value,
                    evidence.source_type,
                )
                for evidence in field.evidence
            ]
            if len(evidence_keys) != len(set(evidence_keys)):
                raise ReturnValidationError(
                    f"duplicate evidence: {model.organizer_id}/{field.field_path}"
                )
            source_types = {evidence.source_type for evidence in field.evidence}
            if field.evidence_status == "VERIFIED_OFFICIAL" and not any(
                source_type.startswith("OFFICIAL_") for source_type in source_types
            ):
                raise ReturnValidationError(
                    f"official verification requires official evidence: {model.organizer_id}/{field.field_path}"
                )
            if (
                field.evidence_status == "VERIFIED_AUTHORIZED_PARTNER"
                and "AUTHORIZED_PARTNER_PAGE" not in source_types
            ):
                raise ReturnValidationError(
                    f"partner verification requires partner evidence: {model.organizer_id}/{field.field_path}"
                )
            for evidence in field.evidence:
                if len(evidence.raw_value.split()) > 20:
                    raise ReturnValidationError(
                        f"raw_value exceeds 20 words: {model.organizer_id}/{field.field_path}"
                    )
                parsed = urlparse(evidence.source_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ReturnValidationError(
                        f"invalid evidence URL: {model.organizer_id}/{field.field_path}"
                    )
                host = (parsed.hostname or "").lower().removeprefix("www.")
                if host in SEARCH_RESULT_HOSTS:
                    raise ReturnValidationError(
                        f"search result URL is not direct evidence: {model.organizer_id}/{field.field_path}"
                    )
    return {
        "batch_id": batch_id,
        "models": len(result.results),
        "target_fields": sum(len(row.field_results) for row in result.results),
        "evidence_records": evidence_count,
        "status_counts": dict(sorted(statuses.items())),
    }


def validate_directory(
    handoff: Path,
    require_complete: bool,
    returns_dir: Path | None = None,
) -> list[dict[str, Any]]:
    batches = {
        path.stem: path for path in sorted((handoff / "batches").glob("*.json"))
    }
    returns_root = returns_dir if returns_dir is not None else handoff / "returns"
    returns = {
        path.name.removesuffix(".result.json"): path
        for path in sorted(returns_root.glob("*.result.json"))
    }
    unknown = sorted(returns.keys() - batches.keys())
    missing = sorted(batches.keys() - returns.keys())
    if unknown or (require_complete and missing):
        raise ReturnValidationError(
            f"return file set differs: missing={missing}, unknown={unknown}"
        )
    return [validate_return(batches[key], returns[key]) for key in sorted(returns)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    parser.add_argument("--returns-dir", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    summaries = validate_directory(
        args.handoff.resolve(),
        args.require_complete,
        args.returns_dir.resolve() if args.returns_dir else None,
    )
    print(json.dumps({"validated": summaries}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
