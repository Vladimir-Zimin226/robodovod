"""Conversational profile adapter for Brain v1.1; calculations remain in v2 routes."""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import requests
from auth import AuthContext, require_auth_context, require_csrf
from database import database_session
from fastapi import APIRouter, Depends, HTTPException
from persistence_models import AnalysisRun, Project
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

AUTH_DEP = Depends(require_auth_context)
CSRF_DEP = Depends(require_csrf)
DB_DEP = Depends(database_session)


MODEL = "deepseek-v4-flash"
PROFILE_KEY = "brain_v1"
MAX_TURNS = 60
MAX_TOKENS = 120_000
MAX_ESTIMATED_RUB = 100.0
MAX_VERSIONS = 300
MODEL_TIMEOUT_SECONDS = 50
MODEL_WAIT_SECONDS = 59
MODEL_OUTPUT_TOKENS = 5000
logger = logging.getLogger("robodovod.brain")
EVENT_KEYS = {"status", "failure_kind", "model", "profile_version", "preparation_ms", "external_ms",
              "save_ms", "total_ms", "input", "output", "provider_ms", "validation_ms",
              "provider_http_status", "finish_reason"}


class BrainModelFailure(HTTPException):
    def __init__(self, kind: str, detail: str, *, metrics: dict[str, Any] | None = None):
        super().__init__(503, detail)
        self.kind = kind
        self.metrics = metrics or {}


def _event(**values: Any) -> None:
    """Log allowlisted operational fields; never messages, prompts or API keys."""
    logger.info("brain_turn %s", " ".join(f"{key}={value}" for key, value in sorted(values.items())
                                         if key in EVENT_KEYS))
FIELD_UNITS = {
    "object_type": None, "process_type": None, "cargo_type": None,
    "operations_per_day": "pallet/day", "shifts_count": "shift/day",
    "shift_hours": "h/shift", "operating_days": "day/year",
    "avg_distance_m": "m", "units_per_trip": "pallet/trip",
    "total_area_m2": "m2", "active_area_m2": "m2",
    "zone_label": None, "zone_constraints": None,
    "staff_headcount": "person", "monthly_gross_salary": "RUB/person/month",
    "exchange_seconds": "s", "manual_units_per_shift": "pallet/shift",
    "cleaning_frequency_per_day": "1/day",
}
NUMERIC = set(FIELD_UNITS) - {"object_type", "process_type", "cargo_type", "zone_label", "zone_constraints"}
PROCESS_CODES = {"warehouse_receiving_shipping", "warehouse_cleaning", "warehouse_storage", "warehouse_picking", "warehouse_palletizing", "warehouse_inventory"}
QUESTION_ORDER = ["object_type", "process_type", "operations_per_day", "shifts_count", "shift_hours", "operating_days", "avg_distance_m", "units_per_trip", "exchange_seconds", "staff_headcount", "monthly_gross_salary"]
LABELS = {"object_type": "Какой у вас объект?", "process_type": "Какую операцию хотите автоматизировать?", "operations_per_day": "Какой объём проходит за сутки?", "shifts_count": "Сколько смен в сутки?", "shift_hours": "Сколько часов в одной смене?", "operating_days": "Сколько рабочих дней в году?", "avg_distance_m": "Каково плечо маршрута в одну сторону, в метрах?", "units_per_trip": "Сколько паллет робот перевозит за рейс?", "exchange_seconds": "Сколько секунд занимает погрузка и выгрузка за рейс?", "cleaning_frequency_per_day": "Сколько уборок этой площади проводится за сутки?", "staff_headcount": "Сколько сотрудников сейчас занято на операции?", "monthly_gross_salary": "Какова зарплата gross одного сотрудника за месяц? Без неё денежная ветка труда останется недоступной."}


class TurnUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    value: str | int | float | None
    unit: str | None = None
    raw_text: str | None = None
    provenance: Literal["user", "derived", "default", "expert_assumption", "public_source", "web_estimate"]
    confidence: Literal["high", "medium", "low"] = "medium"
    source_ref: str | None = None
    needs_user_confirmation: bool = True


class ProcessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_id: str
    action: Literal["activate", "deactivate"]
    reason: str = ""


class TurnQuestion(BaseModel):
    field_paths: list[str] = Field(default_factory=list, max_length=2)
    text: str = ""
    choices: list[str] = Field(default_factory=list, max_length=4)


class BrainTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str
    field_updates: list[TurnUpdate] = Field(max_length=25)
    process_updates: list[ProcessUpdate] = Field(default_factory=list, max_length=10)
    next_action: Literal["ask", "offer_default", "preflight", "calculate", "explain_result", "recalculate", "generate_pdf"]
    question: TurnQuestion | None = None


def _model_response_schema() -> dict[str, Any]:
    """Make Pydantic's defaults compatible with AI Studio strict JSON Schema."""
    def require_all(node: Any) -> Any:
        if isinstance(node, list):
            return [require_all(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = {key: require_all(value) for key, value in node.items() if key != "default"}
        if result.get("type") == "object":
            result["required"] = list(result.get("properties", {}))
            result["additionalProperties"] = False
        return result

    return require_all(BrainTurn.model_json_schema())


class TurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=0)


class RetryRequest(BaseModel):
    expected_version: int = Field(ge=0)


class EditRequest(BaseModel):
    expected_version: int = Field(ge=0)
    field: str
    value: str | None = None
    provenance: Literal["user", "expert_assumption"] = "user"
    confirmed: bool = False


class ConfirmRequest(BaseModel):
    expected_version: int = Field(ge=0)
    fields: list[str] = Field(default_factory=list, max_length=30)
    preflight: bool = False


class BindRequest(BaseModel):
    expected_version: int = Field(ge=1)
    run_id: uuid.UUID


class SelectProcessRequest(BaseModel):
    expected_version: int = Field(ge=1)
    process_code: str


def _owned(db: Session, project_id: uuid.UUID, owner_id: uuid.UUID, lock: bool = False) -> Project:
    query = select(Project).where(Project.id == project_id, Project.owner_id == owner_id, Project.status == "ACTIVE")
    project = db.scalar(query.with_for_update() if lock else query)
    if project is None:
        raise HTTPException(404, "project not found")
    return project


def _state(project: Project) -> dict[str, Any]:
    return deepcopy((project.profile or {}).get(PROFILE_KEY)) or {"version": 0, "versions": [], "usage": {"turns": 0, "tokens": 0}}


def _current(state: dict[str, Any], project_id: uuid.UUID) -> dict[str, Any]:
    if state["versions"]:
        return state["versions"][-1]
    return {"project_id": str(project_id), "profile_version": 0, "parent_version": None,
            "methodology_version": "3.2", "object": {"object_type": "other"}, "active_processes": [], "fields": {},
            "process_fields": {}, "selected_process": None,
            "assumptions": [], "catalog_context": {}, "utterance": None, "preflight_confirmed": False, "runs": []}


def readiness(profile: dict[str, Any]) -> dict[str, Any]:
    fields = profile["fields"]
    known = lambda key: bool(fields.get(key, {}).get("confirmed_by_user") and str(fields[key]["value"]).strip())
    process = fields.get("process_type", {}).get("value")
    technical = [key for key in QUESTION_ORDER[:9] if key not in ("avg_distance_m", "units_per_trip", "exchange_seconds") or process == "transport"]
    if process == "cleaning":
        technical = [key for key in technical if key != "exchange_seconds"] + ["cleaning_frequency_per_day"]
    missing = [key for key in technical if not known(key)]
    if process not in {"transport", "cleaning"}:
        missing.append("supported_formula")
    if known("object_type") and fields["object_type"]["value"] != "retail":
        missing.append("supported_object")
    if known("operations_per_day") and fields["operations_per_day"].get("unit") != ("m2/day" if process == "cleaning" else "pallet/day"):
        missing.append("operations_unit")
    if known("shifts_count") and known("shift_hours") and float(fields["shifts_count"]["value"]) * float(fields["shift_hours"]["value"]) > 24:
        missing.append("schedule_over_24h")
    for key, minimum, maximum, integral in (("total_area_m2", 0, 100_000_000, False),
                                             ("active_area_m2", 0, 100_000_000, False),
                                             ("operations_per_day", 0, 10_000_000, False),
                                             ("shifts_count", 0, 3, True), ("shift_hours", 0, 24, False),
                                             ("operating_days", 1, 366, True), ("avg_distance_m", 0, 1_000_000, False),
                                             ("units_per_trip", 0, 100_000, True), ("exchange_seconds", 0, 86_400, False),
                                             ("cleaning_frequency_per_day", 0, 100, False)):
        if not known(key):
            continue
        try:
            amount = Decimal(str(fields[key]["value"]))
            if amount <= minimum or amount > maximum or (integral and amount != amount.to_integral_value()):
                missing.append(f"invalid_{key}")
        except (InvalidOperation, ValueError):
            missing.append(f"invalid_{key}")
    if known("total_area_m2") and known("active_area_m2") and Decimal(str(fields["active_area_m2"]["value"])) > Decimal(str(fields["total_area_m2"]["value"])):
        missing.append("active_area_exceeds_total")
    if known("shift_hours") and Decimal(str(fields["shift_hours"]["value"])) not in {Decimal(value) for value in (6, 8, 10, 11, 12)}:
        missing.append("invalid_shift_hours")
    labour_fields = ["staff_headcount", "monthly_gross_salary"]
    if process == "transport":
        labour_fields.append("manual_units_per_shift")
    labour = [key for key in labour_fields if not known(key)]
    commercial = ["role_salaries_confirmed_as_monthly_gross", "organizer_price_currency_rub_confirmed", "initial_battery_in_robot_price_confirmed", "battery_replacements_in_service_confirmed", "raas_vendor_scope_confirmed"]
    economic_runs = [item for item in profile.get("runs", []) if item.get("run_kind") == "FULL_ANALYSIS"]
    branches = economic_runs[-1].get("branches", {}) if economic_runs else {}
    def branch_status(key: str, missing: list[str]) -> dict[str, Any]:
        branch = branches.get(key) or {}
        required = branch.get("required_fields")
        return {"ready": branch.get("status") in {"CALCULATED", "AVAILABLE"},
                "missing": required if isinstance(required, list) else missing}
    has_capacity = any(item.get("run_kind") == "CAPACITY_ANALYSIS" for item in profile.get("runs", []))
    has_economics = bool(economic_runs)
    question_key = next((key for key in [*QUESTION_ORDER, "cleaning_frequency_per_day"] if key in missing), None)
    if question_key is None:
        question_key = next((key for key in missing if key.startswith("invalid_") or key == "operations_unit"), None)
    if question_key is None:
        question_key = next((key for key in QUESTION_ORDER if key in labour), None)
    question = None
    if question_key:
        message = ("Укажите 1–3 смены в сутки." if question_key == "invalid_shifts_count" else
                   "Укажите 6, 8, 10, 11 или 12 часов в смене." if question_key == "invalid_shift_hours" else
                   "Проверьте значение и единицу поля." if question_key.startswith("invalid_") or question_key == "operations_unit" else
                   LABELS[question_key])
        question = {"field": question_key, "text": message}
    state = ("REPORT_READY" if has_economics else "RESULT_READY" if has_capacity else
             "READY_FOR_CONFIRMATION" if not missing else "TECHNICAL_MINIMUM" if known("process_type") else
             "PROCESS_IDENTIFIED" if profile.get("active_processes") else "DISCOVERY" if fields else "NEW")
    return {"state": state, "technical": {"ready": not missing, "missing": missing},
            "labour": branch_status("labour", missing + labour) if branches else {"ready": not missing and not labour, "missing": missing + labour},
            "purchase": branch_status("purchase", ["economics_inputs", *commercial[:4]]),
            "raas": branch_status("raas", ["economics_inputs", commercial[0], commercial[4]]),
            "next_question": question}


def _next(state: dict[str, Any], profile: dict[str, Any], **changes: Any) -> dict[str, Any]:
    if len(state["versions"]) >= MAX_VERSIONS:
        raise HTTPException(429, "Лимит версий проекта достигнут; сохранённые расчёты остаются доступными.")
    version = deepcopy(profile)
    version.update(changes)
    version["parent_version"] = profile["profile_version"] or None
    version["profile_version"] = profile["profile_version"] + 1
    version["preflight_confirmed"] = False
    version["runs"] = []
    state["version"] = version["profile_version"]
    state["versions"].append(version)
    return version


def _save(db: Session, project: Project, state: dict[str, Any]) -> None:
    project.profile = {**(project.profile or {}), PROFILE_KEY: state}
    db.commit()


def _check_version(state: dict[str, Any], expected: int) -> None:
    if state["version"] != expected:
        raise HTTPException(409, "profile version changed; reload before editing")


def _run_matches_profile(run: AnalysisRun, profile: dict[str, Any]) -> bool:
    data = run.input_snapshot or {}
    if run.run_kind == "FULL_ANALYSIS":
        return str(data.get("capacity_run_id")) in {item["run_id"] for item in profile["runs"] if item["run_kind"] == "CAPACITY_ANALYSIS"}
    if run.run_kind != "CAPACITY_ANALYSIS":
        return False
    if not any(item.get("assumption_version") == f"profile-v{profile['profile_version']}" for item in data.get("provenance", [])):
        return False
    process = data.get("process") or {}
    if process.get("process_code") != (profile.get("selected_process") or process.get("process_code")):
        return False
    fields = profile["fields"]
    if fields.get("object_type", {}).get("value") != "retail" or not fields["object_type"].get("confirmed_by_user"):
        return False
    expected_process = "cleaning" if process.get("process_code") == "warehouse_cleaning" else "transport"
    if fields.get("process_type", {}).get("value") != expected_process or not fields["process_type"].get("confirmed_by_user"):
        return False
    values = {
        "operations_per_day": process.get("demand"),
        "shifts_count": (process.get("schedule") or {}).get("shifts_per_day"),
        "shift_hours": (process.get("schedule") or {}).get("shift_hours"),
        "operating_days": (process.get("schedule") or {}).get("days_per_year"),
        "avg_distance_m": process.get("route_distance"),
        "units_per_trip": process.get("explicit_batch"),
        "exchange_seconds": (process.get("exchange") or {}).get("total_time"),
    }
    for key, quantity in values.items():
        if key in {"avg_distance_m", "units_per_trip", "exchange_seconds"} and process.get("scope") == "CLEANING_AREA":
            continue
        field = fields.get(key)
        if not field or not field.get("confirmed_by_user") or not isinstance(quantity, dict):
            return False
        try:
            if Decimal(str(field["value"])) != Decimal(str(quantity.get("normalized_value"))):
                return False
        except InvalidOperation:
            return False
    if process.get("scope") == "CLEANING_AREA":
        frequency = fields.get("cleaning_frequency_per_day")
        if not frequency or not frequency.get("confirmed_by_user"):
            return False
        try:
            if Decimal(str(frequency["value"])) != Decimal(str((data.get("cleaning_frequency") or {}).get("normalized_value"))):
                return False
        except InvalidOperation:
            return False
    expected_zone = fields.get("zone_label", {}).get("value") if fields.get("zone_label", {}).get("confirmed_by_user") else "Основная зона"
    if (data.get("zone_context") or {}).get("label") != expected_zone:
        return False
    roles = (data.get("role_pool") or {}).get("roles") or []
    headcount = fields.get("staff_headcount")
    if not headcount or not headcount.get("confirmed_by_user"):
        return len(roles) == 0
    role_code = "cleaner" if expected_process == "cleaning" else "forklift_driver"
    if len(roles) != 1 or roles[0].get("role_code") != role_code:
        return False
    try:
        if Decimal(str(headcount["value"])) != Decimal(str((roles[0].get("headcount") or {}).get("normalized_value"))):
            return False
        salary = fields.get("monthly_gross_salary")
        actual = (roles[0].get("monthly_gross_salary") or {})
        if salary and salary.get("confirmed_by_user"):
            return Decimal(str(salary["value"])) == Decimal(str(actual.get("normalized_value")))
        return actual.get("status") == "MISSING"
    except InvalidOperation:
        return False


def _validate_update(update: TurnUpdate, utterance: str, *, allow_salary_assumption: bool = False) -> tuple[str, dict[str, Any]] | None:
    key = update.path.removeprefix("fields.")
    if key not in FIELD_UNITS or update.value is None or update.provenance not in {"user", "expert_assumption"}:
        return None
    if update.provenance == "expert_assumption" and key == "monthly_gross_salary" and not allow_salary_assumption:
        return None
    value = str(update.value).strip().replace(",", ".")
    if key in NUMERIC:
        if not re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", value) or len(value) > 12:
            return None
        if key != "monthly_gross_salary" and float(value) <= 0:
            return None
        if update.unit != FIELD_UNITS[key] and not (key == "operations_per_day" and update.unit == "m2/day"):
            return None
        if update.provenance == "user" and not re.search(r"(?<!\d)" + re.escape(value) + r"(?!\d)", utterance.replace(",", ".")):
            return None
        if update.provenance == "user":
            match = re.search(r"(?<!\d)" + re.escape(value) + r"(?!\d)", utterance.replace(",", "."))
            nearby = utterance[match.end():match.end() + 24].casefold() if match else ""
            if key == "avg_distance_m" and re.match(r"\s*(?:км|km|километр)", nearby):
                return None
            if key == "operations_per_day" and re.match(r"\s*(?:паллет[ы]?\s*)?(?:в\s*)?(?:недел|месяц|час)", nearby):
                return None
    elif len(value) > 1000:
        return None
    if key == "object_type" and value not in {"retail", "airport", "clinic", "other"}:
        return None
    if key == "process_type" and value not in {"transport", "cleaning", "unsupported"}:
        return None
    if key == "units_per_trip" and not value.isdigit():
        return None
    return key, {"value": value, "unit": FIELD_UNITS[key], "raw_text": utterance,
                 "provenance": update.provenance,
                 "source_ref": "brain-v1.1-scenario-proposal" if update.provenance == "expert_assumption" else None,
                 "confidence": update.confidence, "confirmed_by_user": False,
                 "updated_at": datetime.now(timezone.utc).isoformat()}


def _explicit_facts(message: str) -> tuple[list[TurnUpdate], list[ProcessUpdate]]:
    """Conservative local extraction for outages; every result remains unconfirmed."""
    lower = message.casefold()
    fields: list[TurnUpdate] = []
    processes: list[ProcessUpdate] = []
    if re.search(r"склад[аеуы]?|складск", lower):
        fields.append(TurnUpdate(path="object_type", value="retail", provenance="user", raw_text=message))
    cleaning = bool(re.search(r"уборк|убира|клининг", lower))
    transport = bool(re.search(r"перевоз|перемещ|транспортир", lower) and re.search(r"паллет|поддон", lower))
    if cleaning and not transport:
        fields.append(TurnUpdate(path="process_type", value="cleaning", provenance="user", raw_text=message))
        processes.append(ProcessUpdate(process_id="warehouse_cleaning", action="activate"))
    elif transport:
        fields.append(TurnUpdate(path="process_type", value="transport", provenance="user", raw_text=message))
        processes.append(ProcessUpdate(process_id="warehouse_receiving_shipping", action="activate"))
        if cleaning:
            processes.append(ProcessUpdate(process_id="warehouse_cleaning", action="activate"))
    elif re.search(r"комплект|отбор|пикинг", lower):
        processes.append(ProcessUpdate(process_id="warehouse_picking", action="activate"))
    elif re.search(r"хранени|складир", lower):
        processes.append(ProcessUpdate(process_id="warehouse_storage", action="activate"))
    patterns = [
        ("operations_per_day", r"\b(\d+(?:[.,]\d+)?)\s*(?:паллет\w*|поддон\w*)\s*(?:в\s*(?:сутки|день)|/\s*(?:сутки|день))", "pallet/day"),
        ("operations_per_day", r"\b(\d+(?:[.,]\d+)?)\s*(?:м²|м2|кв\.?\s*м\.?|квадратн\w*\s*метр\w*)\s*(?:в\s*(?:сутки|день)|/\s*(?:сутки|день))", "m2/day"),
        ("avg_distance_m", r"\b(\d+(?:[.,]\d+)?)\s*(?:м\b(?![²2])|метр\w*\b(?!\s*(?:квадрат|кв)))", "m"),
        ("units_per_trip", r"\b(\d+)\s*(?:паллет\w*|поддон\w*)\s*(?:за|/\s*)\s*рейс", "pallet/trip"),
        ("shifts_count", r"\b(\d+)\s*смен\w*", "shift/day"),
        ("shift_hours", r"(?:по\s*)?\b(\d+)\s*(?:ч\b|час\w*)\s*(?:в\s*смен\w*)?", "h/shift"),
        ("operating_days", r"\b(\d+)\s*(?:дн\w*|дней)\s*(?:в|/)\s*год\w*", "day/year"),
        ("staff_headcount", r"\b(\d+)\s*(?:сотрудник\w*|человек|водител\w*)", "person"),
        ("cleaning_frequency_per_day", r"\b(\d+(?:[.,]\d+)?)\s*(?:раз|уборк\w*)\s*(?:в\s*сутки|/\s*сутки)", "1/day"),
    ]
    for key, pattern, unit in patterns:
        found = re.search(pattern, lower)
        if found:
            fields.append(TurnUpdate(path=key, value=found.group(1).replace(",", "."), unit=unit,
                                     provenance="user", raw_text=message))
    return fields, processes


def _answer_to_saved_question(message: str, profile: dict[str, Any]) -> list[TurnUpdate]:
    """A bare numeric reply may propose only the field the server asked about."""
    question = readiness(profile).get("next_question") or {}
    field = question.get("field")
    if field not in NUMERIC or not re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*", message):
        return []
    unit = FIELD_UNITS[field]
    if field == "operations_per_day" and profile.get("fields", {}).get("process_type", {}).get("value") == "cleaning":
        unit = "m2/day"
    return [TurnUpdate(path=field, value=message.strip().replace(",", "."), unit=unit, provenance="user")]


def _apply_proposals(profile: dict[str, Any], message: str, updates: list[TurnUpdate], process_updates: list[ProcessUpdate]) -> None:
    explicit_processes = {item.process_id for item in _explicit_facts(message)[1]}
    process_updates = [item for item in process_updates if item.process_id in explicit_processes]
    mentioned = {item.process_id for item in process_updates if item.action == "activate" and item.process_id in PROCESS_CODES}
    selected = profile.get("selected_process")
    single = next(iter(mentioned)) if len(mentioned) == 1 else None
    process_fields = profile.setdefault("process_fields", {})
    if single and selected and single != selected:
        process_fields[selected] = deepcopy(profile["fields"])
        fields = deepcopy(process_fields.get(single) or {key: deepcopy(value) for key, value in profile["fields"].items()
                                                      if key in {"object_type", "zone_label", "zone_constraints"}})
        profile["selected_process"] = single
    else:
        fields = dict(profile["fields"])
    for update in updates:
        accepted = _validate_update(update, message)
        if accepted:
            fields[accepted[0]] = {**accepted[1], "unit": update.unit}
    profile["fields"] = fields
    profile["object"] = {"object_type": fields.get("object_type", {}).get("value", "other")}
    processes = set(profile["active_processes"])
    for update in process_updates:
        if update.process_id in PROCESS_CODES:
            (processes.add if update.action == "activate" else processes.discard)(update.process_id)
    profile["active_processes"] = sorted(processes)
    if not profile.get("selected_process") and profile["active_processes"]:
        profile["selected_process"] = "warehouse_receiving_shipping" if "warehouse_receiving_shipping" in processes else profile["active_processes"][0]
    if profile.get("selected_process"):
        profile.setdefault("process_fields", {})[profile["selected_process"]] = deepcopy(fields)


def _call_model(message: str, profile: dict[str, Any]) -> tuple[BrainTurn, dict[str, Any]]:
    key, folder = os.getenv("YC_API_KEY"), os.getenv("YC_FOLDER_ID")
    if not key or not folder:
        raise BrainModelFailure("NOT_CONFIGURED", "Сервис диалога сейчас недоступен. Черновик сохранён; поля можно исправить вручную.")
    prompt = ("Ты Robovod Brain v1.1. Извлеки только явно сказанные пользователем поля из последнего сообщения. "
              "Не придумывай объёмы, зарплату, плечо, единицы за рейс. Для числа укажи точную единицу из списка. "
              "object_type: retail/airport/clinic/other; process_type: transport/cleaning/unsupported. "
              "Паллетная перевозка на складе: transport. Из нескольких операций активируй их коды. "
              "Неподтверждённые поля не становятся фактами. Не рассчитывай парк или NPV. "
              "Верни JSON по схеме. Поля: " + json.dumps(FIELD_UNITS, ensure_ascii=False))
    confirmed = {key: {"value": value.get("value"), "unit": value.get("unit")}
                 for key, value in profile.get("fields", {}).items()
                 if key in FIELD_UNITS and value.get("confirmed_by_user")}
    next_question = readiness({**profile, "fields": profile.get("fields", {})}).get("next_question")
    prompt += (" Ты извлекаешь предложения, а не подтверждаешь их. Короткий ответ относится только к следующему вопросу. "
               "Не копируй сохранённые значения в field_updates. Веди беседу одним следующим вопросом; "
               "расчёты и выбор следующего обязательного поля выполняет сервер. Подтверждённый контекст: "
               + json.dumps({"fields": confirmed, "selected_process": profile.get("selected_process"),
                             "next_question": next_question}, ensure_ascii=False))
    body = {"model": f"gpt://{folder}/{MODEL}", "messages": [
        {"role": "system", "content": prompt},
        {"role": "user", "content": message}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "RobovodAgentTurn", "strict": True, "schema": _model_response_schema()}},
        "max_tokens": MODEL_OUTPUT_TOKENS, "temperature": 0.1, "stream": False}
    started = time.perf_counter()
    http_status = None
    finish_reason = None
    token_use = {"input": 0, "output": 0}
    try:
        response = requests.post("https://ai.api.cloud.yandex.net/v1/chat/completions", json=body,
                                 headers={"Authorization": f"Api-Key {key}"}, timeout=(5, MODEL_TIMEOUT_SECONDS))
        provider_ms = round((time.perf_counter() - started) * 1000, 2)
        http_status = getattr(response, "status_code", None)
        response.raise_for_status()
        data = response.json()
        finish_reason = data["choices"][0].get("finish_reason")
        usage = data.get("usage") or {}
        token_use = {"input": int(usage.get("prompt_tokens", 0)), "output": int(usage.get("completion_tokens", 0))}
        if finish_reason == "length":
            raise BrainModelFailure("LENGTH", "Ответ модели оборвался на лимите вывода. Черновик сохранён; повторите запрос.")
        if finish_reason != "stop":
            raise BrainModelFailure("FINISH_REASON", "Модель не завершила ответ. Черновик сохранён; повторите запрос.")
        validation_started = time.perf_counter()
        turn = BrainTurn.model_validate_json(data["choices"][0]["message"]["content"])
        return turn, {**token_use, "provider_ms": provider_ms,
                      "validation_ms": round((time.perf_counter() - validation_started) * 1000, 2),
                      "finish_reason": finish_reason, "provider_http_status": http_status}
    except BrainModelFailure as exc:
        exc.metrics = {**token_use, "provider_ms": round((time.perf_counter() - started) * 1000, 2),
                       "finish_reason": finish_reason, "provider_http_status": http_status}
        raise
    except requests.Timeout as exc:
        raise BrainModelFailure("TIMEOUT", "Время ожидания модели истекло. Черновик сохранён; повторите запрос.",
                                metrics={"provider_ms": round((time.perf_counter() - started) * 1000, 2)}) from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else http_status
        raise BrainModelFailure(f"HTTP_{status or 'UNKNOWN'}", "AI Studio отклонил запрос. Черновик сохранён; повторите позже или исправьте поля вручную.",
                                metrics={"provider_ms": round((time.perf_counter() - started) * 1000, 2),
                                         "provider_http_status": status}) from exc
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise BrainModelFailure("INVALID_RESPONSE", "Модель не ответила корректно. Черновик сохранён; повторите запрос или исправьте поля вручную.",
                                metrics={**token_use, "provider_ms": round((time.perf_counter() - started) * 1000, 2),
                                         "finish_reason": finish_reason, "provider_http_status": http_status}) from exc


def _local_turn(message: str) -> BrainTurn | None:
    """Handle only narrow server-known actions; extraction still uses the local parser."""
    normalized = re.sub(r"[.!?\s]+", " ", message.strip().lower()).strip()
    if normalized in {"рассчитать", "запустить расчёт", "покажи расчёт", "создать pdf", "покажи pdf", "что дальше"}:
        return BrainTurn(message="Проверьте и подтвердите поля профиля; расчёт и PDF запускаются отдельными действиями.",
                         field_updates=[], process_updates=[], next_action="preflight", question=None)
    return None


def _bounded_model_call(message: str, profile: dict[str, Any]) -> tuple[BrainTurn, dict[str, Any]]:
    """Bound the HTTP request's user-visible wait even if a peer trickles data."""
    result: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            result.put((True, _call_model(message, profile)))
        except Exception as exc:  # noqa: BLE001 - transfer worker failure to request thread
            result.put((False, exc))

    threading.Thread(target=run, daemon=True, name="brain-model-request").start()
    try:
        success, value = result.get(timeout=MODEL_WAIT_SECONDS)
    except queue.Empty as exc:
        raise BrainModelFailure("TIMEOUT", "Время ожидания модели истекло. Черновик сохранён; повторите запрос.",
                                metrics={"provider_ms": MODEL_WAIT_SECONDS * 1000}) from exc
    if not success:
        raise value
    return value


class DefaultRequest(BaseModel):
    model_config = {"extra": "forbid", "strict": True}
    expected_version: int = Field(ge=0)
    catalog_code: str = Field(min_length=1, max_length=180)
    field: Literal["exchange_seconds", "units_per_trip", "operating_days"]


def create_brain_router() -> APIRouter:
    router = APIRouter(prefix="/api/brain")

    @router.post("/projects/{project_id}/catalog-default")
    def propose_default(project_id: uuid.UUID, payload: DefaultRequest,
                        context: AuthContext = CSRF_DEP, db: Session = DB_DEP):
        from catalog_runtime import CatalogRuntime

        project = _owned(db, project_id, context.user.id, lock=True)
        state = _state(project)
        _check_version(state, payload.expected_version)
        old = _current(state, project_id)
        snapshot = CatalogRuntime().load_discovery()
        norm = next((item for item in snapshot.admin_defaults if item["key"] == payload.field), None)
        if payload.catalog_code != snapshot.version.code or norm is None:
            raise HTTPException(409, "catalog default changed; reload before applying")
        if old["fields"].get(payload.field, {}).get("confirmed_by_user"):
            raise HTTPException(409, "confirmed user value cannot be replaced by a catalog default")
        fields = deepcopy(old["fields"])
        fields[payload.field] = {"value": norm["value"], "unit": norm["unit"], "raw_text": norm["value"],
            "provenance": "expert_assumption", "source_ref": f"catalog:{snapshot.version.code}:{norm['source']}",
            "confidence": "low", "confirmed_by_user": False, "updated_at": datetime.now(timezone.utc).isoformat(),
            "catalog_default": {**norm, "catalog_code": snapshot.version.code, "sha256": snapshot.version.content_sha256}}
        process_fields = deepcopy(old.get("process_fields") or {})
        if old.get("selected_process"):
            process_fields[old["selected_process"]] = deepcopy(fields)
        current = _next(state, old, fields=fields, process_fields=process_fields, utterance="catalog-default:" + payload.field)
        _save(db, project, state)
        return {"profile": current, "readiness": readiness(current)}

    @router.get("/projects/{project_id}")
    def read(project_id: uuid.UUID, context: AuthContext = AUTH_DEP, db: Session = DB_DEP):
        project = _owned(db, project_id, context.user.id)
        state = _state(project)
        profile = _current(state, project_id)
        if profile.get("model_status") == "PENDING" and profile.get("model_started_at"):
            try:
                expired = (datetime.now(timezone.utc) - datetime.fromisoformat(profile["model_started_at"])).total_seconds() > 70
            except ValueError:
                expired = True
            if expired:
                profile["model_status"] = "TIMEOUT"
                profile["model_failure_kind"] = "ORPHANED_REQUEST"
                profile["model_error"] = "Ожидание прервалось. Сохранённое сообщение можно повторить."
                _save(db, project, state)
        return {"profile": profile, "readiness": readiness(profile), "usage": state["usage"], "versions": state["versions"]}

    def finish_saved_turn(project: Project, db: Session, version: int, attempt_id: str, message: str,
                          previous: dict[str, Any], prepared_at: float,
                          preparation_ms: float) -> dict[str, Any]:
        model_started = time.perf_counter()
        local = _local_turn(message)
        try:
            if local is None:
                answer, token_use = _bounded_model_call(message, previous)
                source = "MODEL"
            else:
                answer, token_use, source = local, {"input": 0, "output": 0}, "LOCAL"
            failure = None
        except HTTPException as exc:
            answer, token_use, source = None, getattr(exc, "metrics", {}), "FALLBACK"
            failure = exc
        external_ms = round((time.perf_counter() - model_started) * 1000, 2) if local is None else 0.0
        db.refresh(project, with_for_update=True)
        state = _state(project)
        if (state["version"] != version or state["versions"][-1].get("model_attempt_id") != attempt_id
                or state["versions"][-1].get("model_status") != "PENDING"):
            _event(status="STALE", failure_kind="VERSION_CONFLICT", model=MODEL,
                   preparation_ms=preparation_ms, external_ms=external_ms)
            raise HTTPException(409, "profile changed during model request")
        current = state["versions"][-1]
        usage = state["usage"]
        if failure is not None:
            current["model_error"] = failure.detail
            local_updates, local_processes = _explicit_facts(message)
            _apply_proposals(current, message, [*local_updates, *_answer_to_saved_question(message, previous)], local_processes)
            current["model_message"] = "Локально распознаны только явно названные значения. Проверьте и подтвердите их."
            current["model_status"] = "TIMEOUT" if getattr(failure, "kind", None) == "TIMEOUT" else "FALLBACK"
            current["model_failure_kind"] = getattr(failure, "kind", "MODEL_ERROR")
        elif usage["tokens"] + token_use["input"] + token_use["output"] > MAX_TOKENS:
            current["model_error"] = "Лимит токенов проекта достигнут; используйте ручное редактирование."
            current["model_status"] = "FALLBACK"
            current["model_failure_kind"] = "TOKEN_LIMIT"
        else:
            local_updates, local_processes = _explicit_facts(message)
            _apply_proposals(current, message, [*answer.field_updates, *local_updates, *_answer_to_saved_question(message, previous)],
                             [*answer.process_updates, *local_processes])
            current["model_message"] = answer.message[:1000]
            current["model_error"] = None
            current["model_status"] = source
            current["model_failure_kind"] = None
        usage["tokens"] += token_use.get("input", 0) + token_use.get("output", 0)
        usage["input_tokens"] = usage.get("input_tokens", 0) + token_use.get("input", 0)
        usage["output_tokens"] = usage.get("output_tokens", 0) + token_use.get("output", 0)
        usage["estimated_rub"] = round(usage["input_tokens"] * 0.3 / 1000 + usage["output_tokens"] * 0.5 / 1000, 4)
        save_started = time.perf_counter()
        _save(db, project, state)
        save_ms = round((time.perf_counter() - save_started) * 1000, 2)
        metrics = {key: token_use.get(key) for key in ("input", "output", "provider_ms", "validation_ms",
                                                     "provider_http_status", "finish_reason")}
        _event(status=current["model_status"], failure_kind=current["model_failure_kind"], model=MODEL,
               profile_version=version, preparation_ms=preparation_ms, external_ms=external_ms,
               save_ms=save_ms, total_ms=round((time.perf_counter() - prepared_at) * 1000, 2), **metrics)
        return {"profile": current, "readiness": readiness(current), "model_error": current.get("model_error"),
                "model_status": current["model_status"], "usage": usage}

    @router.post("/projects/{project_id}/turn")
    def turn(project_id: uuid.UUID, payload: TurnRequest, context: AuthContext = CSRF_DEP, db: Session = DB_DEP):
        started = time.perf_counter()
        project = _owned(db, project_id, context.user.id, lock=True)
        state = _state(project)
        _check_version(state, payload.expected_version)
        profile = _current(state, project_id)
        usage = state["usage"]
        if usage["turns"] >= MAX_TURNS or usage["tokens"] + 5000 >= MAX_TOKENS:
            raise HTTPException(429, "Лимит диалога проекта исчерпан; сохранённый профиль можно редактировать вручную.")
        if usage.get("estimated_rub", 0) + 3 >= MAX_ESTIMATED_RUB:
            raise HTTPException(429, "Лимит расходов на диалог проекта достигнут; сохранённый профиль можно редактировать вручную.")
        now = datetime.now(timezone.utc)
        recent = [stamp for stamp in usage.get("recent_turns", []) if (now - datetime.fromisoformat(stamp)).total_seconds() < 60]
        if len(recent) >= 12:
            raise HTTPException(429, "Слишком много сообщений за минуту. Повторите позже; профиль сохранён.")
        # Save the user's words before calling the external model.
        attempt_id = uuid.uuid4().hex
        current = _next(state, profile, utterance=payload.message, model_message=None, model_error=None,
                        model_status="PENDING", model_failure_kind=None,
                        model_started_at=datetime.now(timezone.utc).isoformat(), model_attempt_id=attempt_id)
        usage["turns"] += 1
        usage["recent_turns"] = [*recent, now.isoformat()]
        _save(db, project, state)
        return finish_saved_turn(project, db, current["profile_version"], attempt_id, payload.message, profile,
                                 started, round((time.perf_counter() - started) * 1000, 2))

    @router.post("/projects/{project_id}/retry")
    def retry(project_id: uuid.UUID, payload: RetryRequest,
              context: AuthContext = CSRF_DEP, db: Session = DB_DEP):
        started = time.perf_counter()
        project = _owned(db, project_id, context.user.id, lock=True)
        state = _state(project)
        _check_version(state, payload.expected_version)
        current = _current(state, project_id)
        if current.get("model_status") not in {"FALLBACK", "TIMEOUT"} or not current.get("utterance"):
            raise HTTPException(409, "no failed saved message to retry")
        message = current["utterance"]
        current["model_status"] = "PENDING"
        current["model_started_at"] = datetime.now(timezone.utc).isoformat()
        attempt_id = uuid.uuid4().hex
        current["model_attempt_id"] = attempt_id
        current["model_error"] = None
        current["model_failure_kind"] = None
        _save(db, project, state)
        return finish_saved_turn(project, db, current["profile_version"], attempt_id, message, current,
                                 started, round((time.perf_counter() - started) * 1000, 2))

    @router.post("/projects/{project_id}/edit")
    def edit(project_id: uuid.UUID, payload: EditRequest, context: AuthContext = CSRF_DEP, db: Session = DB_DEP):
        project = _owned(db, project_id, context.user.id, lock=True)
        state = _state(project)
        _check_version(state, payload.expected_version)
        old = _current(state, project_id)
        if payload.field not in FIELD_UNITS:
            raise HTTPException(422, "unknown field")
        fields = dict(old["fields"])
        if payload.value is None or not payload.value.strip():
            fields.pop(payload.field, None)
        else:
            unit = "m2/day" if payload.field == "operations_per_day" and old["fields"].get("process_type", {}).get("value") == "cleaning" else FIELD_UNITS[payload.field]
            update = TurnUpdate(path=payload.field, value=payload.value, unit=unit, raw_text=payload.value,
                                provenance=payload.provenance)
            accepted = _validate_update(update, payload.value, allow_salary_assumption=True)
            if not accepted:
                raise HTTPException(422, "invalid value or unit")
            fields[payload.field] = {**accepted[1], "unit": unit, "confirmed_by_user": payload.confirmed,
                                     "source_ref": "user-scenario-assumption" if payload.provenance == "expert_assumption" else None}
        process_fields = deepcopy(old.get("process_fields") or {})
        selected = old.get("selected_process")
        if payload.field == "process_type" and selected is None:
            selected = "warehouse_cleaning" if payload.value == "cleaning" else "warehouse_receiving_shipping" if payload.value == "transport" else None
        if selected:
            process_fields[selected] = deepcopy(fields)
        current = _next(state, old, fields=fields, process_fields=process_fields, selected_process=selected,
                        object={"object_type": fields.get("object_type", {}).get("value", "other")}, utterance=f"edit:{payload.field}")
        _save(db, project, state)
        return {"profile": current, "readiness": readiness(current)}

    @router.post("/projects/{project_id}/select-process")
    def select_process(project_id: uuid.UUID, payload: SelectProcessRequest,
                       context: AuthContext = CSRF_DEP, db: Session = DB_DEP):
        project = _owned(db, project_id, context.user.id, lock=True)
        state = _state(project)
        _check_version(state, payload.expected_version)
        old = _current(state, project_id)
        if payload.process_code not in old["active_processes"]:
            raise HTTPException(422, "process is not active in this profile")
        if payload.process_code == old.get("selected_process"):
            return {"profile": old, "readiness": readiness(old)}
        process_fields = deepcopy(old.get("process_fields") or {})
        if old.get("selected_process"):
            process_fields[old["selected_process"]] = deepcopy(old["fields"])
        fields = deepcopy(process_fields.get(payload.process_code) or {})
        if not fields:
            fields = {key: deepcopy(value) for key, value in old["fields"].items()
                      if key in {"object_type", "zone_label", "zone_constraints"}}
            fields["process_type"] = {"value": "cleaning" if payload.process_code == "warehouse_cleaning" else
                                      "transport" if payload.process_code == "warehouse_receiving_shipping" else "unsupported",
                                      "unit": None, "raw_text": "selected process", "provenance": "user",
                                      "source_ref": None, "confidence": "high", "confirmed_by_user": False,
                                      "updated_at": datetime.now(timezone.utc).isoformat()}
        process_fields[payload.process_code] = deepcopy(fields)
        current = _next(state, old, fields=fields, process_fields=process_fields,
                        selected_process=payload.process_code, utterance=f"select:{payload.process_code}")
        _save(db, project, state)
        return {"profile": current, "readiness": readiness(current)}

    @router.post("/projects/{project_id}/confirm")
    def confirm(project_id: uuid.UUID, payload: ConfirmRequest, context: AuthContext = CSRF_DEP, db: Session = DB_DEP):
        project = _owned(db, project_id, context.user.id, lock=True)
        state = _state(project)
        _check_version(state, payload.expected_version)
        old = _current(state, project_id)
        if any(field not in old["fields"] for field in payload.fields):
            raise HTTPException(422, "unknown or missing field")
        fields = {key: {**value, "confirmed_by_user": True} if key in payload.fields else value for key, value in old["fields"].items()}
        process_fields = deepcopy(old.get("process_fields") or {})
        if old.get("selected_process"):
            process_fields[old["selected_process"]] = deepcopy(fields)
        current = _next(state, old, fields=fields, process_fields=process_fields,
                        preflight_confirmed=payload.preflight)
        if payload.preflight and not readiness(current)["technical"]["ready"]:
            raise HTTPException(422, "technical inputs are not ready")
        current["preflight_confirmed"] = payload.preflight
        _save(db, project, state)
        return {"profile": current, "readiness": readiness(current)}

    @router.post("/projects/{project_id}/runs")
    def bind(project_id: uuid.UUID, payload: BindRequest, context: AuthContext = CSRF_DEP, db: Session = DB_DEP):
        project = _owned(db, project_id, context.user.id, lock=True)
        state = _state(project)
        _check_version(state, payload.expected_version)
        current = _current(state, project_id)
        if not current["preflight_confirmed"]:
            raise HTTPException(422, "profile preflight was not confirmed")
        run = db.scalar(select(AnalysisRun).where(AnalysisRun.id == payload.run_id, AnalysisRun.project_id == project_id, AnalysisRun.status == "SUCCEEDED"))
        if run is None:
            raise HTTPException(404, "run not found")
        if not _run_matches_profile(run, current):
            raise HTTPException(422, "run inputs do not match this confirmed profile version")
        current["runs"] = [*current["runs"], {"run_id": str(run.id), "run_kind": run.run_kind, "result_sha256": run.result_sha256,
                                                 "catalog_version": run.catalog_version_code, "rules_version": run.rules_version,
                                                 "economics_version": run.economics_version,
                                                 "branches": (run.result_snapshot or {}).get("branches", {}) if run.run_kind == "FULL_ANALYSIS" else {}}]
        context_bindings = dict(current.get("catalog_context") or {})
        if run.run_kind == "CAPACITY_ANALYSIS":
            context_bindings.update({"capacity_source_code": run.catalog_version_code,
                                     "capacity_source_digest": (run.version_bindings_snapshot or {}).get("catalog_content_digest"),
                                     "capacity_bindings_sha256": run.version_bindings_sha256,
                                     "rules_version": run.rules_version})
        else:
            context_bindings["economics_policy_version"] = run.economics_version
        current["catalog_context"] = context_bindings
        _save(db, project, state)
        return {"profile": current, "readiness": readiness(current)}

    return router
