"""Read-only, evidence-gated discovery selection; never changes runtime pools."""

from decimal import Decimal, InvalidOperation

from calculation.constraints import (
    CandidateConstraintFacts,
    ConstraintEvaluationRequest,
    ObjectConstraintContext,
    evaluate_constraints,
)
from calculation.process_profiles.catalog import load_process_profile_catalog
from pydantic import ValidationError
from roboexpert_api import SAFE_FACT_STATUSES

VERSION = "catalog-selection-v1"
CHECK_LABELS = {
    "object-kind": "Объект",
    "process-scope": "Процесс",
    "payload": "Масса груза",
    "aisle": "Ширина прохода",
    "cargo": "Тип груза",
    "integrations": "Интеграции",
    "passport-availability": "Технический паспорт",
    "availability": "Эксплуатационная доступность",
    "outdoor": "Работа вне помещения",
    "floor-flatness": "Ровность пола",
    "floor-covering": "Покрытие пола",
    "noise": "Шум",
    "sanitization": "Санитарная обработка",
}
REASON_LABELS = {
    "candidate-fact-missing": "нет подтверждённой характеристики",
    "requirement-exceeded": "подтверждённой характеристики недостаточно",
    "object-kind-unsupported": "не поддерживается",
    "process-scope-unsupported": "не поддерживается",
    "technical-passport-unknown": "не подтверждён",
    "availability-fact-unknown": "не подтверждена",
    "limit-exceeded": "превышен доступный предел",
}
OBJECTS = {
    "warehouse": ("склад", "внутрисклад"),
    "airport": ("аэропорт", "аэродром", "перрон"),
    "clinic": ("медицин", "клиник", "больниц", "здравоохран"),
}
# Industry alone is ambiguous: these mappings are discovery hints, never C05 evidence.
NUMERIC = {
    "payload": ("kg", {"kg": 1, "t": 1000}),
    "min_aisle_width": ("m", {"m": 1, "mm": 0.001, "cm": 0.01}),
    "max_speed": ("m/s", {"m/s": 1, "km/h": 1 / 3.6}),
}


def numeric_fact(item, code):
    values = []
    for fact in item.get("facts", []):
        if fact["code"] not in {
            code,
            {"payload": "payload_kg", "min_aisle_width": "min_aisle_width_m"}.get(
                code, code
            ),
        }:
            continue
        if fact.get("status") not in SAFE_FACT_STATUSES or not fact.get("evidence_id"):
            continue
        units = NUMERIC[code][1]
        if fact.get("unit") not in units:
            continue
        try:
            value = Decimal(str(fact["value"])) * Decimal(str(units[fact["unit"]]))
            if value.is_finite() and value >= 0:
                values.append((value, fact["evidence_id"]))
        except (InvalidOperation, ValueError, TypeError):
            pass
    return (
        values[0] if values and len({row[0] for row in values}) == 1 else (None, None)
    )


def annotate(item, object_kind=None, process_code=None, context=None):
    item = dict(item)
    text = " ".join(
        [
            *item.get("use_cases", []),
            *(a.get("case") or "" for a in item.get("applicability", [])),
        ]
    ).casefold()
    objects = [
        key for key, words in OBJECTS.items() if any(word in text for word in words)
    ]
    scope = {
        "TRANSPORT_CYCLE_V1": "TRANSPORT_CYCLE",
        "DELIVERY_CYCLE_V1": "DELIVERY_CYCLE",
        "CLEANING_AREA_V1": "CLEANING_AREA",
        "PALLETIZING_THROUGHPUT_V1": "FIXED_CELL",
    }.get(item.get("calculation_profile"))
    hints = []
    if any(word in text for word in ("уборк", "очистк", "клининг")):
        hints.append("CLEANING_AREA")
    if any(word in text for word in ("логист", "транспорт", "доставк", "перемещ")):
        hints.extend(["TRANSPORT_CYCLE", "DELIVERY_CYCLE"])
    if "паллетизац" in text:
        hints.append("FIXED_CELL")
    if scope:
        hints.append(scope)
        if scope == "TRANSPORT_CYCLE":
            hints.append("DELIVERY_CYCLE")
    item["taxonomy"] = {
        "version": VERSION,
        "objects": objects,
        "process_scopes": sorted(set(hints)),
        "status": "MAPPED_HINT" if objects else "UNKNOWN",
        "source": "catalog applicability; discovery hint only",
    }
    item["normalized_specs"] = {
        code: {
            "value": str(value) if value is not None else None,
            "unit": NUMERIC[code][0],
            "source": source,
        }
        for code in NUMERIC
        for value, source in [numeric_fact(item, code)]
    }
    item["data_quality"] = (
        "verified"
        if any(v["value"] is not None for v in item["normalized_specs"].values())
        else "unknown"
    )
    item["selection"] = {
        "status": "REQUIRES_CHECK",
        "reasons": ["Контекст не задан; пригодность требует обследования"],
        "checks": [],
    }
    if not object_kind:
        return item
    reasons = []
    excluded = bool(objects and object_kind not in objects)
    if excluded:
        reasons.append("Применимость указана для другого объекта")
    elif not objects:
        reasons.append("Применимость к объекту неизвестна")
    profile = next(
        (
            p
            for p in load_process_profile_catalog().profiles
            if p.process_code == process_code
        ),
        None,
    )
    if profile:
        if hints and profile.scope not in hints:
            excluded = True
            reasons.append("Другой физический процесс")
        fields, evidence = {}, {}
        for code, target in (
            ("payload", "payload_kg"),
            ("min_aisle_width", "min_aisle_width_m"),
        ):
            fact = item["normalized_specs"][code]
            if fact["value"] is not None:
                fields[target] = fact["value"]
                evidence[target] = {
                    "evidence_status": "MATCHING_SAFE",
                    "source_ref": fact["source"],
                }
        # Only exact, evidence-backed capability fields. No inference from descriptions.
        for fact in item.get("facts", []):
            name = fact["code"]
            if (
                name
                in {
                    "supported_object_kinds",
                    "supported_process_scopes",
                    "supported_cargo_kinds",
                    "supported_integrations",
                    "outdoor_supported",
                    "technical_passport_available",
                    "sterilization_supported",
                    "class_b_containment_supported",
                    "supported_access_protocols",
                    "supported_floor_coverings",
                    "lift_protocols",
                }
                and fact.get("status") in SAFE_FACT_STATUSES
                and fact.get("evidence_id")
            ):
                fields[name] = fact["value"]
                evidence[name] = {
                    "evidence_status": "MATCHING_SAFE",
                    "source_ref": fact["evidence_id"],
                }
        # Applicability hints cannot become confirmed object/process facts.
        # Malformed capability values remain unknown rather than breaking discovery.
        for name in list(fields):
            try:
                CandidateConstraintFacts(
                    model_id=item["model_id"],
                    position_id=item["position_id"],
                    **{name: fields[name]},
                )
            except ValidationError:
                del fields[name]
                evidence.pop(name, None)
        report = evaluate_constraints(
            ConstraintEvaluationRequest(
                input_revision="catalog.selection.v1",
                process_id="catalog.selection.process",
                process_code=profile.process_code,
                process_scope=profile.scope,
                context=ObjectConstraintContext(
                    object_kind=object_kind.upper(), **(context or {})
                ),
                candidate=CandidateConstraintFacts(
                    model_id=item["model_id"],
                    position_id=item["position_id"],
                    evidence=evidence,
                    **fields,
                ),
            )
        )
        checks = [
            c.model_dump(mode="json")
            for c in report.checks
            if c.applicable and c.status != "N_A"
        ]
        excluded |= report.eligibility == "BLOCKED"
        reasons.extend(
            f"{CHECK_LABELS.get(c['check_id'], c['check_id'])}: {REASON_LABELS.get(c['reason_code'], c['reason_code'])}"
            for c in checks
            if c["status"] in {"FAIL", "UNKNOWN"}
        )
        item["selection"]["checks"] = checks
        item["selection"]["rules_version"] = report.rules_version
    included = bool(
        profile
        and report.eligibility == "ELIGIBLE"
        and objects
        and object_kind in objects
    )
    item["selection"].update(
        status="EXCLUDED" if excluded else "INCLUDED" if included else "REQUIRES_CHECK",
        reasons=reasons
        or [
            "Проверки C05 пройдены; закупочные условия проверяются отдельно"
            if included
            else "Требуется проверка паспорта и условий объекта"
        ],
    )
    item["selection"]["calculation_compatible"] = bool(
        profile
        and item.get("calculation_ready")
        and (scope == profile.scope or
             profile.scope == "DELIVERY_CYCLE" and scope == "TRANSPORT_CYCLE")
        and not excluded
        and item.get("maturity_status") != "RND"
    )
    return item


def filter_items(
    items,
    *,
    q=None,
    system_family=None,
    type_code=None,
    manufacturer=None,
    selectable=None,
    calculation_participation="all",
    sort="name",
    object_kind=None,
    process_code=None,
    maturity=None,
    quality=None,
    include_unknown=False,
    availability=None,
    price_min=None,
    price_max=None,
    payload_min=None,
    payload_max=None,
    aisle_max=None,
    context=None,
):
    result = []
    for original in items:
        item = annotate(original, object_kind, process_code, context)
        if (
            q
            and q.strip().casefold()
            not in " ".join(
                str(v or "")
                for v in [
                    item.get("name"),
                    item.get("manufacturer"),
                    item.get("type_code"),
                    item.get("subtype_code"),
                    item.get("description"),
                    item.get("source_record_key"),
                    *item.get("industries", []),
                    *item.get("use_cases", []),
                    *item.get("regions", []),
                    *(a.get("case") for a in item.get("applicability", [])),
                ]
            ).casefold()
        ):
            continue
        if any(
            value
            and (
                item.get(key) is not None
                if value == "__unknown"
                else item.get(key) != value
            )
            for key, value in (
                ("system_family", system_family),
                ("type_code", type_code),
                ("manufacturer", manufacturer),
                ("maturity_status", maturity),
                ("data_quality", quality),
            )
        ):
            continue
        if availability:
            actual = item.get("admin_metadata", {}).get("availability")
            if actual in {"UNKNOWN", ""}:
                actual = None
            if (availability == "unknown" and actual is not None) or (
                availability != "unknown" and actual != availability
            ):
                continue
        if selectable is not None and item.get("selectable") != selectable:
            continue
        if calculation_participation != "all" and item.get("calculation_ready") != (
            calculation_participation == "participating"
        ):
            continue
        tax = item["taxonomy"]
        if (
            object_kind
            and object_kind not in tax["objects"]
            and not (include_unknown and not tax["objects"])
        ):
            continue
        profile = next(
            (
                p
                for p in load_process_profile_catalog().profiles
                if p.process_code == process_code
            ),
            None,
        )
        if (
            profile
            and profile.scope not in tax["process_scopes"]
            and not (include_unknown and not tax["process_scopes"])
        ):
            continue
        missing = False
        purchase = item.get("purchase") or {}
        price = (
            purchase.get("amount")
            if purchase.get("currency") == "RUB"
            and purchase.get("price_status") == "NORMALIZED"
            else None
        )
        for value, low, high in (
            (price, price_min, price_max),
            (item["normalized_specs"]["payload"]["value"], payload_min, payload_max),
            (item["normalized_specs"]["min_aisle_width"]["value"], None, aisle_max),
        ):
            if low is None and high is None:
                continue
            if value is None:
                if not include_unknown:
                    missing = True
            elif (low is not None and Decimal(str(value)) < Decimal(str(low))) or (
                high is not None and Decimal(str(value)) > Decimal(str(high))
            ):
                missing = True
        if not missing:
            result.append(item)
    key = {"name": "name", "manufacturer": "manufacturer", "type": "type_code"}[sort]
    return sorted(
        result,
        key=lambda item: (
            str(item.get(key) or "").casefold(),
            item.get("name", "").casefold(),
            item.get("source_row_number", 0),
        ),
    )
