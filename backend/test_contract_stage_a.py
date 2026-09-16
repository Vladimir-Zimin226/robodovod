import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from economics import SCENARIOS, _fleet_sizing, calc_recommendation, calc_zone
from fleet import ROBOT_BY_ID, as_dicts
from main import calculate
from models import ScenarioSpec, UserInput, Zone


ROOT = Path(__file__).resolve().parents[1]
ECONOMICS_FIXTURE_V1_SHA256 = "ad53b21e400893837c50970d94faa7e67b4e009c2934a55124ac27d3bc9a37ee"
SCENARIO_FIXTURE_V1_SHA256 = "3df6a7047149d714f61731df75cdcdf7f5bb5a4e8e16e51e06a744f65ae7e850"
ECONOMICS_FIXTURE_V2_SHA256 = "39fd5206bd7c1ca3c118b6579535c4e0b4e8db79e52b9dba3024e058fe338485"
SCENARIO_FIXTURE_ECONOMICS_V2_SHA256 = "f5066adea4a678a00d28211f67d5b391ccb944faf80c0336ff6947124f397623"


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
    robot = ROBOT_BY_ID["amr_light_250"].model_dump(mode="python")
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
    robot = ROBOT_BY_ID["bella_bot"].model_dump(mode="python")
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


def test_current_golden_economics_and_scenario_spec_are_immutable():
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
    response = calculate(UserInput(**fixture["input"]))
    best = next(rec for rec in response.recommendations if rec.is_best)
    actual = {
        "best_robot_id": best.robot_id,
        "economic_status": best.economic_status,
        "quantity": best.quantity,
        "fleet_utilization": best.fleet_utilization,
        "fte_displaced": best.fte_displaced,
        "fte_retained": best.fte_retained,
        "fte_released": best.fte_released,
        "capex": best.capex,
        "opex": best.opex,
        "savings_per_year": best.savings_per_year,
        "payback_years": best.payback_years,
        "npv": best.npv,
        "tco": best.tco,
        "cost_per_move": best.cost_per_move,
        "scenario_quantities": {s.scenario: s.quantity for s in best.scenarios},
        "revision_id": response.revision_id,
    }
    assert actual == fixture["expected"]

    contract_fixture = json.loads(scenario_path.read_text(encoding="utf-8"))
    assert response.scenario_spec.model_dump(mode="json") == contract_fixture
    assert ScenarioSpec.model_validate(contract_fixture).schema_version == "scenario-spec-v1"


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
