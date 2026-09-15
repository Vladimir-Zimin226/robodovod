import math
from typing import Optional, List

from models import (UserInput, Zone, RobotRecommendation, ScenarioResult,
                    CapexBreakdown, OpexBreakdown, ManualBaseline, DataQuality,
                    StaffBreakdown, ZoneResult, CombinedSummary, RejectedRobot)

# ═══════════════════════════════════════════════════════════════
# ДОПУЩЕНИЯ МОДЕЛИ
# ═══════════════════════════════════════════════════════════════
DEFAULT_HORIZON_YEARS = 5
MIN_HORIZON_YEARS = 5
MAX_HORIZON_YEARS = 10
HORIZON_YEARS = DEFAULT_HORIZON_YEARS

ELECTRICITY_TARIFF_RUB = 8.0
DEFAULT_SALARY_MONTH = 80_000
FULLY_LOADED_MULT = 1.55
DEFAULT_SHIFTS = 2
DEFAULT_SHIFT_HOURS = 8
DEFAULT_DISTANCE_M = 120.0
DEFAULT_AREA_M2 = 6000.0
DEFAULT_AISLE_M = 3.0
DEFAULT_DAYS = 365
DEFAULT_DISCOUNT = 0.15
DEFAULT_FREQ = 1
DEFAULT_BOXES_PER_PALLET = 20
LOAD_UNLOAD_TIME_S = 45

VACATION_FACTOR = 1.083
FORKLIFT_SHARE_OF_FTE = 0.4
RESIDUAL_SHARE = 0.40
EXCHANGE_OPERATIONS_PER_TRIP = 2
LABOR_INFLATION = 0.08
OPEX_INFLATION = 0.05
CELL_DESIGN_EFFICIENCY = 0.65
TARGET_FLEET_UTILIZATION = 0.90
DEFAULT_PULT_FTE_PER_SHIFT = 1.0
MIN_AREA_PER_ROBOT_M2 = 30.0

FATIGUE_BY_HOURS = {6: 1.0, 7: 1.0, 8: 1.0, 9: 0.95, 10: 0.95, 11: 0.9, 12: 0.9}

MANUAL_RATE_PER_SHIFT = {"pallets": 80, "boxes": 150, "carts": 44, "deliveries": 30}
MANUAL_PICKS_PER_MIN = 8
MANUAL_CLEAN_RATE_M2_H = 700
MANUAL_CLEAN_HOURS = 6.8
FORKLIFT_ANNUAL_TCO_RUB = 700_000
FORKLIFTS_PER_FTE = 2

SCENARIOS = {
    "pessimistic": dict(label="Пессимистичный", utilization=0.55, hw_mult=1.10,
                        contingency=0.12, supervision=0.30, ramp=0.78,
                        service_mult=1.15, rotation=False),
    "base":        dict(label="Базовый", utilization=0.70, hw_mult=1.00,
                        contingency=0.06, supervision=0.20, ramp=0.90,
                        service_mult=1.00, rotation=True),
    "optimistic":  dict(label="Оптимистичный", utilization=0.80, hw_mult=0.95,
                        contingency=0.03, supervision=0.10, ramp=0.95,
                        service_mult=0.90, rotation=True),
}

MANDATORY_BY_PROCESS = {
    "transport": ["pallets_per_day"],
    "palletizing": ["pallets_per_day"],
    "delivery": ["pallets_per_day"],
    "cleaning": ["area_m2"],
}

QUALITY_WEIGHTS = {
    "pallets_per_day": 14, "area_m2": 5, "avg_distance_m": 10, "shifts_count": 8,
    "shift_hours": 4, "staff_headcount": 20, "fte_cost_rub": 19,
    "aisle_width_m": 10, "payload_kg": 5, "discount_rate": 5,
}

ASSUMPTIONS = {
    "horizon_years_default": DEFAULT_HORIZON_YEARS,
    "horizon_years_min": MIN_HORIZON_YEARS,
    "horizon_years_max": MAX_HORIZON_YEARS,
    "horizon_note": ("Пользователь выбирает горизонт 5-10 лет. "
                     "Дефолт 5 лет. Длинный горизонт снижает чувствительность "
                     "к разовым отклонениям, но увеличивает неопределённость прогноза"),
    "electricity_tariff_rub_kwh": ELECTRICITY_TARIFF_RUB,
    "default_salary_month": DEFAULT_SALARY_MONTH,
    "fully_loaded_mult": FULLY_LOADED_MULT,
    "fully_loaded_note": ("Оклад x 12 x 1.55 = полная годовая стоимость FTE. "
                          "1.302 - взносы, остаток - СИЗ, питание, развозка, "
                          "управленческий overhead, текучка"),
    "manual_rate_per_shift_8h": MANUAL_RATE_PER_SHIFT,
    "manual_picks_per_min": MANUAL_PICKS_PER_MIN,
    "manual_clean_rate_m2_h": MANUAL_CLEAN_RATE_M2_H,
    "forklift_annual_tco_rub": FORKLIFT_ANNUAL_TCO_RUB,
    "forklift_share_of_fte": FORKLIFT_SHARE_OF_FTE,
    "boxes_per_pallet_default": DEFAULT_BOXES_PER_PALLET,
    "residual_share_default": RESIDUAL_SHARE,
    "residual_share_note": ("По умолчанию 40% от robot_capex. Переопределяется "
                            "в economics.residual_share каждого робота: AGV 0.30, "
                            "cleaning 0.35, delivery 0.45, fixed_cell 0.50, aerial 0.15-0.25"),
    "vacation_factor": VACATION_FACTOR,
    "fatigue": "6-8 ч: 1.0; 10 ч: 0.95; 12 ч: 0.9",
    "rotation_formula": ("(7 x дней/365) / (40 / длительность_смены) x 1.083, минимум 1.0. "
                         "1.083 - коэффициент отпусков (28+5 дней в году)"),
    "peak_share_defaults": "1 смена: 1.00; 2 смены: 0.55; 3 смены: 0.45; 4 смены: 0.35",
    "energy_model": "avg_power_w x operating_hours x operating_days x utilization",
    "opex_ramp": "Год 1: savings и OPEX умножаются на ramp",
    "labor_inflation": LABOR_INFLATION,
    "opex_inflation": OPEX_INFLATION,
    "tco_model": ("TCO включает CAPEX + OPEX с индексацией на OPEX_INFLATION "
                  "+ замену батарей. Согласовано с денежными потоками NPV"),
    "cell_design_efficiency": CELL_DESIGN_EFFICIENCY,
    "cell_efficiency_note": ("Учитывает смену паллет, отказы захвата, неидеальную укладку. "
                             "Эффективная скорость = паспортная x utilization x 0.65"),
    "target_fleet_utilization": TARGET_FLEET_UTILIZATION,
    "target_fleet_utilization_note": "Запас 10% на пики и поломки",
    "min_area_per_robot_m2": MIN_AREA_PER_ROBOT_M2,
    "min_area_per_robot_note": ("Минимальная площадь на одного робота в зоне/на объекте. "
                                "Меньше — роботам тесно: мало места для маневрирования, "
                                "стоянки, зарядных станций"),
    "fleet_sizing_note": ("Двойной запас: utilization (0.55-0.80) - рабочая "
                          "загрузка робота в смену; TARGET_FLEET_UTILIZATION (0.90) - "
                          "сколько от этой загрузки можно использовать под пики. "
                          "Итоговая эффективная загрузка = utilization x 0.90"),
    "units_per_trip_note": (
        "units_per_trip из входа имеет приоритет над transport_profile каталога "
        "и прямо умножает пропускную способность одного рейса"
    ),
    "fte_replace_per_shift_note": (
        "fte_replace_per_shift ограничивает заменяемый труд: количество роботов × "
        "смены × FTE на робота за смену × коэффициент ротации сценария. "
        "Экономия не может превышать этот предел или фактический штат"
    ),
    "exchange_operations_per_trip": EXCHANGE_OPERATIONS_PER_TRIP,
    "exchange_note": ("exchange_time_s в backend/fleet - время на одну операцию "
                      "(погрузка ИЛИ разгрузка); за рейс их две"),
    "release_note": ("released_headcount - ползунок UI «Сколько сотрудников "
                     "заменить роботами»: сколько человек из текущего штата "
                     "будет заменено. Не задан - полное высвобождение."),
    "pult_minimum_default": DEFAULT_PULT_FTE_PER_SHIFT,
    "pult_minimum_note": ("Минимум людей на пульте на одну смену. "
                          "1.0 = один человек на смену круглосуточно (дефолт). "
                          "0 = отключить жёсткий минимум, оставить только процент supervision. "
                          "Остаток на пульте = max(supervision x displaced, "
                          "shifts x min_pult_fte_per_shift)"),
    "pult_source_note": ("Операторы пульта набираются из заменённых (тех, чью работу "
                         "взял робот). Если заменённых не хватает на минимум пульта - "
                         "pult_shortage > 0, потребуется перевод из незаменённых."),
    "staffing_model": ("Робот берёт процесс; released_headcount - сколько человек "
                       "реально заменяется; пульт набирается из заменённых; "
                       "ротация подменных бригад - сценарная ось; "
                       "fleet_override - частичная роботизация парка"),
    "savings_note": ("Экономия предполагает реальное высвобождение cashable FTE "
                     "(сокращение или перевод). При полном сохранении персонала "
                     "эффект близок к нулю"),
    "terminal_value_model": ("В последний год горизонта учитывается остаточная "
                             "стоимость парка (per-robot доля от robot_capex, "
                             "масштабируется на hw_mult сценария)"),
    "site_fixed_split_note": (
        "site_fixed делится на warehouse_rub (Wi-Fi, WMS, контроллер — 1× на склад) "
        "и zone_rub (разметка, локальный шлюз — на каждую зону)"
    ),
    "zonal_mode_note": (
        "В зональном режиме каждая зона рассчитывается независимо, "
        "парк суммируется, warehouse_fixed учитывается один раз"
    ),
    "scenario_params": {k: dict(s) for k, s in SCENARIOS.items()},
    "note": ("Предварительное ТЭО. Цены - оценки (sourced estimate), не офферы. "
             "Эффект роста throughput не монетизирован. "
             "Не заменяет инженерное обследование и КП интегратора."),
    "roi_note": ("roi_pct — простая (недисконтированная) доходность: "
                 "(экономия × горизонт + остаточная стоимость − TCO) / TCO × 100. "
                 "Для дисконтированной доходности смотрите NPV"),
}

SOURCES = [
    {"group": "Константы", "parameter": "Курс USD->RUB", "value": "90", "type": "допущение"},
    {"group": "Константы", "parameter": "Взносы к зарплате", "value": "x1.302", "type": "факт (НК РФ)"},
    {"group": "Константы", "parameter": "Полная стоимость FTE", "value": "x1.55 к окладу", "type": "с учётом overhead и текучки"},
    {"group": "Константы", "parameter": "Тариф электроэнергии", "value": "8 RUB/кВт-ч", "type": "промтарифы РФ 5-9"},
    {"group": "Труд", "parameter": "Норма 1 FTE за 8 ч", "value": "80 паллет / 150 коробок / 44 тележки / 30 доставок", "type": "инженерная норма"},
    {"group": "Труд", "parameter": "Ручная укладка", "value": "8 коробов/мин", "type": "диапазон 5-10"},
    {"group": "Труд", "parameter": "Уборка вручную", "value": "700 м2/ч, 6.8 продуктивных ч/смену", "type": "с поломоечной"},
    {"group": "Труд", "parameter": "Усталость 10/12 ч", "value": "0.95 / 0.9", "type": "допущение"},
    {"group": "Труд", "parameter": "Ротация бригад", "value": "(7xдней/365)/(40/длительность) x 1.083", "type": "допущение, сценарная ось"},
    {"group": "Труд", "parameter": "Ричтрак TCO", "value": "~700 тыс. RUB/год", "type": "2.5 млн / 8 лет + сервис"},
    {"group": "Труд", "parameter": "Доля FTE с техникой", "value": "40% (ричтрак)", "type": "оценка"},
    {"group": "Труд", "parameter": "Минимум на пульте", "value": "1 FTE на смену", "type": "параметр пользователя"},
    {"group": "Труд", "parameter": "Сколько заменить", "value": "ползунок 0..штат", "type": "параметр пользователя"},
    {"group": "Эксплуатация", "parameter": "Сервис", "value": "4-6% цены робота/год", "type": "бенчмарк 3-8%"},
    {"group": "Эксплуатация", "parameter": "Жизнь батареи", "value": "3000 циклов (MiR250 spec)", "type": "спецификация"},
    {"group": "Эксплуатация", "parameter": "Интеграция/ПНР", "value": "0.3-1.2 млн RUB/робот", "type": "диапазон $5-80k"},
    {"group": "Эксплуатация", "parameter": "WMS/Wi-Fi/разметка", "value": "1.2-3 млн RUB", "type": "light $5-25k"},
    {"group": "Эксплуатация", "parameter": "Плотность парка", "value": "≥ 30 м² на робота", "type": "эмпирическая норма"},
    {"group": "Финансы", "parameter": "Остаточная стоимость", "value": "per-robot (дефолт 40%)", "type": "оценка вторичного рынка"},
    {"group": "Финансы", "parameter": "Инфляция ФОТ", "value": f"{LABOR_INFLATION:.0%}/год", "type": "допущение"},
    {"group": "Финансы", "parameter": "Инфляция OPEX", "value": f"{OPEX_INFLATION:.0%}/год", "type": "допущение"},
    {"group": "Финансы", "parameter": "Горизонт расчёта", "value": "5-10 лет (дефолт 5)", "type": "параметр пользователя"},
    {"group": "Финансы", "parameter": "site_fixed split", "value": "warehouse × 1, zone × N", "type": "модель"},
    {"group": "Сценарии", "parameter": "7 осей", "value": "см. scenario_params", "type": "исследование"},
]


# ═══════════════════════════════════════════════════════════════
# Резолверы дефолтов
# ═══════════════════════════════════════════════════════════════
def _shifts(inp): return inp.shifts_count or DEFAULT_SHIFTS
def _shift_hours(inp): return inp.shift_hours or DEFAULT_SHIFT_HOURS
def _operating_hours(inp): return min(_shifts(inp) * _shift_hours(inp), 24)
def _fatigue(inp): return FATIGUE_BY_HOURS.get(_shift_hours(inp), 1.0)
def _days(inp): return inp.operating_days or DEFAULT_DAYS
def _discount(inp): return inp.discount_rate or DEFAULT_DISCOUNT
def _distance(inp): return inp.avg_distance_m or DEFAULT_DISTANCE_M
def _aisle(inp): return inp.aisle_width_m or DEFAULT_AISLE_M
def _freq(inp): return inp.cleaning_frequency_per_day or DEFAULT_FREQ
def _boxes_per_pallet(inp): return inp.boxes_per_pallet or DEFAULT_BOXES_PER_PALLET


def _horizon(inp) -> int:
    if inp.horizon_years is not None:
        return int(inp.horizon_years)
    return DEFAULT_HORIZON_YEARS


def _fte_cost(inp) -> float:
    return inp.fte_cost_rub or DEFAULT_SALARY_MONTH * 12 * FULLY_LOADED_MULT


def _rot(inp) -> float:
    base = (7.0 * _days(inp) / 365.0) / (40.0 / _shift_hours(inp))
    return max(1.0, base * VACATION_FACTOR)


def _peak_share(inp) -> float:
    if inp.peak_shift_share is not None:
        return inp.peak_shift_share
    s = _shifts(inp)
    if s <= 1:
        return 1.00
    if s == 2:
        return 0.55
    if s == 3:
        return 0.45
    return 0.35   # 4 смены


def _payload(inp):
    if inp.payload_kg is not None:
        return inp.payload_kg
    return {"pallets": 700, "boxes": 25, "cases": 20, "carts": 0,
            "deliveries": 5}.get(inp.cargo_type, 700)


def _daily_demand(inp):
    if inp.process_type == "cleaning":
        return (inp.area_m2 or DEFAULT_AREA_M2) * _freq(inp)
    return inp.pallets_per_day or 0


def _requested_headcount(inp, displaced: float) -> float:
    if inp.released_headcount is not None:
        return min(float(inp.released_headcount), displaced)
    return displaced


def _min_pult_per_shift(inp) -> float:
    if inp.min_pult_fte_per_shift is not None:
        return inp.min_pult_fte_per_shift
    return DEFAULT_PULT_FTE_PER_SHIFT


def _residual_share(econ: dict) -> float:
    v = econ.get("residual_share")
    if v is None:
        return RESIDUAL_SHARE
    return float(v)


def _site_fixed(econ: dict, is_zone: bool = False) -> float:
    wh = econ.get("site_fixed_warehouse_rub", 0) or 0
    zn = econ.get("site_fixed_zone_rub", 0) or 0
    legacy = econ.get("site_fixed_rub")

    if not wh and not zn and legacy is not None:
        return float(legacy)

    if is_zone:
        return float(zn)
    return float(wh + zn)


def _warehouse_fixed(econ: dict) -> float:
    wh = econ.get("site_fixed_warehouse_rub", 0) or 0
    legacy = econ.get("site_fixed_rub")
    if not wh and legacy is not None:
        return float(legacy)
    return float(wh)


# ═══════════════════════════════════════════════════════════════
# Валидация
# ═══════════════════════════════════════════════════════════════
def validate_mandatory(inp: UserInput) -> Optional[str]:
    if inp.mode == "zonal":
        if not inp.zones:
            return "Зональный режим: добавьте хотя бы одну зону"
        for z in inp.zones:
            if z.process_type == "cleaning" and z.area_m2 is None:
                return f"Зона «{z.name}»: не заполнена площадь уборки"
            if z.process_type != "cleaning" and z.volume_per_day is None:
                return f"Зона «{z.name}»: не заполнен объём в сутки"
            total = (z.shifts_count or 2) * (z.shift_hours or 8)
            if total > 24:
                return f"Зона «{z.name}»: график {total} ч > 24 ч"
        return None

    total = _shifts(inp) * _shift_hours(inp)
    if total > 24:
        return f"Режим {_shifts(inp)}x{_shift_hours(inp)} ч = {total} ч > 24 ч - выберите 2x12 или 3x8"
    names = {"pallets_per_day": "объём в сутки", "area_m2": "площадь уборки"}
    for k in MANDATORY_BY_PROCESS.get(inp.process_type, []):
        if getattr(inp, k) is None:
            return f"Не заполнен обязательный параметр: {names.get(k, k)}"
    return None


def assess_data_quality(inp: UserInput) -> DataQuality:
    if inp.mode == "zonal":
        shared_keys = ("fte_cost_rub", "operating_days", "discount_rate", "horizon_years")
        provided = [k for k in shared_keys if getattr(inp, k, None) is not None]
        assumed = [k for k in shared_keys if k not in provided]
        total = len(shared_keys)
        pct = round(len(provided) / total * 100) if total else 0
        level = "Базовая" if pct < 40 else ("Рабочая" if pct < 70 else "Высокая")
        return DataQuality(completeness_pct=pct, level=level,
                           provided=provided, assumed=assumed,
                           refine_priority=[])

    provided = [k for k in QUALITY_WEIGHTS if getattr(inp, k) is not None]
    assumed = [k for k in QUALITY_WEIGHTS if getattr(inp, k) is None]
    total = sum(QUALITY_WEIGHTS.values())
    pct = round(sum(QUALITY_WEIGHTS[k] for k in provided) / total * 100)
    level = "Базовая" if pct < 40 else ("Рабочая" if pct < 70 else "Высокая")
    order = ["fte_cost_rub", "staff_headcount", "avg_distance_m",
             "aisle_width_m", "shifts_count", "discount_rate"]
    return DataQuality(completeness_pct=pct, level=level, provided=provided,
                       assumed=assumed,
                       refine_priority=[k for k in order if getattr(inp, k) is None])


# ═══════════════════════════════════════════════════════════════
# Модель труда
# ═══════════════════════════════════════════════════════════════
def _manual_rate_per_shift(inp) -> float:
    if inp.cargo_type == "cases":
        base = MANUAL_PICKS_PER_MIN * 60 * 8
    else:
        base = MANUAL_RATE_PER_SHIFT.get(inp.cargo_type, 80)
    return base * (_shift_hours(inp) / 8.0) * _fatigue(inp)


def _daily_slots(inp) -> int:
    if inp.process_type == "cleaning":
        per_person = (MANUAL_CLEAN_RATE_M2_H * MANUAL_CLEAN_HOURS
                      * (_shift_hours(inp) / 8.0) * _fatigue(inp))
        return max(1, math.ceil(_daily_demand(inp) / per_person))
    crews = max(1, math.ceil(inp.pallets_per_day / (_manual_rate_per_shift(inp) * _shifts(inp))))
    return crews * _shifts(inp)


def _estimate_headcount(inp, with_rotation: bool) -> float:
    return _daily_slots(inp) * (_rot(inp) if with_rotation else 1.0)


def _labor_model(inp, sc, qty=None, qty_full=None, fte_replace_per_shift=1.0) -> dict:
    estimate = _estimate_headcount(inp, sc["rotation"])
    coverage = (
        min(1.0, qty / qty_full)
        if qty is not None and qty_full is not None and qty_full > 0 else 1.0
    )
    catalog_capacity = (
        float(qty) * _shifts(inp) * float(fte_replace_per_shift)
        * (_rot(inp) if sc["rotation"] else 1.0)
        if qty is not None else estimate
    )
    base_displaced = min(estimate * coverage, catalog_capacity)
    if inp.staff_headcount:
        base_displaced = min(float(inp.staff_headcount) * coverage, base_displaced)
    displaced = base_displaced

    applied = _requested_headcount(inp, displaced)

    retained_pct = displaced * sc["supervision"]
    min_per_shift = _min_pult_per_shift(inp)
    retained_min = float(_shifts(inp)) * min_per_shift if displaced > 0 else 0.0

    if retained_pct >= retained_min:
        retained = retained_pct
        pult_reason = "supervision_pct"
    else:
        retained = retained_min
        pult_reason = "min_per_shift" if min_per_shift > 0 else "supervision_pct"

    cashable = max(0.0, applied - retained)
    labor = cashable * _fte_cost(inp)

    if inp.cargo_type == "pallets":
        if inp.equipment_count is not None:
            forklifts = inp.equipment_count
        else:
            forklifts = math.ceil(cashable * FORKLIFT_SHARE_OF_FTE / FORKLIFTS_PER_FTE)
    else:
        forklifts = 0

    return dict(
        displaced=displaced, retained=retained, cashable=cashable,
        labor=labor, equip=forklifts * FORKLIFT_ANNUAL_TCO_RUB,
        slots=_daily_slots(inp), applied=applied,
        pult_reason=pult_reason, retained_pct=retained_pct,
        retained_min=retained_min, min_pult_per_shift=min_per_shift,
        catalog_replacement_capacity=catalog_capacity,
    )


def manual_baseline(inp: UserInput) -> ManualBaseline:
    headcount = inp.staff_headcount if inp.staff_headcount else round(_estimate_headcount(inp, True))
    if inp.cargo_type == "pallets":
        if inp.equipment_count is not None:
            forklifts = inp.equipment_count
        else:
            forklifts = math.ceil(headcount * FORKLIFT_SHARE_OF_FTE / FORKLIFTS_PER_FTE)
    else:
        forklifts = 0
    labor = headcount * _fte_cost(inp)
    equip = forklifts * FORKLIFT_ANNUAL_TCO_RUB
    total = labor + equip
    moves = _daily_demand(inp) * _days(inp)
    h = _horizon(inp)
    return ManualBaseline(
        manual_fte=headcount, forklifts=forklifts,
        labor_cost_annual=round(labor, -4), equipment_cost_annual=round(equip, -4),
        total_cost_annual=round(total, -4),
        total_horizon=round(total * h, -4),
        horizon_years=h,
        cost_per_move=round(total / moves, 1) if moves else 0.0)


# ═══════════════════════════════════════════════════════════════
# Матрица совместимости
# ═══════════════════════════════════════════════════════════════
def check_constraints(inp: UserInput, robot: dict) -> Optional[str]:
    if inp.object_type not in robot.get("object_types", []):
        return f"Решение не предназначено для объекта типа «{inp.object_type}»"

    cat, specs = robot["category"], robot["specs"]

    if cat == "aerial":
        return "Летательные платформы - ветка инспекции/инвентаризации (цена по запросу)"

    if cat == "fixed_cell":
        if inp.process_type != "palletizing":
            return "Стационарная ячейка применима только в процессе паллетизации"
        if _payload(inp) > specs["payload_kg"]:
            return f"Вес короба {_payload(inp):.0f} кг выше допустимых {specs['payload_kg']} кг"
        return None

    if cat == "cleaning_robot":
        if inp.process_type != "cleaning":
            return "Уборочные роботы применимы только в процессе уборки"
        if _aisle(inp) < specs["min_aisle_width_m"]:
            return f"Проход {_aisle(inp)} м уже минимальной ширины пути {specs['min_aisle_width_m']} м"
        return None

    if cat == "service_delivery":
        if inp.process_type != "delivery":
            return "Курьерские роботы применимы только в процессе доставки"
        if _aisle(inp) < specs["min_aisle_width_m"]:
            return f"Коридор {_aisle(inp)} м уже допустимых {specs['min_aisle_width_m']} м"
        return None

    if inp.process_type != "transport":
        return "Транспортные роботы не выполняют паллетизацию/уборку/доставку"
    if inp.cargo_type not in robot.get("compatible_cargo", ["pallets", "boxes"]):
        names = {"carts": "поездов тележек (нужен AGV-тягач)",
                 "deliveries": "доставки (нужен курьерский робот)",
                 "cases": "паллетизации (нужна ячейка)"}
        return f"Класс не предназначен для: {names.get(inp.cargo_type, inp.cargo_type)}"
    if _payload(inp) > specs["payload_kg"]:
        return f"Груз {_payload(inp):.0f} кг выше грузоподъёмности {specs['payload_kg']} кг"
    if _aisle(inp) < specs["min_aisle_width_m"]:
        return f"Проход {_aisle(inp)} м уже допустимых {specs['min_aisle_width_m']} м"

    autonomy = specs.get("autonomy_hours")
    speed = specs.get("max_speed_m_s")
    if autonomy and speed:
        trip_h = 2 * _distance(inp) / speed / 3600.0
        if trip_h > autonomy * 0.8:
            return (f"Плечо {_distance(inp):.0f} м требует {trip_h:.1f} ч на рейс - "
                    f"близко к пределу автономности {autonomy} ч")
    return None


# ═══════════════════════════════════════════════════════════════
# Сайзинг
# ═══════════════════════════════════════════════════════════════
def _fleet_sizing(inp, robot, utilization):
    tp = robot.get("transport_profile") or {}
    units = inp.units_per_trip or tp.get("units_per_trip", 1)
    exchange = tp.get("exchange_time_s", LOAD_UNLOAD_TIME_S)
    trip = (2 * _distance(inp) / robot["specs"]["max_speed_m_s"]
            + EXCHANGE_OPERATIONS_PER_TRIP * exchange)
    trips_per_shift = _shift_hours(inp) * 3600 * utilization / trip
    peak_demand = (inp.pallets_per_day or 0) * _peak_share(inp)
    cap_shift = trips_per_shift * units
    if peak_demand <= 0 or cap_shift <= 0:
        return 1, 0.0
    qty = max(1, math.ceil(peak_demand / (cap_shift * TARGET_FLEET_UTILIZATION)))
    return qty, min(peak_demand / (qty * cap_shift), 1.0)


def _cleaning_sizing(inp, robot, utilization):
    cap_day = robot["specs"]["cleaning_rate_m2_h"] * _operating_hours(inp) * utilization
    demand = _daily_demand(inp)
    if cap_day <= 0:
        return 1, 0.0
    qty = max(1, math.ceil(demand / cap_day))
    return qty, min(demand / (qty * cap_day), 1.0)


def _cell_sizing(inp, robot, utilization):
    picks_per_min = (robot["specs"]["picks_per_min_max"]
                     * utilization * CELL_DESIGN_EFFICIENCY)
    bpp = _boxes_per_pallet(inp)
    cap_boxes_day = picks_per_min * 60 * _operating_hours(inp)
    cap_pallets_day = cap_boxes_day / bpp
    if cap_pallets_day <= 0:
        return 1, 0.0
    qty = max(1, math.ceil(inp.pallets_per_day / cap_pallets_day))
    return qty, min(inp.pallets_per_day / (qty * cap_pallets_day), 1.0)


# ═══════════════════════════════════════════════════════════════
# Финансовые утилиты
# ═══════════════════════════════════════════════════════════════
def _payback(capex: float, flows: list):
    cum = -capex
    for i, f in enumerate(flows, 1):
        prev = cum
        cum += f
        if cum >= 0 and f > 0:
            return round(i - 1 + (-prev) / f, 1), cum
    return 99.0, cum


def _energy_cost_per_robot(inp, econ, utilization):
    kwh = (econ.get("avg_power_w", 250) * _operating_hours(inp)
           * _days(inp) * utilization / 1000)
    return kwh * ELECTRICITY_TARIFF_RUB


def _battery_replacement(inp, econ, utilization):
    cost = econ.get("battery_cost_rub") or 0
    cycles, runtime = econ.get("battery_cycles"), econ.get("runtime_h")
    if not cost or not cycles or not runtime:
        return None
    per_year = _operating_hours(inp) * _days(inp) * utilization / runtime
    year = math.ceil(cycles / max(per_year, 1e-9))
    return year if year <= _horizon(inp) else None


# ═══════════════════════════════════════════════════════════════
# Расчёт сценария
# ═══════════════════════════════════════════════════════════════
def _calc_scenario(inp, robot, key, sc, is_zone: bool = False):
    e = robot["economics"]
    cat = robot["category"]
    h = _horizon(inp)

    if cat == "cleaning_robot":
        qty_full, fleet_util = _cleaning_sizing(inp, robot, sc["utilization"])
    elif cat == "fixed_cell":
        qty_full, fleet_util = _cell_sizing(inp, robot, sc["utilization"])
    else:
        qty_full, fleet_util = _fleet_sizing(inp, robot, sc["utilization"])

    if inp.fleet_override is not None:
        qty = max(1, inp.fleet_override)
        fleet_util = min(1.0, fleet_util * qty_full / max(qty, 1))
    else:
        qty = qty_full

    robots = qty * e["robot_capex_rub"] * sc["hw_mult"]
    chargers = (math.ceil(qty * e.get("chargers_per_robot", 0))
                * (e.get("charger_cost_rub") or 0) * sc["hw_mult"])
    integration = qty * e.get("integration_per_robot_rub", 0) * sc["hw_mult"]
    site = _site_fixed(e, is_zone=is_zone) * sc["hw_mult"]
    contingency = (robots + chargers + integration + site) * sc["contingency"]
    capex = robots + chargers + integration + site + contingency

    service = qty * e.get("annual_service_rub", 0) * sc["service_mult"]
    software = qty * e.get("annual_software_rub", 0)
    energy = qty * _energy_cost_per_robot(inp, e, sc["utilization"])
    opex = service + software + energy

    lm = _labor_model(
        inp, sc, qty=qty, qty_full=qty_full,
        fte_replace_per_shift=e["fte_replace_per_shift"],
    )
    displaced = lm["displaced"]
    retained = lm["retained"]
    cashable = lm["cashable"]
    labor = lm["labor"]
    equip = lm["equip"]
    slots = lm["slots"]
    applied = lm["applied"]
    gross = labor + equip

    flows = []
    for t in range(1, h + 1):
        factor = sc["ramp"] if t == 1 else 1.0
        labor_infl = (1 + LABOR_INFLATION) ** (t - 1)
        opex_infl = (1 + OPEX_INFLATION) ** (t - 1)
        flows.append(gross * factor * labor_infl - opex * factor * opex_infl)

    rep = _battery_replacement(inp, e, sc["utilization"])
    battery_cash = 0.0
    if rep:
        battery_cash = qty * (e.get("battery_cost_rub") or 0)
        flows[rep - 1] -= battery_cash

    residual_share = _residual_share(e)
    residual = qty * e["robot_capex_rub"] * sc["hw_mult"] * residual_share
    flows[-1] += residual

    r = _discount(inp)
    npv = -capex + sum(f / ((1 + r) ** t) for t, f in enumerate(flows, 1))
    payback, final_cum = _payback(capex, flows)

    opex_cum = sum(opex * (1 + OPEX_INFLATION) ** t for t in range(h))
    tco = capex + opex_cum + battery_cash

    benefits = gross * (sc["ramp"] + h - 1) + residual
    roi = (benefits - tco) / tco * 100 if tco > 0 else 0.0

    moves = _daily_demand(inp) * _days(inp)

    res = ScenarioResult(
        scenario=key, label=sc["label"], quantity=qty,
        utilization=sc["utilization"],
        horizon_years=h,
        capex=round(capex, -4), opex_annual=round(opex, -4),
        savings_annual=round(gross, -4), net_annual=round(gross - opex, -4),
        payback_years=payback, npv=round(npv, -4), tco=round(tco, -4),
        roi_pct=round(roi),
        cost_per_move=round(tco / max(h, 1) / moves, 1) if moves else 0.0,
        battery_replacement_year=rep)

    det = dict(qty=qty, qty_full=qty_full, fleet_util=fleet_util, slots=slots,
               displaced=displaced, retained=retained, cashable=cashable,
               applied=applied,
               pult_reason=lm["pult_reason"],
               retained_pct=lm["retained_pct"],
               retained_min=lm["retained_min"],
               min_pult_per_shift=lm["min_pult_per_shift"],
               catalog_replacement_capacity=lm["catalog_replacement_capacity"],
               residual_share=residual_share,
               residual=residual,
               horizon_years=h,
               capex=capex, final_cum=final_cum,
               opex_cum=opex_cum,
               cb=(robots, chargers, integration, site, contingency, capex),
               ob=(service, software, energy, opex))
    return res, det


# ═══════════════════════════════════════════════════════════════
# Раскладка по персоналу
# ═══════════════════════════════════════════════════════════════
def _build_staff_breakdown(inp, det) -> StaffBreakdown:
    total = inp.staff_headcount
    replaceable = det["displaced"]
    requested = inp.released_headcount
    applied = det["applied"]
    on_pult = det["retained"]
    released = det["cashable"]
    pult_min = _shifts(inp)

    is_clamped = (requested is not None and requested > replaceable + 1e-6)
    is_below_pult = (applied > 0) and (applied <= on_pult + 1e-6)
    pult_shortage = max(0.0, on_pult - applied)
    pult_source = "from_staff" if pult_shortage > 0 else "from_released"

    return StaffBreakdown(
        staff_total=total,
        staff_replaceable=round(replaceable, 1),
        staff_requested=requested,
        staff_applied=round(applied, 1),
        staff_on_pult=round(on_pult, 1),
        staff_released=round(released, 1),
        pult_minimum=pult_min,
        min_pult_per_shift=det.get("min_pult_per_shift", DEFAULT_PULT_FTE_PER_SHIFT),
        pult_reason=det.get("pult_reason", "supervision_pct"),
        pult_source=pult_source,
        pult_shortage=round(pult_shortage, 1),
        slider_enabled=total is not None and total > 0,
        slider_max=total or 0,
        is_clamped=is_clamped,
        is_below_pult=is_below_pult,
    )


# ═══════════════════════════════════════════════════════════════
# Рекомендация
# ═══════════════════════════════════════════════════════════════
def calc_recommendation(inp, robot, is_zone: bool = False) -> RobotRecommendation:
    scenarios, details = [], {}
    for key, sc in SCENARIOS.items():
        res, det = _calc_scenario(inp, robot, key, sc, is_zone=is_zone)
        scenarios.append(res)
        details[key] = det

    base, det = scenarios[1], details["base"]
    specs, e = robot["specs"], robot["economics"]
    h = det["horizon_years"]

    staff = _build_staff_breakdown(inp, det)

    score = 85
    if _shifts(inp) >= 2: score += 5
    if _shifts(inp) >= 3: score += 5
    if robot["category"] == "internal_mobile":
        margin = _aisle(inp) - specs["min_aisle_width_m"]
        if margin < 0.4: score -= 10
        if margin < 0.15: score -= 10
        if _payload(inp) > 0.85 * specs["payload_kg"]: score -= 5
    if det["fleet_util"] < 0.5: score -= 10
    if det["fleet_util"] > 0.95: score -= 10
    score = max(45, min(100, score))

    w = []
    price = robot.get("price", {})
    if price.get("basis") not in ("exact_public", None):
        w.append(price.get("note", "Цена - оценка; запросите КП интегратора"))

    if inp.fleet_override is not None and det.get("qty_full"):
        if inp.fleet_override < det["qty_full"]:
            coverage_pct = round(inp.fleet_override / det["qty_full"] * 100)
            w.append(f"Частичная роботизация парка: {inp.fleet_override} из {det['qty_full']} "
                     f"роботов - покрытие {coverage_pct}% спроса")
        elif inp.fleet_override > det["qty_full"]:
            w.append(f"Парк больше расчётной потребности ({inp.fleet_override} > {det['qty_full']}) - "
                     f"избыточные мощности")

    if staff.slider_enabled:
        if staff.staff_requested is not None:
            if staff.is_clamped:
                w.append(f"Вы указали заменить {staff.staff_requested} человек, но робот "
                         f"может заменить только {staff.staff_replaceable:.0f} "
                         f"(ограничение по производительности и сменам). "
                         f"Применено к расчёту: {staff.staff_applied:.0f} чел.")
            elif staff.is_below_pult:
                shortage_msg = ""
                if staff.pult_shortage > 0:
                    shortage_msg = (f" Из заменённых не хватает {staff.pult_shortage:.0f} "
                                    f"оператора для пульта — потребуется дополнительный "
                                    f"перевод из незаменённых.")
                w.append(f"Замена {staff.staff_applied:.0f} человек не покрывает пульт: "
                         f"нужно {staff.pult_minimum} FTE (по одному на смену), "
                         f"а заменяется только {staff.staff_applied:.0f}. "
                         f"Экономии на ФОТ нет.{shortage_msg}")
            else:
                msg = (f"Замена персонала: {staff.staff_applied:.0f} из "
                       f"{staff.staff_total} человек. На пульте остаётся "
                       f"{staff.staff_on_pult:.0f} FTE. Реально высвобождается "
                       f"{staff.staff_released:.0f} FTE (это даёт экономию)")
                if staff.pult_shortage > 0:
                    msg += (f". Из заменённых не хватает {staff.pult_shortage:.0f} "
                            f"оператора для пульта — потребуется перевод из незаменённых")
                w.append(msg)
        else:
            w.append(f"Полное высвобождение: робот может заменить {staff.staff_replaceable:.0f} FTE. "
                     f"На пульте остаётся {staff.staff_on_pult:.0f} FTE. "
                     f"Задайте ползунок «Сколько сотрудников заменить роботами», "
                     f"если планируете частичное высвобождение")
    else:
        w.append(f"Штат не задан: displaced оценён из объёма ≈ {det['displaced']:.1f} FTE "
                 f"(допущение). Задайте staff_headcount, чтобы включить ползунок")

    if staff.slider_enabled and det["displaced"] > 0:
        if staff.pult_reason == "min_per_shift":
            pct_alt = det["retained_pct"]
            w.append(f"На пульте остаётся минимум {staff.staff_on_pult:.1f} FTE = "
                     f"{staff.min_pult_per_shift:.1f} чел. × {_shifts(inp)} смен. "
                     f"Это больше, чем {SCENARIOS['base']['supervision']:.0%} "
                     f"от {det['displaced']:.1f} FTE (= {pct_alt:.1f} FTE), поэтому "
                     f"сработал жёсткий минимум. Если смена не требует человека - "
                     f"задайте min_pult_fte_per_shift=0")
        elif det["retained_pct"] > 0:
            w.append(f"На пульте остаётся {staff.staff_on_pult:.1f} FTE = "
                     f"{SCENARIOS['base']['supervision']:.0%} от {det['displaced']:.1f} FTE "
                     f"(процент supervision, base-сценарий)")

    if inp.staff_headcount:
        est = _estimate_headcount(inp, True)
        if inp.staff_headcount > est * 1.3:
            w.append(f"Штат ({inp.staff_headcount}) выше расчётной потребности (~{est:.0f}) - "
                     f"вероятен избыток персонала, эффект выше среднего")
        elif inp.staff_headcount < est * 0.7:
            w.append(f"Штат ({inp.staff_headcount}) ниже потребности (~{est:.0f}) - "
                     f"вероятны переработки/аутсорс; потолок экономии ограничен штатом")

    if inp.fte_cost_rub and inp.fte_cost_rub < 500_000:
        w.append(f"fte_cost_rub = {inp.fte_cost_rub:,.0f} ₽ меньше 500 тыс. "
                 f"Проверьте, что это годовая стоимость ФОТ, а не месячный оклад")

    if inp.peak_shift_share is None:
        w.append(f"Пиковая доля смены не задана, принята {_peak_share(inp):.0%}. "
                 f"Если пик выше - парк будет больше")

    if specs.get("navigation_type") in ("QR", "Magnetic/QR"):
        w.append("Требуется разметка пола, маршруты фиксированы")
    if det["fleet_util"] < 0.6:
        w.append(f"Загрузка флота {det['fleet_util']:.0%} - проверьте возможность сокращения парка")
    if det["fleet_util"] > 0.95:
        w.append(f"Загрузка флота {det['fleet_util']:.0%} - нет запаса на пики и поломки")

    if inp.area_m2 and det["qty"] > 0:
        area_per_robot = inp.area_m2 / det["qty"]
        if area_per_robot < MIN_AREA_PER_ROBOT_M2:
            w.append(
                f"Площадь {inp.area_m2:.0f} м² мала для {det['qty']} роботов "
                f"({area_per_robot:.0f} м² на робота, рекомендуется ≥ "
                f"{MIN_AREA_PER_ROBOT_M2:.0f} м²). Роботам может не хватить "
                f"места для маневрирования и стоянки"
            )

    if robot["category"] == "internal_mobile":
        w.append(f"Требуется {math.ceil(det['qty'] * e.get('chargers_per_robot', 0))} "
                 f"зарядных станций и Wi-Fi-покрытие маршрутов")
    if robot["category"] == "service_delivery":
        w.append("Требуется модернизация лифтов/дверей - заложено в site_fixed_warehouse")
    if robot["category"] == "cleaning_robot":
        w.append("Док-станции воды/зарядки + расходники - уточнить у вендора")
    if robot["category"] == "fixed_cell":
        w.append(f"Расчёт в паллетах при {_boxes_per_pallet(inp)} коробов/паллету - "
                 f"уточните фактическую укладку")

    rep = base.battery_replacement_year
    if rep:
        w.append(f"Замена батарей: ~год {rep} ({det['qty']} шт) - учтено в TCO и NPV")

    residual_share_used = det.get("residual_share", RESIDUAL_SHARE)
    w.append(f"Остаточная стоимость парка в год {h}: "
             f"~{det['residual'] / 1e6:.1f} млн ₽ ({residual_share_used:.0%} CAPEX, "
             f"с учётом сценарного множителя) - учтено в NPV и ROI")
    w.append(f"Горизонт расчёта: {h} лет. "
             f"Год 1 с освоением {SCENARIOS['base']['ramp']:.0%}; "
             f"ФОТ индексируется {LABOR_INFLATION:.0%}/год, OPEX {OPEX_INFLATION:.0%}/год")

    if base.payback_years >= 99:
        w.append(f"Не окупается в горизонте {h} лет")
        if det["final_cum"] > -0.05 * det["capex"]:
            w.append(f"Кумулятив на границе горизонта ({det['final_cum'] / 1e6:.1f} млн от нуля) - "
                     f"окупаемость близка к {h} годам")

    if base.net_annual <= 0 or (base.payback_years >= 99 and base.npv < 0):
        economic_status = "NOT_ACCEPTABLE"
        w.insert(0, "⚠ Экономика неприемлема: вариант не помечен как лучший")
    elif base.npv < 0 or base.payback_years >= 99:
        economic_status = "WARNING"
        w.insert(0, "⚠ Экономика погранична: требуется отдельное решение пользователя")
    else:
        economic_status = "ACCEPTABLE"
    w.append(ASSUMPTIONS["roi_note"])
    w.append(ASSUMPTIONS["note"])

    cb, ob = det["cb"], det["ob"]
    return RobotRecommendation(
        robot_id=robot["id"], robot_name=robot["name"], category=robot["category"],
        quantity=base.quantity, fleet_utilization=round(det["fleet_util"], 2),
        fte_displaced=round(det["displaced"], 1),
        fte_retained=round(det["retained"], 1),
        fte_released=round(det["cashable"], 1),
        horizon_years=h,
        capex=base.capex, opex=base.opex_annual, savings_per_year=base.savings_annual,
        payback_years=base.payback_years, npv=base.npv, tco=base.tco,
        cost_per_move=base.cost_per_move, readiness_score=score,
        price_basis=price.get("basis", "unknown"),
        price_confidence=price.get("confidence", 0),
        price_note=price.get("note", ""),
        economic_status=economic_status,
        capex_breakdown=CapexBreakdown(
            robots=round(cb[0], -4), chargers=round(cb[1], -4),
            integration=round(cb[2], -4), site_fixed=round(cb[3], -4),
            contingency=round(cb[4], -4), total=round(cb[5], -4)),
        opex_breakdown=OpexBreakdown(
            service=round(ob[0], -4), software=round(ob[1], -4),
            energy=round(ob[2], -4), total=round(ob[3], -4)),
        staff_breakdown=staff,
        scenarios=scenarios, warnings=w)


def recommendation_sort_key(rec: RobotRecommendation):
    rank = {"ACCEPTABLE": 0, "WARNING": 1, "NOT_ACCEPTABLE": 2}
    return (rank[rec.economic_status], rec.payback_years, -rec.npv)


# ═══════════════════════════════════════════════════════════════
# ZONAL: собрать UserInput для зоны
# ═══════════════════════════════════════════════════════════════
def zone_to_input(shared: UserInput, zone: Zone) -> UserInput:
    """Собирает UserInput для одной зоны.
    fleet_override берётся из зоны (не из shared)."""
    return UserInput(
        object_type=shared.object_type,
        mode="whole",
        process_type=zone.process_type,
        cargo_type=zone.cargo_type,
        pallets_per_day=zone.volume_per_day,
        area_m2=zone.area_m2,
        avg_distance_m=zone.avg_distance_m,
        shifts_count=zone.shifts_count,
        shift_hours=zone.shift_hours,
        staff_headcount=zone.staff_headcount,
        aisle_width_m=zone.aisle_width_m,
        payload_kg=zone.payload_kg,
        boxes_per_pallet=zone.boxes_per_pallet,
        cleaning_frequency_per_day=zone.cleaning_frequency_per_day,
        peak_shift_share=zone.peak_shift_share,
        units_per_trip=zone.units_per_trip,
        released_headcount=zone.released_headcount,
        min_pult_fte_per_shift=zone.min_pult_fte_per_shift,
        fte_cost_rub=shared.fte_cost_rub,
        equipment_count=None,
        operating_days=shared.operating_days,
        discount_rate=shared.discount_rate,
        horizon_years=shared.horizon_years,
        fleet_override=zone.fleet_override,
        selected_robot_ids=zone.selected_robot_ids,
    )


def calc_zone(shared: UserInput, zone: Zone, robots: List[dict]) -> ZoneResult:
    """Расчёт одной зоны."""
    zone_inp = zone_to_input(shared, zone)

    recommendations: List[RobotRecommendation] = []
    rejected: List[RejectedRobot] = []

    for robot in robots:
        reason = check_constraints(zone_inp, robot)
        selected = robot["id"] in (zone.selected_robot_ids or [])
        if reason and not selected:
            rejected.append(RejectedRobot(robot_id=robot["id"],
                                          robot_name=robot["name"],
                                          reason=reason))
            continue
        rec = calc_recommendation(zone_inp, robot, is_zone=True)
        if selected:
            rec.forced = True
            if reason:
                rec.technical_status = "FORCED_UNSUPPORTED"
                rec.warnings.insert(0, f"⚠ Выбор клиента — не проходит фильтр: {reason}")
        recommendations.append(rec)

    recommendations.sort(key=recommendation_sort_key)
    best = next((
        rec for rec in recommendations
        if rec.technical_status == "ELIGIBLE" and rec.economic_status != "NOT_ACCEPTABLE"
    ), None)
    if best:
        best.is_best = True

    if not recommendations:
        status = "NO_ELIGIBLE_EQUIPMENT"
        status_message = "Для параметров зоны нет допустимого оборудования в каталоге"
    elif best is None:
        status = "NO_ACCEPTABLE_ECONOMICS"
        status_message = "Допустимое оборудование найдено, но экономика всех вариантов неприемлема"
    else:
        status = "RECOMMENDED"
        status_message = None

    result = ZoneResult(
        zone_id=zone.id,
        zone_name=zone.name,
        process_type=zone.process_type,
        cargo_type=zone.cargo_type,
        area_m2=zone.area_m2,
        shifts_count=_shifts(zone_inp),
        shift_hours=_shift_hours(zone_inp),
        volume_per_day=zone.volume_per_day,
        staff_headcount=zone.staff_headcount,
        recommendations=recommendations,
        rejected=rejected,
        best_robot_id=best.robot_id if best else None,
        status=status,
        status_message=status_message,
        manual_baseline=manual_baseline(zone_inp),
        warnings=[status_message] if status_message else [],
    )

    if best:
        result.zone_capex = best.capex
        result.zone_opex_annual = best.opex
        result.zone_savings_annual = best.savings_per_year
        result.zone_net_annual = best.savings_per_year - best.opex
        result.zone_npv = best.npv
        result.zone_tco = best.tco
        result.zone_payback_years = best.payback_years
        result.zone_displaced = best.fte_displaced
        result.zone_released = best.fte_released
        result.zone_robots = best.quantity
        result.staff_breakdown = best.staff_breakdown
        result.warnings = best.warnings[:5]

    return result


# ═══════════════════════════════════════════════════════════════
# ZONAL: агрегация
# ═══════════════════════════════════════════════════════════════
def calc_combined(zone_results: List[ZoneResult], shared: UserInput,
                  robots: List[dict]) -> CombinedSummary:
    h = shared.horizon_years or DEFAULT_HORIZON_YEARS

    total_capex = sum(z.zone_capex for z in zone_results)
    total_opex = sum(z.zone_opex_annual for z in zone_results)
    total_savings = sum(z.zone_savings_annual for z in zone_results)
    total_npv = sum(z.zone_npv for z in zone_results)
    total_tco = sum(z.zone_tco for z in zone_results)
    total_displaced = sum(z.zone_displaced for z in zone_results)
    total_released = sum(z.zone_released for z in zone_results)
    total_robots = sum(z.zone_robots for z in zone_results)

    warehouse_fixed = 0.0
    for z in zone_results:
        if z.best_robot_id:
            for r in robots:
                if r["id"] == z.best_robot_id:
                    warehouse_fixed = max(warehouse_fixed, _warehouse_fixed(r["economics"]))
                    break

    hw_mult = SCENARIOS["base"]["hw_mult"]
    contingency_mult = 1 + SCENARIOS["base"]["contingency"]
    warehouse_capex = warehouse_fixed * hw_mult * contingency_mult

    total_capex_with_warehouse = total_capex + warehouse_capex

    net_annual = total_savings - total_opex
    combined_payback = (round(total_capex_with_warehouse / net_annual, 1)
                        if net_annual > 0 else 99.0)

    total_npv_with_warehouse = total_npv - warehouse_capex

    valid_zones = [z for z in zone_results if z.zone_payback_years < 99]
    best_zone = min(valid_zones, key=lambda z: z.zone_payback_years) if valid_zones else None

    return CombinedSummary(
        zones_count=len(zone_results),
        total_robots=total_robots,
        total_capex=round(total_capex_with_warehouse, -4),
        total_opex_annual=round(total_opex, -4),
        total_savings_annual=round(total_savings, -4),
        total_net_annual=round(net_annual, -4),
        total_displaced=round(total_displaced, 1),
        total_released=round(total_released, 1),
        total_npv=round(total_npv_with_warehouse, -4),
        total_tco=round(total_tco + warehouse_capex, -4),
        combined_payback_years=combined_payback,
        horizon_years=h,
        warehouse_fixed_rub=round(warehouse_fixed, -4),
        best_zone_id=best_zone.zone_id if best_zone else None,
        best_zone_payback=best_zone.zone_payback_years if best_zone else None,
    )
