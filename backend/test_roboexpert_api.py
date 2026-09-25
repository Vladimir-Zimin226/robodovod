from __future__ import annotations

import json
import uuid
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest
from auth import require_csrf
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from roboexpert_api import (
    ComparisonRequest, PilotLimiter, _llm_summary, compare_catalog, create_roboexpert_router, options,
)
from test_capacity_analysis_service import snapshot


def catalog():
    base = snapshot()
    first = base.positions[0]
    second_model = replace(first.model, id="model.second", name="Second transport")
    second = replace(first, id="position.second", model=second_model)
    packaging_runtime = replace(first.model.capacity_runtime, calculation_profile="PALLETIZING_THROUGHPUT_V1")
    packaging_model = replace(first.model, id="model.packaging", name="Packaging line", type_code="Packaging",
                              capacity_runtime=packaging_runtime)
    packaging = replace(first, id="position.packaging", model=packaging_model)
    info_runtime = replace(first.model.capacity_runtime, calculation_ready=False,
                           calculation_readiness_status="UNSUPPORTED_CAPACITY_PROFILE")
    info_model = replace(first.model, id="model.picking", name="Pick by Voice", type_code="Picking",
                         capacity_runtime=info_runtime)
    info = replace(first, id="position.picking", model=info_model)
    return replace(base, models=(first.model, second_model, packaging_model, info_model),
                   positions=(first, second, packaging, info))


def request(*ids):
    return ComparisonRequest(position_ids=list(ids), catalog_version=catalog().version.code)


def test_same_class_shows_sources_and_missing_price_without_cheaper_claim():
    result = compare_catalog(catalog(), request("position.synthetic.transport", "position.second"))
    assert result["schema_version"] == "roboexpert-comparison-v1"
    assert result["criteria"]
    assert any(row["code"] == "payload" and row["numeric_comparable"] for row in result["criteria"])
    assert all(cell["source"]["evidence_id"] for row in result["criteria"] for cell in row["cells"])
    assert result["price"]["comparable"] is False
    assert result["price"]["lowest_position_id"] is None
    assert any("дешевизне недоступен" in item for item in result["summary"]["limitations"])
    assert result["comparison_digest"].startswith("sha256:")


def test_other_physical_profile_and_information_only_cannot_enter_numeric_cohort():
    with pytest.raises(HTTPException) as different:
        compare_catalog(catalog(), request("position.synthetic.transport", "position.packaging"))
    assert different.value.status_code == 422
    with pytest.raises(HTTPException) as info:
        compare_catalog(catalog(), request("position.synthetic.transport", "position.picking"))
    assert info.value.status_code == 422
    source = catalog()
    other_type = replace(source.positions[1], model=replace(source.positions[1].model, type_code="Packing"))
    with pytest.raises(HTTPException):
        compare_catalog(replace(source, positions=(source.positions[0], other_type, *source.positions[2:])),
                        request("position.synthetic.transport", "position.second"))
    item = next(item for item in options(catalog())["items"] if item["position_id"] == "position.picking")
    assert "формулы" in item["information_reason"]
    source = catalog()
    research = replace(source.positions[1], model=replace(source.positions[1].model, maturity_status="RND"))
    with pytest.raises(HTTPException):
        compare_catalog(replace(source, positions=(source.positions[0], research, *source.positions[2:])),
                        request("position.synthetic.transport", "position.second"))


def test_confirmed_price_comparison_requires_evidence_and_same_currency():
    source = catalog()
    first, second = source.positions[:2]
    priced = []
    for item, amount in ((first, "100"), (second, "200")):
        priced.append(replace(item, procurement_option=replace(item.procurement_option, amount=Decimal(amount),
                                                                currency="RUB", price_status="NORMALIZED",
                                                                evidence_id=f"price.{item.id}",
                                                                evidence_status="VERIFIED_OFFICIAL")))
    updated = replace(source, positions=(*priced, *source.positions[2:]))
    result = compare_catalog(updated, request(first.id, second.id))
    assert result["price"]["comparable"] is True
    assert result["price"]["lowest_position_id"] == first.id
    missing_source = replace(priced[1], procurement_option=replace(priced[1].procurement_option, evidence_id=None))
    result = compare_catalog(replace(source, positions=(priced[0], missing_source, *source.positions[2:])), request(first.id, second.id))
    assert result["price"]["comparable"] is False


def test_conflicting_catalog_facts_do_not_become_numeric_comparison():
    source = catalog()
    first = source.positions[0]
    conflict = replace(first.model.facts[0], value=Decimal("4"), evidence_id="other.speed")
    model = replace(first.model, facts=(*first.model.facts, conflict))
    changed = replace(source, positions=(replace(first, model=model), *source.positions[1:]))
    result = compare_catalog(changed, request(first.id, source.positions[1].id))
    speed = next(row for row in result["criteria"] if row["code"] == "max_speed")
    assert speed["cells"][0]["status"] == "CONFLICT"
    assert speed["numeric_comparable"] is False


def test_ai_output_is_limited_and_falls_back_when_it_makes_unsupported_claim(monkeypatch):
    monkeypatch.setenv("YC_API_KEY", "test")
    monkeypatch.setenv("YC_FOLDER_ID", "test")
    comparison = compare_catalog(catalog(), request("position.synthetic.transport", "position.second"))

    def post(_url, **_kwargs):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "choices": [{"message": {"content": json.dumps({"text": "Вторая модель дешевле."})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        })

    assert _llm_summary(comparison, post=post)["status"] == "UNAVAILABLE"
    def safe_post(_url, **_kwargs):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "choices": [{"message": {"content": json.dumps({"text": "Цена неизвестна; нужны паспорт и проверка объекта."})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        })
    answer = _llm_summary(comparison, post=safe_post)
    assert answer["status"] == "OK"
    assert answer["usage"]["estimated_rub"] == 0.04


def test_rate_limits_and_http_web_provenance(monkeypatch):
    limiter = PilotLimiter()
    limiter.check("ai", "user", daily=2, minute=2)
    limiter.check("ai", "user", daily=2, minute=2)
    with pytest.raises(HTTPException) as limited:
        limiter.check("ai", "user", daily=2, minute=2)
    assert limited.value.status_code == 429

    monkeypatch.setattr("roboexpert_api.search_web", lambda _query: {
        "status": "ok", "searched_at": "2026-09-26T00:00:00+00:00", "results": [
            {"url": "https://example.org/passport", "title": "Passport", "snippet": "External result"}],
        "message": "Search result requires checking",
    })
    app = FastAPI()
    app.include_router(create_roboexpert_router(catalog))
    app.dependency_overrides[require_csrf] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    with TestClient(app) as client:
        available = client.get("/api/roboexpert/options")
        assert available.status_code == 200
        selected = client.post("/api/roboexpert/compare", json={"catalog_version": catalog().version.code,
                           "position_ids": ["position.synthetic.transport", "position.second"]})
        assert selected.status_code == 200
        stale = client.post("/api/roboexpert/summary", json={"catalog_version": catalog().version.code,
                           "position_ids": ["position.synthetic.transport", "position.second"],
                           "comparison_digest": "sha256:" + "0" * 64})
        assert stale.status_code == 409
        web = client.post("/api/roboexpert/web", json={"catalog_version": catalog().version.code,
                          "position_id": "position.second", "topic": "passport"})
        assert web.status_code == 200
        assert web.json()["verification_status"] == "REQUIRES_VERIFICATION"
        assert web.json()["results"][0]["url"] == "https://example.org/passport"
        assert web.json()["pricing_estimate"]["daytime_synchronous_request_rub"] == "0.488"
