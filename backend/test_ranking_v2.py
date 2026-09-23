from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from calculation.ranking import (
    RankingRequestV2,
    RankingResultV2,
    _digest,
    _piecewise,
    calculate_ranking,
)
from calculation.service import analyze_ranking
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> dict:
    return json.loads((ROOT / "contracts/fixtures/ranking-v2.golden.json").read_text(encoding="utf-8"))


def request() -> RankingRequestV2:
    return RankingRequestV2.model_validate(fixture()["request"])


def redigest(candidate: dict) -> None:
    candidate["constraint_report_digest"] = _digest(candidate["constraint_report"])
    candidate["executability_digest"] = _digest(candidate["executability"])


def check(candidate: dict, check_id: str) -> dict:
    return next(item for item in candidate["constraint_report"]["checks"] if item["check_id"] == check_id)


def test_golden_service_contract_and_byte_stable_replay():
    data = fixture()
    value = RankingRequestV2.model_validate(data["request"])
    first = analyze_ranking(value)
    second = calculate_ranking(value)
    assert first.model_dump(mode="json") == data["result"] == second.model_dump(mode="json")
    RankingResultV2.model_validate(data["result"])
    assert first.technical_recommendation.candidate_id is not None
    assert first.financial_recommendation.status == "RECOMMENDED"


@pytest.mark.parametrize(("value", "expected"), [
    ("0.4", "0"), ("0.55", "0.5"), ("0.7", "0.8"), ("0.85", "1"), ("0.92", "0.9"), ("1", "0.5"),
])
def test_availability_knots(value: str, expected: str):
    knots = [(Decimal(".4"), Decimal(0)), (Decimal(".55"), Decimal(".5")),
             (Decimal(".7"), Decimal(".8")), (Decimal(".85"), Decimal(1)),
             (Decimal(".92"), Decimal(".9")), (Decimal(1), Decimal(".5"))]
    assert _piecewise(Decimal(value), knots) == Decimal(expected)


def test_aisle_payload_and_trl_boundary_values_are_explicit():
    result = calculate_ranking(request())
    beta = next(item for item in result.candidates if item.candidate_id == "candidate.beta")
    values = {item.component_id: item.normalized_value for item in beta.applicability_components}
    assert values["availability"] == "1"
    assert values["aisle_margin"] == "0.7"
    assert values["payload_margin"] == "1"
    assert values["trl"] == "1"


def test_equal_npv_is_neutral_50_for_every_complete_candidate():
    raw = request().model_dump(mode="json")
    for candidate in raw["candidates"]:
        candidate["npv_project"] = "100"
    result = calculate_ranking(RankingRequestV2.model_validate(raw))
    assert {item.economy_score for item in result.candidates} == {"50.00"}


def test_all_negative_cohort_has_scores_but_no_false_financial_best():
    raw = request().model_dump(mode="json")
    for index, candidate in enumerate(raw["candidates"], 1):
        candidate["npv_project"] = str(-index * 100)
    result = calculate_ranking(RankingRequestV2.model_validate(raw))
    assert all(item.final_score is not None for item in result.candidates)
    assert result.financial_recommendation.status == "NO_POSITIVE_CASE"
    assert result.financial_recommendation.candidate_id is None
    assert "all-complete-npv-non-positive" in result.warnings


def test_hard_fail_is_excluded_before_scoring():
    raw = request().model_dump(mode="json")
    candidate = raw["candidates"][0]
    candidate["constraint_report"]["eligibility"] = "BLOCKED"
    candidate["constraint_report"]["blocker_codes"] = ["payload-failed"]
    redigest(candidate)
    result = calculate_ranking(RankingRequestV2.model_validate(raw))
    excluded = next(item for item in result.candidates if item.candidate_id == candidate["candidate_id"])
    assert excluded.eligibility == "EXCLUDED"
    assert excluded.technical_score is None and excluded.final_score is None and excluded.rank is None


def test_incomplete_finance_keeps_separate_technical_ordering_without_full_score():
    raw = request().model_dump(mode="json")
    candidate = raw["candidates"][1]
    candidate.update({"finance_status": "INCOMPLETE", "npv_project": None})
    result = calculate_ranking(RankingRequestV2.model_validate(raw))
    partial = next(item for item in result.candidates if item.candidate_id == candidate["candidate_id"])
    assert partial.eligibility == "TECHNICAL_ONLY"
    assert partial.technical_score is not None
    assert partial.economy_score is None and partial.final_score is None


def test_unverified_data_counts_half_but_never_becomes_matching_safe():
    raw = request().model_dump(mode="json")
    for field in raw["candidates"][0]["data_fields"]:
        field.update({"status": "UNVERIFIED", "matching_safe": False})
    result = calculate_ranking(RankingRequestV2.model_validate(raw))
    row = next(item for item in result.candidates if item.candidate_id == "candidate.alpha")
    assert Decimal(row.data_score.value) == Decimal(50)
    invalid = copy.deepcopy(raw)
    invalid["candidates"][0]["data_fields"][0]["matching_safe"] = True
    with pytest.raises(ValidationError, match="cannot become matching-safe"):
        RankingRequestV2.model_validate(invalid)


def test_full_data_denominator_is_77_and_all_na_is_not_fake_zero():
    result = calculate_ranking(request())
    assert all(item.data_score.denominator == "77" for item in result.candidates)
    raw = request().model_dump(mode="json")
    for field in raw["candidates"][0]["data_fields"]:
        field.update({"status": "N_A", "matching_safe": False, "provenance_ref": None})
    result = calculate_ranking(RankingRequestV2.model_validate(raw))
    row = next(item for item in result.candidates if item.candidate_id == "candidate.alpha")
    assert row.data_score.status == "N_A" and row.data_score.value is None


def test_integrations_are_advisory_fraction_not_hard_fail():
    raw = request().model_dump(mode="json")
    candidate = raw["candidates"][0]
    integration = check(candidate, "integrations")
    integration.update({"applicable": True, "status": "PASS", "reason_code": "integration-coverage-scored",
                        "required": {"value": ["wms", "erp"], "unit": None, "source_ref": "input:integrations"},
                        "available": {"value": ["wms"], "unit": None, "source_ref": "catalog:integrations"}})
    candidate["integrations"] = {"required_ids": ["erp", "wms"], "supported_matching_safe_ids": ["wms"],
                                 "unknown_ids": ["erp"], "provenance_refs": ["catalog.integrations"]}
    redigest(candidate)
    result = calculate_ranking(RankingRequestV2.model_validate(raw))
    row = next(item for item in result.candidates if item.candidate_id == "candidate.alpha")
    component = next(item for item in row.applicability_components if item.component_id == "integrations")
    assert component.normalized_value == "0.5"
    assert row.eligibility == "FULL"


def test_penalty_only_applies_to_amr_pallet_flow_above_5000():
    result = calculate_ranking(request())
    gamma = next(item for item in result.candidates if item.candidate_id == "candidate.gamma")
    assert gamma.penalty == "-5.00"
    raw = request().model_dump(mode="json")
    raw["candidates"][2]["penalty_context"]["equipment_class"] = "FORKLIFT"
    no_penalty = calculate_ranking(RankingRequestV2.model_validate(raw))
    gamma = next(item for item in no_penalty.candidates if item.candidate_id == "candidate.gamma")
    assert gamma.penalty == "0.00"


def test_reorder_and_ties_are_deterministic_including_replay():
    raw = request().model_dump(mode="json")
    for candidate in raw["candidates"]:
        candidate["npv_project"] = "100"
    baseline = calculate_ranking(RankingRequestV2.model_validate(raw))
    raw["candidates"].reverse()
    reordered = calculate_ranking(RankingRequestV2.model_validate(raw))
    assert baseline.model_dump(mode="json") == reordered.model_dump(mode="json")
    tied = sorted(baseline.candidates, key=lambda item: (item.rank or 999, item.candidate_id))
    assert [item.rank for item in tied] == sorted(item.rank for item in tied)


def test_versioned_rule_set_cannot_be_replaced_by_literal_23_or_31_count():
    raw = request().model_dump(mode="json")
    raw["candidates"][0]["constraint_report"]["checks"].pop()
    redigest(raw["candidates"][0])
    with pytest.raises(ValueError, match="exact ordered versioned C05 rule set"):
        calculate_ranking(RankingRequestV2.model_validate(raw))


def test_negative_fixture_and_strict_schemas():
    negative = json.loads((ROOT / "contracts/fixtures/ranking-v2.negative.json").read_text(encoding="utf-8"))
    for case in negative["invalid"]:
        with pytest.raises(ValidationError, match=case["error_contains"]):
            RankingRequestV2.model_validate(case["request"])
    for name in ("ranking-request-v2.schema.json", "ranking-result-v2.schema.json"):
        schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
