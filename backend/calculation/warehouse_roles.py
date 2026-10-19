"""Object-wide warehouse role scenarios over the active discovery catalog.

This is a scenario engine. Text applicability and the fallback productivity are
explicit assumptions; neither is a vendor performance claim or purchase approval.
"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catalog_repository import CatalogPositionDTO, CatalogSnapshotDTO

SCHEMA = "warehouse-role-analysis-v1"
ROLE_LABELS = {
    "forklift_driver": "Оператор погрузчика",
    "loader": "Грузчик",
    "storekeeper": "Кладовщик",
    "picker": "Комплектовщик",
    "sorter": "Сортировщик",
    "packer": "Упаковщик и паллетизация",
    "cleaner": "Уборщик",
    "inventory_worker": "Сотрудник инвентаризации",
}
ROLE_PATTERNS = {
    "storekeeper": r"стеллаж|хранен|складск.*систем|storage|as.?rs|g2p|шаттл|shuttle",
    "picker": r"комплект(аци|овк|овщик)|отбор|pick|g2p",
    "sorter": r"сортир|sort",
    "packer": r"паллетиз|палетиз|palletiz|palletis|укладк.*паллет",
    "inventory_worker": r"инвентар|inventory|пересч[её]т|уч[её]т.*паллет",
}
SAFE_FACT_STATUSES = {"CORROBORATED", "CROSS_DOCUMENT_ENRICHED", "VERIFIED_OFFICIAL",
                      "VERIFIED_AUTHORIZED_PARTNER", "MANUALLY_APPROVED"}
RATE_CODES = {"throughput_units_per_hour", "units_per_hour", "picks_per_hour",
              "pallets_per_hour", "items_per_hour", "cleaning_m2_per_hour",
              "cleaning_rate_m2_h", "throughput"}


def _number(value: Decimal | int) -> str:
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def _template_path() -> Path:
    container = Path("/data/role-work/roleWorkScenarioData.json")
    return container if container.exists() else Path(__file__).resolve().parents[2] / "frontend/src/roleWorkScenarioData.json"


@lru_cache(maxsize=1)
def warehouse_template() -> dict[str, Any]:
    rows = json.loads(_template_path().read_text(encoding="utf-8"))["records"]
    roles = []
    for row in rows:
        code = row["role_code"]
        if row["object_kind"] != "WAREHOUSE" or code not in ROLE_LABELS:
            continue
        headcount = Decimal(row["object_role_headcount"])
        manual = Decimal(row["manual_units_per_person_shift"])
        roles.append({
            "role_code": code, "label": ROLE_LABELS[code],
            "headcount": str(headcount),
            "monthly_employer_cost_rub": row["monthly_amount_rub_per_person"],
            "daily_volume": str(headcount * manual),
            "manual_units_per_person_shift": str(manual),
            "robotizable_share": row["robotizable_fraction"],
            "unit": row["manual_unit"].split("/")[0],
            "basis": row["work_basis"], "evidence_ref": row["evidence_ref"],
            "scenario_purchase_price_rub": row["scenario_purchase_price_rub"],
            "salary_basis": row["salary_source_ref"],
            "source": "SCENARIO_ASSUMPTION",
        })
    return {"schema_version": "warehouse-role-template-v1", "roles": roles,
            "general": {"total_area_m2": "20000", "shifts_per_day": 2,
                        "hours_per_shift": "10", "days_per_year": 300,
                        "robot_availability": "0.75", "fleet_reserve_share": "0.1",
                        "realizable_labor_share": "0.5", "integration_share": "0.2",
                        "annual_service_share": "0.1", "discount_rate": "0.15",
                        "horizon_years": 5, "raas_monthly_rub": "150000",
                        "raas_setup_rub": "0", "raas_customer_annual_rub": "0"},
            "notice": "Значения ролей и коэффициенты являются редактируемыми сценарными допущениями, не замерами конкретного склада."}


class GeneralInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_area_m2: Decimal = Field(gt=0)
    shifts_per_day: int = Field(ge=1, le=4)
    hours_per_shift: Decimal = Field(gt=0, le=24)
    days_per_year: int = Field(ge=1, le=366)
    robot_availability: Decimal = Field(gt=0, le=1)
    fleet_reserve_share: Decimal = Field(ge=0, le=1)
    realizable_labor_share: Decimal = Field(ge=0, le=1)
    integration_share: Decimal = Field(ge=0, le=2)
    annual_service_share: Decimal = Field(ge=0, le=1)
    discount_rate: Decimal = Field(ge=0, le=1)
    horizon_years: int = Field(ge=1, le=20)
    raas_monthly_rub: Decimal | None = Field(default=None, ge=0)
    raas_setup_rub: Decimal = Field(default=Decimal("0"), ge=0)
    raas_customer_annual_rub: Decimal = Field(default=Decimal("0"), ge=0)
    gross_to_employer_factor: Decimal = Field(default=Decimal("1.302"), gt=0, le=3)


class RoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_code: str
    headcount: Decimal = Field(gt=0)
    monthly_employer_cost_rub: Decimal = Field(ge=0)
    daily_volume: Decimal = Field(gt=0)
    manual_units_per_person_shift: Decimal = Field(gt=0)
    robotizable_share: Decimal = Field(gt=0, le=1)
    source: str = Field(pattern="^(USER|SCENARIO_ASSUMPTION)$")
    basis: str = Field(min_length=3, max_length=1500)
    realizable_labor_share: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def known_role(self):
        if self.role_code not in ROLE_LABELS:
            raise ValueError("unknown warehouse role")
        return self


class CandidateOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_code: str
    position_id: str
    units_per_hour: Decimal | None = Field(default=None, gt=0)
    price_rub: Decimal | None = Field(default=None, gt=0)
    raas_monthly_rub: Decimal | None = Field(default=None, ge=0)
    omit_purchase_price: bool = False
    omit_raas_tariff: bool = False


class WarehouseRoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    general: GeneralInput
    roles: list[RoleInput] = Field(min_length=1, max_length=8)
    selected_positions: dict[str, str] = Field(default_factory=dict)
    overrides: list[CandidateOverride] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def consistent(self):
        codes = [role.role_code for role in self.roles]
        if len(codes) != len(set(codes)):
            raise ValueError("duplicate role")
        if set(self.selected_positions) - set(codes):
            raise ValueError("selected position belongs to an unselected role")
        keys = [(item.role_code, item.position_id) for item in self.overrides]
        if len(keys) != len(set(keys)) or any(code not in codes for code, _ in keys):
            raise ValueError("invalid candidate override")
        return self


def _catalog_text(position: CatalogPositionDTO) -> str:
    model = position.model
    return " ".join(filter(None, [model.name, model.description or "",
        position.applicability.scenario or ""])).casefold()


def _match_role(role_code: str, position: CatalogPositionDTO) -> str | None:
    model = position.model
    profile = model.capacity_runtime.calculation_profile
    text = _catalog_text(position)
    name = model.name.casefold()
    application = " ".join((name, position.applicability.scenario or "")).casefold()
    if role_code == "picker":
        # Voice/light guidance and goods-to-person storage assist a picker but do
        # not themselves perform the pick. A shared catalog scenario is weaker
        # evidence than the model's stated physical function.
        if re.search(r"pick.by.(voice|light)|голосов.*управлен|светов.*отбор", text):
            return None
        if re.search(r"as.?rs|shuttle|шаттл", name) and not re.search(r"комплект|отбор|pick", name):
            return None
        if re.search(ROLE_PATTERNS[role_code], name):
            return "ROLE_NAME"
        if re.search(r"станци[ия].*комплект|робот[- ]комплектовщик|автомат.*отбор", model.description or "", re.I):
            return "ROLE_DESCRIPTION"
        return None
    if role_code == "sorter":
        # The organizer assigned the broad "sorting cargo" scenario to storage,
        # manipulators and picking aids. Their scenario label alone is not enough.
        if re.search(ROLE_PATTERNS[role_code], name):
            return "ROLE_NAME"
        if re.search(r"робот.сортиров|сортировочн.*робот|автомат.*сортиров|сортиров.*посыл|сортиров.*груз", model.description or "", re.I):
            return "ROLE_DESCRIPTION"
        return None
    if role_code in {"forklift_driver", "loader"}:
        if re.search(r"инвентар|inventory", name):
            return None
        pallet_work = bool(re.search(r"паллет|палет|pallet|forklift|погрузчик", text))
        if profile == "TRANSPORT_CYCLE_V1" and pallet_work:
            return "TRANSPORT_PROFILE"
        if pallet_work and re.search(
                r"транспорт|перевоз|перемещ|mobile|amr|agv", text):
            return "CATALOG_TEXT_HINT"
    elif role_code == "cleaner":
        if profile == "CLEANING_AREA_V1":
            return "CLEANING_PROFILE"
        if re.search(r"уборк|поломо|клининг|clean|scrub", text):
            return "CATALOG_TEXT_HINT"
    elif role_code == "packer":
        if profile == "PALLETIZING_THROUGHPUT_V1":
            return "PALLETIZING_PROFILE"
        if re.search(ROLE_PATTERNS[role_code], text):
            return "ROLE_APPLICATION" if re.search(ROLE_PATTERNS[role_code], application) else "CATALOG_TEXT_HINT"
        if (re.search(r"манипулятор|robot.arm|robotic.arm", " ".join((name, (model.type_code or "").casefold())))
                and re.search(r"укладк|упаков|паллет|палет|pallet|pack|склад|логист", text)
                and not re.search(r"agro|урож|яблок|сельск", text)):
            return "GENERAL_MANIPULATOR_HINT"
    elif re.search(ROLE_PATTERNS[role_code], text):
        return "ROLE_APPLICATION" if re.search(ROLE_PATTERNS[role_code], application) else "CATALOG_TEXT_HINT"
    return None


def _verified_rate(position: CatalogPositionDTO, unit: str) -> tuple[Decimal | None, str | None]:
    unit_tokens = {"pallet": ("pallet", "паллет"), "pick": ("pick", "отбор"),
                   "item": ("item", "шт"), "m2": ("m2", "м²")}.get(unit, ())
    for fact in position.model.facts:
        if fact.code not in RATE_CODES or fact.resolution_status not in SAFE_FACT_STATUSES or not fact.evidence_id:
            continue
        if not any(token in fact.canonical_unit.casefold() for token in unit_tokens):
            continue
        if not any(token in fact.canonical_unit.casefold() for token in ("hour", "/h", "/ч", "час")):
            continue
        try:
            rate = Decimal(str(fact.value))
        except Exception:
            continue
        if rate.is_finite() and rate > 0:
            return rate, fact.evidence_id
    return None, None


def _candidate(role: RoleInput, position: CatalogPositionDTO, general: GeneralInput,
               override: CandidateOverride | None, match_basis: str) -> dict[str, Any]:
    unit = warehouse_template_unit(role.role_code)
    verified_rate, rate_evidence = _verified_rate(position, unit)
    rate = (override.units_per_hour if override and override.units_per_hour is not None
            else verified_rate if verified_rate is not None
            else role.manual_units_per_person_shift / general.hours_per_shift)
    rate_source = ("USER" if override and override.units_per_hour is not None else
                   "CATALOG_VERIFIED" if verified_rate is not None else "SCENARIO_ASSUMPTION")
    target = role.daily_volume * role.robotizable_share
    daily_per_robot = rate * general.hours_per_shift * general.shifts_per_day * general.robot_availability
    fleet = math.ceil(target / daily_per_robot * (1 + general.fleet_reserve_share))
    potential_fte = min(role.headcount, target / role.manual_units_per_person_shift)
    labor_share = role.realizable_labor_share if role.realizable_labor_share is not None else general.realizable_labor_share
    fte = potential_fte * labor_share
    annual_reallocated_hours = fte * general.hours_per_shift * general.days_per_year
    annual_labor = fte * role.monthly_employer_cost_rub * 12
    purchase = position.procurement_option
    catalog_price = (purchase.amount if purchase and purchase.currency == "RUB" and purchase.amount and purchase.amount > 0
                     else None)
    scenario_price = Decimal(next(row["scenario_purchase_price_rub"] for row in warehouse_template()["roles"]
                                  if row["role_code"] == role.role_code))
    price = (None if override and override.omit_purchase_price else
             override.price_rub if override and override.price_rub is not None else
             catalog_price if catalog_price is not None else scenario_price)
    price_source = ("UNKNOWN" if price is None else "USER" if override and override.price_rub is not None else
                    "CATALOG" if catalog_price is not None else "SCENARIO_ASSUMPTION")
    capex = price * fleet * (1 + general.integration_share) if price is not None else None
    annual_service = price * fleet * general.annual_service_share if price is not None else None
    annual_net = annual_labor - annual_service if annual_service is not None else None
    npv = (sum(annual_net / (1 + general.discount_rate) ** year
               for year in range(1, general.horizon_years + 1)) - capex
           if annual_net is not None and capex is not None else None)
    payback = capex / annual_net if annual_net is not None and annual_net > 0 else None
    horizon = general.horizon_years
    purchase_tco = capex + annual_service * horizon if capex is not None else None
    purchase_roi = (annual_net * horizon - capex) / capex * 100 if capex is not None and capex > 0 else None
    rent = (None if override and override.omit_raas_tariff else
            override.raas_monthly_rub if override and override.raas_monthly_rub is not None else general.raas_monthly_rub)
    rent_source = "USER" if override and override.raas_monthly_rub is not None else "SCENARIO_ASSUMPTION" if rent is not None else "UNKNOWN"
    raas_capex = general.raas_setup_rub * fleet
    raas_annual_cost = rent * fleet * 12 + general.raas_customer_annual_rub * fleet if rent is not None else None
    raas_net = annual_labor - raas_annual_cost if raas_annual_cost is not None else None
    raas_npv = (sum(raas_net / (1 + general.discount_rate) ** year for year in range(1, horizon + 1)) - raas_capex
                if raas_net is not None else None)
    discount_factor = sum(Decimal(1) / (1 + general.discount_rate) ** year for year in range(1, horizon + 1))
    sensitivity = [{"labor_share": _number(share),
                    "annual_labor_rub": _number(potential_fte * share * role.monthly_employer_cost_rub * 12),
                    "purchase_npv_rub": _number((potential_fte * share * role.monthly_employer_cost_rub * 12 - annual_service) * discount_factor - capex) if capex is not None else None,
                    "raas_npv_rub": _number((potential_fte * share * role.monthly_employer_cost_rub * 12 - raas_annual_cost) * discount_factor - raas_capex) if raas_annual_cost is not None else None}
                   for share in (Decimal("0"), Decimal("0.5"), Decimal("1"))]
    picking_supply_only = (role.role_code == "picker" and
                           bool(re.search(r"станци[ия].*комплект", position.model.description or "", re.I)))
    return {
        "position_id": position.id, "model_id": position.model.id, "name": position.model.name,
        "source_row_number": getattr(position, "source_row_number", None),
        "manufacturer": position.model.manufacturer,
        "maturity_status": position.model.maturity_status,
        "match_basis": match_basis, "match_status": "NEEDS_PHYSICAL_CHECK",
        "work_scope": ("DELIVERY_TO_PICKING_STATION" if picking_supply_only else
                       "PALLET_TRANSPORT_ONLY" if role.role_code == "loader" else "DIRECT_ROLE_WORK"),
        "calculation_profile": position.model.capacity_runtime.calculation_profile,
        "calculation_ready": position.model.capacity_runtime.calculation_ready,
        "unit": unit, "target_units_per_day": _number(target),
        "annual_robotized_units": _number(target * general.days_per_year),
        "robot_units_per_hour": _number(rate), "rate_source": rate_source,
        "rate_evidence_ref": rate_evidence if rate_source == "CATALOG_VERIFIED" else None,
        "rate_basis": (("Условно один робот обслуживает станцию с объёмом отбора одного сотрудника за смену; робот не отбирает товар сам. Это не паспортная производительность."
                        if picking_supply_only else
                        "Условно один робот перевозит объём паллет одного грузчика за смену; погрузка и разгрузка остаются ручными. Это не паспортная производительность."
                        if role.role_code == "loader" else
                        "Условно один робот за смену выполняет объём работы одного сотрудника; это не паспортная производительность.")
                       if rate_source == "SCENARIO_ASSUMPTION" else None),
        "fleet": fleet, "potential_fte": _number(potential_fte),
        "realizable_labor_share": _number(labor_share), "fte_equivalent": _number(fte),
        "annual_reallocated_hours": _number(annual_reallocated_hours),
        "annual_labor_potential_rub": _number(annual_labor),
        "price_rub": _number(price) if price is not None else None,
        "price_source": price_source,
        "price_evidence_ref": purchase.evidence_id if price_source == "CATALOG" else None,
        "capex_rub": _number(capex) if capex is not None else None,
        "annual_service_rub": _number(annual_service) if annual_service is not None else None,
        "annual_net_rub": _number(annual_net) if annual_net is not None else None,
        "npv_rub": _number(npv) if npv is not None else None,
        "payback_years": _number(payback) if payback is not None else None,
        "purchase_tco_rub": _number(purchase_tco) if purchase_tco is not None else None,
        "purchase_roi_percent": _number(purchase_roi) if purchase_roi is not None else None,
        "raas_monthly_rub": _number(rent) if rent is not None else None,
        "raas_source": rent_source, "raas_capex_rub": _number(raas_capex),
        "raas_annual_cost_rub": _number(raas_annual_cost) if raas_annual_cost is not None else None,
        "raas_tco_rub": _number(raas_capex + raas_annual_cost * horizon) if raas_annual_cost is not None else None,
        "raas_annual_net_rub": _number(raas_net) if raas_net is not None else None,
        "raas_npv_rub": _number(raas_npv) if raas_npv is not None else None,
        "raas_roi_percent": None if raas_capex == 0 else _number((raas_net * horizon - raas_capex) / raas_capex * 100) if raas_net is not None else None,
        "labor_sensitivity": sensitivity,
        "status": "RESEARCH_ONLY" if position.model.maturity_status == "RND" else
                  "SCENARIO_WITH_PRICE" if price is not None else "SCENARIO_NEEDS_PRICE",
    }


def warehouse_template_unit(role_code: str) -> str:
    return {row["role_code"]: row["unit"] for row in warehouse_template()["roles"]}[role_code]


def analyze_warehouse_roles(value: WarehouseRoleInput, catalog: CatalogSnapshotDTO) -> dict[str, Any]:
    if catalog.version.status != "PUBLISHED":
        raise ValueError("active catalog is not published")
    overrides = {(item.role_code, item.position_id): item for item in value.overrides}
    role_results = []
    selected_candidates = []
    for role in value.roles:
        candidates = []
        for position in catalog.positions:
            basis = _match_role(role.role_code, position)
            if basis is not None:
                candidates.append(_candidate(role, position, value.general,
                    overrides.get((role.role_code, position.id)), basis))
        basis_rank = {"ROLE_NAME": 0, "TRANSPORT_PROFILE": 0, "CLEANING_PROFILE": 0,
                      "PALLETIZING_PROFILE": 0, "ROLE_DESCRIPTION": 1,
                      "ROLE_APPLICATION": 2, "CATALOG_TEXT_HINT": 3,
                      "GENERAL_MANIPULATOR_HINT": 4}
        candidates.sort(key=lambda row: (row["status"] == "RESEARCH_ONLY",
                                         basis_rank.get(row["match_basis"], 4),
                                         not row["calculation_ready"], row["price_rub"] is None,
                                         row["fleet"], row["name"], row["position_id"]))
        selected_id = value.selected_positions.get(role.role_code)
        if selected_id is None:
            selected_id = next((row["position_id"] for row in candidates if row["status"] != "RESEARCH_ONLY"), None)
        if selected_id == "NONE":
            selected_id = None
        if selected_id and selected_id not in {row["position_id"] for row in candidates}:
            raise ValueError(f"selected position is not a candidate for {role.role_code}")
        selected = next((row for row in candidates if row["position_id"] == selected_id), None)
        if selected is not None:
            selected_candidates.append({"role_code": role.role_code, **selected})
        role_results.append({
            "role_code": role.role_code, "label": ROLE_LABELS[role.role_code],
            "headcount": _number(role.headcount), "monthly_employer_cost_rub": _number(role.monthly_employer_cost_rub),
            "daily_volume": _number(role.daily_volume), "unit": warehouse_template_unit(role.role_code),
            "annual_volume": _number(role.daily_volume * value.general.days_per_year),
            "robotizable_share": _number(role.robotizable_share), "source": role.source,
            "basis": role.basis, "catalog_checked": len(catalog.positions),
            "excluded_count": len(catalog.positions) - len(candidates),
            "candidates": candidates, "selected_position_id": selected_id,
            "status": "CANDIDATES" if candidates else "NO_CATALOG_MATCH",
        })
    all_priced = bool(selected_candidates) and all(row["capex_rub"] is not None for row in selected_candidates)
    all_rented = bool(selected_candidates) and all(row["raas_monthly_rub"] is not None for row in selected_candidates)
    total_capex = sum(Decimal(row["capex_rub"]) for row in selected_candidates) if all_priced else None
    total_net = sum(Decimal(row["annual_net_rub"]) for row in selected_candidates) if all_priced else None
    rent_capex = sum(Decimal(row["raas_capex_rub"]) for row in selected_candidates) if all_rented else None
    rent_net = sum(Decimal(row["raas_annual_net_rub"]) for row in selected_candidates) if all_rented else None
    portfolio = {"selected_roles": len(selected_candidates),
                 "selected_robot_allocations": sum(row["fleet"] for row in selected_candidates),
                 "baseline_annual_labor_rub": _number(sum(role.headcount * role.monthly_employer_cost_rub * 12
                     for role in value.roles if role.role_code in {item["role_code"] for item in selected_candidates})),
                 "fte_equivalent": _number(sum(Decimal(row["fte_equivalent"]) for row in selected_candidates)),
                 "potential_fte": _number(sum(Decimal(row["potential_fte"]) for row in selected_candidates)),
                 "annual_labor_potential_rub": _number(sum(Decimal(row["annual_labor_potential_rub"]) for row in selected_candidates)),
                 "capex_rub": _number(sum(Decimal(row["capex_rub"]) for row in selected_candidates)) if all_priced else None,
                 "annual_net_rub": _number(sum(Decimal(row["annual_net_rub"]) for row in selected_candidates)) if all_priced else None,
                 "npv_rub": _number(sum(Decimal(row["npv_rub"]) for row in selected_candidates)) if all_priced else None,
                 "purchase_tco_rub": _number(sum(Decimal(row["purchase_tco_rub"]) for row in selected_candidates)) if all_priced else None,
                 "purchase_roi_percent": _number((total_net * value.general.horizon_years - total_capex) / total_capex * 100) if all_priced and total_capex > 0 else None,
                 "raas_capex_rub": _number(rent_capex) if all_rented else None,
                 "raas_tco_rub": _number(sum(Decimal(row["raas_tco_rub"]) for row in selected_candidates)) if all_rented else None,
                 "raas_annual_net_rub": _number(rent_net) if all_rented else None,
                 "raas_npv_rub": _number(sum(Decimal(row["raas_npv_rub"]) for row in selected_candidates)) if all_rented else None,
                 "raas_roi_percent": None if not all_rented or rent_capex == 0 else _number((rent_net * value.general.horizon_years - rent_capex) / rent_capex * 100),
                 "missing_purchase": [f"{row['role_code']}/{row['position_id']}.price_rub" for row in selected_candidates if row["capex_rub"] is None],
                 "missing_raas": [f"{row['role_code']}/{row['position_id']}.raas_monthly_rub" for row in selected_candidates if row["raas_monthly_rub"] is None],
                 "status": "RESEARCH_SCENARIO" if any(row["status"] == "RESEARCH_ONLY" for row in selected_candidates)
                           else "SCENARIO_WITH_PRICE" if all_priced else "PARTIAL"}
    return {"schema_version": SCHEMA, "catalog_version": catalog.version.code,
            "catalog_positions_checked": len(catalog.positions),
            "general": value.general.model_dump(mode="json"), "roles": role_results,
            "portfolio": portfolio,
            "limitations": [
                "Соответствие роли и робота по тексту каталога требует проверки физических условий на объекте.",
                "Если нет подтверждённой выработки модели, использована сценарная оценка: один робот обслуживает условный объём работы одного сотрудника за смену в пределах указанных функций робота.",
                "Робот подвоза к станции комплектации не выполняет отбор, а паллетный транспорт не выполняет погрузку; их эффект относится только к указанной части работы роли.",
                "Высвобождаемые ставки и деньги — сценарный потенциал при указанной доле реализации, не обещание сокращения штата.",
                "Если одна модель выбрана для нескольких ролей, парк считается отдельными назначениями; общая загрузка роботов между ролями не доказана.",
                "Интеграция, сервис и ставка дисконтирования заданы общими допущениями; налоги, расходники и финансирование не детализированы.",
            ]}
