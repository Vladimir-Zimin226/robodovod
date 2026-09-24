"""C20 deterministic sensitivity orchestration over immutable C18/C19 bindings."""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated, Literal

from calculation_contracts import Digest, StableId, StrictContractModel
from pydantic import Field, model_validator

from calculation.economics.allocation import (
    MultiprocessAllocationRequestV1,
    MultiprocessAllocationResultV1,
    calculate_multiprocess_allocation,
)

SENSITIVITY_ENGINE_VERSION = "economics-sensitivity-v1"
SENSITIVITY_REQUEST_VERSION = "sensitivity-request-v1"
SENSITIVITY_RESULT_VERSION = "sensitivity-result-v1"
ZERO_DIGEST = "sha256:" + "0" * 64

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]
MoneyString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")]
ParameterId = Literal["EQUIPMENT_PRICE", "OPERATION_VOLUME", "ROLE_SALARY"]


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _plain(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _digest(value: object) -> str:
    if isinstance(value, StrictContractModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CapacitySensitivityBindingV1(StrictContractModel):
    process_id: StableId
    result_version: Annotated[str, Field(min_length=1, max_length=96)]
    result_digest: Digest
    selected_fleet: Annotated[int, Field(ge=0)]
    demand_value: DecimalString
    demand_unit: Annotated[str, Field(min_length=1, max_length=32)]
    provenance_ref: StableId

    @model_validator(mode="after")
    def non_negative(self) -> CapacitySensitivityBindingV1:
        if _d(self.demand_value) <= 0:
            raise ValueError("capacity demand must be positive")
        return self


class SensitivityOverrideV1(StrictContractModel):
    parameter_id: ParameterId
    direction: Literal["LOWER", "UPPER"]
    delta_fraction: DecimalString
    scope_id: StableId
    base_value: DecimalString
    variant_value: DecimalString
    unit: Annotated[str, Field(min_length=1, max_length=32)]
    source: Literal["USER"] = "USER"
    provenance_ref: StableId

    @model_validator(mode="after")
    def exact_ten_percent(self) -> SensitivityOverrideV1:
        delta = _d(self.delta_fraction)
        expected = Decimal("-0.10") if self.direction == "LOWER" else Decimal("0.10")
        base = _d(self.base_value)
        variant = _d(self.variant_value)
        if delta != expected:
            raise ValueError("C20 tornado override must be exactly +/-10 percent")
        if base <= 0 or variant != base * (Decimal(1) + delta):
            raise ValueError("variant value must equal base value multiplied by 1 + delta")
        expected_unit = {
            "EQUIPMENT_PRICE": "RUB/robot",
            "OPERATION_VOLUME": "unit/day",
            "ROLE_SALARY": "RUB/person/month",
        }[self.parameter_id]
        if self.unit != expected_unit:
            raise ValueError("sensitivity parameter unit mismatch")
        return self


class SensitivityVariantInputV1(StrictContractModel):
    variant_id: StableId
    derived_run_id: StableId
    status: Literal["EXECUTABLE", "BLOCKED"]
    override: SensitivityOverrideV1
    capacity_bindings: list[CapacitySensitivityBindingV1]
    rerun_engines: list[Literal[
        "capacity-analysis-service-v2",
        "role-labour-baseline-v1",
        "purchase-cost-ledger-v1",
        "full-cashflows-reconciliation-v1",
        "full-cashflows-reconciliation-v2",
        "multiprocess-allocation-v1",
    ]]
    allocation_request: MultiprocessAllocationRequestV1 | None = None
    blocker_codes: list[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def executable_shape(self) -> SensitivityVariantInputV1:
        if len(self.capacity_bindings) != len({item.process_id for item in self.capacity_bindings}):
            raise ValueError("variant capacity bindings must be unique by process")
        if len(self.rerun_engines) != len(set(self.rerun_engines)):
            raise ValueError("rerun engines cannot be duplicated")
        if not self.rerun_engines or self.rerun_engines[-1] != "multiprocess-allocation-v1":
            raise ValueError("C20 must finish by rerunning the canonical C18 engine")
        if self.status == "EXECUTABLE":
            if self.allocation_request is None or self.blocker_codes:
                raise ValueError("executable variant requires allocation request and no blockers")
            if self.allocation_request.run_id != self.derived_run_id:
                raise ValueError("derived run identity mismatch")
        elif self.allocation_request is not None or not self.blocker_codes:
            raise ValueError("blocked variant requires blockers and forbids a synthetic result request")
        return self


class SensitivityRequestV1(StrictContractModel):
    schema_version: Literal["sensitivity-request-v1"] = SENSITIVITY_REQUEST_VERSION
    run_id: StableId
    parent_run_id: StableId
    project_id: StableId
    tenant_id: StableId
    object_id: StableId
    baseline_allocation_request: MultiprocessAllocationRequestV1
    baseline_allocation_result: MultiprocessAllocationResultV1
    baseline_allocation_result_digest: Digest
    ranking_result_version: Literal["ranking-result-v2"] = "ranking-result-v2"
    ranking_result_digest: Digest
    selected_candidate_id: StableId
    selected_configuration_id: StableId
    baseline_capacity_bindings: list[CapacitySensitivityBindingV1]
    variants: list[SensitivityVariantInputV1]

    @model_validator(mode="after")
    def bind_baseline_and_variants(self) -> SensitivityRequestV1:
        base_request = self.baseline_allocation_request
        base_result = self.baseline_allocation_result
        identity = (self.project_id, self.tenant_id, self.object_id)
        if (base_request.project_id, base_request.tenant_id, base_request.object_id) != identity:
            raise ValueError("baseline allocation request identity mismatch")
        if (base_result.project_id, base_result.tenant_id, base_result.object_id) != identity:
            raise ValueError("baseline allocation result identity mismatch")
        if self.parent_run_id != base_result.run_id or base_request.run_id != base_result.run_id:
            raise ValueError("parent run must bind the immutable C18 baseline")
        if self.baseline_allocation_result_digest != _digest(base_result):
            raise ValueError("baseline allocation result digest mismatch")
        config_ids = {item.configuration_id for item in base_request.configurations}
        if self.selected_configuration_id not in config_ids:
            raise ValueError("selected C19 configuration is outside the frozen C18 cohort")
        process_ids = {item.process_id for item in base_request.configurations}
        base_capacity = {item.process_id: item for item in self.baseline_capacity_bindings}
        if set(base_capacity) != process_ids:
            raise ValueError("baseline capacity bindings must exactly cover C18 processes")
        keys = [(item.override.parameter_id, item.override.direction) for item in self.variants]
        expected = {(parameter, direction) for parameter in (
            "EQUIPMENT_PRICE", "OPERATION_VOLUME", "ROLE_SALARY"
        ) for direction in ("LOWER", "UPPER")}
        if len(keys) != len(set(keys)) or set(keys) != expected:
            raise ValueError("C20 requires exactly six +/-10 percent variants")
        if len({item.variant_id for item in self.variants}) != len(self.variants):
            raise ValueError("variant identities must be unique")
        for variant in self.variants:
            _validate_variant(base_request, base_capacity, variant)
        self.variants = sorted(self.variants, key=lambda item: (item.override.parameter_id, item.override.direction))
        return self


class MetricDeltaV1(StrictContractModel):
    status: Literal["COMPLETE", "NOT_REACHED", "BLOCKED"]
    baseline_value: DecimalString | None
    variant_value: DecimalString | None
    delta_value: DecimalString | None
    unit: Literal["RUB", "YEAR"]
    reason_code: StableId | None = None


class SensitivityVariantResultV1(StrictContractModel):
    variant_id: StableId
    derived_run_id: StableId
    status: Literal["COMPLETE", "BLOCKED"]
    override: SensitivityOverrideV1
    allocation_result_digest: Digest | None
    allocation_trace_digest: Digest | None
    capacity_fleet_base: Annotated[int, Field(ge=0)]
    capacity_fleet_variant: Annotated[int, Field(ge=0)] | None
    capacity_fleet_delta: int | None
    project_capex: MetricDeltaV1
    npv_project: MetricDeltaV1
    simple_payback: MetricDeltaV1
    discounted_payback: MetricDeltaV1
    step_reasons: list[StableId]
    issues: list[StableId]


class SensitivityTraceNodeV1(StrictContractModel):
    node_id: StableId
    operation: Literal["BIND_BASELINE", "APPLY_OVERRIDE", "RERUN_ENGINE", "COMPARE_DELTA", "BLOCK_VARIANT"]
    input_refs: list[str]
    output_ref: StableId
    value: DecimalString | None
    unit: Annotated[str, Field(min_length=1, max_length=32)]
    reason_codes: list[StableId] = Field(default_factory=list)


class SensitivityVersionsV1(StrictContractModel):
    engine_version: Literal["economics-sensitivity-v1"] = SENSITIVITY_ENGINE_VERSION
    request_version: Literal["sensitivity-request-v1"] = SENSITIVITY_REQUEST_VERSION
    result_version: Literal["sensitivity-result-v1"] = SENSITIVITY_RESULT_VERSION
    allocation_engine_version: Literal["multiprocess-allocation-v1"] = "multiprocess-allocation-v1"
    ranking_result_version: Literal["ranking-result-v2"] = "ranking-result-v2"
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"] = "hackathon-calculation-policy-v1"
    precision_policy_version: Literal["decimal-context-28-half-even-v1"] = "decimal-context-28-half-even-v1"


class SensitivityReplayV1(StrictContractModel):
    canonical_input_digest: Digest
    baseline_allocation_result_digest: Digest
    ranking_result_digest: Digest
    variant_allocation_result_digests: list[Digest]
    trace_content_digest: Digest


class SensitivityResultV1(StrictContractModel):
    schema_version: Literal["sensitivity-result-v1"] = SENSITIVITY_RESULT_VERSION
    run_id: StableId
    parent_run_id: StableId
    project_id: StableId
    tenant_id: StableId
    object_id: StableId
    baseline_allocation_result_digest: Digest
    ranking_result_digest: Digest
    selected_candidate_id: StableId
    selected_configuration_id: StableId
    variants: list[SensitivityVariantResultV1]
    trace: list[SensitivityTraceNodeV1]
    versions: SensitivityVersionsV1
    replay: SensitivityReplayV1


def _same_capacity(left: dict[str, CapacitySensitivityBindingV1], right: dict[str, CapacitySensitivityBindingV1]) -> bool:
    return {key: value.model_dump(mode="json") for key, value in left.items()} == {
        key: value.model_dump(mode="json") for key, value in right.items()
    }


def _validate_variant(
    base: MultiprocessAllocationRequestV1,
    base_capacity: dict[str, CapacitySensitivityBindingV1],
    variant: SensitivityVariantInputV1,
) -> None:
    capacity = {item.process_id: item for item in variant.capacity_bindings}
    if set(capacity) != set(base_capacity):
        raise ValueError("variant capacity bindings must exactly cover baseline processes")
    override = variant.override
    if override.parameter_id in ("EQUIPMENT_PRICE", "ROLE_SALARY") and not _same_capacity(base_capacity, capacity):
        raise ValueError("price and salary sensitivity cannot change capacity snapshots")
    if override.parameter_id == "OPERATION_VOLUME":
        if override.scope_id not in capacity:
            raise ValueError("volume override must target a bound process")
        for process_id, after in capacity.items():
            before = base_capacity[process_id]
            if process_id == override.scope_id:
                if after.demand_unit != before.demand_unit or _d(after.demand_value) != _d(override.variant_value):
                    raise ValueError("volume override differs from variant capacity demand")
                if _d(before.demand_value) != _d(override.base_value):
                    raise ValueError("volume override differs from baseline capacity demand")
            elif before.model_dump(mode="json") != after.model_dump(mode="json"):
                raise ValueError("volume override cannot mutate unrelated capacity snapshots")
    if variant.status == "BLOCKED":
        return
    derived = variant.allocation_request
    assert derived is not None
    if (derived.project_id, derived.tenant_id, derived.object_id, derived.cohort_id) != (
        base.project_id, base.tenant_id, base.object_id, base.cohort_id
    ):
        raise ValueError("sensitivity variant escaped baseline tenant/project/object/cohort")
    if (derived.uncertainty, derived.shared_site_capital, derived.shared_annual_costs, derived.discount_rate) != (
        base.uncertainty, base.shared_site_capital, base.shared_annual_costs, base.discount_rate
    ):
        raise ValueError("C20 override cannot mutate uncertainty, shared costs, or discount rate")
    identities = lambda request: [
        (item.configuration_id, item.process_id, item.model_id, item.position_id, item.acquisition)
        for item in request.configurations
    ]
    if identities(derived) != identities(base):
        raise ValueError("sensitivity cannot change selected configuration identities")
    if override.parameter_id == "EQUIPMENT_PRICE":
        positions = {item.position_id for item in base.configurations}
        if override.scope_id not in positions:
            raise ValueError("equipment price override must target a selected position")
        if derived.labour_result_digest != base.labour_result_digest:
            raise ValueError("equipment price override cannot change labour snapshot")
    elif override.parameter_id == "ROLE_SALARY":
        base_roles = {item.role_id: item for item in base.labour_result.roles}
        derived_roles = {item.role_id: item for item in derived.labour_result.roles}
        if override.scope_id not in base_roles or set(base_roles) != set(derived_roles):
            raise ValueError("salary override must target an existing C14 role")
        before, after = base_roles[override.scope_id], derived_roles[override.scope_id]
        if before.money is None or after.money is None:
            raise ValueError("salary sensitivity requires complete role money")
        if _d(before.money.monthly_gross) != _d(override.base_value) or _d(after.money.monthly_gross) != _d(override.variant_value):
            raise ValueError("salary override differs from C14 role money")


def _metric_delta(base: object, variant: object, unit: Literal["RUB", "YEAR"]) -> MetricDeltaV1:
    base_status, variant_status = base.status, variant.status
    if base_status != "COMPLETE" or variant_status != "COMPLETE":
        return MetricDeltaV1(
            status="NOT_REACHED", baseline_value=base.value, variant_value=variant.value,
            delta_value=None, unit=unit, reason_code="metric-not-reached",
        )
    base_value, variant_value = _d(base.value), _d(variant.value)
    render = _money if unit == "RUB" else _plain
    return MetricDeltaV1(
        status="COMPLETE", baseline_value=render(base_value), variant_value=render(variant_value),
        delta_value=render(variant_value - base_value), unit=unit,
    )


def _blocked_metric(unit: Literal["RUB", "YEAR"], reason: str) -> MetricDeltaV1:
    return MetricDeltaV1(
        status="BLOCKED", baseline_value=None, variant_value=None, delta_value=None,
        unit=unit, reason_code=reason,
    )


def calculate_sensitivity(request: SensitivityRequestV1) -> SensitivityResultV1:
    """Rerun canonical C18 for each explicit variant without duplicating its math."""

    base_input_digest = _digest(request.baseline_allocation_request)
    base_before = _digest(request.baseline_allocation_result)
    recalculated_base = calculate_multiprocess_allocation(request.baseline_allocation_request)
    if recalculated_base.model_dump(mode="json") != request.baseline_allocation_result.model_dump(mode="json"):
        raise ValueError("immutable baseline does not replay through canonical C18 engine")
    trace = [SensitivityTraceNodeV1(
        node_id="sensitivity.baseline", operation="BIND_BASELINE",
        input_refs=[base_input_digest, request.baseline_allocation_result_digest, request.ranking_result_digest],
        output_ref="sensitivity.baseline.bound", value=None, unit="binding",
    )]
    base_capacity_total = sum(item.selected_fleet for item in request.baseline_capacity_bindings)
    results: list[SensitivityVariantResultV1] = []
    allocation_digests: list[str] = []
    for variant in request.variants:
        override = variant.override
        trace.append(SensitivityTraceNodeV1(
            node_id=f"override.{variant.variant_id}", operation="APPLY_OVERRIDE",
            input_refs=[override.provenance_ref, f"baseline.{override.scope_id}"],
            output_ref=f"variant.{variant.variant_id}.input", value=override.variant_value,
            unit=override.unit,
        ))
        if variant.status == "BLOCKED":
            reason = variant.blocker_codes[0]
            trace.append(SensitivityTraceNodeV1(
                node_id=f"blocked.{variant.variant_id}", operation="BLOCK_VARIANT",
                input_refs=variant.blocker_codes, output_ref=f"variant.{variant.variant_id}.status",
                value=None, unit="status", reason_codes=variant.blocker_codes,
            ))
            blocked_rub = _blocked_metric("RUB", reason)
            blocked_year = _blocked_metric("YEAR", reason)
            results.append(SensitivityVariantResultV1(
                variant_id=variant.variant_id, derived_run_id=variant.derived_run_id, status="BLOCKED",
                override=override, allocation_result_digest=None, allocation_trace_digest=None,
                capacity_fleet_base=base_capacity_total, capacity_fleet_variant=None, capacity_fleet_delta=None,
                project_capex=blocked_rub, npv_project=blocked_rub,
                simple_payback=blocked_year, discounted_payback=blocked_year,
                step_reasons=[], issues=variant.blocker_codes,
            ))
            continue
        assert variant.allocation_request is not None
        calculated = calculate_multiprocess_allocation(variant.allocation_request)
        result_digest = _digest(calculated)
        allocation_digests.append(result_digest)
        capacity_total = sum(item.selected_fleet for item in variant.capacity_bindings)
        fleet_delta = capacity_total - base_capacity_total
        reasons = [
            "discrete-fleet-step" if fleet_delta else "no-discrete-fleet-step",
            "headcount-step" if calculated.total_released_people != recalculated_base.total_released_people else "no-headcount-step",
        ]
        project_capex = MetricDeltaV1(
            status="COMPLETE", baseline_value=recalculated_base.project_capex_cashflow,
            variant_value=calculated.project_capex_cashflow,
            delta_value=_money(_d(calculated.project_capex_cashflow) - _d(recalculated_base.project_capex_cashflow)),
            unit="RUB",
        )
        results.append(SensitivityVariantResultV1(
            variant_id=variant.variant_id, derived_run_id=variant.derived_run_id, status="COMPLETE",
            override=override, allocation_result_digest=result_digest,
            allocation_trace_digest=calculated.replay.trace_content_digest,
            capacity_fleet_base=base_capacity_total, capacity_fleet_variant=capacity_total,
            capacity_fleet_delta=fleet_delta, project_capex=project_capex,
            npv_project=_metric_delta(recalculated_base.npv_project, calculated.npv_project, "RUB"),
            simple_payback=_metric_delta(recalculated_base.simple_payback, calculated.simple_payback, "YEAR"),
            discounted_payback=_metric_delta(recalculated_base.discounted_payback, calculated.discounted_payback, "YEAR"),
            step_reasons=reasons, issues=[],
        ))
        trace.extend([
            SensitivityTraceNodeV1(
                node_id=f"rerun.{variant.variant_id}", operation="RERUN_ENGINE",
                input_refs=[_digest(variant.allocation_request), *variant.rerun_engines],
                output_ref=f"variant.{variant.variant_id}.allocation", value=None, unit="binding",
            ),
            SensitivityTraceNodeV1(
                node_id=f"delta.{variant.variant_id}.npv", operation="COMPARE_DELTA",
                input_refs=[request.baseline_allocation_result_digest, result_digest],
                output_ref=f"variant.{variant.variant_id}.npv-delta",
                value=results[-1].npv_project.delta_value, unit="RUB", reason_codes=reasons,
            ),
        ])
    if _digest(request.baseline_allocation_result) != base_before:
        raise RuntimeError("sensitivity mutated immutable baseline")
    replay = SensitivityReplayV1(
        canonical_input_digest=_digest(request),
        baseline_allocation_result_digest=request.baseline_allocation_result_digest,
        ranking_result_digest=request.ranking_result_digest,
        variant_allocation_result_digests=sorted(allocation_digests),
        trace_content_digest=ZERO_DIGEST,
    )
    result = SensitivityResultV1(
        run_id=request.run_id, parent_run_id=request.parent_run_id,
        project_id=request.project_id, tenant_id=request.tenant_id, object_id=request.object_id,
        baseline_allocation_result_digest=request.baseline_allocation_result_digest,
        ranking_result_digest=request.ranking_result_digest,
        selected_candidate_id=request.selected_candidate_id,
        selected_configuration_id=request.selected_configuration_id,
        variants=results, trace=trace, versions=SensitivityVersionsV1(), replay=replay,
    )
    payload = result.model_dump(mode="json")
    payload["replay"]["trace_content_digest"] = None
    result.replay.trace_content_digest = _digest(payload)
    return result


__all__ = ["SensitivityRequestV1", "SensitivityResultV1", "calculate_sensitivity"]
