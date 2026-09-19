from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import List, Dict, Any, Optional, Literal


# ═══════════════════════════════════════════════════════════════
# ЗОНА — самостоятельный процесс внутри склада
# ═══════════════════════════════════════════════════════════════
class Zone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=32)
    name: str = Field("Зона", max_length=64)
    process_type: str = Field("transport", pattern="^(transport|palletizing|cleaning|delivery)$")
    cargo_type: str = Field("pallets", pattern="^(pallets|boxes|cases|carts|deliveries)$")

    area_m2: Optional[float] = Field(None, gt=0)
    shifts_count: Optional[int] = Field(None, ge=1, le=4)
    shift_hours: Optional[int] = Field(None, ge=6, le=12)
    volume_per_day: Optional[int] = Field(None, gt=0)
    avg_distance_m: Optional[float] = Field(None, gt=0)
    aisle_width_m: Optional[float] = Field(None, gt=0)
    payload_kg: Optional[float] = Field(None, ge=0)
    boxes_per_pallet: Optional[int] = Field(None, ge=1, le=200)
    cleaning_frequency_per_day: Optional[int] = Field(None, ge=1, le=4)
    peak_shift_share: Optional[float] = Field(None, gt=0, le=1)
    units_per_trip: Optional[int] = Field(
        None, ge=1, le=100,
        description="Вместимость одного рейса; переопределяет каталожный профиль",
    )

    staff_headcount: Optional[int] = Field(None, ge=1, le=500)
    released_headcount: Optional[int] = Field(None, ge=0, le=500)
    min_pult_fte_per_shift: Optional[float] = Field(None, ge=0.0, le=5.0)

    fleet_override: Optional[int] = Field(
        None, ge=1, le=100,
        description="Ручное число роботов в зоне. None - авто-подбор")

    selected_robot_ids: List[str] = Field(default_factory=list)
    polygon: Optional[List[List[float]]] = Field(None, min_length=3)


# ═══════════════════════════════════════════════════════════════
# ВХОДНЫЕ ДАННЫЕ ОТ ПОЛЬЗОВАТЕЛЯ
# ═══════════════════════════════════════════════════════════════
class UserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: str = Field("retail", pattern="^(retail|airport|clinic|other)$")

    # ─── Режим: весь объект или по зонам ───
    mode: str = Field("whole", pattern="^(whole|zonal)$")

    # ─── Whole-режим ───
    process_type: str = Field("transport", pattern="^(transport|palletizing|cleaning|delivery)$")
    cargo_type: str = Field("pallets", pattern="^(pallets|boxes|cases|carts|deliveries)$")
    pallets_per_day: Optional[int] = Field(None, gt=0)
    area_m2: Optional[float] = Field(None, gt=0)
    avg_distance_m: Optional[float] = Field(None, gt=0)
    shifts_count: Optional[int] = Field(None, ge=1, le=4)
    shift_hours: Optional[int] = Field(None, ge=6, le=12)
    staff_headcount: Optional[int] = Field(None, ge=1, le=500)
    aisle_width_m: Optional[float] = Field(None, gt=0)
    payload_kg: Optional[float] = Field(None, ge=0)
    boxes_per_pallet: Optional[int] = Field(None, ge=1, le=200)
    cleaning_frequency_per_day: Optional[int] = Field(None, ge=1, le=4)
    peak_shift_share: Optional[float] = Field(None, gt=0, le=1)
    units_per_trip: Optional[int] = Field(
        None, ge=1, le=100,
        description="Вместимость одного рейса; переопределяет каталожный профиль",
    )
    facility_width_m: Optional[float] = Field(None, gt=0)
    facility_depth_m: Optional[float] = Field(None, gt=0)
    polygon: Optional[List[List[float]]] = Field(None, min_length=3)
    released_headcount: Optional[int] = Field(None, ge=0, le=500)
    min_pult_fte_per_shift: Optional[float] = Field(None, ge=0.0, le=5.0)

    # ─── Общие параметры проекта ───
    fte_cost_rub: Optional[float] = Field(None, gt=0)
    equipment_count: Optional[int] = Field(None, ge=0, le=100)
    operating_days: Optional[int] = Field(None, ge=1, le=365)
    discount_rate: Optional[float] = Field(None, ge=0.04, le=0.40)
    horizon_years: Optional[int] = Field(None, ge=5, le=10)
    fleet_override: Optional[int] = Field(None, ge=1, le=100)

    # ─── Zonal-режим ───
    zones: List[Zone] = Field(default_factory=list)

    selected_robot_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_zone_ids(self):
        ids = [zone.id for zone in self.zones]
        duplicates = sorted({zone_id for zone_id in ids if ids.count(zone_id) > 1})
        if duplicates:
            raise ValueError(f"zone.id должны быть уникальны; дубли: {', '.join(duplicates)}")
        return self


# ═══════════════════════════════════════════════════════════════
# ПАРК РОБОТОВ
# ═══════════════════════════════════════════════════════════════
class RobotSpecs(BaseModel):
    model_config = ConfigDict(extra="allow")

    payload_kg: float
    max_speed_m_s: float
    min_aisle_width_m: float
    autonomy_hours: float
    navigation_type: str


class RobotEconomics(BaseModel):
    model_config = ConfigDict(extra="allow")

    robot_capex_rub: float
    charger_cost_rub: float
    chargers_per_robot: float
    integration_per_robot_rub: float
    annual_service_rub: float
    annual_software_rub: float
    avg_power_w: float
    fte_replace_per_shift: float
    residual_share: Optional[float] = Field(None, ge=0.0, le=1.0)
    site_fixed_warehouse_rub: float = 0.0
    site_fixed_zone_rub: float = 0.0
    site_fixed_rub: Optional[float] = None


class RobotPrice(BaseModel):
    model_config = ConfigDict(extra="allow")

    basis: str
    confidence: float
    note: str


class Robot(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    category: str
    type_label: str
    object_types: List[str]
    name: str
    description: str
    purpose: List[str] = []
    specs: RobotSpecs
    economics: RobotEconomics
    price: RobotPrice
    compatible_cargo: List[str] = []
    transport_profile: Dict[str, Any] = {}


# ═══════════════════════════════════════════════════════════════
# ФИНАНСОВЫЕ РАЗБИВКИ
# ═══════════════════════════════════════════════════════════════
class CapexBreakdown(BaseModel):
    robots: float
    chargers: float
    integration: float
    site_fixed: float
    contingency: float
    total: float


class OpexBreakdown(BaseModel):
    service: float
    software: float
    energy: float
    total: float


class ScenarioResult(BaseModel):
    scenario: str
    label: str
    quantity: int
    utilization: float
    horizon_years: int = 5
    capex: float
    opex_annual: float
    savings_annual: float
    net_annual: float
    payback_years: float
    npv: float
    tco: float
    roi_pct: float
    cost_per_move: float
    battery_replacement_year: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# РАСКЛАДКА ПО ПЕРСОНАЛУ
# ═══════════════════════════════════════════════════════════════
class StaffBreakdown(BaseModel):
    staff_total: Optional[int] = None
    staff_replaceable: float = 0.0
    staff_requested: Optional[int] = None
    staff_applied: float = 0.0
    staff_on_pult: float = 0.0
    staff_released: float = 0.0
    pult_minimum: int = 1
    min_pult_per_shift: float = 1.0
    pult_reason: str = "supervision_pct"
    pult_source: str = "from_released"
    pult_shortage: float = 0.0
    slider_enabled: bool = False
    slider_max: int = 0
    is_clamped: bool = False
    is_below_pult: bool = False


class RobotRecommendation(BaseModel):
    robot_id: str
    robot_name: str
    category: str
    quantity: int
    fleet_utilization: float
    fte_displaced: float
    fte_retained: float
    fte_released: float = 0.0
    horizon_years: int = 5
    capex: float
    opex: float
    savings_per_year: float
    payback_years: float
    npv: float
    tco: float
    cost_per_move: float
    readiness_score: int
    price_basis: str
    price_confidence: float
    price_note: str
    forced: bool = False
    technical_status: Literal["ELIGIBLE", "FORCED_UNSUPPORTED"] = "ELIGIBLE"
    economic_status: Literal["ACCEPTABLE", "WARNING", "NOT_ACCEPTABLE"] = "ACCEPTABLE"
    is_best: bool = False
    capex_breakdown: CapexBreakdown
    opex_breakdown: OpexBreakdown
    staff_breakdown: StaffBreakdown
    scenarios: List[ScenarioResult]
    warnings: List[str]


# ═══════════════════════════════════════════════════════════════
# СИМУЛЯЦИЯ
# ═══════════════════════════════════════════════════════════════
class SimulationUnit(BaseModel):
    id: int
    speed: float
    route: List[List[float]]
    pattern: str = "single"
    route_length_m: float = 0.0
    cycle_time_s: float = 0.0
    phase_offset_s: float = 0.0


class SimulationData(BaseModel):
    width_m: float
    height_m: float
    robots_count: int
    corridors_x: List[float]
    main_aisle_y: float
    units: List[SimulationUnit]
    docks: List[List[float]] = []
    aspect: float = 0.6


# ═══════════════════════════════════════════════════════════════
# ОТКЛОНЁННЫЕ, BASELINE, QUALITY
# ═══════════════════════════════════════════════════════════════
class RejectedRobot(BaseModel):
    robot_id: str
    robot_name: str
    reason: str


class ManualBaseline(BaseModel):
    manual_fte: int
    forklifts: int
    labor_cost_annual: float
    equipment_cost_annual: float
    total_cost_annual: float
    total_horizon: float
    horizon_years: int = 5
    cost_per_move: float


class DataQuality(BaseModel):
    completeness_pct: int
    level: str
    provided: List[str]
    assumed: List[str]
    refine_priority: List[str]


# ═══════════════════════════════════════════════════════════════
# ЗОНАЛЬНЫЙ РЕЗУЛЬТАТ
# ═══════════════════════════════════════════════════════════════
class ZoneResult(BaseModel):
    zone_id: str
    zone_name: str
    process_type: str
    cargo_type: str
    area_m2: Optional[float] = None
    shifts_count: int = 2
    shift_hours: int = 8
    volume_per_day: Optional[int] = None
    staff_headcount: Optional[int] = None

    recommendations: List[RobotRecommendation] = []
    rejected: List[RejectedRobot] = []
    best_robot_id: Optional[str] = None
    status: Literal[
        "RECOMMENDED", "NO_ELIGIBLE_EQUIPMENT", "NO_ACCEPTABLE_ECONOMICS"
    ] = "RECOMMENDED"
    status_message: Optional[str] = None

    zone_capex: float = 0.0
    zone_opex_annual: float = 0.0
    zone_savings_annual: float = 0.0
    zone_net_annual: float = 0.0
    zone_npv: float = 0.0
    zone_tco: float = 0.0
    zone_payback_years: float = 99.0
    zone_displaced: float = 0.0
    zone_released: float = 0.0
    zone_robots: int = 0

    manual_baseline: Optional[ManualBaseline] = None
    staff_breakdown: Optional[StaffBreakdown] = None
    warnings: List[str] = []


class CombinedSummary(BaseModel):
    zones_count: int
    total_robots: int
    total_capex: float
    total_opex_annual: float
    total_savings_annual: float
    total_net_annual: float
    total_displaced: float
    total_released: float
    total_npv: float
    total_tco: float
    combined_payback_years: float
    horizon_years: int
    warehouse_fixed_rub: float
    best_zone_id: Optional[str] = None
    best_zone_payback: Optional[float] = None


# ═══════════════════════════════════════════════════════════════
# ОТВЕТ /api/calculate
# ═══════════════════════════════════════════════════════════════
class CalculationResponse(BaseModel):
    schema_version: Literal["calculation-response-v1"] = "calculation-response-v1"
    revision_id: str
    mode: str = "whole"
    recommendations: List[RobotRecommendation] = []
    rejected: List[RejectedRobot] = []
    manual_baseline: Optional[ManualBaseline] = None
    zones: List[ZoneResult] = []
    combined: Optional[CombinedSummary] = None
    simulation: Optional[SimulationData] = None
    data_quality: DataQuality
    assumptions: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
    scenario_spec: "ScenarioSpec"


# ═══════════════════════════════════════════════════════════════
# ПУБЛИЧНЫЙ КОНТРАКТ СЦЕНАРИЯ ДЛЯ ROBCRAFT
# ═══════════════════════════════════════════════════════════════
class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScenarioPresentation(StrictContractModel):
    autoplay: bool = True
    default_camera_mode: Literal["AUTOPILOT"] = "AUTOPILOT"
    manual_control_available: bool = True
    editor_available: bool = True


class ScenarioFacility(StrictContractModel):
    area_m2: Optional[float] = Field(None, gt=0)
    width_m: Optional[float] = Field(None, gt=0)
    depth_m: Optional[float] = Field(None, gt=0)
    geometry_status: Literal["PROVIDED", "ASSUMED", "UNKNOWN"] = "UNKNOWN"
    occupancy_percent: Optional[float] = Field(None, ge=0, le=100)


class ScenarioZone(StrictContractModel):
    id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1)
    process_type: Literal["transport", "palletizing", "cleaning", "delivery"]
    cargo_type: Literal["pallets", "boxes", "cases", "carts", "deliveries"]
    status: Literal[
        "RECOMMENDED", "NO_ELIGIBLE_EQUIPMENT", "NO_ACCEPTABLE_ECONOMICS"
    ]
    demand_per_day: Optional[float] = Field(None, gt=0)
    avg_distance_m: Optional[float] = Field(None, gt=0)
    aisle_width_m: Optional[float] = Field(None, gt=0)
    polygon: Optional[List[List[float]]] = Field(None, min_length=3)


class ScenarioFleetItem(StrictContractModel):
    zone_id: str = Field(..., min_length=1)
    equipment_model_id: str = Field(..., min_length=1)
    visual_profile: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)
    max_speed_m_s: float = Field(..., ge=0)
    payload_kg: float = Field(..., ge=0)


class ScenarioTaskProfile(StrictContractModel):
    zone_id: str = Field(..., min_length=1)
    kind: Literal["pallet_move", "box_move", "cart_move", "delivery", "cleaning", "palletizing"]
    demand_per_day: float = Field(..., gt=0)
    units_per_trip: int = Field(..., ge=1)
    exchange_time_s: float = Field(..., ge=0)


class ScenarioEconomics(StrictContractModel):
    scenario: Literal["base"] = "base"
    horizon_years: int = Field(..., ge=5, le=10)
    capex_rub: float
    annual_opex_rub: float
    annual_savings_rub: float
    payback_years: Optional[float] = None
    npv_rub: float
    tco_rub: float
    fte_released: float
    confidence: Optional[float] = None
    status: Literal["ACCEPTABLE", "WARNING", "NOT_ACCEPTABLE"]


class ScenarioAssumption(StrictContractModel):
    code: str
    message: str


class ScenarioSpec(StrictContractModel):
    schema_version: Literal["scenario-spec-v1"] = "scenario-spec-v1"
    revision_id: str = Field(..., pattern=r"^calc_[0-9a-f]{16}$")
    source: Literal["calculation"] = "calculation"
    template: Literal["warehouse", "airport", "hospital"]
    seed: str = Field(..., min_length=1)
    presentation: ScenarioPresentation
    facility: ScenarioFacility
    zones: List[ScenarioZone] = Field(..., min_length=1)
    fleet: List[ScenarioFleetItem]
    task_profiles: List[ScenarioTaskProfile]
    economics: ScenarioEconomics
    assumptions: List[ScenarioAssumption] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        zone_ids = [zone.id for zone in self.zones]
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError("ScenarioSpec zone.id должны быть уникальны")
        known = set(zone_ids)
        dangling = sorted({
            item.zone_id for item in [*self.fleet, *self.task_profiles]
            if item.zone_id not in known
        })
        if dangling:
            raise ValueError(f"ScenarioSpec содержит неизвестные zone_id: {', '.join(dangling)}")
        return self


CalculationResponse.model_rebuild()


# Additive C01 DTO specifications.  Legacy request/response models above remain
# unchanged and production routes do not instantiate these contracts yet.
from calculation_contracts import (  # noqa: E402,F401
    CalculationDecisionFixtures,
    CalculationParameterRegistry,
    CalculationSemanticsFixture,
    CalculationSemanticsManifest,
    CalculationTrace,
    CapacityAnalysisErrorResponse,
    CapacityAnalysisRequest,
    CapacityAnalysisResponse,
    CapacityResult,
    FinancialResult,
    KnownQuantity,
    MissingQuantity,
    NormalizedProcess,
    ParameterRegistryProposal,
    PartialCalculationResult,
    ProcessQuantityKind,
    QuantityKind,
    RolePool,
    Unit,
    VersionBindings,
)
