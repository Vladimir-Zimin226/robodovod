"""Strict, deterministic ScenarioSpec v2 contract over immutable C11/C18 snapshots.

This module is deliberately additive.  The legacy ScenarioSpec v1 builder lives
in :mod:`scenario_spec` and remains the only adapter used by ``/api/calculate``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from calculation.economics.allocation import MultiprocessAllocationResultV1
from calculation_contracts import (
    CapacityAnalysisRequest,
    CapacityAnalysisResponse,
    Digest,
    ResultQuantity,
    StableId,
    StrictContractModel,
    VersionBindings,
    calculation_trace_digest,
    semantic_digest,
)


SCENARIO_SPEC_V2 = "scenario-spec-v2"
SCENARIO_SPEC_V2_POLICY = "scenario-spec-policy-v2"


class ScenarioVersionBindingsV2(StrictContractModel):
    scenario_contract_version: Literal["scenario-spec-v2"]
    scenario_policy_version: Literal["scenario-spec-policy-v2"]
    capacity_result_version: Literal["capacity-result-v1"]
    capacity_trace_version: Literal["calculation-trace-v1"]
    calculation: VersionBindings


class ScenarioAnalysisBindingV2(StrictContractModel):
    project_id: StableId
    tenant_id: StableId
    capacity_run_id: StableId
    input_revision: StableId
    capacity_request_digest: Digest
    capacity_result_digest: Digest
    capacity_trace_digest: Digest


class ScenarioOperatingWindowV2(StrictContractModel):
    window_id: StableId
    start_time: ResultQuantity
    duration: ResultQuantity
    timezone: Annotated[str, Field(min_length=1)]
    source: Literal["USER", "FILE", "PRESET", "POLICY"]
    provenance_ref: StableId

    @model_validator(mode="after")
    def validate_time_units(self) -> "ScenarioOperatingWindowV2":
        if self.start_time.unit != "s" or self.duration.unit != "h":
            raise ValueError("operating window must use seconds-from-midnight and hours")
        return self


class ScenarioExchangeV2(StrictContractModel):
    mode: Literal["TOTAL", "SPLIT", "NOT_APPLICABLE"]
    total_time: ResultQuantity | None = None
    load_time: ResultQuantity | None = None
    unload_time: ResultQuantity | None = None

    @model_validator(mode="after")
    def validate_union(self) -> "ScenarioExchangeV2":
        if self.mode == "TOTAL" and (self.total_time is None or self.load_time is not None or self.unload_time is not None):
            raise ValueError("TOTAL exchange requires only total_time")
        if self.mode == "SPLIT" and (self.total_time is not None or self.load_time is None or self.unload_time is None):
            raise ValueError("SPLIT exchange requires load_time and unload_time")
        if self.mode == "NOT_APPLICABLE" and any((self.total_time, self.load_time, self.unload_time)):
            raise ValueError("NOT_APPLICABLE exchange cannot contain time values")
        for value in (self.total_time, self.load_time, self.unload_time):
            if value is not None and value.unit != "s":
                raise ValueError("exchange values must use seconds")
        return self


class ScenarioBatchV2(StrictContractModel):
    semantics: Literal["PHYSICAL_BATCH", "AREA_MICROTASK", "ONE_OUTPUT_UNIT"]
    units_per_cycle: ResultQuantity
    provenance_ref: StableId


class ScenarioRouteBindingV2(StrictContractModel):
    route_id: StableId
    geometry_source: Literal["PROVIDED", "SYNTHETIC", "NOT_APPLICABLE"]
    one_way_distance: ResultQuantity | None = None
    geometry_ref: StableId | None = None
    assumption_ref: StableId | None = None

    @model_validator(mode="after")
    def validate_route(self) -> "ScenarioRouteBindingV2":
        if self.one_way_distance is not None and self.one_way_distance.unit != "m":
            raise ValueError("route distance must use metres")
        if self.geometry_source == "PROVIDED" and self.geometry_ref is None:
            raise ValueError("provided route requires geometry_ref")
        if self.geometry_source == "SYNTHETIC" and self.assumption_ref is None:
            raise ValueError("synthetic route requires an explicit assumption_ref")
        if self.geometry_source == "NOT_APPLICABLE" and any((self.one_way_distance, self.geometry_ref, self.assumption_ref)):
            raise ValueError("not-applicable route cannot carry geometry")
        return self


class ScenarioProfileV2(StrictContractModel):
    process_id: StableId
    process_code: Annotated[str, Field(min_length=1)]
    process_scope: Literal[
        "TRANSPORT_CYCLE", "DELIVERY_CYCLE", "CLEANING_AREA", "FIXED_CELL",
        "SCENARIO_ONLY", "REFERENCE_ONLY", "CONSTRAINT_ONLY",
    ]
    calculation_profile: Literal[
        "TRANSPORT_CYCLE_V1", "DELIVERY_CYCLE_V1", "CLEANING_AREA_V1",
        "PALLETIZING_CELL_V1", "USER_CYCLE_V1", "NOT_APPLICABLE",
    ]
    quantity_kind: Annotated[str, Field(min_length=1)]
    capacity_status: Literal["COMPLETE", "WITH_ASSUMPTIONS", "BLOCKED", "NOT_APPLICABLE"]


class ScenarioTaskV2(StrictContractModel):
    task_id: StableId
    zone_id: StableId
    process_id: StableId
    demand: ResultQuantity
    operating_window_refs: list[StableId] = Field(min_length=1)
    exchange: ScenarioExchangeV2
    batch: ScenarioBatchV2
    route_ref: StableId | None = None


class ScenarioFleetBindingV2(StrictContractModel):
    fleet_id: StableId
    zone_id: StableId
    process_id: StableId
    model_id: Annotated[str, Field(min_length=1)]
    position_id: Annotated[str, Field(min_length=1)]
    selected_fleet: Annotated[int, Field(ge=0)]
    recommended_fleet: Annotated[int, Field(ge=0)]
    nominal_capacity: ResultQuantity
    effective_capacity: ResultQuantity
    coverage: ResultQuantity
    raw_load_ratio: ResultQuantity | None
    utilization: ResultQuantity | None
    overloaded: bool


class ScenarioZoneV2(StrictContractModel):
    zone_id: StableId
    label: Annotated[str, Field(min_length=1)]
    geometry_source: Literal["PROVIDED", "SYNTHETIC", "UNKNOWN"]
    geometry_ref: StableId | None = None
    assumption_ref: StableId | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> "ScenarioZoneV2":
        if self.geometry_source == "PROVIDED" and self.geometry_ref is None:
            raise ValueError("provided zone geometry requires geometry_ref")
        if self.geometry_source == "SYNTHETIC" and self.assumption_ref is None:
            raise ValueError("synthetic zone geometry requires assumption_ref")
        return self


class ScenarioFinanceVersionsV2(StrictContractModel):
    engine_version: Literal["multiprocess-allocation-v1"]
    result_version: Literal["multiprocess-allocation-result-v1"]
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"]
    labour_policy_overlay_version: Literal["hackathon-calculation-policy-v1+v2a-c14"]
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    registry_digest: Digest
    precision_policy_version: Literal["decimal-context-28-half-even-v1"]


class ScenarioFinanceMetricV2(StrictContractModel):
    status: Literal["COMPLETE", "NOT_REACHED"]
    value: Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")] | None
    unit: Literal["RUB", "YEAR"]


class ScenarioFinanceBindingV2(StrictContractModel):
    source_schema_version: Literal["multiprocess-allocation-result-v1"]
    source_run_id: StableId
    source_result_digest: Digest
    cohort_id: StableId
    acquisition: Literal["PURCHASE", "RAAS"]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    horizon_years: Annotated[int, Field(ge=5, le=15)]
    project_capex_cashflow: ScenarioFinanceMetricV2
    npv_project: ScenarioFinanceMetricV2
    simple_payback: ScenarioFinanceMetricV2
    versions: ScenarioFinanceVersionsV2


class ScenarioAssumptionV2(StrictContractModel):
    assumption_id: StableId
    version: Annotated[str, Field(min_length=1)]
    provenance_ref: StableId
    scope: Annotated[str, Field(min_length=1)]
    message: Annotated[str, Field(min_length=1)]


class ScenarioSpecV2(StrictContractModel):
    schema_version: Literal["scenario-spec-v2"]
    revision_id: Annotated[str, Field(pattern=r"^calc_[0-9a-f]{16}$")]
    source: Literal["capacity-analysis"]
    template: Literal["warehouse", "airport", "hospital"]
    seed: Annotated[str, Field(pattern=r"^scenario-[0-9a-f]{16}$")]
    analysis: ScenarioAnalysisBindingV2
    versions: ScenarioVersionBindingsV2
    profile: ScenarioProfileV2
    operating_windows: list[ScenarioOperatingWindowV2] = Field(min_length=1)
    zones: list[ScenarioZoneV2] = Field(min_length=1)
    routes: list[ScenarioRouteBindingV2]
    fleet: list[ScenarioFleetBindingV2]
    tasks: list[ScenarioTaskV2]
    finance: ScenarioFinanceBindingV2 | None
    assumptions: list[ScenarioAssumptionV2]
    trace_node_refs: list[StableId] = Field(min_length=1)
    warnings: list[Annotated[str, Field(min_length=1)]]

    @model_validator(mode="after")
    def validate_references(self) -> "ScenarioSpecV2":
        zone_ids = [item.zone_id for item in self.zones]
        route_ids = [item.route_id for item in self.routes]
        window_ids = [item.window_id for item in self.operating_windows]
        assumption_ids = [item.assumption_id for item in self.assumptions]
        if (len(zone_ids) != len(set(zone_ids)) or len(route_ids) != len(set(route_ids))
                or len(window_ids) != len(set(window_ids))
                or len(assumption_ids) != len(set(assumption_ids))):
            raise ValueError("ScenarioSpec v2 identities must be unique")
        known_zones, known_routes, known_windows = set(zone_ids), set(route_ids), set(window_ids)
        known_assumptions = set(assumption_ids)
        if any(item.zone_id not in known_zones for item in [*self.fleet, *self.tasks]):
            raise ValueError("ScenarioSpec v2 contains a dangling zone reference")
        if any(item.route_ref is not None and item.route_ref not in known_routes for item in self.tasks):
            raise ValueError("ScenarioSpec v2 contains a dangling route reference")
        if any(not set(item.operating_window_refs).issubset(known_windows) for item in self.tasks):
            raise ValueError("ScenarioSpec v2 contains a dangling operating-window reference")
        if any(item.process_id != self.profile.process_id for item in [*self.fleet, *self.tasks]):
            raise ValueError("ScenarioSpec v2 process bindings must match the explicit profile")
        assumption_refs = {
            item.assumption_ref for item in [*self.zones, *self.routes]
            if item.assumption_ref is not None
        }
        if not assumption_refs.issubset(known_assumptions):
            raise ValueError("ScenarioSpec v2 contains a dangling geometry assumption")
        content = self.model_dump(mode="json", exclude={"revision_id"})
        expected = f"calc_{semantic_digest(content).removeprefix('sha256:')[:16]}"
        if self.revision_id != expected:
            raise ValueError("ScenarioSpec v2 revision_id does not match semantic content")
        return self


PROFILE_BY_SCOPE = {
    "TRANSPORT_CYCLE": "TRANSPORT_CYCLE_V1",
    "DELIVERY_CYCLE": "DELIVERY_CYCLE_V1",
    "CLEANING_AREA": "CLEANING_AREA_V1",
    "FIXED_CELL": "PALLETIZING_CELL_V1",
    "SCENARIO_ONLY": "USER_CYCLE_V1",
    "REFERENCE_ONLY": "NOT_APPLICABLE",
    "CONSTRAINT_ONLY": "NOT_APPLICABLE",
}
TEMPLATE_BY_OBJECT = {"WAREHOUSE": "warehouse", "AIRPORT": "airport", "CLINIC": "hospital"}


def _rq(value: str, unit: str, kind: str) -> ResultQuantity:
    return ResultQuantity(value=value, unit=unit, quantity_kind=kind)


def _exchange(request: CapacityAnalysisRequest) -> ScenarioExchangeV2:
    value = request.process.exchange
    if value is None:
        return ScenarioExchangeV2(mode="NOT_APPLICABLE")
    if value.mode == "TOTAL":
        return ScenarioExchangeV2(mode="TOTAL", total_time=_rq(value.total_time.normalized_value, "s", "TIME"))
    return ScenarioExchangeV2(
        mode="SPLIT",
        load_time=_rq(value.load_time.normalized_value, "s", "TIME"),
        unload_time=_rq(value.unload_time.normalized_value, "s", "TIME"),
    )


def _finance_binding(
    finance: MultiprocessAllocationResultV1,
    request: CapacityAnalysisRequest,
    tenant_id: str,
) -> ScenarioFinanceBindingV2:
    if (finance.tenant_id, finance.project_id, finance.input_revision) != (tenant_id, request.project_id, request.input_revision):
        raise ValueError("C18 finance tenant/project/revision binding mismatch")
    process = next((item for item in finance.processes if item.process_id == request.process.process_id), None)
    if process is None or (process.model_id, process.position_id) != (request.model_id, request.position_id):
        raise ValueError("C18 finance process/model/position binding mismatch")
    if process.acquisition != request.acquisition or finance.status != "COMPLETE":
        raise ValueError("C18 finance acquisition/status binding mismatch")
    payback = finance.simple_payback
    return ScenarioFinanceBindingV2(
        source_schema_version=finance.schema_version,
        source_run_id=finance.run_id,
        source_result_digest=semantic_digest(finance),
        cohort_id=finance.cohort_id,
        acquisition=process.acquisition,
        uncertainty=request.uncertainty,
        horizon_years=finance.horizon_years,
        project_capex_cashflow=ScenarioFinanceMetricV2(
            status="COMPLETE", value=finance.project_capex_cashflow, unit="RUB",
        ),
        npv_project=ScenarioFinanceMetricV2.model_validate(finance.npv_project.model_dump(mode="json")),
        simple_payback=ScenarioFinanceMetricV2.model_validate(payback.model_dump(mode="json")),
        versions=ScenarioFinanceVersionsV2.model_validate(finance.versions.model_dump(mode="json", exclude={"request_version"})),
    )


def build_scenario_spec_v2(
    request: CapacityAnalysisRequest,
    response: CapacityAnalysisResponse,
    *,
    tenant_id: str,
    operating_windows: list[ScenarioOperatingWindowV2],
    zone: ScenarioZoneV2,
    route: ScenarioRouteBindingV2,
    batch: ScenarioBatchV2,
    finance: MultiprocessAllocationResultV1 | None = None,
    assumptions: list[ScenarioAssumptionV2] | None = None,
    warnings: list[str] | None = None,
) -> ScenarioSpecV2:
    """Build one process-bound v2 spec without deriving new business values."""

    if (request.input_revision, request.process.process_id, request.model_id, request.position_id) != (
        response.input_revision,
        response.capacity.process_id,
        response.trace.envelope.model_id,
        response.trace.envelope.position_id,
    ):
        raise ValueError("C11 request/response identity binding mismatch")
    if response.run_id != response.trace.envelope.run_id:
        raise ValueError("C11 run binding mismatch")
    if calculation_trace_digest(response.trace) != response.trace.replay.trace_content_digest:
        raise ValueError("C11 trace digest mismatch")
    if response.capacity.value is None:
        raise ValueError("ScenarioSpec v2 requires an executable capacity snapshot")
    if request.process.schedule is None:
        raise ValueError("ScenarioSpec v2 requires explicit operating windows")
    expected_hours = (
        Decimal(request.process.schedule.shifts_per_day.normalized_value)
        * Decimal(request.process.schedule.shift_hours.normalized_value)
    )
    supplied_hours = sum((Decimal(item.duration.value) for item in operating_windows), Decimal(0))
    if supplied_hours != expected_hours:
        raise ValueError("operating windows must preserve C11 operating hours")

    values = response.capacity.value
    demand = request.process.demand
    if not hasattr(demand, "normalized_value"):
        raise ValueError("ScenarioSpec v2 requires known typed demand")
    route_value = route
    if request.process.route_distance is not None and route.one_way_distance is None:
        raise ValueError("route binding must preserve the analytical route distance")
    if request.process.route_distance is not None and (
        route.one_way_distance.value != request.process.route_distance.normalized_value
        or route.one_way_distance.unit != request.process.route_distance.unit
    ):
        raise ValueError("route binding cannot overwrite the analytical route distance")
    if request.process.explicit_batch is not None and (
        batch.units_per_cycle.value != request.process.explicit_batch.normalized_value
    ):
        raise ValueError("batch binding must preserve C11 batch semantics")
    finance_binding = None if finance is None else _finance_binding(finance, request, tenant_id)
    trace_refs = sorted({item.node_id for item in response.trace.formula_nodes})
    if not trace_refs:
        raise ValueError("ScenarioSpec v2 requires calculation trace node references")
    provenance_ref = request.process.demand.provenance_ref
    body = {
        "schema_version": SCENARIO_SPEC_V2,
        "source": "capacity-analysis",
        "template": TEMPLATE_BY_OBJECT[str(request.process.object_kind)],
        "analysis": ScenarioAnalysisBindingV2(
            project_id=request.project_id,
            tenant_id=tenant_id,
            capacity_run_id=response.run_id,
            input_revision=request.input_revision,
            capacity_request_digest=semantic_digest(request),
            capacity_result_digest=semantic_digest(response.capacity),
            capacity_trace_digest=response.trace.replay.trace_content_digest,
        ).model_dump(mode="json"),
        "versions": ScenarioVersionBindingsV2(
            scenario_contract_version=SCENARIO_SPEC_V2,
            scenario_policy_version=SCENARIO_SPEC_V2_POLICY,
            capacity_result_version="capacity-result-v1",
            capacity_trace_version="calculation-trace-v1",
            calculation=response.trace.versions,
        ).model_dump(mode="json"),
        "profile": ScenarioProfileV2(
            process_id=request.process.process_id,
            process_code=request.process.process_code,
            process_scope=request.process.scope,
            calculation_profile=PROFILE_BY_SCOPE[str(request.process.scope)],
            quantity_kind=request.process.quantity_kind,
            capacity_status=response.capacity.status,
        ).model_dump(mode="json"),
        "operating_windows": [item.model_dump(mode="json") for item in sorted(operating_windows, key=lambda item: item.window_id)],
        "zones": [zone.model_dump(mode="json")],
        "routes": [] if route.geometry_source == "NOT_APPLICABLE" else [route_value.model_dump(mode="json")],
        "fleet": [ScenarioFleetBindingV2(
            fleet_id=f"fleet.{request.process.process_id}", zone_id=zone.zone_id,
            process_id=request.process.process_id, model_id=request.model_id, position_id=request.position_id,
            selected_fleet=values.selected_fleet, recommended_fleet=values.recommended_fleet,
            nominal_capacity=values.nominal_capacity, effective_capacity=values.effective_capacity,
            coverage=values.coverage, raw_load_ratio=values.raw_load_ratio,
            utilization=values.utilization, overloaded=values.overloaded,
        ).model_dump(mode="json")],
        "tasks": [ScenarioTaskV2(
            task_id=f"task.{request.process.process_id}", zone_id=zone.zone_id,
            process_id=request.process.process_id,
            demand=_rq(demand.normalized_value, str(demand.unit), "FLOW"),
            operating_window_refs=[item.window_id for item in sorted(operating_windows, key=lambda item: item.window_id)],
            exchange=_exchange(request), batch=batch,
            route_ref=None if route.geometry_source == "NOT_APPLICABLE" else route.route_id,
        ).model_dump(mode="json")],
        "finance": None if finance_binding is None else finance_binding.model_dump(mode="json"),
        "assumptions": [item.model_dump(mode="json") for item in sorted(assumptions or [], key=lambda item: item.assumption_id)],
        "trace_node_refs": trace_refs,
        "warnings": sorted(warnings or []),
    }
    semantic = semantic_digest(body).removeprefix("sha256:")
    body["seed"] = f"scenario-{semantic[:16]}"
    revision = semantic_digest(body).removeprefix("sha256:")
    return ScenarioSpecV2(revision_id=f"calc_{revision[:16]}", **body)


__all__ = [
    "ScenarioAssumptionV2", "ScenarioBatchV2", "ScenarioOperatingWindowV2",
    "ScenarioRouteBindingV2", "ScenarioSpecV2", "ScenarioZoneV2",
    "build_scenario_spec_v2",
]
