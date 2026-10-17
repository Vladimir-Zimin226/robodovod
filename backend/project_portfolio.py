"""Project-level purchase economics from saved, individually priced C11 configurations.

The existing C18 engine owns the combined cash flow. This adapter only binds
per-model direct projections to one object-wide C14 labour snapshot.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from calculation.economics.allocation import (
    DiscountRateV1, MultiprocessAllocationRequestV1, SharedAnnualCostV1,
    SharedSiteCapitalV1,
)
from calculation.labour import (
    CapacityLabourProjectionV1, LabourAnalysisRequestV1,
    ProcessLabourInputV1, SalarySourceBindingV1,
)
from calculation.service import analyze_multiprocess_allocation, analyze_role_labour
from calculation_contracts import KnownQuantity, RoleEntry, RolePool, semantic_digest
from economics_orchestrator import (
    EconomicsExplicitInputsV1, _manual_productivity, _primary_role,
    _role_pool, _scenario_artifacts,
)
from economics_partial import _parse


def _explicit(raw: dict[str, Any], saved_result: dict[str, Any]) -> Any:
    if raw.get("schema_version") != "economics-explicit-inputs-v6":
        raise ValueError("project portfolio requires project economics input v6")
    partial_purchase = saved_result.get("schema_version") == "economics-partial-result-v1"
    if partial_purchase and (saved_result.get("branches", {}).get("purchase", {}).get("status") != "CALCULATED"
                             or not any(item.get("acquisition") == "PURCHASE" and item.get("uncertainty") == "BASE"
                                        for item in saved_result.get("scenarios", []))):
        raise ValueError("project operation needs a calculated purchase branch")
    values, issues = _parse(raw)
    if any(item['field'] in {'charger_power_kw', 'charging_simultaneity_fraction'} for item in issues) or (issues and not partial_purchase):
        raise ValueError("project economics input has invalid or unconfirmed fields")
    basis = saved_result.get("monetary_input_basis") or {}
    if raw.get("implementation_mode") == "PERCENT":
        values["implementation_cost_total_gross"] = (basis.get("implementation") or {}).get("amount_gross_rub")
    if raw.get("raas_mode") == "PERCENT":
        values["raas_monthly_per_robot_gross"] = (basis.get("raas") or {}).get("per_robot_month_gross_rub")
    values["control_monthly_gross"] = values["control_monthly_gross"] or "0"
    values["technician_monthly_gross"] = values["technician_monthly_gross"] or "0"
    if partial_purchase:
        # The saved purchase branch has already passed its own readiness gate.
        # RaaS and visual inputs may still be unknown and are never consumed by
        # the purchase-only adapter below.
        return SimpleNamespace(**values)
    values["schema_version"] = "economics-explicit-inputs-v1"
    selected = {key: value for key, value in values.items() if key in EconomicsExplicitInputsV1.model_fields}
    return EconomicsExplicitInputsV1.model_validate(selected)


def calculate_project_portfolio(
    rows: list[tuple[Any, dict[str, Any], dict[str, Any]]], snapshot: Any,
    *, project_id: str, tenant_id: str, run_id: str,
) -> dict[str, Any]:
    """Combine one complete PURCHASE run per process without averaging models.

    `rows` contains the verified C11 execution context, saved economics input,
    and saved economics result. The caller checks ownership, hashes and bindings.
    """
    if not rows:
        raise ValueError("project portfolio needs at least one process")
    prepared = [(context, _explicit(raw, result), raw) for context, raw, result in rows]
    first_context, first_inputs, _ = prepared[0]
    revision = first_context.capacity_request.input_revision
    object_kind = first_context.capacity_request.process.object_kind
    global_fields = (
        "horizon_years", "discount_rate", "salary_basis", "control_headcount",
        "control_monthly_gross", "technician_headcount", "technician_monthly_gross",
        "shared_site_capital_gross", "shared_annual_cost_gross", "staffing_purchase",
        "staffing_policy", "work_share",
    )
    def signature(inputs):
        return tuple(getattr(inputs, field).model_dump(mode="json") if hasattr(getattr(inputs, field), "model_dump")
                     else getattr(inputs, field) for field in global_fields)
    expected = signature(first_inputs)
    merged_roles: dict[str, RoleEntry] = {}
    processes: list[ProcessLabourInputV1] = []
    configurations = []
    cost_rows = []
    seen = set()
    for context, inputs, raw in prepared:
        request = context.capacity_request
        response = context.capacity_response
        process = request.process
        if (request.project_id != project_id or request.input_revision != revision
                or process.object_kind != object_kind or process.process_id in seen
                or signature(inputs) != expected or context.tenant_id != tenant_id):
            raise ValueError("project operations must share revision, site assumptions and distinct processes")
        seen.add(process.process_id)
        if response.capacity.value is None:
            raise ValueError("a project operation has no calculated fleet")
        local_pool = _role_pool(request, inputs)
        for role in local_pool.roles:
            previous = merged_roles.get(role.role_id)
            if previous is None:
                merged_roles[role.role_id] = role
                continue
            before = previous.model_dump(mode="json")
            current = role.model_dump(mode="json")
            linked = sorted(set(before.pop("process_ids") + current.pop("process_ids")))
            if before != current:
                raise ValueError(f"role {role.role_id} has conflicting headcount or salary between operations")
            merged_roles[role.role_id] = previous.model_copy(update={"process_ids": linked})
        projection = CapacityLabourProjectionV1(
            process_id=process.process_id, input_revision=revision,
            capacity_run_id=response.run_id, capacity_status=response.capacity.status,
            selected_fleet=response.capacity.value.selected_fleet,
            coverage=response.capacity.value.coverage.value,
            capacity_result_digest=semantic_digest(response.capacity),
        )
        processes.append(ProcessLabourInputV1(
            process=process, capacity=projection, role_id=_primary_role(request, inputs),
            manual_units_per_shift=_manual_productivity(request, inputs),
        ))
        artifact = _scenario_artifacts(context, inputs, snapshot, "PURCHASE", "BASE")
        config = artifact.allocation_request.configurations[0]
        configurations.append(config)
        energy = next((item.amount for item in artifact.purchase.annual_ledgers[0].operating_lines
                       if item.category == "ENERGY"), None)
        cost_rows.append({"process_id": process.process_id, "model_id": request.model_id,
                          "position_id": request.position_id,
                          "fleet": response.capacity.value.selected_fleet,
                          "direct_capex_rub": config.direct_capex_cashflow,
                          "first_year_energy_rub": energy,
                          "power_w_per_robot": inputs.average_power_w,
                          "energy_power_basis": raw.get("energy_power_basis", "AVERAGE"),
                          "charger_power_kw": raw.get("charger_power_kw"),
                          "charging_simultaneity_fraction": raw.get("charging_simultaneity_fraction")})
    roles = list(merged_roles.values())
    pool = RolePool(pool_id=f"pool.{run_id}", object_kind=object_kind, roles=roles)
    labour_request = LabourAnalysisRequestV1(
        run_id=f"{run_id}.labour", project_id=project_id, tenant_id=tenant_id,
        input_revision=revision, object_id=f"object.{project_id}", object_kind=object_kind,
        uncertainty="BASE", role_pool=pool, processes=processes,
        salary_sources=[SalarySourceBindingV1(
            role_id=role.role_id, provenance_ref=role.monthly_gross_salary.provenance_ref,
            source="USER") for role in roles if isinstance(role.monthly_gross_salary, KnownQuantity)],
        staffing_decision=first_inputs.staffing_purchase,
        staffing_policy=first_inputs.staffing_policy, work_share=first_inputs.work_share,
        salary_basis=first_inputs.salary_basis,
    )
    labour = analyze_role_labour(labour_request)
    if labour.finance_status != "COMPLETE":
        raise ValueError("project-wide labour is incomplete: " + ", ".join(labour.issues))
    shared_capex = first_inputs.shared_site_capital_gross
    shared_annual = first_inputs.shared_annual_cost_gross
    allocation = analyze_multiprocess_allocation(MultiprocessAllocationRequestV1(
        run_id=run_id, project_id=project_id, tenant_id=tenant_id,
        input_revision=revision, object_id=f"object.{project_id}", cohort_id=f"cohort.{run_id}",
        uncertainty="BASE", configurations=configurations,
        labour_result=labour, labour_result_digest=semantic_digest(labour),
        shared_site_capital=SharedSiteCapitalV1(
            capex_gross=shared_capex, capex_amortizable=shared_capex, capex_cashflow=shared_capex,
            source="USER", provenance_ref="input.project.shared-site-capital"),
        shared_annual_costs=[SharedAnnualCostV1(
            year=year, baseline_cost="0", scenario_cost=shared_annual,
            source="USER", provenance_ref="input.project.shared-annual-cost")
            for year in range(1, first_inputs.horizon_years + 1)],
        discount_rate=DiscountRateV1(value=first_inputs.discount_rate, source="USER",
                                     provenance_ref="input.project.discount-rate"),
    ))
    capex = Decimal(allocation.project_capex_cashflow)
    net_effect = sum(Decimal(item.differential_cf) for item in allocation.annual_ledgers) - capex
    net_roi = None if capex == 0 else format((net_effect / capex * 100).quantize(Decimal('0.01')), 'f')
    charge_inputs_complete = all(row['fleet'] == 0 or (row['charger_power_kw'] is not None
                                  and row['charging_simultaneity_fraction'] is not None) for row in cost_rows)
    peak_charging = (format(sum(Decimal(row['charger_power_kw']) * Decimal(row['charging_simultaneity_fraction'])
                                 * row['fleet'] for row in cost_rows if row['fleet'] > 0), 'f')
                     if charge_inputs_complete else None)
    return {"schema_version": "project-portfolio-economics-v1", "status": "CALCULATED",
            "source_result_digest": semantic_digest(allocation),
            "project_capex_rub": allocation.project_capex_cashflow,
            "project_npv_rub": allocation.npv_project.value,
            "project_net_roi_percent": net_roi,
            "first_year_effect_rub": allocation.annual_ledgers[0].differential_cf,
            "simple_payback_years": allocation.simple_payback.value,
            "discounted_payback_years": allocation.discounted_payback.value,
            "total_released_people": allocation.total_released_people,
            "control_required_once": allocation.control_required_once,
            "technicians_required_once": allocation.technicians_required_once,
            "rows": cost_rows,
            "first_year_energy_rub": str(sum(Decimal(row["first_year_energy_rub"] or "0") for row in cost_rows)),
            "peak_charging_power_kw": peak_charging,
            "peak_charging_reason": None if charge_inputs_complete else "Нет мощности зарядного устройства или доли одновременных зарядок для всех моделей.",
            "annual_ledgers": [item.model_dump(mode="json") for item in allocation.annual_ledgers],
            "versions": allocation.versions.model_dump(mode="json")}
