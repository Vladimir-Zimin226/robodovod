"""Owner-scoped C26 API for immutable calculation evidence exports."""

from __future__ import annotations

import uuid
import hashlib
from collections.abc import Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import AuthContext, require_auth_context
from calculation.evidence_export import (
    EvidenceExportIntegrityError,
    EvidenceExportManifestV3,
    EvidenceRunSnapshotV1,
    build_evidence_export_v3,
)
from calculation.readable_report import build_readable_report
from presentation import VERSION as PRESENTATION_VERSION
from database import database_session
from persistence_models import AnalysisRun, Project


RunLoader = Callable[[Session, uuid.UUID, uuid.UUID, uuid.UUID], EvidenceRunSnapshotV1 | None]


def _load_owned_succeeded_run(
    db: Session,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> EvidenceRunSnapshotV1 | None:
    run = db.scalar(
        select(AnalysisRun)
        .join(Project, Project.id == AnalysisRun.project_id)
        .where(
            AnalysisRun.id == run_id,
            AnalysisRun.project_id == project_id,
            AnalysisRun.status == "SUCCEEDED",
            Project.owner_id == owner_id,
            Project.status == "ACTIVE",
        )
    )
    if run is None:
        return None
    if run.result_snapshot is None or run.finished_at is None:
        raise EvidenceExportIntegrityError("succeeded run is missing its result snapshot")
    return EvidenceRunSnapshotV1(
        run_id=str(run.id),
        project_id=str(run.project_id),
        run_kind=run.run_kind,
        status=run.status,
        revision_id=run.revision_id,
        created_at=run.created_at,
        finished_at=run.finished_at,
        versions={
            "catalog": run.catalog_version_code,
            "rules": run.rules_version,
            "economics": run.economics_version,
            "object_profile": run.object_profile_version,
            "application": run.application_version,
        },
        checksums={
            "input": run.input_sha256,
            "result": run.result_sha256,
            "scenario_spec": run.scenario_spec_sha256,
            "trace": run.trace_sha256,
            "version_bindings": run.version_bindings_sha256,
        },
        input_snapshot=run.input_snapshot,
        result_snapshot=run.result_snapshot,
        scenario_spec_snapshot=run.scenario_spec_snapshot,
        trace_snapshot=run.trace_snapshot,
        version_bindings_snapshot=run.version_bindings_snapshot,
        diagnostics=run.diagnostics,
    )


def create_evidence_export_router(
    run_loader: RunLoader = _load_owned_succeeded_run,
    capacity_loader: RunLoader = _load_owned_succeeded_run,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    def linked_capacity_for(
        run: EvidenceRunSnapshotV1,
        project_id: uuid.UUID,
        context: AuthContext,
        db: Session,
    ) -> EvidenceRunSnapshotV1 | None:
        linked_id = run.input_snapshot.get("capacity_run_id")
        if linked_id is None:
            return None
        try:
            capacity_id = uuid.UUID(str(linked_id))
        except ValueError as exc:
            raise EvidenceExportIntegrityError("invalid linked capacity run id") from exc
        return capacity_loader(db, project_id, capacity_id, context.user.id)

    def package_for(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: AuthContext,
        db: Session,
    ):
        run = run_loader(db, project_id, run_id, context.user.id)
        if run is None:
            # Missing, inactive and another tenant's run deliberately look identical.
            raise HTTPException(status_code=404, detail="analysis run not found")
        try:
            return build_evidence_export_v3(run, linked_capacity_for(run, project_id, context, db))
        except EvidenceExportIntegrityError as exc:
            raise HTTPException(status_code=409, detail="analysis snapshot integrity check failed") from exc

    @router.get(
        "/projects/{project_id}/analysis-runs/{run_id}/exports/manifest",
        response_model=EvidenceExportManifestV3,
    )
    def get_manifest(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        response: Response,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        return package_for(project_id, run_id, context, db).manifest

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/evidence.zip")
    def download_bundle(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        package = package_for(project_id, run_id, context, db)
        filename = f"Рободовод, архив расчёта от {package.manifest.snapshot_captured_at:%d.%m.%Y}.zip"
        fallback = f"Robodovod-evidence-{package.manifest.snapshot_captured_at:%Y-%m-%d}.zip"
        return Response(
            content=package.archive,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename, safe="")}',
                "X-Export-Manifest-Digest": package.manifest.manifest_digest,
                "ETag": f'"{package.manifest.manifest_digest}"',
                "Cache-Control": "private, no-store",
            },
        )

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/report.pdf")
    def download_readable_report(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        run = run_loader(db, project_id, run_id, context.user.id)
        if run is None:
            raise HTTPException(status_code=404, detail="analysis run not found")
        try:
            linked = linked_capacity_for(run, project_id, context, db)
            pdf, source_digest = build_readable_report(run, linked, presentation_version=PRESENTATION_VERSION)
        except EvidenceExportIntegrityError as exc:
            raise HTTPException(status_code=409, detail="analysis snapshot integrity check failed") from exc
        filename = f"Рободовод, отчёт от {run.finished_at:%d.%m.%Y}.pdf"
        fallback = f"Robodovod-report-{run.finished_at:%Y-%m-%d}.pdf"
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename, safe="")}',
                "X-Report-Source-Digest": source_digest,
                "ETag": f'"sha256:{hashlib.sha256(pdf).hexdigest()}"',
                "Cache-Control": "private, no-store",
            },
        )

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/report-preview.pdf")
    def preview_readable_report(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        run = run_loader(db, project_id, run_id, context.user.id)
        if run is None:
            raise HTTPException(status_code=404, detail="analysis run not found")
        try:
            linked = linked_capacity_for(run, project_id, context, db)
            pdf, source_digest = build_readable_report(run, linked, presentation_version=PRESENTATION_VERSION)
        except EvidenceExportIntegrityError as exc:
            raise HTTPException(status_code=409, detail="analysis snapshot integrity check failed") from exc
        filename = f"Рободовод, отчёт от {run.finished_at:%d.%m.%Y}.pdf"
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=Robodovod-report.pdf; filename*=UTF-8''{quote(filename, safe='')}",
                "X-Report-Source-Digest": source_digest,
                "ETag": f'"sha256:{hashlib.sha256(pdf).hexdigest()}"',
                "Cache-Control": "private, no-store",
            },
        )

    return router


__all__ = ["create_evidence_export_router"]
