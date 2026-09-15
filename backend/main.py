import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import UserInput, CalculationResponse, RejectedRobot
from economics import (
    calc_recommendation, check_constraints, manual_baseline,
    assess_data_quality, validate_mandatory,
    calc_zone, calc_combined,
    recommendation_sort_key,
    ASSUMPTIONS, SOURCES,
    DEFAULT_AREA_M2, DEFAULT_HORIZON_YEARS,
)
from simulation import generate_simulation
from auditor import conduct_interview
from scenario_spec import build_scenario_spec

from fleet import (
    ROBOTS as _ROBOTS_PYDANTIC,
    ROBOT_BY_ID as _ROBOT_BY_ID_PYDANTIC,
    CATEGORY_ORDER,
    CATEGORY_LABELS,
    as_dicts,
    by_category_dicts,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("robomera.api")


# ═══════════════════════════════════════════════════════════════
# Парк роботов — сериализованные словари.
# economics.py работает с robot["specs"], поэтому оставляем dict-представление.
# ═══════════════════════════════════════════════════════════════
ROBOTS = as_dicts()
ROBOT_BY_ID = {r["id"]: r for r in ROBOTS}


# ═══════════════════════════════════════════════════════════════
# Пресеты. fte_cost_rub считается от месячного оклада через
# economics.FULLY_LOADED_MULT (1.55), чтобы совпадать с auditor._parse_money.
# ═══════════════════════════════════════════════════════════════
def _fte(monthly_rub: int) -> float:
    """Месячный оклад -> годовая полная стоимость FTE (с overhead и текучкой)."""
    return round(monthly_rub * 12 * 1.55, -3)


PRESETS = {
    "retail": {
        "object_type": "retail",
        "mode": "whole",
        "process_type": "transport",
        "cargo_type": "pallets",
        "area_m2": 12000,
        "avg_distance_m": 180,
        "pallets_per_day": 800,
        "shifts_count": 3,
        "shift_hours": 8,
        "fte_cost_rub": _fte(90_000),
        "aisle_width_m": 2.4,
        "payload_kg": 700,
        "staff_headcount": 12,
        "horizon_years": 5,
    },
    "airport": {
        "object_type": "airport",
        "mode": "whole",
        "process_type": "transport",
        "cargo_type": "carts",
        "area_m2": 80000,
        "avg_distance_m": 600,
        "pallets_per_day": 480,
        "shifts_count": 3,
        "shift_hours": 8,
        "fte_cost_rub": _fte(70_000),
        "aisle_width_m": 2.5,
        "staff_headcount": 12,
        "horizon_years": 5,
    },
    "clinic": {
        "object_type": "clinic",
        "mode": "whole",
        "process_type": "delivery",
        "cargo_type": "deliveries",
        "area_m2": 6000,
        "avg_distance_m": 300,
        "pallets_per_day": 300,
        "shifts_count": 2,
        "shift_hours": 8,
        "fte_cost_rub": _fte(70_000),
        "aisle_width_m": 1.2,
        "staff_headcount": 10,
        "horizon_years": 5,
    },
}


app = FastAPI(title="РобоМера API", version="3.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


class AuditRequest(BaseModel):
    message: str
    history: list = []
    collected: dict = {}
    meta: dict = {}


# ═══════════════════════════════════════════════════════════════
# Служебные
# ═══════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"service": "РобоМера", "version": "3.4.0", "status": "ok"}


# ═══════════════════════════════════════════════════════════════
# Парк роботов
# ═══════════════════════════════════════════════════════════════
@app.get("/api/robots")
def list_robots():
    """Плоский список всего парка."""
    return ROBOTS


@app.get("/api/robots/by-category")
def list_robots_by_category():
    """Парк, сгруппированный по категориям с человекочитаемыми заголовками."""
    return by_category_dicts()


@app.get("/api/robots/categories")
def list_categories():
    """Список категорий в фиксированном порядке."""
    return [{"key": c, "label": CATEGORY_LABELS[c]} for c in CATEGORY_ORDER]


@app.get("/api/robots/{robot_id}")
def get_robot(robot_id: str):
    """Карточка одного робота по id."""
    robot = ROBOT_BY_ID.get(robot_id)
    if not robot:
        raise HTTPException(404, f"Робот '{robot_id}' не найден")
    return robot


# ═══════════════════════════════════════════════════════════════
# Пресеты и источники
# ═══════════════════════════════════════════════════════════════
@app.get("/api/presets/{object_type}")
def get_preset(object_type: str):
    if object_type not in PRESETS:
        raise HTTPException(404, "Пресет не найден")
    return PRESETS[object_type]


@app.get("/api/sources")
def sources():
    prices = [
        {"group": "Цены решений", "parameter": r["name"],
         "value": r.get("price", {}).get("note", ""),
         "type": r.get("price", {}).get("basis", "")}
        for r in ROBOTS
    ]
    return {"usd_rub_rate": 90.0, "sources": SOURCES + prices}


# ═══════════════════════════════════════════════════════════════
# Интервью
# ═══════════════════════════════════════════════════════════════
@app.post("/api/audit")
def audit(req: AuditRequest):
    return conduct_interview(req.message, req.history, req.collected, req.meta)


# ═══════════════════════════════════════════════════════════════
# Расчёт — whole + zonal
# ═══════════════════════════════════════════════════════════════
@app.post("/api/calculate")
def calculate(inp: UserInput) -> CalculationResponse:
    err = validate_mandatory(inp)
    if err:
        raise HTTPException(400, err)

    assumptions = dict(ASSUMPTIONS)
    assumptions["horizon_years"] = inp.horizon_years or DEFAULT_HORIZON_YEARS

    # ─── Zonal-режим ───
    if inp.mode == "zonal":
        try:
            zone_results = [calc_zone(inp, z, ROBOTS) for z in inp.zones]
            combined = calc_combined(zone_results, inp, ROBOTS)
        except Exception as e:
            logger.exception("Zonal calculation failed")
            raise HTTPException(500, f"Ошибка расчёта по зонам: {e}")

        revision_id, scenario_spec, response_warnings = build_scenario_spec(
            inp, [], zone_results, combined, ROBOT_BY_ID,
        )
        return CalculationResponse(
            revision_id=revision_id,
            mode="zonal",
            zones=zone_results,
            combined=combined,
            data_quality=assess_data_quality(inp),
            assumptions=assumptions,
            warnings=response_warnings,
            scenario_spec=scenario_spec,
        )

    # ─── Whole-режим ───
    recommendations, rejected = [], []
    for robot in ROBOTS:
        reason = check_constraints(inp, robot)
        selected = robot["id"] in (inp.selected_robot_ids or [])
        if reason and not selected:
            rejected.append(RejectedRobot(robot_id=robot["id"],
                                          robot_name=robot["name"], reason=reason))
            continue
        rec = calc_recommendation(inp, robot, is_zone=False)
        if selected:
            rec.forced = True
            if reason:
                rec.technical_status = "FORCED_UNSUPPORTED"
                rec.warnings.insert(0, f"⚠ Выбор клиента — не проходит фильтр: {reason}")
        recommendations.append(rec)

    if not recommendations:
        raise HTTPException(400, "Ни одно решение не проходит: " +
                            "; ".join(r.reason for r in rejected))

    # Экономически неприемлемый вариант остаётся доступен для сравнения, но не
    # получает семантику "лучшего" и не становится основой сцены.
    recommendations.sort(key=recommendation_sort_key)
    best = next((
        rec for rec in recommendations
        if rec.technical_status == "ELIGIBLE" and rec.economic_status != "NOT_ACCEPTABLE"
    ), None)
    if best:
        best.is_best = True
    response_warnings = []
    if best is None:
        response_warnings.append(
            "Допустимое оборудование найдено, но экономика всех вариантов неприемлема; "
            "лучшая рекомендация не назначена"
        )

    # Симуляция только для процессов, где она осмысленна
    sim = None
    if best and inp.process_type == "palletizing":
        from models import SimulationData, SimulationUnit
        sim = SimulationData(width_m=22.0, height_m=14.0, robots_count=best.quantity,
                             corridors_x=[8.0, 12.0, 16.0], main_aisle_y=2.0,
                             units=[SimulationUnit(id=0, speed=0.5,
                                                   route=[[2, 2], [9, 2], [16, 2], [9, 2]])])
    elif best and inp.process_type == "transport":
        sim_inp = inp.model_copy(update={"area_m2": inp.area_m2 or DEFAULT_AREA_M2})
        sim = generate_simulation(sim_inp, ROBOT_BY_ID[best.robot_id], best.quantity)

    revision_id, scenario_spec, contract_warnings = build_scenario_spec(
        inp, recommendations, [], None, ROBOT_BY_ID,
    )
    return CalculationResponse(
        revision_id=revision_id,
        mode="whole",
        recommendations=recommendations,
        rejected=rejected,
        simulation=sim,
        manual_baseline=manual_baseline(inp),
        data_quality=assess_data_quality(inp),
        assumptions=assumptions,
        warnings=response_warnings + contract_warnings,
        scenario_spec=scenario_spec,
    )
