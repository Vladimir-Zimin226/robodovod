"""F1 regression: physical inputs survive C11 -> saved scenario -> C23."""
from copy import deepcopy
from decimal import Decimal

import pytest
from calculation.scheduling import (
    SimulationReportV3,
    SimulationRequestV2,
    run_simulation,
)
from calculation.service import analyze_capacity
from calculation_contracts import CapacityAnalysisRequest, semantic_digest
from economics_orchestrator import EconomicsExecutionContextV1, execute_economics_v2
from economics_partial import execute_partial_economics_v2
from test_economics_orchestrator import _capacity_request, _inputs, _snapshot


def execution(demand, distance, fleet=None, full=False):
    raw = _capacity_request().model_dump(mode="json")
    raw["input_revision"] = raw["process"]["input_revision"] = f"revision.f1.{demand}.{distance}.{fleet if fleet is not None else 'auto'}"
    raw["provenance"][0]["confirmation_revision"] = raw["input_revision"]
    for field, value in [("demand", demand), ("route_distance", distance)]:
        raw["process"][field]["raw_value"] = raw["process"][field]["normalized_value"] = str(value)
    if fleet is not None:
        raw["selected_fleet"] = {**raw["process"]["schedule"]["shifts_per_day"],
                                 "name": "fleet_selected", "raw_value": str(fleet),
                                 "normalized_value": str(fleet), "unit": "robot", "raw_unit": "robot"}
    request = CapacityAnalysisRequest.model_validate(raw)
    capacity = analyze_capacity(request, _snapshot(), f"run.capacity.f1.{demand}.{distance}.{fleet if fleet is not None else 'auto'}")
    context = EconomicsExecutionContextV1(
        run_id=f"run.economics.f1.{demand}.{distance}.{fleet if fleet is not None else 'auto'}", project_id=request.project_id,
        tenant_id="tenant.f1", capacity_request=request, capacity_response=capacity.response,
        constraint_report=capacity.constraints.model_dump(mode="json"),
        executability=capacity.executability.model_dump(mode="json"),
    )
    inputs = {**_inputs(), "input_revision": request.input_revision,
              "start_seconds_from_midnight": 32400, "timezone": "Asia/Sakhalin"}
    if full:
        result = execute_economics_v2(inputs, _snapshot(), context)
    else:
        result = execute_partial_economics_v2({"schema_version": "economics-explicit-inputs-v4",
            "input_revision": request.input_revision, "start_seconds_from_midnight": "32400",
            "timezone": "Asia/Sakhalin"}, _snapshot(), context)
    spec = result.scenario_spec_snapshot
    simulation = SimulationRequestV2.model_validate({
        "schema_version": "simulation-request-v2", "request_id": f"simulation.{context.run_id}",
        "project_id": context.project_id, "tenant_id": context.tenant_id,
        "scenario_spec": spec, "mode": "DAILY", "peak_factor": None, "sla": None, "resources": [],
        "limits": {"max_jobs_per_day": 10000, "max_fleet": 100, "max_runtime_seconds": 60, "progress_event_batch": 1000},
        "model_start": {"weekday": "MONDAY", "seconds_from_midnight": 32400, "timezone": "Asia/Sakhalin"},
        "process_chain": None,
    })
    return request, capacity.response, result, simulation, run_simulation(simulation)


@pytest.mark.parametrize("demand,full", [(220, False), (220, True), (2000, True)])
def test_physical_inputs_and_digests_match_c11_spec_c23(demand, full):
    request, capacity, result, simulation, report = execution(demand, 120, full=full)
    assert isinstance(report, SimulationReportV3)
    spec = simulation.scenario_spec
    assert spec.analysis.capacity_run_id == capacity.run_id
    assert spec.analysis.capacity_request_digest == semantic_digest(request)
    assert spec.analysis.capacity_result_digest == semantic_digest(capacity.capacity)
    assert spec.profile.process_id == request.process.process_id
    assert spec.tasks[0].demand.value == str(demand)
    assert spec.routes[0].one_way_distance.value == "120"
    assert spec.tasks[0].batch.units_per_cycle.value == "1"
    assert spec.fleet[0].model_id == request.model_id and spec.fleet[0].position_id == request.position_id
    assert spec.fleet[0].selected_fleet == capacity.capacity.value.selected_fleet
    assert spec.fleet[0].effective_capacity == capacity.capacity.value.effective_capacity
    assert spec.fleet[0].nominal_capacity == capacity.capacity.value.nominal_capacity
    assert spec.tasks[0].exchange.total_time.value == request.process.exchange.total_time.normalized_value
    assert spec.analysis.capacity_trace_digest == capacity.trace.replay.trace_content_digest
    assert report.workload.fleet_units == spec.fleet[0].selected_fleet
    assert Decimal(report.capacity.required_per_hour) * Decimal(report.time_basis.operating_hours_per_day) == demand
    assert report.model_start == simulation.model_start
    assert report.replay.canonical_request_digest == semantic_digest(simulation)
    assert report.replay.scenario_spec_digest == semantic_digest(spec)
    assert result.scenario_spec_snapshot == spec.model_dump(mode="json")


def test_changed_demand_distance_and_fleet_leave_old_sources_and_report_unchanged():
    old = execution(220, 120)
    saved = deepcopy(old[2].scenario_spec_snapshot)
    digests = [semantic_digest(old[0]), semantic_digest(old[3]), semantic_digest(old[4])]
    changed = [execution(260, 120), execution(220, 180), execution(2000, 120, fleet=1)]
    assert all(item[3].scenario_spec.revision_id != old[3].scenario_spec.revision_id for item in changed)
    overloaded = changed[-1][4]
    assert isinstance(overloaded, SimulationReportV3)
    assert overloaded.capacity.verdict == "OVERLOADED"
    assert overloaded.queue.maximum_jobs > old[4].queue.maximum_jobs
    assert overloaded.queue.completed_by_measurement_end < overloaded.queue.measurement_jobs
    assert old[2].scenario_spec_snapshot == saved
    assert [semantic_digest(old[0]), semantic_digest(old[3]), semantic_digest(old[4])] == digests
