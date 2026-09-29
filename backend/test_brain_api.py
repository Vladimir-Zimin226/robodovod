from __future__ import annotations

import threading
import uuid
from types import SimpleNamespace

import brain_api as brain
import pytest
import requests
from fastapi import HTTPException


def test_brain_golden_220_pallets_unconfirmed_then_ready():
    text = "На складе перевозим 220 паллет в сутки на 120 м."
    turn = brain.BrainTurn.model_validate({"message": "Сколько смен?", "field_updates": [
        {"path": "object_type", "value": "retail", "provenance": "user"},
        {"path": "process_type", "value": "transport", "provenance": "user"},
        {"path": "operations_per_day", "value": "220", "unit": "pallet/day", "provenance": "user"},
        {"path": "avg_distance_m", "value": "120", "unit": "m", "provenance": "user"},
    ], "next_action": "ask"})
    fields = dict(filter(None, (brain._validate_update(item, text) for item in turn.field_updates)))
    assert fields["operations_per_day"]["value"] == "220"
    assert fields["avg_distance_m"]["value"] == "120"
    assert all(not item["confirmed_by_user"] for item in fields.values())
    profile = brain._current({"versions": []}, uuid.uuid4())
    profile["fields"] = fields
    assert not brain.readiness(profile)["technical"]["ready"]
    for key, value, unit in (("shifts_count", "2", "shift/day"), ("shift_hours", "11", "h/shift"),
                             ("operating_days", "365", "day/year"), ("units_per_trip", "1", "pallet/trip"),
                             ("exchange_seconds", "90", "s")):
        profile["fields"][key] = {"value": value, "unit": unit, "confirmed_by_user": True}
    for item in profile["fields"].values():
        item["confirmed_by_user"] = True
    assert brain.readiness(profile)["technical"]["ready"]
    assert not brain.readiness(profile)["labour"]["ready"]
    assert "monthly_gross_salary" in brain.readiness(profile)["labour"]["missing"]


def test_brain_rejects_conflicting_units_and_fabricated_values():
    text = "Маршрут 120 км, 220 паллет в неделю"
    distance = brain.TurnUpdate(path="avg_distance_m", value="120", unit="m", provenance="user")
    demand = brain.TurnUpdate(path="operations_per_day", value="220", unit="pallet/day", provenance="user")
    assert brain._validate_update(distance, text) is None
    assert brain._validate_update(demand, text) is None
    assert brain._validate_update(brain.TurnUpdate(path="monthly_gross_salary", value="120000", unit="RUB/person/month", provenance="user"), text) is None


def test_outage_extractor_only_proposes_explicit_golden_values():
    message = "На складе перевозим 220 паллет в сутки на 120 м."
    updates, processes = brain._explicit_facts(message)
    profile = brain._current({"versions": []}, uuid.uuid4())
    brain._apply_proposals(profile, message, updates, processes)
    assert profile["fields"]["operations_per_day"]["value"] == "220"
    assert profile["fields"]["avg_distance_m"]["value"] == "120"
    assert "monthly_gross_salary" not in profile["fields"]
    assert not profile["fields"]["avg_distance_m"]["confirmed_by_user"]
    assert profile["active_processes"] == ["warehouse_receiving_shipping"]
    contradictory, _ = brain._explicit_facts("На складе перевозим 220 паллет в неделю на 120 км")
    profile2 = brain._current({"versions": []}, uuid.uuid4())
    brain._apply_proposals(profile2, "На складе перевозим 220 паллет в неделю на 120 км", contradictory, [])
    assert "operations_per_day" not in profile2["fields"]
    assert "avg_distance_m" not in profile2["fields"]


def test_multiple_processes_keep_separate_demands_and_unsupported_stays_descriptive():
    profile = brain._current({"versions": []}, uuid.uuid4())
    first = "На складе перевозим 220 паллет в сутки на 120 м и убираем помещение"
    updates, processes = brain._explicit_facts(first)
    brain._apply_proposals(profile, first, updates, processes)
    assert profile["selected_process"] == "warehouse_receiving_shipping"
    assert set(profile["active_processes"]) == {"warehouse_receiving_shipping", "warehouse_cleaning"}
    assert profile["fields"]["operations_per_day"]["value"] == "220"
    second = "Убираем 10000 м² в сутки"
    updates, processes = brain._explicit_facts(second)
    brain._apply_proposals(profile, second, updates, processes)
    assert profile["selected_process"] == "warehouse_cleaning"
    assert profile["fields"]["operations_per_day"]["value"] == "10000"
    assert profile["fields"]["operations_per_day"]["unit"] == "m2/day"
    assert "avg_distance_m" not in profile["fields"]
    assert profile["process_fields"]["warehouse_receiving_shipping"]["operations_per_day"]["value"] == "220"
    assert not brain.readiness(profile)["technical"]["ready"]
    unsupported, processes = brain._explicit_facts("На складе комплектуем заказы")
    brain._apply_proposals(profile, "На складе комплектуем заказы", unsupported, processes)
    assert "warehouse_picking" in profile["active_processes"]
    assert not brain.readiness(profile)["technical"]["ready"]


def test_cleaning_requires_explicit_frequency_and_allowed_schedule():
    profile = brain._current({"versions": []}, uuid.uuid4())
    values = {"object_type": ("retail", None), "process_type": ("cleaning", None),
              "operations_per_day": ("10000", "m2/day"), "shifts_count": ("2", "shift/day"),
              "shift_hours": ("11", "h/shift"), "operating_days": ("365", "day/year")}
    profile["fields"] = {key: {"value": value, "unit": unit, "confirmed_by_user": True} for key, (value, unit) in values.items()}
    assert "cleaning_frequency_per_day" in brain.readiness(profile)["technical"]["missing"]
    profile["fields"]["cleaning_frequency_per_day"] = {"value": "1", "unit": "1/day", "confirmed_by_user": False}
    assert "cleaning_frequency_per_day" in brain.readiness(profile)["technical"]["missing"]
    profile["fields"]["cleaning_frequency_per_day"]["confirmed_by_user"] = True
    assert brain.readiness(profile)["technical"]["ready"]
    profile["fields"]["shift_hours"]["value"] = "7"
    assert "invalid_shift_hours" in brain.readiness(profile)["technical"]["missing"]


def test_brain_binding_checks_profile_version_and_values():
    profile = brain._current({"versions": []}, uuid.uuid4())
    profile["profile_version"] = 3
    profile["fields"]["object_type"] = {"value": "retail", "confirmed_by_user": True}
    profile["fields"]["process_type"] = {"value": "transport", "confirmed_by_user": True}
    for key, value in {"operations_per_day": "220", "shifts_count": "2", "shift_hours": "11", "operating_days": "365",
                       "avg_distance_m": "120", "units_per_trip": "1", "exchange_seconds": "90"}.items():
        profile["fields"][key] = {"value": value, "confirmed_by_user": True}
    q = lambda value: {"normalized_value": value}
    data = {"provenance": [{"assumption_version": "profile-v3"}], "zone_context": {"label": "Основная зона"},
            "role_pool": {"roles": []}, "process": {
        "process_code": "warehouse_receiving_shipping", "scope": "TRANSPORT_CYCLE", "demand": q("220"),
        "schedule": {"shifts_per_day": q("2"), "shift_hours": q("11"), "days_per_year": q("365")},
        "route_distance": q("120"), "explicit_batch": q("1"), "exchange": {"total_time": q("90")}}}
    run = SimpleNamespace(run_kind="CAPACITY_ANALYSIS", input_snapshot=data)
    assert brain._run_matches_profile(run, profile)
    run.input_snapshot["process"]["route_distance"] = q("121")
    assert not brain._run_matches_profile(run, profile)


def test_brain_model_failure_contract(monkeypatch):
    def unavailable(_message, _profile):
        from fastapi import HTTPException
        raise HTTPException(503, "model unavailable")
    monkeypatch.setattr(brain, "_call_model", unavailable)
    with pytest.raises(HTTPException) as error:
        brain._call_model("hello", {"fields": {}, "active_processes": []})
    assert error.value.status_code == 503


def test_brain_request_uses_provider_compatible_strict_schema(monkeypatch):
    monkeypatch.setenv("YC_API_KEY", "test")
    monkeypatch.setenv("YC_FOLDER_ID", "test")

    def check_schema(node):
        if isinstance(node, list):
            for item in node:
                check_schema(item)
        elif isinstance(node, dict):
            assert "default" not in node
            if node.get("type") == "object":
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            for item in node.values():
                check_schema(item)

    def post(_url, *, json, headers, timeout):
        assert json["model"] == "gpt://test/deepseek-v4-flash"
        assert json["max_tokens"] >= 3000
        assert timeout[0] <= 5 and timeout[1] <= 50
        assert json["messages"][1]["content"] == "220 паллет в сутки"
        check_schema(json["response_format"]["json_schema"]["schema"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "choices": [{"finish_reason": "stop", "message": {"content":
                         '{"message":"Сколько смен?","field_updates":[],"process_updates":[],"next_action":"ask","question":null}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })

    monkeypatch.setattr(brain.requests, "post", post)
    answer, usage = brain._call_model("220 паллет в сутки", {"fields": {}, "active_processes": []})
    assert answer.next_action == "ask"
    assert usage["input"] == 10 and usage["output"] == 20
    assert usage["finish_reason"] == "stop"


def test_model_gets_only_confirmed_context_and_server_next_question(monkeypatch):
    monkeypatch.setenv("YC_API_KEY", "test")
    monkeypatch.setenv("YC_FOLDER_ID", "test")
    profile = brain._current({"versions": []}, uuid.uuid4())
    profile["fields"] = {"object_type": {"value": "retail", "confirmed_by_user": True},
                         "zone_constraints": {"value": "UNCONFIRMED_PRIVATE_NOTE", "confirmed_by_user": False}}
    def post(_url, *, json, **_kwargs):
        prompt = json['messages'][0]['content']
        assert 'retail' in prompt and 'next_question' in prompt
        assert 'UNCONFIRMED_PRIVATE_NOTE' not in prompt
        assert json['messages'][1]['content'] == 'Перевозка паллет'
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {
            'choices': [{'finish_reason': 'stop', 'message': {'content':
                '{"message":"Какой объём?","field_updates":[],"process_updates":[],"next_action":"ask","question":null}'}}]})
    monkeypatch.setattr(brain.requests, 'post', post)
    brain._call_model('Перевозка паллет', profile)


def test_short_answers_follow_saved_question_without_confirming_numbers():
    profile = brain._current({"versions": []}, uuid.uuid4())
    for key, value in (("object_type", "retail"), ("process_type", "transport"), ("operations_per_day", "220")):
        profile['fields'][key] = {'value': value, 'unit': brain.FIELD_UNITS[key], 'confirmed_by_user': True}
    proposals = brain._answer_to_saved_question('2', profile)
    assert len(proposals) == 1 and proposals[0].path == 'shifts_count'
    brain._apply_proposals(profile, '2', proposals, [])
    assert profile['fields']['shifts_count']['value'] == '2'
    assert not profile['fields']['shifts_count']['confirmed_by_user']
    profile['fields']['shifts_count']['confirmed_by_user'] = True
    proposals = brain._answer_to_saved_question('11', profile)
    assert proposals[0].path == 'shift_hours'
    assert not brain._answer_to_saved_question('11 км', profile)


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
def test_brain_provider_http_failure_is_classified(monkeypatch, status):
    monkeypatch.setenv("YC_API_KEY", "secret-test-key")
    monkeypatch.setenv("YC_FOLDER_ID", "test")

    def post(*_args, **_kwargs):
        response = requests.Response()
        response.status_code = status
        response._content = b"private provider response"
        return response

    monkeypatch.setattr(brain.requests, "post", post)
    with pytest.raises(brain.BrainModelFailure) as caught:
        brain._call_model("private prompt", {})
    assert caught.value.kind == f"HTTP_{status}"
    assert caught.value.metrics["provider_http_status"] == status
    assert "private" not in caught.value.detail


@pytest.mark.parametrize("response", [
    {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}]},
])
def test_brain_provider_incomplete_or_invalid_response(monkeypatch, response):
    monkeypatch.setenv("YC_API_KEY", "test-key")
    monkeypatch.setenv("YC_FOLDER_ID", "test")
    monkeypatch.setattr(brain.requests, "post", lambda *_args, **_kwargs: SimpleNamespace(
        status_code=200, raise_for_status=lambda: None, json=lambda: response))
    with pytest.raises(brain.BrainModelFailure) as caught:
        brain._call_model("message", {})
    assert caught.value.kind == ("LENGTH" if response["choices"][0]["finish_reason"] == "length" else "INVALID_RESPONSE")


def test_brain_user_wait_is_bounded_even_when_provider_does_not_return(monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(brain, "MODEL_WAIT_SECONDS", 0.01)
    monkeypatch.setattr(brain, "_call_model", lambda *_args: gate.wait(1))
    try:
        with pytest.raises(brain.BrainModelFailure) as caught:
            brain._bounded_model_call("message", {})
        assert caught.value.kind == "TIMEOUT"
    finally:
        gate.set()


def test_brain_local_action_skips_provider_and_explicit_facts_remain_local():
    assert brain._local_turn("Запустить расчёт!").next_action == "preflight"
    assert brain._local_turn("220 паллет в сутки") is None
    updates, _processes = brain._explicit_facts("На складе 220 паллет в сутки на 120 м")
    assert {item.path for item in updates} >= {"operations_per_day", "avg_distance_m"}


def test_brain_network_timeout_is_classified(monkeypatch):
    monkeypatch.setenv("YC_API_KEY", "test-key")
    monkeypatch.setenv("YC_FOLDER_ID", "test")
    monkeypatch.setattr(brain.requests, "post", lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout()))
    with pytest.raises(brain.BrainModelFailure) as caught:
        brain._call_model("message", {})
    assert caught.value.kind == "TIMEOUT"


def test_brain_operational_log_excludes_private_values(caplog):
    with caplog.at_level("INFO", logger="robodovod.brain"):
        brain._event(status="FALLBACK", failure_kind="HTTP_401", message="private prompt", api_key="secret")
    assert "status=FALLBACK" in caplog.text
    assert "private prompt" not in caplog.text
    assert "secret" not in caplog.text
