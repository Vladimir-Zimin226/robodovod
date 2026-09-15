"""Build the public, deterministic ScenarioSpec v1 contract.

The calculation service owns this adapter. RobCraft must consume the resulting
DTO and must not infer economics or inspect internal calculation structures.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Optional

from economics import DEFAULT_HORIZON_YEARS, LOAD_UNLOAD_TIME_S
from models import (
    CombinedSummary,
    RobotRecommendation,
    ScenarioAssumption,
    ScenarioEconomics,
    ScenarioFacility,
    ScenarioFleetItem,
    ScenarioPresentation,
    ScenarioSpec,
    ScenarioTaskProfile,
    ScenarioZone,
    UserInput,
    ZoneResult,
)


TEMPLATE_BY_OBJECT = {
    "retail": "warehouse",
    "airport": "airport",
    "clinic": "hospital",
    "other": "warehouse",
}

VISUAL_PROFILE_BY_MODEL = {
    "agv_pallet_qr": "pallet-amr",
    "amr_light_250": "cargo-amr",
    "amr_heavy_1350": "pallet-amr",
    "agv_tug_k05": "tugger",
    "courier_flashbot": "medical-delivery",
    "bella_bot": "service-delivery",
    "cleaner_cc1_pro": "service-cleaner",
    "sweeper_mt1": "industrial-cleaner",
    "palletizer_cell_21": "palletizer-cell",
}

TASK_KIND = {
    ("transport", "pallets"): "pallet_move",
    ("transport", "boxes"): "box_move",
    ("transport", "carts"): "cart_move",
    ("delivery", "deliveries"): "delivery",
    ("cleaning", "pallets"): "cleaning",
    ("palletizing", "cases"): "palletizing",
}


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _best(recommendations: Iterable[RobotRecommendation]) -> Optional[RobotRecommendation]:
    return next((rec for rec in recommendations if rec.is_best), None)


def _visualization_candidate(
    recommendations: Iterable[RobotRecommendation],
) -> Optional[RobotRecommendation]:
    """Return a technically valid model without promoting its economics."""
    return next((rec for rec in recommendations if rec.technical_status == "ELIGIBLE"), None)


def _effective_units_per_trip(inp_units: Optional[int], robot: dict) -> int:
    return int(inp_units or (robot.get("transport_profile") or {}).get("units_per_trip", 1))


def _task_profile(zone_id: str, process_type: str, cargo_type: str,
                  demand: Optional[float], units: Optional[int], robot: dict):
    if not demand or demand <= 0:
        return None
    transport = robot.get("transport_profile") or {}
    return ScenarioTaskProfile(
        zone_id=zone_id,
        kind=TASK_KIND.get((process_type, cargo_type), process_type),
        demand_per_day=demand,
        units_per_trip=_effective_units_per_trip(units, robot),
        exchange_time_s=float(transport.get("exchange_time_s", LOAD_UNLOAD_TIME_S)),
    )


def build_scenario_spec(
    inp: UserInput,
    recommendations: list[RobotRecommendation],
    zone_results: list[ZoneResult],
    combined: Optional[CombinedSummary],
    robot_by_id: dict[str, dict],
) -> tuple[str, ScenarioSpec, list[str]]:
    zones: list[ScenarioZone] = []
    fleet: list[ScenarioFleetItem] = []
    tasks: list[ScenarioTaskProfile] = []
    chosen: list[RobotRecommendation] = []
    visualization_only: list[RobotRecommendation] = []
    warnings: list[str] = []

    if inp.mode == "zonal":
        zone_input_by_id = {zone.id: zone for zone in inp.zones}
        for result in zone_results:
            zone_inp = zone_input_by_id[result.zone_id]
            demand = zone_inp.area_m2 if zone_inp.process_type == "cleaning" else zone_inp.volume_per_day
            zones.append(ScenarioZone(
                id=result.zone_id,
                name=result.zone_name or result.zone_id,
                process_type=result.process_type,
                cargo_type=result.cargo_type,
                status=result.status,
                demand_per_day=demand,
                avg_distance_m=zone_inp.avg_distance_m,
                aisle_width_m=zone_inp.aisle_width_m,
                polygon=zone_inp.polygon,
            ))
            rec = _best(result.recommendations)
            if rec is None:
                if result.status_message:
                    warnings.append(f"Зона «{result.zone_name}»: {result.status_message}")
                rec = _visualization_candidate(result.recommendations)
                if rec is None:
                    continue
                visualization_only.append(rec)
            else:
                chosen.append(rec)
            robot = robot_by_id[rec.robot_id]
            fleet.append(_fleet_item(result.zone_id, rec, robot))
            task = _task_profile(
                result.zone_id, result.process_type, result.cargo_type,
                demand, zone_inp.units_per_trip, robot,
            )
            if task:
                tasks.append(task)
    else:
        rec = _best(recommendations)
        status = "RECOMMENDED" if rec else (
            "NO_ELIGIBLE_EQUIPMENT" if not recommendations else "NO_ACCEPTABLE_ECONOMICS"
        )
        demand = inp.area_m2 if inp.process_type == "cleaning" else inp.pallets_per_day
        zones.append(ScenarioZone(
            id="whole-object",
            name="Весь объект",
            process_type=inp.process_type,
            cargo_type=inp.cargo_type,
            status=status,
            demand_per_day=demand,
            avg_distance_m=inp.avg_distance_m,
            aisle_width_m=inp.aisle_width_m,
            polygon=inp.polygon,
        ))
        if rec:
            chosen.append(rec)
            robot = robot_by_id[rec.robot_id]
            fleet.append(_fleet_item("whole-object", rec, robot))
            task = _task_profile(
                "whole-object", inp.process_type, inp.cargo_type,
                demand, inp.units_per_trip, robot,
            )
            if task:
                tasks.append(task)
        else:
            warnings.append("Нет экономически приемлемой лучшей рекомендации")
            rec = _visualization_candidate(recommendations)
            if rec:
                visualization_only.append(rec)
                robot = robot_by_id[rec.robot_id]
                fleet.append(_fleet_item("whole-object", rec, robot))
                task = _task_profile(
                    "whole-object", inp.process_type, inp.cargo_type,
                    demand, inp.units_per_trip, robot,
                )
                if task:
                    tasks.append(task)

    if inp.mode == "zonal" and combined is not None:
        capex = combined.total_capex
        opex = combined.total_opex_annual
        savings = combined.total_savings_annual
        payback = combined.combined_payback_years
        npv = combined.total_npv
        tco = combined.total_tco
        released = combined.total_released
    elif chosen:
        rec = chosen[0]
        capex, opex, savings = rec.capex, rec.opex, rec.savings_per_year
        payback, npv, tco = rec.payback_years, rec.npv, rec.tco
        released = rec.fte_released
    else:
        capex = opex = savings = npv = tco = released = 0.0
        payback = 99.0

    statuses = {rec.economic_status for rec in chosen}
    if not chosen:
        economic_status = "NOT_ACCEPTABLE"
    elif warnings or "WARNING" in statuses or "NOT_ACCEPTABLE" in statuses:
        economic_status = "WARNING"
    else:
        economic_status = "ACCEPTABLE"

    confidences = [rec.price_confidence for rec in chosen if rec.price_confidence > 0]
    confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

    supplied_areas = [zone.area_m2 for zone in inp.zones if zone.area_m2 is not None]
    area = inp.area_m2
    if inp.mode == "zonal" and supplied_areas:
        area = sum(supplied_areas)

    geometry_provided = bool(inp.polygon or any(zone.polygon for zone in inp.zones))
    assumptions = [
        ScenarioAssumption(
            code="PROVIDED_ZONE_GEOMETRY" if geometry_provided else "CONCEPTUAL_GEOMETRY",
            message="Переданы привязанные к зонам полигоны" if geometry_provided else "Геометрия не передана; RobCraft должен использовать концептуальный шаблон",
        ),
        ScenarioAssumption(
            code="ECONOMICS_BACKEND_OWNED",
            message="Экономический snapshot рассчитан backend и не пересчитывается в renderer",
        ),
    ]
    if visualization_only:
        assumptions.append(ScenarioAssumption(
            code="VISUALIZATION_ONLY_NOT_RECOMMENDATION",
            message=(
                "Парк для зоны с NO_ACCEPTABLE_ECONOMICS передан только для "
                "визуализации технического сценария и не является рекомендацией"
            ),
        ))

    input_payload = inp.model_dump(mode="json")
    for optional_geometry_field in ("facility_width_m", "facility_depth_m", "polygon"):
        if input_payload.get(optional_geometry_field) is None:
            input_payload.pop(optional_geometry_field, None)
    for zone_payload in input_payload.get("zones", []):
        if zone_payload.get("polygon") is None:
            zone_payload.pop("polygon", None)
    seed = f"scenario-{_canonical_hash(input_payload)[:16]}"
    body = {
        "schema_version": "scenario-spec-v1",
        "source": "calculation",
        "template": TEMPLATE_BY_OBJECT[inp.object_type],
        "seed": seed,
        "presentation": ScenarioPresentation().model_dump(mode="json"),
        "facility": ScenarioFacility(
            area_m2=area,
            width_m=inp.facility_width_m,
            depth_m=inp.facility_depth_m,
            geometry_status="PROVIDED" if geometry_provided else "ASSUMED" if area is not None else "UNKNOWN",
            occupancy_percent=None,
        ).model_dump(mode="json"),
        "zones": [zone.model_dump(mode="json") for zone in zones],
        "fleet": [item.model_dump(mode="json") for item in fleet],
        "task_profiles": [task.model_dump(mode="json") for task in tasks],
        "economics": ScenarioEconomics(
            horizon_years=inp.horizon_years or DEFAULT_HORIZON_YEARS,
            capex_rub=capex,
            annual_opex_rub=opex,
            annual_savings_rub=savings,
            payback_years=None if payback >= 99 else payback,
            npv_rub=npv,
            tco_rub=tco,
            fte_released=released,
            confidence=confidence,
            status=economic_status,
        ).model_dump(mode="json"),
        "assumptions": [item.model_dump(mode="json") for item in assumptions],
        "warnings": warnings,
    }
    revision_id = f"calc_{_canonical_hash(body)[:16]}"
    spec = ScenarioSpec(revision_id=revision_id, **body)
    return revision_id, spec, warnings


def _fleet_item(zone_id: str, rec: RobotRecommendation, robot: dict) -> ScenarioFleetItem:
    specs = robot["specs"]
    return ScenarioFleetItem(
        zone_id=zone_id,
        equipment_model_id=rec.robot_id,
        visual_profile=VISUAL_PROFILE_BY_MODEL.get(rec.robot_id, robot["category"]),
        quantity=rec.quantity,
        max_speed_m_s=specs["max_speed_m_s"],
        payload_kg=specs["payload_kg"],
    )
