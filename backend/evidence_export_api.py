"""Owner-scoped C26 API for immutable calculation evidence exports."""

from __future__ import annotations

import uuid
import hashlib
from collections.abc import Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import AuthContext, require_auth_context
from calculation.evidence_export import (
    EvidenceExportIntegrityError,
    EvidenceExportManifestV4,
    EvidenceRunSnapshotV1,
)
from calculation.final_export import build_final_export
from calculation.investor_report import VERSION as INVESTOR_PRESENTATION, build_investor_report
from database import database_session
from persistence_models import AnalysisRun, Project, SimulationArtifact
from simulation_artifacts import SimulationArtifactIntegrityError, load_artifact


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

    def sources_for(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: AuthContext,
        db: Session,
        simulation_request_id: str | None = None,
    ):
        run = run_loader(db, project_id, run_id, context.user.id)
        if run is None:
            # Missing, inactive and another tenant's run deliberately look identical.
            raise HTTPException(status_code=404, detail="analysis run not found")
        try:
            chosen = simulation_request_id or (db.scalar(
                select(SimulationArtifact.request_id).where(
                    SimulationArtifact.project_id == project_id,
                    SimulationArtifact.analysis_run_id == run_id,
                ).order_by(SimulationArtifact.created_at.desc(), SimulationArtifact.id.desc()).limit(1)
            ) if hasattr(db, "scalar") else None)
            simulation = load_artifact(db, context.user.id, project_id, run_id, chosen) if chosen and hasattr(db, "scalar") else None
            if simulation_request_id is not None and simulation is None:
                raise HTTPException(status_code=404, detail="simulation artifact not found")
            return run, linked_capacity_for(run, project_id, context, db), simulation
        except (EvidenceExportIntegrityError, SimulationArtifactIntegrityError) as exc:
            raise HTTPException(status_code=409, detail="analysis snapshot integrity check failed") from exc

    def package_for(project_id, run_id, context, db, simulation_request_id=None):
        try:
            return build_final_export(*sources_for(project_id, run_id, context, db, simulation_request_id))
        except (EvidenceExportIntegrityError, SimulationArtifactIntegrityError) as exc:
            raise HTTPException(status_code=409, detail="analysis snapshot integrity check failed") from exc

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/investor-report.pdf")
    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/investor-report-preview.pdf")
    def investor_report(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        request: Request,
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        """A separate versioned view. Historical report/ZIP endpoints keep their bytes."""
        run, linked, simulation = sources_for(project_id, run_id, context, db, simulation_request_id)
        try:
            pdf, source_digest = build_investor_report(run, linked, simulation)
        except (EvidenceExportIntegrityError, SimulationArtifactIntegrityError) as exc:
            raise HTTPException(status_code=409, detail="analysis snapshot integrity check failed") from exc
        depth = run.input_snapshot.get("economics", {}).get("calculation_depth") or "UNSPECIFIED"
        filename = f"Рободовод, инвестиционная оценка от {run.finished_at:%d.%m.%Y}.pdf"
        disposition = "inline" if request.url.path.endswith("-preview.pdf") else "attachment"
        return Response(content=pdf, media_type="application/pdf", headers={
            "Content-Disposition": f'{disposition}; filename="Robodovod-investor-report.pdf"; filename*=UTF-8\'\'{quote(filename, safe="")}',
            "X-Report-Source-Digest": source_digest,
            "X-Report-Presentation": INVESTOR_PRESENTATION,
            "X-Report-Depth": depth,
            "X-Simulation-Report-Digest": simulation.report_digest if simulation else "none",
            "ETag": f'"sha256:{hashlib.sha256(pdf).hexdigest()}"',
            "Cache-Control": "private, no-store",
        })

    @router.get(
        "/projects/{project_id}/analysis-runs/{run_id}/exports/manifest",
        response_model=EvidenceExportManifestV4,
    )
    def get_manifest(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        response: Response,
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        return package_for(project_id, run_id, context, db, simulation_request_id).manifest

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/evidence.zip")
    def download_bundle(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        package = package_for(project_id, run_id, context, db, simulation_request_id)
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
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        package = package_for(project_id, run_id, context, db, simulation_request_id)
        pdf = package.files[package.manifest.report_filename]
        source_digest = package.manifest.source_snapshot_digests["result"]
        filename = f"Рободовод, отчёт от {package.manifest.snapshot_captured_at:%d.%m.%Y}.pdf"
        fallback = f"Robodovod-report-{package.manifest.snapshot_captured_at:%Y-%m-%d}.pdf"
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
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        package = package_for(project_id, run_id, context, db, simulation_request_id)
        pdf = package.files[package.manifest.report_filename]
        source_digest = package.manifest.source_snapshot_digests["result"]
        filename = f"Рободовод, отчёт от {package.manifest.snapshot_captured_at:%d.%m.%Y}.pdf"
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

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/comparison.csv")
    def download_comparison_csv(
        project_id: uuid.UUID, run_id: uuid.UUID,
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        package = package_for(project_id, run_id, context, db, simulation_request_id)
        return Response(content=package.files["Сравнение.csv"], media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="Robodovod-comparison.csv"',
                                 "X-Export-Manifest-Digest": package.manifest.manifest_digest,
                                 "Cache-Control": "private, no-store"})

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/result.xlsx")
    def download_result_xlsx(
        project_id: uuid.UUID, run_id: uuid.UUID,
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        package = package_for(project_id, run_id, context, db, simulation_request_id)
        return Response(content=package.files["Результат.xlsx"],
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": 'attachment; filename="Robodovod-result.xlsx"',
                                 "X-Export-Manifest-Digest": package.manifest.manifest_digest,
                                 "Cache-Control": "private, no-store"})

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/exports/visualization.svg")
    def download_visualization_svg(
        project_id: uuid.UUID, run_id: uuid.UUID,
        simulation_request_id: str | None = None,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        package = package_for(project_id, run_id, context, db, simulation_request_id)
        if package.manifest.visualization_filename is None:
            raise HTTPException(status_code=404, detail="saved simulation visualization not found")
        return Response(content=package.files["Схема_2D.svg"], media_type="image/svg+xml",
                        headers={"Content-Disposition": 'attachment; filename="Robodovod-simulation-2d.svg"',
                                 "X-Export-Manifest-Digest": package.manifest.manifest_digest,
                                 "Cache-Control": "private, no-store"})

    return router


__all__ = ["create_evidence_export_router"]
