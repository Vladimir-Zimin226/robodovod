"""Versioned object role scenarios. Rates and budgets are explicit assumptions, not C11 passports."""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from calculation.warehouse_roles import GeneralInput, ROLE_LABELS as WAREHOUSE_LABELS, _number

SCHEMA = "object-role-analysis-v3"
KINDS = {"WAREHOUSE", "AIRPORT", "CLINIC"}
LABELS = {**WAREHOUSE_LABELS,
    "baggage_handler": "Обработчик багажа", "trolley_operator": "Оператор тележек",
    "special_equipment_driver": "Водитель спецтехники", "terminal_cleaner": "Уборщик терминала",
    "perron_cleaner": "Уборщик перрона", "runway_inspector": "Инспектор ВПП",
    "security_guard": "Охранник", "passenger_assistant": "Ассистент пассажиров",
    "courier": "Курьер", "ramp_worker": "Работник перрона",
    "ground_support_worker": "Сотрудник наземной поддержки",
    "catering_worker": "Сотрудник пищеблока", "laundry_worker": "Сотрудник прачечной",
    "sanitary": "Санитар", "porter": "Транспортировщик",
    "lab_assistant": "Лаборант", "sterile_supply_worker": "Сотрудник ЦСО",
    "consumable_worker": "Сотрудник снабжения", "lab_result_courier": "Курьер результатов",
    "cleaner": "Уборщик", "inventory_worker": "Сотрудник инвентаризации",
}
FUNCTIONS = {
    "baggage_handler": r"багаж|baggage", "trolley_operator": r"тележ|cart|trolley|amr|agv",
    "special_equipment_driver": r"amr|agv|транспорт|достав|перевоз",
    "terminal_cleaner": r"уборк|clean|scrub|поломо", "perron_cleaner": r"уборк|clean|sweep|подмет",
    "runway_inspector": r"инспекц|inspection|патрул|drone|дрон",
    "security_guard": r"патрул|security|охран|видеонаблюд",
    "passenger_assistant": r"багаж|luggage|тележ|cart|достав",
    "courier": r"курьер|достав|amr|agv", "ramp_worker": r"перевоз|транспорт|amr|agv",
    "ground_support_worker": r"перевоз|транспорт|amr|agv",
    "catering_worker": r"достав|транспорт|amr|agv", "laundry_worker": r"достав|транспорт|amr|agv",
    "sanitary": r"достав|транспорт|amr|agv", "porter": r"достав|транспорт|amr|agv",
    "lab_assistant": r"достав|транспорт|amr|agv", "sterile_supply_worker": r"достав|транспорт|amr|agv",
    "consumable_worker": r"достав|транспорт|amr|agv", "lab_result_courier": r"достав|транспорт|amr|agv",
    "cleaner": r"уборк|clean|scrub|поломо", "inventory_worker": r"инвентар|inventory|сканир",
}


@lru_cache(maxsize=1)
def rows() -> list[dict[str, Any]]:
    path = Path("/data/role-work/roleWorkScenarioData.json")
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / "frontend/src/roleWorkScenarioData.json"
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def object_template(kind: str) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unknown object kind")
    roles: dict[str, dict[str, Any]] = {}
    for row in rows():
        if row["object_kind"] != kind:
            continue
        code = row["role_code"]
        if code not in roles:
            roles[code] = {"role_code": code, "label": LABELS.get(code, code),
                "headcount": row["object_role_headcount"],
                "monthly_employer_cost_rub": row["monthly_amount_rub_per_person"],
                "salary_basis": row["monthly_amount_basis"],
                "headcount_source": row["headcount_source_ref"],
                "salary_source": row["salary_source_ref"],
                "realizable_labor_share": "0.5", "works": []}
        demand = Decimal(row["object_role_headcount"]) * Decimal(row["process_allocation_fraction"]) * Decimal(row["manual_units_per_person_shift"])
        roles[code]["works"].append({
            "process_code": row["process_code"], "evidence_ref": row["evidence_ref"],
            "technical_task": row["technical_task"], "daily_volume": _number(demand),
            "manual_units_per_person_shift": row["manual_units_per_person_shift"],
            "unit": row["manual_unit"].split("/")[0],
            "allocation_fraction": row["process_allocation_fraction"],
            "robotizable_share": row["robotizable_fraction"],
            "robot_units_per_hour": _number(Decimal(row["manual_units_per_person_shift"]) / Decimal(7 if kind != "WAREHOUSE" else 10)),
            "scenario_purchase_price_rub": row["scenario_purchase_price_rub"],
            "raas_mode": "PERCENT", "raas_percent_monthly": "2",
            "scenario_raas_monthly_rub": row["scenario_raas_monthly_rub"],
            "rate_source": row["scenario_rate_source"], "price_source": "SCENARIO_ASSUMPTION",
            "raas_source": "SCENARIO_ASSUMPTION",
            "basis": row["work_basis"], "residual_operations": row["residual_operations"],
            "calculation_status": row["calculation_status"],
            "safety_conditions": row["safety_conditions"], "selected_position_id": "AUTO",
        })
    return {"schema_version": "object-role-template-v3", "kind": kind,
            "general": {"total_area_m2": "20000", "shifts_per_day": 1 if kind != "WAREHOUSE" else 2,
                "hours_per_shift": "7" if kind != "WAREHOUSE" else "10", "days_per_year": 300,
                "robot_availability": "0.75", "fleet_reserve_share": "0.1",
                "realizable_labor_share": "0.5", "integration_share": "0.2",
                "annual_service_share": "0.1", "discount_rate": "0.15", "horizon_years": 5,
                "raas_monthly_rub": None, "raas_setup_rub": "0", "raas_customer_annual_rub": "0",
                "gross_to_employer_factor": "1.302"},
            "roles": list(roles.values()),
            "notice": "Все объёмы, технические подзадачи, выработка и цены — редактируемые типовые допущения, не замеры, паспорт робота или коммерческое предложение."}


class WorkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_code: str
    evidence_ref: str
    technical_task: str = Field(min_length=3)
    daily_volume: Decimal = Field(gt=0)
    manual_units_per_person_shift: Decimal = Field(gt=0)
    unit: str
    allocation_fraction: Decimal = Field(gt=0, le=1)
    robotizable_share: Decimal = Field(ge=0, le=1)
    robot_units_per_hour: Decimal = Field(gt=0)
    scenario_purchase_price_rub: Decimal | None = Field(default=None, gt=0)
    scenario_raas_monthly_rub: Decimal | None = Field(default=None, ge=0)
    raas_mode: str = Field(default="FIXED", pattern="^(FIXED|PERCENT)$")
    raas_percent_monthly: Decimal | None = Field(default=None, ge=0, le=100)
    rate_source: str
    price_source: str
    raas_source: str = "SCENARIO_ASSUMPTION"
    basis: str = Field(min_length=3)
    residual_operations: str
    calculation_status: str
    safety_conditions: str = ""
    selected_position_id: str = "AUTO"


class ObjectRole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_code: str
    headcount: Decimal = Field(gt=0)
    monthly_employer_cost_rub: Decimal = Field(ge=0)
    salary_basis: str = Field(default="EMPLOYER_COST", pattern="^(EMPLOYER_COST|GROSS)$")
    headcount_source: str = "SCENARIO_ASSUMPTION"
    salary_source: str = "SCENARIO_ASSUMPTION"
    realizable_labor_share: Decimal = Field(ge=0, le=1)
    works: list[WorkInput] = Field(min_length=1)

    @model_validator(mode="after")
    def allocation(self):
        if sum((w.allocation_fraction for w in self.works), Decimal(0)) > 1:
            raise ValueError("role work allocations exceed one staff group")
        if len({w.process_code for w in self.works}) != len(self.works):
            raise ValueError("duplicate work within role")
        return self


class ObjectRoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    general: GeneralInput
    roles: list[ObjectRole] = Field(min_length=1, max_length=25)
    include_safety_in_conditional: bool = True

    @model_validator(mode="after")
    def unique_roles(self):
        if self.kind not in KINDS or len({r.role_code for r in self.roles}) != len(self.roles):
            raise ValueError("unknown kind or duplicate role")
        valid = {(row["role_code"], row["process_code"]): row
                 for row in rows() if row["object_kind"] == self.kind}
        for role in self.roles:
            for work in role.works:
                source = valid.get((role.role_code, work.process_code))
                if source is None or source["manual_unit"].split("/")[0] != work.unit:
                    raise ValueError("role work or physical unit does not belong to object")
                if (work.calculation_status != source["calculation_status"] or
                        work.safety_conditions != source["safety_conditions"] or
                        work.evidence_ref != source["evidence_ref"]):
                    raise ValueError("immutable evidence, status or safety conditions changed")
        return self


def _candidates(role_code: str, process_code: str, catalog: Any) -> list[dict[str, Any]]:
    pattern = FUNCTIONS.get(role_code, r"a^")
    if process_code == "clinic_waste_b":
        pattern = r"класс[а ]*б|biohazard|infectious waste|медицинск.*отход"
    elif process_code == "airport_apron_cleaning":
        pattern = r"перрон|apron|outdoor.*clean|наружн.*уборк"
    result = []
    for position in catalog.positions:
        model = position.model
        # Match the stated function; a general object tag alone is insufficient.
        text = f"{model.name} {model.description or ''}".casefold()
        if not re.search(pattern, text):
            continue
        result.append({"position_id": position.id, "name": model.name,
            "manufacturer": model.manufacturer, "maturity_status": model.maturity_status,
            "match_basis": "CATALOG_FUNCTION_TEXT", "physical_fit": "UNCONFIRMED"})
    return sorted(result, key=lambda x: (x["maturity_status"] == "RND", x["name"]))


def _economics(fleet: int, annual_labor: Decimal, potential_annual_labor: Decimal,
               work: WorkInput, general: GeneralInput) -> dict[str, Any]:
    price = work.scenario_purchase_price_rub
    rent = (price * work.raas_percent_monthly / 100
            if work.raas_mode == "PERCENT" and price is not None and work.raas_percent_monthly is not None else
            None if work.raas_mode == "PERCENT" else work.scenario_raas_monthly_rub)
    horizon, discount = general.horizon_years, general.discount_rate
    factor = sum(Decimal(1) / (1 + discount) ** year for year in range(1, horizon + 1))
    capex = price * fleet * (1 + general.integration_share) if price is not None else None
    service = price * fleet * general.annual_service_share if price is not None else None
    net = annual_labor - service if service is not None else None
    rcapex = general.raas_setup_rub * fleet
    rcost = (rent * 12 + general.raas_customer_annual_rub) * fleet if rent is not None else None
    rnet = annual_labor - rcost if rcost is not None else None
    sensitivity = [{"labor_share": _number(share),
        "annual_labor_rub": _number(potential_annual_labor * share),
        "purchase_npv_rub": _number((potential_annual_labor * share - service) * factor - capex) if capex is not None else None,
        "raas_npv_rub": _number((potential_annual_labor * share - rcost) * factor - rcapex) if rcost is not None else None}
        for share in (Decimal("0"), Decimal("0.5"), Decimal("1"))]
    return {"labor_sensitivity": sensitivity,
        "purchase": {"capex_rub": _number(capex) if capex is not None else None,
        "annual_cost_rub": _number(service) if service is not None else None,
        "annual_net_rub": _number(net) if net is not None else None,
        "tco_rub": _number(capex + service * horizon) if capex is not None else None,
        "npv_rub": _number(net * factor - capex) if capex is not None else None,
        "roi_percent": _number((net * horizon - capex) / capex * 100) if capex is not None and capex > 0 else None,
        "payback_years": _number(capex / net) if capex is not None and net > 0 else None,
        "missing": [] if price is not None else ["scenario_purchase_price_rub"]},
        "raas": {"capex_rub": _number(rcapex) if rent is not None else None,
        "mode": work.raas_mode,
        "percent_monthly": _number(work.raas_percent_monthly) if work.raas_mode == "PERCENT" and work.raas_percent_monthly is not None else None,
        "price_basis_rub": _number(price) if work.raas_mode == "PERCENT" and price is not None else None,
        "monthly_per_robot_rub": _number(rent) if rent is not None else None,
        "annual_cost_rub": _number(rcost) if rcost is not None else None,
        "annual_net_rub": _number(rnet) if rnet is not None else None,
        "tco_rub": _number(rcapex + rcost * horizon) if rcost is not None else None,
        "npv_rub": _number(rnet * factor - rcapex) if rnet is not None else None,
        "roi_percent": None if rcapex == 0 or rnet is None else _number((rnet * horizon - rcapex) / rcapex * 100),
        "roi_status": "N/A: CAPEX заказчика равен нулю" if rcapex == 0 else "DEFINED",
        "missing": [] if rent is not None else
        (["scenario_purchase_price_rub"] if price is None else ["raas_percent_monthly"])
        if work.raas_mode == "PERCENT" else ["scenario_raas_monthly_rub"]}}


def _portfolio(works: list[dict[str, Any]], general: GeneralInput) -> dict[str, Any]:
    labor = sum((Decimal(w["annual_labor_rub"]) for w in works), Decimal(0))
    baseline_roles = {w["role_code"]: Decimal(w["role_headcount"]) * Decimal(w["role_monthly_employer_cost_rub"]) * 12
                      for w in works}
    result = {"work_count": len(works), "fleet": sum(w["fleet"] for w in works),
        "baseline_annual_labor_rub": _number(sum(baseline_roles.values(), Decimal(0))),
        "potential_fte": _number(sum((Decimal(w["potential_fte"]) for w in works), Decimal(0))),
        "fte_equivalent": _number(sum((Decimal(w["fte_equivalent"]) for w in works), Decimal(0))),
        "annual_labor_rub": _number(labor)}
    for branch in ("purchase", "raas"):
        complete = all(not w[branch]["missing"] for w in works)
        missing = sorted({f"{w['role_code']}/{w['process_code']}.{field}"
                          for w in works for field in w[branch]["missing"]})
        capex = sum((Decimal(w[branch]["capex_rub"]) for w in works), Decimal(0)) if complete else None
        net = sum((Decimal(w[branch]["annual_net_rub"]) for w in works), Decimal(0)) if complete else None
        result[branch] = {"capex_rub": _number(capex) if complete else None,
            "annual_net_rub": _number(net) if complete else None,
            "tco_rub": _number(sum(Decimal(w[branch]["tco_rub"]) for w in works)) if complete else None,
            "npv_rub": _number(sum(Decimal(w[branch]["npv_rub"]) for w in works)) if complete else None,
            "roi_percent": _number((net * general.horizon_years - capex) / capex * 100) if complete and capex > 0 else None,
            "roi_status": "N/A: CAPEX заказчика равен нулю" if complete and capex == 0 else "DEFINED" if complete else "NEEDS_INPUT",
            "missing": missing}
    return result


def analyze_object_roles(value: ObjectRoleInput, catalog: Any) -> dict[str, Any]:
    if catalog.version.status != "PUBLISHED":
        raise ValueError("active catalog is not published")
    roles_out, all_works = [], []
    for role in value.roles:
        work_out = []
        for work in role.works:
            candidates = _candidates(role.role_code, work.process_code, catalog)
            selected = work.selected_position_id
            if selected == "AUTO":
                selected = next((c["position_id"] for c in candidates if c["maturity_status"] != "RND"), "SCENARIO_TYPE")
            if selected not in {"SCENARIO_TYPE", "NONE"} and selected not in {c["position_id"] for c in candidates}:
                raise ValueError(f"selected position is not a functional candidate for {role.role_code}")
            target = work.daily_volume * work.robotizable_share
            capacity = work.robot_units_per_hour * value.general.hours_per_shift * value.general.shifts_per_day * value.general.robot_availability
            fleet = math.ceil(target / capacity * (1 + value.general.fleet_reserve_share)) if selected != "NONE" else 0
            potential = min(role.headcount * work.allocation_fraction, target / work.manual_units_per_person_shift) if selected != "NONE" else Decimal(0)
            fte = potential * role.realizable_labor_share
            monthly_employer = role.monthly_employer_cost_rub * (value.general.gross_to_employer_factor if role.salary_basis == "GROSS" else 1)
            labor = fte * monthly_employer * 12
            economics = _economics(fleet, labor, potential * monthly_employer * 12, work, value.general)
            row = {"role_code": role.role_code, "role_headcount": _number(role.headcount),
                "role_monthly_employer_cost_rub": _number(monthly_employer),
                "process_code": work.process_code, "evidence_ref": work.evidence_ref,
                "technical_task": work.technical_task, "unit": work.unit,
                "daily_volume": _number(work.daily_volume), "robotizable_share": _number(work.robotizable_share),
                "target_units_per_day": _number(target), "robot_units_per_hour": _number(work.robot_units_per_hour),
                "rate_source": work.rate_source, "price_source": work.price_source,
                "raas_source": work.raas_source,
                "scenario_purchase_price_rub": _number(work.scenario_purchase_price_rub) if work.scenario_purchase_price_rub is not None else None,
                "scenario_raas_monthly_rub": _number(work.scenario_raas_monthly_rub) if work.scenario_raas_monthly_rub is not None else None,
                "raas_mode": work.raas_mode,
                "raas_percent_monthly": _number(work.raas_percent_monthly) if work.raas_percent_monthly is not None else None,
                "allocation_fraction": _number(work.allocation_fraction), "fleet": fleet,
                "potential_fte": _number(potential), "fte_equivalent": _number(fte),
                "annual_labor_rub": _number(labor), "annual_reallocated_hours": _number(fte * value.general.hours_per_shift * value.general.days_per_year),
                "calculation_status": work.calculation_status,
                "scenario_contract": "ASSUMPTION_V2" if work.calculation_status == "REFERENCE_ONLY" else "SCENARIO_V2",
                "safety_conditions": work.safety_conditions,
                "residual_operations": work.residual_operations, "basis": work.basis,
                "candidates": candidates, "selected_position_id": selected,
                "selected_model_name": next((c["name"] for c in candidates if c["position_id"] == selected), None),
                "model_status": "NO_CATALOG_MATCH_SCENARIO_TYPE" if selected == "SCENARIO_TYPE" and not candidates else "SCENARIO_TYPE_SELECTED" if selected == "SCENARIO_TYPE" else "NO_ROBOT" if selected == "NONE" else "CATALOG_FUNCTION_UNCONFIRMED",
                **economics}
            work_out.append(row)
            all_works.append(row)
        roles_out.append({"role_code": role.role_code, "label": LABELS.get(role.role_code, role.role_code),
            "headcount": _number(role.headcount), "monthly_employer_cost_rub": _number(role.monthly_employer_cost_rub * (value.general.gross_to_employer_factor if role.salary_basis == "GROSS" else 1)),
            "salary_input_rub": _number(role.monthly_employer_cost_rub), "salary_basis": role.salary_basis,
            "headcount_source": role.headcount_source, "salary_source": role.salary_source,
            "realizable_labor_share": _number(role.realizable_labor_share),
            "allocated_fraction": _number(sum((w.allocation_fraction for w in role.works), Decimal(0))),
            "works": work_out})
    base = [w for w in all_works if not w["safety_conditions"]]
    conditional = all_works if value.include_safety_in_conditional else base
    return {"schema_version": SCHEMA, "catalog_version": catalog.version.code,
        "kind": value.kind, "general": value.general.model_dump(mode="json"),
        "roles": roles_out, "base_total": _portfolio(base, value.general),
        "conditional_total": _portfolio(conditional, value.general),
        "safety_warning": "Условный расчёт; безопасность и допуск не подтверждены" if len(conditional) > len(base) else None,
        "limitations": ["Типовой сценарий не является утверждённой формулой C11 или паспортом робота.",
            "Парк по работам суммируется без повторного использования между назначениями.",
            "Штат каждой роли учитывается один раз; доли её работ суммарно не больше 1.",
            "Цены покупки и тарифы аренды — бюджетные допущения, не предложения поставщиков."]}
