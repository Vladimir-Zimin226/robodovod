"""Formula dependency closure and run executability contracts for C06.

The resolver never executes a formula and never reads commercial Robot fields.
It distinguishes catalog-level dependency closure from a concrete run, which
also needs normalized scenario values and an eligible C05 constraint report.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from calculation_contracts import DecimalString, StableId, StrictContractModel
from pydantic import Field, model_validator

if TYPE_CHECKING:
    from catalog_repository import FormulaExecutabilityCatalogDTO

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILES_PATH = ROOT / "data" / "calculation" / "formula-executability-profiles-v3.json"


class NumericDomain(StrictContractModel):
    numeric: bool = True
    minimum: DecimalString | None = None
    exclusive_minimum: bool = False
    maximum: DecimalString | None = None


class CatalogFactRequirement(StrictContractModel):
    requirement_id: StableId
    field_path: str = Field(pattern=r"^(specs|capacity)\.")
    expected_units: list[str] = Field(min_length=1)
    domain: NumericDomain
    formula_ids: list[str] = Field(min_length=1)


class ScenarioRequirement(StrictContractModel):
    requirement_id: StableId
    input_path: str = Field(min_length=1)
    expected_units: list[str] = Field(min_length=1)
    domain: NumericDomain
    required: bool
    formula_ids: list[str] = Field(min_length=1)


class PolicyRequirement(StrictContractModel):
    requirement_id: StableId
    parameter_ids: list[StableId] = Field(min_length=1)
    expected_unit: str = Field(min_length=1)
    formula_ids: list[str] = Field(min_length=1)


class FormulaDependency(StrictContractModel):
    formula_id: str = Field(pattern=r"^F0[1-7]$")
    output_id: StableId
    input_ids: list[StableId] = Field(min_length=1)


class ExecutabilityProfile(StrictContractModel):
    profile_id: str = Field(min_length=1)
    equipment_class: str = Field(min_length=1)
    process_scopes: list[str] = Field(min_length=1)
    catalog_facts: list[CatalogFactRequirement]
    scenario_inputs: list[ScenarioRequirement]
    policy_inputs: list[PolicyRequirement]
    formulas: list[FormulaDependency] = Field(min_length=1)

    @model_validator(mode="after")
    def dependency_closure(self) -> ExecutabilityProfile:
        collections = (self.catalog_facts, self.scenario_inputs, self.policy_inputs)
        root_ids = [item.requirement_id for values in collections for item in values]
        if len(root_ids) != len(set(root_ids)):
            raise ValueError(f"duplicate dependency id in {self.profile_id}")
        if any(values != sorted(values, key=lambda item: item.requirement_id) for values in collections):
            raise ValueError(f"dependency inputs must be sorted in {self.profile_id}")
        known = set(root_ids)
        formula_ids: list[str] = []
        for formula in self.formulas:
            if not set(formula.input_ids) <= known:
                raise ValueError(f"formula dependency is unresolved in {self.profile_id}:{formula.formula_id}")
            if formula.output_id in known:
                raise ValueError(f"duplicate formula output in {self.profile_id}")
            known.add(formula.output_id)
            formula_ids.append(formula.formula_id)
        if formula_ids != sorted(formula_ids) or len(formula_ids) != len(set(formula_ids)):
            raise ValueError(f"formula ids must be unique and ordered in {self.profile_id}")
        declared = {
            formula_id
            for values in collections
            for item in values
            for formula_id in item.formula_ids
        }
        if not declared <= set(formula_ids):
            raise ValueError(f"input refers to an absent formula in {self.profile_id}")
        by_formula = {item.formula_id: item for item in self.formulas}
        for values in collections:
            for item in values:
                if any(item.requirement_id not in by_formula[formula_id].input_ids for formula_id in item.formula_ids):
                    raise ValueError(f"declared formula does not consume input in {self.profile_id}:{item.requirement_id}")
        return self


class ExecutabilityProfilesV3(StrictContractModel):
    schema_version: Literal["formula-executability-profiles-v3"]
    profiles_version: Literal["formula-executability-profiles-v3"]
    policy_version: Literal["hackathon-calculation-policy-v1"]
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    constraint_rules_version: Literal["calculation-constraint-rules-v2"]
    profiles: list[ExecutabilityProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_profiles(self) -> ExecutabilityProfilesV3:
        ids = [item.profile_id for item in self.profiles]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("profiles must be unique and ordered")
        return self


class FactBinding(StrictContractModel):
    field_path: str
    value: Any = None
    unit: str | None = None
    evidence_status: Literal[
        "MATCHING_SAFE", "CONFLICT", "AMBIGUOUS_MODEL_MATCH", "NOT_FOUND", "UNKNOWN"
    ]
    source_refs: list[str] = Field(default_factory=list)


class CatalogCandidateInput(StrictContractModel):
    model_id: str = Field(min_length=1)
    position_id: str | None = None
    name: str = Field(min_length=1)
    system_family: str | None = None
    identity_status: Literal["MATCHED", "UNKNOWN", "AMBIGUOUS_MODEL_MATCH"]
    profile_id: str | None = None
    readiness_v2_status: str = Field(min_length=1)
    facts: list[FactBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_facts(self) -> CatalogCandidateInput:
        fields = [item.field_path for item in self.facts]
        if fields != sorted(fields) or len(fields) != len(set(fields)):
            raise ValueError("candidate facts must be unique and ordered")
        return self


class ScenarioValue(StrictContractModel):
    input_path: str = Field(min_length=1)
    value: Any
    unit: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)


class DependencyResolution(StrictContractModel):
    requirement_id: StableId
    source_kind: Literal["CATALOG_FACT", "SCENARIO_INPUT", "POLICY_PARAMETER"]
    status: Literal[
        "RESOLVED_SAFE_FACT",
        "REQUIRED_SCENARIO_INPUT",
        "OPTIONAL_SCENARIO_INPUT",
        "RESOLVED_SCENARIO_INPUT",
        "RESOLVED_POLICY",
        "MISSING_SAFE_FACT",
        "INVALID_UNIT",
        "INVALID_DOMAIN",
        "MISSING_SCENARIO_INPUT",
        "MISSING_POLICY_PARAMETER",
    ]
    field_or_path: str
    value: Any = None
    unit: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    formula_ids: list[str] = Field(min_length=1)
    reason_code: StableId


class ExecutabilityAssumption(StrictContractModel):
    assumption_id: StableId
    permitted_scope: str = Field(min_length=1)
    formula_ids: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    vendor_fact: Literal[False] = False


class CatalogExecutabilityResult(StrictContractModel):
    schema_version: Literal["catalog-formula-executability-result-v3"] = "catalog-formula-executability-result-v3"
    model_id: str
    position_id: str | None
    profile_id: str | None
    catalog_status: Literal[
        "CATALOG_EXECUTABLE", "MISSING_SAFE_FACT", "INVALID_FACT", "UNKNOWN_IDENTITY", "UNSUPPORTED_PROFILE", "NOT_EQUIPMENT"
    ]
    run_executability: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    formula_ids: list[str]
    available_facts: list[DependencyResolution]
    required_scenario_inputs: list[DependencyResolution]
    policy_bindings: list[DependencyResolution]
    assumptions: list[ExecutabilityAssumption]
    blockers: list[StableId]
    unsupported_reason: str | None = None


class RunExecutabilityResult(StrictContractModel):
    schema_version: Literal["formula-run-executability-v3"] = "formula-run-executability-v3"
    model_id: str
    position_id: str | None
    profile_id: str | None
    status: Literal["EXECUTABLE", "PRELIMINARY_EXECUTABLE", "MISSING_INPUT", "NEEDS_VALIDATION", "BLOCKED", "UNSUPPORTED_PROFILE"]
    dependencies: list[DependencyResolution]
    blocker_codes: list[StableId]


class ExecutabilityAuditItemV3(StrictContractModel):
    id: str
    model_id: str
    name: str
    source_row_number: int | None
    system_family: str | None
    result: CatalogExecutabilityResult


class ExecutabilityPoolDiffV3(StrictContractModel):
    schema_version: Literal["catalog-formula-executability-pool-diff-v3"] = "catalog-formula-executability-pool-diff-v3"
    baseline_contract_version: Literal["runtime-calculation-readiness-contract-v2"]
    candidate_contract_version: Literal["formula-executability-profiles-v3"]
    baseline_model_ids: list[str]
    candidate_model_ids: list[str]
    added_model_ids: list[str]
    removed_model_ids: list[str]
    baseline_position_ids: list[str]
    candidate_position_ids: list[str]
    added_position_ids: list[str]
    removed_position_ids: list[str]

    @model_validator(mode="after")
    def fixed_membership(self) -> ExecutabilityPoolDiffV3:
        ordered = (
            self.baseline_model_ids, self.candidate_model_ids,
            self.baseline_position_ids, self.candidate_position_ids,
        )
        if any(values != sorted(values) or len(values) != len(set(values)) for values in ordered):
            raise ValueError("pool identity sets must be unique and ordered")
        if len(self.baseline_model_ids) != 21 or len(self.baseline_position_ids) != 24:
            raise ValueError("C06 baseline membership must remain 21/24")
        if self.added_model_ids or self.removed_model_ids or self.added_position_ids or self.removed_position_ids:
            raise ValueError("C06 must not change pool membership")
        if self.baseline_model_ids != self.candidate_model_ids or self.baseline_position_ids != self.candidate_position_ids:
            raise ValueError("candidate pool differs from v2 baseline")
        return self


class AuditInvariantsV3(StrictContractModel):
    formulas_executed: Literal[False]
    economics_required: Literal[False]
    robot_cost_fields_read: Literal[False]
    runtime_activation_changed: Literal[False]
    pool_membership_changed: Literal[False]
    bas_in_candidate_pool: Literal[False]


class FormulaExecutabilityAuditV3(StrictContractModel):
    schema_version: Literal["catalog-formula-executability-audit-v3"] = "catalog-formula-executability-audit-v3"
    profiles_version: Literal["formula-executability-profiles-v3"]
    readiness_contract_version: Literal["runtime-calculation-readiness-contract-v2"]
    catalog_code: Literal["organizer-catalog-v4"]
    deterministic_order: Literal["models:model_id;positions:source_row_number"]
    inputs_sha256: dict[str, str]
    counts: dict[str, int]
    model_status_counts: dict[str, int]
    position_status_counts: dict[str, int]
    invariants: AuditInvariantsV3
    pool_diff: ExecutabilityPoolDiffV3
    models: list[ExecutabilityAuditItemV3]
    positions: list[ExecutabilityAuditItemV3]

    @model_validator(mode="after")
    def exact_coverage(self) -> FormulaExecutabilityAuditV3:
        if self.counts.get("models") != 187 or self.counts.get("positions") != 223:
            raise ValueError("v3 audit must cover exactly 187/223")
        if len(self.models) != 187 or len(self.positions) != 223:
            raise ValueError("v3 audit item coverage differs")
        if [item.model_id for item in self.models] != sorted(item.model_id for item in self.models):
            raise ValueError("v3 model ordering differs")
        if [item.source_row_number for item in self.positions] != list(range(2, 225)):
            raise ValueError("v3 position ordering differs")
        if sum(self.model_status_counts.values()) != 187 or sum(self.position_status_counts.values()) != 223:
            raise ValueError("v3 status counts differ")
        return self


@lru_cache(maxsize=4)
def load_executability_profiles(path_text: str | None = None) -> ExecutabilityProfilesV3:
    path = Path(path_text) if path_text else DEFAULT_PROFILES_PATH
    return ExecutabilityProfilesV3.model_validate_json(path.read_text(encoding="utf-8"))


def _numeric_status(value: Any, domain: NumericDomain) -> Literal["OK", "INVALID_DOMAIN"]:
    if not domain.numeric:
        return "OK"
    if isinstance(value, bool):
        return "INVALID_DOMAIN"
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "INVALID_DOMAIN"
    if not number.is_finite():
        return "INVALID_DOMAIN"
    if domain.minimum is not None:
        minimum = Decimal(domain.minimum)
        if number < minimum or (domain.exclusive_minimum and number == minimum):
            return "INVALID_DOMAIN"
    if domain.maximum is not None and number > Decimal(domain.maximum):
        return "INVALID_DOMAIN"
    return "OK"


def _normalize_catalog_value(
    value: Any, unit: str | None, expected_units: list[str]
) -> tuple[Any, str | None, list[str]]:
    """Return a conservative scalar in a declared canonical unit.

    Ranges are not averaged: the minimum verified performance/capability is the
    safe capacity input. Only exact unit conversions admitted by C01 are used.
    """

    traces: list[str] = []
    if isinstance(value, dict) and "min" in value:
        value = value["min"]
        traces.append("normalization:conservative-range-minimum")
    elif isinstance(value, list) and value and all(
        not isinstance(item, bool) and isinstance(item, (int, float, Decimal))
        for item in value
    ):
        value = min(value)
        traces.append("normalization:conservative-range-minimum")
    normalized_unit = unit.replace("²", "2") if isinstance(unit, str) else unit
    if normalized_unit in expected_units:
        return value, normalized_unit, traces
    conversions = {
        ("km/h", "m/s"): (Decimal(1) / Decimal("3.6"), "kmh-to-mps"),
        ("t", "kg"): (Decimal(1000), "tonne-to-kg"),
    }
    for target in expected_units:
        conversion = conversions.get((normalized_unit, target))
        if conversion is None:
            continue
        try:
            converted = Decimal(str(value)) * conversion[0]
        except (InvalidOperation, ValueError):
            return value, normalized_unit, traces
        return format(converted.normalize(), "f"), target, [*traces, f"unit-conversion:{conversion[1]}"]
    return value, normalized_unit, traces


def _fact_resolution(requirement: CatalogFactRequirement, fact: FactBinding | None) -> DependencyResolution:
    base = {
        "requirement_id": requirement.requirement_id,
        "source_kind": "CATALOG_FACT",
        "field_or_path": requirement.field_path,
        "formula_ids": requirement.formula_ids,
    }
    if fact is None or fact.evidence_status != "MATCHING_SAFE" or fact.value is None:
        return DependencyResolution(**base, status="MISSING_SAFE_FACT", source_refs=fact.source_refs if fact else [], reason_code="missing-safe-fact")
    value, unit, normalization_refs = _normalize_catalog_value(
        fact.value, fact.unit, requirement.expected_units
    )
    source_refs = [*fact.source_refs, *normalization_refs]
    if unit not in requirement.expected_units:
        return DependencyResolution(**base, status="INVALID_UNIT", value=value, unit=unit, source_refs=source_refs, reason_code="catalog-fact-unit-invalid")
    if _numeric_status(value, requirement.domain) != "OK":
        return DependencyResolution(**base, status="INVALID_DOMAIN", value=value, unit=unit, source_refs=source_refs, reason_code="catalog-fact-domain-invalid")
    return DependencyResolution(**base, status="RESOLVED_SAFE_FACT", value=value, unit=unit, source_refs=source_refs, reason_code="catalog-fact-resolved")


def _policy_resolutions(profile: ExecutabilityProfile, registry: dict[str, Any]) -> list[DependencyResolution]:
    by_id = {item["parameter_id"]: item for item in registry.get("parameters", [])}
    result = []
    for requirement in profile.policy_inputs:
        values = [by_id.get(parameter_id) for parameter_id in requirement.parameter_ids]
        missing = [parameter_id for parameter_id, value in zip(requirement.parameter_ids, values, strict=True) if value is None or value.get("unit") != requirement.expected_unit]
        if missing:
            result.append(DependencyResolution(
                requirement_id=requirement.requirement_id, source_kind="POLICY_PARAMETER",
                status="MISSING_POLICY_PARAMETER", field_or_path=",".join(requirement.parameter_ids),
                source_refs=[f"registry:{item}" for item in requirement.parameter_ids],
                formula_ids=requirement.formula_ids, reason_code="policy-parameter-missing",
            ))
        else:
            result.append(DependencyResolution(
                requirement_id=requirement.requirement_id, source_kind="POLICY_PARAMETER",
                status="RESOLVED_POLICY", field_or_path=",".join(requirement.parameter_ids),
                value=[value["value"] for value in values], unit=requirement.expected_unit,
                source_refs=[f"registry:{item}" for item in requirement.parameter_ids],
                formula_ids=requirement.formula_ids, reason_code="policy-parameter-resolved",
            ))
    return result


def audit_catalog_candidate(
    candidate: CatalogCandidateInput,
    registry: dict[str, Any],
    profiles: ExecutabilityProfilesV3 | None = None,
) -> CatalogExecutabilityResult:
    profiles = profiles or load_executability_profiles()
    profile = next((item for item in profiles.profiles if item.profile_id == candidate.profile_id), None)
    if candidate.identity_status != "MATCHED":
        status, reason = "UNKNOWN_IDENTITY", "identity-not-matched"
    elif candidate.readiness_v2_status == "NOT_EQUIPMENT":
        status, reason = "NOT_EQUIPMENT", "readiness-v2:not-equipment"
    elif profile is None:
        status, reason = "UNSUPPORTED_PROFILE", "profile-not-supported-by-formula-bundle"
    else:
        status, reason = "CATALOG_EXECUTABLE", None
    if profile is None or status == "UNKNOWN_IDENTITY":
        return CatalogExecutabilityResult(
            model_id=candidate.model_id, position_id=candidate.position_id,
            profile_id=candidate.profile_id, catalog_status=status, formula_ids=[],
            available_facts=[], required_scenario_inputs=[], policy_bindings=[],
            assumptions=[], blockers=["unknown-identity"] if status == "UNKNOWN_IDENTITY" else [], unsupported_reason=reason,
        )
    facts = {item.field_path: item for item in candidate.facts}
    fact_resolutions = [_fact_resolution(item, facts.get(item.field_path)) for item in profile.catalog_facts]
    scenario = [DependencyResolution(
        requirement_id=item.requirement_id, source_kind="SCENARIO_INPUT",
        status="REQUIRED_SCENARIO_INPUT" if item.required else "OPTIONAL_SCENARIO_INPUT",
        field_or_path=item.input_path, unit=item.expected_units[0], source_refs=["normalized-intake-v2"],
        formula_ids=item.formula_ids, reason_code="scenario-input-required" if item.required else "scenario-input-optional",
    ) for item in profile.scenario_inputs]
    policy = _policy_resolutions(profile, registry)
    invalid = [item for item in fact_resolutions if item.status in {"INVALID_UNIT", "INVALID_DOMAIN"}]
    missing = [item for item in fact_resolutions if item.status == "MISSING_SAFE_FACT"]
    policy_missing = [item for item in policy if item.status == "MISSING_POLICY_PARAMETER"]
    blockers = [item.requirement_id for item in [*invalid, *missing, *policy_missing]]
    if invalid:
        status = "INVALID_FACT"
    elif missing or policy_missing:
        status = "MISSING_SAFE_FACT"
    return CatalogExecutabilityResult(
        model_id=candidate.model_id, position_id=candidate.position_id,
        profile_id=profile.profile_id, catalog_status=status,
        formula_ids=[item.formula_id for item in profile.formulas],
        available_facts=fact_resolutions, required_scenario_inputs=scenario,
        policy_bindings=policy,
        assumptions=[ExecutabilityAssumption(
            assumption_id=f"assumption.{item.requirement_id}",
            permitted_scope=profile.profile_id,
            formula_ids=item.formula_ids,
            source_refs=item.source_refs,
        ) for item in policy if item.status == "RESOLVED_POLICY"],
        blockers=blockers, unsupported_reason=reason,
    )


def evaluate_run_executability(
    candidate: CatalogCandidateInput,
    scenario_values: list[ScenarioValue],
    constraint_eligibility: Literal["ELIGIBLE", "NEEDS_VALIDATION", "BLOCKED"],
    registry: dict[str, Any],
    profiles: ExecutabilityProfilesV3 | None = None,
    *, allow_preliminary: bool = False,
) -> RunExecutabilityResult:
    profiles = profiles or load_executability_profiles()
    catalog = audit_catalog_candidate(candidate, registry, profiles)
    if catalog.catalog_status in {"UNSUPPORTED_PROFILE", "NOT_EQUIPMENT"}:
        return RunExecutabilityResult(model_id=candidate.model_id, position_id=candidate.position_id, profile_id=candidate.profile_id, status="UNSUPPORTED_PROFILE", dependencies=[], blocker_codes=["unsupported-profile"])
    dependencies = [*catalog.available_facts, *catalog.policy_bindings]
    if catalog.catalog_status != "CATALOG_EXECUTABLE":
        return RunExecutabilityResult(model_id=candidate.model_id, position_id=candidate.position_id, profile_id=candidate.profile_id, status="BLOCKED", dependencies=dependencies, blocker_codes=catalog.blockers)
    profile = next(item for item in profiles.profiles if item.profile_id == candidate.profile_id)
    paths = [item.input_path for item in scenario_values]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate scenario input path")
    allowed_paths = {item.input_path for item in profile.scenario_inputs}
    if not set(paths) <= allowed_paths:
        raise ValueError("scenario input is not declared by the profile")
    provided = {item.input_path: item for item in scenario_values}
    scenario_resolutions = []
    for requirement in profile.scenario_inputs:
        value = provided.get(requirement.input_path)
        base = {
            "requirement_id": requirement.requirement_id, "source_kind": "SCENARIO_INPUT",
            "field_or_path": requirement.input_path, "formula_ids": requirement.formula_ids,
        }
        if value is None:
            status = "MISSING_SCENARIO_INPUT" if requirement.required else "OPTIONAL_SCENARIO_INPUT"
            scenario_resolutions.append(DependencyResolution(**base, status=status, unit=requirement.expected_units[0], reason_code="scenario-input-missing" if requirement.required else "scenario-input-optional"))
        elif value.unit not in requirement.expected_units:
            scenario_resolutions.append(DependencyResolution(**base, status="INVALID_UNIT", value=value.value, unit=value.unit, source_refs=[value.source_ref], reason_code="scenario-input-unit-invalid"))
        elif _numeric_status(value.value, requirement.domain) != "OK":
            scenario_resolutions.append(DependencyResolution(**base, status="INVALID_DOMAIN", value=value.value, unit=value.unit, source_refs=[value.source_ref], reason_code="scenario-input-domain-invalid"))
        else:
            scenario_resolutions.append(DependencyResolution(**base, status="RESOLVED_SCENARIO_INPUT", value=value.value, unit=value.unit, source_refs=[value.source_ref], reason_code="scenario-input-resolved"))
    shifts = provided.get("process.shifts_per_day")
    hours = provided.get("process.shift_hours")
    if shifts is not None and hours is not None:
        try:
            operating_hours = Decimal(str(shifts.value)) * Decimal(str(hours.value))
        except (InvalidOperation, ValueError):
            operating_hours = Decimal("NaN")
        if not operating_hours.is_finite() or operating_hours > Decimal(24):
            scenario_resolutions.append(DependencyResolution(
                requirement_id="input.operating-hours", source_kind="SCENARIO_INPUT",
                status="INVALID_DOMAIN", field_or_path="process.shifts_per_day*process.shift_hours",
                value=format(operating_hours, "f") if operating_hours.is_finite() else None,
                unit="h/day", source_refs=[shifts.source_ref, hours.source_ref],
                formula_ids=["F01"], reason_code="operating-hours-exceed-day",
            ))
    dependencies.extend(scenario_resolutions)
    blockers = [item.requirement_id for item in scenario_resolutions if item.status in {"MISSING_SCENARIO_INPUT", "INVALID_UNIT", "INVALID_DOMAIN"}]
    if constraint_eligibility == "BLOCKED":
        return RunExecutabilityResult(model_id=candidate.model_id, position_id=candidate.position_id, profile_id=candidate.profile_id, status="BLOCKED", dependencies=dependencies, blocker_codes=["constraint-report-blocked"])
    if constraint_eligibility == "NEEDS_VALIDATION":
        return RunExecutabilityResult(model_id=candidate.model_id, position_id=candidate.position_id, profile_id=candidate.profile_id, status="PRELIMINARY_EXECUTABLE" if allow_preliminary and not blockers else "NEEDS_VALIDATION", dependencies=dependencies, blocker_codes=["constraint-report-needs-validation", *blockers])
    return RunExecutabilityResult(model_id=candidate.model_id, position_id=candidate.position_id, profile_id=candidate.profile_id, status="MISSING_INPUT" if blockers else "EXECUTABLE", dependencies=dependencies, blocker_codes=blockers)


def registry_payload(path: Path | None = None) -> dict[str, Any]:
    value = json.loads((path or ROOT / "data" / "calculation" / "registry-v1.json").read_text(encoding="utf-8"))
    if value.get("registry_version") != "hackathon-calculation-parameter-registry-v1":
        raise ValueError("unsupported calculation registry version")
    return value


def candidate_from_repository(
    projection: FormulaExecutabilityCatalogDTO,
) -> CatalogCandidateInput:
    """Adapt the evidence-gated repository DTO without Robot or cost fields."""

    path_by_code = {
        field.rsplit(".", 1)[-1]: field
        for field in projection.calculation_model_fields
    }
    facts = []
    for fact in projection.vendor_facts:
        field_path = path_by_code.get(fact.code)
        if field_path is None:
            continue
        facts.append({
            "field_path": field_path,
            "value": fact.value,
            "unit": fact.canonical_unit,
            "evidence_status": "MATCHING_SAFE",
            "source_refs": [f"catalog-evidence:{fact.evidence_id}"],
        })
    return CatalogCandidateInput.model_validate({
        "model_id": projection.model_id,
        "position_id": projection.position_id,
        "name": projection.name,
        "system_family": projection.system_family,
        "identity_status": "MATCHED",
        "profile_id": projection.profile_id,
        "readiness_v2_status": projection.readiness_v2_status,
        "facts": sorted(facts, key=lambda item: item["field_path"]),
    })
