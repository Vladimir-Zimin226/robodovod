from __future__ import annotations

import copy
import json
import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import calculation.economics.sensitivity as sensitivity_module
import pytest
from calculation.economics.sensitivity import (
    SensitivityRequestV1,
    SensitivityResultV1,
    calculate_sensitivity,
)
from calculation.service import analyze_sensitivity
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> dict:
    return json.loads((ROOT / "contracts/fixtures/sensitivity-v1.golden.json").read_text(encoding="utf-8"))


def request() -> SensitivityRequestV1:
    return SensitivityRequestV1.model_validate(fixture()["request"])


def by_parameter(result: SensitivityResultV1, parameter: str, direction: str):
    return next(
        item for item in result.variants
        if item.override.parameter_id == parameter and item.override.direction == direction
    )


def test_golden_service_and_byte_stable_replay():
    data = fixture()
    value = SensitivityRequestV1.model_validate(data["request"])
    first = analyze_sensitivity(value)
    second = calculate_sensitivity(value)
    assert first.model_dump(mode="json") == data["result"] == second.model_dump(mode="json")
    SensitivityResultV1.model_validate(data["result"])


def test_orchestrator_reuses_canonical_allocation_engine_for_base_and_six_variants():
    with patch.object(
        sensitivity_module,
        "calculate_multiprocess_allocation",
        wraps=sensitivity_module.calculate_multiprocess_allocation,
    ) as engine:
        calculate_sensitivity(request())
    assert engine.call_count == 7


def test_exact_tornado_matrix_and_user_provenance():
    value = request()
    assert {(item.override.parameter_id, item.override.direction) for item in value.variants} == {
        (parameter, direction)
        for parameter in ("EQUIPMENT_PRICE", "OPERATION_VOLUME", "ROLE_SALARY")
        for direction in ("LOWER", "UPPER")
    }
    for item in value.variants:
        assert item.override.source == "USER"
        expected = Decimal("0.90") if item.override.direction == "LOWER" else Decimal("1.10")
        assert Decimal(item.override.variant_value) == Decimal(item.override.base_value) * expected


def test_price_and_salary_do_not_change_capacity_snapshots():
    value = request()
    baseline = [item.model_dump(mode="json") for item in value.baseline_capacity_bindings]
    for variant in value.variants:
        if variant.override.parameter_id in ("EQUIPMENT_PRICE", "ROLE_SALARY"):
            assert [item.model_dump(mode="json") for item in variant.capacity_bindings] == baseline
    result = calculate_sensitivity(value)
    for variant in result.variants:
        if variant.override.parameter_id in ("EQUIPMENT_PRICE", "ROLE_SALARY"):
            assert variant.capacity_fleet_delta == 0


def test_volume_can_cross_discrete_fleet_threshold_and_reason_is_traced():
    result = calculate_sensitivity(request())
    lower = by_parameter(result, "OPERATION_VOLUME", "LOWER")
    upper = by_parameter(result, "OPERATION_VOLUME", "UPPER")
    assert lower.capacity_fleet_delta == 0
    assert "no-discrete-fleet-step" in lower.step_reasons
    assert upper.capacity_fleet_delta == 1
    assert "discrete-fleet-step" in upper.step_reasons
    assert upper.project_capex.delta_value == "2500000.00"


def test_each_delta_links_base_override_engine_and_variant_result():
    value = request()
    result = calculate_sensitivity(value)
    for variant in result.variants:
        assert variant.status == "COMPLETE"
        assert variant.allocation_result_digest is not None
        assert variant.npv_project.delta_value is not None
        nodes = [item for item in result.trace if variant.variant_id in item.node_id]
        assert {item.operation for item in nodes} == {"APPLY_OVERRIDE", "RERUN_ENGINE", "COMPARE_DELTA"}
    assert result.replay.baseline_allocation_result_digest == value.baseline_allocation_result_digest
    assert len(result.replay.variant_allocation_result_digests) == 6


def test_blocked_variant_has_no_synthetic_financial_result():
    raw = request().model_dump(mode="json")
    variant = next(item for item in raw["variants"] if item["variant_id"] == "variant.operation_volume.upper")
    variant["status"] = "BLOCKED"
    variant["allocation_request"] = None
    variant["blocker_codes"] = ["capacity-variant-missing-required-input"]
    value = SensitivityRequestV1.model_validate(raw)
    result = calculate_sensitivity(value)
    blocked = by_parameter(result, "OPERATION_VOLUME", "UPPER")
    assert blocked.status == "BLOCKED"
    assert blocked.allocation_result_digest is None
    assert blocked.npv_project.status == "BLOCKED"
    assert blocked.npv_project.delta_value is None


def test_baseline_is_immutable_and_reorder_is_deterministic():
    value = request()
    before = value.baseline_allocation_result.model_dump(mode="json")
    expected = calculate_sensitivity(value).model_dump(mode="json")
    raw = value.model_dump(mode="json")
    raw["variants"].reverse()
    actual = calculate_sensitivity(SensitivityRequestV1.model_validate(raw)).model_dump(mode="json")
    assert actual == expected
    assert value.baseline_allocation_result.model_dump(mode="json") == before


def test_tenant_and_cohort_isolation_reject_variant_escape():
    raw = request().model_dump(mode="json")
    raw["variants"][0]["allocation_request"]["tenant_id"] = "tenant.other"
    with pytest.raises(ValidationError, match="identity/revision mismatch|escaped baseline"):
        SensitivityRequestV1.model_validate(raw)
    raw = request().model_dump(mode="json")
    raw["variants"][0]["allocation_request"]["cohort_id"] = "cohort.other"
    with pytest.raises(ValidationError, match="escaped baseline"):
        SensitivityRequestV1.model_validate(raw)


def test_negative_fixture_contract_guards():
    negative = json.loads(
        (ROOT / "contracts/fixtures/sensitivity-v1.negative.json").read_text(encoding="utf-8")
    )
    for case in negative["invalid"]:
        with pytest.raises(ValidationError, match=re.escape(case["error_contains"])):
            SensitivityRequestV1.model_validate(case["request"])


def test_replay_rejects_tampered_immutable_baseline():
    raw = request().model_dump(mode="json")
    raw["baseline_allocation_result"]["npv_project"]["value"] = "1.00"
    raw["baseline_allocation_result_digest"] = sensitivity_module._digest(raw["baseline_allocation_result"])
    value = SensitivityRequestV1.model_validate(raw)
    with pytest.raises(ValueError, match="does not replay"):
        calculate_sensitivity(value)


def test_schemas_are_strict_and_unknown_fields_are_rejected():
    for name in ("sensitivity-request-v1.schema.json", "sensitivity-result-v1.schema.json"):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
    raw = copy.deepcopy(fixture()["request"])
    raw["client_calculated_npv"] = "999"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SensitivityRequestV1.model_validate(raw)
