"""Immutable calculation parameter registry v1 loader and validator.

The loader reads only the committed registry snapshot. Reference documents are
build-time evidence and are deliberately not runtime dependencies.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DecimalString = Annotated[
    str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
]
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
StableId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._:-]{0,159}$")]

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = ROOT / "data" / "calculation" / "registry-v1.json"
DEFAULT_MANIFEST_PATH = ROOT / "data" / "calculation" / "registry-v1.manifest.json"
DEFAULT_SCHEMA_PATH = ROOT / "contracts" / "calculation-parameter-registry-v1.schema.json"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParameterDomain(StrictModel):
    minimum: DecimalString | None = None
    maximum: DecimalString | None = None
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True
    allowed_values: list[DecimalString] | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "ParameterDomain":
        if self.minimum is not None and self.maximum is not None:
            if Decimal(self.minimum) > Decimal(self.maximum):
                raise ValueError("domain minimum exceeds maximum")
        if self.allowed_values is not None:
            if not self.allowed_values:
                raise ValueError("allowed_values cannot be empty")
            if len(self.allowed_values) != len(set(self.allowed_values)):
                raise ValueError("allowed_values must be unique")
        return self


class ParameterSourceRef(StrictModel):
    source_id: Literal[
        "R00", "R02", "R03", "R04", "R06", "POLICY_V1", "OFFICIAL_TZ"
    ]
    locator: Annotated[str, Field(min_length=1)]
    source_status: Literal[
        "REFERENCE_CANON",
        "ACCEPTED_POLICY",
        "OFFICIAL_REQUIREMENT",
        "UNIT_DEFINITION",
    ]


class RegistryParameter(StrictModel):
    parameter_id: StableId
    semantic_name: StableId
    value: DecimalString
    unit: Annotated[str, Field(min_length=1, max_length=64)]
    quantity_kind: Literal[
        "COUNT",
        "TIME",
        "DISTANCE",
        "AREA",
        "SPEED",
        "RATE",
        "FRACTION",
        "MONEY",
        "POWER",
        "UNIT_DEFINITION",
        "SCORE",
    ]
    domain: ParameterDomain
    scenario: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC", "ALL"] = "ALL"
    year: Annotated[int, Field(ge=1, le=15)] | None = None
    provenance_kind: Literal["ASSUMPTION", "POLICY", "OFFICIAL", "UNIT_DEFINITION"]
    override_policy: Literal["LOCKED", "EXPLICIT_USER_OVERRIDE"]
    source_refs: list[ParameterSourceRef] = Field(min_length=1)
    source_digest: Digest
    decision_refs: list[Annotated[str, Field(pattern=r"^K(?:0[1-9]|[12][0-9])$")]]
    applicability: list[StableId] = Field(min_length=1)
    consumers: list[Annotated[str, Field(pattern=r"^(?:F(?:0[1-9]|[12][0-9]|3[0-5])|C(?:0[1-9]|[12][0-9]))$")]] = Field(
        min_length=1
    )
    effective_version: Literal["hackathon-calculation-policy-v1"]
    replaced_by: StableId | None = None
    label_key: StableId
    description_key: StableId

    @model_validator(mode="after")
    def validate_value(self) -> "RegistryParameter":
        try:
            value = Decimal(self.value)
        except InvalidOperation as exc:
            raise ValueError("parameter value is not decimal") from exc
        domain = self.domain
        if domain.minimum is not None:
            minimum = Decimal(domain.minimum)
            if value < minimum or (value == minimum and not domain.minimum_inclusive):
                raise ValueError("parameter value is below domain")
        if domain.maximum is not None:
            maximum = Decimal(domain.maximum)
            if value > maximum or (value == maximum and not domain.maximum_inclusive):
                raise ValueError("parameter value is above domain")
        if domain.allowed_values is not None and self.value not in domain.allowed_values:
            raise ValueError("parameter value is not allowed")
        return self


class CoverageRecord(StrictModel):
    coverage_id: StableId
    source_id: Literal["R02", "R06"]
    locator: Annotated[str, Field(min_length=1)]
    disposition: Literal[
        "REGISTRY_VALUES",
        "DERIVED_FORMULA",
        "USER_INPUT_REQUIRED",
        "VENDOR_INPUT_REQUIRED",
        "POLICY_RULE",
        "SUPERSEDED",
        "FORBIDDEN_UNSAFE_DEFAULT",
        "EXPLANATION_ONLY",
    ]
    parameter_ids: list[StableId] = Field(default_factory=list)
    decision_refs: list[Annotated[str, Field(pattern=r"^K(?:0[1-9]|[12][0-9])$")]]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_disposition(self) -> "CoverageRecord":
        if self.disposition == "REGISTRY_VALUES" and not self.parameter_ids:
            raise ValueError("registry coverage requires parameter_ids")
        if self.disposition != "REGISTRY_VALUES" and self.parameter_ids:
            raise ValueError("non-registry coverage cannot claim parameter values")
        return self


class SupersessionRecord(StrictModel):
    supersession_id: StableId
    source_ref: Annotated[str, Field(min_length=1)]
    old_semantics: Annotated[str, Field(min_length=1)]
    replacement_parameter_ids: list[StableId] = Field(default_factory=list)
    replacement_rule: Annotated[str, Field(min_length=1)]
    decision_refs: list[Annotated[str, Field(pattern=r"^K(?:0[1-9]|[12][0-9])$")]]


class CalculationParameterRegistryV1(StrictModel):
    schema_version: Literal["calculation-parameter-registry-v1"]
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    policy_version: Literal["hackathon-calculation-policy-v1"]
    registry_digest: Digest
    semantic_order: Literal["parameter_id"]
    parameters: list[RegistryParameter]
    coverage: list[CoverageRecord]
    supersessions: list[SupersessionRecord]

    @model_validator(mode="after")
    def validate_registry(self) -> "CalculationParameterRegistryV1":
        ids = [item.parameter_id for item in self.parameters]
        if ids != sorted(ids):
            raise ValueError("parameters must be ordered by parameter_id")
        if len(ids) != len(set(ids)):
            raise ValueError("parameter_id must be unique")
        semantic_keys = [
            (item.semantic_name, tuple(item.applicability), item.scenario, item.year)
            for item in self.parameters
        ]
        if len(semantic_keys) != len(set(semantic_keys)):
            raise ValueError("semantic scope/scenario/year identity must be unique")
        known = set(ids)
        coverage_ids = [item.coverage_id for item in self.coverage]
        if coverage_ids != sorted(coverage_ids) or len(coverage_ids) != len(set(coverage_ids)):
            raise ValueError("coverage IDs must be unique and sorted")
        for item in self.coverage:
            if any(parameter_id not in known for parameter_id in item.parameter_ids):
                raise ValueError("coverage has unknown parameter_id")
        for item in self.supersessions:
            if any(parameter_id not in known for parameter_id in item.replacement_parameter_ids):
                raise ValueError("supersession has unknown replacement parameter")
        return self

    def by_id(self, parameter_id: str) -> RegistryParameter:
        for parameter in self.parameters:
            if parameter.parameter_id == parameter_id:
                return parameter
        raise KeyError(parameter_id)

    def values_for(self, semantic_name: str) -> tuple[RegistryParameter, ...]:
        return tuple(
            item for item in self.parameters if item.semantic_name == semantic_name
        )


class SourceArtifact(StrictModel):
    source_id: Literal["R00", "R02", "R03", "R04", "R06", "POLICY_V1"]
    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    role: Literal["REFERENCE", "ACCEPTED_POLICY"]
    runtime_dependency: Literal[False]


class RegistryManifestV1(StrictModel):
    schema_version: Literal["calculation-parameter-registry-manifest-v1"]
    registry_version: Literal["hackathon-calculation-parameter-registry-v1"]
    registry_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    registry_semantic_digest: Digest
    schema_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    sources: list[SourceArtifact]
    parameter_count: Annotated[int, Field(gt=0)]
    coverage_count: Annotated[int, Field(gt=0)]
    supersession_count: Annotated[int, Field(gt=0)]
    scenario_parameter_count: Annotated[int, Field(gt=0)]
    required_decisions: list[Annotated[str, Field(pattern=r"^K(?:0[1-9]|[12][0-9])$")]]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def registry_semantic_payload(value: CalculationParameterRegistryV1 | dict[str, Any]) -> dict[str, Any]:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    payload = json.loads(json.dumps(payload))
    payload.pop("registry_digest", None)
    return payload


def registry_semantic_digest(value: CalculationParameterRegistryV1 | dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(registry_semantic_payload(value))).hexdigest()
    return f"sha256:{digest}"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def load_registry(path: str | Path = DEFAULT_REGISTRY_PATH) -> CalculationParameterRegistryV1:
    resolved = Path(path).resolve()
    registry = CalculationParameterRegistryV1.model_validate(_load_json(resolved))
    if registry_semantic_digest(registry) != registry.registry_digest:
        raise ValueError("registry semantic digest mismatch")
    return registry


@lru_cache(maxsize=8)
def load_registry_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> RegistryManifestV1:
    return RegistryManifestV1.model_validate(_load_json(Path(path).resolve()))


def verify_registry_artifacts(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> CalculationParameterRegistryV1:
    registry_file = Path(registry_path).resolve()
    manifest = load_registry_manifest(Path(manifest_path).resolve())
    raw_digest = hashlib.sha256(registry_file.read_bytes()).hexdigest()
    if raw_digest != manifest.registry_sha256:
        raise ValueError("registry file digest mismatch")
    registry = load_registry(registry_file)
    if registry.registry_digest != manifest.registry_semantic_digest:
        raise ValueError("registry manifest semantic digest mismatch")
    schema_digest = hashlib.sha256(Path(schema_path).resolve().read_bytes()).hexdigest()
    if schema_digest != manifest.schema_sha256:
        raise ValueError("registry schema digest mismatch")
    if len(registry.parameters) != manifest.parameter_count:
        raise ValueError("registry parameter count mismatch")
    if len(registry.coverage) != manifest.coverage_count:
        raise ValueError("registry coverage count mismatch")
    if len(registry.supersessions) != manifest.supersession_count:
        raise ValueError("registry supersession count mismatch")
    scenario_count = sum(item.scenario != "ALL" for item in registry.parameters)
    if scenario_count != manifest.scenario_parameter_count:
        raise ValueError("registry scenario parameter count mismatch")

    source_hashes = {item.source_id: item.sha256 for item in manifest.sources}
    for parameter in registry.parameters:
        source_binding = [
            {
                "source_id": item.source_id,
                "source_sha256": source_hashes[item.source_id],
                "locator": item.locator,
                "source_status": item.source_status,
            }
            for item in parameter.source_refs
        ]
        expected_digest = "sha256:" + hashlib.sha256(
            canonical_bytes(source_binding)
        ).hexdigest()
        if expected_digest != parameter.source_digest:
            raise ValueError(f"source digest mismatch for {parameter.parameter_id}")
    return registry


__all__ = [
    "CalculationParameterRegistryV1",
    "CoverageRecord",
    "RegistryManifestV1",
    "RegistryParameter",
    "load_registry",
    "load_registry_manifest",
    "registry_semantic_digest",
    "verify_registry_artifacts",
]
