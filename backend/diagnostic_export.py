"""Bounded, administrator-only diagnostic snapshot inputs.

This is deliberately not a PostgreSQL restore backup. It contains readable
calculation state and recent backend request metadata, never authentication
material, environment files, raw request bodies or Docker socket access.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import uuid
import zipfile
from collections import deque
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

import catalog_models  # noqa: F401 -- register mappings on shared metadata
import persistence_models  # noqa: F401 -- register mappings on shared metadata
from storage_models import Base


MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_REQUEST_EVENTS = 5000
TABLE_NAMES = (
    "users",
    "projects",
    "project_files",
    "project_file_imports",
    "scenarios",
    "analysis_runs",
    "simulation_artifacts",
    "analysis_run_economics_versions",
    "economics_route_activations",
    "audit_entries",
    "project_deletion_jobs",
    "catalog_versions",
    "source_artifacts",
    "catalog_version_sources",
    "import_runs",
    "catalog_activations",
    "manufacturers",
    "catalog_source_rows",
    "equipment_models",
    "catalog_media_assets",
    "catalog_position_media",
    "catalog_description_imports",
    "catalog_position_enrichments",
    "equipment_applicability",
    "field_evidence",
    "spec_observations",
    "resolved_spec_facts",
    "resolved_spec_fact_evidence",
    "procurement_options",
)
EXCLUDED_COLUMNS = {"users": {"password_hash"}}
_SENSITIVE_KEY = re.compile(
    r"password|passphrase|secret|token|credential|authorization|cookie|csrf|api[_-]?key|database[_-]?url",
    re.IGNORECASE,
)
_REQUEST_EVENTS: deque[dict[str, Any]] = deque(maxlen=MAX_REQUEST_EVENTS)
_REQUEST_EVENTS_LOCK = threading.Lock()


class DiagnosticArchiveTooLarge(RuntimeError):
    """The export exceeded its explicit safety limit; no partial ZIP is sent."""


def record_http_event(
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    error_type: str | None = None,
) -> None:
    """Keep safe request metadata only: never URL query, body, cookies or headers."""

    if not path.startswith("/api/") or path == "/api/admin/diagnostics/export":
        return
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": method[:12],
        "path": path[:256],
        "status_code": status_code,
        "duration_ms": duration_ms,
    }
    if error_type is not None:
        event["error_type"] = error_type[:80]
    with _REQUEST_EVENTS_LOCK:
        _REQUEST_EVENTS.append(event)


def request_events_snapshot() -> list[dict[str, Any]]:
    with _REQUEST_EVENTS_LOCK:
        return list(_REQUEST_EVENTS)


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>" if _SENSITIVE_KEY.search(str(key)) else _safe_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, bytes):
        return {"binary_omitted_bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    return value


def _json_line(value: dict[str, Any]) -> bytes:
    return (json.dumps(_safe_value(value), ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def build_diagnostic_archive(db: Session) -> bytes:
    """Export an allowlisted, bounded JSONL snapshot from the current database."""

    output = io.BytesIO()
    total_bytes = 0
    members: dict[str, dict[str, Any]] = {}

    def write_rows(archive: zipfile.ZipFile, name: str, rows: Any) -> None:
        nonlocal total_bytes
        digest = hashlib.sha256()
        count = 0
        with archive.open(name, "w") as target:
            for row in rows:
                line = _json_line(row)
                total_bytes += len(line)
                if total_bytes > MAX_UNCOMPRESSED_BYTES:
                    raise DiagnosticArchiveTooLarge("diagnostic archive exceeds 128 MiB")
                target.write(line)
                digest.update(line)
                count += 1
        members[name] = {"rows": count, "sha256": digest.hexdigest()}

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table_name in TABLE_NAMES:
            table = Base.metadata.tables[table_name]
            columns = [
                column for column in table.columns
                if column.name not in EXCLUDED_COLUMNS.get(table_name, set())
            ]
            query = select(*columns).select_from(table).order_by(*table.primary_key.columns)
            result = db.execute(query.execution_options(stream_results=True))
            write_rows(
                archive,
                f"database/{table_name}.jsonl",
                (dict(row._mapping) for row in result),
            )

        write_rows(archive, "logs/backend-requests.jsonl", request_events_snapshot())
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        manifest = {
            "schema_version": "diagnostic-bundle-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "alembic_revision": revision,
            "scope": "all tenants; confidential diagnostic snapshot, not a restore backup",
            "members": members,
            "excluded": [
                "users.password_hash",
                "user_sessions and session token/CSRF hashes",
                "environment files, secrets, raw request bodies and headers",
                "uploaded file bytes and Docker/Caddy container logs",
            ],
            "log_window": f"last {MAX_REQUEST_EVENTS} backend API requests since process start",
        }
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"),
        )
    return output.getvalue()
