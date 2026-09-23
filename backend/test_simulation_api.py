from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth_context, require_csrf
from calculation.scheduling import SimulationErrorV1, SimulationReportV1, SimulationRequestV1
from calculation_contracts import semantic_digest
from database import database_session
from simulation_api import SimulationJobRegistry, create_simulation_router


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "fixtures" / "simulation-request-v1.capacity-only.golden.json"


def _request(*, tenant_id: str | None = None, project_id: str | None = None) -> SimulationRequestV1:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if tenant_id is not None:
        raw["tenant_id"] = tenant_id
        raw["scenario_spec"]["analysis"]["tenant_id"] = tenant_id
    if project_id is not None:
        raw["project_id"] = project_id
        raw["scenario_spec"]["analysis"]["project_id"] = project_id
    spec = raw["scenario_spec"]
    spec["revision_id"] = "calc_" + semantic_digest(
        {key: value for key, value in spec.items() if key != "revision_id"}
    ).removeprefix("sha256:")[:16]
    return SimulationRequestV1.model_validate(raw)


def _wait(registry: SimulationJobRegistry, request: SimulationRequestV1):
    for _ in range(200):
        state = registry.get(request.tenant_id, request.request_id)
        if state is not None and state.state not in ("PENDING", "RUNNING"):
            return state
        time.sleep(0.005)
    raise AssertionError("simulation did not finish")


def test_registry_runs_c23_and_preserves_revision_digest_and_capacity_only_report():
    registry = SimulationJobRegistry()
    request = _request()
    started = registry.start(request)
    assert started.scenario_revision_id == request.scenario_spec.revision_id
    assert started.request_digest == semantic_digest(request)
    terminal = _wait(registry, request)
    assert terminal.state == "SUCCEEDED"
    assert isinstance(terminal.report, SimulationReportV1)
    assert terminal.report.replay.canonical_request_digest == semantic_digest(request)
    assert request.scenario_spec.finance is None
    assert terminal.report.sla.verdict == "NOT_EVALUATED"
    assert terminal.report.engineering_claim == "PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION"


def test_registry_cancel_is_typed_and_tenant_lookup_is_isolated():
    entered = threading.Event()

    def cancellable(request, *, should_cancel, progress):
        entered.set()
        while not should_cancel():
            time.sleep(0.002)
        return SimulationErrorV1(
            request_id=request.request_id,
            scenario_revision_id=request.scenario_spec.revision_id,
            code="CANCELLED",
            message="cancelled by C24 test",
        )

    registry = SimulationJobRegistry(runner=cancellable)
    request = _request()
    registry.start(request)
    assert entered.wait(timeout=1)
    assert registry.get("tenant.other", request.request_id) is None
    registry.cancel(request.tenant_id, request.request_id)
    terminal = _wait(registry, request)
    assert terminal.state == "CANCELLED"
    assert terminal.error.code == "CANCELLED"


def test_api_requires_bound_tenant_project_and_uses_csrf_for_mutations():
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    context = SimpleNamespace(user=SimpleNamespace(id=user_id))
    registry = SimulationJobRegistry()
    app = FastAPI()
    router = create_simulation_router(
        registry,
        project_authorizer=lambda _db, candidate, owner: (
            candidate == project_id and owner == user_id
        ),
    )
    app.include_router(router)
    app.dependency_overrides[require_auth_context] = lambda: context
    app.dependency_overrides[database_session] = lambda: object()
    client = TestClient(app)

    request = _request(tenant_id=str(user_id), project_id=str(project_id))
    assert client.post(
        "/api/v2/simulations", json=request.model_dump(mode="json")
    ).status_code == 403
    app.dependency_overrides[require_csrf] = lambda: context
    response = client.post("/api/v2/simulations", json=request.model_dump(mode="json"))
    assert response.status_code == 202
    assert response.json()["scenario_revision_id"] == request.scenario_spec.revision_id

    for _ in range(100):
        progress = client.get(f"/api/v2/simulations/{request.request_id}")
        assert progress.status_code == 200
        if progress.json()["state"] == "SUCCEEDED":
            break
        time.sleep(0.005)
    assert progress.json()["report"]["scenario_revision_id"] == request.scenario_spec.revision_id

    other = _request(tenant_id=str(uuid.uuid4()), project_id=str(project_id))
    denied = client.post("/api/v2/simulations", json=other.model_dump(mode="json"))
    assert denied.status_code == 403

    start_route = next(route for route in router.routes if route.path == "/api/v2/simulations")
    cancel_route = next(route for route in router.routes if route.path.endswith("/{request_id}/cancel"))
    assert any(item.call is require_csrf for item in start_route.dependant.dependencies)
    assert any(item.call is require_csrf for item in cancel_route.dependant.dependencies)


def test_api_rejects_unknown_version_extra_field_and_request_collision():
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    context = SimpleNamespace(user=SimpleNamespace(id=user_id))
    registry = SimulationJobRegistry()
    app = FastAPI()
    app.include_router(create_simulation_router(registry, project_authorizer=lambda *_: True))
    app.dependency_overrides[require_auth_context] = lambda: context
    app.dependency_overrides[require_csrf] = lambda: context
    app.dependency_overrides[database_session] = lambda: object()
    client = TestClient(app)
    request = _request(tenant_id=str(user_id), project_id=str(project_id)).model_dump(mode="json")

    invalid_version = {**request, "schema_version": "simulation-request-v2"}
    assert client.post("/api/v2/simulations", json=invalid_version).status_code == 422
    assert client.post(
        "/api/v2/simulations", json={**request, "client_capacity": 1}
    ).status_code == 422

    assert client.post("/api/v2/simulations", json=request).status_code == 202
    changed = json.loads(json.dumps(request))
    changed["mode"] = "PEAK_STRESS"
    changed["peak_factor"] = "1.5"
    assert client.post("/api/v2/simulations", json=changed).status_code == 409


def test_unexpected_runner_failure_is_a_typed_redacted_terminal_error():
    def failing_runner(*_args, **_kwargs):
        raise RuntimeError("secret backend detail")

    registry = SimulationJobRegistry(runner=failing_runner)
    request = _request()
    registry.start(request)
    terminal = _wait(registry, request)
    assert terminal.state == "FAILED"
    assert terminal.error.code == "INVALID_SCENARIO"
    assert terminal.error.message == "simulation execution failed"
    assert "secret" not in terminal.error.message


def test_run_state_schema_is_generated_exactly():
    from scripts.build_simulation_2d_contract import TARGET, expected_bytes

    assert TARGET.read_bytes() == expected_bytes()
