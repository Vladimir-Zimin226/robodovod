from copy import deepcopy
from dataclasses import replace
import uuid
import pytest
from catalog_repository import CatalogFactDTO
from calculation_contracts import parse_capacity_analysis_request
from calculation.service import analyze_capacity
from candidate_comparison_api import CompareRequest, compare_candidates
from test_capacity_analysis_service import request, snapshot, q


def constrained(**fields):
    raw = request().model_dump(mode='json')
    raw.update(schema_version='capacity-analysis-request-v4', execution_mode='PRELIMINARY_DEMO', demo_assumptions_confirmed=True,
               zone_context={'zone_id':'zone.test', 'label':'Test zone'},
               object_constraint_context={'object_kind':'WAREHOUSE', **fields, 'requirement_sources': {
                   key: {'kind':'USER','user_confirmed':True,'source_ref':f'user.{key}'} for key in fields}})
    raw['process']['process_id'] = 'zone.test.warehouse_receiving_shipping'
    return parse_capacity_analysis_request(raw)


def catalog(aisle=None, outdoor=None):
    original = snapshot(); first = original.positions[0]
    facts = list(first.model.facts)
    if aisle is not None: facts.append(CatalogFactDTO('min_aisle_width', 'GLOBAL', aisle, 'm', 'VERIFIED_OFFICIAL', 'evidence.aisle'))
    if outdoor is not None: facts.append(CatalogFactDTO('outdoor_supported', 'GLOBAL', outdoor, None, 'VERIFIED_OFFICIAL', 'evidence.outdoor'))
    model = replace(first.model, facts=tuple(facts))
    return replace(original, models=(model,), positions=(replace(first, model=model),))


@pytest.mark.parametrize('fields,source,expected', [
    ({'max_payload_kg':'1300'}, catalog(), 'BLOCKED'),
    ({'min_aisle_width_m':'1'}, catalog(aisle=1.2), 'BLOCKED'),
    ({'min_aisle_width_m':'1.5'}, catalog(aisle=1.2), 'NEEDS_VALIDATION'),
    ({'outdoor_required':True}, catalog(outdoor=False), 'BLOCKED'),
    ({'outdoor_required':True}, catalog(), 'NEEDS_VALIDATION'),
])
def test_same_requirements_change_selection_and_saved_physics(fields, source, expected):
    physical = constrained(**fields)
    before = deepcopy(physical.model_dump(mode='json'))
    execution = analyze_capacity(physical, source, 'run.constraints')
    comparison = compare_candidates(physical, source, CompareRequest(source_run_id=uuid.uuid4(), position_ids=[physical.position_id]))
    row = comparison['candidates'][0]
    assert execution.constraints.eligibility == expected
    assert row['constraints'] == execution.constraints.model_dump(mode='json')
    assert (row['status'] == 'EXCLUDED') == (expected == 'BLOCKED')
    assert physical.model_dump(mode='json') == before
    if expected == 'BLOCKED': assert comparison['technical_recommendation']['position_id'] is None


def test_confirmation_and_object_binding_are_required():
    raw = constrained(outdoor_required=True).model_dump(mode='json')
    raw['object_constraint_context']['requirement_sources'] = {}
    with pytest.raises(ValueError, match='confirm object requirement'): parse_capacity_analysis_request(raw)
    raw['object_constraint_context']['object_kind'] = 'AIRPORT'
    with pytest.raises(ValueError, match='belong'): parse_capacity_analysis_request(raw)


def test_unknown_passport_is_not_changed_to_safe_by_empty_requirements():
    execution = analyze_capacity(constrained(), catalog(), 'run.unknown')
    checks = execution.constraints.checks
    assert any(check.status == 'UNKNOWN' for check in checks)
    assert execution.constraints.eligibility == 'NEEDS_VALIDATION'


def test_saved_context_roundtrip_keeps_defaults_and_confirmed_requirements():
    physical = constrained(min_aisle_width_m='1.5')
    assert parse_capacity_analysis_request(physical.model_dump(mode='json')) == physical


def test_trip_payload_is_item_mass_times_explicit_batch_not_one_item():
    raw = constrained(max_payload_kg='1300').model_dump(mode='json')
    raw['process']['item_mass'] = q('item_mass', '800', 'kg/unit', 'RATE').model_dump(mode='json')
    raw['process']['explicit_batch']['raw_value'] = '2'
    raw['process']['explicit_batch']['normalized_value'] = '2'
    missing = deepcopy(raw)
    missing['object_constraint_context']['max_payload_kg'] = None
    missing['object_constraint_context']['requirement_sources'].pop('max_payload_kg')
    with pytest.raises(ValueError, match='confirm required trip payload'):
        parse_capacity_analysis_request(missing)
    with pytest.raises(ValueError, match='trip load'):
        parse_capacity_analysis_request(raw)
    raw['object_constraint_context']['max_payload_kg'] = '1600'
    assert parse_capacity_analysis_request(raw).object_constraint_context['max_payload_kg'] == '1600'
