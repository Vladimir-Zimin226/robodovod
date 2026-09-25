import pytest

from calculation.service import analyze_capacity
from economics_orchestrator import EconomicsExecutionContextV1
from economics_partial import DEMO_SCENARIO, INPUT_VERSION_V3, INPUT_VERSION_V4, execute_partial_economics_v2
from economics_runtime_migration import historical_mapping
from test_economics_orchestrator import _capacity_request, _inputs, _snapshot


def _context():
    snapshot = _snapshot()
    request = _capacity_request()
    capacity = analyze_capacity(request, snapshot, "run.capacity.partial")
    return snapshot, EconomicsExecutionContextV1(
        run_id="run.economics.partial",
        project_id=request.project_id,
        tenant_id="tenant.partial",
        capacity_request=request,
        capacity_response=capacity.response,
        constraint_report=capacity.constraints.model_dump(mode="json"),
        executability=capacity.executability.model_dump(mode="json"),
    )


def _input():
    return {**_inputs(), "schema_version": "economics-explicit-inputs-v2"}


def test_empty_inputs_save_capacity_and_no_false_finance():
    snapshot, context = _context()
    result = execute_partial_economics_v2(
        {"schema_version": "economics-explicit-inputs-v2", "input_revision": context.capacity_request.input_revision},
        snapshot, context,
    ).result_snapshot
    assert result["schema_version"] == "economics-partial-result-v1"
    assert "assumption_evidence" not in result
    assert result["branches"]["capacity"]["status"] == "AVAILABLE"
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"
    assert result["branches"]["raas"]["status"] == "NOT_CALCULATED"
    assert result["scenarios"] == []
    assert len(result["scenario_statuses"]) == 6
    assert all(item["npv_project"] is None for item in result["scenario_statuses"])
    assert result["c05"]["procurement_ready"] is False
    assert "raas_monthly_per_robot_gross" in result["branches"]["raas"]["required_fields"]


def test_visual_only_v4_builds_valid_spec_without_inventing_npv():
    from calculation.scheduling import SimulationReportV1, SimulationRequestV1, run_simulation
    from scenario_spec_v2 import ScenarioSpecV2

    snapshot, context = _context()
    raw = {"schema_version": INPUT_VERSION_V4, "input_revision": context.capacity_request.input_revision,
           "start_seconds_from_midnight": "28800", "timezone": "Europe/Moscow"}
    execution = execute_partial_economics_v2(raw, snapshot, context)
    result = execution.result_snapshot
    assert result["visualization"]["status"] == "AVAILABLE"
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"
    assert all(item["npv_project"] is None for item in result["scenario_statuses"])
    spec = ScenarioSpecV2.model_validate(execution.scenario_spec_snapshot)
    assert spec.analysis.capacity_run_id == context.capacity_response.run_id
    assert spec.finance is None
    assert execute_partial_economics_v2(raw, snapshot, context).scenario_spec_snapshot == execution.scenario_spec_snapshot
    simulation = SimulationRequestV1.model_validate({
        "schema_version": "simulation-request-v1", "request_id": "simulation.partial",
        "tenant_id": context.tenant_id, "project_id": context.project_id,
        "scenario_spec": execution.scenario_spec_snapshot, "mode": "DAILY",
        "peak_factor": None, "sla": None, "resources": [],
        "limits": {"max_jobs_per_day": 10000, "max_fleet": 100,
                   "max_runtime_seconds": 60, "progress_event_batch": 1000},
    })
    report = run_simulation(simulation)
    assert isinstance(report, SimulationReportV1)
    assert report.scenario_revision_id == spec.revision_id


def test_visual_v4_lists_missing_calendar_and_old_v2_keeps_historical_stub():
    snapshot, context = _context()
    raw = {"schema_version": INPUT_VERSION_V4, "input_revision": context.capacity_request.input_revision,
           "start_seconds_from_midnight": "28800"}
    execution = execute_partial_economics_v2(raw, snapshot, context)
    assert execution.scenario_spec_snapshot["schema_version"] == "scenario-spec-partial-v1"
    assert "timezone" in execution.scenario_spec_snapshot["required_fields"]
    old = execute_partial_economics_v2({**raw, "schema_version": "economics-explicit-inputs-v2", "timezone": "Europe/Moscow"}, snapshot, context)
    assert old.scenario_spec_snapshot["reason_code"] == "PARTIAL_FINANCIAL_INPUT"


def test_purchase_calculates_without_raas_tariff_or_recommendation():
    snapshot, context = _context()
    raw = _input()
    raw["raas_monthly_per_robot_gross"] = None
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["branches"]["purchase"]["status"] == "CALCULATED"
    assert result["branches"]["raas"]["status"] == "NOT_CALCULATED"
    assert len(result["scenarios"]) == 3
    assert {item["acquisition"] for item in result["scenarios"]} == {"PURCHASE"}
    assert all(item["recommendation"]["status"] == "NOT_CALCULATED" for item in result["scenarios"])
    assert all(item["procurement"]["procurement_ready"] is False for item in result["scenarios"])
    assert all(item["npv_project"] is None for item in result["scenario_statuses"] if item["acquisition"] == "RAAS")


def test_labour_calculates_without_purchase_inputs():
    snapshot, context = _context()
    raw = _input()
    raw["implementation_cost_total_gross"] = None
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["branches"]["labour"]["status"] == "CALCULATED"
    assert result["labour"]["status"] == "COMPLETE"
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"
    assert result["scenarios"] == []


def test_partial_mapping_does_not_call_missing_gross_explicit():
    raw = _input()
    raw["control_monthly_gross"] = None
    mapping = historical_mapping("economics-runtime-v2", {
        "schema_version": "economics-run-input-v3", "economics": raw,
    })
    assert mapping.fte_basis_status == "MISSING_GROSS"
    raw["control_monthly_gross"] = "100000"
    with_capacity_gross = historical_mapping("economics-runtime-v2", {
        "schema_version": "economics-run-input-v3", "economics": raw,
        "capacity_role_salaries_complete": True,
    })
    assert with_capacity_gross.fte_basis_status == "EXPLICIT_GROSS"


def test_invalid_money_and_units_do_not_become_zero():
    snapshot, context = _context()
    raw = _input()
    raw.update(average_power_w="100 kW", annual_service_per_robot_gross="-1",
               shared_site_capital_gross="0", raas_monthly_per_robot_gross=None)
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["scenarios"] == []
    assert {"average_power_w", "annual_service_per_robot_gross"} <= {
        item["field"] for item in result["issues"] if item["code"] == "INVALID_VALUE"
    }
    assert "shared_site_capital_gross" not in result["branches"]["purchase"]["required_fields"]


def test_honest_range_is_saved_without_choosing_a_midpoint():
    snapshot, context = _context()
    raw = _input()
    raw["implementation_cost_total_gross"] = "500000..800000"
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["input_ranges"]["implementation_cost_total_gross"] == {"min": "500000", "max": "800000"}
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"
    assert result["scenarios"] == []
    assert any(item["code"] == "RANGE_ONLY" for item in result["issues"])


def test_complete_v2_inputs_use_existing_full_engine():
    snapshot, context = _context()
    result = execute_partial_economics_v2(_input(), snapshot, context)
    assert result.result_snapshot["schema_version"] == "commercial-scenarios-bundle-v2"
    assert len(result.result_snapshot["scenarios"]) == 6


def _confirmed_demo_input():
    raw = _input()
    raw["schema_version"] = INPUT_VERSION_V3
    raw["field_sources"] = {field: "ASSUMPTION" for field in DEMO_SCENARIO["fields"]}
    raw["assumption_evidence"] = {}
    for field, proposal in DEMO_SCENARIO["fields"].items():
        raw[field] = proposal["value"]
        raw["assumption_evidence"][field] = {
            "schema_version": "scenario-assumption-evidence-v1",
            "template_id": DEMO_SCENARIO["schema_version"], "version": "v1",
            "source": DEMO_SCENARIO["source"], "rationale": proposal["rationale"],
            "published_on": DEMO_SCENARIO["published_on"],
            "confirmed_value": proposal["value"], "confirmed": True,
        }
    raw.update(DEMO_SCENARIO["other_inputs"])
    return raw


def test_confirmed_versioned_warehouse_demo_computes_six_scenarios_without_procurement_upgrade():
    snapshot, context = _context()
    raw = _confirmed_demo_input()
    result = execute_partial_economics_v2(raw, snapshot, context)
    assert result.result_snapshot["schema_version"] == "commercial-scenarios-bundle-v2"
    assert len(result.result_snapshot["scenarios"]) == 6
    assert all(item["procurement"]["procurement_status"] == "UNVERIFIED" for item in result.result_snapshot["scenarios"])
    assert context.constraint_report["eligibility"] == "NEEDS_VALIDATION"
    assert len(result.result_snapshot["sensitivity"]["variants"]) == 6


def test_confirmed_v4_demo_keeps_full_financial_and_visual_bundle():
    snapshot, context = _context()
    raw = _confirmed_demo_input()
    raw["schema_version"] = INPUT_VERSION_V4
    result = execute_partial_economics_v2(raw, snapshot, context)
    assert result.result_snapshot["schema_version"] == "commercial-scenarios-bundle-v2"
    assert len(result.result_snapshot["scenarios"]) == 6
    assert result.scenario_spec_snapshot["schema_version"] == "scenario-spec-v2"


def test_unconfirmed_or_modified_demo_value_stays_partial_and_never_substitutes_zero():
    snapshot, context = _context()
    raw = _confirmed_demo_input()
    raw["assumption_evidence"]["raas_monthly_per_robot_gross"]["confirmed"] = False
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["schema_version"] == "economics-partial-result-v1"
    assert result["branches"]["raas"]["status"] == "NOT_CALCULATED"
    assert any(item["code"] == "ASSUMPTION_UNCONFIRMED" for item in result["issues"])
    raw = _confirmed_demo_input()
    raw["implementation_cost_total_gross"] = "600000"
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"
    assert result["scenarios"] == []


def test_confirmed_custom_revision_changes_result_without_mutating_original_input():
    from copy import deepcopy

    snapshot, context = _context()
    original = _confirmed_demo_input()
    saved = deepcopy(original)
    first = execute_partial_economics_v2(original, snapshot, context).result_snapshot
    edited = deepcopy(original)
    edited["implementation_cost_total_gross"] = "600000"
    edited["assumption_evidence"]["implementation_cost_total_gross"] = {
        "schema_version": "scenario-assumption-evidence-v1", "template_id": None,
        "version": "custom-v1", "source": "USER", "rationale": "Изменено для нового сценария",
        "published_on": "2026-09-25", "confirmed_value": "600000", "confirmed": True,
    }
    second = execute_partial_economics_v2(edited, snapshot, context).result_snapshot
    first_npv = next(item for item in first["scenarios"] if item["acquisition"] == "PURCHASE" and item["uncertainty"] == "BASE")["financial"]["npv_project"]["value"]
    second_npv = next(item for item in second["scenarios"] if item["acquisition"] == "PURCHASE" and item["uncertainty"] == "BASE")["financial"]["npv_project"]["value"]
    assert first_npv != second_npv
    assert original == saved


def test_partial_replay_is_deterministic_and_keeps_c05():
    snapshot, context = _context()
    raw = _input()
    raw["raas_monthly_per_robot_gross"] = None
    first = execute_partial_economics_v2(raw, snapshot, context)
    second = execute_partial_economics_v2(raw, snapshot, context)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.result_snapshot["c05"]["eligibility"] == "NEEDS_VALIDATION"
    assert first.result_snapshot["c05"]["procurement_ready"] is False
@pytest.mark.parametrize("field", [key for key in _input() if key not in {"schema_version", "input_revision"}])
def test_each_optional_omission_has_a_structured_result(field):
    snapshot, context = _context()
    raw = _input()
    raw[field] = None
    execution = execute_partial_economics_v2(raw, snapshot, context)
    assert execution.result_snapshot["schema_version"] in {
        "economics-partial-result-v1", "commercial-scenarios-bundle-v2"
    }
