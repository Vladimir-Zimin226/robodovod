"""C23 deterministic queue model and immutable SimulationReport v1.

The scheduler consumes ScenarioSpec v2 values.  It never recomputes capacity or
finance and never invents failure/charging distributions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_EVEN
from typing import Annotated, Callable, Literal

from pydantic import ConfigDict, Field, model_validator

from calculation_contracts import Digest, StableId, StrictContractModel, semantic_digest
from scenario_spec_v2 import ScenarioSpecV2


SIMULATION_REQUEST_VERSION = "simulation-request-v1"
SIMULATION_REPORT_VERSION = "simulation-report-v1"
SIMULATION_ENGINE_VERSION = "deterministic-queue-v1"
SIMULATION_POLICY_VERSION = "hackathon-calculation-policy-v1+k18-c23"
EVENT_ORDER_VERSION = "event-order-time-priority-process-resource-job-v1"
ARRIVAL_MODEL_VERSION = "uniform-arrivals-v1"
MICROS_PER_SECOND = 1_000_000
SECONDS_PER_HOUR = 3600
DAY_US = 24 * SECONDS_PER_HOUR * MICROS_PER_SECOND

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]


class FrozenContractModel(StrictContractModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    result = format(value.normalize(), "f")
    return "0" if result in ("-0", "") else result


def _micros(seconds: Decimal) -> int:
    return int((seconds * MICROS_PER_SECOND).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


class SimulationLimitsV1(StrictContractModel):
    max_jobs_per_day: Literal[10000]
    max_fleet: Literal[100]
    max_runtime_seconds: Literal[60]
    progress_event_batch: Literal[1000]


class SimulationSlaV1(StrictContractModel):
    minutes: DecimalString
    target_fraction: DecimalString
    provenance_ref: StableId

    @model_validator(mode="after")
    def validate_sla(self) -> "SimulationSlaV1":
        if _d(self.minutes) <= 0:
            raise ValueError("SLA minutes must be positive")
        if not Decimal(0) < _d(self.target_fraction) <= Decimal(1):
            raise ValueError("SLA target must be within (0, 1]")
        return self


class SimulationResourceV1(StrictContractModel):
    resource_id: StableId
    stage: Literal["LOAD", "OUTBOUND", "WORK", "UNLOAD", "RETURN"]
    capacity: Annotated[int, Field(ge=1, le=100)]
    source: Literal["USER", "FILE", "PROVIDED_GEOMETRY"]
    provenance_ref: StableId


class SimulationRequestV1(StrictContractModel):
    schema_version: Literal["simulation-request-v1"]
    request_id: StableId
    tenant_id: StableId
    project_id: StableId
    scenario_spec: ScenarioSpecV2
    mode: Literal["DAILY", "PEAK_STRESS"]
    peak_factor: DecimalString | None = None
    sla: SimulationSlaV1 | None = None
    resources: list[SimulationResourceV1]
    limits: SimulationLimitsV1

    @model_validator(mode="after")
    def bind_scenario(self) -> "SimulationRequestV1":
        if (self.tenant_id, self.project_id) != (
            self.scenario_spec.analysis.tenant_id,
            self.scenario_spec.analysis.project_id,
        ):
            raise ValueError("simulation tenant/project does not match ScenarioSpec")
        if self.mode == "PEAK_STRESS" and (self.peak_factor is None or _d(self.peak_factor) <= 0):
            raise ValueError("PEAK_STRESS requires a positive explicit peak_factor")
        if self.mode == "DAILY" and self.peak_factor is not None:
            raise ValueError("DAILY must not apply peak_factor")
        ids = [item.resource_id for item in self.resources]
        stages = [item.stage for item in self.resources]
        if len(ids) != len(set(ids)) or len(stages) != len(set(stages)):
            raise ValueError("resource ids and stage bindings must be unique")
        return self


class SimulationVersionsV1(FrozenContractModel):
    engine_version: Literal["deterministic-queue-v1"] = SIMULATION_ENGINE_VERSION
    request_version: Literal["simulation-request-v1"] = SIMULATION_REQUEST_VERSION
    report_version: Literal["simulation-report-v1"] = SIMULATION_REPORT_VERSION
    policy_version: Literal["hackathon-calculation-policy-v1+k18-c23"] = SIMULATION_POLICY_VERSION
    event_order_version: Literal["event-order-time-priority-process-resource-job-v1"] = EVENT_ORDER_VERSION
    arrival_model_version: Literal["uniform-arrivals-v1"] = ARRIVAL_MODEL_VERSION
    availability_model_version: Literal["aggregate-nonproductive-allowance-v1"] = "aggregate-nonproductive-allowance-v1"
    failure_model_version: Literal["not-provided"] = "not-provided"
    scenario_contract_version: Literal["scenario-spec-v2"] = "scenario-spec-v2"
    precision_policy_version: Literal["decimal-context-28-half-even-v1"] = "decimal-context-28-half-even-v1"


class SimulationTimeBasisV1(FrozenContractModel):
    unit: Literal["MICROSECOND"] = "MICROSECOND"
    seed: Literal[42] = 42
    timezone: Annotated[str, Field(min_length=1)]
    warmup_days: Literal[1] = 1
    measurement_days: Literal[1] = 1
    completion_grace_days: Literal[1] = 1
    operating_hours_per_day: DecimalString
    window_refs: list[StableId] = Field(min_length=1)


class SimulationWorkloadV1(FrozenContractModel):
    mode: Literal["DAILY", "PEAK_STRESS"]
    daily_units: DecimalString
    peak_factor: DecimalString | None
    simulated_units_per_day: DecimalString
    batch_units: DecimalString
    jobs_per_day: Annotated[int, Field(ge=0)]
    fleet_units: Annotated[int, Field(ge=0)]
    quantity_unit: Annotated[str, Field(min_length=1)]
    arrival_assumption: Literal["UNIFORM_ARRIVALS"] = "UNIFORM_ARRIVALS"


class SimulationCapacityComparisonV1(FrozenContractModel):
    required_per_hour: DecimalString
    expected_effective_per_hour: DecimalString
    observed_per_hour: DecimalString
    unit: Annotated[str, Field(min_length=1)]
    deviation_percent: DecimalString | None
    verdict: Literal["CONSISTENT", "DEVIATION", "OVERLOADED", "N_A", "INPUT_MISMATCH"]
    denominator: Literal["EXPECTED_EFFECTIVE_FLEET_CAPACITY"] = "EXPECTED_EFFECTIVE_FLEET_CAPACITY"
    warning_threshold_percent: Literal["10"] = "10"


class SimulationQueueMetricsV1(FrozenContractModel):
    maximum_jobs: Annotated[int, Field(ge=0)]
    mean_wait_seconds: DecimalString | None
    p95_wait_seconds: DecimalString | None
    mean_turnaround_seconds: DecimalString | None
    p95_turnaround_seconds: DecimalString | None
    measurement_jobs: Annotated[int, Field(ge=0)]
    completed_by_measurement_end: Annotated[int, Field(ge=0)]
    completed_with_grace: Annotated[int, Field(ge=0)]
    completed_units_by_measurement_end: DecimalString
    completed_units_with_grace: DecimalString
    completed_unit: Annotated[str, Field(min_length=1)]
    censored_jobs: Annotated[int, Field(ge=0)]


class SimulationUtilizationV1(FrozenContractModel):
    busy_fraction: DecimalString | None
    productive_fraction: DecimalString | None
    nonproductive_fraction: DecimalString | None
    busy_seconds: DecimalString
    productive_seconds: DecimalString
    nonproductive_allowance_seconds: DecimalString
    failure_downtime_seconds: None
    failure_downtime_status: Literal["NOT_EVALUATED_NO_INPUT"]
    resource_wait_seconds: DecimalString
    denominator: Literal["FLEET_OPERATING_TIME"] = "FLEET_OPERATING_TIME"


class SimulationSlaResultV1(FrozenContractModel):
    verdict: Literal["PASS", "FAIL", "CONDITIONAL", "NOT_EVALUATED"]
    sla_minutes: DecimalString | None
    target_fraction: DecimalString | None
    on_time_fraction: DecimalString | None
    on_time_jobs: Annotated[int, Field(ge=0)]
    denominator_jobs: Annotated[int, Field(ge=0)]
    reason_codes: list[StableId]


class SimulationResourceMetricsV1(FrozenContractModel):
    resource_id: StableId
    stage: Literal["LOAD", "OUTBOUND", "WORK", "UNLOAD", "RETURN"]
    capacity: Annotated[int, Field(ge=1)]
    wait_seconds: DecimalString
    utilization_fraction: DecimalString


class SimulationTraceNodeV1(FrozenContractModel):
    node_id: StableId
    operation: Literal[
        "DERIVE_SERVICE_TIME", "BUILD_CALENDAR", "GENERATE_ARRIVALS",
        "DISPATCH_FIFO", "APPLY_NONPRODUCTIVE_ALLOWANCE", "COMPARE_CAPACITY", "EVALUATE_SLA",
    ]
    input_refs: list[Annotated[str, Field(min_length=1)]]
    output_ref: Annotated[str, Field(min_length=1)]
    value: DecimalString | None
    unit: Annotated[str, Field(min_length=1)]


class SimulationReplayV1(FrozenContractModel):
    scenario_spec_digest: Digest
    canonical_request_digest: Digest
    report_content_digest: Digest


class SimulationReportV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)
    schema_version: Literal["simulation-report-v1"]
    report_id: StableId
    request_id: StableId
    tenant_id: StableId
    project_id: StableId
    scenario_revision_id: Annotated[str, Field(pattern=r"^calc_[0-9a-f]{16}$")]
    status: Literal["CONSISTENT", "DEVIATION", "OVERLOADED", "CONDITIONAL_MODEL", "NOT_EVALUATED"]
    engineering_claim: Literal["PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION"]
    time_basis: SimulationTimeBasisV1
    workload: SimulationWorkloadV1
    capacity: SimulationCapacityComparisonV1
    queue: SimulationQueueMetricsV1
    utilization: SimulationUtilizationV1
    sla: SimulationSlaResultV1
    resources: list[SimulationResourceMetricsV1]
    limitations: list[StableId]
    trace: list[SimulationTraceNodeV1]
    versions: SimulationVersionsV1
    replay: SimulationReplayV1

    @model_validator(mode="after")
    def validate_content_digest(self) -> "SimulationReportV1":
        content = self.model_dump(mode="json")
        actual = content["replay"]["report_content_digest"]
        content["replay"]["report_content_digest"] = "sha256:" + "0" * 64
        if actual != semantic_digest(content):
            raise ValueError("SimulationReport content digest mismatch")
        return self


class SimulationErrorV1(FrozenContractModel):
    schema_version: Literal["simulation-error-v1"] = "simulation-error-v1"
    request_id: StableId
    scenario_revision_id: Annotated[str, Field(pattern=r"^calc_[0-9a-f]{16}$")]
    code: Literal["CANCELLED", "TIMEOUT", "LIMIT_EXCEEDED", "INVALID_SCENARIO"]
    message: Annotated[str, Field(min_length=1)]


class SimulationProgressV1(FrozenContractModel):
    schema_version: Literal["simulation-progress-v1"] = "simulation-progress-v1"
    request_id: StableId
    processed_events: Annotated[int, Field(ge=0)]
    total_events: Annotated[int, Field(ge=0)]


class _Stop(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


@dataclass
class _Calendar:
    windows: list[tuple[int, int]]
    hours: Decimal

    def for_day(self, day: int) -> list[tuple[int, int]]:
        return [(day * DAY_US + start, day * DAY_US + end) for start, end in self.windows]

    def next_work_time(self, point: int) -> int:
        day = max(0, point // DAY_US)
        for candidate_day in range(day, day + 10000):
            for start, end in self.for_day(candidate_day):
                if point < start:
                    return start
                if start <= point < end:
                    return point
        raise ValueError("calendar has no future work window")

    def add_work(self, point: int, duration: int) -> tuple[int, list[tuple[int, int]]]:
        current = self.next_work_time(point)
        remaining = duration
        intervals: list[tuple[int, int]] = []
        while remaining > 0:
            day = current // DAY_US
            window = next((item for item in self.for_day(day) if item[0] <= current < item[1]), None)
            if window is None:
                current = self.next_work_time(current)
                continue
            used = min(remaining, window[1] - current)
            intervals.append((current, current + used))
            current += used
            remaining -= used
            if remaining:
                current = self.next_work_time(current)
        return current, intervals

    def work_offset(self, day: int, offset: int) -> int:
        remaining = offset
        for start, end in self.for_day(day):
            length = end - start
            if remaining < length:
                return start + remaining
            remaining -= length
        return self.for_day(day)[-1][1]

    def day_end(self, day: int) -> int:
        return self.for_day(day)[-1][1]


@dataclass
class _Job:
    seq: int
    day: int
    release: int
    units: Decimal
    start: int = 0
    completion: int = 0
    resource_wait: int = 0
    busy_intervals: list[tuple[int, int]] | None = None
    productive_us: int = 0


def _calendar(spec: ScenarioSpecV2) -> _Calendar:
    windows: list[tuple[int, int]] = []
    for item in sorted(spec.operating_windows, key=lambda value: (Decimal(value.start_time.value), value.window_id)):
        start = _micros(_d(item.start_time.value))
        end = start + _micros(_d(item.duration.value) * SECONDS_PER_HOUR)
        if start < 0 or end > DAY_US or (windows and start < windows[-1][1]):
            raise ValueError("operating windows must be ordered, non-overlapping and inside one day")
        windows.append((start, end))
    hours = sum((_d(item.duration.value) for item in spec.operating_windows), Decimal(0))
    if hours <= 0:
        raise ValueError("simulation requires positive operating hours")
    return _Calendar(windows, hours)


def _nearest_rank(values: list[int], percentile: Decimal) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = int((Decimal(len(ordered)) * percentile).to_integral_value(rounding=ROUND_CEILING))
    return ordered[max(0, rank - 1)]


def _overlap(intervals: list[tuple[int, int]], windows: list[tuple[int, int]]) -> int:
    return sum(max(0, min(end, window_end) - max(start, window_start))
               for start, end in intervals for window_start, window_end in windows)


def _capacity_verdict(expected: Decimal, observed: Decimal, *, overloaded: bool) -> tuple[Decimal | None, str]:
    if expected == 0:
        return (None, "OVERLOADED") if overloaded else ((None, "N_A") if observed == 0 else (None, "INPUT_MISMATCH"))
    deviation = abs(observed - expected) / expected * 100
    if overloaded:
        return deviation, "OVERLOADED"
    return deviation, "DEVIATION" if deviation > 10 else "CONSISTENT"


def _service_model(spec: ScenarioSpecV2, calendar: _Calendar) -> tuple[Decimal, Decimal, Decimal, list[tuple[str, Decimal]]]:
    if len(spec.tasks) != 1 or len(spec.fleet) != 1:
        raise ValueError("simulation-report-v1 requires one process-bound task and fleet")
    task, fleet = spec.tasks[0], spec.fleet[0]
    batch = _d(task.batch.units_per_cycle.value)
    selected = Decimal(fleet.selected_fleet)
    nominal, effective = _d(fleet.nominal_capacity.value), _d(fleet.effective_capacity.value)
    demand_unit = str(task.demand.unit)
    batch_unit = str(task.batch.units_per_cycle.unit)
    nominal_unit = str(fleet.nominal_capacity.unit)
    effective_unit = str(fleet.effective_capacity.unit)
    if batch <= 0:
        raise ValueError("simulation requires a positive explicit batch")
    if not demand_unit.endswith("/day") or nominal_unit != effective_unit or not nominal_unit.endswith(("/day", "/h")):
        raise ValueError("simulation demand and capacity require comparable daily/hourly units")
    if demand_unit.split("/", 1)[0] != batch_unit.split("/", 1)[0] or demand_unit.split("/", 1)[0] != nominal_unit.split("/", 1)[0]:
        raise ValueError("simulation demand, batch and capacity units are not comparable")
    if effective > nominal:
        raise ValueError("effective capacity cannot exceed nominal capacity")
    if selected <= 0 or nominal <= 0 or effective <= 0 or batch <= 0:
        return batch, Decimal(0), Decimal(0), []
    availability = effective / nominal
    nominal_per_robot_hour = nominal / selected
    if str(fleet.nominal_capacity.unit).endswith("/day"):
        nominal_per_robot_hour /= calendar.hours
    nominal_seconds = batch / nominal_per_robot_hour * SECONDS_PER_HOUR
    effective_seconds = nominal_seconds / availability
    exchange = task.exchange
    stages: list[tuple[str, Decimal]]
    if exchange.mode in ("TOTAL", "SPLIT"):
        if exchange.mode == "TOTAL":
            load = unload = _d(exchange.total_time.value) / 2
        else:
            load, unload = _d(exchange.load_time.value), _d(exchange.unload_time.value)
        travel = max(Decimal(0), nominal_seconds - load - unload) / 2
        stages = [("LOAD", load), ("OUTBOUND", travel), ("UNLOAD", unload), ("RETURN", travel)]
    else:
        stages = [("WORK", nominal_seconds)]
    return batch, nominal_seconds, effective_seconds, stages


def _run(request: SimulationRequestV1, *, should_cancel: Callable[[], bool],
         progress: Callable[[SimulationProgressV1], None], clock: Callable[[], float]) -> SimulationReportV1:
    spec = request.scenario_spec
    calendar = _calendar(spec)
    task, fleet = spec.tasks[0], spec.fleet[0]
    daily = _d(task.demand.value)
    factor = Decimal(1) if request.mode == "DAILY" else _d(request.peak_factor)
    simulated = daily * factor
    batch, nominal_seconds, effective_seconds, stages = _service_model(spec, calendar)
    jobs_per_day = int((simulated / batch).to_integral_value(rounding=ROUND_CEILING)) if simulated > 0 else 0
    if jobs_per_day > request.limits.max_jobs_per_day or fleet.selected_fleet > request.limits.max_fleet:
        raise _Stop("LIMIT_EXCEEDED", "simulation request exceeds the documented C23 profile")
    total_jobs = jobs_per_day * 2
    started_at = clock()
    robots = [0] * fleet.selected_fleet
    resource_slots = {item.stage: [0] * item.capacity for item in request.resources}
    resource_by_stage = {item.stage: item for item in request.resources}
    resource_waits = {item.resource_id: 0 for item in request.resources}
    resource_busy = {item.resource_id: 0 for item in request.resources}
    jobs: list[_Job] = []
    seq = 0
    day_work_us = int(calendar.hours * SECONDS_PER_HOUR * MICROS_PER_SECOND)
    remaining_per_day = simulated
    for day in range(2):
        remaining_per_day = simulated
        for index in range(jobs_per_day):
            release_offset = int((Decimal(index) * day_work_us / jobs_per_day).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
            units = min(batch, remaining_per_day)
            remaining_per_day -= units
            jobs.append(_Job(seq=seq, day=day, release=calendar.work_offset(day, release_offset), units=units))
            seq += 1
    availability = Decimal(0) if nominal_seconds == 0 else nominal_seconds / effective_seconds
    for index, job in enumerate(jobs):
        if index % request.limits.progress_event_batch == 0:
            if should_cancel():
                raise _Stop("CANCELLED", "simulation cancelled at a deterministic event batch")
            if clock() - started_at > request.limits.max_runtime_seconds:
                raise _Stop("TIMEOUT", "simulation exceeded the 60 second C23 limit")
            progress(SimulationProgressV1(request_id=request.request_id, processed_events=index, total_events=total_jobs))
        if not robots or effective_seconds <= 0:
            continue
        robot_id = min(range(len(robots)), key=lambda item: (robots[item], item))
        current = calendar.next_work_time(max(job.release, robots[robot_id]))
        job.start = current
        intervals: list[tuple[int, int]] = []
        productive_us = 0
        for stage, stage_seconds_base in stages:
            stage_seconds = stage_seconds_base * (job.units / batch)
            stage_us = _micros(stage_seconds)
            resource = resource_by_stage.get(stage)
            if resource is not None:
                slots = resource_slots[stage]
                slot = min(range(len(slots)), key=lambda item: (slots[item], item))
                stage_start = calendar.next_work_time(max(current, slots[slot]))
                wait = max(0, stage_start - current)
                job.resource_wait += wait
                resource_waits[resource.resource_id] += wait
                current = stage_start
            current, stage_intervals = calendar.add_work(current, stage_us)
            intervals.extend(stage_intervals)
            productive_us += stage_us
            if resource is not None:
                resource_slots[stage][slot] = current
                resource_busy[resource.resource_id] += stage_us
        allowance_seconds = max(Decimal(0), effective_seconds - nominal_seconds) * (job.units / batch)
        current, allowance_intervals = calendar.add_work(current, _micros(allowance_seconds))
        intervals.extend(allowance_intervals)
        job.productive_us = productive_us
        job.busy_intervals = intervals
        job.completion = current
        robots[robot_id] = current
    progress(SimulationProgressV1(request_id=request.request_id, processed_events=total_jobs, total_events=total_jobs))

    measurement = [item for item in jobs if item.day == 1]
    measurement_windows = calendar.for_day(1)
    measurement_end = calendar.day_end(1)
    grace_end = calendar.day_end(2)
    completed_measurement = [item for item in measurement if item.completion and item.completion <= measurement_end]
    completed_grace = [item for item in measurement if item.completion and item.completion <= grace_end]
    completed_units = sum((item.units for item in completed_measurement), Decimal(0))
    required_per_hour = simulated / calendar.hours if calendar.hours else Decimal(0)
    expected_per_hour = _d(fleet.effective_capacity.value)
    if str(fleet.effective_capacity.unit).endswith("/day"):
        expected_per_hour /= calendar.hours
    observed_per_hour = completed_units / calendar.hours if calendar.hours else Decimal(0)
    is_overloaded = len(completed_measurement) < len(measurement) and simulated > expected_per_hour * calendar.hours
    deviation, capacity_verdict = _capacity_verdict(
        expected_per_hour, observed_per_hour, overloaded=is_overloaded,
    )

    wait_values = [max(0, item.start - item.release) for item in measurement if item.start]
    turnaround_values = [item.completion - item.release for item in completed_grace]
    events = [(item.release, 1, 1) for item in measurement] + [(item.start, 2, -1) for item in measurement if item.start]
    depth = maximum_queue = 0
    for _, _, delta in sorted(events):
        depth += delta
        maximum_queue = max(maximum_queue, depth)
    measure_busy = sum(_overlap(item.busy_intervals or [], measurement_windows) for item in jobs)
    measure_productive = int((Decimal(measure_busy) * availability).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    fleet_work_us = fleet.selected_fleet * day_work_us

    sla_reasons: list[str] = []
    if request.sla is None:
        sla_verdict, on_time, target = "NOT_EVALUATED", None, None
        sla_reasons.append("sla-not-supplied")
    else:
        deadline_us = _micros(_d(request.sla.minutes) * 60)
        on_time_count = sum(1 for item in measurement if item.completion and item.completion <= item.release + deadline_us)
        on_time = Decimal(on_time_count) / len(measurement) if measurement else None
        target = _d(request.sla.target_fraction)
        if not request.resources or any(item.geometry_source != "PROVIDED" for item in spec.routes):
            sla_verdict = "CONDITIONAL"
            sla_reasons.append("resource-model-incomplete")
        else:
            sla_verdict = "PASS" if on_time is not None and on_time >= target else "FAIL"
    on_time_count = 0 if on_time is None else sum(
        1 for item in measurement if item.completion
        and item.completion <= item.release + _micros(_d(request.sla.minutes) * 60)
    )

    limitations = ["not-engineering-certification", "no-random-failure-model", "charging-in-aggregate-allowance"]
    if not request.resources:
        limitations.append("resource-bottlenecks-not-modelled")
    if any(item.geometry_source != "PROVIDED" for item in spec.routes):
        limitations.append("synthetic-route-geometry")
    overall = "OVERLOADED" if capacity_verdict == "OVERLOADED" else (
        "DEVIATION" if capacity_verdict in ("DEVIATION", "INPUT_MISMATCH") else (
            "CONDITIONAL_MODEL" if sla_verdict == "CONDITIONAL" or "resource-bottlenecks-not-modelled" in limitations
            else "NOT_EVALUATED" if not measurement else "CONSISTENT"
        )
    )
    scenario_digest = semantic_digest(spec)
    request_digest = semantic_digest(request)
    trace = [
        SimulationTraceNodeV1(node_id="simulation.service", operation="DERIVE_SERVICE_TIME", input_refs=["scenario.fleet.nominal_capacity", "scenario.fleet.effective_capacity", "scenario.task.batch"], output_ref="service.effective-seconds", value=_decimal(effective_seconds), unit="s"),
        SimulationTraceNodeV1(node_id="simulation.calendar", operation="BUILD_CALENDAR", input_refs=["scenario.operating_windows"], output_ref="calendar.operating-hours", value=_decimal(calendar.hours), unit="h/day"),
        SimulationTraceNodeV1(node_id="simulation.arrivals", operation="GENERATE_ARRIVALS", input_refs=["scenario.task.demand", "scenario.task.batch"], output_ref="workload.jobs-per-day", value=str(jobs_per_day), unit="job/day"),
        SimulationTraceNodeV1(node_id="simulation.dispatch", operation="DISPATCH_FIFO", input_refs=["workload.arrivals", "scenario.fleet.selected"], output_ref="queue.completed-with-grace", value=str(len(completed_grace)), unit="job"),
        SimulationTraceNodeV1(node_id="simulation.allowance", operation="APPLY_NONPRODUCTIVE_ALLOWANCE", input_refs=["service.nominal-seconds", "service.effective-seconds"], output_ref="utilization.nonproductive-seconds", value=_decimal(Decimal(max(0, measure_busy - measure_productive)) / MICROS_PER_SECOND), unit="s"),
        SimulationTraceNodeV1(node_id="simulation.capacity", operation="COMPARE_CAPACITY", input_refs=["scenario.fleet.effective_capacity", "queue.completed-by-measurement-end"], output_ref="capacity.deviation-percent", value=None if deviation is None else _decimal(deviation), unit="%"),
        SimulationTraceNodeV1(node_id="simulation.sla", operation="EVALUATE_SLA", input_refs=["request.sla", "queue.turnaround"], output_ref="sla.on-time-fraction", value=None if on_time is None else _decimal(on_time), unit="1"),
    ]
    payload = dict(
        schema_version=SIMULATION_REPORT_VERSION,
        report_id="report.placeholder",
        request_id=request.request_id, tenant_id=request.tenant_id, project_id=request.project_id,
        scenario_revision_id=spec.revision_id, status=overall,
        engineering_claim="PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION",
        time_basis=SimulationTimeBasisV1(timezone=spec.operating_windows[0].timezone, operating_hours_per_day=_decimal(calendar.hours), window_refs=[item.window_id for item in spec.operating_windows]),
        workload=SimulationWorkloadV1(mode=request.mode, daily_units=_decimal(daily), peak_factor=request.peak_factor, simulated_units_per_day=_decimal(simulated), batch_units=_decimal(batch), jobs_per_day=jobs_per_day, fleet_units=fleet.selected_fleet, quantity_unit=str(task.demand.unit)),
        capacity=SimulationCapacityComparisonV1(required_per_hour=_decimal(required_per_hour), expected_effective_per_hour=_decimal(expected_per_hour), observed_per_hour=_decimal(observed_per_hour), unit=str(fleet.effective_capacity.unit).replace("/day", "/h"), deviation_percent=None if deviation is None else _decimal(deviation), verdict=capacity_verdict),
        queue=SimulationQueueMetricsV1(maximum_jobs=maximum_queue, mean_wait_seconds=None if not wait_values else _decimal(Decimal(sum(wait_values)) / len(wait_values) / MICROS_PER_SECOND), p95_wait_seconds=None if not wait_values else _decimal(Decimal(_nearest_rank(wait_values, Decimal("0.95"))) / MICROS_PER_SECOND), mean_turnaround_seconds=None if not turnaround_values else _decimal(Decimal(sum(turnaround_values)) / len(turnaround_values) / MICROS_PER_SECOND), p95_turnaround_seconds=None if not turnaround_values else _decimal(Decimal(_nearest_rank(turnaround_values, Decimal("0.95"))) / MICROS_PER_SECOND), measurement_jobs=len(measurement), completed_by_measurement_end=len(completed_measurement), completed_with_grace=len(completed_grace), completed_units_by_measurement_end=_decimal(completed_units), completed_units_with_grace=_decimal(sum((item.units for item in completed_grace), Decimal(0))), completed_unit=str(task.batch.units_per_cycle.unit), censored_jobs=len(measurement) - len(completed_grace)),
        utilization=SimulationUtilizationV1(busy_fraction=None if not fleet_work_us else _decimal(Decimal(measure_busy) / fleet_work_us), productive_fraction=None if not fleet_work_us else _decimal(Decimal(measure_productive) / fleet_work_us), nonproductive_fraction=None if not fleet_work_us else _decimal(Decimal(max(0, measure_busy - measure_productive)) / fleet_work_us), busy_seconds=_decimal(Decimal(measure_busy) / MICROS_PER_SECOND), productive_seconds=_decimal(Decimal(measure_productive) / MICROS_PER_SECOND), nonproductive_allowance_seconds=_decimal(Decimal(max(0, measure_busy - measure_productive)) / MICROS_PER_SECOND), failure_downtime_seconds=None, failure_downtime_status="NOT_EVALUATED_NO_INPUT", resource_wait_seconds=_decimal(Decimal(sum(item.resource_wait for item in measurement)) / MICROS_PER_SECOND)),
        sla=SimulationSlaResultV1(verdict=sla_verdict, sla_minutes=None if request.sla is None else request.sla.minutes, target_fraction=None if target is None else _decimal(target), on_time_fraction=None if on_time is None else _decimal(on_time), on_time_jobs=on_time_count, denominator_jobs=len(measurement), reason_codes=sla_reasons),
        resources=[SimulationResourceMetricsV1(resource_id=item.resource_id, stage=item.stage, capacity=item.capacity, wait_seconds=_decimal(Decimal(resource_waits[item.resource_id]) / MICROS_PER_SECOND), utilization_fraction=_decimal(Decimal(resource_busy[item.resource_id]) / (item.capacity * 2 * day_work_us))) for item in sorted(request.resources, key=lambda value: value.resource_id)],
        limitations=sorted(limitations), trace=trace, versions=SimulationVersionsV1(),
        replay=SimulationReplayV1(scenario_spec_digest=scenario_digest, canonical_request_digest=request_digest, report_content_digest="sha256:" + "0" * 64),
    )
    canonical = SimulationReportV1.model_construct(**payload).model_dump(mode="json")
    report_id = f"report.{semantic_digest(canonical).removeprefix('sha256:')[:16]}"
    finalized = {**canonical, "report_id": report_id, "replay": {**canonical["replay"]}}
    semantic = {**finalized, "replay": {**finalized["replay"]}}
    semantic["replay"]["report_content_digest"] = "sha256:" + "0" * 64
    finalized["replay"]["report_content_digest"] = semantic_digest(semantic)
    return SimulationReportV1.model_validate(finalized)


def run_simulation(
    request: SimulationRequestV1,
    *,
    should_cancel: Callable[[], bool] | None = None,
    progress: Callable[[SimulationProgressV1], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> SimulationReportV1 | SimulationErrorV1:
    """Run C23 without persistence/API side effects and return a typed terminal result."""

    try:
        return _run(request, should_cancel=should_cancel or (lambda: False),
                    progress=progress or (lambda _value: None), clock=clock)
    except _Stop as error:
        return SimulationErrorV1(
            request_id=request.request_id,
            scenario_revision_id=request.scenario_spec.revision_id,
            code=error.code,
            message=error.message,
        )
    except (ValueError, ZeroDivisionError) as error:
        return SimulationErrorV1(
            request_id=request.request_id,
            scenario_revision_id=request.scenario_spec.revision_id,
            code="INVALID_SCENARIO",
            message=str(error),
        )


__all__ = [
    "SimulationErrorV1", "SimulationProgressV1", "SimulationReportV1",
    "SimulationRequestV1", "SimulationResourceV1", "SimulationSlaV1",
    "run_simulation",
]
