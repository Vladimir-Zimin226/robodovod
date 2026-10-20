"""One serializable investment report projection shared by preview UI and PDF.

All money comes from the role engines. Cashflow series only distributes their
annual net values across years using the reported discount rate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _amount(value: Decimal | None) -> str | None:
    return None if value is None else f"{value.quantize(Decimal('0.01')):.2f}"


def _money_text(value: str) -> str:
    """Format narrative rubles without changing the numeric report fields."""
    return f"{Decimal(value):,.2f}".replace(",", " ").replace(".", ",")


def _finance(capex: Any, annual_net: Any, npv: Any, roi: Any, payback: Any,
             discount: Decimal, active_horizon: int) -> dict[str, Any]:
    initial, yearly = _decimal(capex), _decimal(annual_net)
    if initial is None or yearly is None:
        return {"capex_rub": capex, "annual_net_rub": annual_net,
                "npv_rub": npv, "roi_percent": roi, "payback_years": payback,
                "cashflows": [], "horizons": []}
    cumulative = -initial
    cashflows = [{"year": 0, "net_rub": _amount(-initial),
                  "cumulative_rub": _amount(cumulative)}]
    for year in range(1, 11):
        cumulative += yearly
        cashflows.append({"year": year, "net_rub": _amount(yearly),
                          "cumulative_rub": _amount(cumulative)})
    horizons = []
    for years in (5, 10):
        calculated = sum((yearly / (1 + discount) ** year
                          for year in range(1, years + 1)), -initial)
        horizons.append({"years": years,
            "npv_rub": npv if years == active_horizon else _amount(calculated),
            "roi_percent": roi if years == active_horizon else
            _amount((yearly * years - initial) / initial * 100) if initial > 0 else None})
    return {"capex_rub": capex, "annual_net_rub": annual_net,
            "npv_rub": npv, "roi_percent": roi, "payback_years": payback,
            "cashflows": cashflows, "horizons": horizons}


def build_role_report_view(result: dict[str, Any]) -> dict[str, Any]:
    """Project an immutable engine result; no catalog lookup or input mutation."""
    warehouse = result["schema_version"].startswith("warehouse-role-analysis")
    kind = result.get("kind", "WAREHOUSE")
    name = {"WAREHOUSE": "Склад", "AIRPORT": "Аэропорт", "CLINIC": "Клиника"}[kind]
    general = result["general"]
    years = int(general["horizon_years"])
    discount = Decimal(str(general["discount_rate"]))
    works, simulations, sources, safety = [], [], [], []
    for role in result["roles"]:
        entries = role.get("works", []) if not warehouse else [role]
        for work in entries:
            selected = None if not warehouse else next((candidate for candidate in role["candidates"]
                if candidate["position_id"] == role["selected_position_id"]), None)
            source = selected if warehouse else work
            object_candidate = None if warehouse else next((candidate for candidate in work["candidates"]
                if candidate["position_id"] == work["selected_position_id"]), None)
            item = {"role": role["label"], "task": work.get("technical_task", role["label"]),
                "headcount": role["headcount"], "salary_rub_month": role["monthly_employer_cost_rub"],
                "volume_per_day": work["daily_volume"], "unit": work["unit"],
                "model": source.get("name") if warehouse and source else
                    source.get("selected_model_name") if source else None,
                "position_id": source.get("position_id") if warehouse and source else
                    work.get("selected_position_id"),
                "fleet": source.get("fleet") if source else 0,
                "physical_fit": source.get("physical_fit") if warehouse and source else
                    object_candidate.get("physical_fit") if object_candidate else None,
                "rate_source": source.get("rate_source") if source else None,
                "price_source": source.get("price_source") if source else None,
                "evidence_ref": work.get("evidence_ref") or role.get("source"),
                "safety_conditions": work.get("safety_conditions"),
                "simulation": source.get("simulation") if source else None}
            works.append(item)
            if item["simulation"]:
                sim = item["simulation"]
                simulations.append({"role": role["label"], "status": sim["status"],
                    "cycle_s": sim.get("cycle_s"), "distance_loaded_m": sim.get("distance_loaded_m"),
                    "distance_empty_m": sim.get("distance_empty_m"), "time_wait_s": sim.get("time_wait_s"),
                    "fleet_required": sim.get("fleet_required"), "flags": sim.get("flags", []),
                    "shared_lane": sim.get("shared_lane")})
            if item["safety_conditions"]:
                safety.append(f"{role['label']}: {item['safety_conditions']}")
            sources.append({"role": role["label"], "rate": item["rate_source"],
                "price": item["price_source"], "evidence": item["evidence_ref"],
                "position_id": item["position_id"],
                "payload_evidence_id": (selected or object_candidate or {}).get("payload_evidence_id"),
                "rate_evidence_ref": (selected or {}).get("rate_evidence_ref"),
                "price_evidence_ref": (selected or {}).get("price_evidence_ref")})
    total = result["portfolio"] if warehouse else result["base_total"]
    financial_rows = ([next((candidate for candidate in role["candidates"]
        if candidate["position_id"] == role["selected_position_id"]), None)
        for role in result["roles"]] if warehouse else
        [work for role in result["roles"] for work in role["works"] if not work["safety_conditions"]])
    financial_rows = [row for row in financial_rows if row is not None]
    purchase = _finance(total.get("capex_rub") if warehouse else total["purchase"]["capex_rub"],
        total.get("annual_net_rub") if warehouse else total["purchase"]["annual_net_rub"],
        total.get("npv_rub") if warehouse else total["purchase"]["npv_rub"],
        total.get("purchase_roi_percent") if warehouse else total["purchase"]["roi_percent"],
        total.get("purchase_payback_years") if warehouse else total["purchase"]["payback_years"],
        discount, years)
    rent = _finance(total.get("raas_capex_rub") if warehouse else total["raas"]["capex_rub"],
        total.get("raas_annual_net_rub") if warehouse else total["raas"]["annual_net_rub"],
        total.get("raas_npv_rub") if warehouse else total["raas"]["npv_rub"],
        total.get("raas_roi_percent") if warehouse else total["raas"]["roi_percent"],
        None, discount, years)
    rent_costs = [row.get("raas_annual_cost_rub") if warehouse else row["raas"].get("annual_cost_rub")
                  for row in financial_rows]
    rent["annual_operating_cost_rub"] = (_amount(sum((_decimal(cost) for cost in rent_costs), Decimal(0)))
                                          if rent_costs and all(cost is not None for cost in rent_costs) else None)
    fleet = total["selected_robot_allocations"] if warehouse else total["fleet"]
    labor = _decimal(total.get("annual_labor_potential_rub") if warehouse else total.get("annual_labor_rub"))
    purchase_cost = labor - _decimal(purchase["annual_net_rub"]) if labor is not None and purchase["annual_net_rub"] is not None else None
    waterfall = []
    if labor is not None and purchase_cost is not None and purchase["capex_rub"] is not None:
        factor = sum((Decimal(1) / (1 + discount) ** year for year in range(1, years + 1)), Decimal(0))
        benefit_pv = labor * factor
        service_pv = purchase_cost * factor
        capex = _decimal(purchase["capex_rub"])
        steps = [("PV реализуемого ФОТ", Decimal(0), benefit_pv),
                 ("PV сервиса", benefit_pv, benefit_pv - service_pv),
                 ("CAPEX покупки", benefit_pv - service_pv, benefit_pv - service_pv - capex)]
        waterfall = [{"label": label, "start_rub": _amount(start), "end_rub": _amount(end),
                      "amount_rub": _amount(end - start)} for label, start, end in steps]
        waterfall.append({"label": "NPV покупки", "start_rub": "0.00",
                          "end_rub": purchase["npv_rub"], "amount_rub": purchase["npv_rub"]})
    sensitivity = []
    for index, share in enumerate(("0", "0.5", "1")):
        parts = [row["labor_sensitivity"][index] for row in financial_rows
                 if len(row.get("labor_sensitivity", [])) > index]
        complete_purchase = bool(parts) and all(item["purchase_npv_rub"] is not None for item in parts)
        complete_rent = bool(parts) and all(item["raas_npv_rub"] is not None for item in parts)
        sensitivity.append({"labor_share": share,
            "purchase_npv_rub": _amount(sum((_decimal(item["purchase_npv_rub"]) for item in parts), Decimal(0))) if complete_purchase else None,
            "raas_npv_rub": _amount(sum((_decimal(item["raas_npv_rub"]) for item in parts), Decimal(0))) if complete_rent else None})
    risks = [
        "Типовой сценарий не подтверждает инженерную пригодность или паспорт робота."
        if item == "Типовой сценарий не является утверждённой формулой C11 или паспортом робота."
        else item
        for item in [*result.get("limitations", []), *safety]
    ]
    if any(item["physical_fit"] in ("UNKNOWN", "FAIL") for item in works):
        risks.append("Физическая пригодность части назначений не подтверждена.")
    if any(sim["status"] != "MODELED" for sim in simulations):
        risks.append("Часть маршрутов не смоделирована; положительный эффект для них не подтверждён.")
    status = "Демонстрационная геометрия; сценарные допущения требуют проверки на объекте"
    object_name = {"WAREHOUSE": "склада", "AIRPORT": "аэропорта", "CLINIC": "клиники"}[kind]
    conclusion = (f"Для {object_name} расчётный парк — {fleet}. "
        + (f"NPV покупки за {years} лет: {_money_text(purchase['npv_rub'])} ₽. " if purchase["npv_rub"] is not None
           else "NPV покупки не рассчитан: нужны цены. ")
        + (f"NPV аренды: {_money_text(rent['npv_rub'])} ₽." if rent["npv_rub"] is not None
           else "NPV аренды не рассчитан: нужен тариф."))
    return {"schema_version": "role-report-view-v1", "object": name,
        "date_utc": datetime.now(timezone.utc).date().isoformat(),
        "evidence_status": status, "catalog_version": result["catalog_version"],
        "calculation_version": result["schema_version"], "executive_conclusion": conclusion,
        "active_horizon_years": years, "discount_rate": str(discount),
        "fleet": fleet, "fte_equivalent": total["fte_equivalent"],
        "works": works, "simulations": simulations,
        "economics": {"purchase": purchase, "raas": rent},
        "waterfall": waterfall, "sensitivity": sensitivity,
        "conditional": None if warehouse else {"fleet": result["conditional_total"]["fleet"],
            "purchase_npv_rub": result["conditional_total"]["purchase"]["npv_rub"],
            "warning": result.get("safety_warning")},
        "what_if": "Временные изменения с шага «Деньги» не входят в базовый PDF; его скачивают по исходному сценарию.",
        "sources": sources, "risks": risks,
        "assumptions": {key: general[key] for key in ("robot_availability", "fleet_reserve_share",
            "realizable_labor_share", "integration_share", "annual_service_share", "discount_rate")}}
