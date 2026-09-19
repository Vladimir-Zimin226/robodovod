from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation_contracts import (
    CalculationDecisionFixtures,
    CalculationSemanticsFixture,
    CalculationSemanticsManifest,
    CalculationTrace,
    CapacityAnalysisErrorResponse,
    CapacityAnalysisRequest,
    CapacityResult,
    KnownQuantity,
    NormalizedProcess,
    PartialCalculationResult,
    RolePool,
    calculation_trace_digest,
    semantic_digest,
)
from models import ScenarioSpec

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts" / "fixtures"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_calculation_contracts import expected_files  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_generated_schemas_and_fixtures_are_exact():
    stale = [
        str(path.relative_to(ROOT))
        for path, expected in expected_files()
        if not path.is_file() or path.read_bytes() != expected
    ]
    assert stale == []


def test_complete_fixture_roundtrips_and_keeps_independent_partial_statuses():
    raw = _load("calculation-semantics-v1.complete.json")
    fixture = CalculationSemanticsFixture.model_validate(raw)
    assert fixture.model_dump(mode="json") == raw
    assert fixture.result.capacity.status == "WITH_ASSUMPTIONS"
    assert fixture.result.financial.status == "INCOMPLETE"
    assert fixture.result.capacity.value is not None
    assert fixture.result.financial.value is None
    assert calculation_trace_digest(fixture.trace) == fixture.trace.replay.trace_content_digest
    assert {item.kind for item in fixture.trace.provenance} == {
        "USER",
        "VENDOR_FACT",
        "ASSUMPTION",
    }


def test_capacity_only_fixture_does_not_require_finance():
    raw = _load("calculation-partial-result-v1.capacity-only.json")
    result = PartialCalculationResult.model_validate(raw)
    assert result.result_status == "CAPACITY_ONLY"
    assert result.capacity.value is not None
    assert result.financial is None


def test_future_capacity_api_contract_is_additive_and_has_typed_errors():
    complete = _load("calculation-semantics-v1.complete.json")
    request = CapacityAnalysisRequest.model_validate(
        {
            "schema_version": "capacity-analysis-request-v2",
            "project_id": "project.contract-fixture",
            "input_revision": complete["normalized_process"]["input_revision"],
            "process": complete["normalized_process"],
            "role_pool": None,
            "model_id": "synthetic-contract-model",
            "position_id": "synthetic-contract-position",
            "acquisition": "PURCHASE",
            "uncertainty": "BASE",
        }
    )
    assert "financial" not in request.model_dump(mode="json")

    error = CapacityAnalysisErrorResponse.model_validate(
        _load("capacity-analysis-error-v1.blocked.json")
    )
    assert error.error_code == "CALCULATION_BLOCKED"
    assert error.partial_capacity.status == "BLOCKED"


def test_blocked_trace_has_null_result_and_no_unsafe_fallback():
    raw = _load("calculation-trace-v1.blocked-missing-speed.json")
    trace = CalculationTrace.model_validate(raw)
    speed = next(item for item in trace.inputs if item.name == "operating_speed")
    assert speed.status == "MISSING"
    assert speed.missing_reason == "MISSING_SAFE_FACT"
    assert trace.results[0].status == "BLOCKED"
    assert trace.results[0].value is None
    assert calculation_trace_digest(trace) == trace.replay.trace_content_digest


def test_k02_k03_k04_examples_are_versioned_and_unambiguous():
    fixture = CalculationDecisionFixtures.model_validate(
        _load("calculation-decision-fixtures-v1.json")
    )
    assert [item.expected_total_seconds for item in fixture.k02_exchange] == [
        "45",
        "90",
        "90",
    ]
    assert [item.legacy_migration for item in fixture.k02_exchange] == [
        False,
        False,
        True,
    ]
    assert [item.expected_batch for item in fixture.k03_batch] == [3, 2, None]
    zero = fixture.k04_capacity[0]
    assert (zero.expected_capacity, zero.expected_coverage) == ("0", "0")
    assert zero.expected_utilization is None
    assert zero.expected_status == "OVERLOADED"


def test_quantity_rejects_wrong_kind_unit_and_wrong_semantic_unit():
    base = {
        "status": "KNOWN",
        "name": "one_way_distance",
        "raw_value": "120",
        "raw_unit": "m",
        "normalized_value": "120",
        "unit": "m",
        "quantity_kind": "DISTANCE",
        "numeric_encoding": "DECIMAL_STRING",
        "provenance_ref": "prov.user",
    }
    assert KnownQuantity.model_validate(base).normalized_value == "120"
    with pytest.raises(ValidationError, match="incompatible with quantity_kind"):
        KnownQuantity.model_validate({**base, "quantity_kind": "TIME"})
    with pytest.raises(ValidationError, match="must normalize"):
        KnownQuantity.model_validate(
            {
                **base,
                "name": "shift_hours",
                "raw_unit": "m",
                "unit": "m",
            }
        )
    with pytest.raises(ValidationError):
        KnownQuantity.model_validate({**base, "normalized_value": 120})


def test_normalized_process_rejects_unknown_fields_invalid_schedule_and_zero_demand():
    raw = _load("calculation-semantics-v1.complete.json")["normalized_process"]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        NormalizedProcess.model_validate({**raw, "legacy_default": 45})

    invalid_schedule = copy.deepcopy(raw)
    invalid_schedule["schedule"]["shifts_per_day"]["raw_value"] = "3"
    invalid_schedule["schedule"]["shifts_per_day"]["normalized_value"] = "3"
    invalid_schedule["schedule"]["shift_hours"]["raw_value"] = "12"
    invalid_schedule["schedule"]["shift_hours"]["normalized_value"] = "12"
    with pytest.raises(ValidationError, match="cannot exceed 24"):
        NormalizedProcess.model_validate(invalid_schedule)

    zero = copy.deepcopy(raw)
    zero["demand"]["raw_value"] = "0"
    zero["demand"]["normalized_value"] = "0"
    with pytest.raises(ValidationError, match="demand must be positive"):
        NormalizedProcess.model_validate(zero)

    silent_relabel = copy.deepcopy(raw)
    silent_relabel["quantity_kind"] = "DELIVERY"
    with pytest.raises(ValidationError, match="does not match process quantity_kind"):
        NormalizedProcess.model_validate(silent_relabel)


def test_exchange_is_a_discriminated_union_without_double_count_path():
    raw = _load("calculation-semantics-v1.complete.json")["normalized_process"]
    both = copy.deepcopy(raw)
    both["exchange"]["load_time"] = both["exchange"]["total_time"]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        NormalizedProcess.model_validate(both)

    half_split = copy.deepcopy(raw)
    half_split["exchange"] = {
        "mode": "SPLIT",
        "load_time": {
            **raw["exchange"]["total_time"],
            "name": "load_time",
        },
    }
    with pytest.raises(ValidationError):
        NormalizedProcess.model_validate(half_split)


def test_role_identity_is_object_scoped_and_salary_has_no_hidden_default():
    raw = _load("calculation-semantics-v1.complete.json")["role_pool"]
    pool = RolePool.model_validate(raw)
    assert pool.roles[0].monthly_gross_salary.status == "MISSING"

    duplicate = copy.deepcopy(raw)
    duplicate["roles"].append(copy.deepcopy(duplicate["roles"][0]))
    duplicate["roles"][1]["role_id"] = "warehouse.forklift-driver-copy"
    with pytest.raises(ValidationError, match="object-scoped"):
        RolePool.model_validate(duplicate)

    zero_salary = copy.deepcopy(raw)
    zero_salary["roles"][0]["monthly_gross_salary"] = {
        "status": "KNOWN",
        "name": "monthly_gross_salary",
        "raw_value": "0",
        "raw_unit": "RUB/person/month",
        "normalized_value": "0",
        "unit": "RUB/person/month",
        "quantity_kind": "MONEY",
        "numeric_encoding": "DECIMAL_STRING",
        "provenance_ref": "prov.user",
    }
    with pytest.raises(ValidationError, match="ZERO_COST_ROLE"):
        RolePool.model_validate(zero_salary)


def test_result_status_nullability_is_strict_and_zero_fleet_has_no_nan_semantics():
    raw = _load("calculation-semantics-v1.complete.json")["result"]["capacity"]
    blocked = copy.deepcopy(raw)
    blocked["status"] = "BLOCKED"
    with pytest.raises(ValidationError, match="null value"):
        CapacityResult.model_validate(blocked)

    zero = copy.deepcopy(raw)
    zero["value"].update(
        {
            "selected_fleet": 0,
            "effective_capacity": {
                "value": "0",
                "unit": "unit/h",
                "quantity_kind": "RATE",
                "numeric_encoding": "DECIMAL_STRING",
            },
            "coverage": {
                "value": "0",
                "unit": "1",
                "quantity_kind": "FRACTION",
                "numeric_encoding": "DECIMAL_STRING",
            },
            "raw_load_ratio": None,
            "utilization": None,
            "overloaded": True,
        }
    )
    parsed = CapacityResult.model_validate(zero)
    assert parsed.value.utilization is None


def test_forbidden_vendor_fact_status_and_unknown_versions_are_rejected():
    raw = _load("calculation-semantics-v1.complete.json")["trace"]
    unsafe = copy.deepcopy(raw)
    vendor = next(item for item in unsafe["provenance"] if item["kind"] == "VENDOR_FACT")
    vendor["evidence_status"] = "CONFLICT"
    with pytest.raises(ValidationError):
        CalculationTrace.model_validate(unsafe)

    unknown = copy.deepcopy(raw)
    unknown["versions"]["precision_policy_version"] = "future-policy-v9"
    with pytest.raises(ValidationError):
        CalculationTrace.model_validate(unknown)


def test_trace_requires_topological_order_and_semantic_digest_ignores_runtime_only_metadata():
    raw = _load("calculation-semantics-v1.complete.json")["trace"]
    reordered = copy.deepcopy(raw)
    reordered["formula_nodes"][0], reordered["formula_nodes"][1] = (
        reordered["formula_nodes"][1],
        reordered["formula_nodes"][0],
    )
    with pytest.raises(ValidationError, match="topological order"):
        CalculationTrace.model_validate(reordered)

    trace = CalculationTrace.model_validate(raw)
    changed_runtime = trace.model_copy(
        update={
            "runtime_metadata": trace.runtime_metadata.model_copy(
                update={"build_id": "another-build", "runtime_id": "x"}
            )
        }
    )
    assert calculation_trace_digest(trace) == calculation_trace_digest(changed_runtime)
    assert semantic_digest({"a": "е\u0308", "b": 1}) == semantic_digest(
        {"b": 1, "a": "ё"}
    )


def test_manifest_and_legacy_scenario_contract_both_validate():
    manifest = CalculationSemanticsManifest.model_validate(
        json.loads(
            (ROOT / "contracts" / "calculation-semantics-manifest-v1.json").read_text(
                encoding="utf-8"
            )
        )
    )
    assert len(manifest.source_parameter_map) == 7
    assert manifest.compatibility[0].mode == "UNCHANGED"
    assert manifest.capacity_api.path == "/api/v2/capacity-analyses"
    assert manifest.capacity_api.legacy_path_unchanged == "/api/calculate"

    legacy = json.loads(
        (FIXTURES / "scenario-spec-v1.golden.json").read_text(encoding="utf-8")
    )
    assert ScenarioSpec.model_validate(legacy).model_dump(mode="json") == legacy
