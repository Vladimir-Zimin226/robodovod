"""Conservatively repair two exhausted Deep Research returns from local evidence only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.validate_catalog_deep_research_returns import validate_return

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "data" / "research" / "catalog-runtime-eligibility-v1"

EXPECTED_SOURCE_HASHES = {
    "deep-other-01": "bf557c74bca865c454eb5085f14dd94b5edfd88bc9fd71380e7bb850f2fe5017",
    "hybrid-conflicts-01": "f9874dce352828efb9302998a3b8842a8e1e4257f77e9a36c2036048e6fa13ad",
}

SOURCE_MAP = {
    "CR-02": ("https://arobosys.ru/robot", "ООО «АРС Смарт Роботикс»", "OFFICIAL_MODEL_PAGE"),
    "Робот-штабелёр": ("https://robocv.ru/robot-shtabelyor", "ООО «РобоСиВи»", "OFFICIAL_MODEL_PAGE"),
    "Спецификация робота-штабелёра RoboCV": (
        "https://robocv.ru/wp-content/uploads/2021/05/robot-shtabelyor-robocv-specifikaciya.pdf",
        "ООО «РобоСиВи»",
        "OFFICIAL_DATASHEET",
    ),
    "Ronavi H1500": ("https://ronavi-robotics.ru/catalogue/h1500", "ООО «Ронави Роботикс»", "OFFICIAL_MODEL_PAGE"),
    "AMR100": ("https://xn--l1aeahg.xn--p1ai/amr-100/", "ООО «Морос»", "OFFICIAL_MODEL_PAGE"),
    "Робот-тягач": ("https://robocv.ru/robot-tyagach", "ООО «РобоСиВи»", "OFFICIAL_MODEL_PAGE"),
    "Спецификация робота-тягача RoboCV": (
        "https://robocv.ru/wp-content/uploads/2021/05/robot-tyagach-robocv-specifikaciya.pdf",
        "ООО «РобоСиВи»",
        "OFFICIAL_DATASHEET",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _extract(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    if text.count("CATALOG_RESULT_JSON_BEGIN") != 1 or text.count("CATALOG_RESULT_JSON_END") != 1:
        raise ValueError(f"invalid marker count: {path}")
    match = re.search(r"```json\s*", text)
    if match is None:
        raise ValueError(f"JSON fence absent: {path}")
    end = text.find("```", match.end())
    value = json.loads(text[match.end() : end])
    if not isinstance(value, dict):
        raise ValueError(f"embedded JSON root must be object: {path}")
    return value


def _not_found(field_path: str, reason: str) -> dict[str, Any]:
    return {
        "field_path": field_path,
        "evidence_status": "NOT_FOUND",
        "normalized_value": None,
        "normalized_unit": None,
        "evidence": [],
        "confidence": 0.0,
        "notes": reason,
    }


def _source_for(title: str) -> tuple[str, str, str]:
    matches = [
        (len(key), value) for key, value in SOURCE_MAP.items() if key in title
    ]
    if not matches:
        raise ValueError(f"cannot map evidence title to one local official URL: {title!r}")
    return max(matches, key=lambda item: item[0])[1]


def _evidence(row: dict[str, Any]) -> dict[str, Any]:
    url, publisher, source_type = _source_for(row["source_title"])
    return {
        "raw_value": row["raw_value"],
        "source_url": url,
        "source_title": row["source_title"],
        "publisher": publisher,
        "source_type": source_type,
        "source_locator": row["source_locator"],
        "publication_or_update_date": row["publication_or_update_date"],
        "accessed_at": row["accessed_at"],
    }


def _returned_fields(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = source.get("field_results", source.get("fields"))
    if not isinstance(rows, list):
        raise ValueError("model has no field result list")
    result = {row["field_path"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("duplicate returned field")
    return result


def _assert_scope(source: dict[str, Any], batch: dict[str, Any]) -> None:
    rows = source["results"]
    actual = {row["organizer_id"]: row for row in rows}
    expected = {row["organizer_id"]: row for row in batch["models"]}
    if len(actual) != len(rows) or set(actual) != set(expected):
        raise ValueError(f"model coverage differs: {batch['batch_id']}")
    for organizer_id, model in expected.items():
        if set(_returned_fields(actual[organizer_id])) != set(model["research_targets"]):
            raise ValueError(f"target coverage differs: {organizer_id}")


def _repair_deep_other(source: dict[str, Any], batch: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    models = []
    for expected in sorted(batch["models"], key=lambda row: row["organizer_id"]):
        fields = [
            _not_found(
                field,
                "Допустимый официальный источник производителя или доказанного авторизованного партнёра не найден; сторонние публикации отклонены.",
            )
            for field in sorted(expected["research_targets"])
        ]
        models.append(
            {
                "organizer_id": expected["organizer_id"],
                "identity_status": "MODEL_NOT_FOUND",
                "matched_manufacturer": expected.get("manufacturer"),
                "matched_model": None,
                "field_results": fields,
                "unresolved_issues": [
                    "Research returned only non-official third-party sources for candidate facts; all such facts were rejected during local repair."
                ],
            }
        )
    decisions.append(
        {
            "action": "REJECT_NON_OFFICIAL_EVIDENCE",
            "affected_fields": 5,
            "detail": "ComNews/other third-party claims were not accepted as official or authorized-partner evidence.",
        }
    )
    return {
        "schema_version": "catalog-official-source-research-return-v1",
        "batch_id": batch["batch_id"],
        "research_completed_at": source["research_completed_at"],
        "results": models,
    }, decisions


def _field_from_source(
    source_field: dict[str, Any], status: str, value: Any, unit: str | None, notes: str
) -> dict[str, Any]:
    return {
        "field_path": source_field["field_path"],
        "evidence_status": status,
        "normalized_value": value,
        "normalized_unit": unit,
        "evidence": [_evidence(row) for row in source_field["evidence"]],
        "confidence": source_field["confidence"],
        "notes": notes,
    }


def _repair_hybrid(source: dict[str, Any], batch: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    returned = {row["organizer_id"]: row for row in source["results"]}
    decisions: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    configurations = {
        "0ece582a-084c-4a8b-99f4-576f0e01b7c8": {
            "identity_status": "EXACT_MODEL_MATCH_WITH_CONFLICTS",
            "manufacturer": "ООО «АРС Смарт Роботикс»",
            "model": "CR-02 / SmartCube",
            "conflicts": {"specs.max_speed"},
            "verified": set(),
            "ambiguous": set(),
        },
        "2ffc706d-fe43-4c2b-baad-a624a95ad3ce": {
            "identity_status": "EXACT_MODEL_MATCH_WITH_CONFLICTS",
            "manufacturer": "ООО «РобоСиВи»",
            "model": "Робот-штабелёр RoboCV",
            "conflicts": {"specs.aisle_requirements", "specs.max_speed"},
            "verified": {"specs.min_aisle_width"},
            "ambiguous": set(),
        },
        "5760e938-9a43-45a7-b8e8-f4f2e6383930": {
            "identity_status": "AMBIGUOUS_MODEL_MATCH",
            "manufacturer": "ООО «Ронави Роботикс»",
            "model": None,
            "conflicts": set(),
            "verified": set(),
            "ambiguous": {"specs.min_aisle_width"},
        },
        "89ffd69f-f07b-4bf2-8023-1fd765a2b6ff": {
            "identity_status": "AMBIGUOUS_MODEL_MATCH",
            "manufacturer": "ООО «Морос»",
            "model": None,
            "conflicts": set(),
            "verified": set(),
            "ambiguous": {
                "specs.autonomy",
                "specs.charging_requirements",
                "specs.dimensions",
                "specs.integrations",
                "specs.max_speed",
                "specs.positioning_accuracy",
            },
        },
        "b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1": {
            "identity_status": "EXACT_MODEL_MATCH_WITH_CONFLICTS",
            "manufacturer": "ООО «РобоСиВи»",
            "model": "Робот-тягач RoboCV",
            "conflicts": {"specs.max_speed", "specs.payload", "specs.positioning_accuracy"},
            "verified": {"specs.min_aisle_width"},
            "ambiguous": set(),
        },
    }
    semantic_rejections = {
        ("2ffc706d-fe43-4c2b-baad-a624a95ad3ce", "specs.autonomy"): "Режим работы 24/7 не является длительностью автономной работы.",
        ("5760e938-9a43-45a7-b8e8-f4f2e6383930", "capacity.exchange_time_s"): "До 10 часов автономной работы не является временем обменной операции.",
        ("b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1", "specs.autonomy"): "Режим работы 24/7 не является длительностью автономной работы.",
    }
    expected_by_id = {row["organizer_id"]: row for row in batch["models"]}
    for organizer_id in sorted(expected_by_id):
        expected = expected_by_id[organizer_id]
        source_fields = _returned_fields(returned[organizer_id])
        config = configurations[organizer_id]
        fields: list[dict[str, Any]] = []
        for field_path in sorted(expected["research_targets"]):
            source_field = source_fields[field_path]
            rejection = semantic_rejections.get((organizer_id, field_path))
            if rejection:
                fields.append(_not_found(field_path, rejection))
                decisions.append(
                    {"action": "REJECT_SEMANTIC_MISMATCH", "organizer_id": organizer_id, "field_path": field_path, "detail": rejection}
                )
            elif field_path in config["conflicts"]:
                fields.append(
                    _field_from_source(
                        source_field,
                        "CONFLICT",
                        None,
                        None,
                        "Обе стороны сохранены; применимая revision/configuration документально не доказана.",
                    )
                )
            elif field_path in config["ambiguous"]:
                fields.append(
                    _field_from_source(
                        source_field,
                        "AMBIGUOUS_MODEL_MATCH",
                        None,
                        None,
                        "Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.",
                    )
                )
            elif field_path in config["verified"]:
                fields.append(
                    _field_from_source(
                        source_field,
                        "VERIFIED_OFFICIAL",
                        source_field["normalized_value"],
                        source_field["normalized_unit"],
                        "Evidence URL восстановлен детерминированным join с локальным known_source_candidate.",
                    )
                )
            else:
                fields.append(
                    _not_found(
                        field_path,
                        source_field.get("notes")
                        or "Допустимое однозначное model-specific значение не подтверждено.",
                    )
                )
        models.append(
            {
                "organizer_id": organizer_id,
                "identity_status": config["identity_status"],
                "matched_manufacturer": config["manufacturer"],
                "matched_model": config["model"],
                "field_results": fields,
                "unresolved_issues": [
                    "Locally repaired from exhausted research output; no runtime or catalog import is authorized."
                ],
            }
        )
    decisions.append(
        {
            "action": "RESTORE_OFFICIAL_URL_FROM_LOCAL_CANDIDATE",
            "detail": "Missing URLs/publishers/source types were joined by exact source title to locally stored official candidates; no URL was guessed.",
        }
    )
    return {
        "schema_version": "catalog-official-source-research-return-v1",
        "batch_id": batch["batch_id"],
        "research_completed_at": source["research_completed_at"],
        "results": models,
    }, decisions


def _markdown(result: dict[str, Any], decisions: list[dict[str, Any]], source_hash: str) -> str:
    counts = Counter(
        field["evidence_status"]
        for model in result["results"]
        for field in model["field_results"]
    )
    lines = [
        f"# Локально нормализованный результат `{result['batch_id']}`",
        "",
        "> Review-only repair из уже полученного Deep Research отчёта и локальных batch/source-candidate данных. Не является разрешением на импорт в catalog/runtime.",
        "",
        f"Исходный SHA-256: `{source_hash}`.",
        "",
        "Статусы: " + ", ".join(f"`{key}`={value}" for key, value in sorted(counts.items())) + ".",
        "",
        "Решения repair сохранены в `catalog-deep-research-local-repair-v1.json`.",
        "",
        "CATALOG_RESULT_JSON_BEGIN",
        "```json",
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2),
        "```",
        "CATALOG_RESULT_JSON_END",
        "",
    ]
    return "\n".join(lines)


def repair(deep_other_path: Path, hybrid_path: Path, output_dir: Path, review_path: Path) -> dict[str, Any]:
    inputs = {"deep-other-01": deep_other_path, "hybrid-conflicts-01": hybrid_path}
    reports: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for batch_id, source_path in inputs.items():
        source_hash = _sha256(source_path)
        if source_hash != EXPECTED_SOURCE_HASHES[batch_id]:
            raise ValueError(f"unexpected source hash for {batch_id}: {source_hash}")
        source = _extract(source_path)
        batch_path = HANDOFF / "batches" / f"{batch_id}.json"
        batch = _load_json(batch_path)
        if source.get("batch_id") != batch_id:
            raise ValueError(f"batch_id mismatch: {source_path}")
        _assert_scope(source, batch)
        if batch_id == "deep-other-01":
            result, decisions = _repair_deep_other(source, batch)
        else:
            result, decisions = _repair_hybrid(source, batch)
        result_path = output_dir / f"{batch_id}.result.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        validation = validate_return(batch_path, result_path)
        markdown_path = output_dir / f"{batch_id}.repaired.md"
        markdown_path.write_text(
            _markdown(result, decisions, source_hash), encoding="utf-8", newline="\n"
        )
        reports.append(
            {
                "batch_id": batch_id,
                "source_path": str(source_path),
                "source_sha256": source_hash,
                "result_path": str(result_path),
                "result_sha256": _sha256(result_path),
                "validation": validation,
                "decisions": decisions,
            }
        )
    repair_report = {
        "schema_version": "catalog-deep-research-local-repair-v1",
        "policy": {
            "network_used": False,
            "runtime_or_catalog_write": False,
            "conservative_downgrade": True,
        },
        "repairs": reports,
    }
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        json.dumps(repair_report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return repair_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deep-other-report", type=Path, required=True)
    parser.add_argument("--hybrid-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--review-report",
        type=Path,
        default=ROOT / "data" / "review" / "catalog-deep-research-local-repair-v1.json",
    )
    args = parser.parse_args()
    report = repair(
        args.deep_other_report.resolve(),
        args.hybrid_report.resolve(),
        args.output_dir.resolve(),
        args.review_report.resolve(),
    )
    print(json.dumps({row["batch_id"]: row["validation"] for row in report["repairs"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
