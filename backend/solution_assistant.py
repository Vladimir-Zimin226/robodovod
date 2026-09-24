"""Version-scoped, evidence-first solution discovery and explicit web lookup."""

from __future__ import annotations

import base64
import binascii
import os
import re
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

import requests
from auth import CSRF_COOKIE, require_auth_context
from catalog_repository import CatalogPositionDTO, CatalogSnapshotDTO
from database import database_session
from fastapi import APIRouter, Depends, HTTPException, Request
from persistence_models import Project
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session


WEB_SEARCH_URL = "https://searchapi.api.cloud.yandex.net/v2/web/search"
_WORD = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
_STOP = {"для", "что", "как", "это", "или", "при", "нужен", "нужна", "нужно", "робот", "роботы", "решение", "сравни", "найди", "подбери", "склад", "работы", "работу"}
_SYNONYMS = {
    "паллет": "паллет", "поддон": "паллет", "поддонов": "паллет", "паллеты": "паллет",
    "уборка": "уборк", "убирать": "уборк", "очистка": "уборк",
    "доставка": "достав", "доставить": "достав", "перевозка": "транспорт",
    "транспортировка": "транспорт", "перемещение": "транспорт",
}
_LIMITS = ("огранич", "не поддерж", "не подходит", "требует", "невозмож", "запрещ")


class AssistantRequest(BaseModel):
    message: str = Field(min_length=3, max_length=400)
    history: list[str] = Field(default_factory=list, max_length=6)
    project_id: uuid.UUID | None = None
    compare_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)


class WebSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    project_id: uuid.UUID | None = None


class _WindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, kind: str, subject: str, limit: int) -> None:
        now = time.monotonic()
        key = (kind, subject)
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < now - 60:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(429, "Слишком много запросов. Повторите через минуту.")
            hits.append(now)


_LIMITER = _WindowLimiter()


def _tokens(value: str) -> set[str]:
    result = set()
    for word in _WORD.findall(value.casefold()):
        if word in _STOP or len(word) < 3:
            continue
        result.add(_SYNONYMS.get(word, word[:5] if len(word) >= 6 else word))
    return result


def _short(value: str | None, size: int = 520) -> str | None:
    if not value:
        return None
    return " ".join(value.split())[:size]


def _card(position: CatalogPositionDTO, catalog_code: str) -> dict[str, Any]:
    model = position.model
    media = position.media
    source_name = media.source_name if media else position.source_name
    source_date = media.source_observed_on if media else position.source_observed_on
    use = _short(position.applicability.scenario or position.applicability.case_text)
    description = _short(model.description)
    limits_text = " ".join(value for value in (position.applicability.case_text, model.description) if value)
    limits = _short(limits_text if any(term in limits_text.casefold() for term in _LIMITS) else None)
    return {
        "id": position.id,
        "name": model.name,
        "manufacturer": model.manufacturer,
        "family": model.system_family,
        "type": model.type_code,
        "use": use,
        "description": description,
        "limits": limits,
        "facts": [
            {"code": fact.code, "value": str(fact.value), "unit": fact.canonical_unit,
             "status": fact.resolution_status, "evidence_id": fact.evidence_id}
            for fact in model.facts
        ],
        "capacity": {
            "status": model.capacity_runtime.calculation_readiness_status,
            "ready": model.capacity_runtime.calculation_ready,
            "requires_assumptions": model.capacity_runtime.calculation_requires_assumptions,
            "blockers": list(model.capacity_runtime.calculation_blockers),
        },
        "source": {
            "catalog_code": catalog_code,
            "name": source_name,
            "observed_on": source_date.isoformat() if source_date else None,
            "pdf_page": media.source_page if media else None,
            "source_row": position.source_row_number,
            "card_url": f"/api/catalog/positions/{position.id}",
        },
    }


def build_corpus(snapshot: CatalogSnapshotDTO) -> dict[str, Any]:
    """Build from the current active snapshot every time; activation needs no stale index job."""
    cards = [_card(position, snapshot.version.code) for position in snapshot.positions]
    return {"version": snapshot.version.code, "content_sha256": snapshot.version.content_sha256,
            "position_count": len(cards), "cards": cards}


def _rank(cards: list[dict[str, Any]], message: str) -> list[dict[str, Any]]:
    query = _tokens(message)
    if not query:
        return []
    ranked = []
    for card in cards:
        primary = _tokens(" ".join(str(card.get(field) or "") for field in ("name", "family", "type", "use")))
        secondary = _tokens(card.get("description") or "")
        fact_terms = _tokens(" ".join(fact["code"] for fact in card["facts"]))
        score = 3 * len(query & primary) + len(query & secondary) + len(query & fact_terms)
        if score:
            ranked.append((score, card))
    ranked.sort(key=lambda item: (-item[0], item[1]["name"], item[1]["id"]))
    return [card for _, card in ranked[:6]]


def _extract_draft(text: str) -> dict[str, Any]:
    lower = text.casefold()
    fields: dict[str, Any] = {"object_type": "other"}
    if any(word in lower for word in ("паллет", "поддон")):
        fields.update(process_type="transport", cargo_type="pallets")
    elif any(word in lower for word in ("уборк", "убират", "мойк")):
        fields.update(process_type="cleaning", cargo_type="cases")
    elif any(word in lower for word in ("достав", "курьер")):
        fields.update(process_type="delivery", cargo_type="deliveries")
    elif any(word in lower for word in ("короб", "ящик")):
        fields.update(process_type="transport", cargo_type="boxes")
    patterns = {
        "pallets_per_day": r"\b(\d{1,6})\s*(?:паллет\w*|поддон\w*|рейс\w*|достав\w*)\s*(?:в\s*(?:сутки|день)|/\s*(?:сутки|день))",
        "avg_distance_m": r"\b(?:плечо|расстояние|маршрут)\s*(\d{1,5}(?:[.,]\d+)?)\s*м\b",
        "shifts_count": r"\b([1-4])\s*смен\w*\b",
        "staff_headcount": r"\b(\d{1,3})\s*(?:человек|сотрудник\w*|водител\w*)\b",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, lower)
        if match:
            value = float(match.group(1).replace(",", ".")) if key == "avg_distance_m" else int(match.group(1))
            if value > 0:
                fields[key] = value
    return {"fields": fields, "summary": _short(text, 400), "confirmed": False}


def answer_catalog(snapshot: CatalogSnapshotDTO, request: AssistantRequest) -> dict[str, Any]:
    corpus = build_corpus(snapshot)
    cards_by_id = {card["id"]: card for card in corpus["cards"]}
    compare_ids = [str(value) for value in request.compare_ids]
    if len(compare_ids) != len(set(compare_ids)) or (compare_ids and len(compare_ids) < 2):
        raise HTTPException(422, "Для сравнения выберите 2–3 разные позиции.")
    if any(value not in cards_by_id for value in compare_ids):
        raise HTTPException(422, "Позиция сравнения отсутствует в активном каталоге.")
    context = " ".join([*request.history[-3:], request.message])[:1200]
    matches = _rank(corpus["cards"], context)
    compared = [cards_by_id[value] for value in compare_ids] if compare_ids else matches[:3]
    question = "Уточните груз или операцию, объём за день и условия объекта — тогда поиск станет точнее."
    if matches:
        if "pallets_per_day" not in _extract_draft(context)["fields"]:
            question = "Сколько операций или единиц груза нужно обрабатывать за день?"
        elif "avg_distance_m" not in _extract_draft(context)["fields"]:
            question = "Каково среднее расстояние одного рейса и есть ли ограничения по проходам?"
        else:
            question = "Есть ли ограничения по массе груза, ширине проходов или графику смен?"
    reply = (
        f"В активном каталоге {corpus['version']} нашёл {len(matches)} подходящих позиций. "
        "Характеристики ниже приведены только при наличии подтверждённого факта; применимость и закупку нужно проверять отдельно."
        if matches else
        f"По этой формулировке в активном каталоге {corpus['version']} подтверждённых совпадений нет. "
        "Попробуйте описать операцию и груз другими словами."
    )
    draft = _extract_draft(context)
    return {"mode": "catalog", "catalog": {key: corpus[key] for key in ("version", "content_sha256", "position_count")},
            "reply": reply, "question": question, "matches": matches,
            "comparison": compared if len(compared) >= 2 else [],
            "draft": draft if len(draft["fields"]) > 1 else None,
            "note": "Данные каталога не подтверждают доступность для покупки и не изменяют статус C05."}


def _safe_url(value: str) -> str | None:
    if any(ord(char) < 32 for char in value):
        return None
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return None
    return value.strip()[:1200]


def parse_web_results(raw_data: str) -> list[dict[str, str]]:
    """Treat provider XML as untrusted data; never fetch linked pages or execute markup."""
    xml = base64.b64decode(raw_data, validate=True)
    if len(xml) > 1_000_000 or b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("unsafe web search response")
    root = ET.fromstring(xml)
    results = []
    for doc in root.findall(".//doc")[:5]:
        url = _safe_url(doc.findtext("url") or "")
        if not url:
            continue
        title = _short("".join(doc.find("title").itertext()) if doc.find("title") is not None else url, 160) or url
        passages = ["".join(node.itertext()) for node in doc.findall(".//passage")[:2]]
        snippet = _short(" ".join(passages), 400) or "Фрагмент не предоставлен поисковой системой."
        results.append({"url": url, "title": title, "snippet": snippet})
    return results


def search_web(query: str, *, post: Callable[..., Any] = requests.post) -> dict[str, Any]:
    searched_at = datetime.now(timezone.utc).isoformat()
    key, folder = os.getenv("YC_API_KEY"), os.getenv("YC_FOLDER_ID")
    if not key or not folder:
        return {"mode": "web", "status": "unavailable", "searched_at": searched_at, "results": [],
                "message": "Внешний поиск сейчас не настроен. Каталог остаётся доступен."}
    try:
        response = post(
            WEB_SEARCH_URL,
            headers={"Authorization": f"Api-Key {key}", "Content-Type": "application/json"},
            json={"query": {"searchType": "SEARCH_TYPE_RU", "queryText": query, "familyMode": "FAMILY_MODE_STRICT"},
                  "folderId": folder, "responseFormat": "FORMAT_XML",
                  "groupSpec": {"groupMode": "GROUP_MODE_FLAT", "groupsOnPage": "5", "docsInGroup": "1"},
                  "maxPassages": "2"},
            timeout=8,
        )
        if response.status_code != 200:
            raise RuntimeError("provider returned non-200")
        results = parse_web_results(response.json()["rawData"])
    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError, binascii.Error, ET.ParseError):
        return {"mode": "web", "status": "unavailable", "searched_at": searched_at, "results": [],
                "message": "Внешний поиск временно недоступен. Проверьте доступ Yandex Search API или повторите позже."}
    return {"mode": "web", "status": "ok", "searched_at": searched_at, "results": results,
            "message": "Найденные в интернете сведения не проверены по официальному каталогу и не меняют расчёт или цену."}


def _owned_project(project_id: uuid.UUID | None, request: Request, db: Session, *, csrf: bool) -> str | None:
    if project_id is None and not csrf:
        return None
    context = require_auth_context(request, db)
    if csrf:
        import hmac
        from auth import _digest
        token = request.headers.get("X-CSRF-Token")
        cookie = request.cookies.get(CSRF_COOKIE)
        if not token or not cookie or not hmac.compare_digest(token, cookie) or not hmac.compare_digest(_digest(token), context.session.csrf_sha256):
            raise HTTPException(403, "CSRF validation failed")
    if project_id is not None and db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_id == context.user.id)) is None:
        raise HTTPException(404, "project not found")
    return str(context.user.id)


def create_solution_assistant_router(load_snapshot: Callable[[], CatalogSnapshotDTO]) -> APIRouter:
    router = APIRouter(prefix="/api/assistant")

    @router.post("/catalog")
    def catalog(payload: AssistantRequest, request: Request, db: Session = Depends(database_session)):
        _LIMITER.check("catalog", request.client.host if request.client else "unknown", 60)
        for item in payload.history:
            if len(item) > 400:
                raise HTTPException(422, "История диалога слишком длинная.")
        _owned_project(payload.project_id, request, db, csrf=payload.project_id is not None)
        return answer_catalog(load_snapshot(), payload)

    @router.post("/web")
    def web(payload: WebSearchRequest, request: Request, db: Session = Depends(database_session)):
        if len(payload.query.split()) > 40:
            raise HTTPException(422, "Для внешнего поиска используйте не более 40 слов.")
        subject = _owned_project(payload.project_id, request, db, csrf=True)
        _LIMITER.check("web", subject or "unknown", 5)
        return search_web(payload.query.strip())

    return router
