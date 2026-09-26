"""F5 saved financial comparison, produced only when a new run is calculated.

The accepted v2 engine and its golden fixture remain unchanged.  This adapter
persists a separately versioned project-level presentation and sensitivity
results; exports read those saved values and never rerun the engines.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from types import SimpleNamespace
from typing import Any

from calculation.service import analyze_capacity
from calculation_contracts import parse_capacity_analysis_request, semantic_digest
from economics_orchestrator import (
    ACQUISITIONS,
    UNCERTAINTIES,
    EconomicsExecutionContextV1,
    EconomicsExplicitInputsV1,
    _primary_role,
    _role_pool,
    _role_with_salary,
    _scenario_artifacts,
    execute_economics_v2,
)
from economics_runtime_migration import EconomicsV2ExecutionV1

PRESENTATION_VERSION = "financial-comparison-v1"
SENSITIVITY_VERSION = "scenario-sensitivity-v1"


def _money(value: Decimal | str | int) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _metric(value: str | None, unit: str, basis: str, source: str,
            *, status: str = "COMPLETE", reason: str | None = None) -> dict[str, Any]:
    return {"status": status, "value": value, "unit": unit, "basis": basis,
            "source_ref": source, "reason": reason}


def _saved_metric(value: Any, basis: str, source: str) -> dict[str, Any]:
    return _metric(value.value, value.unit, basis, source, status=value.status,
                   reason="Срок не достигнут за горизонт" if value.status == "NOT_REACHED" else None)


def _project_metrics(artifact: Any) -> dict[str, Any]:
    allocation = artifact.allocation
    financial = artifact.financial
    purchase = artifact.acquisition == "PURCHASE"
    capex = Decimal(allocation.project_capex_cashflow)
    annual_effect = sum((Decimal(row.differential_cf) for row in allocation.annual_ledgers), Decimal(0))
    roi = None if capex == 0 else _money(annual_effect / capex * 100)
    operating: list[Decimal] = []
    for index, row in enumerate(allocation.annual_ledgers):
        if purchase:
            direct = Decimal(artifact.purchase.annual_ledgers[index].operating_total)
        else:
            direct = (Decimal(financial.annual_ledgers[index].customer_opex)
                      + Decimal(financial.annual_ledgers[index].raas_payment))
        operating.append(direct + Decimal(row.object_scenario_fot)
                         + Decimal(row.shared_scenario_cost))
    baseline = [-Decimal(row.combined_baseline_cf) for row in allocation.annual_ledgers]
    source = allocation.run_id
    return {
        "capex": _metric(_money(capex), "RUB", "C18: вложения заказчика в проект", source),
        "opex_year_1": _metric(_money(operating[0]), "RUB/year", "прямой OPEX + ФОТ + общие расходы, год 1", source),
        "opex_change_year_1": _metric(_money(operating[0] - baseline[0]), "RUB/year", "OPEX сценария минус затраты baseline, год 1", source),
        "fot_year_1": _metric(allocation.annual_ledgers[0].object_scenario_fot,
                              "RUB/year", "ФОТ после внедрения, год 1", source),
        "effect_year_1": _metric(allocation.annual_ledgers[0].differential_cf, "RUB/year",
                                 "разность потоков против baseline, год 1", source),
        "effect_total": _metric(_money(annual_effect), "RUB", "сумма годовых разностей без первоначальных вложений", source),
        "net_benefit": _metric(_money(annual_effect - capex), "RUB", "эффект за горизонт минус CAPEX", source),
        "roi": _metric(roi, "PERCENT", "эффект за горизонт / CAPEX проекта × 100", source,
                       status="N_A" if roi is None else "COMPLETE",
                       reason="Нулевые инвестиции: ROI на CAPEX не определён" if roi is None else None),
        "tco": _metric(_money(capex + sum(operating, Decimal(0))), "RUB",
                       "CAPEX проекта + OPEX и ФОТ за горизонт; без вычета остаточной стоимости", source),
        "npv": _saved_metric(allocation.npv_project, "C18: NPV проекта против baseline", source),
        "simple_payback": _saved_metric(allocation.simple_payback, "C18: простой срок окупаемости", source),
        "discounted_payback": _saved_metric(allocation.discounted_payback, "C18: дисконтированный срок", source),
    }


def _baseline(artifact: Any) -> dict[str, Any]:
    allocation = artifact.allocation
    rows = allocation.annual_ledgers
    annual_costs = [-Decimal(row.combined_baseline_cf) for row in rows]
    source = allocation.run_id
    return {
        "scenario_id": "scenario.baseline.base", "acquisition": "BASELINE", "uncertainty": "BASE",
        "metrics": {
            "capex": _metric(None, "RUB", "без инвестиционного проекта", source, status="N_A", reason="Baseline не является инвестицией"),
            "opex_year_1": _metric(_money(annual_costs[0]), "RUB/year", "сохранённый денежный поток без роботов, год 1", source),
            "opex_change_year_1": _metric("0.00", "RUB/year", "сравнение baseline с собой", source),
            "fot_year_1": _metric(rows[0].object_baseline_fot, "RUB/year", "сохранённый ФОТ без роботов, год 1", source),
            "effect_year_1": _metric(None, "RUB/year", "инвестиционного сравнения нет", source, status="N_A", reason="Baseline — точка сравнения"),
            "effect_total": _metric(None, "RUB", "инвестиционного сравнения нет", source, status="N_A", reason="Baseline — точка сравнения"),
            "net_benefit": _metric(None, "RUB", "инвестиционного сравнения нет", source, status="N_A", reason="Baseline — точка сравнения"),
            "roi": _metric(None, "PERCENT", "нет инвестиций", source, status="N_A", reason="Baseline не является инвестицией"),
            "tco": _metric(_money(sum(annual_costs, Decimal(0))), "RUB", "сумма затрат без роботов за горизонт", source),
            "npv": _saved_metric(allocation.npv_base, "C18: дисконтированный поток baseline", source),
            "simple_payback": _metric(None, "YEAR", "нет инвестиций", source, status="N_A", reason="Baseline не является инвестицией"),
            "discounted_payback": _metric(None, "YEAR", "нет инвестиций", source, status="N_A", reason="Baseline не является инвестицией"),
        },
        "annual_cashflows": [{"year": row.year, "baseline": row.combined_baseline_cf,
                              "scenario": row.combined_baseline_cf, "effect": None,
                              "source_ref": source} for row in rows],
        "capital_lines": [],
    }


def _scenario(artifact: Any) -> dict[str, Any]:
    source = artifact.allocation.run_id
    if artifact.acquisition == "PURCHASE":
        capital = [{"label": line.line_id, "amount": line.amount, "unit": "RUB",
                    "source_refs": line.source_refs, "basis": line.basis}
                   for line in artifact.purchase.capital_lines]
    else:
        capital = [{"label": "Инфраструктура заказчика", "amount": artifact.financial.capex_infrastructure_gross,
                    "unit": "RUB", "source_refs": [artifact.financial.run_id], "basis": "RaaS customer infrastructure"}]
    capital.append({"label": "Общие вложения объекта", "amount": artifact.allocation.shared_capex_cashflow,
                    "unit": "RUB", "source_refs": ["input.economics.shared-site-capital"], "basis": "общая инфраструктура"})
    return {
        "scenario_id": f"scenario.{artifact.acquisition.lower()}.{artifact.uncertainty.lower()}",
        "acquisition": artifact.acquisition, "uncertainty": artifact.uncertainty,
        "metrics": _project_metrics(artifact), "capital_lines": capital,
        "annual_cashflows": [{"year": row.year, "baseline": row.combined_baseline_cf,
                              "scenario": row.combined_scenario_cf, "effect": row.differential_cf,
                              "source_ref": source} for row in artifact.allocation.annual_ledgers],
    }


def _sensitivity(context: EconomicsExecutionContextV1, inputs: EconomicsExplicitInputsV1,
                 snapshot: Any, artifact: Any) -> list[dict[str, Any]]:
    """Rerun canonical engines for each scenario; keep failures as explicit BLOCKED."""
    request = context.capacity_request
    role_id = _primary_role(request, inputs)
    role = next(item for item in _role_pool(request, inputs).roles if item.role_id == role_id)
    if artifact.acquisition == "BASELINE":
        parameters = ("OPERATION_VOLUME", "ROLE_SALARY", "MANUAL_PRODUCTIVITY")
    elif artifact.acquisition == "RAAS":
        parameters = ("RAAS_TARIFF", "OPERATION_VOLUME", "ROLE_SALARY")
    else:
        parameters = ("EQUIPMENT_PRICE", "OPERATION_VOLUME", "ROLE_SALARY")
    base_price = artifact.procurement.money.raw_money.raw_amount if artifact.acquisition == "PURCHASE" else None
    bases = {
        "EQUIPMENT_PRICE": (base_price, "RUB/robot", "catalog.procurement.price"),
        "RAAS_TARIFF": (inputs.raas_monthly_per_robot_gross, "RUB/robot/month", "input.economics.raas-monthly"),
        "OPERATION_VOLUME": (request.process.demand.normalized_value, "unit/day", request.process.demand.provenance_ref),
        "ROLE_SALARY": (role.monthly_gross_salary.normalized_value, "RUB/person/month", role.monthly_gross_salary.provenance_ref),
        "MANUAL_PRODUCTIVITY": (inputs.manual_units_per_shift, "unit/person/shift", "input.economics.manual-units-per-shift"),
    }
    if artifact.acquisition == "BASELINE":
        baseline_value = Decimal(artifact.allocation.npv_base.value)
    else:
        baseline_value = Decimal(artifact.allocation.npv_project.value)
    variants = []
    for parameter in parameters:
        base_value, unit, provenance = bases[parameter]
        for direction, multiplier in (("LOWER", Decimal("0.9")), ("UPPER", Decimal("1.1"))):
            item: dict[str, Any] = {"parameter": parameter, "direction": direction,
                "base_value": base_value, "variant_value": None, "unit": unit,
                "source_ref": provenance, "status": "BLOCKED", "delta_npv": None,
                "baseline_npv": _money(baseline_value), "variant_npv": None, "reason": None}
            if base_value is None or Decimal(str(base_value)) <= 0:
                item["reason"] = "Нет положительного сохранённого базового значения"
                variants.append(item)
                continue
            value = Decimal(str(base_value)) * multiplier
            item["variant_value"] = format(value, "f")
            try:
                variant_context = context
                variant_inputs = inputs
                price_override = None
                role_pool = None
                if parameter == "EQUIPMENT_PRICE":
                    price_override = _money(value)
                elif parameter == "RAAS_TARIFF":
                    variant_inputs = inputs.model_copy(update={"raas_monthly_per_robot_gross": _money(value)})
                elif parameter == "MANUAL_PRODUCTIVITY":
                    variant_inputs = inputs.model_copy(update={"manual_units_per_shift": format(value, "f")})
                elif parameter == "ROLE_SALARY":
                    pool = _role_pool(request, inputs)
                    role_pool = pool.model_copy(update={"roles": [
                        _role_with_salary(entry, _money(value)) if entry.role_id == role_id else entry
                        for entry in pool.roles]})
                else:
                    raw = request.model_dump(mode="json")
                    raw["process"]["demand"]["raw_value"] = format(value, "f")
                    raw["process"]["demand"]["normalized_value"] = format(value, "f")
                    next_request = parse_capacity_analysis_request(raw)
                    next_response = analyze_capacity(next_request, snapshot,
                        f"{context.run_id}.f5.{artifact.acquisition.lower()}.{artifact.uncertainty.lower()}.{direction.lower()}").response
                    if next_response.capacity.value is None:
                        raise ValueError("Вариант объёма не проходит технические ограничения")
                    variant_context = EconomicsExecutionContextV1(
                        run_id=context.run_id, project_id=context.project_id, tenant_id=context.tenant_id,
                        capacity_request=next_request, capacity_response=next_response,
                        constraint_report=context.constraint_report, executability=context.executability)
                rerun = _scenario_artifacts(variant_context, variant_inputs, snapshot,
                    "PURCHASE" if artifact.acquisition == "BASELINE" else artifact.acquisition,
                    artifact.uncertainty, primary_price_override=price_override, role_pool=role_pool)
                compared = rerun.allocation.npv_base if artifact.acquisition == "BASELINE" else rerun.allocation.npv_project
                if compared.value is None:
                    raise ValueError("NPV варианта не рассчитан")
                value_npv = Decimal(compared.value)
                item.update(status="COMPLETE", variant_npv=_money(value_npv),
                            delta_npv=_money(value_npv - baseline_value), reason=None)
            except (ValueError, ArithmeticError) as exc:
                item["reason"] = str(exc)
            variants.append(item)
    return variants


def execute_economics_v3(raw_inputs: dict[str, Any] | EconomicsExplicitInputsV1,
                         snapshot: Any, context: EconomicsExecutionContextV1) -> EconomicsV2ExecutionV1:
    inputs = raw_inputs if isinstance(raw_inputs, EconomicsExplicitInputsV1) else EconomicsExplicitInputsV1.model_validate(raw_inputs)
    accepted = execute_economics_v2(inputs, snapshot, context)
    artifacts = [_scenario_artifacts(context, inputs, snapshot, acquisition, uncertainty)
                 for acquisition in ACQUISITIONS for uncertainty in UNCERTAINTIES]
    base = next(item for item in artifacts if item.acquisition == "PURCHASE" and item.uncertainty == "BASE")
    baseline = _baseline(base)
    baseline_sensitivity = _sensitivity(context, inputs, snapshot,
        SimpleNamespace(acquisition="BASELINE", uncertainty="BASE", allocation=base.allocation))
    scenarios = [_scenario(item) for item in artifacts]
    sensitivity = {baseline["scenario_id"]: baseline_sensitivity}
    sensitivity.update({row["scenario_id"]: _sensitivity(context, inputs, snapshot, item)
                        for row, item in zip(scenarios, artifacts)})
    comparison = {
        "schema_version": PRESENTATION_VERSION,
        "horizon_years": inputs.horizon_years,
        "currency": "RUB",
        "baseline": baseline,
        "scenarios": scenarios,
        "sensitivity": {"schema_version": SENSITIVITY_VERSION, "by_scenario": sensitivity},
        "inputs": {
            "demand": {"value": context.capacity_request.process.demand.normalized_value,
                       "unit": str(context.capacity_request.process.demand.unit),
                       "source_ref": context.capacity_request.process.demand.provenance_ref},
            "manual_productivity": {"value": inputs.manual_units_per_shift, "unit": "unit/person/shift",
                                    "source_ref": "input.economics.manual-units-per-shift"},
            "price": {"value": base.procurement.money.raw_money.raw_amount,
                      "currency": base.procurement.money.raw_money.currency,
                      "tax_basis": base.procurement.money.raw_money.tax_basis,
                      "vat_rate": base.procurement.money.raw_money.vat_rate,
                      "source_ref": base.procurement.money.raw_money.source.source_id,
                      "source_note": inputs.purchase_price_source},
            "raas_tariff": {"value": inputs.raas_monthly_per_robot_gross, "unit": "RUB/robot/month",
                            "source_ref": "input.economics.raas-monthly"},
        },
        "limitations": ["Предварительная оценка; паспорт, цена и объект требуют обследования.",
                        "ROI имеет базу CAPEX проекта; ранее рассчитанный ROI RaaS на TCO не является этим показателем.",
                        "Чувствительность привязана к каждому сценарию и его профилю неопределённости."],
    }
    result = dict(accepted.result_snapshot)
    result.update(schema_version="commercial-scenarios-bundle-v3", comparison=comparison)
    result["versions"] = {**result["versions"], "financial_presentation": PRESENTATION_VERSION,
                           "scenario_sensitivity": SENSITIVITY_VERSION,
                           "orchestrator": "production-economics-orchestrator-v3"}
    return EconomicsV2ExecutionV1(
        result_snapshot=result, scenario_spec_snapshot=accepted.scenario_spec_snapshot,
        revision_id=accepted.revision_id, rules_version=accepted.rules_version,
        object_profile_version=accepted.object_profile_version,
        application_version="production-economics-orchestrator-v3",
        diagnostics={**accepted.diagnostics, "financial_presentation_digest": semantic_digest(comparison)},
    )


__all__ = ["PRESENTATION_VERSION", "SENSITIVITY_VERSION", "execute_economics_v3"]
