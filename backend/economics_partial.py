"""Versioned partial C13-C21 execution over a saved, immutable C11 run.

Unknown fields stay unknown. The old explicit-inputs-v1 route is left intact for
historical replay; this module only handles economics-explicit-inputs-v2.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from calculation_contracts import KnownQuantity
from economics_orchestrator import (
    ACQUISITIONS,
    UNCERTAINTIES,
    EconomicsExecutionContextV1,
    EconomicsExplicitInputsV1,
    _allocation_projection,
    _financial_projection,
    _labour,
    _position,
    _procurement_projection,
    _scenario_artifacts,
    execute_economics_v2,
)
from economics_runtime_migration import EconomicsV2ExecutionV1

INPUT_VERSION = "economics-explicit-inputs-v2"
RESULT_VERSION = "economics-partial-result-v1"
PARTIAL_RULES_VERSION = "calculation-rules-c13-c21-partial-v1"

DECIMALS = {
    "discount_rate": (Decimal("0"), Decimal("1")),
    "manual_units_per_shift": (Decimal("0"), None),
    "control_monthly_gross": (Decimal("0"), None),
    "technician_monthly_gross": (Decimal("0"), None),
    "implementation_cost_total_gross": (Decimal("0"), None),
    "annual_service_per_robot_gross": (Decimal("0"), None),
    "average_power_w": (Decimal("0"), None),
    "shared_site_capital_gross": (Decimal("0"), None),
    "shared_annual_cost_gross": (Decimal("0"), None),
    "raas_monthly_per_robot_gross": (Decimal("0"), None),
}
POSITIVE = {"manual_units_per_shift", "average_power_w"}
INTEGERS = {
    "horizon_years": (5, 15),
    "control_headcount": (0, None),
    "technician_headcount": (0, None),
    "warranty_years": (0, 15),
    "raas_contract_months": (1, 180),
    "start_seconds_from_midnight": (0, 86399),
}
CONFIRMATIONS = (
    "role_salaries_confirmed_as_monthly_gross",
    "organizer_price_currency_rub_confirmed",
    "initial_battery_in_robot_price_confirmed",
    "battery_replacements_in_service_confirmed",
    "raas_vendor_scope_confirmed",
)
LABOUR_FIELDS = (
    "role_salaries_confirmed_as_monthly_gross", "control_headcount",
    "control_monthly_gross", "technician_headcount", "technician_monthly_gross",
)
PURCHASE_FIELDS = (
    "evaluation_date", "horizon_years", "discount_rate",
    "organizer_price_currency_rub_confirmed", "implementation_cost_total_gross",
    "annual_service_per_robot_gross", "warranty_years", "average_power_w",
    "initial_battery_in_robot_price_confirmed",
    "battery_replacements_in_service_confirmed", "shared_site_capital_gross",
    "shared_annual_cost_gross",
)
RAAS_FIELDS = (
    "raas_monthly_per_robot_gross", "raas_contract_months",
    "raas_infrastructure_owner", "raas_vendor_scope_confirmed",
)
VISUAL_FIELDS = ("start_seconds_from_midnight", "timezone")


def _issue(field: str, code: str, message: str, next_step: str) -> dict[str, str]:
    return {"field": field, "code": code, "message": message, "next_step": next_step}


def _parse(raw: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    values: dict[str, Any] = {"schema_version": INPUT_VERSION, "input_ranges": {}}
    issues: list[dict[str, str]] = []
    for field, (minimum, maximum) in DECIMALS.items():
        value = raw.get(field)
        if value is None or value == "":
            values[field] = None
            continue
        if isinstance(value, str):
            bounds = re.fullmatch(r"((?:0|[1-9][0-9]*)(?:\.[0-9]+)?)\.\.((?:0|[1-9][0-9]*)(?:\.[0-9]+)?)", value)
            if bounds:
                lower, upper = map(Decimal, bounds.groups())
                if lower <= upper and lower >= minimum and (field not in POSITIVE or lower > 0) and (maximum is None or upper <= maximum):
                    values[field] = None
                    values["input_ranges"][field] = {"min": bounds.group(1), "max": bounds.group(2)}
                    issues.append(_issue(field, "RANGE_ONLY", "Диапазон сохранён без подстановки среднего значения.", "Для NPV укажите отдельное точечное сценарное значение или оставьте ветку без расчёта."))
                    continue
        try:
            if not isinstance(value, str) or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None:
                raise ValueError()
            number = Decimal(value)
            if not number.is_finite() or number < minimum or (field in POSITIVE and number == 0) or (maximum is not None and number > maximum):
                raise ValueError()
            values[field] = value
        except (InvalidOperation, ValueError):
            values[field] = None
            issues.append(_issue(field, "INVALID_VALUE", "Число или единица измерения неверны.", "Введите число в указанной единице; ноль допустим только для известного нулевого расхода."))
    for field, (minimum, maximum) in INTEGERS.items():
        value = raw.get(field)
        if value is None or value == "":
            values[field] = None
            continue
        if isinstance(value, bool) or not str(value).isdigit():
            valid = False
        else:
            number = int(value)
            valid = number >= minimum and (maximum is None or number <= maximum)
        values[field] = int(value) if valid else None
        if not valid:
            issues.append(_issue(field, "INVALID_VALUE", "Ожидается целое число в допустимом диапазоне.", "Исправьте значение или оставьте поле пустым, если оно неизвестно."))
    for field in CONFIRMATIONS:
        values[field] = raw.get(field) is True
    for field in ("input_revision", "primary_role_id", "raas_infrastructure_owner", "timezone"):
        value = raw.get(field)
        values[field] = value if isinstance(value, str) and value.strip() else None
    value = raw.get("evaluation_date")
    try:
        values["evaluation_date"] = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        values["evaluation_date"] = None
        issues.append(_issue("evaluation_date", "INVALID_VALUE", "Неверная дата оценки.", "Укажите дату в формате ГГГГ-ММ-ДД."))
    if values["raas_infrastructure_owner"] not in (None, "CUSTOMER", "VENDOR"):
        values["raas_infrastructure_owner"] = None
        issues.append(_issue("raas_infrastructure_owner", "INVALID_VALUE", "Неизвестная сторона оплаты инфраструктуры.", "Выберите заказчика или поставщика."))
    if values["timezone"] is not None and len(values["timezone"]) > 64:
        values["timezone"] = None
        issues.append(_issue("timezone", "INVALID_VALUE", "Часовой пояс слишком длинный.", "Укажите IANA часовой пояс."))
    sources = raw.get("field_sources", {})
    values["field_sources"] = {key: source for key, source in sources.items()
                               if key in DECIMALS | INTEGERS and source in ("USER", "ASSUMPTION")
                               and (values.get(key) is not None or key in values["input_ranges"])} if isinstance(sources, dict) else {}
    return values, issues


def _missing(values: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if values.get(field) is None or values.get(field) is False]


def _status(missing: list[str], *, reason: str = "MISSING_INPUT") -> dict[str, Any]:
    return {"status": "NOT_CALCULATED" if missing else "AVAILABLE", "reason_code": reason if missing else None, "required_fields": sorted(set(missing))}


def execute_partial_economics_v2(
    raw: dict[str, Any], snapshot: Any, context: EconomicsExecutionContextV1
) -> EconomicsV2ExecutionV1:
    if raw.get("schema_version") != INPUT_VERSION:
        raise ValueError("unsupported partial economics input version")
    values, issues = _parse(raw)
    request = context.capacity_request
    if values["input_revision"] != request.input_revision:
        issues.append(_issue("input_revision", "SNAPSHOT_MISMATCH", "Версия входа не совпадает с сохранённым C11.", "Откройте исходный C11 run и повторите ввод."))
    role_refs = request.process.role_refs
    if values["primary_role_id"] is not None and values["primary_role_id"] not in role_refs:
        issues.append(_issue("primary_role_id", "INVALID_VALUE", "Роль отсутствует в сохранённом процессе.", "Выберите роль из C03."))
    if len(role_refs) > 1 and values["primary_role_id"] not in role_refs:
        issues.append(_issue("primary_role_id", "MISSING_INPUT", "Для процесса с несколькими ролями нужна основная роль.", "Выберите роль из C03."))
    elif len(role_refs) == 1 and values["primary_role_id"] is None:
        values["primary_role_id"] = role_refs[0]
    if request.process.scope != "CLEANING_AREA" and values["manual_units_per_shift"] is None:
        issues.append(_issue("manual_units_per_shift", "MISSING_INPUT", "Неизвестна ручная производительность.", "Укажите единиц за смену или оставьте экономику без расчёта."))
    if values["raas_contract_months"] is not None and values["horizon_years"] is not None and values["raas_contract_months"] < values["horizon_years"] * 12:
        issues.append(_issue("raas_contract_months", "CONTRACT_TOO_SHORT", "Срок RaaS короче горизонта расчёта.", "Укажите договор на весь горизонт или сократите горизонт."))
    missing_salaries = []
    if request.role_pool is not None:
        missing_salaries = [f"role_pool.{role.role_id}.monthly_gross_salary" for role in request.role_pool.roles if role.role_code not in {"control_operator", "tech_support"} and not isinstance(role.monthly_gross_salary, KnownQuantity)]
    else:
        missing_salaries = ["role_pool"]
    capacity_available = context.capacity_response.capacity.status in ("COMPLETE", "WITH_ASSUMPTIONS") and context.capacity_response.capacity.value is not None
    context_missing = [] if capacity_available else ["capacity_technical_result"]
    if values["input_revision"] != request.input_revision:
        context_missing.append("input_revision")
    labour_missing = _missing(values, LABOUR_FIELDS) + missing_salaries + context_missing
    if request.process.scope != "CLEANING_AREA" and values["manual_units_per_shift"] is None:
        labour_missing.append("manual_units_per_shift")
    if len(role_refs) > 1 and values["primary_role_id"] not in role_refs:
        labour_missing.append("primary_role_id")
    if values["primary_role_id"] is not None and values["primary_role_id"] not in role_refs:
        labour_missing.append("primary_role_id")
    purchase_missing = labour_missing + _missing(values, PURCHASE_FIELDS)
    raas_missing = purchase_missing + _missing(values, RAAS_FIELDS)
    if any(item["field"] == "raas_contract_months" and item["code"] == "CONTRACT_TOO_SHORT" for item in issues):
        raas_missing.append("raas_contract_months")
    if any(item["field"] == "evaluation_date" and item["code"] == "INVALID_VALUE" for item in issues):
        purchase_missing.append("evaluation_date")
        raas_missing.append("evaluation_date")
    position = None
    try:
        position = _position(snapshot, request)
    except ValueError as exc:
        purchase_missing.append("catalog_position")
        raas_missing.append("catalog_position")
        issues.append(_issue("catalog_position", "CATALOG_UNAVAILABLE", str(exc), "Выберите доступную позицию активного каталога."))
    if position is not None and position.procurement_option is None:
        purchase_missing.append("organizer_price")
        raas_missing.append("organizer_price")
        issues.append(_issue("organizer_price", "MISSING_INPUT", "В каталоге нет исходной цены для сравнения.", "Выберите позицию с ценой; не подставляйте ноль."))
    branches = {
        "capacity": {"status": "AVAILABLE" if capacity_available else "NOT_CALCULATED", "reason_code": None if capacity_available else "CAPACITY_BLOCKED", "required_fields": context_missing, "source_run_id": context.capacity_response.run_id, "capacity_status": context.capacity_response.capacity.status,
                     "selected_fleet": context.capacity_response.capacity.value.selected_fleet if capacity_available else None},
        "labour": _status(labour_missing),
        "purchase": _status(purchase_missing),
        "raas": _status(raas_missing),
    }
    # Private engines only read fields of the ready branch. No placeholder
    # prices, salaries or confirmations are constructed for missing inputs.
    class BranchInputs:
        pass
    branch_inputs = BranchInputs()
    for key, value in values.items():
        setattr(branch_inputs, key, value)
    labour_projection = None
    if not labour_missing:
        try:
            labour = _labour(context, branch_inputs, "BASE")
            labour_projection = {
                "status": labour.finance_status,
                "source_schema_version": labour.schema_version,
                "total_released": labour.total_released,
                "total_additional_control": labour.total_additional_control,
                "roles": [{"role_id": role.role_id, "released": role.released,
                           "annual_direct": role.money.annual_direct if role.money else None}
                          for role in labour.roles],
            }
            branches["labour"] = {"status": "CALCULATED", "reason_code": None, "required_fields": []}
        except ValueError as exc:
            branches["labour"] = _status(["labour"], reason="DOMAIN_INCOMPLETE")
            purchase_missing.append("labour")
            raas_missing.append("labour")
            issues.append(_issue("labour", "DOMAIN_INCOMPLETE", str(exc), "Проверьте численность, зарплаты и производительность."))
    scenarios = []
    if not purchase_missing and position is not None:
        for acquisition in ACQUISITIONS:
            if acquisition == "RAAS" and raas_missing:
                continue
            try:
                for uncertainty in UNCERTAINTIES:
                    artifact = _scenario_artifacts(context, branch_inputs, snapshot, acquisition, uncertainty)
                    scenarios.append({
                        "scenario_id": f"scenario.{acquisition.lower()}.{uncertainty.lower()}",
                        "acquisition": acquisition, "uncertainty": uncertainty,
                        "procurement": _procurement_projection(artifact.procurement),
                        "financial": _financial_projection(artifact.financial),
                        "allocation": _allocation_projection(artifact.allocation),
                        "recommendation": {"status": "NOT_CALCULATED", "reason_code": "C05_AND_PROCUREMENT_UNVERIFIED"},
                    })
            except ValueError as exc:
                scenarios = [item for item in scenarios if item["acquisition"] != acquisition]
                branches[acquisition.lower()] = _status([acquisition.lower()], reason="DOMAIN_INCOMPLETE")
                issues.append(_issue(acquisition.lower(), "DOMAIN_INCOMPLETE", str(exc), "Проверьте условия расчёта и источники данных ветки."))
            else:
                branches[acquisition.lower()] = {"status": "CALCULATED", "reason_code": None, "required_fields": []}
                branches["labour"] = {"status": "CALCULATED", "reason_code": None, "required_fields": []}
    # A complete input uses the established full engine and its six-scenario
    # bundle. This preserves all existing calculations and golden snapshots.
    complete = not issues and not raas_missing and not _missing(values, VISUAL_FIELDS)
    if complete:
        full = {key: value for key, value in values.items() if key in EconomicsExplicitInputsV1.model_fields}
        full["schema_version"] = "economics-explicit-inputs-v1"
        return execute_economics_v2(full, snapshot, context)
    for field in sorted(set(purchase_missing + raas_missing + _missing(values, VISUAL_FIELDS))):
        if field not in {item["field"] for item in issues}:
            issues.append(_issue(field, "MISSING_INPUT", "Показатель пока неизвестен.", "Укажите подтверждённое значение или явное пользовательское допущение; ноль вводите только при известном нуле."))
    scenario_statuses = [
        {"scenario_id": f"scenario.{acquisition.lower()}.{uncertainty.lower()}",
         "acquisition": acquisition, "uncertainty": uncertainty,
         "status": "CALCULATED" if any(item["acquisition"] == acquisition and item["uncertainty"] == uncertainty for item in scenarios) else "NOT_CALCULATED",
         "reason_code": branches[acquisition.lower()]["reason_code"],
         "required_fields": branches[acquisition.lower()]["required_fields"],
         "npv_project": next((item["financial"]["npv_project"] for item in scenarios if item["acquisition"] == acquisition and item["uncertainty"] == uncertainty), None)}
        for acquisition in ACQUISITIONS for uncertainty in UNCERTAINTIES
    ]
    result = {
        "schema_version": RESULT_VERSION, "run_id": context.run_id,
        "project_id": context.project_id, "tenant_id": context.tenant_id,
        "input_revision": request.input_revision, "capacity_run_id": context.capacity_response.run_id,
        "capacity_input": {"input_revision": request.input_revision, "process": {"scope": request.process.scope, "role_refs": request.process.role_refs}},
        "branches": branches, "labour": labour_projection, "scenarios": scenarios,
        "scenario_statuses": scenario_statuses, "issues": issues,
        "c05": {"eligibility": context.constraint_report.get("eligibility"), "executability": context.executability.get("status"), "procurement_ready": False},
        "input_provenance": values["field_sources"], "input_ranges": values["input_ranges"],
        "limitations": ["Частичный расчёт: отсутствующие показатели не заменены нулём.", "Сценарные допущения пользователя не являются подтверждением поставщика.", "C05 и закупочная готовность требуют отдельной проверки."],
    }
    return EconomicsV2ExecutionV1(
        result_snapshot=result,
        scenario_spec_snapshot={"schema_version": "scenario-spec-partial-v1", "status": "NOT_CALCULATED", "reason_code": "PARTIAL_FINANCIAL_INPUT", "capacity_run_id": context.capacity_response.run_id},
        revision_id=request.input_revision, rules_version=PARTIAL_RULES_VERSION,
        object_profile_version="calculation-intake-normalization-v2",
        application_version="production-economics-partial-v1",
        diagnostics={"route": "ECONOMICS_PARTIAL_V1", "capacity_run_id": context.capacity_response.run_id, "catalog_version": snapshot.version.code, "procurement_ready": False, "issue_codes": [item["code"] for item in issues]},
    )
