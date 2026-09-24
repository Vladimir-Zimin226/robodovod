"""C24 authenticated API adapter for the C23 simulation service.

The adapter owns only execution lifecycle state.  All simulation semantics and
KPI values remain owned by :mod:`calculation.scheduling`.
"""

from __future__ import annotations

import threading
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import AuthContext, require_auth_context, require_csrf
from calculation.scheduling import (
    SimulationErrorV1,
    SimulationProgressV1,
    SimulationReportV1,
    SimulationRequestV1,
    run_simulation,
)
from calculation_contracts import Digest, StableId, StrictContractModel, semantic_digest
from database import database_session, get_database
from persistence_models import Project
from simulation_artifacts import (
    SimulationArtifactIntegrityError, load_artifact, owned_run,
    save_artifact, verify_run_binding,
)


class SimulationRunStateV1(StrictContractModel):
    """Strict polling envelope bound to one request and scenario revision."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)
    schema_version: Literal["simulation-run-state-v1"] = "simulation-run-state-v1"
    request_id: StableId
    tenant_id: StableId
    project_id: StableId
    scenario_revision_id: Annotated[str, Field(pattern=r"^calc_[0-9a-f]{16}$")]
    request_digest: Digest
    state: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    progress: SimulationProgressV1
    report: SimulationReportV1 | None
    error: SimulationErrorV1 | None

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> "SimulationRunStateV1":
        if self.progress.request_id != self.request_id:
            raise ValueError("progress request binding mismatch")
        if self.report is not None and (
            self.report.request_id != self.request_id
            or self.report.scenario_revision_id != self.scenario_revision_id
            or self.report.tenant_id != self.tenant_id
            or self.report.project_id != self.project_id
        ):
            raise ValueError("report binding mismatch")
        if self.error is not None and (
            self.error.request_id != self.request_id
            or self.error.scenario_revision_id != self.scenario_revision_id
        ):
            raise ValueError("error binding mismatch")
        if self.state == "SUCCEEDED" and (self.report is None or self.error is not None):
            raise ValueError("successful run requires only a report")
        if self.state in ("FAILED", "CANCELLED") and (
            self.error is None or self.report is not None
        ):
            raise ValueError("failed run requires only an error")
        if self.state in ("PENDING", "RUNNING") and (
            self.report is not None or self.error is not None
        ):
            raise ValueError("active run cannot contain a terminal payload")
        return self


Runner = Callable[..., SimulationReportV1 | SimulationErrorV1]


@dataclass
class _Job:
    request: SimulationRequestV1
    request_digest: str
    state: str = "PENDING"
    progress: SimulationProgressV1 = field(init=False)
    report: SimulationReportV1 | None = None
    error: SimulationErrorV1 | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    on_success: Callable[[SimulationRequestV1, SimulationReportV1], None] | None = None
    binding_id: str | None = None

    def __post_init__(self) -> None:
        self.progress = SimulationProgressV1(
            request_id=self.request.request_id,
            processed_events=0,
            total_events=0,
        )


class SimulationJobRegistry:
    """Thread-safe, process-local lifecycle registry for C24.

    Persistence of reports is intentionally deferred; saved-run storage is not
    changed by C24.  The request digest makes retries idempotent and rejects a
    request-id collision with different semantic content.
    """

    def __init__(
        self,
        *,
        runner: Runner = run_simulation,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._runner = runner
        self._executor = executor or ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="simulation-c24"
        )
        self._lock = threading.RLock()
        self._jobs: dict[tuple[str, str], _Job] = {}

    @staticmethod
    def _key(tenant_id: str, request_id: str) -> tuple[str, str]:
        return tenant_id, request_id

    def start(self, request: SimulationRequestV1, *,
              on_success: Callable[[SimulationRequestV1, SimulationReportV1], None] | None = None,
              retry_failed: bool = False, binding_id: str | None = None) -> SimulationRunStateV1:
        key = self._key(request.tenant_id, request.request_id)
        digest = semantic_digest(request)
        with self._lock:
            existing = self._jobs.get(key)
            if existing is not None:
                if existing.request_digest != digest or existing.binding_id != binding_id:
                    raise ValueError("request_id is already bound to different content")
                if not retry_failed or existing.state not in ("FAILED", "CANCELLED"):
                    return self._snapshot(existing)
            job = _Job(request=request, request_digest=digest, on_success=on_success, binding_id=binding_id)
            self._jobs[key] = job
            self._executor.submit(self._execute, key)
            return self._snapshot(job)

    def _execute(self, key: tuple[str, str]) -> None:
        with self._lock:
            job = self._jobs[key]
            job.state = "RUNNING"

        def on_progress(value: SimulationProgressV1) -> None:
            with self._lock:
                current = self._jobs[key]
                if current is not job:
                    return
                if current.state == "CANCELLED":
                    return
                if value.request_id != current.request.request_id:
                    raise ValueError("scheduler emitted stale progress")
                current.progress = value

        try:
            result = self._runner(
                job.request,
                should_cancel=job.cancel.is_set,
                progress=on_progress,
            )
        except Exception:
            result = SimulationErrorV1(
                request_id=job.request.request_id,
                scenario_revision_id=job.request.scenario_spec.revision_id,
                code="INVALID_SCENARIO",
                message="simulation execution failed",
            )
        if isinstance(result, SimulationReportV1) and job.on_success is not None and not job.cancel.is_set():
            try:
                job.on_success(job.request, result)
            except Exception:
                result = SimulationErrorV1(
                    request_id=job.request.request_id,
                    scenario_revision_id=job.request.scenario_spec.revision_id,
                    code="INVALID_SCENARIO",
                    message="simulation evidence persistence failed",
                )
        with self._lock:
            current = self._jobs[key]
            if current is not job:
                return
            if current.state == "CANCELLED":
                return
            if isinstance(result, SimulationReportV1):
                current.report = result
                current.state = "SUCCEEDED"
            else:
                current.error = result
                current.state = "CANCELLED" if result.code == "CANCELLED" else "FAILED"

    def get(self, tenant_id: str, request_id: str, binding_id: str | None = None) -> SimulationRunStateV1 | None:
        with self._lock:
            job = self._jobs.get(self._key(tenant_id, request_id))
            return None if job is None or job.binding_id != binding_id else self._snapshot(job)

    def cancel(self, tenant_id: str, request_id: str, binding_id: str | None = None) -> SimulationRunStateV1 | None:
        with self._lock:
            job = self._jobs.get(self._key(tenant_id, request_id))
            if job is None or job.binding_id != binding_id:
                return None
            if job.state in ("PENDING", "RUNNING"):
                job.cancel.set()
                job.state = "CANCELLED"
                job.error = SimulationErrorV1(
                    request_id=job.request.request_id,
                    scenario_revision_id=job.request.scenario_spec.revision_id,
                    code="CANCELLED",
                    message="simulation cancellation requested by the authenticated client",
                )
            return self._snapshot(job)

    @staticmethod
    def _snapshot(job: _Job) -> SimulationRunStateV1:
        return SimulationRunStateV1(
            request_id=job.request.request_id,
            tenant_id=job.request.tenant_id,
            project_id=job.request.project_id,
            scenario_revision_id=job.request.scenario_spec.revision_id,
            request_digest=job.request_digest,
            state=job.state,
            progress=job.progress,
            report=job.report,
            error=job.error,
        )


ProjectAuthorizer = Callable[[Session, uuid.UUID, uuid.UUID], bool]


def _owns_project(db: Session, project_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
    return db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.owner_id == owner_id,
            Project.status == "ACTIVE",
        )
    ) is not None


def create_simulation_router(
    registry: SimulationJobRegistry | None = None,
    *,
    project_authorizer: ProjectAuthorizer = _owns_project,
) -> APIRouter:
    jobs = registry or SimulationJobRegistry()
    saved_jobs = SimulationJobRegistry()
    router = APIRouter(prefix="/api/v2/simulations", tags=["simulation-v1"])

    def stored_state(evidence) -> SimulationRunStateV1:
        total = evidence.report.workload.jobs_per_day * 2
        return SimulationRunStateV1(
            request_id=evidence.request.request_id,
            tenant_id=evidence.request.tenant_id,
            project_id=evidence.request.project_id,
            scenario_revision_id=evidence.request.scenario_spec.revision_id,
            request_digest=evidence.request_digest,
            state="SUCCEEDED",
            progress=SimulationProgressV1(request_id=evidence.request.request_id, processed_events=total, total_events=total),
            report=evidence.report,
            error=None,
        )

    def saved_run(db: Session, context: AuthContext, project_id: uuid.UUID,
                  run_id: uuid.UUID) -> None:
        if owned_run(db, context.user.id, project_id, run_id) is None:
            raise HTTPException(status_code=404, detail="saved analysis run not found")

    def stored(db: Session, context: AuthContext, project_id: uuid.UUID,
               run_id: uuid.UUID, request_id: str):
        try:
            return load_artifact(db, context.user.id, project_id, run_id, request_id)
        except SimulationArtifactIntegrityError as exc:
            raise HTTPException(status_code=409, detail="stored simulation evidence integrity check failed") from exc

    def authorize(
        request: SimulationRequestV1,
        context: AuthContext,
        db: Session,
    ) -> None:
        tenant_id = str(context.user.id)
        if request.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="simulation tenant mismatch")
        try:
            project_id = uuid.UUID(request.project_id)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="project_id must identify a persisted project"
            ) from None
        if not project_authorizer(db, project_id, context.user.id):
            raise HTTPException(status_code=404, detail="project not found")

    @router.post("", response_model=SimulationRunStateV1, status_code=status.HTTP_202_ACCEPTED)
    def start_simulation(
        payload: SimulationRequestV1,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ) -> SimulationRunStateV1:
        authorize(payload, context, db)
        try:
            return jobs.start(payload)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @router.get("/{request_id}", response_model=SimulationRunStateV1)
    def simulation_progress(
        request_id: str,
        context: AuthContext = Depends(require_auth_context),
    ) -> SimulationRunStateV1:
        result = jobs.get(str(context.user.id), request_id)
        if result is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        return result

    @router.post("/{request_id}/cancel", response_model=SimulationRunStateV1)
    def cancel_simulation(
        request_id: str,
        context: AuthContext = Depends(require_csrf),
    ) -> SimulationRunStateV1:
        result = jobs.cancel(str(context.user.id), request_id)
        if result is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        return result

    @router.post("/projects/{project_id}/analysis-runs/{run_id}",
                 response_model=SimulationRunStateV1, status_code=status.HTTP_202_ACCEPTED)
    def start_saved_simulation(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        payload: SimulationRequestV1,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ) -> SimulationRunStateV1:
        authorize(payload, context, db)
        if payload.project_id != str(project_id):
            raise HTTPException(status_code=422, detail="simulation project path mismatch")
        run = owned_run(db, context.user.id, project_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="saved analysis run not found")
        try:
            verify_run_binding(run, payload)
        except SimulationArtifactIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        evidence = stored(db, context, project_id, run_id, payload.request_id)
        if evidence is not None:
            if evidence.request_digest != semantic_digest(payload):
                raise HTTPException(status_code=409, detail="immutable simulation request_id collision")
            return stored_state(evidence)

        def persist(request: SimulationRequestV1, report: SimulationReportV1) -> None:
            with get_database().session() as session:
                save_artifact(session, context.user.id, project_id, run_id, request, report)

        try:
            return saved_jobs.start(payload, on_success=persist, retry_failed=True, binding_id=str(run_id))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/{request_id}",
                response_model=SimulationRunStateV1)
    def saved_simulation_progress(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        request_id: str,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ) -> SimulationRunStateV1:
        saved_run(db, context, project_id, run_id)
        evidence = stored(db, context, project_id, run_id, request_id)
        if evidence is not None:
            return stored_state(evidence)
        state = saved_jobs.get(str(context.user.id), request_id, str(run_id))
        if state is None or state.project_id != str(project_id):
            raise HTTPException(status_code=404, detail="simulation not found")
        return state

    @router.post("/projects/{project_id}/analysis-runs/{run_id}/{request_id}/cancel",
                 response_model=SimulationRunStateV1)
    def cancel_saved_simulation(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        request_id: str,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(database_session),
    ) -> SimulationRunStateV1:
        saved_run(db, context, project_id, run_id)
        evidence = stored(db, context, project_id, run_id, request_id)
        if evidence is not None:
            return stored_state(evidence)
        state = saved_jobs.cancel(str(context.user.id), request_id, str(run_id))
        if state is None or state.project_id != str(project_id):
            raise HTTPException(status_code=404, detail="simulation not found")
        return state

    @router.get("/projects/{project_id}/analysis-runs/{run_id}/{request_id}/evidence.json")
    def download_simulation_evidence(
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        request_id: str,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session),
    ):
        saved_run(db, context, project_id, run_id)
        evidence = stored(db, context, project_id, run_id, request_id)
        if evidence is None:
            raise HTTPException(status_code=404, detail="simulation evidence not found")
        body = {
            "schema_version": "simulation-artifact-v1",
            "artifact_id": str(evidence.artifact_id),
            "analysis_run_id": str(evidence.analysis_run_id),
            "project_id": str(evidence.project_id),
            "scenario_spec_digest": evidence.scenario_spec_digest,
            "request_digest": evidence.request_digest,
            "report_digest": evidence.report_digest,
            "request": evidence.request.model_dump(mode="json"),
            "report": evidence.report.model_dump(mode="json"),
        }
        data = (json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        return Response(content=data, media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="robomera-simulation-{request_id}.json"',
            "X-Simulation-Report-Digest": evidence.report_digest,
            "Cache-Control": "private, no-store",
        })

    return router


__all__ = [
    "SimulationJobRegistry",
    "SimulationRunStateV1",
    "create_simulation_router",
]
