"""C03 process/role intake normalization v2.

The module is additive and is intentionally not registered as a production
route.  It converts strict USER/FILE/LLM input into the C01 normalized DTOs,
keeps raw provenance and reports field errors without running formulas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from calculation_contracts import (
    MissingQuantity,
    MissingReason,
    NormalizedProcess,
    ObjectKind,
    PROCESS_DEMAND_UNITS,
    ProcessCode,
    ProcessQuantityKind,
    ProcessSchedule,
    ProcessScope,
    QuantityKind,
    QuantityName,
    RoleCode,
    RoleEntry,
    RolePool,
    StableId,
    StrictContractModel,
    Unit,
    KnownQuantity,
)
from calculation.units import UnitNormalizationError, canonical_decimal, normalize_unit


INTAKE_SCHEMA_VERSION = "calculation-intake-v2"
NORMALIZATION_SCHEMA_VERSION = "calculation-intake-normalization-v2"
PROCESS_PROJECTION_VERSION = "calculation-process-projection-v2"


class RawSource(StrEnum):
    USER = "USER"
    FILE = "FILE"
    LLM = "LLM"
    PRESET = "PRESET"
    ASSUMPTION = "ASSUMPTION"
    LEGACY_V1 = "LEGACY_V1"


class ActivationSource(StrEnum):
    USER = "USER"
    FILE = "FILE"
    LLM = "LLM"
    ROLE = "ROLE"
    POLICY = "POLICY"
    LEGACY_V1 = "LEGACY_V1"


class RawProvenance(StrictContractModel):
    source: RawSource
    raw_text: str | None = Field(default=None, max_length=4096)
    file_name: str | None = Field(default=None, max_length=255)
    file_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    sheet: str | None = Field(default=None, max_length=128)
    row: int | None = Field(default=None, ge=1)
    cell: str | None = Field(default=None, pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")
    llm_message_id: str | None = Field(default=None, max_length=128)
    alias: str | None = Field(default=None, max_length=128)
    user_confirmed: bool = False

    @model_validator(mode="after")
    def validate_source_details(self) -> RawProvenance:
        if self.source == RawSource.FILE and not self.file_sha256:
            raise ValueError("FILE provenance requires file_sha256")
        if self.source == RawSource.LLM and not self.raw_text:
            raise ValueError("LLM provenance requires raw_text")
        return self


class RawQuantity(StrictContractModel):
    value: str = Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
    unit: str = Field(min_length=1, max_length=32)
    provenance: RawProvenance


class ProcessScheduleInput(StrictContractModel):
    shifts_per_day: RawQuantity | None = None
    shift_hours: RawQuantity | None = None
    days_per_year: RawQuantity | None = None


class ProcessIntake(StrictContractModel):
    block_id: StableId
    process_id: StableId
    process_code: ProcessCode
    active: bool
    activation_source: ActivationSource
    quantity_kind: ProcessQuantityKind
    demand: RawQuantity | None = None
    schedule: ProcessScheduleInput | None = None
    route_distance: RawQuantity | None = None
    explicit_batch: RawQuantity | None = None
    role_refs: list[StableId] = Field(default_factory=list)


class RoleIntake(StrictContractModel):
    role_id: StableId
    object_scope: ObjectKind | Literal["SITE"]
    role_code: RoleCode
    label: str | None = Field(default=None, min_length=1, max_length=128)
    headcount: RawQuantity
    monthly_gross_salary: RawQuantity | None = None
    zero_cost_marker: Literal["ZERO_COST_ROLE"] | None = None
    process_ids: list[StableId] = Field(default_factory=list)
    allocation_shares: dict[StableId, str] | None = None


class CalculationIntakeRequestV2(StrictContractModel):
    schema_version: Literal["calculation-intake-v2"] = INTAKE_SCHEMA_VERSION
    input_revision: StableId
    object_id: StableId
    object_kind: ObjectKind
    facility_areas: dict[Literal["total_area", "active_area"], RawQuantity | None] | None = None
    processes: list[ProcessIntake]
    roles: list[RoleIntake]
    additional_income_raw: RawQuantity | None = None
    legacy_import_version: str | None = Field(default=None, max_length=128)
    source_profile_version: str | None = Field(default=None, max_length=160)
    raw_profile_parameters: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_identities(self) -> CalculationIntakeRequestV2:
        if self.facility_areas:
            for area in self.facility_areas.values():
                if area is not None and (area.unit != "m2" or not 0 < Decimal(area.value) <= 100000000):
                    raise ValueError("facility area must be positive square metres")
            total = self.facility_areas.get("total_area")
            active = self.facility_areas.get("active_area")
            if total and active and Decimal(active.value) > Decimal(total.value):
                raise ValueError("active area exceeds total area")
        process_ids = [item.process_id for item in self.processes]
        block_ids = [item.block_id for item in self.processes]
        role_ids = [item.role_id for item in self.roles]
        if len(process_ids) != len(set(process_ids)):
            raise ValueError("duplicate process_id")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("duplicate block_id")
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("duplicate role_id")
        role_identities = [(item.object_scope, item.role_code) for item in self.roles]
        if len(role_identities) != len(set(role_identities)):
            raise ValueError("duplicate object-scoped role")
        known_processes = set(process_ids)
        known_roles = set(role_ids)
        for process in self.processes:
            if set(process.role_refs) - known_roles:
                raise ValueError("process contains unknown role_ref")
        for role in self.roles:
            if role.object_scope not in (self.object_kind, "SITE"):
                raise ValueError("role object_scope does not match object_kind")
            if set(role.process_ids) - known_processes:
                raise ValueError("role contains unknown process_id")
        return self


class IntakeIssue(StrictContractModel):
    code: StableId
    field: str = Field(min_length=1, max_length=256)
    message: str = Field(min_length=1, max_length=512)


class ConversionNode(StrictContractModel):
    node_id: StableId
    field: str
    raw_value: str
    raw_unit: str
    normalized_value: str
    normalized_unit: str
    rule: str
    provenance: RawProvenance


class NormalizationResponseV2(StrictContractModel):
    schema_version: Literal["calculation-intake-normalization-v2"] = NORMALIZATION_SCHEMA_VERSION
    valid: bool
    input_revision: StableId
    object_id: StableId
    process_projection_version: Literal["calculation-process-projection-v2"] = PROCESS_PROJECTION_VERSION
    normalized_processes: list[NormalizedProcess]
    role_pool: RolePool
    errors: list[IntakeIssue]
    required_inputs: list[str]
    conversions: list[ConversionNode]
    raw_extensions: dict[str, Any]


@dataclass(frozen=True)
class ProcessDefinition:
    object_kind: ObjectKind
    scope: ProcessScope
    roles: tuple[RoleCode, ...]
    allowed_kinds: tuple[ProcessQuantityKind, ...]


def _d(obj: ObjectKind, scope: ProcessScope, roles: tuple[RoleCode, ...], *kinds: ProcessQuantityKind) -> ProcessDefinition:
    return ProcessDefinition(obj, scope, roles, kinds)


PROCESS_DEFINITIONS: dict[ProcessCode, ProcessDefinition] = {
    ProcessCode.WAREHOUSE_RECEIVING_SHIPPING: _d(ObjectKind.WAREHOUSE, ProcessScope.TRANSPORT_CYCLE, (RoleCode.FORKLIFT_DRIVER, RoleCode.LOADER), ProcessQuantityKind.PALLET),
    ProcessCode.WAREHOUSE_STORAGE: _d(ObjectKind.WAREHOUSE, ProcessScope.REFERENCE_ONLY, (RoleCode.STOREKEEPER,), ProcessQuantityKind.PALLET),
    ProcessCode.WAREHOUSE_PICKING: _d(ObjectKind.WAREHOUSE, ProcessScope.REFERENCE_ONLY, (RoleCode.PICKER, RoleCode.SORTER), ProcessQuantityKind.PICK, ProcessQuantityKind.BOX),
    ProcessCode.WAREHOUSE_PALLETIZING: _d(ObjectKind.WAREHOUSE, ProcessScope.FIXED_CELL, (RoleCode.PACKER,), ProcessQuantityKind.PALLET, ProcessQuantityKind.CASE),
    ProcessCode.WAREHOUSE_CLEANING: _d(ObjectKind.WAREHOUSE, ProcessScope.CLEANING_AREA, (RoleCode.CLEANER,), ProcessQuantityKind.SQUARE_METER),
    ProcessCode.WAREHOUSE_INVENTORY: _d(ObjectKind.WAREHOUSE, ProcessScope.REFERENCE_ONLY, (RoleCode.INVENTORY_WORKER,), ProcessQuantityKind.ITEM),
    ProcessCode.AIRPORT_BAGGAGE: _d(ObjectKind.AIRPORT, ProcessScope.TRANSPORT_CYCLE, (RoleCode.BAGGAGE_HANDLER,), ProcessQuantityKind.ITEM, ProcessQuantityKind.CART),
    ProcessCode.AIRPORT_CATERING: _d(ObjectKind.AIRPORT, ProcessScope.TRANSPORT_CYCLE, (RoleCode.TROLLEY_OPERATOR,), ProcessQuantityKind.PORTION, ProcessQuantityKind.BOX, ProcessQuantityKind.KILOGRAM),
    ProcessCode.AIRPORT_FUELLING: _d(ObjectKind.AIRPORT, ProcessScope.REFERENCE_ONLY, (RoleCode.SPECIAL_EQUIPMENT_DRIVER,), ProcessQuantityKind.DELIVERY),
    ProcessCode.AIRPORT_INTERNAL_LOGISTICS: _d(ObjectKind.AIRPORT, ProcessScope.TRANSPORT_CYCLE, (RoleCode.TROLLEY_OPERATOR,), ProcessQuantityKind.CART, ProcessQuantityKind.DELIVERY),
    ProcessCode.AIRPORT_TERMINAL_CLEANING: _d(ObjectKind.AIRPORT, ProcessScope.CLEANING_AREA, (RoleCode.TERMINAL_CLEANER,), ProcessQuantityKind.SQUARE_METER),
    ProcessCode.AIRPORT_APRON_CLEANING: _d(ObjectKind.AIRPORT, ProcessScope.CLEANING_AREA, (RoleCode.PERRON_CLEANER,), ProcessQuantityKind.SQUARE_METER),
    ProcessCode.AIRPORT_WASTE: _d(ObjectKind.AIRPORT, ProcessScope.TRANSPORT_CYCLE, (RoleCode.TROLLEY_OPERATOR,), ProcessQuantityKind.KILOGRAM, ProcessQuantityKind.BIN),
    ProcessCode.AIRPORT_INSPECTION: _d(ObjectKind.AIRPORT, ProcessScope.REFERENCE_ONLY, (RoleCode.RUNWAY_INSPECTOR, RoleCode.SECURITY_GUARD), ProcessQuantityKind.ITEM),
    ProcessCode.AIRPORT_PASSENGER_ASSISTANCE: _d(ObjectKind.AIRPORT, ProcessScope.REFERENCE_ONLY, (RoleCode.PASSENGER_ASSISTANT, RoleCode.COURIER), ProcessQuantityKind.DELIVERY),
    ProcessCode.AIRPORT_GROUND_SERVICE: _d(ObjectKind.AIRPORT, ProcessScope.REFERENCE_ONLY, (RoleCode.RAMP_WORKER, RoleCode.GROUND_SUPPORT_WORKER), ProcessQuantityKind.DELIVERY),
    ProcessCode.CLINIC_FOOD: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.CATERING_WORKER,), ProcessQuantityKind.PORTION),
    ProcessCode.CLINIC_LINEN: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.LAUNDRY_WORKER,), ProcessQuantityKind.KILOGRAM),
    ProcessCode.CLINIC_MEDICINES: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.SANITARY, RoleCode.PORTER), ProcessQuantityKind.DELIVERY, ProcessQuantityKind.ITEM),
    ProcessCode.CLINIC_BIOMATERIALS: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.LAB_ASSISTANT,), ProcessQuantityKind.SAMPLE),
    ProcessCode.CLINIC_STERILE_SETS: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.STERILE_SUPPLY_WORKER,), ProcessQuantityKind.SET),
    ProcessCode.CLINIC_CONSUMABLES: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.CONSUMABLE_WORKER,), ProcessQuantityKind.ITEM),
    ProcessCode.CLINIC_WASTE_A: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.SANITARY, RoleCode.PORTER), ProcessQuantityKind.KILOGRAM),
    ProcessCode.CLINIC_WASTE_B: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.SANITARY, RoleCode.PORTER), ProcessQuantityKind.KILOGRAM),
    ProcessCode.CLINIC_RESULTS: _d(ObjectKind.CLINIC, ProcessScope.DELIVERY_CYCLE, (RoleCode.LAB_RESULT_COURIER,), ProcessQuantityKind.DELIVERY, ProcessQuantityKind.DIGITAL_FLOW),
    ProcessCode.CLINIC_CLEANING: _d(ObjectKind.CLINIC, ProcessScope.CLEANING_AREA, (RoleCode.CLEANER,), ProcessQuantityKind.SQUARE_METER),
    ProcessCode.CLINIC_INVENTORY: _d(ObjectKind.CLINIC, ProcessScope.REFERENCE_ONLY, (RoleCode.INVENTORY_WORKER,), ProcessQuantityKind.ITEM),
    ProcessCode.CLINIC_SAFETY_REQUIREMENTS: _d(ObjectKind.CLINIC, ProcessScope.CONSTRAINT_ONLY, (), ProcessQuantityKind.ITEM),
}


def _missing(name: QuantityName, kind: QuantityKind, unit: Unit, reason: MissingReason = MissingReason.MISSING_INPUT) -> MissingQuantity:
    return MissingQuantity(name=name, quantity_kind=kind, expected_unit=unit, missing_reason=reason)


def _known(raw: RawQuantity, *, name: QuantityName, kind: QuantityKind, expected_unit: Unit, field: str, conversions: list[ConversionNode]) -> KnownQuantity:
    value, unit = normalize_unit(raw.value, raw.unit, expected_kind=str(kind))
    if unit != str(expected_unit):
        raise UnitNormalizationError("UNIT_SEMANTIC_MISMATCH")
    node_id = f"conversion.{len(conversions) + 1:04d}"
    conversions.append(ConversionNode(node_id=node_id, field=field, raw_value=raw.value, raw_unit=raw.unit, normalized_value=value, normalized_unit=unit, rule="PHYSICAL_UNIT_DEFINITION", provenance=raw.provenance))
    return KnownQuantity(name=name, raw_value=canonical_decimal(raw.value), raw_unit=expected_unit, normalized_value=value, unit=expected_unit, quantity_kind=kind, provenance_ref=node_id)


def _issue(errors: list[IntakeIssue], required: list[str], code: str, field: str, message: str) -> None:
    errors.append(IntakeIssue(code=code.lower().replace("_", "-"), field=field, message=message))
    if field not in required:
        required.append(field)


def normalize_intake(request: CalculationIntakeRequestV2) -> NormalizationResponseV2:
    """Normalize intake deterministically, returning semantic field errors."""

    errors: list[IntakeIssue] = []
    required: list[str] = []
    conversions: list[ConversionNode] = []
    normalized_processes: list[NormalizedProcess] = []

    for process in request.processes:
        field_root = f"processes.{process.block_id}"
        definition = PROCESS_DEFINITIONS[process.process_code]
        process_semantic_valid = True
        if definition.object_kind != request.object_kind:
            _issue(errors, required, "PROCESS_OBJECT_MISMATCH", f"{field_root}.process_code", "Process does not belong to object kind")
            process_semantic_valid = False
        if process.quantity_kind not in definition.allowed_kinds:
            _issue(errors, required, "QUANTITY_KIND_MISMATCH", f"{field_root}.quantity_kind", "Quantity kind is not allowed for process")
            process_semantic_valid = False
        expected_unit = Unit(PROCESS_DEMAND_UNITS[str(process.quantity_kind)])
        if process.demand is None:
            demand = _missing(QuantityName.DEMAND_PER_DAY, QuantityKind.FLOW, expected_unit, MissingReason.NOT_APPLICABLE if not process.active else MissingReason.MISSING_INPUT)
            if process.active:
                _issue(errors, required, "DEMAND_REQUIRED", f"{field_root}.demand", "Active process requires positive demand")
                process_semantic_valid = False
        else:
            try:
                demand = _known(process.demand, name=QuantityName.DEMAND_PER_DAY, kind=QuantityKind.FLOW, expected_unit=expected_unit, field=f"{field_root}.demand", conversions=conversions)
                if process.active and Decimal(demand.normalized_value) <= 0:
                    _issue(errors, required, "DEMAND_NOT_POSITIVE", f"{field_root}.demand", "Active process demand must be positive")
                    process_semantic_valid = False
            except UnitNormalizationError as exc:
                demand = _missing(QuantityName.DEMAND_PER_DAY, QuantityKind.FLOW, expected_unit, MissingReason.UNIT_MISMATCH)
                _issue(errors, required, str(exc), f"{field_root}.demand", "Demand unit is incompatible")
                if process.active:
                    process_semantic_valid = False

        schedule = None
        if process.schedule is not None and all((process.schedule.shifts_per_day, process.schedule.shift_hours, process.schedule.days_per_year)):
            try:
                schedule = ProcessSchedule(
                    shifts_per_day=_known(process.schedule.shifts_per_day, name=QuantityName.SHIFTS_PER_DAY, kind=QuantityKind.COUNT, expected_unit=Unit.SHIFT, field=f"{field_root}.schedule.shifts_per_day", conversions=conversions),
                    shift_hours=_known(process.schedule.shift_hours, name=QuantityName.SHIFT_HOURS, kind=QuantityKind.TIME, expected_unit=Unit.HOUR, field=f"{field_root}.schedule.shift_hours", conversions=conversions),
                    days_per_year=_known(process.schedule.days_per_year, name=QuantityName.DAYS_PER_YEAR, kind=QuantityKind.TIME, expected_unit=Unit.DAY, field=f"{field_root}.schedule.days_per_year", conversions=conversions),
                )
            except (UnitNormalizationError, ValueError) as exc:
                _issue(errors, required, "SCHEDULE_INVALID", f"{field_root}.schedule", "Schedule values or H=shifts×hours are invalid")
        elif process.active:
            _issue(errors, required, "SCHEDULE_REQUIRED", f"{field_root}.schedule", "Active process requires complete schedule")

        route = None
        if process.route_distance is not None:
            try:
                route = _known(process.route_distance, name=QuantityName.ONE_WAY_DISTANCE, kind=QuantityKind.DISTANCE, expected_unit=Unit.METER, field=f"{field_root}.route_distance", conversions=conversions)
                if Decimal(route.normalized_value) <= 0:
                    route = None
                    _issue(errors, required, "ROUTE_NOT_POSITIVE", f"{field_root}.route_distance", "Route distance must be positive")
            except UnitNormalizationError as exc:
                _issue(errors, required, str(exc), f"{field_root}.route_distance", "Route unit is incompatible")
        elif process.active and definition.scope in (ProcessScope.TRANSPORT_CYCLE, ProcessScope.DELIVERY_CYCLE):
            required.append(f"{field_root}.route_distance")

        explicit_batch = None
        if process.explicit_batch is not None:
            # A batch is an entered physical count, never an implicit conversion
            # between portions, kg, samples, pallets or deliveries.
            try:
                batch_value = canonical_decimal(process.explicit_batch.value)
                if process.explicit_batch.unit != "unit/trip" or Decimal(batch_value) <= 0:
                    raise UnitNormalizationError("BATCH_INVALID")
                node_id = f"conversion.{len(conversions) + 1:04d}"
                conversions.append(ConversionNode(node_id=node_id, field=f"{field_root}.explicit_batch", raw_value=process.explicit_batch.value, raw_unit=process.explicit_batch.unit, normalized_value=batch_value, normalized_unit="unit/trip", rule="IDENTITY_TYPED_BATCH", provenance=process.explicit_batch.provenance))
                explicit_batch = KnownQuantity(name=QuantityName.UNITS_PER_TRIP, raw_value=batch_value, raw_unit=Unit.UNIT_PER_TRIP, normalized_value=batch_value, unit=Unit.UNIT_PER_TRIP, quantity_kind=QuantityKind.RATE, provenance_ref=node_id)
            except UnitNormalizationError as exc:
                _issue(errors, required, str(exc), f"{field_root}.explicit_batch", "Batch must be a positive unit/trip value")
        elif process.active and process.quantity_kind in (
            ProcessQuantityKind.BOX,
            ProcessQuantityKind.CASE,
            ProcessQuantityKind.KILOGRAM,
            ProcessQuantityKind.SAMPLE,
            ProcessQuantityKind.SET,
            ProcessQuantityKind.BIN,
            ProcessQuantityKind.ITEM,
            ProcessQuantityKind.PORTION,
        ):
            required.append(f"{field_root}.explicit_batch")

        if process_semantic_valid:
            normalized_processes.append(NormalizedProcess(process_id=process.process_id, input_revision=request.input_revision, object_kind=request.object_kind, process_code=process.process_code, scope=definition.scope, active=process.active, quantity_kind=process.quantity_kind, demand=demand, schedule=schedule, route_distance=route, explicit_batch=explicit_batch, role_refs=process.role_refs))

    normalized_roles: list[RoleEntry] = []
    for role in request.roles:
        root = f"roles.{role.role_id}"
        try:
            headcount = _known(role.headcount, name=QuantityName.ROLE_HEADCOUNT, kind=QuantityKind.COUNT, expected_unit=Unit.PERSON, field=f"{root}.headcount", conversions=conversions)
            if Decimal(headcount.normalized_value) < 0:
                _issue(errors, required, "HEADCOUNT_NEGATIVE", f"{root}.headcount", "Headcount cannot be negative")
                headcount = _missing(QuantityName.ROLE_HEADCOUNT, QuantityKind.COUNT, Unit.PERSON)
        except UnitNormalizationError as exc:
            _issue(errors, required, str(exc), f"{root}.headcount", "Headcount unit is incompatible")
            headcount = _missing(QuantityName.ROLE_HEADCOUNT, QuantityKind.COUNT, Unit.PERSON, MissingReason.UNIT_MISMATCH)
        salary = None
        if role.monthly_gross_salary is not None and role.monthly_gross_salary.provenance.source in (RawSource.USER, RawSource.FILE):
            try:
                salary = _known(role.monthly_gross_salary, name=QuantityName.MONTHLY_GROSS_SALARY, kind=QuantityKind.MONEY, expected_unit=Unit.RUB_PER_PERSON_MONTH, field=f"{root}.monthly_gross_salary", conversions=conversions)
            except UnitNormalizationError as exc:
                _issue(errors, required, str(exc), f"{root}.monthly_gross_salary", "Salary must be monthly gross RUB/person/month")
        elif role.monthly_gross_salary is not None and role.monthly_gross_salary.provenance.source == RawSource.ASSUMPTION and role.monthly_gross_salary.provenance.user_confirmed:
            salary = _known(role.monthly_gross_salary, name=QuantityName.MONTHLY_GROSS_SALARY, kind=QuantityKind.MONEY, expected_unit=Unit.RUB_PER_PERSON_MONTH, field=f"{root}.monthly_gross_salary", conversions=conversions)
        else:
            if role.monthly_gross_salary is not None:
                _issue(errors, required, "SALARY_CONFIRMATION_REQUIRED", f"{root}.monthly_gross_salary", "Preset/LLM salary is raw only until user confirmation")
        if salary is None:
            salary = _missing(QuantityName.MONTHLY_GROSS_SALARY, QuantityKind.MONEY, Unit.RUB_PER_PERSON_MONTH)
            salary_field = f"{root}.monthly_gross_salary"
            if salary_field not in required:
                required.append(salary_field)
        elif Decimal(salary.normalized_value) < 0:
            _issue(errors, required, "SALARY_NEGATIVE", f"{root}.monthly_gross_salary", "Salary cannot be negative")
            salary = _missing(QuantityName.MONTHLY_GROSS_SALARY, QuantityKind.MONEY, Unit.RUB_PER_PERSON_MONTH)
        elif Decimal(salary.normalized_value) == 0 and role.zero_cost_marker != "ZERO_COST_ROLE":
            _issue(errors, required, "SALARY_ZERO_UNMARKED", f"{root}.monthly_gross_salary", "Zero salary requires ZERO_COST_ROLE")
            salary = _missing(QuantityName.MONTHLY_GROSS_SALARY, QuantityKind.MONEY, Unit.RUB_PER_PERSON_MONTH)
        elif Decimal(salary.normalized_value) > 0 and role.zero_cost_marker is not None:
            _issue(errors, required, "SALARY_MARKER_INVALID", f"{root}.zero_cost_marker", "ZERO_COST_ROLE is valid only for zero salary")
            salary = _missing(QuantityName.MONTHLY_GROSS_SALARY, QuantityKind.MONEY, Unit.RUB_PER_PERSON_MONTH)
        normalized_roles.append(RoleEntry(role_id=role.role_id, object_scope=role.object_scope, role_code=role.role_code, label=role.label, headcount=headcount, monthly_gross_salary=salary, zero_cost_marker=role.zero_cost_marker, process_ids=role.process_ids))

    role_pool = RolePool(pool_id=f"{request.object_id}.roles", object_kind=request.object_kind, roles=normalized_roles)
    normalized_salary_by_role = {
        role.role_id: role.monthly_gross_salary for role in normalized_roles
    }
    raw_extensions: dict[str, Any] = {
        **({"facility_areas": {key: value.model_dump(mode="json") if value else None
                              for key, value in request.facility_areas.items()}}
           if request.facility_areas else {}),
        "additional_income_raw": request.additional_income_raw.model_dump(mode="json") if request.additional_income_raw else None,
        "activation_sources": {item.process_id: item.activation_source for item in request.processes},
        "role_allocations_raw": {item.role_id: item.allocation_shares for item in request.roles if item.allocation_shares is not None},
        "unaccepted_salary_raw": {
            item.role_id: item.monthly_gross_salary.model_dump(mode="json")
            for item in request.roles
            if item.monthly_gross_salary is not None
            and isinstance(normalized_salary_by_role[item.role_id], MissingQuantity)
        },
        "legacy_import_version": request.legacy_import_version,
        "source_profile_version": request.source_profile_version,
        "raw_profile_parameters": request.raw_profile_parameters,
    }
    return NormalizationResponseV2(valid=not errors, input_revision=request.input_revision, object_id=request.object_id, normalized_processes=normalized_processes, role_pool=role_pool, errors=errors, required_inputs=required, conversions=conversions, raw_extensions=raw_extensions)


def process_projection(object_kind: ObjectKind) -> list[dict[str, Any]]:
    """Return the immutable K19 block projection for one object kind."""

    return [
        {
            "process_code": code.value,
            "scope": definition.scope.value,
            "suggested_roles": [role.value for role in definition.roles],
            "allowed_quantity_kinds": [kind.value for kind in definition.allowed_kinds],
        }
        for code, definition in PROCESS_DEFINITIONS.items()
        if definition.object_kind == object_kind
    ]


_PROFILE_ADAPTERS: dict[str, dict[str, Any]] = {
    "warehouse": {
        "object": ObjectKind.WAREHOUSE,
        "active": ProcessCode.WAREHOUSE_RECEIVING_SHIPPING,
        "kind": ProcessQuantityKind.PALLET,
        "demand_codes": ("obem_priemki_poddony_sutki", "obem_otgruzki_poddony_sutki"),
        "shifts": "kolichestvo_rabochih_smen_v_sutki",
        "hours": "prodolzhitelnost_smeny",
        "days": "rabochih_dney_v_godu",
        "role": RoleCode.FORKLIFT_DRIVER,
        "headcount": "iz_nih_operatory_pogruzchikov",
    },
    "airport": {
        "object": ObjectKind.AIRPORT,
        "active": ProcessCode.AIRPORT_BAGGAGE,
        "kind": ProcessQuantityKind.ITEM,
        "demand_codes": ("obem_peremescheniya_bagazha_edinic_sutki",),
        "role": RoleCode.BAGGAGE_HANDLER,
        "headcount": "chislennost_personala_nazemnogo_obsluzhivaniya_ramp",
        "schedule": ("3", "8", "365"),
    },
    "medical_facility": {
        "object": ObjectKind.CLINIC,
        "active": ProcessCode.CLINIC_FOOD,
        "kind": ProcessQuantityKind.PORTION,
        "demand_codes": ("obschee_kolichestvo_porciy_pitaniya_v_sutki",),
        "shifts": "kolichestvo_smen_medpersonala_uhod_za_pacientami",
        "role": RoleCode.CATERING_WORKER,
        "headcount": "chislennost_sotrudnikov_pischebloka_razdacha",
        "schedule": (None, "8", "365"),
    },
}


def adapt_project_file_v1(result: Any, *, input_revision: str, object_id: str) -> CalculationIntakeRequestV2:
    """Compatibility adapter for a valid existing ``IntakeResult``.

    The legacy normalized ``UserInput`` remains untouched.  The adapter reads
    its accepted raw parameter set and file provenance, preserving all 42/39/57
    values so existing import runs can be replayed independently.
    """

    if not getattr(result, "valid", False):
        raise ValueError("legacy intake must be valid before v2 adaptation")
    config = _PROFILE_ADAPTERS[result.profile_code]
    values = result.parameter_values
    def provenance(parameter_code: str, *, raw_text: str | None = None) -> RawProvenance:
        location = result.parameter_provenance[parameter_code]["source"]
        return RawProvenance(
            source=RawSource.FILE,
            file_name=result.original_name,
            file_sha256=result.sha256,
            sheet=location.get("sheet"),
            row=location.get("row"),
            cell=location.get("cell"),
            raw_text=raw_text,
            alias=parameter_code,
        )

    file_provenance = provenance(config["demand_codes"][0], raw_text=" + ".join(config["demand_codes"]))
    demand = sum(float(values[code]) for code in config["demand_codes"])
    demand_text = canonical_decimal(str(demand))
    demand_unit = str(PROCESS_DEMAND_UNITS[str(config["kind"])])
    if "schedule" in config:
        shifts, hours, days = config["schedule"]
        if shifts is None:
            shifts = str(values[config["shifts"]])
    else:
        shifts, hours, days = (str(values[config["shifts"]]), str(values[config["hours"]]), str(values[config["days"]]))
    schedule = ProcessScheduleInput(
        shifts_per_day=RawQuantity(value=canonical_decimal(shifts), unit="shift", provenance=provenance(config.get("shifts", config["demand_codes"][0]))),
        shift_hours=RawQuantity(value=canonical_decimal(hours), unit="h", provenance=provenance(config.get("hours", config["demand_codes"][0]))),
        days_per_year=RawQuantity(value=canonical_decimal(days), unit="day", provenance=provenance(config.get("days", config["demand_codes"][0]))),
    )
    role_id = f"{object_id}.{config['role'].value}"
    processes: list[ProcessIntake] = []
    for code, definition in PROCESS_DEFINITIONS.items():
        if definition.object_kind != config["object"]:
            continue
        active = code == config["active"]
        processes.append(ProcessIntake(
            block_id=f"block.{code.value}",
            process_id=f"{object_id}.{code.value}",
            process_code=code,
            active=active,
            activation_source=ActivationSource.LEGACY_V1,
            quantity_kind=config["kind"] if active else definition.allowed_kinds[0],
            demand=RawQuantity(value=demand_text, unit=demand_unit, provenance=file_provenance) if active else None,
            schedule=schedule if active else None,
            role_refs=[role_id] if active else [],
        ))
    active_process_id = f"{object_id}.{config['active'].value}"
    role = RoleIntake(
        role_id=role_id,
        object_scope=config["object"],
        role_code=config["role"],
        headcount=RawQuantity(value=canonical_decimal(str(values[config["headcount"]])), unit="person", provenance=provenance(config["headcount"])),
        monthly_gross_salary=None,
        process_ids=[active_process_id],
    )
    return CalculationIntakeRequestV2(
        input_revision=input_revision,
        object_id=object_id,
        object_kind=config["object"],
        processes=processes,
        roles=[role],
        legacy_import_version="project-file-intake-v1",
        source_profile_version=result.profile_version,
        raw_profile_parameters={code: {"value": value, "provenance": result.parameter_provenance[code]} for code, value in values.items()},
    )
