"""Deterministic process readiness, architecture and hard-constraint engine.

This module deliberately does not size a fleet or calculate economics.  It
keeps process readiness separate from the hard technical gates used for an
individual catalog candidate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from models import UserInput


CheckStatus = Literal["PASS", "FAIL", "UNKNOWN", "ASSUMED"]
OverallStatus = Literal["READY", "NEEDS_VALIDATION", "NOT_READY"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadinessRequest(StrictModel):
    input: UserInput
    provenance: dict[str, Any] = Field(default_factory=dict)
    parameter_values: dict[str, Any] = Field(default_factory=dict)
    parameter_provenance: dict[str, Any] = Field(default_factory=dict)


class ValueRef(StrictModel):
    value: Any
    unit: str | None = None


class EvidenceRef(StrictModel):
    kind: Literal["USER", "FILE", "PRESET", "CALCULATED", "CATALOG", "ASSUMPTION"]
    field: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)


class ConstraintResult(StrictModel):
    code: str
    label: str
    dimension: str
    critical: bool
    required: ValueRef | None = None
    available: ValueRef | None = None
    status: CheckStatus
    reason_code: str
    explanation: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ReadinessDimension(StrictModel):
    code: str
    label: str
    status: CheckStatus
    score: int = Field(ge=0, le=100)
    checks: list[ConstraintResult]


class ArchitectureCandidate(StrictModel):
    architecture_id: Literal[
        "PALLET_TRANSPORT_AMR",
        "FIXED_PATH_AGV",
        "AUTONOMOUS_FORKLIFT",
        "TUGGER_TRAIN",
        "PARTIAL_AUTOMATION",
        "AUTONOMOUS_CLEANING",
        "INDOOR_DELIVERY_AMR",
        "NOT_READY",
    ]
    fit_score: int = Field(ge=0, le=100)
    status: Literal["RECOMMENDED", "POSSIBLE", "NEEDS_VALIDATION", "BLOCKED"]
    reason_codes: list[str]
    preconditions: list[str] = Field(default_factory=list)


class TechnicalCandidate(StrictModel):
    equipment_model_id: str
    equipment_model_name: str
    status: Literal["ELIGIBLE", "NEEDS_VALIDATION", "REJECTED"]
    hard_constraints: list[ConstraintResult]
    critical_unknowns: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


class ReadinessReport(StrictModel):
    schema_version: Literal["readiness-report-v1"] = "readiness-report-v1"
    rules_version: Literal["readiness-rules-v1"] = "readiness-rules-v1"
    overall_status: OverallStatus
    score: int = Field(ge=0, le=100)
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    dimensions: list[ReadinessDimension]
    blockers: list[str]
    preconditions: list[str]
    architecture_candidates: list[ArchitectureCandidate]
    technical_candidates: list[TechnicalCandidate]


_DIMENSION_LABELS = {
    "PROCESS": "Стандартизация процесса",
    "ENVIRONMENT": "Физическая среда",
    "INFRASTRUCTURE": "Инфраструктура и интеграции",
    "SAFETY": "Безопасность и эксплуатация",
    "ECONOMICS": "Экономический потенциал",
    "EVIDENCE": "Полнота подтверждений",
}
_STATUS_RANK = {"PASS": 0, "ASSUMED": 1, "UNKNOWN": 2, "FAIL": 3}
_STATUS_SCORE = {"PASS": 100, "ASSUMED": 50, "UNKNOWN": 0, "FAIL": 0}


def _value(value: Any, unit: str | None = None) -> ValueRef:
    return ValueRef(value=value, unit=unit)


def _provenance(
    field: str,
    provenance: Mapping[str, Any],
    *,
    fallback_kind: Literal["USER", "ASSUMPTION"] = "USER",
) -> EvidenceRef:
    raw = provenance.get(field)
    if isinstance(raw, Mapping):
        raw_kind = str(raw.get("kind", fallback_kind)).upper()
        kind = raw_kind if raw_kind in {
            "USER", "FILE", "PRESET", "CALCULATED", "CATALOG", "ASSUMPTION"
        } else fallback_kind
        source = raw.get("source") if isinstance(raw.get("source"), Mapping) else {}
        return EvidenceRef(kind=kind, field=field, source=dict(source))
    return EvidenceRef(kind=fallback_kind, field=field)


def _check(
    *,
    code: str,
    label: str,
    dimension: str,
    critical: bool,
    status: CheckStatus,
    reason_code: str,
    explanation: str,
    required: ValueRef | None = None,
    available: ValueRef | None = None,
    evidence: Iterable[EvidenceRef] = (),
) -> ConstraintResult:
    return ConstraintResult(
        code=code,
        label=label,
        dimension=dimension,
        critical=critical,
        required=required,
        available=available,
        status=status,
        reason_code=reason_code,
        explanation=explanation,
        evidence=list(evidence),
    )


def _contexts(inp: UserInput) -> list[Any]:
    return list(inp.zones) if inp.mode == "zonal" and inp.zones else [inp]


def _all_values(inp: UserInput, field: str) -> list[Any]:
    return [getattr(item, field, None) for item in _contexts(inp)]


def _process_checks(inp: UserInput, provenance: Mapping[str, Any]) -> list[ConstraintResult]:
    contexts = _contexts(inp)
    volume_field = "area_m2" if all(item.process_type == "cleaning" for item in contexts) else "volume_per_day" if inp.mode == "zonal" else "pallets_per_day"
    volumes = _all_values(inp, volume_field)
    volume_known = all(value is not None for value in volumes)
    shifts = _all_values(inp, "shifts_count")
    hours = _all_values(inp, "shift_hours")
    schedule_known = all(value is not None for value in [*shifts, *hours])
    schedule_invalid = schedule_known and any(
        shifts[index] * hours[index] > 24 for index in range(len(contexts))
    )
    schedule_value = (
        [{"shifts": shifts[i] or 2, "hours": hours[i] or 8} for i in range(len(contexts))]
        if len(contexts) > 1
        else {"shifts": shifts[0] or 2, "hours": hours[0] or 8}
    )
    return [
        _check(
            code="PROCESS_DEFINED", label="Тип процесса и груза", dimension="PROCESS",
            critical=True, status="PASS", reason_code="PROCESS_AND_CARGO_PROVIDED",
            explanation="Тип процесса и обрабатываемого груза определён.",
            available=_value([{"process": item.process_type, "cargo": item.cargo_type} for item in contexts]),
            evidence=[_provenance("process_type", provenance), _provenance("cargo_type", provenance)],
        ),
        _check(
            code="PROCESS_VOLUME", label="Объём процесса", dimension="PROCESS",
            critical=True, status="PASS" if volume_known else "UNKNOWN",
            reason_code="PROCESS_VOLUME_PROVIDED" if volume_known else "PROCESS_VOLUME_MISSING",
            explanation="Объём процесса подтверждён." if volume_known else "Нужен объём процесса для проверки применимости и последующего сайзинга.",
            required=_value("provided"), available=_value(volumes) if volume_known else None,
            evidence=[_provenance(volume_field, provenance)] if volume_known else [],
        ),
        _check(
            code="OPERATING_SCHEDULE", label="Рабочий график", dimension="PROCESS",
            critical=schedule_invalid,
            status="FAIL" if schedule_invalid else "PASS" if schedule_known else "ASSUMED",
            reason_code="OPERATING_WINDOW_EXCEEDS_DAY" if schedule_invalid else "OPERATING_SCHEDULE_PROVIDED" if schedule_known else "DEFAULT_OPERATING_SCHEDULE",
            explanation=(
                "Суммарная длительность смен превышает 24 часа."
                if schedule_invalid else
                "Рабочий график подтверждён."
                if schedule_known else
                "Для предварительной оценки принято 2 смены по 8 часов; подтвердите график."
            ),
            available=_value(schedule_value),
            evidence=(
                [_provenance("shifts_count", provenance), _provenance("shift_hours", provenance)]
                if schedule_known else [EvidenceRef(kind="ASSUMPTION", field="operating_schedule", source={"shifts": 2, "hours": 8})]
            ),
        ),
    ]


def _environment_checks(inp: UserInput, provenance: Mapping[str, Any]) -> list[ConstraintResult]:
    contexts = _contexts(inp)
    mobile = any(item.process_type in {"transport", "cleaning", "delivery"} for item in contexts)
    payload_relevant = any(item.process_type in {"transport", "palletizing", "delivery"} for item in contexts)
    aisles = _all_values(inp, "aisle_width_m")
    payloads = _all_values(inp, "payload_kg")
    aisle_known = all(value is not None for value in aisles)
    payload_known = all(value is not None for value in payloads)
    checks = []
    if mobile:
        checks.append(_check(
            code="AISLE_GEOMETRY", label="Минимальная ширина прохода", dimension="ENVIRONMENT",
            critical=True, status="PASS" if aisle_known else "UNKNOWN",
            reason_code="AISLE_WIDTH_PROVIDED" if aisle_known else "AISLE_WIDTH_MISSING",
            explanation="Геометрия проходов задана." if aisle_known else "Измерьте самое узкое место маршрута; критическую геометрию нельзя подменять значением по умолчанию.",
            required=_value("provided", "m"), available=_value(min(aisles), "m") if aisle_known else None,
            evidence=[_provenance("aisle_width_m", provenance)] if aisle_known else [],
        ))
    if payload_relevant:
        checks.append(_check(
            code="CARGO_PAYLOAD", label="Максимальная масса груза", dimension="ENVIRONMENT",
            critical=True, status="PASS" if payload_known else "UNKNOWN",
            reason_code="PAYLOAD_PROVIDED" if payload_known else "PAYLOAD_MISSING",
            explanation="Масса груза задана." if payload_known else "Подтвердите максимальную массу единицы груза вместе с оснасткой.",
            required=_value("provided", "kg"), available=_value(max(payloads), "kg") if payload_known else None,
            evidence=[_provenance("payload_kg", provenance)] if payload_known else [],
        ))
    return checks


def _supporting_checks(
    inp: UserInput,
    provenance: Mapping[str, Any],
    parameter_values: Mapping[str, Any],
    parameter_provenance: Mapping[str, Any],
) -> list[ConstraintResult]:
    integration_fields = [
        "nalichie_wms", "nalichie_fids_aodb_sistemy",
        "nalichie_mis_medicinskaya_informacionnaya_sistema",
    ]
    integration_field = next((key for key in integration_fields if key in parameter_values), None)
    charging_fields = [
        "moschnost_elektrosnabzheniya_dostupnaya",
        "dostupnaya_moschnost_dlya_zaryadnoy_infrastruktury",
    ]
    charging_field = next((key for key in charging_fields if key in parameter_values), None)
    staff_known = inp.staff_headcount is not None
    cost_known = inp.fte_cost_rub is not None

    def parameter_evidence(field: str | None) -> list[EvidenceRef]:
        if field is None:
            return []
        return [_provenance(field, parameter_provenance, fallback_kind="USER")]

    return [
        _check(
            code="CHARGING_POWER", label="Мощность для зарядной инфраструктуры", dimension="INFRASTRUCTURE",
            critical=False, status="PASS" if charging_field else "UNKNOWN",
            reason_code="CHARGING_POWER_PROVIDED" if charging_field else "CHARGING_POWER_MISSING",
            explanation="Доступная мощность указана в профиле объекта." if charging_field else "Проверьте доступную мощность и места зарядки на обследовании.",
            available=_value(parameter_values[charging_field], "kW") if charging_field else None,
            evidence=parameter_evidence(charging_field),
        ),
        _check(
            code="IT_INTEGRATION", label="Система управления объектом", dimension="INFRASTRUCTURE",
            critical=False, status="PASS" if integration_field else "UNKNOWN",
            reason_code="INTEGRATION_SYSTEM_PROVIDED" if integration_field else "INTEGRATION_SYSTEM_UNKNOWN",
            explanation="Интеграционная система указана." if integration_field else "Нужно определить WMS/FIDS/МИС и доступность API.",
            available=_value(parameter_values[integration_field]) if integration_field else None,
            evidence=parameter_evidence(integration_field),
        ),
        _check(
            code="SAFETY_SURVEY", label="Обследование безопасности маршрута", dimension="SAFETY",
            critical=False, status="UNKNOWN", reason_code="SAFETY_SURVEY_REQUIRED",
            explanation="До пилота нужны карта потоков людей, опасных зон и процедура аварийной остановки.",
        ),
        _check(
            code="LABOR_BASELINE", label="Штат и стоимость труда", dimension="ECONOMICS",
            critical=False, status="PASS" if staff_known and cost_known else "UNKNOWN",
            reason_code="LABOR_BASELINE_PROVIDED" if staff_known and cost_known else "LABOR_BASELINE_INCOMPLETE",
            explanation="Экономический baseline задан." if staff_known and cost_known else "Для экономики подтвердите численность и полную стоимость FTE.",
            available=_value({"staff": inp.staff_headcount, "fte_cost_rub_year": inp.fte_cost_rub}) if staff_known or cost_known else None,
            evidence=[_provenance(field, provenance) for field in ("staff_headcount", "fte_cost_rub") if getattr(inp, field) is not None],
        ),
    ]


def _dimensions(checks: list[ConstraintResult]) -> list[ReadinessDimension]:
    result = []
    for code, label in _DIMENSION_LABELS.items():
        own = [item for item in checks if item.dimension == code]
        if not own:
            continue
        status = max((item.status for item in own), key=_STATUS_RANK.__getitem__)
        score = round(sum(_STATUS_SCORE[item.status] for item in own) / len(own))
        result.append(ReadinessDimension(code=code, label=label, status=status, score=score, checks=own))
    return result


def _architectures(inp: UserInput, overall: OverallStatus, preconditions: list[str]) -> list[ArchitectureCandidate]:
    pairs = {(item.process_type, item.cargo_type) for item in _contexts(inp)}
    choices: list[tuple[str, int, list[str]]] = []
    if any(process == "transport" and cargo in {"pallets", "boxes"} for process, cargo in pairs):
        choices.extend([
            ("PALLET_TRANSPORT_AMR", 92, ["REPETITIVE_INTERNAL_TRANSPORT", "FLEXIBLE_ROUTE"]),
            ("FIXED_PATH_AGV", 76, ["REPETITIVE_INTERNAL_TRANSPORT", "STABLE_ROUTE"]),
        ])
        if any(cargo == "pallets" for _, cargo in pairs):
            choices.append(("AUTONOMOUS_FORKLIFT", 72, ["PALLET_LOAD", "FORK_INTERFACE_REQUIRED"]))
    if any(process == "transport" and cargo == "carts" for process, cargo in pairs):
        choices.extend([
            ("TUGGER_TRAIN", 90, ["CART_TRAIN", "REPETITIVE_INTERNAL_TRANSPORT"]),
            ("FIXED_PATH_AGV", 70, ["CART_TRAIN", "STABLE_ROUTE"]),
        ])
    if any(process == "palletizing" for process, _ in pairs):
        choices.append(("PARTIAL_AUTOMATION", 88, ["FIXED_OPERATION", "PALLETIZING_CELL"]))
    if any(process == "cleaning" for process, _ in pairs):
        choices.append(("AUTONOMOUS_CLEANING", 90, ["REPETITIVE_AREA_COVERAGE"]))
    if any(process == "delivery" for process, _ in pairs):
        choices.append(("INDOOR_DELIVERY_AMR", 90, ["INDOOR_POINT_TO_POINT_DELIVERY"]))
    if not choices:
        choices.append(("NOT_READY", 0, ["NO_ARCHITECTURE_RULE"]))

    result = []
    for index, (architecture_id, score, reasons) in enumerate(choices):
        if overall == "NOT_READY" or architecture_id == "NOT_READY":
            status = "BLOCKED"
        elif overall == "NEEDS_VALIDATION":
            status = "NEEDS_VALIDATION"
        else:
            status = "RECOMMENDED" if index == 0 else "POSSIBLE"
        result.append(ArchitectureCandidate(
            architecture_id=architecture_id,
            fit_score=score,
            status=status,
            reason_codes=reasons,
            preconditions=preconditions if status in {"NEEDS_VALIDATION", "BLOCKED"} else [],
        ))
    return result


def evaluate_equipment_constraints(
    inp: UserInput,
    robot: Mapping[str, Any],
    provenance: Mapping[str, Any] | None = None,
    *,
    catalog_version: str = "unversioned-test-input",
) -> TechnicalCandidate:
    """Evaluate candidate facts without filling missing critical requirements."""

    provenance = provenance or {}
    contexts = _contexts(inp)
    specs = robot.get("specs") or {}
    catalog_evidence = EvidenceRef(
        kind="CATALOG", field=None,
        source={"catalog_version": catalog_version, "equipment_model_id": robot.get("id")},
    )
    checks: list[ConstraintResult] = []
    object_ok = all(inp.object_type in robot.get("object_types", []) for _ in contexts)
    checks.append(_check(
        code="OBJECT_TYPE", label="Тип объекта", dimension="ENVIRONMENT", critical=True,
        status="PASS" if object_ok else "FAIL",
        reason_code="OBJECT_TYPE_COMPATIBLE" if object_ok else "OBJECT_TYPE_INCOMPATIBLE",
        explanation="Модель допускает этот тип объекта." if object_ok else "Модель не предназначена для выбранного типа объекта.",
        required=_value(inp.object_type), available=_value(robot.get("object_types", [])), evidence=[catalog_evidence],
    ))

    category = robot.get("category")
    compatibility = {
        "aerial": set(),
        "fixed_cell": {"palletizing"},
        "cleaning_robot": {"cleaning"},
        "service_delivery": {"delivery"},
        "internal_mobile": {"transport"},
    }.get(category, {"transport"})
    processes = {item.process_type for item in contexts}
    process_ok = processes.issubset(compatibility)
    checks.append(_check(
        code="PROCESS_COMPATIBILITY", label="Совместимость с процессом", dimension="PROCESS", critical=True,
        status="PASS" if process_ok else "FAIL",
        reason_code="PROCESS_COMPATIBLE" if process_ok else "PROCESS_INCOMPATIBLE",
        explanation="Класс оборудования соответствует процессу." if process_ok else "Класс оборудования не выполняет выбранный процесс.",
        required=_value(sorted(processes)), available=_value(sorted(compatibility)), evidence=[catalog_evidence],
    ))

    if category in {"internal_mobile", "service_delivery"}:
        required_cargo = {item.cargo_type for item in contexts}
        available_cargo = set(robot.get("compatible_cargo") or [])
        cargo_ok = required_cargo.issubset(available_cargo)
        checks.append(_check(
            code="CARGO_COMPATIBILITY", label="Тип груза", dimension="ENVIRONMENT", critical=True,
            status="PASS" if cargo_ok else "FAIL",
            reason_code="CARGO_COMPATIBLE" if cargo_ok else "CARGO_INCOMPATIBLE",
            explanation="Оснастка совместима с типом груза." if cargo_ok else "Каталожная совместимость с выбранным типом груза не подтверждена.",
            required=_value(sorted(required_cargo)), available=_value(sorted(available_cargo)), evidence=[catalog_evidence],
        ))

    payload_relevant = any(item.process_type in {"transport", "palletizing", "delivery"} for item in contexts)
    if payload_relevant:
        values = _all_values(inp, "payload_kg")
        known = all(value is not None for value in values)
        required = max(values) if known else None
        available = specs.get("payload_kg")
        status: CheckStatus = "UNKNOWN" if required is None or available is None else "PASS" if required <= available else "FAIL"
        checks.append(_check(
            code="PAYLOAD", label="Грузоподъёмность", dimension="ENVIRONMENT", critical=True,
            status=status,
            reason_code={"PASS": "PAYLOAD_SUFFICIENT", "FAIL": "PAYLOAD_EXCEEDED", "UNKNOWN": "PAYLOAD_REQUIREMENT_MISSING"}[status],
            explanation={"PASS": "Грузоподъёмность достаточна.", "FAIL": "Требуемая масса выше грузоподъёмности модели.", "UNKNOWN": "Масса груза не подтверждена; модель нельзя автоматически рекомендовать."}[status],
            required=_value(required, "kg") if required is not None else None,
            available=_value(available, "kg") if available is not None else None,
            evidence=([_provenance("payload_kg", provenance)] if required is not None else []) + ([catalog_evidence] if available is not None else []),
        ))

    mobile = category in {"internal_mobile", "cleaning_robot", "service_delivery"}
    if mobile:
        values = _all_values(inp, "aisle_width_m")
        known = all(value is not None for value in values)
        required = min(values) if known else None
        available = specs.get("min_aisle_width_m")
        status = "UNKNOWN" if required is None or available is None else "PASS" if required >= available else "FAIL"
        checks.append(_check(
            code="AISLE_WIDTH", label="Ширина прохода", dimension="ENVIRONMENT", critical=True,
            status=status,
            reason_code={"PASS": "AISLE_WIDTH_SUFFICIENT", "FAIL": "AISLE_TOO_NARROW", "UNKNOWN": "AISLE_WIDTH_REQUIREMENT_MISSING"}[status],
            explanation={"PASS": "Минимальный проход достаточен.", "FAIL": "Проход уже минимально допустимого для модели.", "UNKNOWN": "Ширина узкого места не подтверждена; модель нельзя автоматически рекомендовать."}[status],
            required=_value(required, "m") if required is not None else None,
            available=_value(available, "m") if available is not None else None,
            evidence=([_provenance("aisle_width_m", provenance)] if required is not None else []) + ([catalog_evidence] if available is not None else []),
        ))

    failures = [item for item in checks if item.critical and item.status == "FAIL"]
    unknowns = [item for item in checks if item.critical and item.status in {"UNKNOWN", "ASSUMED"}]
    status = "REJECTED" if failures else "NEEDS_VALIDATION" if unknowns else "ELIGIBLE"
    return TechnicalCandidate(
        equipment_model_id=str(robot.get("id")),
        equipment_model_name=str(robot.get("name")),
        status=status,
        hard_constraints=checks,
        critical_unknowns=[item.code for item in unknowns],
        rejection_reasons=[item.reason_code for item in failures],
    )


def evaluate_readiness(
    inp: UserInput,
    robots: Iterable[Mapping[str, Any]],
    *,
    provenance: Mapping[str, Any] | None = None,
    parameter_values: Mapping[str, Any] | None = None,
    parameter_provenance: Mapping[str, Any] | None = None,
    catalog_version: str = "unversioned-test-input",
) -> ReadinessReport:
    provenance = provenance or {}
    parameter_values = parameter_values or {}
    parameter_provenance = parameter_provenance or {}
    checks = [
        *_process_checks(inp, provenance),
        *_environment_checks(inp, provenance),
        *_supporting_checks(inp, provenance, parameter_values, parameter_provenance),
    ]
    critical_failures = [item for item in checks if item.critical and item.status == "FAIL"]
    critical_unknowns = [item for item in checks if item.critical and item.status in {"UNKNOWN", "ASSUMED"}]
    overall: OverallStatus = "NOT_READY" if critical_failures else "NEEDS_VALIDATION" if critical_unknowns else "READY"
    blockers = [item.explanation for item in critical_failures]
    preconditions = [item.explanation for item in checks if item.status in {"UNKNOWN", "ASSUMED"}]
    score = round(sum(_STATUS_SCORE[item.status] for item in checks) / len(checks)) if checks else 0
    known = sum(item.status in {"PASS", "FAIL"} for item in checks)
    confidence = "HIGH" if known / len(checks) >= 0.8 else "MEDIUM" if known / len(checks) >= 0.55 else "LOW"
    technical = [
        evaluate_equipment_constraints(
            inp, robot, provenance, catalog_version=catalog_version
        )
        for robot in robots
    ]
    return ReadinessReport(
        overall_status=overall,
        score=score,
        confidence=confidence,
        dimensions=_dimensions(checks),
        blockers=blockers,
        preconditions=preconditions,
        architecture_candidates=_architectures(inp, overall, preconditions),
        technical_candidates=technical,
    )
