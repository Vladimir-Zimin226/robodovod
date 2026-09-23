from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.scheduling import (
    SimulationErrorV1,
    SimulationReportV1,
    SimulationRequestV1,
    SimulationSlaV1,
    _capacity_verdict,
    run_simulation,
)
from calculation_contracts import semantic_digest
from models import ScenarioSpec
from scenario_spec_v2 import ScenarioSpecV2


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts" / "fixtures"


def _raw_request() -> dict:
    return json.loads((FIXTURES / "simulation-request-v1.capacity-only.golden.json").read_text(encoding="utf-8"))


def _request(**updates) -> SimulationRequestV1:
    raw = _raw_request()
    raw.update(updates)
    return SimulationRequestV1.model_validate(raw)


def _scenario(mutator) -> ScenarioSpecV2:
    raw = _raw_request()["scenario_spec"]
    mutator(raw)
    raw["revision_id"] = "calc_" + semantic_digest({key: value for key, value in raw.items() if key != "revision_id"}).removeprefix("sha256:")[:16]
    return ScenarioSpecV2.model_validate(raw)


def test_capacity_only_golden_is_deterministic_and_replay_digest_is_self_checking():
    request = _request()
    first = run_simulation(request)
    second = run_simulation(request)
    assert isinstance(first, SimulationReportV1)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.model_dump(mode="json") == json.loads(
        (FIXTURES / "simulation-report-v1.capacity-only.golden.json").read_text(encoding="utf-8")
    )
    canonical = first.model_dump(mode="json")
    canonical["replay"]["report_content_digest"] = "sha256:" + "0" * 64
    assert first.replay.report_content_digest == semantic_digest(canonical)
    assert first.time_basis.seed == 42
    assert first.workload.jobs_per_day == 510
    assert first.queue.completed_by_measurement_end == 507
    assert first.queue.completed_with_grace == 510
    assert first.queue.completed_units_with_grace == "51000"
    assert Decimal(first.utilization.productive_seconds) + Decimal(first.utilization.nonproductive_allowance_seconds) == Decimal(first.utilization.busy_seconds)
    assert first.utilization.failure_downtime_status == "NOT_EVALUATED_NO_INPUT"
    assert first.utilization.failure_downtime_seconds is None
    assert first.versions.failure_model_version == "not-provided"
    with pytest.raises(ValidationError, match="frozen_instance"):
        first.queue.maximum_jobs = 99


def test_strict_unknown_version_extra_field_and_tenant_isolation():
    for name in (
        "simulation-request-v1.unknown-version.invalid.json",
        "simulation-request-v1.extra-field.invalid.json",
    ):
        with pytest.raises(ValidationError):
            SimulationRequestV1.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))
    with pytest.raises(ValidationError, match="tenant/project"):
        _request(tenant_id="tenant.other")
    report = json.loads((FIXTURES / "simulation-report-v1.capacity-only.golden.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        SimulationReportV1.model_validate({**report, "schema_version": "simulation-report-v2"})
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SimulationReportV1.model_validate({**report, "client_kpi": 1})
    tampered = {**report, "queue": {**report["queue"], "maximum_jobs": 99}}
    with pytest.raises(ValidationError, match="content digest"):
        SimulationReportV1.model_validate(tampered)


def test_explicit_peak_factor_and_policy_limits_have_no_hidden_request_defaults():
    raw = _raw_request()
    raw["mode"] = "PEAK_STRESS"
    with pytest.raises(ValidationError, match="peak_factor"):
        SimulationRequestV1.model_validate(raw)
    raw = _raw_request()
    del raw["limits"]["max_runtime_seconds"]
    with pytest.raises(ValidationError, match="max_runtime_seconds"):
        SimulationRequestV1.model_validate(raw)
    with pytest.raises(ValidationError, match="target_fraction"):
        SimulationSlaV1.model_validate({"minutes": "20", "provenance_ref": "prov.sla"})


def test_22_hour_and_24_hour_bases_are_explicit_and_change_replay():
    baseline = run_simulation(_request())
    short = _scenario(lambda raw: raw["operating_windows"][0]["duration"].update(value="22"))
    changed = run_simulation(_request(scenario_spec=short.model_dump(mode="json")))
    assert isinstance(baseline, SimulationReportV1) and isinstance(changed, SimulationReportV1)
    assert baseline.time_basis.operating_hours_per_day == "24"
    assert changed.time_basis.operating_hours_per_day == "22"
    assert baseline.replay.scenario_spec_digest != changed.replay.scenario_spec_digest
    assert baseline.report_id != changed.report_id


def test_zero_expected_zero_observed_and_overloaded_queue():
    def zero(raw):
        raw["tasks"][0]["demand"]["value"] = "0"
        fleet = raw["fleet"][0]
        fleet["selected_fleet"] = fleet["recommended_fleet"] = 0
        fleet["nominal_capacity"]["value"] = fleet["effective_capacity"]["value"] = "0"

    zero_report = run_simulation(_request(scenario_spec=_scenario(zero).model_dump(mode="json")))
    assert isinstance(zero_report, SimulationReportV1)
    assert zero_report.capacity.verdict == "N_A"
    assert zero_report.capacity.deviation_percent is None

    def zero_capacity(raw):
        raw["fleet"][0]["nominal_capacity"]["value"] = "0"
        raw["fleet"][0]["effective_capacity"]["value"] = "0"

    no_capacity = run_simulation(_request(scenario_spec=_scenario(zero_capacity).model_dump(mode="json")))
    assert isinstance(no_capacity, SimulationReportV1)
    assert no_capacity.capacity.verdict == "OVERLOADED"
    assert no_capacity.queue.completed_with_grace == 0

    overloaded = _scenario(lambda raw: raw["tasks"][0]["demand"].update(value="100000"))
    overload_report = run_simulation(_request(scenario_spec=overloaded.model_dump(mode="json")))
    assert isinstance(overload_report, SimulationReportV1)
    assert overload_report.capacity.verdict == "OVERLOADED"
    assert overload_report.queue.censored_jobs > 0


def test_deviation_boundary_is_strictly_greater_than_ten_percent():
    assert _capacity_verdict(Decimal("100"), Decimal("90"), overloaded=False) == (Decimal("10"), "CONSISTENT")
    assert _capacity_verdict(Decimal("100"), Decimal("89.999"), overloaded=False)[1] == "DEVIATION"
    assert _capacity_verdict(Decimal("0"), Decimal("1"), overloaded=False) == (None, "INPUT_MISMATCH")


def test_sla_20_and_30_minutes_use_explicit_inputs_and_resource_model():
    def twenty_five_minutes(raw):
        raw["tasks"][0]["demand"]["value"] = "1000"
        raw["fleet"][0]["effective_capacity"]["value"] = "23040"

    scenario = _scenario(twenty_five_minutes).model_dump(mode="json")
    resource = [{
        "resource_id": "resource.work", "stage": "WORK", "capacity": 100,
        "source": "USER", "provenance_ref": "prov.resource",
    }]
    sla20 = {"minutes": "20", "target_fraction": "1", "provenance_ref": "prov.sla"}
    sla30 = {"minutes": "30", "target_fraction": "1", "provenance_ref": "prov.sla"}
    failed = run_simulation(_request(scenario_spec=scenario, resources=resource, sla=sla20))
    passed = run_simulation(_request(scenario_spec=scenario, resources=resource, sla=sla30))
    assert isinstance(failed, SimulationReportV1) and isinstance(passed, SimulationReportV1)
    assert failed.sla.verdict == "FAIL"
    assert passed.sla.verdict == "PASS"


def test_independent_shared_resource_queue_adds_wait_without_double_availability():
    resource = [{
        "resource_id": "resource.work", "stage": "WORK", "capacity": 1,
        "source": "USER", "provenance_ref": "prov.resource",
    }]
    report = run_simulation(_request(resources=resource))
    assert isinstance(report, SimulationReportV1)
    assert Decimal(report.resources[0].wait_seconds) > 0
    assert Decimal(report.utilization.resource_wait_seconds) > 0
    assert Decimal(report.utilization.productive_seconds) + Decimal(report.utilization.nonproductive_allowance_seconds) == Decimal(report.utilization.busy_seconds)


def test_progress_cancel_limit_and_timeout_are_typed_terminal_results():
    progress = []
    report = run_simulation(_request(), progress=progress.append)
    assert isinstance(report, SimulationReportV1)
    assert progress[0].processed_events == 0
    assert progress[-1].processed_events == progress[-1].total_events

    cancelled = run_simulation(_request(), should_cancel=lambda: True)
    assert isinstance(cancelled, SimulationErrorV1) and cancelled.code == "CANCELLED"

    oversized = _scenario(lambda raw: raw["tasks"][0]["demand"].update(value="1000100"))
    limited = run_simulation(_request(scenario_spec=oversized.model_dump(mode="json")))
    assert isinstance(limited, SimulationErrorV1) and limited.code == "LIMIT_EXCEEDED"

    ticks = iter((0.0, 61.0))
    timed_out = run_simulation(_request(), clock=lambda: next(ticks))
    assert isinstance(timed_out, SimulationErrorV1) and timed_out.code == "TIMEOUT"


def test_documented_maximum_profile_finishes_within_policy_limit():
    def maximum(raw):
        raw["tasks"][0]["demand"]["value"] = "1000000"
        fleet = raw["fleet"][0]
        fleet["selected_fleet"] = fleet["recommended_fleet"] = 100
        fleet["nominal_capacity"]["value"] = "1920000"
        fleet["effective_capacity"]["value"] = "1344000"

    request = _request(scenario_spec=_scenario(maximum).model_dump(mode="json"))
    started = time.monotonic()
    report = run_simulation(request)
    elapsed = time.monotonic() - started
    assert isinstance(report, SimulationReportV1)
    assert report.workload.jobs_per_day == 10000
    assert elapsed <= request.limits.max_runtime_seconds


def test_v1_contract_is_unchanged_and_generated_contracts_are_exact():
    v1 = json.loads((FIXTURES / "scenario-spec-v1.golden.json").read_text(encoding="utf-8"))
    assert ScenarioSpec.model_validate(v1).model_dump(mode="json") == v1
    from scripts.build_simulation_report_v1_contract import expected_files

    assert [str(path.relative_to(ROOT)) for path, expected in expected_files() if path.read_bytes() != expected] == []
