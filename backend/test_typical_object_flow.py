"""Current capacity/economics/simulation flow on explicit synthetic model facts.

Organizer object numbers do not prove a particular vendor's suitability.
"""
from dataclasses import replace
from decimal import Decimal

import pytest

from calculation.service import analyze_capacity
from calculation.scheduling import SimulationRequestV2, SimulationReportV1, run_simulation
from calculation_contracts import CapacityAnalysisRequest
from catalog_repository import CatalogFactDTO, CatalogApplicabilityDTO
from economics_orchestrator import EconomicsExecutionContextV1
from economics_partial import execute_partial_economics_v2
from economics_final import execute_economics_v4
from test_economics_orchestrator import _capacity_request, _snapshot, _q
from test_economics_partial import _staffing_input


def _object_context(kind):
    airport = kind == 'AIRPORT'
    raw = _capacity_request().model_dump(mode='json')
    process = raw['process']
    process.update(object_kind=kind, process_code='airport_terminal_cleaning' if airport else 'clinic_food',
        scope='CLEANING_AREA' if airport else 'DELIVERY_CYCLE', quantity_kind='SQUARE_METER' if airport else 'PORTION',
        demand=_q('demand_per_day', '51000' if airport else '1950', 'm2/day' if airport else 'portion/day', 'FLOW'))
    process['schedule']['shifts_per_day'] = _q('shifts_per_day', '3', 'shift', 'COUNT')
    process['schedule']['shift_hours'] = _q('shift_hours', '8', 'h', 'TIME')
    if airport:
        process.update(route_distance=None, exchange=None, explicit_batch=None)
        raw['cleaning_area'] = _q('cleaning_area', '51000', 'm2', 'AREA')
        raw['cleaning_frequency'] = _q('cleaning_frequency', '1', '1/day', 'RATE')
    else:
        process['route_distance'] = _q('one_way_distance', '180', 'm', 'DISTANCE')
        process['explicit_batch'] = _q('units_per_trip', '65', 'unit/trip', 'RATE')
        process['exchange']['total_time'] = _q('exchange_total_time', '180', 's', 'TIME')
    raw['role_pool']['object_kind'] = kind
    role = raw['role_pool']['roles'][0]
    role.update(object_scope=kind, role_code='terminal_cleaner' if airport else 'catering_worker',
        headcount=_q('role_headcount', '30' if airport else '6', 'person', 'COUNT'), monthly_gross_salary=_q('monthly_gross_salary', '65000' if airport else '52000', 'RUB/person/month', 'MONEY'))
    request = CapacityAnalysisRequest.model_validate(raw)
    snapshot = _snapshot()
    model = snapshot.models[0]
    if airport:
        fact = CatalogFactDTO('cleaning_rate_m2_h', 'GLOBAL', 600, 'm2/h', 'VERIFIED_OFFICIAL', 'fixture.cleaning-rate')
        runtime = replace(model.capacity_runtime, calculation_profile='CLEANING_AREA_V1',
            calculation_model_fields=('capacity.cleaning_rate_m2_h',), vendor_facts=(fact,))
        model = replace(model, capacity_runtime=runtime, facts=(fact,))
    position = replace(snapshot.positions[0], model=model,
        applicability=CatalogApplicabilityDTO('airport' if airport else 'medical_facility', 'cleaning' if airport else 'delivery', 'RU', None))
    snapshot = replace(snapshot, models=(model,), positions=(position,))
    execution = analyze_capacity(request, snapshot, 'run.capacity.typical')
    assert execution.response.capacity.value is not None
    context = EconomicsExecutionContextV1(run_id='run.economics.typical', project_id=request.project_id,
        tenant_id='tenant.typical', capacity_request=request, capacity_response=execution.response,
        constraint_report=execution.constraints.model_dump(mode='json'), executability=execution.executability.model_dump(mode='json'))
    return snapshot, context


@pytest.mark.parametrize('kind', ['AIRPORT', 'CLINIC'])
def test_typical_object_full_economics_and_automatic_physical_simulation(kind):
    snapshot, context = _object_context(kind)
    raw = {**_staffing_input(), 'calculation_depth': 'FULL', 'horizon_years': '7', 'raas_contract_months': '84',
        'start_seconds_from_midnight': '32400', 'timezone': 'Asia/Sakhalin',
        'staffing_purchase': {'control_mode': 'HIRE', 'technician_mode': 'HIRE'},
        'staffing_raas': {'control_mode': 'HIRE', 'technician_mode': 'VENDOR'}}
    raw['manual_units_per_shift'] = None if kind == 'AIRPORT' else '65'
    result = execute_partial_economics_v2(raw, snapshot, context, full_engine=execute_economics_v4)
    assert result.result_snapshot['schema_version'] == 'commercial-scenarios-bundle-v3'
    assert len(result.result_snapshot['scenarios']) == 6
    assert result.scenario_spec_snapshot['tasks'][0]['demand']['value'] == ('51000' if kind == 'AIRPORT' else '1950')
    spec = result.scenario_spec_snapshot
    if kind == 'AIRPORT':
        assert spec['tasks'][0]['batch']['units_per_cycle']['unit'] == 'm2'
        assert any('Микрозадание уборки' in text for text in spec['warnings'])
    request = SimulationRequestV2.model_validate({'schema_version': 'simulation-request-v2',
        'request_id': 'simulation.typical', 'tenant_id': context.tenant_id, 'project_id': context.project_id,
        'scenario_spec': spec, 'mode': 'DAILY', 'peak_factor': None, 'sla': None, 'resources': [],
        'model_start': {'weekday': 'MONDAY', 'seconds_from_midnight': 32400, 'timezone': 'Asia/Sakhalin'},
        'process_chain': None,
        'limits': {'max_jobs_per_day': 10000, 'max_fleet': 100, 'max_runtime_seconds': 60, 'progress_event_batch': 1000}})
    report = run_simulation(request)
    assert isinstance(report, SimulationReportV1), report
    assert report.queue.measurement_jobs <= 10000
    assert Decimal(report.capacity.required_per_hour) > 0


@pytest.mark.parametrize('kind', ['AIRPORT', 'CLINIC'])
def test_typical_object_preview_with_current_catalog_profiles(kind):
    import uuid
    from candidate_comparison_api import CompareRequest, compare_candidates
    snapshot, context = _object_context(kind)
    original = snapshot.models[0].capacity_runtime
    result = compare_candidates(context.capacity_request, snapshot,
        CompareRequest(source_run_id=uuid.uuid4(), position_ids=[snapshot.positions[0].id]))
    assert result['candidates'][0]['capacity']['status'] == 'WITH_ASSUMPTIONS'
    assert result['candidates'][0]['technical_score'] is not None
    assert result['technical_recommendation']['status'] == 'PRELIMINARY'
    assert snapshot.models[0].capacity_runtime is original
    if kind == 'CLINIC':
        assert original.calculation_profile == 'TRANSPORT_CYCLE_V1'
        assert context.executability['profile_id'] == 'DELIVERY_CYCLE_V1'
        assert any(p.provenance_id == 'prov.delivery-profile.confirmation' for p in context.capacity_response.trace.provenance)


def test_generic_transport_delivery_binding_requires_preliminary_confirmation():
    snapshot, context = _object_context('CLINIC')
    raw = context.capacity_request.model_dump(mode='json')
    raw.update(execution_mode='VERIFIED', demo_assumptions_confirmed=False)
    execution = analyze_capacity(CapacityAnalysisRequest.model_validate(raw), snapshot, 'run.delivery.verified')
    assert execution.executability.profile_id == 'TRANSPORT_CYCLE_V1'
    assert execution.response.capacity.value is None
    assert not any(p.provenance_id == 'prov.delivery-profile.confirmation' for p in execution.response.trace.provenance)


def test_preliminary_delivery_preserves_explicit_object_exclusion():
    snapshot, context = _object_context('CLINIC')
    model = snapshot.models[0]
    fact = CatalogFactDTO('supported_object_kinds', 'GLOBAL', ['WAREHOUSE'], '1', 'VERIFIED_OFFICIAL', 'fixture.objects')
    model = replace(model, facts=(*model.facts, fact))
    snapshot = replace(snapshot, models=(model,), positions=(replace(snapshot.positions[0], model=model),))
    execution = analyze_capacity(context.capacity_request, snapshot, 'run.delivery.excluded')
    assert execution.constraints.eligibility == 'BLOCKED'
    assert execution.response.capacity.value is None
