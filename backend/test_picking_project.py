"""Picking math must keep units and roles separate from pallet transport."""

import pytest
from pydantic import ValidationError

from calculation.picking_project import calculate_picking_project
from picking_project_api import _csv_value


def scenario():
    return {
        'schema_version': 'warehouse-picking-project-input-v1',
        'process_id': 'zone-1.warehouse_picking',
        'unit': 'ORDER_LINE', 'unit_basis': 'One order line is one pick at this site',
        'unit_confirmed': True, 'demand_per_day': '1000',
        'shifts_per_day': 2, 'hours_per_shift': '8', 'days_per_year': 250,
        'operation_source': 'ASSUMPTION',
        'operation_basis': 'Scenario schedule and fraction for this test',
        'operation_confirmed': True,
        'robot_units_per_hour': '100', 'robot_rate_source': 'ASSUMPTION',
        'robot_rate_basis': 'Scenario rate for this test', 'robot_rate_confirmed': True,
        'availability_fraction': '0.8', 'robotizable_fraction': '0.5',
        'roles': [
            {'role_code': 'picker', 'headcount': 10,
             'monthly_employer_cost': '100000', 'manual_units_per_shift': '100',
             'robotizable_fraction': '0.5', 'residual_extra_shifts_per_day': '0',
             'robot_covers_role': True, 'source': 'ASSUMPTION',
             'basis': 'Scenario staffing for this test', 'confirmed': True},
            {'role_code': 'sorter', 'headcount': 2,
             'monthly_employer_cost': '80000', 'manual_units_per_shift': '500',
             'robotizable_fraction': '0', 'residual_extra_shifts_per_day': '0',
             'robot_covers_role': False, 'source': 'ASSUMPTION',
             'basis': 'Scenario staffing for this test', 'confirmed': True},
        ],
        'money': {'purchase_robot_price': '2000000', 'purchase_implementation': '500000',
                  'purchase_annual_opex_per_robot': '250000',
                  'raas_monthly_per_robot': '200000', 'raas_customer_capex': '100000',
                  'raas_customer_annual_opex': '100000', 'shared_site_capex': '0',
                  'shared_site_annual_opex': '0', 'purchase_new_staff_annual_cost': '0',
                  'raas_new_staff_annual_cost': '0', 'horizon_years': 5,
                  'discount_rate': '0.15', 'source': 'ASSUMPTION',
                  'basis': 'Scenario financial values for this test', 'confirmed': True},
    }


def test_capacity_role_effect_and_finance_are_separate():
    result = calculate_picking_project(scenario())
    assert result['status'] == 'COMPLETE'
    assert result['capacity']['recommended_fleet'] == 1
    assert result['capacity']['covered_units_per_day'] == '500.00'
    assert result['labour']['roles'][0]['released_people'] == 5
    assert result['labour']['roles'][1]['released_people'] == 0
    assert result['labour']['total_released_people'] == 5
    assert result['financial']['purchase']['status'] == 'COMPLETE'
    assert result['financial']['raas']['status'] == 'COMPLETE'
    assert result['purchase_recommendation'] is False


def test_missing_evidence_is_partial_and_does_not_invent_money():
    data = scenario()
    data['robot_rate_confirmed'] = False
    result = calculate_picking_project(data)
    assert result['capacity']['selected_fleet'] is None
    assert result['financial']['purchase']['npv_rub'] is None
    assert 'robot_rate_evidence' in result['missing']


def test_unconfirmed_operating_assumption_blocks_capacity():
    data = scenario()
    data['operation_confirmed'] = False
    result = calculate_picking_project(data)
    assert result['status'] == 'PARTIAL'
    assert result['capacity']['recommended_fleet'] is None
    assert 'operation_confirmed' in result['missing']


def test_extra_residual_work_does_not_double_count_uncovered_demand():
    data = scenario()
    data['roles'][0]['residual_extra_shifts_per_day'] = '2'
    result = calculate_picking_project(data)
    assert result['labour']['roles'][0]['remaining_worker_shifts_per_day'] == 7
    assert result['labour']['roles'][0]['released_people'] == 3


def test_zero_fleet_means_no_released_staff():
    data = scenario()
    data['selected_fleet'] = 0
    result = calculate_picking_project(data)
    assert result['capacity']['selected_fleet'] == 0
    assert result['labour']['total_released_people'] == 0


def test_units_and_role_duplicates_are_rejected():
    data = scenario()
    data['unit'] = 'PALLET'
    with pytest.raises(ValidationError):
        calculate_picking_project(data)
    data = scenario()
    data['process_id'] = 'zone-1.warehouse_receiving_shipping'
    with pytest.raises(ValidationError):
        calculate_picking_project(data)
    data = scenario()
    data['roles'][1]['role_code'] = 'picker'
    with pytest.raises(ValidationError):
        calculate_picking_project(data)


def test_financial_zero_capex_has_explicit_undefined_roi():
    data = scenario()
    data['money']['purchase_robot_price'] = '0'
    data['money']['purchase_implementation'] = '0'
    result = calculate_picking_project(data)
    assert result['financial']['purchase']['status'] == 'COMPLETE'
    assert result['financial']['purchase']['roi_pct'] is None
    assert result['financial']['purchase']['roi_reason']


def test_residual_work_above_available_staff_blocks_finance():
    data = scenario()
    data['roles'][0]['residual_extra_shifts_per_day'] = '11'
    result = calculate_picking_project(data)
    assert result['status'] == 'PARTIAL'
    assert 'roles.picker.residual_workload_exceeds_staff' in result['missing']
    assert result['financial']['purchase']['npv_rub'] is None


def test_csv_sources_cannot_become_spreadsheet_formulas():
    assert _csv_value('=2+2') == "'=2+2"
    assert _csv_value('-12.5') == '-12.5'
