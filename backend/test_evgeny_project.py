from copy import deepcopy
from decimal import Decimal
import pytest
from calculation.operating_policy import StaffingPolicyV2
from calculation_contracts import OperatingAvailabilityV1
from economics_partial import INPUT_VERSION_V6, execute_partial_economics_v2
from test_economics_partial import _context, _staffing_input

def policy():
    return {'schema_version':'staffing-policy-v2', 'robots_per_control_post':'5',
            'robots_per_day_technician':'20', 'technician_presence':'DAY_WORKLOAD',
            'rotation_factor':'1', 'source':'ASSUMPTION', 'basis':'Synthetic boundary test',
            'date':'2026-09-28', 'confirmed':True}

def project_input():
    return {**_staffing_input(), 'schema_version':INPUT_VERSION_V6,
            'implementation_mode':'FIXED','raas_mode':'FIXED',
            'staffing_policy':policy(), 'work_share':{
                'schema_version':'robotizable-work-share-v1', 'fraction':'0.5',
                'residual_operations':'Unloading and manual inspection',
                'source':'ASSUMPTION','basis':'Synthetic boundary test',
                'date':'2026-09-28','confirmed':True},
            'staffing_purchase':{'control_mode':'HIRE','technician_mode':'HIRE'},
            'staffing_raas':{'control_mode':'HIRE','technician_mode':'VENDOR'}}

@pytest.mark.parametrize('fleet',[0,1,10,20,21])
@pytest.mark.parametrize('shifts',[1,2,3])
def test_staffing_load_boundaries(fleet,shifts):
    result=StaffingPolicyV2.model_validate(policy()).requirement(fleet,shifts)
    assert result['control_posts'] == (fleet+4)//5
    assert result['control_person_shifts'] == (fleet+4)//5*shifts
    assert result['control_fte'] == result['control_person_shifts']
    assert result['technician_fte'] == (fleet+19)//20

def test_rotation_and_presence_are_applied_once():
    result=StaffingPolicyV2.model_validate({**policy(),'rotation_factor':'1.4',
                  'technician_presence':'EACH_SHIFT'}).requirement(10,2)
    assert result['control_person_shifts'] == 4
    assert result['control_fte'] == 6
    assert result['technician_fte'] == 3

@pytest.mark.parametrize('fraction',['0','0.5','1'])
def test_new_work_share_limits_actual_role_and_preserves_source(fraction):
    snapshot,context=_context()
    raw=project_input();raw['work_share']['fraction']=fraction
    before=deepcopy(raw)
    result=execute_partial_economics_v2(raw,snapshot,context).result_snapshot
    assert raw==before
    assert result['work_share']['fraction']==fraction
    assert result['staffing_preview']['PURCHASE']['control_required']==4
    assert result['staffing_preview']['PURCHASE']['technicians_required']==1
    released=result['staffing_preview']['PURCHASE']['released']
    headcount=int(context.capacity_request.role_pool.roles[0].headcount.normalized_value)
    assert 0<=released<=int(Decimal(headcount)*Decimal(fraction))

def test_unknown_work_share_and_pay_remain_partial():
    snapshot,context=_context()
    raw=project_input();raw['work_share']=None
    result=execute_partial_economics_v2(raw,snapshot,context).result_snapshot
    assert result['branches']['purchase']['status']=='NOT_CALCULATED'
    raw=project_input();raw['control_monthly_gross']=None
    result=execute_partial_economics_v2(raw,snapshot,context).result_snapshot
    assert result['branches']['purchase']['status']=='NOT_CALCULATED'
    assert result['staffing_preview']['PURCHASE']['control_required']==4

def test_downtime_modes_and_unknown_are_not_double_counted():
    common={'basis':'Measured project inputs','source':'USER','confirmed':True}
    allin=OperatingAvailabilityV1(mode='ALL_IN',availability='0.7',**common)
    assert allin.practical_fraction(Decimal(24))==Decimal('0.7')
    explicit=OperatingAvailabilityV1(mode='EXPLICIT_DOWNTIME',autonomy_hours='8',
        charge_hours='2',service_hours_per_day='1',refill_hours_per_day='0',**common)
    assert explicit.practical_fraction(Decimal(24))<1
    with pytest.raises(ValueError):
        OperatingAvailabilityV1(mode='ALL_IN',availability='0.7',charge_hours='2',**common)
    with pytest.raises(ValueError):
        OperatingAvailabilityV1(mode='EXPLICIT_DOWNTIME',autonomy_hours='8',charge_hours=None,
            service_hours_per_day='0',refill_hours_per_day='0',**common)

def test_cleaning_practical_capacity_respects_nameplate_and_downtime():
    from test_cleaning_capacity import request
    from calculation.capacity.cleaning import calculate_cleaning_capacity
    common={'basis':'Synthetic airport downtime','source':'ASSUMPTION','confirmed':True}
    baseline=request(rate='3000')
    allin=OperatingAvailabilityV1(mode='ALL_IN',availability='0.7',**common)
    result=calculate_cleaning_capacity(baseline.model_copy(update={'operations':allin}))
    assert result.capacity.value.recommended_fleet==2
    explicit=OperatingAvailabilityV1(mode='EXPLICIT_DOWNTIME',autonomy_hours='8',
        charge_hours='8',service_hours_per_day='1',refill_hours_per_day='1',**common)
    result=calculate_cleaning_capacity(baseline.model_copy(update={'operations':explicit}))
    assert result.capacity.value.recommended_fleet==2
    assert Decimal(result.capacity.value.effective_capacity.value)<=Decimal(result.capacity.value.nominal_capacity.value)

def test_v6_project_finance_and_conclusion_are_profile_specific():
    from economics_final import execute_economics_v4
    snapshot,context=_context()
    result=execute_partial_economics_v2(project_input(),snapshot,context,full_engine=execute_economics_v4).result_snapshot
    assert result['schema_version']=='commercial-scenarios-bundle-v3'
    assert len(result['scenarios'])==6
    for row in result['scenarios']:
        facts=row['report_facts']
        comparison=next(item for item in result['comparison']['scenarios'] if item['scenario_id']==row['scenario_id'])
        assert facts['project_npv']['value']==comparison['metrics']['npv']['value']
        assert facts['project_simple_payback']['value']==comparison['metrics']['simple_payback']['value']
        assert facts['project_discounted_payback']['value']==comparison['metrics']['discounted_payback']['value']
        assert row['recommendation']['candidate_id'] is None
        assert 'procurement-not-confirmed' in row['recommendation']['reason_codes']
        assert row['staffing']['control_required']==4

def test_percent_modes_are_server_canonical_and_ignore_stale_fixed_amounts():
    from economics_final import execute_economics_v4
    snapshot,context=_context()
    fixed=project_input()
    fixed['implementation_cost_total_gross']='4500000'
    fixed['raas_monthly_per_robot_gross']='60000'
    absolute=execute_partial_economics_v2(fixed,snapshot,context,full_engine=execute_economics_v4).result_snapshot
    percent={**fixed,'implementation_mode':'PERCENT','implementation_percent':'15',
             'raas_mode':'PERCENT','raas_percent_monthly':'2',
             'implementation_cost_total_gross':'999999','raas_monthly_per_robot_gross':'999999'}
    result=execute_partial_economics_v2(percent,snapshot,context,full_engine=execute_economics_v4).result_snapshot
    assert result['monetary_input_basis']['implementation']['amount_gross_rub']=='4500000.00'
    assert result['monetary_input_basis']['raas']['per_robot_month_gross_rub']=='60000.00'
    assert [r['report_facts']['project_npv'] for r in result['scenarios']]==[r['report_facts']['project_npv'] for r in absolute['scenarios']]

@pytest.mark.parametrize('percent,expected',[('0','0.00'),('2','60000.00'),('4','120000.00')])
def test_raas_percent_is_monthly_and_uses_known_money_basis(percent,expected):
    from economics_final import execute_economics_v4
    snapshot,context=_context()
    raw=project_input();raw.update(raas_mode='PERCENT',raas_percent_monthly=percent)
    result=execute_partial_economics_v2(raw,snapshot,context,full_engine=execute_economics_v4).result_snapshot
    assert result['monetary_input_basis']['raas']['per_robot_month_gross_rub']==expected
    raw['purchase_price_override_gross']=None
    raw['purchase_price_source']=None
    result=execute_partial_economics_v2(raw,snapshot,context,full_engine=execute_economics_v4).result_snapshot
    assert result['monetary_input_basis']['raas']['mode']=='PERCENT'

def test_what_if_engine_changes_money_without_mutating_saved_physical_source():
    from economics_final import execute_economics_v4
    snapshot,context=_context()
    raw=project_input()
    original_request=deepcopy(context.capacity_request.model_dump(mode='json'))
    original_capacity=deepcopy(context.capacity_response.model_dump(mode='json'))
    before=execute_partial_economics_v2(raw,snapshot,context,full_engine=execute_economics_v4).result_snapshot
    edited=deepcopy(raw);edited['raas_monthly_per_robot_gross']='120000'
    after=execute_partial_economics_v2(edited,snapshot,context,full_engine=execute_economics_v4).result_snapshot
    assert before['input_revision']==after['input_revision']==context.capacity_request.input_revision
    assert context.capacity_request.model_dump(mode='json')==original_request
    assert context.capacity_response.model_dump(mode='json')==original_capacity
    original_raas=next(r for r in before['scenarios'] if r['scenario_id']=='scenario.raas.base')
    changed_raas=next(r for r in after['scenarios'] if r['scenario_id']=='scenario.raas.base')
    assert original_raas['report_facts']['project_npv']!=changed_raas['report_facts']['project_npv']
