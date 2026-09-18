"""Build a deterministic, review-only assessment of validated research returns."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.validate_catalog_deep_research_returns import validate_return

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "data" / "research" / "catalog-runtime-eligibility-v1"
OUTPUT = ROOT / "data" / "review" / "catalog-official-source-enrichment-review-v1.json"
SEARCH_HOSTS = {"bing.com", "google.com", "yandex.ru", "yandex.com"}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _known_comparison(field: dict[str, Any], known: list[dict[str, Any]]) -> str:
    relevant = [row for row in known if row["field_path"] == field["field_path"]]
    if not relevant:
        return "NO_KNOWN_FACT"
    if field["evidence_status"] not in {"VERIFIED_OFFICIAL", "VERIFIED_AUTHORIZED_PARTNER"}:
        return "NOT_COMPARABLE"
    new_pair = (
        _canonical_value(field["normalized_value"]),
        field["normalized_unit"],
    )
    old_pairs = {
        (_canonical_value(row.get("normalized_value")), row.get("normalized_unit"))
        for row in relevant
        if row.get("normalized_value") is not None
    }
    if new_pair in old_pairs:
        return "MATCHES_KNOWN_FACT"
    return "DIFFERS_FROM_KNOWN_FACT" if old_pairs else "NO_COMPARABLE_KNOWN_VALUE"


def _decision(status: str, comparison: str) -> str:
    if status == "CONFLICT":
        return "CONFLICT_REVIEW"
    if status == "AMBIGUOUS_MODEL_MATCH":
        return "IDENTITY_REVIEW"
    if status == "NOT_FOUND":
        return "REMAINS_MISSING"
    if comparison == "DIFFERS_FROM_KNOWN_FACT":
        return "POTENTIAL_CONFLICT_REVIEW"
    return "ACCEPT_CANDIDATE"


def _warnings(field: dict[str, Any]) -> list[str]:
    warnings: set[str] = set()
    if field["evidence_status"] == "VERIFIED_AUTHORIZED_PARTNER":
        warnings.add("PARTNER_AUTHORIZATION_REQUIRES_MANUAL_CHECK")
    if field["evidence_status"] == "NOT_FOUND" and len(field["notes"].strip()) < 30:
        warnings.add("NOT_FOUND_SEARCH_DETAIL_TOO_SHORT")
    for evidence in field["evidence"]:
        host = (urlparse(evidence["source_url"]).hostname or "").lower()
        if host.removeprefix("www.") in SEARCH_HOSTS:
            warnings.add("SEARCH_RESULT_URL_IS_NOT_DIRECT_EVIDENCE")
    return sorted(warnings)


def build_review(handoff: Path, returns_dir: Path, require_complete: bool) -> dict[str, Any]:
    batch_paths = sorted((handoff / "batches").glob("*.json"))
    batch_by_id = {path.stem: path for path in batch_paths}
    result_paths = sorted(returns_dir.glob("*.result.json"))
    result_by_id = {
        path.name.removesuffix(".result.json"): path for path in result_paths
    }
    unknown = sorted(result_by_id.keys() - batch_by_id.keys())
    missing = sorted(batch_by_id.keys() - result_by_id.keys())
    if unknown or (require_complete and missing):
        raise ValueError(f"return file set differs: missing={missing}, unknown={unknown}")

    batches: list[dict[str, Any]] = []
    total_decisions: Counter[str] = Counter()
    total_statuses: Counter[str] = Counter()
    total_warnings: Counter[str] = Counter()
    for batch_id in sorted(result_by_id):
        batch_path = batch_by_id[batch_id]
        result_path = result_by_id[batch_id]
        validation = validate_return(batch_path, result_path)
        batch = _load(batch_path)
        result = _load(result_path)
        expected = {row["organizer_id"]: row for row in batch["models"]}
        returned = {row["organizer_id"]: row for row in result["results"]}
        reviewed_models: list[dict[str, Any]] = []
        batch_decisions: Counter[str] = Counter()
        batch_statuses: Counter[str] = Counter()
        for organizer_id in sorted(expected):
            expected_model = expected[organizer_id]
            returned_model = returned[organizer_id]
            fields: list[dict[str, Any]] = []
            returned_fields = {
                row["field_path"]: row for row in returned_model["field_results"]
            }
            for field_path in sorted(expected_model["research_targets"]):
                field = returned_fields[field_path]
                comparison = _known_comparison(
                    field, expected_model["known_facts_do_not_silently_overwrite"]
                )
                decision = _decision(field["evidence_status"], comparison)
                warnings = _warnings(field)
                batch_decisions[decision] += 1
                batch_statuses[field["evidence_status"]] += 1
                total_decisions[decision] += 1
                total_statuses[field["evidence_status"]] += 1
                total_warnings.update(warnings)
                fields.append(
                    {
                        "field_path": field_path,
                        "evidence_status": field["evidence_status"],
                        "normalized_value": field["normalized_value"],
                        "normalized_unit": field["normalized_unit"],
                        "known_fact_comparison": comparison,
                        "review_decision": decision,
                        "warnings": warnings,
                        "evidence": sorted(
                            field["evidence"],
                            key=lambda row: (
                                row["source_url"], row["source_locator"], row["raw_value"]
                            ),
                        ),
                        "notes": field["notes"],
                    }
                )
            reviewed_models.append(
                {
                    "organizer_id": organizer_id,
                    "position_ids": sorted(expected_model["position_ids"]),
                    "name": expected_model["name"],
                    "manufacturer": expected_model["manufacturer"],
                    "equipment_class": expected_model["equipment_class"],
                    "identity_status": returned_model["identity_status"],
                    "matched_manufacturer": returned_model["matched_manufacturer"],
                    "matched_model": returned_model["matched_model"],
                    "unresolved_issues": returned_model["unresolved_issues"],
                    "field_reviews": fields,
                }
            )
        batches.append(
            {
                "batch_id": batch_id,
                "mode": batch["mode"],
                "input_sha256": {
                    "batch": _sha256(batch_path),
                    "return": _sha256(result_path),
                },
                "validation": validation,
                "review_decision_counts": dict(sorted(batch_decisions.items())),
                "field_status_counts": dict(sorted(batch_statuses.items())),
                "models": reviewed_models,
            }
        )
    return {
        "schema_version": "catalog-official-source-enrichment-review-v1",
        "review_policy": {
            "mode": "REVIEW_ONLY",
            "writes_runtime_or_catalog": False,
            "automatic_acceptance": False,
            "known_facts_are_context_only": True,
        },
        "coverage": {
            "available_batches": len(batches),
            "expected_batches": len(batch_by_id),
            "missing_batch_ids": missing,
            "models": sum(len(batch["models"]) for batch in batches),
            "target_fields": sum(
                len(model["field_reviews"])
                for batch in batches
                for model in batch["models"]
            ),
        },
        "field_status_counts": dict(sorted(total_statuses.items())),
        "review_decision_counts": dict(sorted(total_decisions.items())),
        "warning_counts": dict(sorted(total_warnings.items())),
        "batches": batches,
    }


def render_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    lines = [
        "# Review результатов official-source research",
        "",
        "> Это staging/review-отчёт. Он не изменяет base, overlay, backend, fleet или runtime.",
        "",
        "## Покрытие",
        "",
        f"- Пакеты: {coverage['available_batches']} из {coverage['expected_batches']}.",
        f"- Модели: {coverage['models']}.",
        f"- Target fields: {coverage['target_fields']}.",
        f"- Отсутствующие пакеты: {', '.join(coverage['missing_batch_ids']) or 'нет'}.",
        "",
        "## Итоги полей",
        "",
        "| Решение review | Количество |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{key}` | {value} |"
        for key, value in report["review_decision_counts"].items()
    )
    lines += ["", "## По моделям", "", "| Batch | Organizer ID | Модель | Identity | Accept | Review | Missing |", "|---|---|---|---|---:|---:|---:|"]
    for batch in report["batches"]:
        for model in batch["models"]:
            decisions = Counter(row["review_decision"] for row in model["field_reviews"])
            manual = sum(
                value for key, value in decisions.items() if key not in {"ACCEPT_CANDIDATE", "REMAINS_MISSING"}
            )
            lines.append(
                f"| `{batch['batch_id']}` | `{model['organizer_id']}` | "
                f"{str(model['name']).replace('|', '\\|')} | `{model['identity_status']}` | "
                f"{decisions['ACCEPT_CANDIDATE']} | {manual} | {decisions['REMAINS_MISSING']} |"
            )
    lines += ["", "## Ограничение", "", "`ACCEPT_CANDIDATE` означает только пригодность для ручной приёмки evidence. Это не runtime-ready и не разрешение на импорт.", ""]
    return "\n".join(lines)


def write_review(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    output.with_suffix(".md").write_text(
        render_markdown(report), encoding="utf-8", newline="\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    parser.add_argument("--returns-dir", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    handoff = args.handoff.resolve()
    returns_dir = args.returns_dir.resolve() if args.returns_dir else handoff / "returns"
    report = build_review(handoff, returns_dir, args.require_complete)
    write_review(report, args.output.resolve())
    print(json.dumps(report["coverage"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
