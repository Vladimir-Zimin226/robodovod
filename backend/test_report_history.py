from __future__ import annotations

from types import SimpleNamespace

from report_history import summarize_run


def run(id, kind, input_snapshot, result_snapshot, *, parent=None, status="SUCCEEDED"):
    return SimpleNamespace(id=id, run_kind=kind, input_snapshot=input_snapshot,
                           result_snapshot=result_snapshot, parent_run_id=parent, status=status)


def test_partial_and_full_versions_share_only_the_saved_capacity_link():
    capacity = run("capacity-a", "CAPACITY_ANALYSIS", {
        "process": {"process_code": "warehouse_receiving_shipping", "process_id": "zone.a.process"},
        "zone_context": {"label": "Приёмка"}, "model_id": "model-a",
    }, {"capacity": {"value": {"selected_fleet": 3}}})
    other_capacity = run("capacity-b", "CAPACITY_ANALYSIS", {
        "process": {"process_code": "warehouse_receiving_shipping", "process_id": "zone.b.process"},
        "zone_context": {"label": "Отгрузка"}, "model_id": "model-b",
    }, {"capacity": {"value": {"selected_fleet": 7}}})
    partial = run("partial", "FULL_ANALYSIS", {"capacity_run_id": "capacity-a", "economics": {
        "schema_version": "economics-explicit-inputs-v4", "horizon_years": 5,
        "discount_rate": "0.15", "field_sources": {"discount_rate": "ASSUMPTION"},
    }}, {"schema_version": "economics-partial-result-v1", "branches": {
        "capacity": {"status": "AVAILABLE", "selected_fleet": 3}, "labour": {"status": "CALCULATED"},
        "purchase": {"status": "CALCULATED"}, "raas": {"status": "NOT_CALCULATED"},
    }, "scenarios": [{"scenario_id": "scenario.purchase.base", "acquisition": "PURCHASE",
                     "uncertainty": "BASE", "financial": {"status": "COMPLETE",
                     "npv_project": {"status": "COMPLETE", "value": "120.00", "unit": "RUB"}}}],
        "scenario_statuses": [{"scenario_id": "scenario.purchase.base", "status": "CALCULATED"}]}, parent="capacity-a")
    full = run("full", "FULL_ANALYSIS", {"capacity_run_id": "capacity-a", "economics": {
        "schema_version": "economics-explicit-inputs-v4", "horizon_years": 5,
        "discount_rate": "0.15", "raas_monthly_per_robot_gross": "1000",
    }}, {"schema_version": "commercial-scenarios-bundle-v2", "roles": [{
        "monthly_gross_salary": {"status": "KNOWN"}}], "scenarios": [
        {"acquisition": "PURCHASE", "uncertainty": "BASE", "financial": {"status": "COMPLETE",
         "npv_project": {"status": "COMPLETE", "value": "200.00", "unit": "RUB"}}},
        {"acquisition": "RAAS", "uncertainty": "BASE", "financial": {"status": "COMPLETE",
         "npv_project": {"status": "COMPLETE", "value": "90.00", "unit": "RUB"}}},
    ]}, parent="partial")
    by_id = {item.id: item for item in (capacity, other_capacity, partial, full)}
    first = summarize_run(partial, by_id, model_names={"model-a": "MULE"})
    second = summarize_run(full, by_id, model_names={"model-a": "MULE"}, simulation_count=1)
    third = summarize_run(other_capacity, by_id)
    assert first["group_run_id"] == second["group_run_id"] == "capacity-a"
    assert third["group_run_id"] == "capacity-b"
    assert (first["zone_label"], first["model_name"], first["fleet"]) == ("Приёмка", "MULE", 3)
    assert first["result_type"] == "PARTIAL" and second["result_type"] == "FULL"
    assert first["branches"]["raas"] == "NOT_CALCULATED"
    assert second["branches"]["simulation"] == "SAVED"
    assert first["npv"] == [{"acquisition": "PURCHASE", "uncertainty": "BASE", "value": "120.00", "unit": "RUB"}]
    assert len(second["npv"]) == 2
    assert first["completeness"]["inputs"]["confirmed"] == 1  # unconfirmed assumption is excluded
    assert first["can_create_version"] is True


def test_uncalculated_money_and_legacy_result_never_gain_invented_npv():
    capacity = run("cap", "CAPACITY_ANALYSIS", {"process": {}}, {"capacity": {"value": {"selected_fleet": 1}}})
    partial = run("partial", "FULL_ANALYSIS", {"capacity_run_id": "cap"}, {
        "schema_version": "economics-partial-result-v1", "branches": {},
        "scenarios": [{"scenario_id": "s", "acquisition": "RAAS", "uncertainty": "BASE",
                       "financial": {"status": "INCOMPLETE", "npv_project": {"status": "INCOMPLETE", "value": None, "unit": "RUB"}}}],
        "scenario_statuses": [{"scenario_id": "s", "status": "NOT_CALCULATED"}]})
    legacy = run("legacy", "FULL_ANALYSIS", {}, {"mode": "zonal", "npv_project": "999"})
    assert summarize_run(partial, {"cap": capacity})["npv"] == []
    card = summarize_run(legacy, {})
    assert card["npv"] == [] and card["branches"]["purchase"] == "UNKNOWN"


def test_failed_run_is_not_reported_as_full_and_v1_saved_inputs_can_be_edited():
    capacity = run("cap", "CAPACITY_ANALYSIS", {"process": {}}, {"capacity": {"value": {"selected_fleet": 1}}})
    failed = run("failed", "FULL_ANALYSIS", {"capacity_run_id": "cap", "economics": {
        "schema_version": "economics-explicit-inputs-v1", "discount_rate": "0.15",
    }}, None, status="FAILED")
    saved = run("saved", "FULL_ANALYSIS", {"capacity_run_id": "cap", "economics": {
        "schema_version": "economics-explicit-inputs-v1", "discount_rate": "0.15",
    }}, {"schema_version": "commercial-scenarios-bundle-v2", "scenarios": []})
    assert summarize_run(failed, {"cap": capacity})["result_type"] == "UNAVAILABLE"
    assert summarize_run(failed, {"cap": capacity})["can_create_version"] is False
    assert summarize_run(saved, {"cap": capacity})["can_create_version"] is True
