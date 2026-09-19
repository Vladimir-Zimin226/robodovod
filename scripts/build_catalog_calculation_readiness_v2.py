"""Build the split calculation/deployment readiness audit without activation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scripts.build_catalog_official_source_staging import (
    ROOT,
    STAGING,
    build_staging,
    project_eligibility,
    schema_bytes,
)

CONTRACT = ROOT / "contracts" / "runtime-calculation-readiness-contract-v2.json"
CONTRACT_SCHEMA = ROOT / "contracts" / "runtime-calculation-readiness-contract-v2.schema.json"
REPORT_SCHEMA = ROOT / "contracts" / "catalog-calculation-readiness-audit-v2.schema.json"
LOCAL_ADAPTER = (
    ROOT
    / "data"
    / "enrichment"
    / "catalog-official-source-enrichment-v1"
    / "local-adapter-overlay-v1.json"
)
BASE_EVIDENCE = (
    ROOT / "data" / "import" / "organizer-catalog-v4" / "catalog_field_evidence.csv"
)
REPORT = ROOT / "data" / "review" / "catalog-calculation-readiness-audit-v2.json"
SUMMARY = ROOT / "data" / "review" / "catalog-calculation-readiness-summary-v2.md"

CalculationStatus = Literal[
    "CALCULATION_READY",
    "CALCULATION_READY_WITH_ASSUMPTIONS",
    "CALCULATION_BLOCKED",
    "UNSUPPORTED_CAPACITY_PROFILE",
    "NOT_EQUIPMENT",
]
DeploymentStatus = Literal[
    "DEPLOYMENT_READY",
    "DEPLOYMENT_REVIEW_REQUIRED",
    "UNSUPPORTED_CAPACITY_PROFILE",
    "NOT_EQUIPMENT",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ScenarioInput(StrictModel):
    field: str = Field(min_length=1)
    input_path: str = Field(min_length=1)
    fallback_value: int | float
    unit: str = Field(min_length=1)
    provenance: str = Field(min_length=1)


class EquipmentClassV2(StrictModel):
    code: str = Field(min_length=1)
    capacity_profile: str = Field(min_length=1)
    calculation_model_fields: list[str] = Field(min_length=1)
    scenario_inputs: list[ScenarioInput]
    deployment_fields: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fields(self) -> "EquipmentClassV2":
        for values in (
            self.calculation_model_fields,
            [item.field for item in self.scenario_inputs],
            self.deployment_fields,
        ):
            if values != sorted(values) or len(values) != len(set(values)):
                raise ValueError(f"fields must be unique and sorted for {self.code}")
        expected = set(self.calculation_model_fields) | {
            item.field for item in self.scenario_inputs
        }
        if not expected <= set(self.deployment_fields):
            raise ValueError(f"deployment gate omits calculation inputs for {self.code}")
        return self


class PolicyV2(StrictModel):
    calculation_scope: Literal["PRELIMINARY_CAPACITY_ONLY"]
    matching_safe_availability: Literal["MATCHING_SAFE"]
    calculation_conflicts_block_only_affected_fields: Literal[True]
    deployment_requires_all_fields_and_no_conflicts: Literal[True]
    scenario_assumptions_are_not_vendor_facts: Literal[True]
    materialization_into_runtime_required: Literal[True]
    economics_in_scope: Literal[False]
    runtime_switch_allowed: Literal[False]
    capacity_formulas_changed: Literal[False]


class ContractV2(StrictModel):
    schema_version: Literal["runtime-calculation-readiness-contract-v2"]
    catalog_code: Literal["organizer-catalog-v4"]
    policy: PolicyV2
    equipment_classes: list[EquipmentClassV2] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_classes(self) -> "ContractV2":
        codes = [item.code for item in self.equipment_classes]
        profiles = [item.capacity_profile for item in self.equipment_classes]
        if len(codes) != len(set(codes)) or len(profiles) != len(set(profiles)):
            raise ValueError("equipment classes and profiles must be unique")
        return self


class LocalFact(StrictModel):
    adapter_id: str = Field(pattern=r"^L[0-9]{3}$")
    organizer_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    field_path: str = Field(min_length=1)
    normalized_value: Any
    normalized_unit: str | None
    evidence_status: Literal["CROSS_DOCUMENT_ENRICHED"]
    source_file: str = Field(min_length=1)
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_locator: str = Field(min_length=1)
    raw_value: str = Field(min_length=1)
    derivation: str = Field(min_length=1)


class LocalOverlay(StrictModel):
    schema_version: Literal["catalog-local-adapter-overlay-v1"]
    catalog_code: Literal["organizer-catalog-v4"]
    facts: list[LocalFact] = Field(min_length=1)


class AppliedAssumption(StrictModel):
    field: str = Field(min_length=1)
    input_path: str = Field(min_length=1)
    fallback_value: int | float
    unit: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    policy: Literal["SCENARIO_INPUT_THEN_EXPLICIT_FALLBACK"]
    vendor_fact: Literal[False]


class ReadinessItem(StrictModel):
    id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source_row_number: int | None
    equipment_class: str | None
    capacity_profile: str | None
    in_accepted_research_cohort: bool
    calculation_status: CalculationStatus
    deployment_status: DeploymentStatus
    calculation_model_fields: list[str]
    scenario_input_fields: list[str]
    deployment_fields: list[str]
    missing_calculation_fields: list[str]
    calculation_assumptions: list[AppliedAssumption]
    missing_deployment_fields: list[str]
    conflict_fields: list[str]


class ReadinessReport(StrictModel):
    schema_version: Literal["catalog-calculation-readiness-audit-v2"]
    contract_version: Literal["runtime-calculation-readiness-contract-v2"]
    catalog_code: Literal["organizer-catalog-v4"]
    deterministic_order: Literal["models:organizer_id;positions:source_row_number"]
    inputs_sha256: dict[str, str]
    counts: dict[str, int]
    model_calculation_status_counts: dict[str, int]
    position_calculation_status_counts: dict[str, int]
    model_deployment_status_counts: dict[str, int]
    position_deployment_status_counts: dict[str, int]
    accepted_research_cohort_counts: dict[str, int]
    local_adapter_facts: int
    models: list[ReadinessItem]
    positions: list[ReadinessItem]

    @model_validator(mode="after")
    def validate_exact_coverage(self) -> "ReadinessReport":
        if self.counts != {"models": 187, "positions": 223}:
            raise ValueError("readiness audit must cover exactly 187/223")
        if len(self.models) != 187 or len(self.positions) != 223:
            raise ValueError("readiness item counts differ")
        if [item.id for item in self.models] != sorted(item.id for item in self.models):
            raise ValueError("model ordering differs")
        if [item.source_row_number for item in self.positions] != list(range(2, 225)):
            raise ValueError("position ordering differs")
        if sum(self.model_calculation_status_counts.values()) != 187:
            raise ValueError("model calculation counts differ")
        if sum(self.position_calculation_status_counts.values()) != 223:
            raise ValueError("position calculation counts differ")
        return self


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract() -> ContractV2:
    return ContractV2.model_validate(_load(CONTRACT))


def load_local_overlay() -> LocalOverlay:
    overlay = LocalOverlay.model_validate(_load(LOCAL_ADAPTER))
    keys = [(fact.organizer_id, fact.field_path) for fact in overlay.facts]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError("local adapter facts must be unique and ordered")
    evidence_text = BASE_EVIDENCE.read_text(encoding="utf-8-sig")
    for fact in overlay.facts:
        if (
            fact.organizer_id not in evidence_text
            or fact.source_file not in evidence_text
            or fact.raw_value not in evidence_text
        ):
            raise ValueError(f"local adapter evidence is not anchored: {fact.adapter_id}")
    return overlay


def _availability(item: Any, local_fields: set[str]) -> dict[str, str]:
    result = {field: "MISSING" for field in item.required_fields}
    result.update({field: "MATCHING_SAFE" for field in local_fields})
    result.update({field.field: field.availability for field in item.present_fields})
    result.update({field: "MATCHING_SAFE" for field in local_fields})
    return result


def _item(
    source: Any,
    class_by_code: dict[str, EquipmentClassV2],
    cohort_ids: set[str],
    local_by_model: dict[str, set[str]],
) -> ReadinessItem:
    if source.status == "NOT_EQUIPMENT":
        return ReadinessItem(
            id=source.id,
            model_id=source.model_id,
            name=source.name,
            source_row_number=source.source_row_number,
            equipment_class=None,
            capacity_profile=None,
            in_accepted_research_cohort=source.model_id in cohort_ids,
            calculation_status="NOT_EQUIPMENT",
            deployment_status="NOT_EQUIPMENT",
            calculation_model_fields=[],
            scenario_input_fields=[],
            deployment_fields=[],
            missing_calculation_fields=[],
            calculation_assumptions=[],
            missing_deployment_fields=[],
            conflict_fields=[],
        )
    definition = class_by_code.get(source.equipment_class or "")
    if definition is None:
        return ReadinessItem(
            id=source.id,
            model_id=source.model_id,
            name=source.name,
            source_row_number=source.source_row_number,
            equipment_class=source.equipment_class,
            capacity_profile=source.capacity_profile,
            in_accepted_research_cohort=source.model_id in cohort_ids,
            calculation_status="UNSUPPORTED_CAPACITY_PROFILE",
            deployment_status="UNSUPPORTED_CAPACITY_PROFILE",
            calculation_model_fields=[],
            scenario_input_fields=[],
            deployment_fields=[],
            missing_calculation_fields=[],
            calculation_assumptions=[],
            missing_deployment_fields=[],
            conflict_fields=[],
        )
    availability = _availability(source, local_by_model.get(source.model_id, set()))
    missing_calculation = sorted(
        field
        for field in definition.calculation_model_fields
        if availability.get(field) != "MATCHING_SAFE"
    )
    assumptions = [
        AppliedAssumption(
            **scenario.model_dump(),
            policy="SCENARIO_INPUT_THEN_EXPLICIT_FALLBACK",
            vendor_fact=False,
        )
        for scenario in definition.scenario_inputs
        if availability.get(scenario.field) != "MATCHING_SAFE"
    ]
    if missing_calculation:
        calculation_status: CalculationStatus = "CALCULATION_BLOCKED"
    elif assumptions:
        calculation_status = "CALCULATION_READY_WITH_ASSUMPTIONS"
    else:
        calculation_status = "CALCULATION_READY"
    conflict_fields = sorted({conflict.field for conflict in source.conflicts})
    missing_deployment = sorted(
        field
        for field in definition.deployment_fields
        if availability.get(field) != "MATCHING_SAFE"
    )
    deployment_status: DeploymentStatus = (
        "DEPLOYMENT_READY"
        if not missing_deployment and not conflict_fields
        else "DEPLOYMENT_REVIEW_REQUIRED"
    )
    return ReadinessItem(
        id=source.id,
        model_id=source.model_id,
        name=source.name,
        source_row_number=source.source_row_number,
        equipment_class=definition.code,
        capacity_profile=definition.capacity_profile,
        in_accepted_research_cohort=source.model_id in cohort_ids,
        calculation_status=calculation_status,
        deployment_status=deployment_status,
        calculation_model_fields=definition.calculation_model_fields,
        scenario_input_fields=[item.field for item in definition.scenario_inputs],
        deployment_fields=definition.deployment_fields,
        missing_calculation_fields=missing_calculation,
        calculation_assumptions=assumptions,
        missing_deployment_fields=missing_deployment,
        conflict_fields=conflict_fields,
    )


def build_report() -> ReadinessReport:
    contract = load_contract()
    staging = build_staging()
    source = project_eligibility(staging)
    local = load_local_overlay()
    class_by_code = {item.code: item for item in contract.equipment_classes}
    cohort_ids = {fact.organizer_id for fact in staging.facts}
    local_by_model: dict[str, set[str]] = {}
    for fact in local.facts:
        local_by_model.setdefault(fact.organizer_id, set()).add(fact.field_path)
    models = [
        _item(item, class_by_code, cohort_ids, local_by_model) for item in source.models
    ]
    model_by_id = {item.model_id: item for item in models}
    positions = [
        model_by_id[item.model_id].model_copy(
            update={"id": item.id, "source_row_number": item.source_row_number}, deep=True
        )
        for item in source.positions
    ]
    calc_statuses = [
        "CALCULATION_READY",
        "CALCULATION_READY_WITH_ASSUMPTIONS",
        "CALCULATION_BLOCKED",
        "UNSUPPORTED_CAPACITY_PROFILE",
        "NOT_EQUIPMENT",
    ]
    deployment_statuses = [
        "DEPLOYMENT_READY",
        "DEPLOYMENT_REVIEW_REQUIRED",
        "UNSUPPORTED_CAPACITY_PROFILE",
        "NOT_EQUIPMENT",
    ]
    model_calc = Counter(item.calculation_status for item in models)
    position_calc = Counter(item.calculation_status for item in positions)
    model_deployment = Counter(item.deployment_status for item in models)
    position_deployment = Counter(item.deployment_status for item in positions)
    cohort = [item for item in models if item.in_accepted_research_cohort]
    cohort_calc = Counter(item.calculation_status for item in cohort)
    return ReadinessReport.model_validate(
        {
            "schema_version": "catalog-calculation-readiness-audit-v2",
            "contract_version": contract.schema_version,
            "catalog_code": contract.catalog_code,
            "deterministic_order": "models:organizer_id;positions:source_row_number",
            "inputs_sha256": {
                "contract": _sha256(CONTRACT),
                "local_adapter": _sha256(LOCAL_ADAPTER),
                "base_evidence": _sha256(BASE_EVIDENCE),
                "staging_overlay": _sha256(STAGING),
            },
            "counts": {"models": 187, "positions": 223},
            "model_calculation_status_counts": {
                key: model_calc[key] for key in calc_statuses
            },
            "position_calculation_status_counts": {
                key: position_calc[key] for key in calc_statuses
            },
            "model_deployment_status_counts": {
                key: model_deployment[key] for key in deployment_statuses
            },
            "position_deployment_status_counts": {
                key: position_deployment[key] for key in deployment_statuses
            },
            "accepted_research_cohort_counts": {
                "models": len(cohort),
                **{key: cohort_calc[key] for key in calc_statuses},
            },
            "local_adapter_facts": len(local.facts),
            "models": models,
            "positions": positions,
        }
    )


def _bytes(value: BaseModel) -> bytes:
    return (
        json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def summary(report: ReadinessReport) -> str:
    ready_models = [
        item
        for item in report.models
        if item.calculation_status
        in {"CALCULATION_READY", "CALCULATION_READY_WITH_ASSUMPTIONS"}
    ]
    cohort_ready = [item for item in ready_models if item.in_accepted_research_cohort]
    rows = "\n".join(
        f"| {item.name} | {item.equipment_class} | {item.calculation_status} |"
        for item in cohort_ready
    )
    return f"""# Calculation/deployment readiness audit v2

Contract v2 разделяет предварительный capacity-расчёт и инженерную готовность. Scenario
assumptions имеют явную provenance и не становятся vendor facts. Runtime и
active catalog не переключены, capacity formulas не изменены. Для запуска через
текущий backend всё ещё требуется materialization adapter; economics в scope
этого gate не входит.

## Exact coverage

- Models: 187.
- Positions: 223.
- Accepted research cohort: {report.accepted_research_cohort_counts['models']} models.
- Local adapter facts: {report.local_adapter_facts}.

## Calculation status

| Status | Models | Positions |
|---|---:|---:|
| CALCULATION_READY | {report.model_calculation_status_counts['CALCULATION_READY']} | {report.position_calculation_status_counts['CALCULATION_READY']} |
| CALCULATION_READY_WITH_ASSUMPTIONS | {report.model_calculation_status_counts['CALCULATION_READY_WITH_ASSUMPTIONS']} | {report.position_calculation_status_counts['CALCULATION_READY_WITH_ASSUMPTIONS']} |
| CALCULATION_BLOCKED | {report.model_calculation_status_counts['CALCULATION_BLOCKED']} | {report.position_calculation_status_counts['CALCULATION_BLOCKED']} |
| UNSUPPORTED_CAPACITY_PROFILE | {report.model_calculation_status_counts['UNSUPPORTED_CAPACITY_PROFILE']} | {report.position_calculation_status_counts['UNSUPPORTED_CAPACITY_PROFILE']} |
| NOT_EQUIPMENT | {report.model_calculation_status_counts['NOT_EQUIPMENT']} | {report.position_calculation_status_counts['NOT_EQUIPMENT']} |

## Deployment status

| Status | Models | Positions |
|---|---:|---:|
| DEPLOYMENT_READY | {report.model_deployment_status_counts['DEPLOYMENT_READY']} | {report.position_deployment_status_counts['DEPLOYMENT_READY']} |
| DEPLOYMENT_REVIEW_REQUIRED | {report.model_deployment_status_counts['DEPLOYMENT_REVIEW_REQUIRED']} | {report.position_deployment_status_counts['DEPLOYMENT_REVIEW_REQUIRED']} |
| UNSUPPORTED_CAPACITY_PROFILE | {report.model_deployment_status_counts['UNSUPPORTED_CAPACITY_PROFILE']} | {report.position_deployment_status_counts['UNSUPPORTED_CAPACITY_PROFILE']} |
| NOT_EQUIPMENT | {report.model_deployment_status_counts['NOT_EQUIPMENT']} | {report.position_deployment_status_counts['NOT_EQUIPMENT']} |

## Расчётный пул accepted research cohort

| Model | Class | Calculation status |
|---|---|---|
{rows}

`CALCULATION_READY_WITH_ASSUMPTIONS` означает: model-specific formula facts
доказаны, а операционные cycle inputs должны прийти из сценария; при их
отсутствии применяется зафиксированный fallback. Это не означает готовность к
закупке или внедрению.
"""


def _check(path: Path, payload: bytes) -> None:
    if not path.is_file() or path.read_bytes() != payload:
        raise ValueError(f"generated artifact differs: {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    contract = load_contract()
    report = build_report()
    artifacts = {
        CONTRACT_SCHEMA: schema_bytes(ContractV2),
        REPORT_SCHEMA: schema_bytes(ReadinessReport),
        REPORT: _bytes(report),
        SUMMARY: summary(report).encode("utf-8"),
    }
    if args.write:
        for path, payload in artifacts.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
    else:
        for path, payload in artifacts.items():
            _check(path, payload)
    print(
        json.dumps(
            {
                "models": report.model_calculation_status_counts,
                "positions": report.position_calculation_status_counts,
                "deployment_models": report.model_deployment_status_counts,
                "cohort": report.accepted_research_cohort_counts,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
