"""Extract and validate catalog research JSON embedded in Markdown reports."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from scripts.validate_catalog_deep_research_returns import (
    ReturnValidationError,
    validate_return,
)

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "data" / "research" / "catalog-runtime-eligibility-v1"
REPORTS = ROOT / "Исследования" / "Результаты сюда"
BEGIN_MARKER = "CATALOG_RESULT_JSON_BEGIN"
END_MARKER = "CATALOG_RESULT_JSON_END"


class ReportExtractionError(ValueError):
    """Raised when a Markdown report cannot produce a trustworthy return."""


def extract_json_object(report_path: Path) -> dict[str, Any]:
    text = report_path.read_text(encoding="utf-8-sig")
    if text.count(BEGIN_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise ReportExtractionError(
            f"report must contain exactly one JSON marker pair: {report_path.name}"
        )
    body = text.split(BEGIN_MARKER, 1)[1].split(END_MARKER, 1)[0].strip()
    lines = body.splitlines()
    if (
        len(lines) < 3
        or lines[0].strip().lower() != "```json"
        or lines[-1].strip() != "```"
    ):
        raise ReportExtractionError(
            f"JSON markers must wrap one fenced json block: {report_path.name}"
        )
    raw_json = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ReportExtractionError(
            f"embedded JSON is invalid at line {exc.lineno}, column {exc.colno}: "
            f"{report_path.name}"
        ) from exc
    if not isinstance(value, dict):
        raise ReportExtractionError(
            f"embedded JSON root must be an object: {report_path.name}"
        )
    return value


def _canonical(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def extract_directory(
    handoff: Path,
    reports_dir: Path,
    output_dir: Path,
    require_complete: bool,
) -> list[dict[str, Any]]:
    batches = {
        path.stem: path for path in sorted((handoff / "batches").glob("*.json"))
    }
    reports = [
        path
        for path in sorted(reports_dir.glob("*.md"))
        if not path.name.startswith("00-")
    ]
    extracted: dict[str, tuple[Path, bytes]] = {}
    for report in reports:
        value = extract_json_object(report)
        batch_id = value.get("batch_id")
        if not isinstance(batch_id, str) or batch_id not in batches:
            raise ReportExtractionError(
                f"unknown or missing batch_id in report: {report.name}"
            )
        if batch_id in extracted:
            previous = extracted[batch_id][0].name
            raise ReportExtractionError(
                f"duplicate reports for {batch_id}: {previous}, {report.name}"
            )
        extracted[batch_id] = (report, _canonical(value))

    missing = sorted(batches.keys() - extracted.keys())
    if require_complete and missing:
        raise ReportExtractionError(f"missing reports: {missing}")

    summaries: list[dict[str, Any]] = []
    validated: list[tuple[str, bytes]] = []
    with tempfile.TemporaryDirectory(prefix="robodovod-report-extraction-") as temporary:
        temporary_dir = Path(temporary)
        for batch_id in sorted(extracted):
            candidate = temporary_dir / f"{batch_id}.result.json"
            payload = extracted[batch_id][1]
            candidate.write_bytes(payload)
            summary = validate_return(batches[batch_id], candidate)
            summary["report"] = extracted[batch_id][0].name
            summaries.append(summary)
            validated.append((batch_id, payload))

    output_dir.mkdir(parents=True, exist_ok=True)
    for batch_id, payload in validated:
        (output_dir / f"{batch_id}.result.json").write_bytes(payload)
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    reports_dir = args.reports_dir.resolve()
    try:
        summaries = extract_directory(
            args.handoff.resolve(),
            reports_dir,
            args.output_dir.resolve() if args.output_dir else reports_dir,
            args.require_complete,
        )
    except (OSError, ReportExtractionError, ReturnValidationError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps({"extracted": summaries}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
