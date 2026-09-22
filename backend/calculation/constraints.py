"""Evidence-gated applicability constraints for C05.

This service does not rank candidates, size fleets or calculate economics.
Rules are evaluated once and the same report is consumed by readiness and
future execution paths.  Legacy ``economics.check_constraints`` is untouched.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from calculation_contracts import (
    CALCULATION_POLICY_VERSION,
    DecimalString,
    ObjectKind,
    ProcessCode,
    ProcessScope,
    StableId,
    StrictContractModel,
)
from pydantic import Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES_PATH = ROOT / "data" / "calculation" / "constraint-rules-v2.json"
RULES_VERSION = "calculation-constraint-rules-v2"


class ConstraintRule(StrictContractModel):
    rule_id: StableId
    version: Literal["2.0.0"]
    severity: Literal["CRITICAL", "WARNING", "ADVISORY"]
    evaluator: StableId
    source_refs: list[str] = Field(min_length=1)
    decision_refs: list[str] = Field(default_factory=list)
    localization_key: StableId


class ConstraintRules(StrictContractModel):
    schema_version: Literal["constraint-rules-v2"]
    rules_version: Literal["calculation-constraint-rules-v2"]
    policy_version: Literal["hackathon-calculation-policy-v1"]
    migration_notes: list[str]
    rules: list[ConstraintRule] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_rules(self) -> ConstraintRules:
        ids = [item.rule_id for item in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate constraint rule")
        return self


class RequirementSource(StrictContractModel):
    kind: Literal["USER", "FILE", "ASSUMPTION", "POLICY"]
    source_ref: str = Field(min_length=1)
    user_confirmed: bool = False


class EvidenceBinding(StrictContractModel):
    evidence_status: Literal[
        "MATCHING_SAFE", "CONFLICT", "AMBIGUOUS_MODEL_MATCH", "NOT_FOUND", "UNKNOWN"
    ]
    source_ref: str = Field(min_length=1)
    fact_id: str | None = None


class ObjectConstraintContext(StrictContractModel):
    object_kind: ObjectKind
    route_zones: list[str] = Field(default_factory=list)
    route_floors: list[int] = Field(default_factory=list)
    time_scope: Literal["DAY", "NIGHT", "ANY"] = "ANY"
    required_cargo_kind: str | None = None
    max_payload_kg: DecimalString | None = None
    min_aisle_width_m: DecimalString | None = None
    ceiling_height_m: DecimalString | None = None
    required_lift_height_m: DecimalString | None = None
    temperature_min_c: DecimalString | None = None
    temperature_max_c: DecimalString | None = None
    max_noise_dba: DecimalString | None = None
    floor_flatness_mm_2m: DecimalString | None = None
    floor_covering: str | None = None
    max_slope_percent: DecimalString | None = None
    outdoor_required: bool = False
    airside_required: bool = False
    apron_required: bool = False
    restricted_zone_required: bool = False
    sanitization_required: bool = False
    class_b_containment_required: bool = False
    required_access_protocols: list[str] = Field(default_factory=list)
    required_integrations: list[str] = Field(default_factory=list)
    horizon_years: int | None = Field(default=None, ge=1)
    budget_rub: DecimalString | None = None
    available_charging_power_kw: DecimalString | None = None
    active_area_m2: DecimalString | None = None
    fleet_units: int | None = Field(default=None, ge=0)
    requirement_sources: dict[str, RequirementSource] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_requirement_domain(self) -> ObjectConstraintContext:
        non_negative = (
            "max_payload_kg", "min_aisle_width_m", "ceiling_height_m",
            "required_lift_height_m", "max_noise_dba", "floor_flatness_mm_2m",
            "max_slope_percent", "budget_rub", "available_charging_power_kw",
            "active_area_m2",
        )
        if any(
            getattr(self, field) is not None and _decimal(getattr(self, field)) < 0
            for field in non_negative
        ):
            raise ValueError("physical requirements must be non-negative")
        if (
            self.temperature_min_c is not None
            and self.temperature_max_c is not None
            and _decimal(self.temperature_min_c) > _decimal(self.temperature_max_c)
        ):
            raise ValueError("temperature_min_c must not exceed temperature_max_c")
        unknown_sources = set(self.requirement_sources) - set(type(self).model_fields)
        if unknown_sources:
            raise ValueError(f"unknown requirement source keys: {sorted(unknown_sources)}")
        return self


class CandidateConstraintFacts(StrictContractModel):
    model_id: StableId
    position_id: StableId
    supported_object_kinds: list[ObjectKind] | None = None
    supported_process_scopes: list[ProcessScope] | None = None
    supported_cargo_kinds: list[str] | None = None
    payload_kg: DecimalString | None = None
    min_aisle_width_m: DecimalString | None = None
    max_lift_height_m: DecimalString | None = None
    lift_protocols: list[str] | None = None
    temperature_min_c: DecimalString | None = None
    temperature_max_c: DecimalString | None = None
    noise_dba: DecimalString | None = None
    allowed_time_scopes: list[Literal["DAY", "NIGHT", "ANY"]] | None = None
    allowed_zones: list[str] | None = None
    airside_operational_permission: bool | None = None
    apron_operational_permission: bool | None = None
    restricted_zone_access_supported: bool | None = None
    sterilization_supported: bool | None = None
    class_b_containment_supported: bool | None = None
    cleanable_surface: bool | None = None
    material_disinfection_supported: bool | None = None
    supported_access_protocols: list[str] | None = None
    technical_passport_available: bool | None = None
    floor_flatness_tolerance_mm_2m: DecimalString | None = None
    supported_floor_coverings: list[str] | None = None
    max_slope_percent: DecimalString | None = None
    outdoor_supported: bool | None = None
    availability: DecimalString | None = None
    supported_integrations: list[str] | None = None
    expected_life_years: DecimalString | None = None
    capex_rub: DecimalString | None = None
    charging_power_kw: DecimalString | None = None
    evidence: dict[str, EvidenceBinding] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_candidate_domain(self) -> CandidateConstraintFacts:
        non_negative = (
            "payload_kg", "min_aisle_width_m", "max_lift_height_m", "noise_dba",
            "floor_flatness_tolerance_mm_2m", "max_slope_percent",
            "expected_life_years", "capex_rub", "charging_power_kw",
        )
        if any(
            getattr(self, field) is not None and _decimal(getattr(self, field)) < 0
            for field in non_negative
        ):
            raise ValueError("candidate physical facts must be non-negative")
        if self.availability is not None and not Decimal(0) <= _decimal(self.availability) <= Decimal(1):
            raise ValueError("availability must be between 0 and 1")
        if (
            self.temperature_min_c is not None
            and self.temperature_max_c is not None
            and _decimal(self.temperature_min_c) > _decimal(self.temperature_max_c)
        ):
            raise ValueError("candidate temperature_min_c must not exceed temperature_max_c")
        evidence_fields = set(type(self).model_fields) - {"model_id", "position_id", "evidence"}
        unknown_evidence = set(self.evidence) - evidence_fields
        if unknown_evidence:
            raise ValueError(f"unknown evidence keys: {sorted(unknown_evidence)}")
        return self


class ConstraintEvaluationRequest(StrictContractModel):
    schema_version: Literal["constraint-evaluation-request-v2"] = "constraint-evaluation-request-v2"
    input_revision: StableId
    process_id: StableId
    process_code: ProcessCode
    process_scope: ProcessScope
    context: ObjectConstraintContext
    candidate: CandidateConstraintFacts

    @model_validator(mode="after")
    def process_matches_object(self) -> ConstraintEvaluationRequest:
        if self.process_code.split("_", 1)[0].upper() != self.context.object_kind:
            raise ValueError("process_code does not belong to object_kind")
        return self


class ConstraintValue(StrictContractModel):
    value: Any
    unit: str | None = None
    source_ref: str


class ConstraintCheck(StrictContractModel):
    check_id: StableId
    rule_version: str
    applicable: bool
    severity: Literal["CRITICAL", "WARNING", "ADVISORY"]
    status: Literal["PASS", "FAIL", "UNKNOWN", "ASSUMED", "N_A"]
    reason_code: StableId
    scope: dict[str, Any]
    required: ConstraintValue | None = None
    available: ConstraintValue | None = None
    source_refs: list[str]
    decision_refs: list[str]
    localization_key: StableId


class ConstraintReportV2(StrictContractModel):
    schema_version: Literal["constraint-report-v2"] = "constraint-report-v2"
    rules_version: Literal["calculation-constraint-rules-v2"] = RULES_VERSION
    policy_version: Literal["hackathon-calculation-policy-v1"] = CALCULATION_POLICY_VERSION
    input_revision: StableId
    process_id: StableId
    model_id: StableId
    position_id: StableId
    eligibility: Literal["ELIGIBLE", "NEEDS_VALIDATION", "BLOCKED"]
    checks: list[ConstraintCheck]
    blocker_codes: list[StableId]
    validation_codes: list[StableId]
    warning_codes: list[StableId]


@lru_cache(maxsize=4)
def load_constraint_rules(path_text: str | None = None) -> ConstraintRules:
    path = Path(path_text) if path_text else DEFAULT_RULES_PATH
    return ConstraintRules.model_validate_json(path.read_text(encoding="utf-8"))


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def _fact(request: ConstraintEvaluationRequest, field: str) -> tuple[Any, str | None]:
    binding = request.candidate.evidence.get(field)
    if binding is None or binding.evidence_status != "MATCHING_SAFE":
        return None, binding.source_ref if binding else None
    return getattr(request.candidate, field), binding.source_ref


def _required(request: ConstraintEvaluationRequest, field: str) -> tuple[Any, str]:
    source = request.context.requirement_sources.get(field)
    value = getattr(request.context, field)
    if source is None:
        return value, f"request:{field}"
    return value, source.source_ref


def _value(value: Any, unit: str | None, source_ref: str | None) -> ConstraintValue | None:
    return None if value is None or source_ref is None else ConstraintValue(value=value, unit=unit, source_ref=source_ref)


def _compare_max(request: ConstraintEvaluationRequest, required_field: str, fact_field: str, unit: str) -> tuple[str, str, ConstraintValue | None, ConstraintValue | None]:
    required, required_ref = _required(request, required_field)
    available, available_ref = _fact(request, fact_field)
    if required is None:
        return "N_A", "requirement-not-applicable", None, _value(available, unit, available_ref)
    if available is None:
        return "UNKNOWN", "candidate-fact-missing", _value(required, unit, required_ref), None
    passed = _decimal(available) >= _decimal(required)
    return ("PASS" if passed else "FAIL"), ("requirement-satisfied" if passed else "requirement-exceeded"), _value(required, unit, required_ref), _value(available, unit, available_ref)


def _compare_min(request: ConstraintEvaluationRequest, required_field: str, fact_field: str, unit: str) -> tuple[str, str, ConstraintValue | None, ConstraintValue | None]:
    required, required_ref = _required(request, required_field)
    available, available_ref = _fact(request, fact_field)
    if required is None:
        return "N_A", "requirement-not-applicable", None, _value(available, unit, available_ref)
    if available is None:
        return "UNKNOWN", "candidate-fact-missing", _value(required, unit, required_ref), None
    passed = _decimal(required) >= _decimal(available)
    return ("PASS" if passed else "FAIL"), ("requirement-satisfied" if passed else "requirement-exceeded"), _value(required, unit, required_ref), _value(available, unit, available_ref)


def _compare_consumption(
    request: ConstraintEvaluationRequest,
    available_field: str,
    consumption_field: str,
    unit: str,
) -> tuple[str, str, ConstraintValue | None, ConstraintValue | None]:
    available, available_ref = _required(request, available_field)
    consumption, consumption_ref = _fact(request, consumption_field)
    if available is None:
        return "N_A", "limit-not-provided", None, _value(consumption, unit, consumption_ref)
    if consumption is None:
        return "UNKNOWN", "candidate-fact-missing", _value(available, unit, available_ref), None
    passed = _decimal(consumption) <= _decimal(available)
    return (
        ("PASS" if passed else "FAIL"),
        ("limit-satisfied" if passed else "limit-exceeded"),
        _value(available, unit, available_ref),
        _value(consumption, unit, consumption_ref),
    )


def _boolean(request: ConstraintEvaluationRequest, required_field: str, fact_field: str) -> tuple[str, str, ConstraintValue | None, ConstraintValue | None]:
    required, required_ref = _required(request, required_field)
    available, available_ref = _fact(request, fact_field)
    if not required:
        return "N_A", "requirement-not-applicable", None, _value(available, None, available_ref)
    if available is None:
        return "UNKNOWN", "candidate-fact-missing", _value(True, None, required_ref), None
    return ("PASS" if available else "FAIL"), ("requirement-satisfied" if available else "capability-not-supported"), _value(True, None, required_ref), _value(available, None, available_ref)


def _evaluate(rule: ConstraintRule, request: ConstraintEvaluationRequest) -> tuple[str, str, ConstraintValue | None, ConstraintValue | None]:
    evaluator = rule.evaluator
    if evaluator == "object-kind":
        available, ref = _fact(request, "supported_object_kinds")
        if available is None:
            return "UNKNOWN", "candidate-fact-missing", _value(request.context.object_kind, None, "request:object_kind"), None
        passed = request.context.object_kind in available
        return ("PASS" if passed else "FAIL"), ("object-kind-supported" if passed else "object-kind-unsupported"), _value(request.context.object_kind, None, "request:object_kind"), _value(available, None, ref)
    if evaluator == "process-scope":
        available, ref = _fact(request, "supported_process_scopes")
        if available is None:
            return "UNKNOWN", "candidate-fact-missing", _value(request.process_scope, None, "request:process_scope"), None
        passed = request.process_scope in available
        return ("PASS" if passed else "FAIL"), ("process-scope-supported" if passed else "process-scope-unsupported"), _value(request.process_scope, None, "request:process_scope"), _value(available, None, ref)
    if evaluator == "cargo":
        required, required_ref = _required(request, "required_cargo_kind")
        if required is None:
            return "N_A", "cargo-kind-not-required", None, None
        available, available_ref = _fact(request, "supported_cargo_kinds")
        if available is None:
            return "UNKNOWN", "cargo-compatibility-unknown", _value(required, None, required_ref), None
        passed = required in available
        return ("PASS" if passed else "FAIL"), ("cargo-supported" if passed else "cargo-unsupported"), _value(required, None, required_ref), _value(available, None, available_ref)
    if evaluator == "payload":
        return _compare_max(request, "max_payload_kg", "payload_kg", "kg")
    if evaluator == "aisle":
        return _compare_min(request, "min_aisle_width_m", "min_aisle_width_m", "m")
    if evaluator == "lift-height":
        return _compare_max(request, "required_lift_height_m", "max_lift_height_m", "m")
    if evaluator == "ceiling-clearance":
        lift, lift_ref = _required(request, "required_lift_height_m")
        ceiling, ceiling_ref = _required(request, "ceiling_height_m")
        if lift is None:
            return "N_A", "lift-clearance-not-required", None, None
        required = _decimal(lift) + Decimal(1)
        if ceiling is None:
            return "UNKNOWN", "ceiling-height-unknown", _value(format(required, "f"), "m", lift_ref), None
        passed = _decimal(ceiling) >= required
        return ("PASS" if passed else "FAIL"), ("ceiling-clearance-satisfied" if passed else "ceiling-clearance-insufficient"), _value(format(required, "f"), "m", lift_ref), _value(ceiling, "m", ceiling_ref)
    if evaluator == "route-floors":
        floors, floors_ref = _required(request, "route_floors")
        if len(set(floors)) <= 1:
            return "N_A", "single-floor-route", None, None
        protocols, protocols_ref = _fact(request, "lift_protocols")
        if protocols is None:
            return "UNKNOWN", "lift-integration-unknown", _value(floors, None, floors_ref), None
        passed = bool(protocols)
        return ("PASS" if passed else "FAIL"), ("lift-route-supported" if passed else "lift-route-unsupported"), _value(floors, None, floors_ref), _value(protocols, None, protocols_ref)
    if evaluator == "temperature":
        low, low_ref = _required(request, "temperature_min_c")
        high, high_ref = _required(request, "temperature_max_c")
        if low is None and high is None:
            return "N_A", "temperature-not-required", None, None
        fact_low, fact_low_ref = _fact(request, "temperature_min_c")
        fact_high, fact_high_ref = _fact(request, "temperature_max_c")
        if fact_low is None or fact_high is None:
            return "UNKNOWN", "temperature-range-unknown", _value([low, high], "degC", low_ref or high_ref), None
        passed = (low is None or _decimal(fact_low) <= _decimal(low)) and (high is None or _decimal(fact_high) >= _decimal(high))
        return ("PASS" if passed else "FAIL"), ("temperature-range-supported" if passed else "temperature-range-exceeded"), _value([low, high], "degC", low_ref or high_ref), _value([fact_low, fact_high], "degC", fact_low_ref or fact_high_ref)
    if evaluator == "noise":
        limit, limit_ref = _required(request, "max_noise_dba")
        if limit is None:
            return "N_A", "noise-not-required", None, None
        noise, noise_ref = _fact(request, "noise_dba")
        times, times_ref = _fact(request, "allowed_time_scopes")
        zones, zones_ref = _fact(request, "allowed_zones")
        if noise is None or times is None or zones is None:
            return "UNKNOWN", "scoped-noise-facts-unknown", _value(limit, "dBA", limit_ref), None
        time_ok = "ANY" in times or request.context.time_scope == "ANY" or request.context.time_scope in times
        zone_ok = not request.context.route_zones or all(zone in zones for zone in request.context.route_zones)
        passed = _decimal(noise) <= _decimal(limit) and time_ok and zone_ok
        return ("PASS" if passed else "FAIL"), ("scoped-noise-supported" if passed else "scoped-noise-exceeded"), _value({"limit": limit, "time": request.context.time_scope, "zones": request.context.route_zones}, "dBA", limit_ref), _value({"noise": noise, "times": times, "zones": zones}, "dBA", noise_ref or times_ref or zones_ref)
    if evaluator == "airside":
        return _boolean(request, "airside_required", "airside_operational_permission")
    if evaluator == "apron":
        return _boolean(request, "apron_required", "apron_operational_permission")
    if evaluator == "restricted-zone":
        return _boolean(request, "restricted_zone_required", "restricted_zone_access_supported")
    if evaluator == "sanitization":
        return _boolean(request, "sanitization_required", "sterilization_supported")
    if evaluator == "class-b-containment":
        return _boolean(request, "class_b_containment_required", "class_b_containment_supported")
    if evaluator == "cleanable-surface":
        required = request.context.sanitization_required or request.context.class_b_containment_required
        if not required:
            return "N_A", "cleanable-surface-not-required", None, None
        return _boolean(request, "sanitization_required" if request.context.sanitization_required else "class_b_containment_required", "cleanable_surface")
    if evaluator == "material-disinfection":
        if not request.context.sanitization_required:
            return "N_A", "material-disinfection-not-required", None, None
        return _boolean(request, "sanitization_required", "material_disinfection_supported")
    if evaluator == "access-protocols":
        required, required_ref = _required(request, "required_access_protocols")
        if not required:
            return "N_A", "access-protocols-not-required", None, None
        available, available_ref = _fact(request, "supported_access_protocols")
        if available is None:
            return "UNKNOWN", "access-protocols-unknown", _value(required, None, required_ref), None
        passed = set(required).issubset(available)
        return ("PASS" if passed else "FAIL"), ("access-protocols-supported" if passed else "access-protocols-unsupported"), _value(required, None, required_ref), _value(available, None, available_ref)
    if evaluator == "passport-availability":
        available, available_ref = _fact(request, "technical_passport_available")
        if available is None:
            return "UNKNOWN", "technical-passport-unknown", _value(True, None, "policy:K15"), None
        return ("PASS" if available else "FAIL"), ("technical-passport-available" if available else "technical-passport-unavailable"), _value(True, None, "policy:K15"), _value(available, None, available_ref)
    if evaluator == "floor-flatness":
        return _compare_max(request, "floor_flatness_mm_2m", "floor_flatness_tolerance_mm_2m", "mm/2m")
    if evaluator == "floor-covering":
        required, required_ref = _required(request, "floor_covering")
        if required is None:
            return "N_A", "floor-covering-not-required", None, None
        available, available_ref = _fact(request, "supported_floor_coverings")
        if available is None:
            return "UNKNOWN", "floor-covering-fact-unknown", _value(required, None, required_ref), None
        passed = required in available
        return ("PASS" if passed else "FAIL"), ("floor-covering-supported" if passed else "floor-covering-unsupported"), _value(required, None, required_ref), _value(available, None, available_ref)
    if evaluator == "slope":
        return _compare_max(request, "max_slope_percent", "max_slope_percent", "%")
    if evaluator == "outdoor":
        return _boolean(request, "outdoor_required", "outdoor_supported")
    if evaluator == "availability":
        available, ref = _fact(request, "availability")
        if available is None:
            return "UNKNOWN", "availability-fact-unknown", _value("0.4", "1", "policy:K15"), None
        passed = _decimal(available) >= Decimal("0.4")
        return ("PASS" if passed else "FAIL"), ("availability-supported" if passed else "availability-below-minimum"), _value("0.4", "1", "policy:K15"), _value(available, "1", ref)
    if evaluator == "integrations":
        required, required_ref = _required(request, "required_integrations")
        if not required:
            return "N_A", "integrations-not-required", None, None
        available, available_ref = _fact(request, "supported_integrations")
        if available is None:
            return "UNKNOWN", "integration-facts-unknown", _value(required, None, required_ref), None
        missing = sorted(set(required) - set(available))
        status = "PASS" if not missing else "UNKNOWN"
        return status, ("integrations-supported" if not missing else "integrations-need-review"), _value(required, None, required_ref), _value(available, None, available_ref)
    if evaluator == "life-warning":
        horizon, horizon_ref = _required(request, "horizon_years")
        if horizon is None:
            return "N_A", "horizon-not-provided", None, None
        life, life_ref = _fact(request, "expected_life_years")
        if life is None:
            return "UNKNOWN", "life-fact-unknown", _value(horizon, "year", horizon_ref), None
        passed = _decimal(life) >= Decimal(horizon)
        return ("PASS" if passed else "FAIL"), ("life-covers-horizon" if passed else "life-shorter-than-horizon"), _value(horizon, "year", horizon_ref), _value(life, "year", life_ref)
    if evaluator == "budget-warning":
        return _compare_consumption(request, "budget_rub", "capex_rub", "RUB")
    if evaluator == "charging-warning":
        return _compare_consumption(request, "available_charging_power_kw", "charging_power_kw", "kW")
    if evaluator == "density-warning":
        area, area_ref = _required(request, "active_area_m2")
        fleet, fleet_ref = _required(request, "fleet_units")
        if area is None or not fleet:
            return "N_A", "density-inputs-not-available", None, None
        density = _decimal(area) / Decimal(fleet)
        passed = density >= Decimal(30)
        return ("PASS" if passed else "FAIL"), ("density-warning-not-triggered" if passed else "density-below-review-threshold"), _value("30", "m2/robot", "reference-v2:ZV2-14"), _value(format(density, "f"), "m2/robot", area_ref or fleet_ref)
    raise ValueError(f"unknown evaluator {evaluator}")


def evaluate_constraints(request: ConstraintEvaluationRequest, rules: ConstraintRules | None = None) -> ConstraintReportV2:
    rules = rules or load_constraint_rules()
    checks: list[ConstraintCheck] = []
    scope = {
        "process_code": request.process_code,
        "process_scope": request.process_scope,
        "route_zones": request.context.route_zones,
        "route_floors": request.context.route_floors,
        "time_scope": request.context.time_scope,
    }
    for rule in rules.rules:
        status, reason, required, available = _evaluate(rule, request)
        if status == "PASS" and required is not None and any(
            source.kind == "ASSUMPTION" and source.source_ref == required.source_ref
            for source in request.context.requirement_sources.values()
        ):
            status, reason = "ASSUMED", "requirement-source-assumed"
        source_refs = list(rule.source_refs)
        if required is not None:
            source_refs.append(required.source_ref)
        if available is not None:
            source_refs.append(available.source_ref)
        checks.append(ConstraintCheck(
            check_id=rule.rule_id, rule_version=rule.version,
            applicable=status != "N_A", severity=rule.severity, status=status,
            reason_code=reason, scope=scope, required=required, available=available,
            source_refs=list(dict.fromkeys(source_refs)), decision_refs=rule.decision_refs,
            localization_key=rule.localization_key,
        ))
    blockers = [item.check_id for item in checks if item.severity == "CRITICAL" and item.status == "FAIL"]
    validation = [item.check_id for item in checks if item.severity == "CRITICAL" and item.status in {"UNKNOWN", "ASSUMED"}]
    warnings = [item.check_id for item in checks if item.severity in {"WARNING", "ADVISORY"} and item.status in {"FAIL", "UNKNOWN", "ASSUMED"}]
    eligibility = "BLOCKED" if blockers else "NEEDS_VALIDATION" if validation else "ELIGIBLE"
    return ConstraintReportV2(
        input_revision=request.input_revision, process_id=request.process_id,
        model_id=request.candidate.model_id, position_id=request.candidate.position_id,
        eligibility=eligibility, checks=checks, blocker_codes=blockers,
        validation_codes=validation, warning_codes=warnings,
    )
