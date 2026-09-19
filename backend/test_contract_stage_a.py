import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from economics import SCENARIOS, _fleet_sizing, calc_recommendation, calc_zone
from main import calculate_with_catalog
from models import ScenarioSpec, UserInput, Zone
from test_robot_fixtures import synthetic_robot, synthetic_snapshot


def calculate(inp: UserInput):
    return calculate_with_catalog(inp, synthetic_snapshot())


ROOT = Path(__file__).resolve().parents[1]
ECONOMICS_FIXTURE_V1_SHA256 = "f7edc1b39715a5f2b0c8d618816a5fbfaec46cec4bcc48b4e9a445ca144d72dd"
SCENARIO_FIXTURE_V1_SHA256 = "18ab263b610c6a40b49ac264b26f2008865744dee26497f774c0ff2987ab0d99"
ECONOMICS_FIXTURE_V2_SHA256 = "6885e39ccfbc97512a3e12c0e80d7f63f30618267bcc8117d0ebbcea1714a2a2"
SCENARIO_FIXTURE_ECONOMICS_V2_SHA256 = "36ac851ea15509590a2d5cc007ecb5c3140cceac15f8e878f7506e076a8a8e04"


def _semantic_fixture_hash(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_unknown_input_fields_are_rejected_at_every_level():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        UserInput(process_type="transport", pallets_per_day=10, typo_field=1)

    with pytest.raises(ValidationError, match="extra_forbidden"):
        UserInput(
            mode="zonal",
            zones=[{"id": "A", "volume_per_day": 10, "typo_field": 1}],
        )

def test_zone_ids_must_be_unique():
    with pytest.raises(ValidationError, match="zone.id должны быть уникальны"):
        UserInput(
            mode="zonal",
            zones=[
                Zone(id="A", volume_per_day=10),
                Zone(id="A", volume_per_day=20),
            ],
        )


def test_units_per_trip_from_input_changes_whole_and_zonal_sizing():
    robot = synthetic_robot("light")
    one = UserInput(
        object_type="retail", process_type="transport", cargo_type="boxes",
        pallets_per_day=600, avg_distance_m=100, units_per_trip=1,
    )
    ten = one.model_copy(update={"units_per_trip": 10})
    qty_one, _ = _fleet_sizing(one, robot, SCENARIOS["base"]["utilization"])
    qty_ten, _ = _fleet_sizing(ten, robot, SCENARIOS["base"]["utilization"])
    assert qty_ten < qty_one

    shared = UserInput(object_type="retail", mode="zonal")
    zone_one = Zone(
        id="boxes", process_type="transport", cargo_type="boxes",
        volume_per_day=600, avg_distance_m=100, units_per_trip=1,
    )
    zone_ten = zone_one.model_copy(update={"units_per_trip": 10})
    assert calc_zone(shared, zone_ten, [robot]).recommendations[0].quantity < (
        calc_zone(shared, zone_one, [robot]).recommendations[0].quantity
    )


def test_fte_replace_per_shift_is_an_explicit_labor_cap():
    inp = UserInput(
        object_type="clinic", process_type="delivery", cargo_type="deliveries",
        pallets_per_day=30, shifts_count=2, shift_hours=8,
        staff_headcount=100, min_pult_fte_per_shift=0,
    )
    robot = synthetic_robot("delivery")
    robot["economics"]["fte_replace_per_shift"] = 0.2
    low = calc_recommendation(inp, robot)
    robot_high = copy.deepcopy(robot)
    robot_high["economics"]["fte_replace_per_shift"] = 2.0
    high = calc_recommendation(inp, robot_high)
    assert low.fte_displaced < high.fte_displaced


def test_zone_without_equipment_has_explicit_status_and_no_best():
    inp = UserInput(
        object_type="retail",
        mode="zonal",
        zones=[Zone(id="clean", process_type="cleaning", area_m2=1000)],
    )
    response = calculate(inp)
    zone = response.zones[0]
    assert zone.status == "NO_ELIGIBLE_EQUIPMENT"
    assert zone.status_message
    assert zone.best_robot_id is None
    assert response.scenario_spec.zones[0].status == "NO_ELIGIBLE_EQUIPMENT"
    assert response.scenario_spec.fleet == []


def test_zonal_scenario_is_calculated_and_revision_is_atomic():
    response = calculate(UserInput(**{
        "object_type": "retail",
        "mode": "zonal",
        "fte_cost_rub": 1_674_000,
        "zones": [{
            "id": "receiving",
            "name": "Приёмка",
            "process_type": "transport",
            "cargo_type": "boxes",
            "volume_per_day": 600,
            "avg_distance_m": 100,
            "payload_kg": 20,
            "units_per_trip": 10
        }]
    }))
    assert response.mode == "zonal"
    assert response.revision_id == response.scenario_spec.revision_id
    assert response.scenario_spec.task_profiles[0].units_per_trip == 10
    assert response.scenario_spec.fleet


def test_unacceptable_economics_is_not_marked_best():
    response = calculate(UserInput(
        object_type="retail", process_type="transport", cargo_type="pallets",
        pallets_per_day=10, fte_cost_rub=1, staff_headcount=1,
    ))
    assert response.recommendations
    assert all(not rec.is_best for rec in response.recommendations)
    assert all(rec.economic_status == "NOT_ACCEPTABLE" for rec in response.recommendations)
    assert response.warnings
    assert response.scenario_spec.economics.status == "NOT_ACCEPTABLE"
    assert len(response.scenario_spec.fleet) == 1
    assert len(response.scenario_spec.task_profiles) == 1
    assert response.scenario_spec.zones[0].status == "NO_ACCEPTABLE_ECONOMICS"
    assert any(
        item.code == "VISUALIZATION_ONLY_NOT_RECOMMENDATION"
        for item in response.scenario_spec.assumptions
    )


def test_legacy_golden_fixtures_remain_immutable():
    economics_path = ROOT / "backend" / "fixtures" / "economics-warehouse-v1.json"
    scenario_path = ROOT / "contracts" / "fixtures" / "scenario-spec-v1.golden.json"
    assert _semantic_fixture_hash(economics_path) == ECONOMICS_FIXTURE_V1_SHA256
    assert _semantic_fixture_hash(scenario_path) == SCENARIO_FIXTURE_V1_SHA256


def test_synthetic_calculation_and_scenario_spec_are_deterministic():
    economics_path = ROOT / "backend" / "fixtures" / "economics-warehouse-v2.json"
    scenario_path = (
        ROOT / "contracts" / "fixtures"
        / "scenario-spec-v1.economics-v2.golden.json"
    )
    assert _semantic_fixture_hash(economics_path) == ECONOMICS_FIXTURE_V2_SHA256
    assert (
        _semantic_fixture_hash(scenario_path)
        == SCENARIO_FIXTURE_ECONOMICS_V2_SHA256
    )

    fixture = json.loads(economics_path.read_text(encoding="utf-8"))
    first = calculate(UserInput(**fixture["input"]))
    second = calculate(UserInput(**fixture["input"]))
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.revision_id == first.scenario_spec.revision_id
    assert ScenarioSpec.model_validate(
        first.scenario_spec.model_dump(mode="json")
    ).schema_version == "scenario-spec-v1"


def test_contract_rejects_unknown_version_and_fields():
    fixture = json.loads(
        (ROOT / "contracts" / "fixtures" / "scenario-spec-v1.golden.json")
        .read_text(encoding="utf-8")
    )
    wrong_version = {**fixture, "schema_version": "scenario-spec-v2"}
    with pytest.raises(ValidationError):
        ScenarioSpec.model_validate(wrong_version)

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ScenarioSpec.model_validate({**fixture, "renderer_internal": {}})

    nested_unknown = copy.deepcopy(fixture)
    nested_unknown["economics"]["renderer_internal"] = 1
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ScenarioSpec.model_validate(nested_unknown)


def test_revision_changes_with_units_per_trip_and_is_reproducible():
    base = dict(
        object_type="retail", process_type="transport", cargo_type="boxes",
        pallets_per_day=100, payload_kg=20, units_per_trip=2,
    )
    first = calculate(UserInput(**base))
    same = calculate(UserInput(**base))
    changed = calculate(UserInput(**{**base, "units_per_trip": 4}))
    assert first.revision_id == same.revision_id
    assert first.revision_id != changed.revision_id
    assert first.revision_id == first.scenario_spec.revision_id


def test_floorplan_geometry_is_preserved_in_scenario_spec():
    polygon = [[0.0, 0.0], [24.0, 0.0], [24.0, 12.0], [0.0, 12.0]]
    response = calculate(UserInput(
        object_type="retail", process_type="transport", cargo_type="boxes",
        pallets_per_day=100, payload_kg=20, facility_width_m=24,
        facility_depth_m=12, polygon=polygon,
    ))
    assert response.scenario_spec.facility.geometry_status == "PROVIDED"
    assert response.scenario_spec.facility.width_m == 24
    assert response.scenario_spec.facility.depth_m == 12
    assert response.scenario_spec.zones[0].polygon == polygon
    assert response.scenario_spec.assumptions[0].code == "PROVIDED_ZONE_GEOMETRY"
