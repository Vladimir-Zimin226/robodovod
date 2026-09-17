from fastapi.testclient import TestClient

from fleet import as_dicts
from main import app
from models import UserInput
from readiness import evaluate_equipment_constraints, evaluate_readiness


ROBOTS = as_dicts()


def _input(**updates) -> UserInput:
    values = {
        "object_type": "retail",
        "process_type": "transport",
        "cargo_type": "pallets",
        "pallets_per_day": 500,
        "aisle_width_m": 2.0,
        "payload_kg": 800,
        "shifts_count": 2,
        "shift_hours": 8,
        "staff_headcount": 12,
        "fte_cost_rub": 1_500_000,
    }
    values.update(updates)
    return UserInput(**values)


def _robot(robot_id: str) -> dict:
    return next(item for item in ROBOTS if item["id"] == robot_id)


def _constraint(candidate, code: str):
    return next(item for item in candidate.hard_constraints if item.code == code)


def test_missing_critical_geometry_is_unknown_and_needs_validation():
    report = evaluate_readiness(
        _input(aisle_width_m=None),
        ROBOTS,
    )

    geometry = next(
        check
        for dimension in report.dimensions
        for check in dimension.checks
        if check.code == "AISLE_GEOMETRY"
    )
    candidate = next(
        item for item in report.technical_candidates
        if item.equipment_model_id == "amr_heavy_1350"
    )

    assert report.overall_status == "NEEDS_VALIDATION"
    assert geometry.status == "UNKNOWN"
    assert geometry.available is None
    assert geometry.evidence == []
    assert candidate.status == "NEEDS_VALIDATION"
    assert _constraint(candidate, "AISLE_WIDTH").status == "UNKNOWN"
    assert "AISLE_WIDTH" in candidate.critical_unknowns
    assert report.architecture_candidates[0].status == "NEEDS_VALIDATION"


def test_payload_and_aisle_failures_are_structured_hard_rejects():
    candidate = evaluate_equipment_constraints(
        _input(payload_kg=1_600, aisle_width_m=0.7),
        _robot("amr_heavy_1350"),
    )

    payload = _constraint(candidate, "PAYLOAD")
    aisle = _constraint(candidate, "AISLE_WIDTH")
    assert candidate.status == "REJECTED"
    assert payload.status == "FAIL"
    assert payload.required.value == 1_600
    assert payload.available.value == 1_350
    assert payload.reason_code == "PAYLOAD_EXCEEDED"
    assert aisle.status == "FAIL"
    assert aisle.reason_code == "AISLE_TOO_NARROW"
    assert set(candidate.rejection_reasons) >= {"PAYLOAD_EXCEEDED", "AISLE_TOO_NARROW"}


def test_unknown_payload_never_uses_legacy_default_or_becomes_pass():
    candidate = evaluate_equipment_constraints(
        _input(payload_kg=None),
        _robot("amr_light_250"),
    )

    payload = _constraint(candidate, "PAYLOAD")
    assert payload.status == "UNKNOWN"
    assert payload.required is None
    assert payload.available.value == 250
    assert candidate.status == "NEEDS_VALIDATION"


def test_assumption_is_visible_and_is_not_counted_as_evidence_pass():
    report = evaluate_readiness(
        _input(shifts_count=None, shift_hours=None),
        ROBOTS,
    )
    schedule = next(
        check
        for dimension in report.dimensions
        for check in dimension.checks
        if check.code == "OPERATING_SCHEDULE"
    )

    assert schedule.status == "ASSUMED"
    assert schedule.available.value == {"shifts": 2, "hours": 8}
    assert schedule.evidence[0].kind == "ASSUMPTION"
    assert schedule.reason_code == "DEFAULT_OPERATING_SCHEDULE"


def test_critical_operating_failure_blocks_architecture_independently_of_score():
    report = evaluate_readiness(
        _input(shifts_count=3, shift_hours=10),
        ROBOTS,
    )

    assert report.overall_status == "NOT_READY"
    assert report.blockers == ["Суммарная длительность смен превышает 24 часа."]
    assert report.score > 0
    assert report.architecture_candidates[0].status == "BLOCKED"


def test_architecture_selection_precedes_sku_and_has_alternatives():
    report = evaluate_readiness(_input(), ROBOTS)

    assert [item.architecture_id for item in report.architecture_candidates] == [
        "PALLET_TRANSPORT_AMR",
        "FIXED_PATH_AGV",
        "AUTONOMOUS_FORKLIFT",
    ]
    assert report.architecture_candidates[0].fit_score > report.architecture_candidates[1].fit_score
    assert report.architecture_candidates[0].status == "RECOMMENDED"


def test_file_parameter_evidence_enables_infrastructure_checks():
    report = evaluate_readiness(
        _input(),
        ROBOTS,
        parameter_values={
            "nalichie_wms": "Да",
            "moschnost_elektrosnabzheniya_dostupnaya": 500,
        },
        parameter_provenance={
            "nalichie_wms": {"kind": "FILE", "source": {"sheet": "Склад", "row": 42}},
            "moschnost_elektrosnabzheniya_dostupnaya": {"kind": "FILE", "source": {"sheet": "Склад", "row": 41}},
        },
    )
    checks = {
        check.code: check
        for dimension in report.dimensions
        for check in dimension.checks
    }

    assert checks["IT_INTEGRATION"].status == "PASS"
    assert checks["IT_INTEGRATION"].evidence[0].kind == "FILE"
    assert checks["CHARGING_POWER"].status == "PASS"


def test_same_input_and_rules_produce_identical_report():
    first = evaluate_readiness(_input(), ROBOTS).model_dump(mode="json")
    second = evaluate_readiness(_input(), ROBOTS).model_dump(mode="json")
    assert first == second


def test_readiness_endpoint_exposes_versioned_contract_without_changing_calculate():
    response = TestClient(app).post(
        "/api/readiness",
        json={"input": _input().model_dump(mode="json")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "readiness-report-v1"
    assert payload["rules_version"] == "readiness-rules-v1"
    assert payload["architecture_candidates"][0]["architecture_id"] == "PALLET_TRANSPORT_AMR"
    assert payload["technical_candidates"]
