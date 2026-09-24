"""Immutable, owner-scoped storage for C23 reports bound to saved runs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from calculation.scheduling import SimulationReportV1, SimulationRequestV1
from calculation_contracts import semantic_digest
from persistence_models import AnalysisRun, Project, SimulationArtifact


class SimulationArtifactIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class StoredSimulationEvidence:
    artifact_id: uuid.UUID
    analysis_run_id: uuid.UUID
    project_id: uuid.UUID
    request: SimulationRequestV1
    report: SimulationReportV1
    request_digest: str
    report_digest: str
    scenario_spec_digest: str


def owned_run(db: Session, owner_id: uuid.UUID, project_id: uuid.UUID,
              run_id: uuid.UUID) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun).join(Project, Project.id == AnalysisRun.project_id).where(
            AnalysisRun.id == run_id,
            AnalysisRun.project_id == project_id,
            AnalysisRun.run_kind == "FULL_ANALYSIS",
            AnalysisRun.status == "SUCCEEDED",
            Project.owner_id == owner_id,
            Project.status == "ACTIVE",
        )
    )


def verify_run_binding(run: AnalysisRun, request: SimulationRequestV1) -> str:
    spec_digest = semantic_digest(request.scenario_spec).removeprefix("sha256:")
    if (run.scenario_spec_sha256 != spec_digest
            or run.scenario_spec_snapshot != request.scenario_spec.model_dump(mode="json")
            or str(run.project_id) != request.project_id):
        raise SimulationArtifactIntegrityError("simulation ScenarioSpec does not match the saved run")
    return spec_digest


def save_artifact(db: Session, owner_id: uuid.UUID, project_id: uuid.UUID,
                  run_id: uuid.UUID, request: SimulationRequestV1,
                  report: SimulationReportV1) -> StoredSimulationEvidence:
    run = owned_run(db, owner_id, project_id, run_id)
    if run is None:
        raise SimulationArtifactIntegrityError("saved analysis run is unavailable")
    spec_digest = verify_run_binding(run, request)
    if (report.request_id != request.request_id
            or report.project_id != request.project_id
            or report.tenant_id != request.tenant_id
            or report.scenario_revision_id != request.scenario_spec.revision_id
            or report.replay.scenario_spec_digest != f"sha256:{spec_digest}"
            or report.replay.canonical_request_digest != semantic_digest(request)):
        raise SimulationArtifactIntegrityError("C23 report is not bound to the saved request")
    existing = load_artifact(db, owner_id, project_id, run_id, request.request_id)
    if existing is not None:
        if existing.request_digest != semantic_digest(request) or existing.report_digest != semantic_digest(report):
            raise SimulationArtifactIntegrityError("immutable simulation request_id collision")
        return existing
    artifact = SimulationArtifact(
        analysis_run_id=run_id, project_id=project_id, request_id=request.request_id,
        artifact_version="simulation-artifact-v1",
        request_snapshot=request.model_dump(mode="json"),
        report_snapshot=report.model_dump(mode="json"),
        request_sha256=semantic_digest(request).removeprefix("sha256:"),
        report_sha256=semantic_digest(report).removeprefix("sha256:"),
        scenario_spec_sha256=spec_digest,
    )
    db.add(artifact)
    db.commit()
    return load_artifact(db, owner_id, project_id, run_id, request.request_id)


def load_artifact(db: Session, owner_id: uuid.UUID, project_id: uuid.UUID,
                  run_id: uuid.UUID, request_id: str) -> StoredSimulationEvidence | None:
    run = owned_run(db, owner_id, project_id, run_id)
    if run is None:
        return None
    artifact = db.scalar(select(SimulationArtifact).where(
        SimulationArtifact.analysis_run_id == run_id,
        SimulationArtifact.project_id == project_id,
        SimulationArtifact.request_id == request_id,
    ))
    if artifact is None:
        return None
    if artifact.artifact_version != "simulation-artifact-v1":
        raise SimulationArtifactIntegrityError("unknown simulation artifact version")
    request = SimulationRequestV1.model_validate(artifact.request_snapshot)
    report = SimulationReportV1.model_validate(artifact.report_snapshot)
    if (artifact.request_sha256 != semantic_digest(request).removeprefix("sha256:")
            or artifact.report_sha256 != semantic_digest(report).removeprefix("sha256:")
            or artifact.scenario_spec_sha256 != run.scenario_spec_sha256
            or artifact.scenario_spec_sha256 != semantic_digest(request.scenario_spec).removeprefix("sha256:")
            or report.replay.canonical_request_digest != semantic_digest(request)
            or report.replay.scenario_spec_digest != f"sha256:{artifact.scenario_spec_sha256}"
            or report.request_id != request.request_id
            or report.project_id != request.project_id
            or report.tenant_id != request.tenant_id
            or report.scenario_revision_id != request.scenario_spec.revision_id):
        raise SimulationArtifactIntegrityError("stored C23 artifact digest binding mismatch")
    return StoredSimulationEvidence(
        artifact_id=artifact.id, analysis_run_id=run_id, project_id=project_id,
        request=request, report=report,
        request_digest=f"sha256:{artifact.request_sha256}",
        report_digest=f"sha256:{artifact.report_sha256}",
        scenario_spec_digest=f"sha256:{artifact.scenario_spec_sha256}",
    )


__all__ = ["SimulationArtifactIntegrityError", "StoredSimulationEvidence", "owned_run", "verify_run_binding", "save_artifact", "load_artifact"]
