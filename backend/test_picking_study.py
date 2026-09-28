import pytest
from calculation.picking_study import PickingStudyV1, calculate_picking_study

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
