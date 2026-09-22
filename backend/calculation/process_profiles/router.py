"""Pure process-to-capacity-handler routing; it does not execute formulas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from calculation_contracts import NormalizedProcess, ProcessCode, ProcessScope, StrictContractModel

from .catalog import ConstraintCheckId, FormulaId, InputRequirement, ProcessProfileCatalogV1, load_process_profile_catalog


class ProcessRouteDecisionV1(StrictContractModel):
    schema_version: Literal["process-route-decision-v1"] = "process-route-decision-v1"
    process_id: str = Field(min_length=1)
    process_code: ProcessCode
    declared_scope: ProcessScope
    disposition: Literal[
        "TRANSPORT", "CLEANING", "PALLETIZING", "USER_CYCLE",
        "REFERENCE_ONLY", "CONSTRAINT_ONLY", "NOT_APPLICABLE",
    ]
    engine: Literal["C07_TRANSPORT", "C08_CLEANING", "C09_PALLETIZING", "C10_USER_CYCLE"] | None
    formula_ids: list[FormulaId]
    required_inputs: list[InputRequirement]
    applicable_checks: list[ConstraintCheckId]
    reason_code: str
    user_cycle_opt_in: bool

    @model_validator(mode="after")
    def consistent(self) -> "ProcessRouteDecisionV1":
        executable = self.disposition in {"TRANSPORT", "CLEANING", "PALLETIZING", "USER_CYCLE"}
        if executable != (self.engine is not None):
            raise ValueError("executable disposition requires exactly one engine")
        if self.disposition == "USER_CYCLE" and not self.user_cycle_opt_in:
            raise ValueError("USER_CYCLE must be explicit opt-in")
        return self


def route_process(
    process: NormalizedProcess,
    *,
    use_user_cycle: bool = False,
    catalog: ProcessProfileCatalogV1 | None = None,
) -> ProcessRouteDecisionV1:
    catalog = catalog or load_process_profile_catalog()
    profile = catalog.by_code(process.process_code)
    if process.object_kind != profile.object_kind or process.scope != profile.scope:
        raise ValueError("normalized process differs from immutable C10 mapping")
    common = dict(
        process_id=process.process_id,
        process_code=str(process.process_code),
        declared_scope=str(profile.scope),
        required_inputs=list(profile.required_inputs),
        applicable_checks=list(profile.applicable_checks),
    )
    if not process.active:
        return ProcessRouteDecisionV1(**common, disposition="NOT_APPLICABLE", engine=None,
            formula_ids=[], reason_code="inactive-process-block", user_cycle_opt_in=False)
    if process.process_code == "clinic_results" and process.quantity_kind == "DIGITAL_FLOW":
        return ProcessRouteDecisionV1(**common, disposition="NOT_APPLICABLE", engine=None,
            formula_ids=[], reason_code="digital-flow-has-no-physical-fleet", user_cycle_opt_in=False)
    if use_user_cycle:
        if not profile.user_cycle_allowed:
            raise ValueError("USER_CYCLE is only allowed for REFERENCE_ONLY profiles")
        return ProcessRouteDecisionV1(**common, disposition="USER_CYCLE", engine="C10_USER_CYCLE",
            formula_ids=["F01", "F03", "F04", "F07"], reason_code="explicit-user-cycle",
            user_cycle_opt_in=True)
    engine_by_handler = {
        "TRANSPORT": "C07_TRANSPORT",
        "CLEANING": "C08_CLEANING",
        "PALLETIZING": "C09_PALLETIZING",
    }
    if profile.capacity_handler in engine_by_handler:
        return ProcessRouteDecisionV1(**common, disposition=profile.capacity_handler,
            engine=engine_by_handler[profile.capacity_handler], formula_ids=profile.formula_ids,
            reason_code="formula-profile-selected", user_cycle_opt_in=False)
    disposition = "CONSTRAINT_ONLY" if profile.scope == "CONSTRAINT_ONLY" else "REFERENCE_ONLY"
    return ProcessRouteDecisionV1(**common, disposition=disposition, engine=None,
        formula_ids=[], reason_code=profile.unsupported_reason_code or "unsupported-process-profile",
        user_cycle_opt_in=False)
