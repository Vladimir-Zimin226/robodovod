import pytest
from decimal import Decimal
from calculation.picking_study import PickingStudyV1, PickingStudyV2, calculate_picking_study, calculate_picking_study_v2

def data(**changes):
    return PickingStudyV1.model_validate({
        'unit':'PICK','demand_per_day':'1000','hours_per_shift':'8','shifts_per_day':2,
        'robot_picks_per_hour':'100','robot_rate_source':'SYNTHETIC_TEST',
        'manual_picks_per_shift':'100','manual_rate_source':'MEASUREMENT',
        'robotizable_fraction':'0.5','residual_operations':'Manual inspection and packing',
        'existing_pickers':10,'annual_gross_per_picker':'1200000','robot_price_gross':'1000000',
        'annual_robot_opex_gross':'100000','confirmation':True,**changes})

def test_picking_arithmetic_separate_from_pallet_transport():
    result=calculate_picking_study(data())
    assert result['recommended_fleet']==1
    assert result['released_people']==5
    assert result['catalog_model_verified'] is False
    assert result['project_npv'] is not None

def test_unknown_model_and_role_inputs_are_partial():
    result=calculate_picking_study(data(robot_picks_per_hour=None,robot_rate_source=None))
    assert result['status']=='PARTIAL' and result['project_npv'] is None
    result=calculate_picking_study(data(robotizable_fraction=None))
    assert result['released_people'] is None

@pytest.mark.parametrize('fleet',[0,1,2])
def test_partial_replacement_never_exceeds_current_staff(fleet):
    result=calculate_picking_study(data(selected_fleet=fleet))
    assert 0<=result['released_people']<=5

def test_unit_cannot_be_pallet():
    with pytest.raises(ValueError):
        data(unit='PALLET')


def research(**changes):
    raw = data().model_dump(mode='json')
    raw.update(schema_version='warehouse-picking-study-v2', residual_worker_shifts_per_day='1',
               residual_rate_source='SYNTHETIC_TEST')
    raw.update(changes)
    return PickingStudyV2.model_validate(raw)


def test_research_profile_zero_demand_never_releases_people_or_claims_npv():
    result = calculate_picking_study_v2(research(demand_per_day='0'))
    assert result['profile_version'] == 'warehouse-picking-research-v2'
    assert result['recommended_fleet'] == 0
    assert Decimal(result['robot_covered_per_day']) == 0
    assert result['potential_avoided_worker_shifts_per_day'] == 0
    assert result['released_people'] is None and result['project_npv'] is None


def test_manual_productivity_and_residual_work_change_research_effect():
    fast = calculate_picking_study_v2(research())
    slow = calculate_picking_study_v2(research(manual_picks_per_shift='50'))
    extra = calculate_picking_study_v2(research(residual_worker_shifts_per_day='3'))
    assert Decimal(fast['robot_covered_per_day']) == 500
    assert fast['potential_avoided_worker_shifts_per_day'] == 4
    assert slow['potential_avoided_worker_shifts_per_day'] == 9
    assert extra['potential_avoided_worker_shifts_per_day'] == 2
    assert fast['released_people'] is None and fast['project_npv'] is None


def test_residual_measurement_is_required_and_v1_remains_unchanged():
    partial = calculate_picking_study_v2(research(residual_worker_shifts_per_day=None, residual_rate_source=None))
    assert partial['status'] == 'PARTIAL' and partial['potential_avoided_worker_shifts_per_day'] is None
    assert 'residual_operations' in calculate_picking_study_v2(research(residual_operations='   '))['missing']
    with pytest.raises(ValueError): research(residual_worker_shifts_per_day='1', residual_rate_source=None)
    assert calculate_picking_study(data())['schema_version'] == 'warehouse-picking-study-result-v1'
