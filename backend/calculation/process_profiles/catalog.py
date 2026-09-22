"""C10 exact 28-row process catalog accepted by policy K19."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from calculation_contracts import (
    ObjectKind,
    ProcessCode,
    ProcessQuantityKind,
    ProcessScope,
    RoleCode,
    StrictContractModel,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = ROOT / "data/calculation/process-profile-catalog-v1.json"

CapacityHandler = Literal["TRANSPORT", "CLEANING", "PALLETIZING", "NONE"]
InputRequirement = Literal[
    "DEMAND", "SCHEDULE", "ROUTE", "BATCH", "AREA", "FREQUENCY",
    "CELL_RATE", "DISCOVERY_INPUTS", "CONSTRAINT_CONTEXT",
]
FormulaId = Literal["F01", "F02", "F03", "F04", "F05", "F06", "F07"]
ConstraintCheckId = Literal[
    "object-kind", "process-scope", "cargo", "payload", "aisle", "lift-height",
    "ceiling-clearance", "route-floors", "temperature", "noise", "airside",
    "apron", "restricted-zone", "sanitization", "class-b-containment",
    "cleanable-surface", "material-disinfection", "access-protocols",
    "passport-availability", "floor-flatness", "floor-covering", "slope",
    "outdoor", "availability", "integrations", "life-warning",
    "budget-warning", "charging-warning", "density-warning",
]
RequirementCode: TypeAlias = Annotated[str, Field(pattern=r"^requirement\.(?:demand|schedule|route|batch|area|frequency|cell-rate|discovery-inputs|constraint-context)$")]
ErrorCode: TypeAlias = Annotated[str, Field(pattern=r"^error\.missing-(?:demand|schedule|route|batch|area|frequency|cell-rate|discovery-inputs|constraint-context)$")]


class ProcessProfileUIV1(StrictContractModel):
    label_key: str = Field(min_length=1)
    description_key: str = Field(min_length=1)
    demand_label_key: str = Field(min_length=1)
    show_capacity_action: bool


class ProcessProfileV1(StrictContractModel):
    microstage_id: str = Field(pattern=r"^C10\.(?:0[1-9]|1[0-9]|2[0-8])$")
    process_code: ProcessCode
    object_kind: ObjectKind
    scope: ProcessScope
    capacity_handler: CapacityHandler
    default_role_codes: list[RoleCode]
    allowed_quantity_kinds: list[ProcessQuantityKind] = Field(min_length=1)
    has_fot_savings: bool
    formula_ids: list[FormulaId]
    required_inputs: list[InputRequirement]
    applicable_checks: list[ConstraintCheckId] = Field(min_length=1)
    requirement_codes: list[RequirementCode] = Field(min_length=1)
    error_codes: list[ErrorCode] = Field(min_length=1)
    user_cycle_allowed: bool
    unsupported_reason_code: str | None = None
    ui: ProcessProfileUIV1
    source_refs: list[str] = Field(min_length=1)
    decision_refs: list[Literal["K15", "K19"]] = Field(min_length=1)
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_semantics(self) -> "ProcessProfileV1":
        if not str(self.process_code).startswith(str(self.object_kind).lower() + "_"):
            raise ValueError("process code/object identity mismatch")
        if len(self.default_role_codes) != len(set(self.default_role_codes)):
            raise ValueError("default roles must be unique")
        if len(self.allowed_quantity_kinds) != len(set(self.allowed_quantity_kinds)):
            raise ValueError("allowed quantity kinds must be unique")
        expected = {
            "TRANSPORT": ({ProcessScope.TRANSPORT_CYCLE, ProcessScope.DELIVERY_CYCLE}, ["F01", "F02", "F03", "F04", "F07"]),
            "CLEANING": ({ProcessScope.CLEANING_AREA}, ["F01", "F05", "F07"]),
            "PALLETIZING": ({ProcessScope.FIXED_CELL}, ["F01", "F06", "F07"]),
        }
        if self.capacity_handler in expected:
            scopes, formula_ids = expected[self.capacity_handler]
            if self.scope not in scopes or self.formula_ids != formula_ids:
                raise ValueError("capacity handler scope/formulas mismatch")
            if self.user_cycle_allowed or self.unsupported_reason_code is not None:
                raise ValueError("formula profile cannot also be unsupported/user-cycle")
        elif self.scope == ProcessScope.REFERENCE_ONLY:
            if self.formula_ids or not self.user_cycle_allowed or not self.unsupported_reason_code:
                raise ValueError("REFERENCE_ONLY requires reason and opt-in USER_CYCLE")
        elif self.scope == ProcessScope.CONSTRAINT_ONLY:
            if self.formula_ids or self.user_cycle_allowed or not self.unsupported_reason_code:
                raise ValueError("CONSTRAINT_ONLY cannot size a fleet")
        else:
            raise ValueError("NONE handler requires reference/constraint scope")
        if self.has_fot_savings != bool(self.default_role_codes):
            raise ValueError("has_fot_savings follows explicit role availability")
        if "POLICY_V1:K19" not in self.source_refs or "K19" not in self.decision_refs:
            raise ValueError("every mapping must cite accepted K19")
        if self.ui.show_capacity_action != (self.capacity_handler != "NONE"):
            raise ValueError("UI capacity action must follow formula handler")
        return self


class ProcessProfileCatalogV1(StrictContractModel):
    schema_version: Literal["process-profile-catalog-v1"] = "process-profile-catalog-v1"
    catalog_version: Literal["calculation-process-catalog-v1"] = "calculation-process-catalog-v1"
    policy_version: Literal["hackathon-calculation-policy-v1"] = "hackathon-calculation-policy-v1"
    process_projection_version: Literal["calculation-process-projection-v2"] = "calculation-process-projection-v2"
    candidate_pool_models: Literal[21] = 21
    candidate_pool_positions: Literal[24] = 24
    pool_membership_changed: Literal[False] = False
    profiles: list[ProcessProfileV1] = Field(min_length=28, max_length=28)

    @model_validator(mode="after")
    def exact_coverage(self) -> "ProcessProfileCatalogV1":
        expected_ids = [f"C10.{index:02d}" for index in range(1, 29)]
        if [item.microstage_id for item in self.profiles] != expected_ids:
            raise ValueError("C10 microstages must be exact and ordered")
        codes = [item.process_code for item in self.profiles]
        if len(codes) != len(set(codes)) or set(codes) != set(ProcessCode):
            raise ValueError("catalog must cover every process code exactly once")
        roles = {role for item in self.profiles for role in item.default_role_codes}
        required_roles = set(RoleCode) - {RoleCode.TECH_SUPPORT, RoleCode.CONTROL_OPERATOR}
        if not required_roles <= roles:
            raise ValueError("catalog omits an object process role")
        return self

    def by_code(self, process_code: ProcessCode | str) -> ProcessProfileV1:
        return next(item for item in self.profiles if item.process_code == process_code)


@lru_cache(maxsize=4)
def load_process_profile_catalog(path_text: str | None = None) -> ProcessProfileCatalogV1:
    path = Path(path_text) if path_text else DEFAULT_CATALOG_PATH
    return ProcessProfileCatalogV1.model_validate_json(path.read_text(encoding="utf-8"))
