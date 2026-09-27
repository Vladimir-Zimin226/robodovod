"""C26 immutable, snapshot-driven evidence export builder.

The builder performs no capacity, finance, ranking, SLA or simulation math.
It verifies persisted snapshot digests and serializes their existing values into
an offline PDF and a spreadsheet-safe CSV bundle.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import textwrap
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from calculation_contracts import Digest, StrictContractModel, semantic_digest


EXPORT_POLICY_VERSION = "calculation-evidence-export-policy-v1"
EXPORT_GENERATOR_VERSION = "snapshot-evidence-export-v1"
EXPORT_POLICY_VERSION_V2 = "calculation-evidence-export-policy-v2"
EXPORT_GENERATOR_VERSION_V2 = "snapshot-evidence-export-v2"
ENTRYPOINT_FILENAME = "НАЧНИТЕ_ЗДЕСЬ.md"
GUIDE_FILENAME = "Как_читать_разделы.md"
READABLE_REPORT_FILENAME = "Отчёт_Рободовод.pdf"
TECHNICAL_REPORT_FILENAME = "Технический_дамп.pdf"
SECTION_NAMES = (
    "Inputs", "Selection", "Scenarios", "CashFlow", "Sensitivity",
    "Sources", "Trace", "Simulation", "Versions",
)
_FORMULA_PREFIX = re.compile(r"^[\s\u0000-\u001f]*[=+\-@]")
_CANONICAL_NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


class EvidenceRunSnapshotV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    project_id: str
    run_kind: Literal["FULL_ANALYSIS", "CAPACITY_ANALYSIS"]
    status: Literal["SUCCEEDED"]
    revision_id: str | None
    created_at: datetime
    finished_at: datetime
    versions: dict[str, str | None]
    checksums: dict[str, str | None]
    input_snapshot: dict[str, Any]
    result_snapshot: dict[str, Any]
    scenario_spec_snapshot: dict[str, Any] | None
    trace_snapshot: dict[str, Any] | None
    version_bindings_snapshot: dict[str, Any] | None
    diagnostics: dict[str, Any]


class EvidenceSectionV1(StrictContractModel):
    name: Literal[
        "Inputs", "Selection", "Scenarios", "CashFlow", "Sensitivity",
        "Sources", "Trace", "Simulation", "Versions",
    ]
    status: Literal["AVAILABLE", "NOT_AVAILABLE"]
    filename: str
    record_count: Annotated[int, Field(ge=0)]
    reason_code: str | None
    source_refs: list[str]


class EvidenceArtifactV1(StrictContractModel):
    filename: str
    media_type: str
    byte_size: Annotated[int, Field(gt=0)]
    sha256: Digest


class EvidenceExportManifestV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["calculation-evidence-export-manifest-v1"]
    run_id: str
    project_id: str
    run_kind: Literal["FULL_ANALYSIS", "CAPACITY_ANALYSIS"]
    revision_id: str | None
    snapshot_captured_at: datetime
    export_policy_version: Literal["calculation-evidence-export-policy-v1"]
    generator_version: Literal["snapshot-evidence-export-v1"]
    versions: dict[str, str | None]
    source_snapshot_digests: dict[str, Digest | None]
    sections: list[EvidenceSectionV1]
    artifacts: list[EvidenceArtifactV1]
    bundle_content_digest: Digest
    limitations: list[str]
    manifest_digest: Digest

    @model_validator(mode="after")
    def validate_manifest_digest(self) -> "EvidenceExportManifestV1":
        content = self.model_dump(mode="json")
        actual = content["manifest_digest"]
        content["manifest_digest"] = "sha256:" + "0" * 64
        if actual != semantic_digest(content):
            raise ValueError("evidence export manifest digest mismatch")
        return self


class EvidenceExportManifestV2(EvidenceExportManifestV1):
    """Human-readable package; v1 stays available for historical golden replay."""

    schema_version: Literal["calculation-evidence-export-manifest-v2"]
    export_policy_version: Literal["calculation-evidence-export-policy-v2"]
    generator_version: Literal["snapshot-evidence-export-v2"]
    entrypoint_filename: Literal["НАЧНИТЕ_ЗДЕСЬ.md"]
    report_filename: Literal["Отчёт_Рободовод.pdf"]
    linked_capacity_run_id: str | None
    linked_capacity_snapshot_digests: dict[str, Digest | None] | None


class EvidenceExportManifestV3(EvidenceExportManifestV2):
    schema_version: Literal["calculation-evidence-export-manifest-v3"]
    export_policy_version: Literal["calculation-evidence-export-policy-v3"]
    generator_version: Literal["snapshot-evidence-export-v3"]
    presentation_version: Literal["readable-presentation-v2"]


class EvidenceExportManifestV4(EvidenceExportManifestV3):
    """F5 human package over unchanged run and optional saved C23 artifact."""

    schema_version: Literal["calculation-evidence-export-manifest-v4"]
    export_policy_version: Literal["calculation-evidence-export-policy-v4"]
    generator_version: Literal["snapshot-evidence-export-v4"]
    comparison_filename: Literal["Сравнение.csv"]
    workbook_filename: Literal["Результат.xlsx"]
    visualization_filename: Literal["Схема_2D.svg"] | None
    simulation_request_id: str | None
    simulation_report_digest: Digest | None
    scenario_spec_digest: Digest | None


@dataclass(frozen=True)
class EvidenceExportPackage:
    manifest: EvidenceExportManifestV1 | EvidenceExportManifestV2 | EvidenceExportManifestV3 | EvidenceExportManifestV4
    archive: bytes
    files: dict[str, bytes]


class EvidenceExportIntegrityError(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _bare_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest(payload: bytes) -> str:
    return f"sha256:{_bare_sha256(payload)}"


def _verify_snapshots(run: EvidenceRunSnapshotV1) -> dict[str, str | None]:
    values = {
        "input": run.input_snapshot,
        "result": run.result_snapshot,
        "scenario_spec": run.scenario_spec_snapshot,
        "trace": run.trace_snapshot,
        "version_bindings": run.version_bindings_snapshot,
    }
    verified: dict[str, str | None] = {}
    for name, value in values.items():
        stored = run.checksums.get(name)
        if value is None:
            if stored is not None:
                raise EvidenceExportIntegrityError(f"{name} checksum exists without snapshot")
            verified[name] = None
            continue
        actual = _bare_sha256(_canonical_bytes(value))
        if stored != actual:
            raise EvidenceExportIntegrityError(f"{name} snapshot checksum mismatch")
        verified[name] = f"sha256:{actual}"
    return verified


def _source_ref(container: dict[str, Any], snapshot_name: str, digest: str, path: str) -> str:
    for key in ("source_ref", "provenance_ref", "trace_node_ref", "node_id", "formula_id"):
        value = container.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("source_refs", "trace_node_refs", "input_refs"):
        value = container.get(key)
        if isinstance(value, list) and value:
            return "|".join(str(item) for item in value)
    return f"snapshot:{snapshot_name}:{digest}#{path or '$'}"


def _flatten(value: Any, *, snapshot_name: str, digest: str, path: str = "", parent: dict[str, Any] | None = None) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{path}.{key}" if path else key
            rows.extend(_flatten(value[key], snapshot_name=snapshot_name, digest=digest, path=child, parent=value))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_flatten(item, snapshot_name=snapshot_name, digest=digest, path=f"{path}[{index}]", parent=parent))
    else:
        if value is None:
            rendered, status = "NULL", "NULL"
        elif isinstance(value, bool):
            rendered, status = ("true" if value else "false"), "AVAILABLE"
        elif isinstance(value, str):
            rendered, status = value, "AVAILABLE"
        else:
            rendered, status = json.dumps(value, ensure_ascii=False, separators=(",", ":")), "AVAILABLE"
        rows.append((path or "$", rendered, _source_ref(parent or {}, snapshot_name, digest, path), status))
    return rows


def _matching_nodes(value: Any, keywords: tuple[str, ...], path: str = "") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            normalized = key.lower().replace("-", "_")
            if any(token in normalized for token in keywords):
                found.append((child_path, child))
            else:
                found.extend(_matching_nodes(child, keywords, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_matching_nodes(child, keywords, f"{path}[{index}]"))
    return found


def _rows_for_section(run: EvidenceRunSnapshotV1, digests: dict[str, str | None], section: str) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    result = run.result_snapshot
    result_digest = digests["result"] or "sha256:" + "0" * 64
    if section == "Inputs":
        digest = digests["input"] or "sha256:" + "0" * 64
        return _flatten(run.input_snapshot, snapshot_name="input", digest=digest), [digest]
    if section == "Versions":
        body = {"run_versions": run.versions, "version_bindings": run.version_bindings_snapshot}
        refs = [item for item in (digests["version_bindings"],) if item]
        return _flatten(body, snapshot_name="versions", digest=refs[0] if refs else result_digest), refs or [result_digest]
    if section == "Trace" and run.trace_snapshot is not None:
        digest = digests["trace"] or result_digest
        return _flatten(run.trace_snapshot, snapshot_name="trace", digest=digest), [digest]

    keyword_map = {
        "Selection": ("selection", "recommendation", "ranking", "rejected", "selected_fleet", "recommended_fleet"),
        "Scenarios": ("scenarios", "scenario_variants"),
        "CashFlow": ("cashflow", "cash_flow", "ledger", "financial"),
        "Sensitivity": ("sensitivity",),
        "Sources": ("source", "provenance", "evidence", "assumption"),
        "Trace": ("trace",),
        "Simulation": ("simulation_report", "simulationreport"),
    }
    nodes = _matching_nodes(result, keyword_map[section])
    if section == "Simulation" and result.get("schema_version") in ("simulation-report-v1", "simulation-report-v2", "simulation-report-v3"):
        nodes = [("$", result)]
    rows: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for node_path, node in nodes:
        for row in _flatten(node, snapshot_name="result", digest=result_digest, path=node_path):
            identity = (row[0], row[1])
            if identity not in seen:
                seen.add(identity)
                rows.append(row)
    return rows, [result_digest] if rows else []


def _safe_cell(value: Any) -> str:
    rendered = str(value)
    if _CANONICAL_NUMBER.fullmatch(rendered):
        return rendered
    return f"'{rendered}" if _FORMULA_PREFIX.match(rendered) else rendered


def _csv_bytes(rows: list[tuple[str, str, str, str]], *, reason: str | None) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(("path", "value", "source_ref", "status"))
    if rows:
        for row in rows:
            writer.writerow(tuple(_safe_cell(cell) for cell in row))
    else:
        writer.writerow(("$", "NOT_AVAILABLE", reason or "section-not-in-run-snapshot", "NOT_AVAILABLE"))
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def _pdf_escape(value: str) -> str:
    ascii_value = value.encode("ascii", "backslashreplace").decode("ascii")
    return ascii_value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(lines: list[str]) -> bytes:
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(textwrap.wrap(line, width=105, replace_whitespace=False, drop_whitespace=False) or [""])
    pages = [wrapped[index:index + 72] for index in range(0, len(wrapped), 72)] or [["EMPTY EXPORT"]]
    page_ids = [4 + index * 2 for index in range(len(pages))]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{item} 0 R' for item in page_ids)}] >>".encode("ascii"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    }
    for index, page in enumerate(pages):
        page_id = page_ids[index]
        content_id = page_id + 1
        commands = ["BT", "/F1 7 Tf", "32 810 Td", "10 TL"]
        for line in page:
            commands.append(f"({_pdf_escape(line)}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii")
        objects[page_id] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects) + 1):
        offsets.append(output.tell())
        output.write(f"{object_id} 0 obj\n".encode("ascii"))
        output.write(objects[object_id])
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return output.getvalue()


def _artifact(filename: str, media_type: str, payload: bytes) -> EvidenceArtifactV1:
    return EvidenceArtifactV1(filename=filename, media_type=media_type, byte_size=len(payload), sha256=_digest(payload))


def build_evidence_export(run: EvidenceRunSnapshotV1) -> EvidenceExportPackage:
    digests = _verify_snapshots(run)
    files: dict[str, bytes] = {}
    sections: list[EvidenceSectionV1] = []
    limitations = [
        "snapshot-only-no-live-price-refresh",
        "missing-sections-exported-as-not-available",
        "no-client-capacity-finance-sla-or-simulation-arithmetic",
        "preliminary-analysis-not-engineering-certification",
    ]
    pdf_lines = [
        "ROBOMERA CALCULATION EVIDENCE EXPORT",
        f"run_id={run.run_id}", f"project_id={run.project_id}",
        f"run_kind={run.run_kind}", f"revision_id={run.revision_id or 'NOT_AVAILABLE'}",
        f"snapshot_captured_at={run.finished_at.isoformat()}",
        f"export_policy_version={EXPORT_POLICY_VERSION}",
        f"generator_version={EXPORT_GENERATOR_VERSION}",
        "PRELIMINARY ANALYSIS; NOT ENGINEERING CERTIFICATION",
        "EXPORT LIMITATIONS:",
        *(f"- {item}" for item in limitations),
    ]
    for section in SECTION_NAMES:
        rows, refs = _rows_for_section(run, digests, section)
        reason = None if rows else "section-not-in-run-snapshot"
        filename = f"{section}.csv"
        csv_payload = _csv_bytes(rows, reason=reason)
        files[filename] = csv_payload
        sections.append(EvidenceSectionV1(
            name=section, status="AVAILABLE" if rows else "NOT_AVAILABLE",
            filename=filename, record_count=len(rows), reason_code=reason,
            source_refs=refs,
        ))
        pdf_lines.append(f"SECTION {section}: {'AVAILABLE' if rows else 'NOT_AVAILABLE'} records={len(rows)} reason={reason or '-'}")
        pdf_lines.extend(csv_payload.decode("utf-8-sig").splitlines())

    snapshot_document = {
        "schema_version": "calculation-evidence-snapshot-v1",
        "run_id": run.run_id,
        "project_id": run.project_id,
        "run_kind": run.run_kind,
        "revision_id": run.revision_id,
        "snapshot_captured_at": run.finished_at.isoformat(),
        "versions": run.versions,
        "source_snapshot_digests": digests,
        "input_snapshot": run.input_snapshot,
        "result_snapshot": run.result_snapshot,
        "scenario_spec_snapshot": run.scenario_spec_snapshot,
        "trace_snapshot": run.trace_snapshot,
        "version_bindings_snapshot": run.version_bindings_snapshot,
        "diagnostics": run.diagnostics,
    }
    snapshot_payload = json.dumps(snapshot_document, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    files["Snapshot.json"] = snapshot_payload
    pdf_lines.append("FULL SNAPSHOT JSON (unicode escaped for built-in offline PDF font)")
    pdf_lines.extend(json.dumps(snapshot_document, ensure_ascii=True, indent=2, sort_keys=True).splitlines())
    files["Report.pdf"] = _pdf_bytes(pdf_lines)

    artifacts = [
        _artifact(name, "application/pdf" if name.endswith(".pdf") else "application/json" if name.endswith(".json") else "text/csv; charset=utf-8", payload)
        for name, payload in sorted(files.items())
    ]
    bundle_content_digest = semantic_digest([item.model_dump(mode="json") for item in artifacts])
    manifest_body = {
        "schema_version": "calculation-evidence-export-manifest-v1",
        "run_id": run.run_id,
        "project_id": run.project_id,
        "run_kind": run.run_kind,
        "revision_id": run.revision_id,
        "snapshot_captured_at": run.finished_at,
        "export_policy_version": EXPORT_POLICY_VERSION,
        "generator_version": EXPORT_GENERATOR_VERSION,
        "versions": run.versions,
        "source_snapshot_digests": digests,
        "sections": sections,
        "artifacts": artifacts,
        "bundle_content_digest": bundle_content_digest,
        "limitations": limitations,
        "manifest_digest": "sha256:" + "0" * 64,
    }
    manifest_body["manifest_digest"] = semantic_digest(
        EvidenceExportManifestV1.model_construct(**manifest_body).model_dump(mode="json")
    )
    manifest = EvidenceExportManifestV1.model_validate(manifest_body)
    manifest_payload = json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted({**files, "manifest.json": manifest_payload}.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return EvidenceExportPackage(manifest=manifest, archive=archive_buffer.getvalue(), files=files)


def build_evidence_export_v3(
    run: EvidenceRunSnapshotV1,
    capacity_run: EvidenceRunSnapshotV1 | None = None,
) -> EvidenceExportPackage:
    """Versioned readable presentation over unchanged verified machine snapshots."""
    from calculation.readable_report import build_readable_report
    from presentation import VERSION, humanize, section, status

    previous = build_evidence_export_v2(run, capacity_run)
    files = dict(previous.files)
    files[READABLE_REPORT_FILENAME], source_digest = build_readable_report(
        run, capacity_run, presentation_version=VERSION,
    )
    if source_digest != previous.manifest.source_snapshot_digests["result"]:
        raise EvidenceExportIntegrityError("readable report source does not match run")
    missing = [section(item.name) for item in previous.manifest.sections if item.status == "NOT_AVAILABLE"]
    kind = "расчёт потребного парка" if run.run_kind == "CAPACITY_ANALYSIS" else "расчёт экономики роботизации"
    capacity_input = run.input_snapshot if run.run_kind == "CAPACITY_ANALYSIS" else capacity_run.input_snapshot if capacity_run else {}
    pallet_transport = (capacity_input.get("process") or {}).get("process_code") == "warehouse_receiving_shipping"
    lines = [
        "# НАЧНИТЕ ЗДЕСЬ", "",
        f"## Сохранённый расчёт от {run.finished_at:%d.%m.%Y}", "",
        f"Это {kind}. Сначала откройте **{READABLE_REPORT_FILENAME}**: в нём результаты, ограничения и следующие шаги.",
        *(["Охват: учтена перевозка подготовленных паллет; отбор коробок и упаковка не рассчитаны. Экономия комплектовщиков и упаковщиков не включена."] if pallet_transport else []),
        f"Затем откройте **{GUIDE_FILENAME}**: он объясняет разделы данных архива.",
        "Исходные цены, паспорт модели и условия поставки требуют отдельного подтверждения перед закупкой.",
        f"Разделы без данных: {', '.join(missing) if missing else 'нет'}.", "",
        "## Технические подробности", "",
        f"Версия представления: {VERSION}. Идентификатор расчёта: {run.run_id}.",
        f"Проект: {run.project_id}. Тип: {run.run_kind}. Ревизия: {run.revision_id or 'отсутствует'}.",
        f"Контрольная сумма результата: {previous.manifest.source_snapshot_digests['result']}.",
        "Snapshot.json и CSV содержат исходные машинные ключи без изменения. manifest.json содержит версии, контрольные суммы и список файлов.",
        "Для проверки каждого файла сравните его SHA-256 с artifacts в manifest.json; manifest_digest проверяется по каноническому JSON с нулевым значением этого поля.",
        f"{TECHNICAL_REPORT_FILENAME} сохраняет прежний формат для аудита.", "",
    ]
    files[ENTRYPOINT_FILENAME] = ("\n".join(lines) + "\n").encode("utf-8")
    guide = [
        "# Как читать разделы архива", "",
        "Данные в таблицах взяты из сохранённого расчёта. Отсутствующий раздел не означает нулевое значение.",
    ]
    for item in previous.manifest.sections:
        purpose, _, _ = _SECTION_GUIDE[item.name]
        guide.extend(["", f"## {section(item.name)}", "", humanize(purpose),
                      f"Состояние: {status(item.status)}. Записей: {item.record_count}."])
    guide.extend(["", "## Технические подробности", "",
                  f"Версия представления: {VERSION}.",
                  "Имена CSV соответствуют машинным разделам: " + ", ".join(item.filename for item in previous.manifest.sections) + ".",
                  "Поля path, value, source_ref, status и исходные ключи доступны в CSV. Снимки и контрольные суммы находятся в Snapshot.json и manifest.json.", ""])
    files[GUIDE_FILENAME] = ("\n".join(guide) + "\n").encode("utf-8")
    artifacts = [_artifact(name, "application/pdf" if name.endswith(".pdf") else "application/json" if name.endswith(".json") else "text/csv; charset=utf-8" if name.endswith(".csv") else "text/markdown; charset=utf-8", payload)
                 for name, payload in sorted(files.items())]
    body = previous.manifest.model_dump(mode="python")
    body.update(schema_version="calculation-evidence-export-manifest-v3",
                export_policy_version="calculation-evidence-export-policy-v3",
                generator_version="snapshot-evidence-export-v3",
                presentation_version=VERSION, sections=previous.manifest.sections, artifacts=artifacts,
                bundle_content_digest=semantic_digest([item.model_dump(mode="json") for item in artifacts]),
                manifest_digest="sha256:" + "0" * 64)
    body["manifest_digest"] = semantic_digest(EvidenceExportManifestV3.model_construct(**body).model_dump(mode="json"))
    manifest = EvidenceExportManifestV3.model_validate(body)
    manifest_payload = json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted({**files, "manifest.json": manifest_payload}.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return EvidenceExportPackage(manifest=manifest, archive=buffer.getvalue(), files=files)


_SECTION_GUIDE = {
    "Inputs": ("Какие исходные величины были сохранены.", "path, value и status; отличайте NULL от 0.", "input_snapshot этого run."),
    "Selection": ("Какой парк или кандидат выбран и почему.", "selected_fleet, ranking, recommendation и причины отказа.", "result_snapshot и C11, если они входят в run."),
    "Scenarios": ("Какие варианты покупки, RaaS и неопределённости есть в результате.", "acquisition, uncertainty, status и reason_codes.", "result_snapshot; отсутствующая ветка не вычислялась."),
    "CashFlow": ("Какие денежные потоки сохранены по годам.", "year, baseline, scenario, differential и source_ref.", "финансовые ledger в result_snapshot; CSV не пересчитывает NPV."),
    "Sensitivity": ("Какие изменения параметров были проверены.", "параметр, направление, delta NPV и причины BLOCKED.", "sensitivity в result_snapshot."),
    "Sources": ("На каких ссылках, фактах и допущениях основан результат.", "source_ref, provenance_ref, статус источника.", "поля provenance/assumption/evidence в result_snapshot; допущение не является офертой."),
    "Trace": ("Как связаны входы, формулы и выходы.", "node_id, formula_id, input_refs и status.", "trace_snapshot или trace-узлы result_snapshot."),
    "Simulation": ("Есть ли C23 report внутри именно этого immutable run.", "request_id, report_digest, SLA verdict и ограничения.", "simulation_report в result_snapshot; поздние C23 artifacts хранятся отдельно по request_id."),
    "Versions": ("Какие версии каталога и правил использованы.", "catalog, rules, economics, application, version_bindings.", "версии AnalysisRun и version_bindings_snapshot."),
}


def _human_guide(sections: list[EvidenceSectionV1]) -> bytes:
    lines = [
        "# Как читать файлы архива", "",
        "Во всех CSV столбцы path, value, source_ref, status. Значения взяты из сохранённых снимков; экспорт не запускает расчёт.",
        "NOT_AVAILABLE означает, что раздел отсутствует в этом run. Строка-заглушка и record_count=0 не означают ноль, сбой или подтверждённый факт.",
        "",
    ]
    for section in sections:
        purpose, fields, source = _SECTION_GUIDE[section.name]
        lines.extend([
            f"## {section.filename} — {section.status}", "",
            f"Что проверяет: {purpose}",
            f"Что смотреть: {fields}",
            f"Откуда взято: {source}",
            f"Записей: {section.record_count}. " + (f"Причина пустого раздела: {section.reason_code}." if section.reason_code else "Данные есть в сохранённом run."),
            "",
        ])
    lines.extend([
        "## Snapshot.json", "",
        "Что проверяет: полный машинный снимок run без потерь от выборки CSV.",
        "Что смотреть: input_snapshot, result_snapshot, scenario_spec_snapshot, trace_snapshot, версии и source_snapshot_digests.",
        "Откуда взято: неизменяемый AnalysisRun; каждый исходный снимок сверен с сохранённым SHA-256.",
        "Если есть C11_Snapshot.json, это проверенный связанный технический run с собственными входом, результатом и trace. Его run_id и digest указаны также в manifest.json.",
        "",
        "## C23 и подтверждение фактов", "",
        "C23 report доказывает только результат своей сохранённой модели очереди и SLA при указанных входах. Поздние append-only C23 artifacts не включаются в этот неизменяемый пакет run; их открывают отдельно по request_id.",
        "Расчёт и его SHA-256 доказывают воспроизводимость вычислений. Паспорт, цена, состав поставки и доступность требуют отдельного документа изготовителя или поставщика.",
        "",
    ])
    return ("\n".join(lines) + "\n").encode("utf-8")


def _human_entrypoint(
    run: EvidenceRunSnapshotV1,
    digests: dict[str, str | None],
    sections: list[EvidenceSectionV1],
    linked: EvidenceRunSnapshotV1 | None,
) -> bytes:
    missing = [item.name for item in sections if item.status == "NOT_AVAILABLE"]
    c05 = run.result_snapshot.get("c05")
    c05_state = (c05.get("eligibility") if isinstance(c05, dict) else None) or run.diagnostics.get("constraint_eligibility")
    capacity_label = run.run_id if run.run_kind == "CAPACITY_ANALYSIS" else linked.run_id if linked is not None else run.input_snapshot.get("capacity_run_id") or "NOT_AVAILABLE"
    report_kind = ("Техническая мощность C11" if run.run_kind == "CAPACITY_ANALYSIS" else
                   "Частичная экономика" if run.result_snapshot.get("schema_version") == "economics-partial-result-v1" else
                   "Полная экономика: baseline, покупка и RaaS" if run.result_snapshot.get("schema_version") in {"commercial-scenarios-bundle-v2", "commercial-scenarios-bundle-v3"} else
                   "Исторический расчёт")
    lines = [
        "# НАЧНИТЕ ЗДЕСЬ", "",
        f"**Отчёт № {run.run_id}** · дата сохранённого расчёта {run.finished_at:%d.%m.%Y}.",
        f"Вид результата: {report_kind}.",
        *([f"Глубина расчёта: { {'BASIC': 'Базовый', 'ADVANCED': 'Углублённый', 'FULL': 'Полный'}.get(run.input_snapshot.get('economics', {}).get('calculation_depth'), 'Не указана') }."]
          if run.input_snapshot.get("economics", {}).get("calculation_depth") else []),
        f"Проект: {run.project_id}. Тип run: {run.run_kind}. Ревизия: {run.revision_id or 'NOT_AVAILABLE'}.",
        f"Версии: правила {run.versions.get('rules') or 'NOT_AVAILABLE'}; экономика {run.versions.get('economics') or 'NOT_AVAILABLE'}; приложение {run.versions.get('application') or 'NOT_AVAILABLE'}.",
        f"SHA-256 сохранённого результата: {digests['result']}. Полный перечень SHA-256 файлов — в manifest.json.",
        "",
        "## Что открывать", "",
        f"1. **{READABLE_REPORT_FILENAME}** — читаемый русский отчёт по сохранённым значениям.",
        f"2. **{GUIDE_FILENAME}** — что проверяет каждый CSV, какие поля смотреть и откуда они взяты.",
        "3. **Inputs.csv → Selection.csv → Scenarios.csv → CashFlow.csv** — путь от ввода до результата; остальные CSV раскрывают чувствительность, источники, трассировку, C23 и версии.",
        "4. **Snapshot.json** — полный машинный снимок; при наличии **C11_Snapshot.json** — связанный расчёт мощности; **manifest.json** — контрольные суммы и статусы разделов.",
        "",
        "## Что пакет подтверждает и что остаётся открытым", "",
        "Пакет подтверждает сохранённые входы, результаты и версии указанного run при совпадении контрольных сумм. Он не является подтверждением характеристик или коммерческих условий поставщика.",
        f"C05: {c05_state or 'проверьте сохранённые ограничения'}; пригодность к внедрению и закупке подтверждаются отдельно.",
        f"Разделы без данных: {', '.join(missing) if missing else 'нет'}. NOT_AVAILABLE — нет данных в этом run, а не ноль.",
        f"Источник C11: {capacity_label}; C23 evidence из поздних append-only artifacts проверяйте отдельно по request_id.",
        "",
        "## Проверка целостности", "",
        "Сверьте run_id и дату здесь, в PDF и manifest.json. Для каждого файла кроме manifest.json сравните SHA-256 с artifacts в manifest.json.",
        "Сам manifest.json проверяется полем manifest_digest: SHA-256 канонического JSON с временным нулевым значением этого поля.",
        f"{TECHNICAL_REPORT_FILENAME} — старый машинный дамп для аудита; он не является главным отчётом.",
        "",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_evidence_export_v2(
    run: EvidenceRunSnapshotV1,
    capacity_run: EvidenceRunSnapshotV1 | None = None,
) -> EvidenceExportPackage:
    """Build a deterministic, navigable archive from verified saved snapshots."""

    from calculation.readable_report import build_readable_report

    base = build_evidence_export(run)
    digests = _verify_snapshots(run)
    readable_pdf, source_digest = build_readable_report(run, capacity_run)
    if source_digest != digests["result"]:
        raise EvidenceExportIntegrityError("readable report source does not match run")
    linked_digests = _verify_snapshots(capacity_run) if capacity_run is not None else None
    files = dict(base.files)
    files[TECHNICAL_REPORT_FILENAME] = files.pop("Report.pdf")
    files[READABLE_REPORT_FILENAME] = readable_pdf
    files[GUIDE_FILENAME] = _human_guide(base.manifest.sections)
    files[ENTRYPOINT_FILENAME] = _human_entrypoint(run, digests, base.manifest.sections, capacity_run)
    if capacity_run is not None:
        linked_document = {
            "schema_version": "calculation-evidence-linked-capacity-v1",
            "run_id": capacity_run.run_id,
            "project_id": capacity_run.project_id,
            "snapshot_captured_at": capacity_run.finished_at.isoformat(),
            "versions": capacity_run.versions,
            "source_snapshot_digests": linked_digests,
            "input_snapshot": capacity_run.input_snapshot,
            "result_snapshot": capacity_run.result_snapshot,
            "trace_snapshot": capacity_run.trace_snapshot,
            "version_bindings_snapshot": capacity_run.version_bindings_snapshot,
        }
        files["C11_Snapshot.json"] = json.dumps(linked_document, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    artifacts = [
        _artifact(name, "application/pdf" if name.endswith(".pdf") else "application/json" if name.endswith(".json") else "text/csv; charset=utf-8" if name.endswith(".csv") else "text/markdown; charset=utf-8", payload)
        for name, payload in sorted(files.items())
    ]
    limitations = [
        *base.manifest.limitations,
        "c23-append-only-artifacts-not-in-this-run-snapshot",
        "scenario-assumptions-are-not-vendor-confirmations",
    ]
    manifest_body = {
        "schema_version": "calculation-evidence-export-manifest-v2",
        "run_id": run.run_id,
        "project_id": run.project_id,
        "run_kind": run.run_kind,
        "revision_id": run.revision_id,
        "snapshot_captured_at": run.finished_at,
        "export_policy_version": EXPORT_POLICY_VERSION_V2,
        "generator_version": EXPORT_GENERATOR_VERSION_V2,
        "versions": run.versions,
        "source_snapshot_digests": digests,
        "linked_capacity_run_id": capacity_run.run_id if capacity_run else None,
        "linked_capacity_snapshot_digests": linked_digests,
        "entrypoint_filename": ENTRYPOINT_FILENAME,
        "report_filename": READABLE_REPORT_FILENAME,
        "sections": base.manifest.sections,
        "artifacts": artifacts,
        "bundle_content_digest": semantic_digest([item.model_dump(mode="json") for item in artifacts]),
        "limitations": limitations,
        "manifest_digest": "sha256:" + "0" * 64,
    }
    manifest_body["manifest_digest"] = semantic_digest(
        EvidenceExportManifestV2.model_construct(**manifest_body).model_dump(mode="json")
    )
    manifest = EvidenceExportManifestV2.model_validate(manifest_body)
    manifest_payload = json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted({**files, "manifest.json": manifest_payload}.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return EvidenceExportPackage(manifest=manifest, archive=archive_buffer.getvalue(), files=files)


__all__ = [
    "EvidenceExportIntegrityError", "EvidenceExportManifestV1", "EvidenceExportManifestV2", "EvidenceExportManifestV3", "EvidenceExportManifestV4",
    "EvidenceExportPackage", "EvidenceRunSnapshotV1", "build_evidence_export",
    "build_evidence_export_v2", "build_evidence_export_v3",
]
