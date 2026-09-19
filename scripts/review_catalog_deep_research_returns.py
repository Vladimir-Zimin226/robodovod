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
DECISIONS_OUTPUT = (
    ROOT / "data" / "review" / "catalog-official-source-enrichment-decisions-v1.md"
)
DECISIONS_LEDGER = (
    ROOT
    / "data"
    / "review"
    / "catalog-official-source-enrichment-reviewed-decisions-v1.json"
)
RESOLUTION_OUTPUT = (
    ROOT / "data" / "review" / "catalog-official-source-enrichment-resolution-v1.json"
)
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
    projected_models: Counter[str] = Counter()
    projected_positions: Counter[str] = Counter()
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
                known_facts = sorted(
                    (
                        row
                        for row in expected_model["known_facts_do_not_silently_overwrite"]
                        if row["field_path"] == field_path
                    ),
                    key=lambda row: _canonical_value(row),
                )
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
                        "known_facts": known_facts,
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
            field_evidence_statuses = {row["evidence_status"] for row in fields}
            if (
                returned_model["identity_status"]
                in {"AMBIGUOUS_MODEL_MATCH", "EXACT_MODEL_MATCH_WITH_CONFLICTS"}
                or field_evidence_statuses & {"CONFLICT", "AMBIGUOUS_MODEL_MATCH"}
            ):
                projected_status = "CONFLICT_REVIEW"
            elif "NOT_FOUND" in field_evidence_statuses:
                projected_status = "NEEDS_FACTS"
            else:
                projected_status = "RUNTIME_READY"
            projected_models[projected_status] += 1
            projected_positions[projected_status] += len(expected_model["position_ids"])
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
                    "projected_status_after_manual_acceptance": projected_status,
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
        "projected_research_subset_status_counts": {
            "models": dict(sorted(projected_models.items())),
            "positions": dict(sorted(projected_positions.items())),
        },
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
    projected = report["projected_research_subset_status_counts"]
    lines += [
        "",
        "## Проекция исследовательского subset после ручной приёмки",
        "",
        "| Статус | Модели | Позиции |",
        "|---|---:|---:|",
    ]
    for status in sorted(set(projected["models"]) | set(projected["positions"])):
        lines.append(
            f"| `{status}` | {projected['models'].get(status, 0)} | "
            f"{projected['positions'].get(status, 0)} |"
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


def _display_value(value: Any, unit: str | None) -> str:
    if value is None:
        return "—"
    rendered = (
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, (dict, list))
        else str(value)
    )
    return f"{rendered} {unit}" if unit else rendered


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _validate_decision_ledger(
    report: dict[str, Any],
    review_rows: list[tuple[str, dict[str, Any], dict[str, Any]]],
    accept_rows: list[tuple[str, dict[str, Any], dict[str, Any]]],
    ledger: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    expected: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for prefix, rows in (("R", review_rows), ("A", accept_rows)):
        for number, (_, model, field) in enumerate(rows, start=1):
            expected[f"{prefix}{number:03d}"] = (model, field)
    recorded: dict[str, dict[str, Any]] = {}
    for decision in ledger.get("decisions", []):
        decision_id = decision.get("decision_id")
        if decision_id in recorded:
            raise ValueError(f"duplicate decision_id in ledger: {decision_id}")
        if decision_id not in expected:
            raise ValueError(f"unknown decision_id in ledger: {decision_id}")
        model, field = expected[decision_id]
        identity = (
            decision.get("organizer_id"),
            decision.get("model_name"),
            decision.get("field_path"),
        )
        expected_identity = (
            model["organizer_id"],
            model["name"],
            field["field_path"],
        )
        if identity != expected_identity:
            raise ValueError(
                f"decision identity mismatch for {decision_id}: "
                f"{identity!r} != {expected_identity!r}"
            )
        recorded[decision_id] = decision
    report_sha256 = hashlib.sha256(_canonical_value(report).encode("utf-8")).hexdigest()
    for rule in ledger.get("bulk_decisions", []):
        if rule.get("decision") != "ACCEPT_EXACT_CANDIDATE":
            raise ValueError(f"unsupported bulk decision: {rule.get('decision')}")
        if rule.get("review_canonical_sha256") != report_sha256:
            raise ValueError(
                f"bulk decision {rule.get('decision_id')} review hash mismatch"
            )
        start = int(rule["candidate_id_from"].removeprefix("A"))
        end = int(rule["candidate_id_to"].removeprefix("A"))
        if not (1 <= start <= end <= len(accept_rows)):
            raise ValueError(f"invalid bulk candidate range: {start}..{end}")
        applied = 0
        for number in range(start, end + 1):
            decision_id = f"A{number:03d}"
            if decision_id in recorded:
                raise ValueError(f"bulk decision overlaps recorded {decision_id}")
            _, model, field = accept_rows[number - 1]
            if (
                field["evidence_status"] != "VERIFIED_OFFICIAL"
                or not field["evidence"]
                or field["warnings"]
                or field["normalized_value"] is None
                or field["known_fact_comparison"]
                not in {"NO_KNOWN_FACT", "NO_COMPARABLE_KNOWN_VALUE", "MATCHES_KNOWN_FACT"}
            ):
                raise ValueError(f"bulk acceptance guard failed for {decision_id}")
            recorded[decision_id] = {
                "decision_id": decision_id,
                "organizer_id": model["organizer_id"],
                "model_name": model["name"],
                "field_path": field["field_path"],
                "decision": "ACCEPT_EXACT_CANDIDATE",
                "selected_value": field["normalized_value"],
                "selected_unit": field["normalized_unit"],
                "selected_evidence": field["evidence"],
                "bulk_decision_id": rule["decision_id"],
                "import_status": "NOT_IMPORTED",
            }
            applied += 1
        if applied != rule["candidate_count"]:
            raise ValueError(
                f"bulk decision {rule.get('decision_id')} count mismatch: "
                f"{applied} != {rule.get('candidate_count')}"
            )
    return recorded


def render_decision_queue(
    report: dict[str, Any], ledger: dict[str, Any] | None = None
) -> str:
    """Render a stable human queue without authorizing any catalog mutation."""
    rows = [
        (batch["batch_id"], model, field)
        for batch in report["batches"]
        for model in batch["models"]
        for field in model["field_reviews"]
    ]
    review_rows = [
        row
        for row in rows
        if row[2]["review_decision"]
        in {"CONFLICT_REVIEW", "IDENTITY_REVIEW", "POTENTIAL_CONFLICT_REVIEW"}
    ]
    accept_rows = [row for row in rows if row[2]["review_decision"] == "ACCEPT_CANDIDATE"]
    missing_rows = [row for row in rows if row[2]["review_decision"] == "REMAINS_MISSING"]
    recorded = _validate_decision_ledger(
        report, review_rows, accept_rows, ledger or {}
    )
    resolved_reviews = sum(
        f"R{number:03d}" in recorded
        for number in range(1, len(review_rows) + 1)
    )
    resolved_accepts = sum(
        f"A{number:03d}" in recorded
        for number in range(1, len(accept_rows) + 1)
    )
    lines = [
        "# Очередь ручных решений по обогащению каталога",
        "",
        "> Review-only: решения в этом файле сами по себе не изменяют catalog, runtime или backend/fleet.",
        "",
        "## Как работать",
        "",
        "Разбираем по одному пункту в порядке ID. Для каждого пункта допустимы решения: `ACCEPT`, `REJECT` или `DEFER/VERIFY`. При `ACCEPT` фиксируется конкретное значение и evidence; конфликт целиком без выбора применимой ревизии принимать нельзя.",
        "",
        f"- Конфликты/identity всего: {len(review_rows)}.",
        f"- Уже зафиксировано ручных решений: {resolved_reviews}.",
        f"- Требуют проверки конфликта/identity: {len(review_rows) - resolved_reviews}.",
        f"- Кандидаты на принятие всего: {len(accept_rows)}.",
        f"- Уже рассмотрено обычных кандидатов: {resolved_accepts}.",
        f"- Ожидают решения: {len(accept_rows) - resolved_accepts}.",
        f"- Остаются без фактов: {len(missing_rows)}.",
        "",
        "## Сначала: конфликты и identity",
        "",
    ]
    for number, (batch_id, model, field) in enumerate(review_rows, start=1):
        decision_id = f"R{number:03d}"
        recorded_decision = recorded.get(decision_id)
        if recorded_decision:
            decision_text = (
                f"**{recorded_decision['decision']}** — "
                f"{_display_value(recorded_decision.get('selected_value'), recorded_decision.get('selected_unit'))}. "
                f"{recorded_decision['rationale']}"
            )
        else:
            decision_text = "**не принято**."
        lines += [
            f"### {decision_id} — {model['name']} — `{field['field_path']}`",
            "",
            f"- Batch: `{batch_id}`; organizer ID: `{model['organizer_id']}`.",
            f"- Catalog positions: {', '.join(f'`{value}`' for value in model['position_ids'])}.",
            f"- Производитель: {model['manufacturer']}; класс: `{model['equipment_class']}`.",
            f"- Identity: `{model['identity_status']}`; найдено: {_display_value(model['matched_model'], None)}.",
            f"- Требуется: `{field['review_decision']}`; evidence status: `{field['evidence_status']}`.",
            f"- Кандидат: `{_display_value(field['normalized_value'], field['normalized_unit'])}`.",
            f"- Сравнение с локальным fact: `{field['known_fact_comparison']}`.",
        ]
        if field["known_facts"]:
            lines += ["- Локальные facts:"]
            for known in field["known_facts"]:
                lines.append(
                    "  - `"
                    + _display_value(known.get("normalized_value"), known.get("normalized_unit"))
                    + "` — "
                    + _escape_table(known.get("source_ref") or known.get("source") or "source указан в batch")
                )
        lines += [f"- Пояснение: {_escape_table(field['notes'])}", "- Evidence:"]
        if field["evidence"]:
            for evidence in field["evidence"]:
                lines.append(
                    f"  - «{_escape_table(evidence['raw_value'])}» — "
                    f"[{_escape_table(evidence['source_title'])}]({evidence['source_url']}), "
                    f"{_escape_table(evidence['publisher'])}, "
                    f"{_escape_table(evidence['source_locator'])}."
                )
        else:
            lines.append("  - Нет допустимого evidence; значение принимать нельзя.")
        lines += [
            "- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.",
            f"- Решение: {decision_text}",
            "",
        ]

    lines += ["## Затем: кандидаты на принятие", ""]
    current_model: str | None = None
    for number, (batch_id, model, field) in enumerate(accept_rows, start=1):
        model_key = f"{batch_id}:{model['organizer_id']}"
        if model_key != current_model:
            lines += [
                f"### {model['name']}",
                "",
                f"`{model['organizer_id']}` · positions: {', '.join(f'`{value}`' for value in model['position_ids'])} · identity `{model['identity_status']}`",
                "",
                "| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |",
                "|---|---|---|---|---|---|---|",
            ]
            current_model = model_key
        evidence = field["evidence"][0] if field["evidence"] else None
        source = (
            f"[{_escape_table(evidence['source_title'])}]({evidence['source_url']})"
            if evidence
            else "—"
        )
        check = field["notes"] or "Проверить применимость к точной модели."
        recorded_decision = recorded.get(f"A{number:03d}")
        decision = (
            f"`{recorded_decision['decision']}`" if recorded_decision else "не принято"
        )
        lines.append(
            f"| `A{number:03d}` | `{field['field_path']}` | "
            f"{_escape_table(_display_value(field['normalized_value'], field['normalized_unit']))} | "
            f"`{field['known_fact_comparison']}` | {source} | {_escape_table(check)} | {decision} |"
        )
    lines += [
        "",
        "## Ненайденные поля",
        "",
        "Эти поля не являются кандидатами на принятие. Они остаются `NEEDS_FACTS`; запрещено заменять их типовыми значениями класса.",
        "",
        "| Робот | Organizer ID | Количество | Поля |",
        "|---|---|---:|---|",
    ]
    missing_by_model: dict[tuple[str, str], tuple[dict[str, Any], list[str]]] = {}
    for _, model, field in missing_rows:
        key = (model["organizer_id"], model["name"])
        missing_by_model.setdefault(key, (model, []))[1].append(field["field_path"])
    for key in sorted(missing_by_model, key=lambda row: (row[1], row[0])):
        model, fields = missing_by_model[key]
        lines.append(
            f"| {_escape_table(model['name'])} | `{model['organizer_id']}` | {len(fields)} | "
            + ", ".join(f"`{field}`" for field in sorted(fields))
            + " |"
        )
    lines += ["", "## Статус", "", "Все пункты изначально имеют статус **не принято**. Решения фиксируются следующими итерациями по одному ID.", ""]
    return "\n".join(lines)


def build_resolution(
    report: dict[str, Any], ledger: dict[str, Any]
) -> dict[str, Any]:
    rows = [
        (batch["batch_id"], model, field)
        for batch in report["batches"]
        for model in batch["models"]
        for field in model["field_reviews"]
    ]
    review_rows = [
        row
        for row in rows
        if row[2]["review_decision"]
        in {"CONFLICT_REVIEW", "IDENTITY_REVIEW", "POTENTIAL_CONFLICT_REVIEW"}
    ]
    accept_rows = [row for row in rows if row[2]["review_decision"] == "ACCEPT_CANDIDATE"]
    missing_rows = [row for row in rows if row[2]["review_decision"] == "REMAINS_MISSING"]
    recorded = _validate_decision_ledger(report, review_rows, accept_rows, ledger)
    expected_ids = {
        *(f"R{number:03d}" for number in range(1, len(review_rows) + 1)),
        *(f"A{number:03d}" for number in range(1, len(accept_rows) + 1)),
    }
    unresolved = sorted(expected_ids - recorded.keys())
    accepted = sorted(
        (
            value
            for value in recorded.values()
            if not value["decision"].startswith(("DEFER", "REJECT"))
        ),
        key=lambda row: row["decision_id"],
    )
    deferred = sorted(
        (value for value in recorded.values() if value["decision"].startswith("DEFER")),
        key=lambda row: row["decision_id"],
    )
    rejected = sorted(
        (value for value in recorded.values() if value["decision"].startswith("REJECT")),
        key=lambda row: row["decision_id"],
    )
    missing = [
        {
            "batch_id": batch_id,
            "organizer_id": model["organizer_id"],
            "model_name": model["name"],
            "field_path": field["field_path"],
            "notes": field["notes"],
        }
        for batch_id, model, field in missing_rows
    ]
    counts = {
        "research_target_fields": len(rows),
        "accepted_fields": len(accepted),
        "deferred_fields": len(deferred),
        "rejected_fields": len(rejected),
        "remains_missing_fields": len(missing),
        "unresolved_decision_fields": len(unresolved),
    }
    if sum(
        counts[key]
        for key in (
            "accepted_fields",
            "deferred_fields",
            "rejected_fields",
            "remains_missing_fields",
            "unresolved_decision_fields",
        )
    ) != counts["research_target_fields"]:
        raise ValueError(f"resolution coverage mismatch: {counts}")
    return {
        "schema_version": "catalog-official-source-enrichment-resolution-v1",
        "policy": {
            "mode": "REVIEW_ONLY",
            "writes_runtime_or_catalog": False,
            "accepted_values_are_exact_review_candidates": True,
        },
        "counts": counts,
        "unresolved_decision_ids": unresolved,
        "accepted": accepted,
        "deferred": deferred,
        "rejected": rejected,
        "remains_missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    parser.add_argument("--returns-dir", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--decisions-output", type=Path, default=DECISIONS_OUTPUT)
    parser.add_argument("--decisions-ledger", type=Path, default=DECISIONS_LEDGER)
    parser.add_argument("--resolution-output", type=Path, default=RESOLUTION_OUTPUT)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    handoff = args.handoff.resolve()
    returns_dir = args.returns_dir.resolve() if args.returns_dir else handoff / "returns"
    report = build_review(handoff, returns_dir, args.require_complete)
    write_review(report, args.output.resolve())
    ledger_path = args.decisions_ledger.resolve()
    ledger = _load(ledger_path) if ledger_path.exists() else None
    args.decisions_output.resolve().write_text(
        render_decision_queue(report, ledger), encoding="utf-8", newline="\n"
    )
    resolution = build_resolution(report, ledger or {})
    resolution["input_sha256"] = {
        "review": _sha256(args.output.resolve()),
        "decision_ledger": _sha256(ledger_path),
    }
    args.resolution_output.resolve().write_text(
        json.dumps(resolution, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report["coverage"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
