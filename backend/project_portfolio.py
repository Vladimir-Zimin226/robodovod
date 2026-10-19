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
    EconomicsExplicitInputsV1, RoleWorkProfileV1, _role_labour_inputs,
    _role_pool, _scenario_artifacts,
)
from economics_partial import _parse


def _explicit(raw: dict[str, Any], saved_result: dict[str, Any]) -> Any:
    if raw.get("schema_version") not in {"economics-explicit-inputs-v6", "economics-explicit-inputs-v7"}:
        raise ValueError("project portfolio requires project economics input v6")
    partial_purchase = saved_result.get("schema_version") == "economics-partial-result-v1"
    if partial_purchase and (saved_result.get("branches", {}).get("purchase", {}).get("status") != "CALCULATED"
                             or not any(item.get("acquisition") == "PURCHASE" and item.get("uncertainty") == "BASE"
                                        for item in saved_result.get("scenarios", []))):
        raise ValueError("project operation needs a calculated purchase branch")
    values, issues = _parse(raw)
    if "role_work_profiles" in raw:
        values["role_work_profiles"] = [RoleWorkProfileV1.model_validate(item)
                                        for item in raw["role_work_profiles"]]
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
    excluded_operations: list[dict[str, Any]] | None = None,
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
    primary_processes_by_role: dict[str, set[str]] = {}
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
        for labour_input in _role_labour_inputs(request, inputs, projection):
            if labour_input.role_id is not None:
                primary_processes_by_role.setdefault(labour_input.role_id, set()).add(process.process_id)
            processes.append(labour_input)
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
    calculated_roles = {item.role_id: item for item in labour.roles}
    blocked_processes_by_role: dict[str, set[str]] = {}
    for operation in excluded_operations or []:
        for role_id in operation.get("role_refs") or []:
            blocked_processes_by_role.setdefault(role_id, set()).add(operation["process_id"])
    role_effects = []
    for role in sorted(roles, key=lambda item: item.role_id):
        linked = sorted(set(role.process_ids) & seen)
        blocked = blocked_processes_by_role.pop(role.role_id, set())
        if not linked and not blocked:
            continue  # Site-wide control and technical staff are reported separately.
        included = sorted(primary_processes_by_role.get(role.role_id, set()) & set(linked))
        excluded = sorted((set(linked) - set(included)) | blocked)
        result = calculated_roles.get(role.role_id)
        status = "NOT_CALCULATED" if not included or result is None else "PARTIAL" if excluded else "CALCULATED"
        role_effects.append({
            "role_id": role.role_id, "role_code": role.role_code,
            "headcount": role.headcount.normalized_value if isinstance(role.headcount, KnownQuantity) else None,
            "status": status, "included_process_ids": included,
            "excluded_process_ids": excluded,
            "released": result.released if result is not None and included else None,
            "annual_direct_rub_per_person": result.money.annual_direct if result is not None and result.money else None,
            "reason": None if status == "CALCULATED" else "Для этой роли нет подтверждённой отдельной трудовой модели во всех связанных операциях.",
        })
    for role_id, process_ids in sorted(blocked_processes_by_role.items()):
        role_effects.append({
            "role_id": role_id, "role_code": None, "headcount": None,
            "status": "NOT_CALCULATED", "included_process_ids": [],
            "excluded_process_ids": sorted(process_ids), "released": None,
            "annual_direct_rub_per_person": None,
            "reason": "Для этой роли нет рассчитанного парка и трудового эффекта.",
        })
    role_effects.sort(key=lambda item: item["role_id"])
    unassessed_roles = [item for item in role_effects if item["status"] != "CALCULATED"]
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
    return {"schema_version": "project-portfolio-economics-v2", "status": "PARTIAL" if unassessed_roles else "CALCULATED",
            "source_result_digest": semantic_digest(allocation),
            "project_capex_rub": allocation.project_capex_cashflow,
            "project_npv_rub": allocation.npv_project.value,
            "project_net_roi_percent": net_roi,
            "first_year_effect_rub": allocation.annual_ledgers[0].differential_cf,
            "simple_payback_years": allocation.simple_payback.value,
            "discounted_payback_years": allocation.discounted_payback.value,
            "total_released_people": allocation.total_released_people,
            "role_effects": role_effects,
            "unassessed_roles": unassessed_roles,
            "control_required_once": allocation.control_required_once,
            "technicians_required_once": allocation.technicians_required_once,
            "rows": cost_rows,
            "first_year_energy_rub": str(sum(Decimal(row["first_year_energy_rub"] or "0") for row in cost_rows)),
            "peak_charging_power_kw": peak_charging,
            "peak_charging_reason": None if charge_inputs_complete else "Нет мощности зарядного устройства или доли одновременных зарядок для всех моделей.",
            "annual_ledgers": [item.model_dump(mode="json") for item in allocation.annual_ledgers],
            "versions": allocation.versions.model_dump(mode="json")}
