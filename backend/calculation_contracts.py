"""Strict, additive calculation semantics contracts for C01.

These DTOs describe normalized inputs, partial results and reproducible traces.
They intentionally do not execute formulas and are not wired to production API
routes.  Decimal values cross the contract boundary as canonical strings.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


CALCULATION_POLICY_VERSION = "hackathon-calculation-policy-v1"
PRECISION_POLICY_VERSION = "decimal-context-28-half-even-v1"
PROCESS_CATALOG_VERSION = "calculation-process-catalog-v1"
FORMULA_BUNDLE_VERSION = "calculation-formulas-v1"
CONSTRAINT_RULES_VERSION = "calculation-constraints-v1"
COMMERCIAL_POLICY_VERSION = "hackathon-commercial-policy-v1"

DecimalString = Annotated[
    str,
    Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"),
]
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
StableId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$")]


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ObjectKind(StrEnum):
    WAREHOUSE = "WAREHOUSE"
    AIRPORT = "AIRPORT"
    CLINIC = "CLINIC"


class ProcessCode(StrEnum):
    WAREHOUSE_RECEIVING_SHIPPING = "warehouse_receiving_shipping"
    WAREHOUSE_STORAGE = "warehouse_storage"
    WAREHOUSE_PICKING = "warehouse_picking"
    WAREHOUSE_PALLETIZING = "warehouse_palletizing"
    WAREHOUSE_CLEANING = "warehouse_cleaning"
    WAREHOUSE_INVENTORY = "warehouse_inventory"
    AIRPORT_BAGGAGE = "airport_baggage"
    AIRPORT_CATERING = "airport_catering"
    AIRPORT_FUELLING = "airport_fuelling"
    AIRPORT_INTERNAL_LOGISTICS = "airport_internal_logistics"
    AIRPORT_TERMINAL_CLEANING = "airport_terminal_cleaning"
    AIRPORT_APRON_CLEANING = "airport_apron_cleaning"
    AIRPORT_WASTE = "airport_waste"
    AIRPORT_INSPECTION = "airport_inspection"
    AIRPORT_PASSENGER_ASSISTANCE = "airport_passenger_assistance"
    AIRPORT_GROUND_SERVICE = "airport_ground_service"
    CLINIC_FOOD = "clinic_food"
    CLINIC_LINEN = "clinic_linen"
    CLINIC_MEDICINES = "clinic_medicines"
    CLINIC_BIOMATERIALS = "clinic_biomaterials"
    CLINIC_STERILE_SETS = "clinic_sterile_sets"
    CLINIC_CONSUMABLES = "clinic_consumables"
    CLINIC_WASTE_A = "clinic_waste_a"
    CLINIC_WASTE_B = "clinic_waste_b"
    CLINIC_RESULTS = "clinic_results"
    CLINIC_CLEANING = "clinic_cleaning"
    CLINIC_INVENTORY = "clinic_inventory"
    CLINIC_SAFETY_REQUIREMENTS = "clinic_safety_requirements"


class ProcessScope(StrEnum):
    TRANSPORT_CYCLE = "TRANSPORT_CYCLE"
    DELIVERY_CYCLE = "DELIVERY_CYCLE"
    CLEANING_AREA = "CLEANING_AREA"
    FIXED_CELL = "FIXED_CELL"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    SCENARIO_ONLY = "SCENARIO_ONLY"
    CONSTRAINT_ONLY = "CONSTRAINT_ONLY"


class RoleCode(StrEnum):
    FORKLIFT_DRIVER = "forklift_driver"
    LOADER = "loader"
    STOREKEEPER = "storekeeper"
    PICKER = "picker"
    SORTER = "sorter"
    PACKER = "packer"
    CLEANER = "cleaner"
    INVENTORY_WORKER = "inventory_worker"
    BAGGAGE_HANDLER = "baggage_handler"
    TROLLEY_OPERATOR = "trolley_operator"
    SPECIAL_EQUIPMENT_DRIVER = "special_equipment_driver"
    TERMINAL_CLEANER = "terminal_cleaner"
    PERRON_CLEANER = "perron_cleaner"
    RUNWAY_INSPECTOR = "runway_inspector"
    SECURITY_GUARD = "security_guard"
    PASSENGER_ASSISTANT = "passenger_assistant"
    COURIER = "courier"
    RAMP_WORKER = "ramp_worker"
    GROUND_SUPPORT_WORKER = "ground_support_worker"
    CATERING_WORKER = "catering_worker"
    LAUNDRY_WORKER = "laundry_worker"
    SANITARY = "sanitary"
    PORTER = "porter"
    LAB_ASSISTANT = "lab_assistant"
    STERILE_SUPPLY_WORKER = "sterile_supply_worker"
    CONSUMABLE_WORKER = "consumable_worker"
    LAB_RESULT_COURIER = "lab_result_courier"
    TECH_SUPPORT = "tech_support"
    CONTROL_OPERATOR = "control_operator"


class QuantityKind(StrEnum):
    TIME = "TIME"
    DISTANCE = "DISTANCE"
    MASS = "MASS"
    AREA = "AREA"
    COUNT = "COUNT"
    FLOW = "FLOW"
    SPEED = "SPEED"
    RATE = "RATE"
    FRACTION = "FRACTION"
    MONEY = "MONEY"
    ENERGY = "ENERGY"
    POWER = "POWER"
    UNIT_DEFINITION = "UNIT_DEFINITION"


class ProcessQuantityKind(StrEnum):
    PALLET = "PALLET"
    BOX = "BOX"
    CASE = "CASE"
    CART = "CART"
    DELIVERY = "DELIVERY"
    PORTION = "PORTION"
    KILOGRAM = "KILOGRAM"
    SAMPLE = "SAMPLE"
    SET = "SET"
    BIN = "BIN"
    ITEM = "ITEM"
    SQUARE_METER = "SQUARE_METER"
    PICK = "PICK"
    DIGITAL_FLOW = "DIGITAL_FLOW"


class Unit(StrEnum):
    SECOND = "s"
    HOUR = "h"
    DAY = "day"
    METER = "m"
    KILOGRAM = "kg"
    SQUARE_METER = "m2"
    UNIT = "unit"
    PERSON = "person"
    ROBOT = "robot"
    SHIFT = "shift"
    TRIP = "trip"
    UNIT_PER_DAY = "unit/day"
    PALLET_PER_DAY = "pallet/day"
    BOX_PER_DAY = "box/day"
    CASE_PER_DAY = "case/day"
    CART_PER_DAY = "cart/day"
    DELIVERY_PER_DAY = "delivery/day"
    PORTION_PER_DAY = "portion/day"
    KILOGRAM_PER_DAY = "kg/day"
    SAMPLE_PER_DAY = "sample/day"
    SET_PER_DAY = "set/day"
    BIN_PER_DAY = "bin/day"
    ITEM_PER_DAY = "item/day"
    PICK_PER_DAY = "pick/day"
    SQUARE_METER_PER_DAY = "m2/day"
    UNIT_PER_HOUR = "unit/h"
    TRIP_PER_HOUR = "trip/h"
    SECOND_PER_HOUR = "s/h"
    MINUTE_PER_HOUR = "min/h"
    PER_DAY = "1/day"
    SQUARE_METER_PER_HOUR = "m2/h"
    UNIT_PER_MINUTE = "unit/min"
    PICK_PER_MINUTE = "pick/min"
    PICK_PER_HOUR = "pick/h"
    PALLET_PER_MINUTE = "pallet/min"
    BOX_PER_PALLET = "box/pallet"
    METER_PER_SECOND = "m/s"
    KILOGRAM_PER_UNIT = "kg/unit"
    UNIT_PER_TRIP = "unit/trip"
    UNIT_PER_CYCLE = "unit/cycle"
    DIMENSIONLESS = "1"
    PERCENT = "%"
    RUB = "RUB"
    RUB_PER_PERSON_MONTH = "RUB/person/month"
    KILOWATT_HOUR = "kWh"
    WATT = "W"


UNIT_KINDS: dict[str, QuantityKind] = {
    "s": QuantityKind.TIME,
    "h": QuantityKind.TIME,
    "day": QuantityKind.TIME,
    "m": QuantityKind.DISTANCE,
    "kg": QuantityKind.MASS,
    "m2": QuantityKind.AREA,
    "unit": QuantityKind.COUNT,
    "person": QuantityKind.COUNT,
    "robot": QuantityKind.COUNT,
    "shift": QuantityKind.COUNT,
    "trip": QuantityKind.COUNT,
    "unit/day": QuantityKind.FLOW,
    "pallet/day": QuantityKind.FLOW,
    "box/day": QuantityKind.FLOW,
    "case/day": QuantityKind.FLOW,
    "cart/day": QuantityKind.FLOW,
    "delivery/day": QuantityKind.FLOW,
    "portion/day": QuantityKind.FLOW,
    "kg/day": QuantityKind.FLOW,
    "sample/day": QuantityKind.FLOW,
    "set/day": QuantityKind.FLOW,
    "bin/day": QuantityKind.FLOW,
    "item/day": QuantityKind.FLOW,
    "pick/day": QuantityKind.FLOW,
    "m2/day": QuantityKind.FLOW,
    "unit/h": QuantityKind.RATE,
    "trip/h": QuantityKind.RATE,
    "s/h": QuantityKind.UNIT_DEFINITION,
    "min/h": QuantityKind.UNIT_DEFINITION,
    "1/day": QuantityKind.RATE,
    "m2/h": QuantityKind.RATE,
    "unit/min": QuantityKind.RATE,
    "pick/min": QuantityKind.RATE,
    "pick/h": QuantityKind.RATE,
    "pallet/min": QuantityKind.RATE,
    "box/pallet": QuantityKind.RATE,
    "m/s": QuantityKind.SPEED,
    "kg/unit": QuantityKind.RATE,
    "unit/trip": QuantityKind.RATE,
    "unit/cycle": QuantityKind.RATE,
    "1": QuantityKind.FRACTION,
    "%": QuantityKind.FRACTION,
    "RUB": QuantityKind.MONEY,
    "RUB/person/month": QuantityKind.MONEY,
    "kWh": QuantityKind.ENERGY,
    "W": QuantityKind.POWER,
}


class QuantityName(StrEnum):
    SHIFTS_PER_DAY = "shifts_per_day"
    SHIFT_HOURS = "shift_hours"
    OPERATING_HOURS_PER_DAY = "operating_hours_per_day"
    DAYS_PER_YEAR = "days_per_year"
    DEMAND_PER_DAY = "demand_per_day"
    CLEANING_AREA = "cleaning_area"
    TOTAL_AREA = "total_area"
    CLEANING_AREA_SHARE = "cleaning_area_share"
    CLEANING_AREA_PER_DAY = "cleaning_area_per_day"
    PEAK_FACTOR = "peak_factor"
    RESERVE_SHARE = "reserve_share"
    ONE_WAY_DISTANCE = "one_way_distance"
    EXCHANGE_TOTAL_TIME = "exchange_total_time"
    LOAD_TIME = "load_time"
    UNLOAD_TIME = "unload_time"
    OPERATING_SPEED = "operating_speed"
    SAFE_MAX_SPEED = "safe_max_speed"
    PAYLOAD = "payload"
    ITEM_MASS = "item_mass"
    HANDLING_BATCH_LIMIT = "handling_batch_limit"
    PASSPORT_BATCH_LIMIT = "passport_batch_limit"
    GEOMETRY_BATCH_LIMIT = "geometry_batch_limit"
    UNITS_PER_TRIP = "units_per_trip"
    CYCLE_TIME = "cycle_time"
    UNITS_PER_CYCLE = "units_per_cycle"
    TRIPS_PER_HOUR = "trips_per_hour"
    SECONDS_PER_HOUR = "seconds_per_hour"
    REQUIRED_CAPACITY = "required_capacity"
    FLEET_CAPACITY = "fleet_capacity"
    CLEANING_FREQUENCY = "cleaning_frequency"
    CLEANING_RATE = "cleaning_rate"
    CELL_RATE = "cell_rate"
    CELL_EFFICIENCY = "cell_efficiency"
    MINUTES_PER_HOUR = "minutes_per_hour"
    PICKS_PER_HOUR = "picks_per_hour"
    BOXES_PER_PALLET = "boxes_per_pallet"
    BOXES_PER_DAY = "boxes_per_day"
    PALLETS_PER_DAY = "pallets_per_day"
    AVAILABILITY = "availability"
    FLEET_SELECTED = "fleet_selected"
    FLEET_RECOMMENDED = "fleet_recommended"
    NOMINAL_CAPACITY = "nominal_capacity"
    EFFECTIVE_CAPACITY = "effective_capacity"
    COVERAGE = "coverage"
    RAW_LOAD_RATIO = "raw_load_ratio"
    UTILIZATION = "utilization"
    ROLE_HEADCOUNT = "role_headcount"
    MONTHLY_GROSS_SALARY = "monthly_gross_salary"


NORMALIZED_UNITS: dict[str, Unit] = {
    QuantityName.SHIFTS_PER_DAY: Unit.SHIFT,
    QuantityName.SHIFT_HOURS: Unit.HOUR,
    QuantityName.OPERATING_HOURS_PER_DAY: Unit.HOUR,
    QuantityName.DAYS_PER_YEAR: Unit.DAY,
    QuantityName.DEMAND_PER_DAY: Unit.UNIT_PER_DAY,
    QuantityName.CLEANING_AREA_PER_DAY: Unit.SQUARE_METER_PER_DAY,
    QuantityName.PEAK_FACTOR: Unit.DIMENSIONLESS,
    QuantityName.RESERVE_SHARE: Unit.DIMENSIONLESS,
    QuantityName.ONE_WAY_DISTANCE: Unit.METER,
    QuantityName.EXCHANGE_TOTAL_TIME: Unit.SECOND,
    QuantityName.LOAD_TIME: Unit.SECOND,
    QuantityName.UNLOAD_TIME: Unit.SECOND,
    QuantityName.OPERATING_SPEED: Unit.METER_PER_SECOND,
    QuantityName.SAFE_MAX_SPEED: Unit.METER_PER_SECOND,
    QuantityName.PAYLOAD: Unit.KILOGRAM,
    QuantityName.ITEM_MASS: Unit.KILOGRAM_PER_UNIT,
    QuantityName.HANDLING_BATCH_LIMIT: Unit.UNIT_PER_TRIP,
    QuantityName.PASSPORT_BATCH_LIMIT: Unit.UNIT_PER_TRIP,
    QuantityName.GEOMETRY_BATCH_LIMIT: Unit.UNIT_PER_TRIP,
    QuantityName.UNITS_PER_TRIP: Unit.UNIT_PER_TRIP,
    QuantityName.CYCLE_TIME: Unit.SECOND,
    QuantityName.UNITS_PER_CYCLE: Unit.UNIT_PER_CYCLE,
    QuantityName.TRIPS_PER_HOUR: Unit.TRIP_PER_HOUR,
    QuantityName.SECONDS_PER_HOUR: Unit.SECOND_PER_HOUR,
    QuantityName.REQUIRED_CAPACITY: Unit.UNIT_PER_HOUR,
    QuantityName.FLEET_CAPACITY: Unit.UNIT_PER_HOUR,
    QuantityName.CLEANING_AREA: Unit.SQUARE_METER,
    QuantityName.TOTAL_AREA: Unit.SQUARE_METER,
    QuantityName.CLEANING_AREA_SHARE: Unit.DIMENSIONLESS,
    QuantityName.CLEANING_FREQUENCY: Unit.PER_DAY,
    QuantityName.CLEANING_RATE: Unit.SQUARE_METER_PER_HOUR,
    QuantityName.CELL_RATE: Unit.PICK_PER_MINUTE,
    QuantityName.CELL_EFFICIENCY: Unit.DIMENSIONLESS,
    QuantityName.MINUTES_PER_HOUR: Unit.MINUTE_PER_HOUR,
    QuantityName.PICKS_PER_HOUR: Unit.PICK_PER_HOUR,
    QuantityName.BOXES_PER_PALLET: Unit.BOX_PER_PALLET,
    QuantityName.BOXES_PER_DAY: Unit.BOX_PER_DAY,
    QuantityName.PALLETS_PER_DAY: Unit.PALLET_PER_DAY,
    QuantityName.AVAILABILITY: Unit.DIMENSIONLESS,
    QuantityName.FLEET_SELECTED: Unit.ROBOT,
    QuantityName.FLEET_RECOMMENDED: Unit.ROBOT,
    QuantityName.NOMINAL_CAPACITY: Unit.UNIT_PER_HOUR,
    QuantityName.EFFECTIVE_CAPACITY: Unit.UNIT_PER_HOUR,
    QuantityName.COVERAGE: Unit.DIMENSIONLESS,
    QuantityName.RAW_LOAD_RATIO: Unit.DIMENSIONLESS,
    QuantityName.UTILIZATION: Unit.DIMENSIONLESS,
    QuantityName.ROLE_HEADCOUNT: Unit.PERSON,
    QuantityName.MONTHLY_GROSS_SALARY: Unit.RUB_PER_PERSON_MONTH,
}

PROCESS_DEMAND_UNITS: dict[str, Unit] = {
    ProcessQuantityKind.PALLET: Unit.PALLET_PER_DAY,
    ProcessQuantityKind.BOX: Unit.BOX_PER_DAY,
    ProcessQuantityKind.CASE: Unit.CASE_PER_DAY,
    ProcessQuantityKind.CART: Unit.CART_PER_DAY,
    ProcessQuantityKind.DELIVERY: Unit.DELIVERY_PER_DAY,
    ProcessQuantityKind.PORTION: Unit.PORTION_PER_DAY,
    ProcessQuantityKind.KILOGRAM: Unit.KILOGRAM_PER_DAY,
    ProcessQuantityKind.SAMPLE: Unit.SAMPLE_PER_DAY,
    ProcessQuantityKind.SET: Unit.SET_PER_DAY,
    ProcessQuantityKind.BIN: Unit.BIN_PER_DAY,
    ProcessQuantityKind.ITEM: Unit.ITEM_PER_DAY,
    ProcessQuantityKind.SQUARE_METER: Unit.SQUARE_METER_PER_DAY,
    ProcessQuantityKind.PICK: Unit.PICK_PER_DAY,
    ProcessQuantityKind.DIGITAL_FLOW: Unit.ITEM_PER_DAY,
}
DEMAND_UNITS = frozenset(PROCESS_DEMAND_UNITS.values())


class MissingReason(StrEnum):
    MISSING_INPUT = "MISSING_INPUT"
    MISSING_SAFE_FACT = "MISSING_SAFE_FACT"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    CONFLICTING_FACT = "CONFLICTING_FACT"
    UNAPPROVED_ASSUMPTION = "UNAPPROVED_ASSUMPTION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class KnownQuantity(StrictContractModel):
    status: Literal["KNOWN"] = "KNOWN"
    name: QuantityName
    raw_value: DecimalString
    raw_unit: Unit
    normalized_value: DecimalString
    unit: Unit
    quantity_kind: QuantityKind
    numeric_encoding: Literal["DECIMAL_STRING"] = "DECIMAL_STRING"
    provenance_ref: StableId

    @model_validator(mode="after")
    def validate_units(self) -> KnownQuantity:
        if UNIT_KINDS[str(self.raw_unit)] != self.quantity_kind:
            raise ValueError("raw_unit is incompatible with quantity_kind")
        if UNIT_KINDS[str(self.unit)] != self.quantity_kind:
            raise ValueError("unit is incompatible with quantity_kind")
        expected = NORMALIZED_UNITS[str(self.name)]
        if self.name == QuantityName.DEMAND_PER_DAY:
            if self.unit not in DEMAND_UNITS:
                raise ValueError("demand_per_day requires a typed demand unit")
        elif self.unit != expected:
            raise ValueError(f"{self.name} must normalize to {expected}")
        return self


class MissingQuantity(StrictContractModel):
    status: Literal["MISSING"] = "MISSING"
    name: QuantityName
    quantity_kind: QuantityKind
    expected_unit: Unit
    missing_reason: MissingReason
    provenance_ref: StableId | None = None

    @model_validator(mode="after")
    def validate_expected_unit(self) -> MissingQuantity:
        if UNIT_KINDS[str(self.expected_unit)] != self.quantity_kind:
            raise ValueError("expected_unit is incompatible with quantity_kind")
        expected = NORMALIZED_UNITS[str(self.name)]
        if self.name == QuantityName.DEMAND_PER_DAY:
            if self.expected_unit not in DEMAND_UNITS:
                raise ValueError("demand_per_day requires a typed demand unit")
        elif self.expected_unit != expected:
            raise ValueError("expected_unit is not canonical for quantity name")
        return self


InputQuantity: TypeAlias = Annotated[
    KnownQuantity | MissingQuantity, Field(discriminator="status")
]


class TotalExchange(StrictContractModel):
    mode: Literal["TOTAL"] = "TOTAL"
    total_time: KnownQuantity

    @model_validator(mode="after")
    def validate_semantics(self) -> TotalExchange:
        if self.total_time.name != QuantityName.EXCHANGE_TOTAL_TIME:
            raise ValueError("total exchange requires exchange_total_time")
        return self


class SplitExchange(StrictContractModel):
    mode: Literal["SPLIT"] = "SPLIT"
    load_time: KnownQuantity
    unload_time: KnownQuantity

    @model_validator(mode="after")
    def validate_semantics(self) -> SplitExchange:
        if self.load_time.name != QuantityName.LOAD_TIME:
            raise ValueError("split exchange requires load_time")
        if self.unload_time.name != QuantityName.UNLOAD_TIME:
            raise ValueError("split exchange requires unload_time")
        return self


ExchangeTime: TypeAlias = Annotated[
    TotalExchange | SplitExchange, Field(discriminator="mode")
]


class ProcessSchedule(StrictContractModel):
    shifts_per_day: KnownQuantity
    shift_hours: KnownQuantity
    days_per_year: KnownQuantity

    @model_validator(mode="after")
    def validate_domain(self) -> ProcessSchedule:
        required_names = (
            (self.shifts_per_day, QuantityName.SHIFTS_PER_DAY),
            (self.shift_hours, QuantityName.SHIFT_HOURS),
            (self.days_per_year, QuantityName.DAYS_PER_YEAR),
        )
        for quantity, name in required_names:
            if quantity.name != name:
                raise ValueError(f"schedule field must be {name}")
        shifts = _decimal(self.shifts_per_day.normalized_value)
        hours = _decimal(self.shift_hours.normalized_value)
        days = _decimal(self.days_per_year.normalized_value)
        if shifts not in (1, 2, 3):
            raise ValueError("shifts_per_day must be 1..3")
        if hours not in (6, 8, 10, 11, 12):
            raise ValueError("shift_hours must be an allowed discrete value")
        if shifts * hours > 24:
            raise ValueError("daily operating hours cannot exceed 24")
        if days < 1 or days > 366 or days != days.to_integral_value():
            raise ValueError("days_per_year must be an integer in 1..366")
        return self


class RoleEntry(StrictContractModel):
    role_id: StableId
    object_scope: ObjectKind | Literal["SITE"]
    role_code: RoleCode
    label: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    headcount: InputQuantity
    monthly_gross_salary: InputQuantity
    zero_cost_marker: Literal["ZERO_COST_ROLE"] | None = None
    process_ids: list[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_role_quantities(self) -> RoleEntry:
        if self.headcount.name != QuantityName.ROLE_HEADCOUNT:
            raise ValueError("headcount must use role_headcount semantics")
        if self.monthly_gross_salary.name != QuantityName.MONTHLY_GROSS_SALARY:
            raise ValueError("salary must use monthly_gross_salary semantics")
        if isinstance(self.monthly_gross_salary, KnownQuantity):
            salary = _decimal(self.monthly_gross_salary.normalized_value)
            if salary < 0:
                raise ValueError("salary cannot be negative")
            if salary == 0 and self.zero_cost_marker != "ZERO_COST_ROLE":
                raise ValueError("zero salary requires ZERO_COST_ROLE")
            if salary > 0 and self.zero_cost_marker is not None:
                raise ValueError("ZERO_COST_ROLE is only valid for zero salary")
        return self


class RolePool(StrictContractModel):
    schema_version: Literal["role-pool-v1"] = "role-pool-v1"
    pool_id: StableId
    object_kind: ObjectKind
    roles: list[RoleEntry]

    @model_validator(mode="after")
    def validate_identities(self) -> RolePool:
        identities = [(role.object_scope, role.role_code) for role in self.roles]
        if len(identities) != len(set(identities)):
            raise ValueError("role identity is object-scoped and must be unique")
        for role in self.roles:
            if role.object_scope not in (self.object_kind, "SITE"):
                raise ValueError("role object_scope does not match pool object")
        return self


class NormalizedProcess(StrictContractModel):
    schema_version: Literal["normalized-process-v1"] = "normalized-process-v1"
    process_id: StableId
    input_revision: StableId
    object_kind: ObjectKind
    process_code: ProcessCode
    scope: ProcessScope
    active: bool
    quantity_kind: ProcessQuantityKind
    demand: InputQuantity
    schedule: ProcessSchedule | None = None
    route_distance: InputQuantity | None = None
    exchange: ExchangeTime | None = None
    item_mass: InputQuantity | None = None
    explicit_batch: InputQuantity | None = None
    role_refs: list[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_process(self) -> NormalizedProcess:
        prefix = self.process_code.split("_", 1)[0].upper()
        if prefix != self.object_kind:
            raise ValueError("process_code does not belong to object_kind")
        if self.demand.quantity_kind != QuantityKind.FLOW:
            raise ValueError("process demand must have FLOW dimension")
        expected_demand_unit = PROCESS_DEMAND_UNITS[str(self.quantity_kind)]
        demand_unit = (
            self.demand.unit
            if isinstance(self.demand, KnownQuantity)
            else self.demand.expected_unit
        )
        if demand_unit != expected_demand_unit:
            raise ValueError("demand unit does not match process quantity_kind")
        if self.active:
            if not isinstance(self.demand, KnownQuantity):
                raise ValueError("active process requires known demand")
            if _decimal(self.demand.normalized_value) <= 0:
                raise ValueError("active process demand must be positive")
        if self.scope in (ProcessScope.TRANSPORT_CYCLE, ProcessScope.DELIVERY_CYCLE):
            if self.route_distance is not None and (
                self.route_distance.name != QuantityName.ONE_WAY_DISTANCE
            ):
                raise ValueError("route_distance must be one_way_distance")
        if self.explicit_batch is not None and (
            self.explicit_batch.name != QuantityName.UNITS_PER_TRIP
        ):
            raise ValueError("explicit_batch must be units_per_trip")
        return self


class BlockerReason(StrEnum):
    MISSING_INPUT = "MISSING_INPUT"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    UNSUPPORTED_PROCESS_PROFILE = "UNSUPPORTED_PROCESS_PROFILE"
    MISSING_SAFE_FACT = "MISSING_SAFE_FACT"
    CONFLICTING_FACT = "CONFLICTING_FACT"
    UNAPPROVED_ASSUMPTION = "UNAPPROVED_ASSUMPTION"
    INVALID_DOMAIN = "INVALID_DOMAIN"
    UNKNOWN_POLICY_VERSION = "UNKNOWN_POLICY_VERSION"
    MISSING_COMMERCIAL_TERMS = "MISSING_COMMERCIAL_TERMS"
    MISSING_ROLE_SALARY = "MISSING_ROLE_SALARY"
    UNKNOWN_TAX_BASIS = "UNKNOWN_TAX_BASIS"


class ContractIssue(StrictContractModel):
    code: StableId
    reason: BlockerReason
    severity: Literal["WARNING", "BLOCKER"]
    field_refs: list[Annotated[str, Field(min_length=1)]]
    node_refs: list[StableId] = Field(default_factory=list)
    decision_refs: list[Annotated[str, Field(pattern=r"^K(?:0[1-9]|[12][0-9])$")]] = Field(
        default_factory=list
    )
    message: Annotated[str, Field(min_length=1, max_length=500)]


class ResultQuantity(StrictContractModel):
    value: DecimalString
    unit: Unit
    quantity_kind: QuantityKind
    numeric_encoding: Literal["DECIMAL_STRING"] = "DECIMAL_STRING"

    @model_validator(mode="after")
    def validate_unit(self) -> ResultQuantity:
        if UNIT_KINDS[str(self.unit)] != self.quantity_kind:
            raise ValueError("result unit is incompatible with quantity_kind")
        return self


class CapacityValues(StrictContractModel):
    recommended_fleet: Annotated[int, Field(ge=0)]
    selected_fleet: Annotated[int, Field(ge=0)]
    nominal_capacity: ResultQuantity
    effective_capacity: ResultQuantity
    coverage: ResultQuantity
    raw_load_ratio: ResultQuantity | None
    utilization: ResultQuantity | None
    overloaded: bool

    @model_validator(mode="after")
    def validate_zero_fleet(self) -> CapacityValues:
        if self.selected_fleet == 0:
            if _decimal(self.effective_capacity.value) != 0:
                raise ValueError("fleet 0 requires effective capacity 0")
            if _decimal(self.coverage.value) != 0:
                raise ValueError("fleet 0 requires coverage 0")
            if self.utilization is not None:
                raise ValueError("fleet 0 requires null utilization")
            if not self.overloaded:
                raise ValueError("fleet 0 with active demand is overloaded")
        if self.utilization is not None:
            utilization = _decimal(self.utilization.value)
            if utilization < 0 or utilization > 1:
                raise ValueError("display utilization must be in 0..1")
        return self


class CapacityResult(StrictContractModel):
    schema_version: Literal["capacity-result-v1"] = "capacity-result-v1"
    process_id: StableId
    status: Literal["COMPLETE", "WITH_ASSUMPTIONS", "BLOCKED", "NOT_APPLICABLE"]
    value: CapacityValues | None
    blockers: list[ContractIssue] = Field(default_factory=list)
    warnings: list[ContractIssue] = Field(default_factory=list)
    trace_ref: StableId

    @model_validator(mode="after")
    def validate_status(self) -> CapacityResult:
        if self.status in ("COMPLETE", "WITH_ASSUMPTIONS") and self.value is None:
            raise ValueError("completed capacity requires a value")
        if self.status == "BLOCKED" and (self.value is not None or not self.blockers):
            raise ValueError("blocked capacity requires null value and blockers")
        if self.status == "NOT_APPLICABLE" and self.value is not None:
            raise ValueError("not-applicable capacity requires null value")
        return self


class FinancialValues(StrictContractModel):
    capex: ResultQuantity
    annual_opex: ResultQuantity
    annual_effect: ResultQuantity
    npv: ResultQuantity | None = None


class FinancialResult(StrictContractModel):
    schema_version: Literal["financial-result-v1"] = "financial-result-v1"
    process_id: StableId
    status: Literal["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    benefit_status: Literal["POSITIVE", "NON_POSITIVE", "UNKNOWN", "NOT_APPLICABLE"]
    value: FinancialValues | None
    blockers: list[ContractIssue] = Field(default_factory=list)
    warnings: list[ContractIssue] = Field(default_factory=list)
    trace_ref: StableId | None = None

    @model_validator(mode="after")
    def validate_status(self) -> FinancialResult:
        if self.status == "COMPLETE" and self.value is None:
            raise ValueError("complete finance requires a value")
        if self.status == "INCOMPLETE" and (self.value is not None or not self.blockers):
            raise ValueError("incomplete finance requires null value and blockers")
        if self.status == "NOT_APPLICABLE" and self.value is not None:
            raise ValueError("not-applicable finance requires null value")
        return self


class PartialCalculationResult(StrictContractModel):
    schema_version: Literal["calculation-partial-result-v1"] = (
        "calculation-partial-result-v1"
    )
    result_status: Literal["CAPACITY_ONLY", "PARTIAL", "COMPLETE"]
    capacity: CapacityResult
    financial: FinancialResult | None = None

    @model_validator(mode="after")
    def validate_independence(self) -> PartialCalculationResult:
        if self.result_status == "CAPACITY_ONLY" and self.financial is not None:
            raise ValueError("CAPACITY_ONLY must omit financial result")
        if self.result_status == "COMPLETE" and (
            self.capacity.status not in ("COMPLETE", "WITH_ASSUMPTIONS")
            or self.financial is None
            or self.financial.status != "COMPLETE"
        ):
            raise ValueError("COMPLETE requires independently complete layers")
        if self.result_status == "PARTIAL" and self.financial is None:
            raise ValueError("PARTIAL must include the incomplete layer")
        return self


class OperatingAvailabilityV1(StrictContractModel):
    schema_version: Literal['operating-availability-v1'] = 'operating-availability-v1'
    mode: Literal['ALL_IN', 'EXPLICIT_DOWNTIME']
    availability: DecimalString | None = None
    autonomy_hours: DecimalString | None = None
    charge_hours: DecimalString | None = None
    service_hours_per_day: DecimalString | None = None
    refill_hours_per_day: DecimalString | None = None
    basis: Annotated[str, Field(min_length=3, max_length=500)]
    source: Literal['USER', 'ASSUMPTION']
    confirmed: bool

    @model_validator(mode='after')
    def validate_operating_availability(self):
        if not self.confirmed:
            raise ValueError('operating availability must be explicitly confirmed')
        if self.mode == 'ALL_IN':
            if self.availability is None or not 0 < Decimal(self.availability) <= 1:
                raise ValueError('all-in availability must be within (0,1]')
            if any(v is not None for v in [self.autonomy_hours, self.charge_hours, self.service_hours_per_day, self.refill_hours_per_day]):
                raise ValueError('all-in availability already includes downtime')
        else:
            if self.availability is not None:
                raise ValueError('explicit downtime cannot also use all-in losses')
            if any(v is None for v in [self.autonomy_hours, self.charge_hours, self.service_hours_per_day, self.refill_hours_per_day]):
                raise ValueError('unknown downtime cannot be zero')
            if Decimal(self.autonomy_hours) <= 0 or any(Decimal(v) < 0 for v in [self.charge_hours, self.service_hours_per_day, self.refill_hours_per_day]):
                raise ValueError('invalid downtime')
        return self

    def practical_fraction(self, hours):
        if self.mode == 'ALL_IN':
            return Decimal(self.availability)
        productive = hours * Decimal(self.autonomy_hours) / (Decimal(self.autonomy_hours) + Decimal(self.charge_hours))
        productive -= Decimal(self.service_hours_per_day) + Decimal(self.refill_hours_per_day)
        if productive <= 0:
            raise ValueError('downtime consumes the available window')
        return min(Decimal(1), productive / hours)


class CapacityAnalysisRequest(StrictContractModel):
    schema_version: Literal["capacity-analysis-request-v2"] = (
        "capacity-analysis-request-v2"
    )
    project_id: StableId
    input_revision: StableId
    process: NormalizedProcess
    role_pool: RolePool | None = None
    model_id: Annotated[str, Field(min_length=1)]
    position_id: Annotated[str, Field(min_length=1)]
    acquisition: Literal["PURCHASE", "RAAS"]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    execution_mode: Literal["VERIFIED", "PRELIMINARY_DEMO"] = "VERIFIED"
    demo_assumptions_confirmed: bool = False
    selected_fleet: KnownQuantity | None = None
    operating_speed: KnownQuantity | None = None
    cleaning_area: KnownQuantity | None = None
    cleaning_frequency: KnownQuantity | None = None
    operations: OperatingAvailabilityV1 | None = Field(default=None, exclude_if=lambda v: v is None)
    provenance: list[Provenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_execution_inputs(self) -> "CapacityAnalysisRequest":
        if self.execution_mode == "PRELIMINARY_DEMO" and not self.demo_assumptions_confirmed:
            raise ValueError("preliminary demo requires explicit acknowledgement")
        if self.execution_mode == "VERIFIED" and self.demo_assumptions_confirmed:
            raise ValueError("demo acknowledgement is valid only in preliminary mode")
        if self.input_revision != self.process.input_revision:
            raise ValueError("request and process input_revision must match")
        expected = (
            (self.selected_fleet, QuantityName.FLEET_SELECTED),
            (self.operating_speed, QuantityName.OPERATING_SPEED),
            (self.cleaning_area, QuantityName.CLEANING_AREA),
            (self.cleaning_frequency, QuantityName.CLEANING_FREQUENCY),
        )
        for quantity, name in expected:
            if quantity is not None and quantity.name != name:
                raise ValueError(f"execution input must use {name}")
        refs = {item.provenance_id for item in self.provenance}
        if len(refs) != len(self.provenance):
            raise ValueError("request provenance ids must be unique")
        if any(item is not None and item.provenance_ref not in refs for item, _ in expected):
            raise ValueError("execution input has dangling provenance")
        return self


class CapacityZoneContextV1(StrictContractModel):
    schema_version: Literal["capacity-zone-context-v1"] = "capacity-zone-context-v1"
    zone_id: StableId
    label: Annotated[str, Field(min_length=1, max_length=128)]
    constraints_note: Annotated[str, Field(max_length=1000)] = ""
    constraints_status: Literal["UNVERIFIED"] = "UNVERIFIED"


class FacilityAreaValueV1(StrictContractModel):
    value: DecimalString
    unit: Literal["m2"] = "m2"
    source: Literal["USER", "FILE", "ASSUMPTION", "LLM"]
    confirmed: bool

    @model_validator(mode="after")
    def validate_value(self) -> "FacilityAreaValueV1":
        if not 0 < Decimal(self.value) <= 100000000:
            raise ValueError("facility area must be positive square metres")
        if not self.confirmed:
            raise ValueError("facility area must be confirmed")
        return self


class FacilityContextV1(StrictContractModel):
    schema_version: Literal["facility-context-v1"] = "facility-context-v1"
    total_area: FacilityAreaValueV1 | None = None
    active_area: FacilityAreaValueV1 | None = None

    @model_validator(mode="after")
    def validate_areas(self) -> "FacilityContextV1":
        if self.total_area and self.active_area and Decimal(self.active_area.value) > Decimal(self.total_area.value):
            raise ValueError("active area exceeds total area")
        return self


class CapacityAnalysisRequestV3(CapacityAnalysisRequest):
    schema_version: Literal["capacity-analysis-request-v3"] = "capacity-analysis-request-v3"
    zone_context: CapacityZoneContextV1
    facility_context: FacilityContextV1 | None = None

    @model_validator(mode="after")
    def validate_zone(self) -> "CapacityAnalysisRequestV3":
        if not self.process.process_id.startswith(f"{self.zone_context.zone_id}."):
            raise ValueError("v3 zone context must bind the selected process")
        return self


class CapacityAnalysisRequestV4(CapacityAnalysisRequestV3):
    schema_version: Literal['capacity-analysis-request-v4'] = 'capacity-analysis-request-v4'
    object_constraint_context: dict[str, Any]

    @model_validator(mode='after')
    def validate_constraints(self) -> 'CapacityAnalysisRequestV4':
        # Lazy import keeps the foundational quantity contracts independent of C05.
        from calculation.object_context import validate_object_context
        self.object_constraint_context = validate_object_context(self.object_constraint_context, self.process)
        return self


def parse_capacity_analysis_request(raw: dict[str, Any]) -> CapacityAnalysisRequest | CapacityAnalysisRequestV3 | CapacityAnalysisRequestV4:
    model = {'capacity-analysis-request-v3': CapacityAnalysisRequestV3,
             'capacity-analysis-request-v4': CapacityAnalysisRequestV4}.get(raw.get('schema_version'), CapacityAnalysisRequest)
    return model.model_validate(raw)


class CapacityAnalysisResponse(StrictContractModel):
    schema_version: Literal["capacity-analysis-response-v2"] = (
        "capacity-analysis-response-v2"
    )
    run_id: StableId
    input_revision: StableId
    capacity: CapacityResult
    trace: CalculationTrace

    @model_validator(mode="after")
    def validate_identity(self) -> CapacityAnalysisResponse:
        if self.run_id != self.trace.envelope.run_id:
            raise ValueError("response and trace run_id must match")
        if self.input_revision != self.trace.envelope.input_revision:
            raise ValueError("response and trace input_revision must match")
        if self.capacity.process_id != self.trace.envelope.process_id:
            raise ValueError("response and trace process_id must match")
        return self


class CapacityAnalysisErrorResponse(StrictContractModel):
    schema_version: Literal["capacity-analysis-error-v1"] = (
        "capacity-analysis-error-v1"
    )
    request_id: StableId
    run_id: StableId | None = None
    error_code: Literal[
        "INVALID_REQUEST",
        "UNKNOWN_CONTRACT_VERSION",
        "CAPACITY_SOURCE_UNAVAILABLE",
        "CALCULATION_BLOCKED",
        "ACCESS_DENIED",
        "INTERNAL_ERROR",
    ]
    issues: list[ContractIssue] = Field(min_length=1)
    partial_capacity: CapacityResult | None = None


class VersionBindings(StrictContractModel):
    catalog_version_id: Annotated[str, Field(min_length=1)]
    catalog_content_digest: Digest
    capacity_projection_version: Annotated[str, Field(min_length=1)]
    capacity_projection_digest: Digest
    registry_version: Literal[
        "calculation-parameter-registry-v1",
        "hackathon-calculation-parameter-registry-v1",
    ]
    registry_digest: Digest
    process_catalog_version: Literal["calculation-process-catalog-v1"]
    formula_bundle_version: Literal["calculation-formulas-v1"]
    constraint_rules_version: Literal[
        "calculation-constraints-v1", "calculation-constraint-rules-v2"
    ]
    commercial_policy_version: Literal["hackathon-commercial-policy-v1"]
    precision_policy_version: Literal["decimal-context-28-half-even-v1"]
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"]


class UserProvenance(StrictContractModel):
    provenance_id: StableId
    kind: Literal["USER"] = "USER"
    confirmation_revision: StableId


class FileProvenance(StrictContractModel):
    provenance_id: StableId
    kind: Literal["FILE"] = "FILE"
    file_digest: Digest
    locator: Annotated[str, Field(min_length=1)]


class PresetProvenance(StrictContractModel):
    provenance_id: StableId
    kind: Literal["PRESET"] = "PRESET"
    preset_id: StableId
    preset_version: Annotated[str, Field(min_length=1)]


SafeEvidenceStatus = Literal[
    "CORROBORATED",
    "CROSS_DOCUMENT_ENRICHED",
    "ORGANIZER_NAME",
    "VERIFIED_OFFICIAL",
    "VERIFIED_AUTHORIZED_PARTNER",
    "MANUALLY_APPROVED",
]


class VendorFactProvenance(StrictContractModel):
    provenance_id: StableId
    kind: Literal["VENDOR_FACT"] = "VENDOR_FACT"
    fact_id: StableId
    model_id: Annotated[str, Field(min_length=1)]
    position_id: Annotated[str, Field(min_length=1)]
    scope: Annotated[str, Field(min_length=1)]
    evidence_ids: list[StableId] = Field(min_length=1)
    evidence_status: SafeEvidenceStatus
    permitted_for_matching: Literal[True]


class AssumptionProvenance(StrictContractModel):
    provenance_id: StableId
    kind: Literal["ASSUMPTION"] = "ASSUMPTION"
    assumption_id: StableId
    assumption_version: Annotated[str, Field(min_length=1)]
    rationale: Annotated[str, Field(min_length=1)]
    permitted_scope: Annotated[str, Field(min_length=1)]
    confirmation_state: Literal["POLICY_ACCEPTED", "USER_CONFIRMED"]


class PolicyProvenance(StrictContractModel):
    provenance_id: StableId
    kind: Literal["POLICY"] = "POLICY"
    policy_id: StableId
    policy_version: Annotated[str, Field(min_length=1)]
    decision_refs: list[Annotated[str, Field(pattern=r"^K(?:0[1-9]|[12][0-9])$")]]


class DerivedProvenance(StrictContractModel):
    provenance_id: StableId
    kind: Literal["DERIVED"] = "DERIVED"
    parent_node_ids: list[StableId] = Field(min_length=1)


Provenance: TypeAlias = Annotated[
    UserProvenance
    | FileProvenance
    | PresetProvenance
    | VendorFactProvenance
    | AssumptionProvenance
    | PolicyProvenance
    | DerivedProvenance,
    Field(discriminator="kind"),
]


class TraceEnvelope(StrictContractModel):
    schema_version: Literal["calculation-trace-v1"] = "calculation-trace-v1"
    engine_version: Annotated[str, Field(min_length=1)]
    run_id: StableId
    input_revision: StableId
    acquisition: Literal["PURCHASE", "RAAS"]
    uncertainty: Literal["PESSIMISTIC", "BASE", "OPTIMISTIC"]
    process_id: StableId
    model_id: Annotated[str, Field(min_length=1)] | None
    position_id: Annotated[str, Field(min_length=1)] | None


class FormulaNode(StrictContractModel):
    node_id: StableId
    formula_id: Annotated[str, Field(pattern=r"^F(?:0[1-9]|[12][0-9]|3[0-5])$")]
    formula_version: Annotated[str, Field(min_length=1)]
    source_refs: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    source_digest: Digest
    template_id: StableId
    applicability_domain: Annotated[str, Field(min_length=1)]
    dependency_node_ids: list[StableId] = Field(default_factory=list)
    input_refs: list[Annotated[str, Field(min_length=1)]] = Field(default_factory=list)


class UnitConversion(StrictContractModel):
    conversion_id: StableId
    input_ref: Annotated[str, Field(min_length=1)]
    from_unit: Unit
    to_unit: Unit
    exact_factor: DecimalString
    operation: Literal["MULTIPLY", "DIVIDE", "IDENTITY"]
    before: DecimalString
    after: DecimalString
    unit_definition_version: Literal["si-unit-definitions-v1"] = "si-unit-definitions-v1"


class IntermediateValue(StrictContractModel):
    value_id: StableId
    node_id: StableId
    name: QuantityName
    value: ResultQuantity
    parent_refs: list[Annotated[str, Field(min_length=1)]]


class AssumptionUse(StrictContractModel):
    assumption_id: StableId
    assumption_version: Annotated[str, Field(min_length=1)]
    provenance_ref: StableId
    rationale: Annotated[str, Field(min_length=1)]
    permitted_scope: Annotated[str, Field(min_length=1)]
    mode: Literal["DEFAULT", "OVERRIDE"]
    raw_user_override: DecimalString | None
    applicable_scenario: Literal["ALL", "PESSIMISTIC", "BASE", "OPTIMISTIC"]
    confirmation_state: Literal["POLICY_ACCEPTED", "USER_CONFIRMED"]


class ConstraintEvaluation(StrictContractModel):
    evaluation_id: StableId
    check_id: StableId
    check_version: Annotated[str, Field(min_length=1)]
    required_ref: Annotated[str, Field(min_length=1)] | None
    available_ref: Annotated[str, Field(min_length=1)] | None
    status: Literal["PASS", "FAIL", "UNKNOWN", "ASSUMED", "N_A"]
    criticality: Literal["CRITICAL", "ADVISORY"]
    reason_code: StableId
    scope: Annotated[str, Field(min_length=1)]
    prerequisite_refs: list[Annotated[str, Field(min_length=1)]] = Field(
        default_factory=list
    )


class RoundingEvent(StrictContractModel):
    rounding_id: StableId
    node_id: StableId
    operation: Literal["CEIL", "FLOOR", "QUANTIZE", "DISPLAY"]
    input_value: DecimalString
    output_value: DecimalString
    precision_policy_version: Literal["decimal-context-28-half-even-v1"]
    reason: Annotated[str, Field(min_length=1)]
    source_ref: Annotated[str, Field(min_length=1)]


class TraceResult(StrictContractModel):
    result_id: StableId
    status: Literal["COMPLETE", "WITH_ASSUMPTIONS", "BLOCKED", "NOT_APPLICABLE"]
    value: ResultQuantity | None
    supporting_node_ids: list[StableId] = Field(default_factory=list)
    capacity_basis: Literal["NOMINAL", "EFFECTIVE", "NOT_APPLICABLE"]

    @model_validator(mode="after")
    def validate_status(self) -> TraceResult:
        if self.status in ("COMPLETE", "WITH_ASSUMPTIONS") and self.value is None:
            raise ValueError("complete trace result requires a value")
        if self.status in ("BLOCKED", "NOT_APPLICABLE") and self.value is not None:
            raise ValueError("non-executed trace result must be null")
        return self


class ReplayBinding(StrictContractModel):
    canonical_input_digest: Digest
    trace_content_digest: Digest
    deterministic_seed: Annotated[str, Field(min_length=1)] | None = None


class RuntimeMetadata(StrictContractModel):
    build_id: Annotated[str, Field(min_length=1)] | None = None
    runtime_id: Annotated[str, Field(min_length=1)] | None = None


class CalculationTrace(StrictContractModel):
    envelope: TraceEnvelope
    versions: VersionBindings
    provenance: list[Provenance]
    inputs: list[InputQuantity]
    formula_nodes: list[FormulaNode]
    conversions: list[UnitConversion] = Field(default_factory=list)
    intermediates: list[IntermediateValue] = Field(default_factory=list)
    assumptions: list[AssumptionUse] = Field(default_factory=list)
    constraints: list[ConstraintEvaluation] = Field(default_factory=list)
    roundings: list[RoundingEvent] = Field(default_factory=list)
    results: list[TraceResult]
    issues: list[ContractIssue] = Field(default_factory=list)
    replay: ReplayBinding
    runtime_metadata: RuntimeMetadata = Field(default_factory=RuntimeMetadata)

    @model_validator(mode="after")
    def validate_graph(self) -> CalculationTrace:
        provenance_ids = [item.provenance_id for item in self.provenance]
        if len(provenance_ids) != len(set(provenance_ids)):
            raise ValueError("provenance_id must be unique")
        known_provenance = set(provenance_ids)
        for quantity in self.inputs:
            if quantity.provenance_ref and quantity.provenance_ref not in known_provenance:
                raise ValueError("input has dangling provenance_ref")

        node_ids = [node.node_id for node in self.formula_nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node_id must be unique")
        seen: set[str] = set()
        for node in self.formula_nodes:
            if any(dependency not in seen for dependency in node.dependency_node_ids):
                raise ValueError("formula_nodes must be in stable topological order")
            seen.add(node.node_id)
        for result in self.results:
            if any(node_id not in seen for node_id in result.supporting_node_ids):
                raise ValueError("result has dangling supporting node")
        return self


class PrecisionPolicy(StrictContractModel):
    version: Literal["decimal-context-28-half-even-v1"]
    decimal_context_precision: Literal[28]
    rounding_mode: Literal["ROUND_HALF_EVEN"]
    raw_numeric_encoding: Literal["DECIMAL_STRING"]
    intermediate_rounding: Literal["NONE"]
    money_display_digits: Literal[2]
    percent_score_payback_display_digits: Literal[2]
    event_time_unit: Literal["microsecond"]
    score_tolerance: Literal["0.000001"]
    ceil_epsilon: Literal["FORBIDDEN"]


class SourceParameterBinding(StrictContractModel):
    formula_id: Annotated[str, Field(pattern=r"^F0[1-7]$")]
    source_refs: list[Annotated[str, Field(min_length=1)]]
    parameter_names: list[QuantityName]
    decision_refs: list[Annotated[str, Field(pattern=r"^K(?:02|03|04|19|27)$")]]


class CompatibilityRule(StrictContractModel):
    rule_id: StableId
    from_contract: Annotated[str, Field(min_length=1)]
    to_contract: Annotated[str, Field(min_length=1)]
    mode: Literal["UNCHANGED", "ADDITIVE", "PROVENANCE_GATED_ADAPTER"]
    lossy: bool
    rule: Annotated[str, Field(min_length=1)]


class RegistryFieldProposal(StrictContractModel):
    name: Literal[
        "parameter_id",
        "semantic_name",
        "value",
        "unit",
        "quantity_kind",
        "source_refs",
        "source_digest",
        "decision_refs",
        "effective_version",
        "replaced_by",
        "applicability",
    ]
    required: bool


class ParameterRegistryProposal(StrictContractModel):
    schema_version: Literal["calculation-parameter-registry-v1-proposal"] = (
        "calculation-parameter-registry-v1-proposal"
    )
    target_registry_version: Literal["calculation-parameter-registry-v1"]
    immutable_snapshot: Literal[True]
    semantic_order: Literal["parameter_id"]
    fields: list[RegistryFieldProposal]

    @model_validator(mode="after")
    def validate_fields(self) -> ParameterRegistryProposal:
        names = [item.name for item in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("registry proposal fields must be unique")
        required = {
            "parameter_id",
            "semantic_name",
            "value",
            "unit",
            "quantity_kind",
            "source_refs",
            "source_digest",
            "decision_refs",
            "effective_version",
            "applicability",
        }
        if not required.issubset({item.name for item in self.fields if item.required}):
            raise ValueError("registry proposal omits required provenance fields")
        return self


class ParameterDefinition(StrictContractModel):
    parameter_id: StableId
    semantic_name: Annotated[str, Field(min_length=1)]
    value: DecimalString
    unit: Unit
    quantity_kind: QuantityKind
    source_refs: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    source_digest: Digest
    decision_refs: list[Annotated[str, Field(pattern=r"^K(?:0[1-9]|[12][0-9])$")]]
    effective_version: Annotated[str, Field(min_length=1)]
    replaced_by: StableId | None = None
    applicability: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unit(self) -> ParameterDefinition:
        if UNIT_KINDS[str(self.unit)] != self.quantity_kind:
            raise ValueError("parameter unit is incompatible with quantity_kind")
        return self


class CalculationParameterRegistry(StrictContractModel):
    schema_version: Literal["calculation-parameter-registry-v1"] = (
        "calculation-parameter-registry-v1"
    )
    registry_version: Annotated[str, Field(min_length=1)]
    registry_digest: Digest
    semantic_order: Literal["parameter_id"] = "parameter_id"
    entries: list[ParameterDefinition]

    @model_validator(mode="after")
    def validate_entries(self) -> CalculationParameterRegistry:
        ids = [item.parameter_id for item in self.entries]
        if ids != sorted(ids):
            raise ValueError("registry entries must use stable parameter_id order")
        if len(ids) != len(set(ids)):
            raise ValueError("parameter_id must be unique")
        return self


class K02ExchangeExample(StrictContractModel):
    example_id: StableId
    source_semantics: Literal["NEW_TOTAL", "RAW_SPLIT", "LEGACY_PER_OPERATION"]
    normalized_exchange: ExchangeTime
    expected_total_seconds: DecimalString
    legacy_migration: bool


class K03BatchExample(StrictContractModel):
    example_id: StableId
    payload_kg: DecimalString
    item_mass_kg: DecimalString
    handling_limit: Annotated[int, Field(ge=1)] | None = None
    passport_limit: Annotated[int, Field(ge=1)] | None = None
    geometry_limit: Annotated[int, Field(ge=1)] | None = None
    expected_batch: Annotated[int, Field(ge=1)] | None
    expected_reason: Literal["RESOLVED", "INVALID_DOMAIN", "LIMIT_EXCEEDS_MASS_CAP"]


class K04CapacityExample(StrictContractModel):
    example_id: StableId
    active: bool
    demand: DecimalString
    selected_fleet: Annotated[int, Field(ge=0)]
    expected_capacity: DecimalString
    expected_coverage: DecimalString | None
    expected_raw_load_ratio: DecimalString | None
    expected_utilization: DecimalString | None
    expected_status: Literal["COMPLETE", "OVERLOADED", "NOT_APPLICABLE"]


class CalculationDecisionFixtures(StrictContractModel):
    schema_version: Literal["calculation-decision-fixtures-v1"] = (
        "calculation-decision-fixtures-v1"
    )
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"]
    k02_exchange: list[K02ExchangeExample]
    k03_batch: list[K03BatchExample]
    k04_capacity: list[K04CapacityExample]


class CalculationSemanticsManifest(StrictContractModel):
    schema_version: Literal["calculation-semantics-manifest-v1"] = (
        "calculation-semantics-manifest-v1"
    )
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"]
    decision_refs: list[Literal["K02", "K03", "K04", "K19", "K27"]]
    supported_contract_versions: list[
        Literal[
            "normalized-process-v1",
            "role-pool-v1",
            "capacity-result-v1",
            "financial-result-v1",
            "calculation-partial-result-v1",
            "calculation-trace-v1",
        ]
    ]
    precision_policy: PrecisionPolicy
    source_parameter_map: list[SourceParameterBinding]
    compatibility: list[CompatibilityRule]
    registry_proposal: ParameterRegistryProposal
    capacity_api: "CapacityApiDeclaration"


class CapacityApiDeclaration(StrictContractModel):
    method: Literal["POST"] = "POST"
    path: Literal["/api/v2/capacity-analyses"] = "/api/v2/capacity-analyses"
    request_schema_version: Literal["capacity-analysis-request-v2"]
    response_schema_version: Literal["capacity-analysis-response-v2"]
    error_schema_version: Literal["capacity-analysis-error-v1"]
    legacy_path_unchanged: Literal["/api/calculate"]


class CalculationSemanticsFixture(StrictContractModel):
    schema_version: Literal["calculation-semantics-fixture-v1"] = (
        "calculation-semantics-fixture-v1"
    )
    normalized_process: NormalizedProcess
    role_pool: RolePool
    result: PartialCalculationResult
    trace: CalculationTrace


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal string") from exc


def canonical_json_bytes(value: BaseModel | dict[str, Any] | list[Any]) -> bytes:
    """Serialize semantic content deterministically for replay digests."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    def normalize(item: Any) -> Any:
        if isinstance(item, str):
            return unicodedata.normalize("NFC", item)
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, dict):
            return {
                unicodedata.normalize("NFC", str(key)): normalize(child)
                for key, child in item.items()
            }
        return item

    return json.dumps(
        normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def semantic_digest(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def trace_semantic_content(trace: CalculationTrace | dict[str, Any]) -> dict[str, Any]:
    """Return content covered by trace_content_digest.

    Runtime/build metadata and the digest field itself are deliberately excluded;
    run identity remains included so a persisted run is replayed as one snapshot.
    """

    if isinstance(trace, CalculationTrace):
        payload = trace.model_dump(mode="json")
    else:
        payload = json.loads(json.dumps(trace))
    payload.pop("runtime_metadata", None)
    payload["replay"] = dict(payload["replay"])
    payload["replay"].pop("trace_content_digest", None)
    return payload


def calculation_trace_digest(trace: CalculationTrace | dict[str, Any]) -> str:
    return semantic_digest(trace_semantic_content(trace))


__all__ = [
    "CalculationSemanticsFixture",
    "CalculationSemanticsManifest",
    "CalculationDecisionFixtures",
    "CalculationParameterRegistry",
    "CalculationTrace",
    "CapacityAnalysisErrorResponse",
    "CapacityAnalysisRequest",
    "CapacityAnalysisResponse",
    "CapacityResult",
    "FinancialResult",
    "InputQuantity",
    "KnownQuantity",
    "MissingQuantity",
    "NormalizedProcess",
    "ParameterRegistryProposal",
    "PartialCalculationResult",
    "ProcessQuantityKind",
    "QuantityKind",
    "RolePool",
    "Unit",
    "VersionBindings",
    "calculation_trace_digest",
    "canonical_json_bytes",
    "semantic_digest",
]
