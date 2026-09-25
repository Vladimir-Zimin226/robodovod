from __future__ import annotations

import uuid
from types import SimpleNamespace

import brain_api as brain
import pytest
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
