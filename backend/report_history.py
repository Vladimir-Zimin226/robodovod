"""Read-only report cards from immutable analysis and simulation evidence."""

from __future__ import annotations

from typing import Any


ECONOMICS_INPUTS = (
    "manual_units_per_shift", "role_salaries_confirmed_as_monthly_gross",
    "control_headcount", "control_monthly_gross", "technician_headcount",
    "technician_monthly_gross", "evaluation_date", "horizon_years",
    "discount_rate", "organizer_price_currency_rub_confirmed",
    "implementation_cost_total_gross", "annual_service_per_robot_gross",
    "warranty_years", "average_power_w", "initial_battery_in_robot_price_confirmed",
    "battery_replacements_in_service_confirmed", "shared_site_capital_gross",
    "shared_annual_cost_gross", "raas_monthly_per_robot_gross",
    "raas_contract_months", "raas_infrastructure_owner",
    "raas_vendor_scope_confirmed", "start_seconds_from_midnight", "timezone",
)


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _confirmed(value: Any, field: str, inputs: dict) -> bool:
    if value is None or value == "" or value is False:
        return False
    if _dict(inputs.get("field_sources")).get(field) != "ASSUMPTION":
        return True
    evidence = _dict(_dict(inputs.get("assumption_evidence")).get(field))
    return evidence.get("confirmed") is True and str(evidence.get("confirmed_value")) == str(value)


def _npv(result: dict) -> list[dict[str, str]]:
    values = []
    for scenario in result.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        financial = _dict(scenario.get("financial"))
        metric = _dict(financial.get("npv_project"))
        if (financial.get("status") != "COMPLETE" or metric.get("status") != "COMPLETE"
                or metric.get("value") is None or metric.get("unit") != "RUB"):
            continue
        if result.get("schema_version") == "economics-partial-result-v1":
            state = next((item for item in result.get("scenario_statuses", [])
                          if isinstance(item, dict) and item.get("scenario_id") == scenario.get("scenario_id")), None)
            if not state or state.get("status") != "CALCULATED":
                continue
        acquisition = scenario.get("acquisition")
        uncertainty = scenario.get("uncertainty")
        if acquisition in {"PURCHASE", "RAAS"} and uncertainty in {"BASE", "PESSIMISTIC", "OPTIMISTIC"}:
            values.append({"acquisition": acquisition, "uncertainty": uncertainty,
                           "value": str(metric["value"]), "unit": "RUB"})
    return values


def _branches(run: Any, result: dict, *, fleet: Any, simulation_count: int) -> dict[str, str]:
    branches = {key: "NOT_CALCULATED" for key in ("capacity", "labour", "purchase", "raas")}
    if fleet is not None:
        branches["capacity"] = "CALCULATED"
    if result.get("schema_version") == "economics-partial-result-v1":
        for key in branches:
            status = _dict(_dict(result.get("branches")).get(key)).get("status")
            if status in {"AVAILABLE", "CALCULATED"}:
                branches[key] = "CALCULATED"
    elif result.get("schema_version") in {"commercial-scenarios-bundle-v2", "commercial-scenarios-bundle-v3"}:
        roles = result.get("roles")
        if isinstance(roles, list) and roles and all(_dict(role.get("monthly_gross_salary")).get("status") == "KNOWN" for role in roles if isinstance(role, dict)):
            branches["labour"] = "CALCULATED"
        for scenario in result.get("scenarios", []):
            if isinstance(scenario, dict) and _dict(scenario.get("financial")).get("status") == "COMPLETE":
                key = str(scenario.get("acquisition", "")).lower()
                if key in branches:
                    branches[key] = "CALCULATED"
    elif run.run_kind == "FULL_ANALYSIS":
        for key in ("labour", "purchase", "raas"):
            branches[key] = "UNKNOWN"
    branches["simulation"] = "SAVED" if simulation_count > 0 else "NOT_SAVED"
    return branches


def _capacity_source(run: Any, by_id: dict[str, Any]) -> Any | None:
    if run.run_kind == "CAPACITY_ANALYSIS":
        return run
    inputs = _dict(run.input_snapshot)
    source_id = inputs.get("capacity_run_id") or _dict(run.result_snapshot).get("capacity_run_id")
    source = by_id.get(str(source_id))
    if source is None and run.parent_run_id is not None:
        parent = by_id.get(str(run.parent_run_id))
        if parent is not None and parent.run_kind == "CAPACITY_ANALYSIS":
            source = parent
    return source if source is not None and source.run_kind == "CAPACITY_ANALYSIS" else None


def summarize_run(run: Any, by_id: dict[str, Any], *, model_names: dict[Any, str] | None = None,
                  simulation_count: int = 0) -> dict[str, Any]:
    """Project one row without changing a run or interpreting unknown money as zero."""
    result = _dict(run.result_snapshot)
    capacity = _capacity_source(run, by_id)
    source_input = _dict(capacity.input_snapshot if capacity is not None else run.input_snapshot)
    process = _dict(source_input.get("process"))
    zone = source_input.get("zone_context")
    if isinstance(zone, dict):
        zone = zone.get("label") or zone.get("name")
    capacity_result = _dict(capacity.result_snapshot if capacity is not None else result)
    value = _dict(_dict(capacity_result.get("capacity")).get("value"))
    fleet = value.get("selected_fleet")
    if fleet is None:
        fleet = _dict(_dict(result.get("branches")).get("capacity")).get("selected_fleet")
    economics = _dict(_dict(run.input_snapshot).get("economics"))
    inputs = None
    if economics:
        supplied = sum(_confirmed(economics.get(field), field, economics) for field in ECONOMICS_INPUTS)
        inputs = {"confirmed": supplied, "total": len(ECONOMICS_INPUTS)}
    elif run.run_kind == "CAPACITY_ANALYSIS":
        technical = [process.get("demand"), process.get("route_distance"), process.get("schedule"), source_input.get("model_id")]
        inputs = {"confirmed": sum(item is not None for item in technical), "total": len(technical)}
    branches = _branches(run, result, fleet=fleet, simulation_count=simulation_count)
    branch_total = len(branches)
    branch_calculated = sum(value in {"CALCULATED", "SAVED"} for value in branches.values())
    model_id = source_input.get("model_id")
    if run.status != "SUCCEEDED":
        kind = "UNAVAILABLE"
    elif run.run_kind == "CAPACITY_ANALYSIS" or result.get("schema_version") == "economics-partial-result-v1":
        kind = "PARTIAL"
    else:
        kind = "FULL"
    return {
        "schema_version": "report-history-summary-v1",
        "group_run_id": str(capacity.id) if capacity is not None else str(run.id),
        "linked_capacity_run_id": str(capacity.id) if capacity is not None and capacity is not run else None,
        "process_code": process.get("process_code"), "process_id": process.get("process_id"),
        "zone_label": zone if isinstance(zone, str) and zone.strip() else None,
        "model_name": ((model_names or {}).get((getattr(capacity or run, "catalog_version_code", None), str(model_id)))
                       or (model_names or {}).get(str(model_id))),
        "result_type": kind,
        "fleet": fleet,
        "branches": branches,
        "npv": _npv(result),
        "completeness": {"inputs": inputs, "branches_calculated": branch_calculated,
                         "branches_total": branch_total},
        "simulation_count": simulation_count,
        "can_create_version": run.status == "SUCCEEDED" and bool(economics)
            and economics.get("schema_version") in {"economics-explicit-inputs-v1", "economics-explicit-inputs-v2", "economics-explicit-inputs-v3", "economics-explicit-inputs-v4", "economics-explicit-inputs-v5"},
    }


__all__ = ["summarize_run"]
