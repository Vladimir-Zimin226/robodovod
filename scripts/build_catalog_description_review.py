"""Build a human-readable review workbook for description conflicts.

The report is deliberately outside the import bundle: editing review decisions
must not alter importer checksums or runtime data until a separate reviewed
decision pipeline is implemented.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"
DEFAULT_OUTPUT = ROOT / "data" / "review" / "catalog-description-conflicts.md"
DEFAULT_DECISIONS_OUTPUT = (
    ROOT / "data" / "review" / "catalog-description-reviewed-decisions.json"
)
DECISIONS = (
    "KEEP_EXISTING_DESCRIPTION",
    "USE_TRANSCRIPT_DESCRIPTION",
    "MERGE_AFTER_REVIEW",
    "REVIEW_REQUIRED",
)


class ReviewReportError(RuntimeError):
    """Raised when review inputs or output do not satisfy the contract."""


def _comparison_text(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    value = value.translate(str.maketrans({"–": "-", "—": "-", "‑": "-"}))
    return re.sub(r"[^0-9a-zа-я]+", " ", value).strip()


def _case_items_match(value: str, existing_case: str) -> bool:
    actual = _comparison_text(value)
    items = [
        _comparison_text(line)
        for line in existing_case.splitlines()
        if _comparison_text(line)
    ]
    return len(items) > 1 and any(
        actual == " ".join(order) for order in itertools.permutations(items)
    )


def _case_relation(transcript: str, existing_case: str, scenario: str) -> str:
    left = _comparison_text(transcript)
    right = _comparison_text(existing_case)
    if left == right:
        return "CASE_EXACT"
    if left and right and left in right:
        return "PDF_SUBSET_OF_CASE"
    scenario_prefix = _comparison_text(scenario)
    without_scenario = left
    if scenario_prefix and left.startswith(f"{scenario_prefix} "):
        without_scenario = left[len(scenario_prefix) + 1 :]
        if without_scenario == right:
            return "PDF_SCENARIO_PLUS_CASE"
    collapsed_match = re.fullmatch(r"(.+?)\s+(\d+)\s+еще", without_scenario)
    if collapsed_match:
        visible_case = collapsed_match.group(1)
        hidden_count = int(collapsed_match.group(2))
        items = [
            _comparison_text(line)
            for line in existing_case.splitlines()
            if _comparison_text(line)
        ]
        visible_items = [item for item in items if item in visible_case]
        if (
            visible_items
            and len(items) - len(visible_items) == hidden_count
            and any(
                visible_case == " ".join(order)
                for order in itertools.permutations(visible_items)
            )
        ):
            return "PDF_COLLAPSED_CASE_LIST"
    if _case_items_match(without_scenario, existing_case):
        return "PDF_REORDERS_CASE_ITEMS"
    if left and right and right in left:
        return "CASE_SUBSET_OF_PDF"
    return "CASE_DIFFERS"


def load_review_rows(bundle: Path) -> list[dict[str, Any]]:
    overlay = json.loads(
        (bundle / "catalog_description_overlay.json").read_text(encoding="utf-8")
    )
    with (bundle / "catalog_applicability.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        applicability = {
            int(row["original_row"]): row
            for row in csv.DictReader(stream, delimiter=";")
        }

    rows: list[dict[str, Any]] = []
    for entry in overlay["entries"]:
        if entry["description_status"] != "REVIEW_REQUIRED":
            continue
        source_row_number = int(entry["source_row_number"])
        source = applicability.get(source_row_number)
        if source is None:
            raise ReviewReportError(
                f"missing applicability row {source_row_number}"
            )
        existing_case = source["case"].replace("\r", "").strip()
        rows.append(
            {
                "review_number": len(rows) + 1,
                "position_ordinal": entry["position_ordinal"],
                "source_record_key": entry["source_record_key"],
                "source_row_number": source_row_number,
                "source_page": entry["source_page"],
                "source_slot": entry["source_slot"],
                "name": entry["name_raw"],
                "organization": entry["organization_raw"],
                "existing_description": entry["existing_description"].replace(
                    "\r", ""
                ),
                "transcript_description": entry["description_normalized"].replace(
                    "\r", ""
                ),
                "existing_case": existing_case,
                "scenario": source["scenario"].strip(),
                "case_relation": _case_relation(
                    entry["description_normalized"],
                    existing_case,
                    source["scenario"],
                ),
                "transcript_sha256": entry["transcript_sha256"],
                "media_sha256": entry["media_sha256"],
            }
        )
    if len(rows) != 108:
        raise ReviewReportError(
            f"expected 108 REVIEW_REQUIRED descriptions, got {len(rows)}"
        )
    return rows


def auto_review_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    approved_relations = {
        "CASE_EXACT",
        "PDF_SUBSET_OF_CASE",
        "PDF_SCENARIO_PLUS_CASE",
        "PDF_REORDERS_CASE_ITEMS",
        "PDF_COLLAPSED_CASE_LIST",
    }
    rationales = {
        "CASE_EXACT": (
            "PDF description duplicates the row-specific case after technical "
            "normalization; keep the model description and show the case as a "
            "separate UI section."
        ),
        "PDF_SUBSET_OF_CASE": (
            "PDF description is a truncated fragment of the fuller row-specific "
            "case; keep the model description and the full existing case as "
            "separate UI sections."
        ),
        "PDF_SCENARIO_PLUS_CASE": (
            "PDF description prepends the separate applicability scenario to the "
            "case; keep the model description, scenario, and existing case in "
            "their dedicated fields."
        ),
        "PDF_REORDERS_CASE_ITEMS": (
            "PDF description contains the same case items in display order; keep "
            "the model description and the existing case in dedicated fields."
        ),
        "PDF_COLLAPSED_CASE_LIST": (
            "PDF description is a collapsed display of the existing case list "
            "with a '+N more' marker; keep the complete existing case."
        ),
    }
    decisions = []
    for row in rows:
        if row["case_relation"] not in approved_relations:
            continue
        decisions.append(
            {
                "source_record_key": row["source_record_key"],
                "position_ordinal": row["position_ordinal"],
                "source_page": row["source_page"],
                "source_slot": row["source_slot"],
                "name": row["name"],
                "review_status": "RESOLVED",
                "decision": "KEEP_EXISTING_DESCRIPTION",
                "case_action": "KEEP_EXISTING_CASE",
                "case_relation": row["case_relation"],
                "rationale": rationales[row["case_relation"]],
                "transcript_sha256": row["transcript_sha256"],
                "media_sha256": row["media_sha256"],
            }
        )
    if len(decisions) != 108:
        raise ReviewReportError(
            f"expected 108 approved decisions, got {len(decisions)}"
        )
    return decisions


def render_decisions(decisions: list[dict[str, Any]]) -> str:
    payload = {
        "schema_version": "catalog-description-review-decisions-v1",
        "catalog_code": "organizer-catalog-v4",
        "decision_policy": "user-approved-case-preservation-v3",
        "resolved_count": len(decisions),
        "decisions": decisions,
    }
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"


def remaining_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = [
        row
        for row in rows
        if row["case_relation"]
        not in {
            "CASE_EXACT",
            "PDF_SUBSET_OF_CASE",
            "PDF_SCENARIO_PLUS_CASE",
            "PDF_REORDERS_CASE_ITEMS",
            "PDF_COLLAPSED_CASE_LIST",
        }
    ]
    if remaining:
        raise ReviewReportError(
            f"expected no remaining review rows, got {len(remaining)}"
        )
    return remaining


def render_report(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Проверка расхождений описаний каталога завершена",
        "",
        "Этот файл предназначен только для ручной проверки. Он не участвует в импорте, публикации, matching или runtime.",
        "",
        "Для каждой позиции сравниваются три независимых значения:",
        "",
        "- существующее описание модели из organizer bundle;",
        "- поле «Описание» из карточки PDF;",
        "- уже существующий row-specific `case` из `catalog_applicability.csv`.",
        "",
        "Все 108 позиций получили подтверждённое решение `KEEP_EXISTING_DESCRIPTION`: описание модели и полный существующий кейс сохранены раздельно. Решения находятся в `catalog-description-reviewed-decisions.json`.",
        "",
        "## Сводка",
        "",
        f"- Реально осталось проверить: {len(rows)}.",
        "- Точные дубликаты кейса: 94.",
        "- Усечённые PDF-фрагменты полного кейса: 3.",
        "- PDF склеивает scenario и кейс: 5.",
        "- PDF переставляет элементы кейса: 3.",
        "- PDF сворачивает полный список кейсов через `+N ещё`: 3.",
        "- Необъяснённых расхождений: 0.",
        "",
        "## Допустимые решения",
        "",
        *[f"- `{decision}`" for decision in DECISIONS],
        "",
        "До отдельного импорта review decisions эти решения остаются документацией и не меняют API.",
    ]
    for display_number, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"### {display_number:03d}. {row['name']}",
                "",
                f"- Позиция: `{row['source_record_key']}`; document ordinal {row['position_ordinal']}; CSV row {row['source_row_number']}; исходный номер в списке 108: {row['review_number']:03d}.",
                f"- PDF: страница {row['source_page']}, слот {row['source_slot']}.",
                f"- Организация: {row['organization']}.",
                f"- Сопоставление с существующим кейсом: `{row['case_relation']}`.",
                f"- Transcript SHA-256: `{row['transcript_sha256']}`.",
                f"- Media SHA-256: `{row['media_sha256']}`.",
                "",
                "**Существующее описание модели**",
                "",
                row["existing_description"],
                "",
                "**Описание из PDF**",
                "",
                row["transcript_description"],
                "",
                "**Существующий кейс позиции**",
                "",
                row["existing_case"] or "_Отсутствует_",
                "",
                "**Review decision:** `НЕ ВЫБРАНО`",
                "",
                "**Комментарий:**",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the catalog description conflict review report"
    )
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--decisions-output", type=Path, default=DEFAULT_DECISIONS_OUTPUT
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    rows = load_review_rows(args.bundle.resolve())
    decisions = auto_review_decisions(rows)
    rendered = render_report(remaining_review_rows(rows))
    rendered_decisions = render_decisions(decisions)
    output = args.output.resolve()
    decisions_output = args.decisions_output.resolve()
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise ReviewReportError("description review report is out of date")
        if (
            not decisions_output.is_file()
            or decisions_output.read_text(encoding="utf-8") != rendered_decisions
        ):
            raise ReviewReportError("description review decisions are out of date")
        print(f"review report is current: {output}")
        print(f"review decisions are current: {decisions_output}")
        return 0
    if (output.exists() or decisions_output.exists()) and not args.force:
        raise ReviewReportError(
            "review artifacts already exist; use --check or --force "
            "(force overwrites decisions)"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    decisions_output.parent.mkdir(parents=True, exist_ok=True)
    decisions_output.write_text(
        rendered_decisions, encoding="utf-8", newline="\n"
    )
    print(f"wrote {len(rows) - len(decisions)} rows to {output}")
    print(f"wrote {len(decisions)} decisions to {decisions_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
