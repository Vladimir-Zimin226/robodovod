"""C25 reconciliation between C23 KPI and RobCraft visual telemetry.

RobCraft is a time-step renderer, not a second capacity or economics engine.
Only observations explicitly captured on the C23 measurement basis are
comparable; ordinary live renderer snapshots remain NOT_COMPARABLE.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from calculation.scheduling import SimulationReportV1
from calculation_contracts import DecimalString, Digest, StableId, StrictContractModel


class RobCraftReportBindingsV1(StrictContractModel):
    scenario_revision_id: Annotated[str, Field(pattern=r"^calc_[0-9a-f]{16}$")]
    scenario_spec_version: Literal["scenario-spec-v1", "scenario-spec-v2"]
    scenario_seed: str
    authoritative_report_id: StableId | None
    authoritative_report_digest: Digest | None
    scheduler_seed: int | None


class RobCraftReportVersionsV1(StrictContractModel):
    renderer_engine_version: Literal["robcraft-time-step-v1"]
    event_profile_version: Literal["robcraft-visual-events-v1"]
    report_version: Literal["robcraft-renderer-report-v1"]


class RobCraftMeasurementBasisV1(StrictContractModel):
    kind: Literal["LIVE_RENDERER_WINDOW", "C23_MEASUREMENT_WINDOW"]
    elapsed_seconds: DecimalString
    operating_hours_per_day: DecimalString
    operating_window_refs: list[StableId]
    warmup_days: int | None = None
    measurement_days: int | None = None


class RobCraftGeometryStatusV1(StrictContractModel):
    source: Literal["PROVIDED", "SYNTHETIC", "UNKNOWN", "REPRESENTATIVE"]
    status: Literal["BASE", "MODIFIED"]
    base_revision_id: Annotated[str, Field(pattern=r"^calc_[0-9a-f]{16}$")]
    economics_status: Literal["UNCHANGED"]
    analytical_route_ref: StableId | None
    analytical_distance_value: DecimalString | None
    analytical_distance_unit: Literal["m"] | None

    @model_validator(mode="after")
    def bind_distance(self) -> "RobCraftGeometryStatusV1":
        if (self.analytical_distance_value is None) != (self.analytical_distance_unit is None):
            raise ValueError("analytical distance value and unit must appear together")
        return self


class RobCraftObservedMetricsV1(StrictContractModel):
    completed_units: DecimalString
    throughput_units_per_hour: DecimalString
    throughput_unit: Annotated[str, Field(min_length=1)]
    queued_jobs: Annotated[int, Field(ge=0)]
    average_queue_seconds: DecimalString


class RobCraftUtilizationV1(StrictContractModel):
    moving_percent: DecimalString
    moving_basis: Literal["ROBOT_MOVING_TIME_OVER_RENDERER_ELAPSED_FLEET_TIME"]
    productive_percent: None
    productive_status: Literal["NOT_EVALUATED_LOCAL_TIME_STEP"]


class RobCraftEnergyV1(StrictContractModel):
    value: DecimalString
    unit: Literal["ARBITRARY_RENDERER_UNIT"]
    economics_status: Literal["NOT_COMPARABLE_TO_RUB_OR_KWH"]


class RobCraftModelStatusV1(StrictContractModel):
    sla: Literal["NOT_EVALUATED_USE_C23_REPORT"]
    failures: Literal["VISUAL_DEMO_ONLY_NOT_ANALYTICAL"]
    charging: Literal["VISUAL_DEMO_ONLY_NOT_ANALYTICAL"]
    engineering_claim: Literal["CONCEPTUAL_VISUALIZATION_NOT_CERTIFICATION"]


class RobCraftRendererReportV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)
    schema_version: Literal["robcraft-renderer-report-v1"]
    status: Literal["LOCAL_VISUAL_OBSERVATION_ONLY"]
    bindings: RobCraftReportBindingsV1
    versions: RobCraftReportVersionsV1
    measurement_basis: RobCraftMeasurementBasisV1
    geometry: RobCraftGeometryStatusV1
    observed: RobCraftObservedMetricsV1
    utilization: RobCraftUtilizationV1
    energy: RobCraftEnergyV1
    model_status: RobCraftModelStatusV1
    limitations: list[StableId]


class RobCraftKpiComparisonV1(StrictContractModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)
    schema_version: Literal["robcraft-kpi-comparison-v1"] = "robcraft-kpi-comparison-v1"
    scenario_revision_id: Annotated[str, Field(pattern=r"^calc_[0-9a-f]{16}$")]
    authoritative_report_id: StableId
    authoritative_report_digest: Digest
    renderer_report_version: Literal["robcraft-renderer-report-v1"]
    status: Literal["CONSISTENT", "DEVIATION", "NOT_COMPARABLE", "INPUT_MISMATCH"]
    authoritative_observed_per_hour: DecimalString
    renderer_observed_per_hour: DecimalString
    unit: Annotated[str, Field(min_length=1)]
    deviation_percent: DecimalString | None
    warning_threshold_percent: Literal["10"] = "10"
    warning: bool
    denominator: Literal["C23_OBSERVED_CAPACITY"] = "C23_OBSERVED_CAPACITY"
    reasons: list[StableId]
    geometry_status: Literal["BASE", "MODIFIED"]
    economics_status: Literal["UNCHANGED"]


def _canonical(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def compare_robcraft_report(
    authoritative: SimulationReportV1,
    renderer: RobCraftRendererReportV1,
) -> RobCraftKpiComparisonV1:
    """Compare only like-for-like throughput; never infer finance or SLA."""

    bindings = renderer.bindings
    if (
        bindings.scenario_revision_id != authoritative.scenario_revision_id
        or bindings.authoritative_report_id != authoritative.report_id
        or bindings.authoritative_report_digest != authoritative.replay.report_content_digest
        or bindings.scheduler_seed != authoritative.time_basis.seed
    ):
        raise ValueError("stale or mismatched RobCraft/C23 report binding")

    basis = renderer.measurement_basis
    expected_measurement_seconds = (
        Decimal(authoritative.time_basis.operating_hours_per_day)
        * Decimal(3600)
        * Decimal(authoritative.time_basis.measurement_days)
    )
    same_basis = (
        basis.kind == "C23_MEASUREMENT_WINDOW"
        and Decimal(basis.elapsed_seconds) == expected_measurement_seconds
        and Decimal(basis.operating_hours_per_day) == Decimal(authoritative.time_basis.operating_hours_per_day)
        and basis.operating_window_refs == authoritative.time_basis.window_refs
        and basis.warmup_days == authoritative.time_basis.warmup_days
        and basis.measurement_days == authoritative.time_basis.measurement_days
    )
    same_unit = renderer.observed.throughput_unit == authoritative.capacity.unit
    reasons: list[str] = []
    if not same_basis:
        reasons.append("measurement-basis-mismatch")
    if not same_unit:
        reasons.append("throughput-unit-mismatch")

    reference = Decimal(authoritative.capacity.observed_per_hour)
    observed = Decimal(renderer.observed.throughput_units_per_hour)
    status: str
    deviation: Decimal | None = None
    warning = False
    if not same_basis or not same_unit:
        status = "NOT_COMPARABLE"
    elif reference == 0:
        status = "CONSISTENT" if observed == 0 else "INPUT_MISMATCH"
        warning = observed != 0
        if warning:
            reasons.append("zero-authoritative-observed")
    else:
        deviation = abs(observed - reference) / abs(reference) * Decimal(100)
        warning = deviation > Decimal(10)
        status = "DEVIATION" if warning else "CONSISTENT"
        if warning:
            reasons.append("deviation-strictly-greater-than-10-percent")

    return RobCraftKpiComparisonV1(
        scenario_revision_id=authoritative.scenario_revision_id,
        authoritative_report_id=authoritative.report_id,
        authoritative_report_digest=authoritative.replay.report_content_digest,
        renderer_report_version=renderer.versions.report_version,
        status=status,
        authoritative_observed_per_hour=authoritative.capacity.observed_per_hour,
        renderer_observed_per_hour=renderer.observed.throughput_units_per_hour,
        unit=authoritative.capacity.unit,
        deviation_percent=None if deviation is None else _canonical(deviation),
        warning=warning,
        reasons=reasons,
        geometry_status=renderer.geometry.status,
        economics_status=renderer.geometry.economics_status,
    )


__all__ = [
    "RobCraftKpiComparisonV1",
    "RobCraftRendererReportV1",
    "compare_robcraft_report",
]
