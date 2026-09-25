"""Catalog scoped Roboexpert comparison with optional, bounded AI and web research."""

from __future__ import annotations

import os
import json
import re
import threading
import time
from collections import defaultdict, deque
from decimal import Decimal
from typing import Any, Callable, Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from auth import AuthContext, require_csrf
from calculation_contracts import semantic_digest
from catalog_repository import CatalogPositionDTO, CatalogSnapshotDTO
from solution_assistant import search_web


VERSION = "roboexpert-comparison-v1"
MODEL = "deepseek-v4-flash"
SEARCH_DAY_RUB = Decimal("0.488")
SEARCH_PRICING_URL = "https://aistudio.yandex.ru/ru/docs/search-api/pricing"
MODEL_PRICING_URL = "https://yandex.cloud/ru/blog/yandex-ai-studio-deepseek-v4-flash"
SAFE_FACT_STATUSES = frozenset({
    "CORROBORATED", "CROSS_DOCUMENT_ENRICHED", "VERIFIED_OFFICIAL",
    "VERIFIED_AUTHORIZED_PARTNER", "MANUALLY_APPROVED",
})
NUMERIC_FACTS = frozenset({"payload", "max_speed", "min_aisle_width", "autonomy_hours"})
FIELD_LABELS = {"payload": "Грузоподъёмность", "max_speed": "Максимальная скорость",
                "min_aisle_width": "Минимальная ширина прохода", "autonomy_hours": "Автономность"}
SEARCH_TOPICS = {"passport": "технический паспорт pdf", "price": "цена коммерческое предложение",
                 "service": "сервис обслуживание", "availability": "поставка доступность"}
CSRF = Depends(require_csrf)


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position_ids: list[str] = Field(min_length=2, max_length=3)
    catalog_version: str = Field(min_length=1, max_length=100)


class SummaryRequest(ComparisonRequest):
    comparison_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position_id: str = Field(min_length=1, max_length=128)
    catalog_version: str = Field(min_length=1, max_length=100)
    topic: Literal["passport", "price", "service", "availability"]


class PilotLimiter:
    """Per-process guard. Provider billing remains the authoritative cost record."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, kind: str, subject: str, *, daily: int, minute: int) -> dict[str, int]:
        now = time.monotonic()
        with self.lock:
            for key, limit in (((kind, subject), daily), ((kind, "__global__"), min(daily * 20, 40))):
                hits = self.hits[key]
                while hits and hits[0] < now - 86400:
                    hits.popleft()
                if len(hits) >= limit or sum(stamp > now - 60 for stamp in hits) >= (minute if key[1] != "__global__" else minute * 20):
                    raise HTTPException(429, "Лимит вызовов Робоэксперта достигнут. Повторите позже.")
            self.hits[(kind, subject)].append(now)
            self.hits[(kind, "__global__")].append(now)
            return {"user_calls_today": len(self.hits[(kind, subject)]), "user_daily_limit": daily}


PILOT_LIMITER = PilotLimiter()


def class_key(position: CatalogPositionDTO) -> str:
    model = position.model
    runtime = model.capacity_runtime
    # A supported calculation profile defines the physical task; informational
    # records use their catalog type and cannot enter a numerical cohort.
    if runtime.calculation_ready and runtime.calculation_profile:
        return f"profile:{model.system_family}:{model.type_code}:{runtime.calculation_profile}"
    return f"information:{model.system_family}:{model.type_code}:{model.subtype_code or '-'}"


def information_reason(position: CatalogPositionDTO) -> str | None:
    if position.model.maturity_status == "RND":
        return "Исследовательская модель: готовность к внедрению не подтверждена."
    runtime = position.model.capacity_runtime
    if runtime.calculation_ready:
        return None
    if runtime.calculation_readiness_status == "NOT_EQUIPMENT":
        return "Информационное решение без расчёта потребного парка оборудования."
    if runtime.calculation_readiness_status == "UNSUPPORTED_CAPACITY_PROFILE":
        return "Для этой операции пока нет поддержанной формулы потребного парка."
    return "Для расчёта парка не хватает проверенных характеристик или поддержанной модели."


def options(snapshot: CatalogSnapshotDTO) -> dict[str, Any]:
    return {"schema_version": "roboexpert-options-v1", "catalog_version": snapshot.version.code,
            "catalog_digest": snapshot.version.content_sha256,
            "items": [{"position_id": item.id, "name": item.model.name,
                       "manufacturer": item.model.manufacturer, "type_code": item.model.type_code,
                       "class_key": class_key(item), "maturity_status": item.model.maturity_status,
                       "calculation_ready": item.model.capacity_runtime.calculation_ready,
                       "calculation_profile": item.model.capacity_runtime.calculation_profile,
                       "information_reason": information_reason(item)}
                      for item in sorted(snapshot.positions, key=lambda value: (value.model.name, value.id))]}


def _source(position: CatalogPositionDTO, evidence_id: str | None, catalog_version: str) -> dict[str, Any]:
    return {"catalog_version": catalog_version,
            "evidence_id": evidence_id if evidence_id not in {None, "", "None", "null"} else None,
            "card_url": f"/api/catalog/positions/{position.id}"}


def _fact(position: CatalogPositionDTO, code: str, catalog_version: str) -> dict[str, Any]:
    found = [item for item in position.model.facts if item.code == code]
    if not found:
        return {"status": "MISSING", "value": None, "unit": None, "confirmed": False,
                "source": _source(position, None, catalog_version)}
    if len({(str(item.value), item.canonical_unit) for item in found}) > 1:
        return {"status": "CONFLICT", "value": None, "unit": None, "confirmed": False,
                "source": _source(position, ", ".join(item.evidence_id for item in found if item.evidence_id), catalog_version)}
    fact = found[0]
    confirmed = all(item.resolution_status in SAFE_FACT_STATUSES
                    and item.evidence_id not in {None, "", "None", "null"} for item in found)
    return {"status": fact.resolution_status, "value": str(fact.value),
            "unit": fact.canonical_unit, "confirmed": confirmed,
            "source": _source(position, fact.evidence_id, catalog_version)}


def _price(position: CatalogPositionDTO, catalog_version: str) -> dict[str, Any]:
    value = position.procurement_option
    return {"status": value.price_status, "value": str(value.amount) if value.amount is not None else None,
            "unit": value.currency, "confirmed": value.amount is not None and value.currency == "RUB"
            and value.price_status == "NORMALIZED" and bool(value.evidence_id)
            and value.evidence_status in SAFE_FACT_STATUSES,
            "source": _source(position, value.evidence_id, catalog_version)}


def _finite_decimal(value: str | None) -> bool:
    try:
        return value is not None and Decimal(value).is_finite()
    except (ValueError, ArithmeticError):
        return False


def compare_catalog(snapshot: CatalogSnapshotDTO, payload: ComparisonRequest) -> dict[str, Any]:
    if payload.catalog_version != snapshot.version.code:
        raise HTTPException(409, "Активный каталог обновился. Загрузите Робоэксперт заново.")
    if len(set(payload.position_ids)) != len(payload.position_ids):
        raise HTTPException(422, "Выберите 2–3 разные позиции.")
    positions = {item.id: item for item in snapshot.positions}
    if any(item not in positions for item in payload.position_ids):
        raise HTTPException(422, "Позиция отсутствует в активном каталоге.")
    selected = [positions[item] for item in payload.position_ids]
    classes = {class_key(item) for item in selected}
    if len(classes) != 1 or any(not item.model.capacity_runtime.calculation_ready
                                or item.model.maturity_status == "RND" for item in selected):
        raise HTTPException(422, "Сравнение доступно для 2–3 расчётных позиций одного физического класса. Остальные смотрите как справочные карточки.")
    codes = sorted({fact.code for item in selected for fact in item.model.facts})
    criteria = []
    for code in codes:
        cells = [_fact(item, code, snapshot.version.code) for item in selected]
        units = {cell["unit"] for cell in cells if cell["value"] is not None}
        comparable = len(units) == 1 and all(cell["confirmed"] for cell in cells)
        criteria.append({"code": code, "label": FIELD_LABELS.get(code, code), "cells": cells,
                         "numeric_comparable": comparable and code in NUMERIC_FACTS
                         and all(_finite_decimal(cell["value"]) for cell in cells),
                         "unit_status": "SAME" if len(units) <= 1 else "DIFFERENT"})
    prices = [_price(item, snapshot.version.code) for item in selected]
    price_comparable = all(cell["confirmed"] for cell in prices) and len({cell["unit"] for cell in prices}) == 1
    price_best = None
    if price_comparable:
        price_best = selected[min(range(len(prices)), key=lambda index: Decimal(prices[index]["value"]))].id
    result = {
        "schema_version": VERSION, "catalog_version": snapshot.version.code,
        "catalog_digest": snapshot.version.content_sha256,
        "class_key": next(iter(classes)),
        "positions": [{"position_id": item.id, "name": item.model.name,
                       "manufacturer": item.model.manufacturer, "maturity_status": item.model.maturity_status,
                       "calculation_profile": item.model.capacity_runtime.calculation_profile,
                       "calculation_readiness_status": item.model.capacity_runtime.calculation_readiness_status,
                       "deployment_readiness_status": item.model.capacity_runtime.deployment_readiness_status,
                       "card_url": f"/api/catalog/positions/{item.id}"} for item in selected],
        "criteria": criteria, "price": {"cells": prices, "comparable": price_comparable,
                                         "lowest_position_id": price_best},
        "summary": {"advantages": [], "limitations": [], "verify_on_site": [
            "Проверьте массу и габариты груза, ширину маршрута, интеграции и условия эксплуатации.",
            "Запросите актуальный паспорт, цену, сервис и доступность у поставщика.",
        ]},
    }
    for item in criteria:
        if not item["numeric_comparable"]:
            result["summary"]["limitations"].append(f"{item['label']}: нет одинаково подтверждённых значений и единиц для всех позиций.")
        elif item["code"] in {"payload", "max_speed"}:
            try:
                values = [Decimal(cell["value"]) for cell in item["cells"]]
            except (ValueError, ArithmeticError):
                continue
            if len(set(values)) > 1:
                highest = max(range(len(values)), key=lambda index: values[index])
                result["summary"]["advantages"].append(
                    f"{item['label']}: наибольшее подтверждённое значение у "
                    f"{selected[highest].model.name} — {item['cells'][highest]['value']} {item['cells'][highest]['unit']}. "
                    "Это не вывод о пригодности на вашем объекте."
                )
    if not price_comparable:
        result["summary"]["limitations"].append("Подтверждённая сопоставимая цена отсутствует; вывод о дешевизне недоступен.")
    else:
        result["summary"]["advantages"].append(f"Минимальная подтверждённая цена среди выбранных: {next(item['name'] for item in result['positions'] if item['position_id'] == price_best)}. Это не сравнение полной стоимости владения.")
    result["comparison_digest"] = semantic_digest(result)
    return result


def _llm_summary(comparison: dict[str, Any], *, post: Callable[..., Any] = requests.post) -> dict[str, Any]:
    key, folder = os.getenv("YC_API_KEY"), os.getenv("YC_FOLDER_ID")
    if not key or not folder:
        return {"status": "UNAVAILABLE", "message": "AI Studio не настроен; структурированное сравнение доступно.", "usage": None}
    # The model receives catalog facts only. It cannot alter rankings or the catalog.
    facts = {key: comparison[key] for key in ("catalog_version", "positions", "criteria", "price", "summary")}
    prompt = ("Составь краткую русскую сводку о 2–3 роботах из JSON. Не вычисляй баллы и не утверждай пригодность. "
              "Пиши только о данных и ограничениях; неизвестные цены и паспорта обозначь явно. "
              "Не используй слова 'дешевле', 'прочнее', 'подходит'. Не добавляй фактов или веб-источников. "
              "Ответь JSON с единственным полем text, не более 1200 символов.")
    body = {"model": f"gpt://{folder}/{MODEL}", "messages": [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(facts, ensure_ascii=False, default=str)[:14000]},
    ], "response_format": {"type": "json_object"}, "max_tokens": 450, "temperature": 0.1, "stream": False}
    try:
        response = post("https://ai.api.cloud.yandex.net/v1/chat/completions", json=body,
                        headers={"Authorization": f"Api-Key {key}"}, timeout=30)
        response.raise_for_status()
        data = response.json()
        text = json.loads(data["choices"][0]["message"]["content"])["text"]
        if (not isinstance(text, str) or len(text) > 1200
                or re.search(r"дешевле|прочнее|подходит|рейтинг|балл\s*\d", text, re.IGNORECASE)):
            raise ValueError("unsafe model summary")
        usage = data.get("usage") or {}
        input_tokens, output_tokens = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        return {"status": "OK", "text": text, "model": MODEL, "usage": {
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "estimated_rub": round(input_tokens * 0.3 / 1000 + output_tokens * 0.5 / 1000, 4),
            "cost_note": "Оценка по пилотному тарифу, не сумма счёта провайдера.",
            "pricing_url": MODEL_PRICING_URL}}
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        return {"status": "UNAVAILABLE", "message": "AI Studio сейчас недоступен; структурированное сравнение сохранено.", "usage": None}


def create_roboexpert_router(load_snapshot: Callable[[], CatalogSnapshotDTO]) -> APIRouter:
    router = APIRouter(prefix="/api/roboexpert")

    @router.get("/options")
    def get_options():
        return options(load_snapshot())

    @router.post("/compare")
    def compare(payload: ComparisonRequest):
        return compare_catalog(load_snapshot(), payload)

    @router.post("/summary")
    def summary(payload: SummaryRequest, context: AuthContext = CSRF):
        comparison = compare_catalog(load_snapshot(), payload)
        if comparison["comparison_digest"] != payload.comparison_digest:
            raise HTTPException(409, "Сравнение изменилось. Обновите страницу.")
        limits = PILOT_LIMITER.check("ai", str(context.user.id), daily=5, minute=2)
        answer = _llm_summary(comparison)
        return {"source": "YANDEX_AI_STUDIO", "catalog_version": comparison["catalog_version"],
                "comparison_digest": payload.comparison_digest, "limits": limits, **answer}

    @router.post("/web")
    def web(payload: SearchRequest, context: AuthContext = CSRF):
        snapshot = load_snapshot()
        if payload.catalog_version != snapshot.version.code:
            raise HTTPException(409, "Активный каталог обновился. Загрузите Робоэксперт заново.")
        position = next((item for item in snapshot.positions if item.id == payload.position_id), None)
        if position is None:
            raise HTTPException(422, "Позиция отсутствует в активном каталоге.")
        limits = PILOT_LIMITER.check("web", str(context.user.id), daily=5, minute=2)
        query = f"{position.model.manufacturer or ''} {position.model.name} {SEARCH_TOPICS[payload.topic]}"[:300]
        result = search_web(query)
        return {"source": "YANDEX_SEARCH_API", "position_id": position.id, "topic": payload.topic,
                "catalog_version": snapshot.version.code, "verification_status": "REQUIRES_VERIFICATION",
                "searched_at": result["searched_at"], "status": result["status"],
                "results": result["results"], "message": result["message"], "limits": limits,
                "pricing_estimate": {"checked_on": "2026-09-26", "daytime_synchronous_request_rub": str(SEARCH_DAY_RUB),
                                     "global_daily_cap_rub": str(SEARCH_DAY_RUB * 40),
                                     "source_url": SEARCH_PRICING_URL},
                "cost_note": "Оценка по дневному тарифу; фактическую стоимость сверяйте со счётом Yandex Cloud."}

    return router
