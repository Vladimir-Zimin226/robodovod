import json
import time
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth_context, require_csrf
from calculation.scheduling import SimulationReportV3, SimulationRequestV1, SimulationRequestV2, run_simulation
from calculation_contracts import semantic_digest
from database import database_session
from simulation_api import SimulationJobRegistry, SimulationRunStateV1, create_simulation_router
from simulation_artifacts import load_artifact
from warehouse_chain_api import default_chain
from scripts.build_simulation_stage6_contracts import CONTRACTS, expected


FIXTURE = Path(__file__).resolve().parents[1] / "contracts/fixtures/simulation-request-v1.capacity-only.golden.json"
WAREHOUSE = Path(__file__).resolve().parents[1] / "frontend/tests/fixtures/warehouse-2d-stage3.json"


def request(stages=None):
    raw = (json.loads(FIXTURE.read_text(encoding="utf-8")) if stages is None
           else json.loads(WAREHOUSE.read_text(encoding="utf-8"))["request"])
    raw["schema_version"] = "simulation-request-v2"
    raw["request_id"] = "simulation.stage6"
    raw["model_start"] = {"weekday": "MONDAY", "seconds_from_midnight": 0, "timezone": "Europe/Moscow"}
    raw["process_chain"] = None if stages is None else {
        "schema_version": "warehouse-process-chain-v2", "warehouse_chain_version": 1,
        "warehouse_chain_digest": "sha256:" + "a" * 64, "stages": stages,
    }
    return SimulationRequestV2.model_validate(raw)


def stage(code, flow, rate):
    return {"stage": code, "flow_code": flow, "units_per_pallet": "1",
            "service_rate_per_hour": rate, "capacity": 2, "resource_kind": "HUMAN",
            "resource_id": f"staff.{code.lower()}",
            "source_ref": f"input.{code.lower()}", "conversion_refs": ["conversion.picking_lines.shipping"]}


def test_v3_defaults_keep_pallet_metrics_and_mark_other_stages_external():
    legacy = run_simulation(SimulationRequestV1.model_validate_json(FIXTURE.read_text(encoding="utf-8")))
    result = run_simulation(request())
    assert isinstance(result, SimulationReportV3)
    assert result.schema_version == "simulation-report-v3"
    assert result.model_start.weekday == "MONDAY"
    assert result.capacity == legacy.capacity
    assert result.queue == legacy.queue
    assert all(item.status == "EXTERNAL_BOUNDARY" and item.maximum_queue_jobs is None for item in result.stages)
    assert result.replay.canonical_request_digest == semantic_digest(request())


def test_slower_picking_or_packaging_changes_only_corresponding_station_queue():
    fast = [stage("PICKING", "picking_lines", "1000"),
            stage("BUFFER", "tote_handoff", "1000"),
            stage("FEED_TO_PACK", "tote_handoff", "1000"),
            stage("PACKAGING", "packaging", "1000")]
    normal = run_simulation(request(fast))
    slow_pick = deepcopy(fast)
    slow_pick[0]["service_rate_per_hour"] = "2"
    picked = run_simulation(request(slow_pick))
    slow_pack = deepcopy(fast)
    slow_pack[3]["service_rate_per_hour"] = "2"
    packed = run_simulation(request(slow_pack))
    assert isinstance(normal, SimulationReportV3)
    assert isinstance(picked, SimulationReportV3)
    assert isinstance(packed, SimulationReportV3)
    assert picked.stages[0].maximum_queue_jobs > normal.stages[0].maximum_queue_jobs
    assert packed.stages[3].maximum_queue_jobs > normal.stages[3].maximum_queue_jobs
    assert picked.stages[3].completed_by_measurement_end < normal.stages[3].completed_by_measurement_end
    assert packed.stages[3].completed_by_measurement_end < normal.stages[3].completed_by_measurement_end
    assert picked.queue == packed.queue == normal.queue
    assert picked.capacity == packed.capacity == normal.capacity
    assert "extended-stage-economics-not-evaluated" in packed.limitations


def test_monday_evening_shift_crosses_midnight_without_changing_old_calendar():
    raw = request().model_dump(mode="json")
    spec = raw["scenario_spec"]
    primary = deepcopy(spec["operating_windows"][0])
    primary["window_id"] = "window.primary"
    primary["start_time"]["value"] = "72000"
    primary["duration"]["value"] = "4"
    next_day = deepcopy(primary)
    next_day["window_id"] = "window.next-day"
    next_day["start_time"]["value"] = "0"
    next_day["duration"]["value"] = "12"
    spec["operating_windows"] = [primary, next_day]
    spec["tasks"][0]["operating_window_refs"] = ["window.primary", "window.next-day"]
    spec["revision_id"] = "calc_" + semantic_digest({key: value for key, value in spec.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
    raw["model_start"]["seconds_from_midnight"] = 72000
    result = run_simulation(SimulationRequestV2.model_validate(raw))
    assert isinstance(result, SimulationReportV3)
    assert result.time_basis.operating_hours_per_day == "16"
    assert result.model_start.seconds_from_midnight == 72000


def test_saved_eight_o_clock_and_other_timezone_are_preserved():
    raw = request().model_dump(mode="json")
    spec = raw["scenario_spec"]
    spec["operating_windows"][0]["start_time"]["value"] = "28800"
    spec["operating_windows"][0]["duration"]["value"] = "16"
    spec["operating_windows"][0]["timezone"] = "Asia/Sakhalin"
    spec["revision_id"] = "calc_" + semantic_digest({key: value for key, value in spec.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
    raw["model_start"] = {"weekday": "MONDAY", "seconds_from_midnight": 28800, "timezone": "Asia/Sakhalin"}
    report = run_simulation(SimulationRequestV2.model_validate(raw))
    assert isinstance(report, SimulationReportV3)
    assert report.model_start.timezone == report.time_basis.timezone == "Asia/Sakhalin"
    assert report.model_start.seconds_from_midnight == 28800


def test_v3_job_state_serializes_and_reopens_the_same_report_contract():
    registry = SimulationJobRegistry()
    value = request()
    registry.start(value)
    for _ in range(200):
        state = registry.get(value.tenant_id, value.request_id)
        if state.state == "SUCCEEDED":
            break
        time.sleep(0.005)
    assert state.state == "SUCCEEDED"
    restored = SimulationRunStateV1.model_validate_json(state.model_dump_json())
    assert restored.report.schema_version == "simulation-report-v3"
    assert restored.report.report_id == state.report.report_id


def test_220_pallets_120_metres_and_typical_warehouse_remain_transport_only():
    original = json.loads(WAREHOUSE.read_text(encoding="utf-8"))["request"]
    assert original["scenario_spec"]["routes"][0]["one_way_distance"]["value"] == "120"
    for demand in ("1000", "220"):
        raw = deepcopy(original)
        raw["schema_version"] = "simulation-request-v2"
        raw["request_id"] = f"simulation.warehouse.{demand}"
        raw["scenario_spec"]["tasks"][0]["demand"]["value"] = demand
        spec = raw["scenario_spec"]
        spec["revision_id"] = "calc_" + semantic_digest({key: value for key, value in spec.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
        raw["model_start"] = {"weekday": "MONDAY", "seconds_from_midnight": 0, "timezone": "Europe/Moscow"}
        raw["process_chain"] = None
        report = run_simulation(SimulationRequestV2.model_validate(raw))
        assert isinstance(report, SimulationReportV3)
        assert report.workload.daily_units == demand
        assert all(item.status == "EXTERNAL_BOUNDARY" for item in report.stages)
        assert "extended-stage-economics-not-evaluated" in report.limitations


def test_v2_http_run_returns_full_v3_report_without_truncating_stage_metrics():
    user_id, project_id = uuid.uuid4(), uuid.uuid4()
    raw = request().model_dump(mode="json")
    raw["tenant_id"] = raw["scenario_spec"]["analysis"]["tenant_id"] = str(user_id)
    raw["project_id"] = raw["scenario_spec"]["analysis"]["project_id"] = str(project_id)
    spec = raw["scenario_spec"]
    spec["revision_id"] = "calc_" + semantic_digest({key: value for key, value in spec.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
    app = FastAPI()
    app.include_router(create_simulation_router(project_authorizer=lambda *_: True))
    context = SimpleNamespace(user=SimpleNamespace(id=user_id))
    app.dependency_overrides[require_auth_context] = lambda: context
    app.dependency_overrides[require_csrf] = lambda: context
    app.dependency_overrides[database_session] = lambda: object()
    client = TestClient(app)
    response = client.post("/api/v2/simulations", json=raw)
    assert response.status_code == 202
    for _ in range(200):
        state = client.get(f"/api/v2/simulations/{raw['request_id']}").json()
        if state["state"] == "SUCCEEDED":
            break
        time.sleep(0.005)
    assert state["report"]["schema_version"] == "simulation-report-v3"
    assert len(state["report"]["stages"]) == 4
    assert state["report"]["model_start"]["weekday"] == "MONDAY"


def test_extended_http_request_rejects_unlinked_or_mismatched_warehouse_volume():
    user_id, project_id = uuid.uuid4(), uuid.uuid4()
    raw = json.loads(WAREHOUSE.read_text(encoding="utf-8"))["request"]
    raw["schema_version"] = "simulation-request-v2"
    raw["request_id"] = "simulation.stage6.chain.validation"
    raw["tenant_id"] = raw["scenario_spec"]["analysis"]["tenant_id"] = str(user_id)
    raw["project_id"] = raw["scenario_spec"]["analysis"]["project_id"] = str(project_id)
    spec = raw["scenario_spec"]
    spec["revision_id"] = "calc_" + semantic_digest({key: value for key, value in spec.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
    raw["model_start"] = {"weekday": "MONDAY", "seconds_from_midnight": 0, "timezone": "Europe/Moscow"}
    chain = default_chain(project_id)
    chain["version"] = 1
    picker = next(item for item in chain["flows"] if item["code"] == "picking_lines")
    picker.update(value="10000", source="USER", confirmed=True)
    staff = next(item for item in chain["resources"] if item["resource_id"] == "staff.picker")
    staff.update(amount="2", source="USER", confirmed=True)
    chain["conversions"] = [{"from_code": "picking_lines", "to_code": "shipping", "factor": "0.1", "source": "USER", "source_ref": "observed.flow", "confirmed": True}]
    raw["process_chain"] = {"schema_version": "warehouse-process-chain-v2", "warehouse_chain_version": 1,
        "warehouse_chain_digest": semantic_digest(chain), "stages": [{
            "stage": "PICKING", "flow_code": "picking_lines", "units_per_pallet": "10",
            "service_rate_per_hour": "100", "capacity": 2, "resource_kind": "HUMAN",
            "resource_id": "staff.picker", "source_ref": "input.simulation.rate.picking",
            "conversion_refs": ["conversion.picking_lines.shipping"],
        }]}
    app = FastAPI()
    app.include_router(create_simulation_router(project_authorizer=lambda *_: True))
    context = SimpleNamespace(user=SimpleNamespace(id=user_id))
    project = SimpleNamespace(profile={"warehouse_chain_v1": {"versions": [chain]}})
    app.dependency_overrides[require_auth_context] = lambda: context
    app.dependency_overrides[require_csrf] = lambda: context
    app.dependency_overrides[database_session] = lambda: SimpleNamespace(scalar=lambda *_: project)
    client = TestClient(app)
    assert client.post("/api/v2/simulations", json=raw).status_code == 202
    altered = deepcopy(raw)
    altered["request_id"] = "simulation.stage6.chain.tampered"
    altered["process_chain"]["stages"][0]["units_per_pallet"] = "20"
    assert client.post("/api/v2/simulations", json=altered).status_code == 422
    altered["process_chain"]["stages"][0]["units_per_pallet"] = "10"
    altered["process_chain"]["stages"][0]["resource_kind"] = "ROBOT"
    assert client.post("/api/v2/simulations", json=altered).status_code == 422


def test_new_contract_schemas_are_published_without_rewriting_legacy_fixtures():
    for name, model in CONTRACTS.items():
        target = Path(__file__).resolve().parents[1] / "contracts" / f"{name}.schema.json"
        assert target.read_bytes() == expected(name, model)


def test_new_artifact_reopens_exact_v3_request_and_report(monkeypatch):
    value = request()
    report = run_simulation(value)
    spec_sha = semantic_digest(value.scenario_spec).removeprefix("sha256:")
    run_id, project_id, owner_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    artifact = SimpleNamespace(id=uuid.uuid4(), artifact_version="simulation-artifact-v1",
        request_snapshot=value.model_dump(mode="json"), report_snapshot=report.model_dump(mode="json"),
        request_sha256=semantic_digest(value).removeprefix("sha256:"),
        report_sha256=semantic_digest(report).removeprefix("sha256:"), scenario_spec_sha256=spec_sha)
    monkeypatch.setattr("simulation_artifacts.owned_run", lambda *_: SimpleNamespace(scenario_spec_sha256=spec_sha))
    loaded = load_artifact(SimpleNamespace(scalar=lambda *_: artifact), owner_id, project_id, run_id, value.request_id)
    assert loaded.request == value
    assert loaded.report == report
    assert loaded.report.replay.report_content_digest == report.replay.report_content_digest
