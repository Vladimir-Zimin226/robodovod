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


@dataclass(frozen=True)
class EvidenceExportPackage:
    manifest: EvidenceExportManifestV1
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
    if section == "Simulation" and result.get("schema_version") in ("simulation-report-v1", "simulation-report-v2"):
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


__all__ = [
    "EvidenceExportIntegrityError", "EvidenceExportManifestV1",
    "EvidenceExportPackage", "EvidenceRunSnapshotV1", "build_evidence_export",
]
