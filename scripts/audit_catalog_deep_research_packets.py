"""Cross-audit all generated Deep Research packets without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "data" / "research" / "catalog-runtime-eligibility-v1"
ELIGIBILITY_AUDIT = ROOT / "data" / "review" / "catalog-runtime-eligibility-report-v1.json"
OUTPUT = ROOT / "data" / "review" / "catalog-deep-research-packet-audit-v1.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_packets(handoff: Path, eligibility_path: Path) -> dict[str, Any]:
    manifest = _load(handoff / "manifest.json")
    eligibility = _load(eligibility_path)
    contract = _load(handoff / "upload" / "deep-mobile-01" / "02-RUNTIME-CONTRACT.json")
    contract_by_class = {row["code"]: row for row in contract["equipment_classes"]}
    issues: list[dict[str, str]] = []
    model_ids: list[str] = []
    position_ids: list[str] = []
    target_counts: Counter[str] = Counter()
    packet_rows: list[dict[str, Any]] = []
    manifest_batches = {row["batch_id"]: row for row in manifest["batches"]}
    batch_paths = sorted((handoff / "batches").glob("*.json"))

    def issue(code: str, location: str, detail: str) -> None:
        issues.append({"code": code, "location": location, "detail": detail})

    if len(batch_paths) != 6:
        issue("BATCH_COUNT", "batches", f"expected 6, found {len(batch_paths)}")
    for batch_path in batch_paths:
        batch = _load(batch_path)
        batch_id = batch["batch_id"]
        prompt_path = handoff / "prompts" / f"{batch_id}.prompt.md"
        prompt = prompt_path.read_text(encoding="utf-8")
        manifest_row = manifest_batches.get(batch_id)
        if not manifest_row or manifest_row["sha256"] != _sha256(batch_path):
            issue("MANIFEST_HASH", batch_id, "batch hash missing or differs")
        if batch["model_count"] != len(batch["models"]):
            issue("DECLARED_MODEL_COUNT", batch_id, "model_count differs from models")
        actual_targets = sum(len(row["research_targets"]) for row in batch["models"])
        if f"ровно {batch['model_count']} model results" not in prompt:
            issue("PROMPT_MODEL_COUNT", batch_id, "exact model count is absent")
        if f"{actual_targets} field results" not in prompt:
            issue("PROMPT_TARGET_COUNT", batch_id, "exact target count is absent")
        for required_text in (
            "Публичный веб-поиск обязателен",
            "CATALOG_RESULT_JSON_BEGIN",
            "CATALOG_RESULT_JSON_END",
        ):
            if required_text not in prompt:
                issue("PROMPT_GUARD", batch_id, f"missing {required_text!r}")
        upload = handoff / "upload" / batch_id
        for filename in (
            f"01-BATCH-{batch_id}.json",
            "02-RUNTIME-CONTRACT.json",
            "03-RETURN-SCHEMA-REQUIRED.json",
            "COPY-PASTE-PROMPT.md",
            "RECOVERY-CURRENT-CHAT.md",
        ):
            if not (upload / filename).is_file():
                issue("UPLOAD_FILE", batch_id, f"missing {filename}")
        hash_files = {
            "batch": upload / f"01-BATCH-{batch_id}.json",
            "runtime_contract": upload / "02-RUNTIME-CONTRACT.json",
            "return_schema": upload / "03-RETURN-SCHEMA-REQUIRED.json",
        }
        if manifest_row:
            for key, path in hash_files.items():
                if path.is_file() and manifest_row["upload_sha256"].get(key) != _sha256(path):
                    issue("UPLOAD_HASH", f"{batch_id}/{key}", "manifest hash differs")
        if hash_files["batch"].is_file() and hash_files["batch"].read_bytes() != batch_path.read_bytes():
            issue("UPLOAD_COPY", batch_id, "uploaded batch differs from canonical batch")
        if (upload / "COPY-PASTE-PROMPT.md").is_file() and (
            (upload / "COPY-PASTE-PROMPT.md").read_bytes() != prompt_path.read_bytes()
        ):
            issue("UPLOAD_COPY", batch_id, "uploaded prompt differs from canonical prompt")
        for model in batch["models"]:
            organizer_id = model["organizer_id"]
            model_ids.append(organizer_id)
            position_ids.extend(model["position_ids"])
            target_counts[batch_id] += len(model["research_targets"])
            contract_row = contract_by_class.get(model["equipment_class"])
            if not contract_row:
                if model["equipment_class"] is not None or model["required_fields"]:
                    issue("EQUIPMENT_CLASS", organizer_id, "class absent from contract")
                continue
            required = sorted(
                set(contract_row["required_runtime_fields"])
                | set(contract_row["capacity_profile"]["required_fields"])
            )
            if sorted(model["required_fields"]) != required:
                issue("REQUIRED_FIELDS", organizer_id, "batch fields differ from contract")
            conflict_fields = {
                row["field"]
                for row in model["conflicts"]
                if row["field"] != "model_identity_or_revision"
            }
            extras = sorted(
                set(model["research_targets"]) - set(required) - conflict_fields
            )
            if extras:
                issue("TARGET_OUTSIDE_CONTRACT", organizer_id, ", ".join(extras))
            if not model["research_targets"]:
                issue("EMPTY_TARGETS", organizer_id, "no research targets")
        packet_rows.append(
            {
                "batch_id": batch_id,
                "mode": batch["mode"],
                "models": len(batch["models"]),
                "positions": sum(len(row["position_ids"]) for row in batch["models"]),
                "target_fields": actual_targets,
                "batch_sha256": _sha256(batch_path),
                "prompt_sha256": _sha256(prompt_path),
            }
        )
    if len(model_ids) != len(set(model_ids)):
        issue("DUPLICATE_MODEL", "all batches", "organizer_id appears more than once")
    if len(position_ids) != len(set(position_ids)):
        issue("DUPLICATE_POSITION", "all batches", "position_id appears more than once")
    if len(model_ids) != 41:
        issue("MODEL_SCOPE", "all batches", f"expected 41, found {len(model_ids)}")
    if len(position_ids) != 44:
        issue("POSITION_SCOPE", "all batches", f"expected 44, found {len(position_ids)}")
    if eligibility.get("counts") != {"models": 187, "positions": 223}:
        issue("PARENT_AUDIT_SCOPE", eligibility_path.name, "expected 187 models/223 positions")
    return {
        "schema_version": "catalog-deep-research-packet-audit-v1",
        "status": "PASS" if not issues else "FAIL",
        "source_eligibility_scope": eligibility["counts"],
        "research_scope": {
            "batches": len(batch_paths),
            "models": len(model_ids),
            "positions": len(position_ids),
            "target_fields": sum(target_counts.values()),
        },
        "invariants": {
            "unique_models": len(model_ids) == len(set(model_ids)),
            "unique_positions": len(position_ids) == len(set(position_ids)),
            "runtime_switch_allowed": contract["policy"]["runtime_switch_allowed"],
            "capacity_formulas_in_scope": contract["policy"]["capacity_formulas_in_scope"],
        },
        "packets": sorted(packet_rows, key=lambda row: row["batch_id"]),
        "issues": sorted(issues, key=lambda row: (row["code"], row["location"], row["detail"])),
    }


def render_markdown(report: dict[str, Any]) -> str:
    source = report["source_eligibility_scope"]
    research = report["research_scope"]
    lines = [
        "# Cross-audit пакетов Deep Research",
        "",
        f"Статус: **{report['status']}**.",
        "",
        f"Исходный eligibility audit: {source['positions']} позиций / {source['models']} моделей.",
        f"Research handoff: {research['batches']} пакетов / {research['positions']} позиций / {research['models']} моделей / {research['target_fields']} target fields.",
        "",
        "| Batch | Режим | Модели | Позиции | Targets |",
        "|---|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| `{row['batch_id']}` | `{row['mode']}` | {row['models']} | {row['positions']} | {row['target_fields']} |"
        for row in report["packets"]
    )
    lines += ["", "## Нарушения", ""]
    if report["issues"]:
        lines.extend(
            f"- `{row['code']}` / `{row['location']}`: {row['detail']}"
            for row in report["issues"]
        )
    else:
        lines.append("Нарушений не найдено.")
    lines += ["", "> 44 позиции — только исследовательский subset из полного аудита 223 позиций; это не потеря или склейка каталога.", ""]
    return "\n".join(lines)


def write_audit(report: dict[str, Any], output: Path) -> None:
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
    parser.add_argument("--eligibility-audit", type=Path, default=ELIGIBILITY_AUDIT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = audit_packets(args.handoff.resolve(), args.eligibility_audit.resolve())
    write_audit(report, args.output.resolve())
    print(json.dumps({"status": report["status"], **report["research_scope"]}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
