"""Full money matrix on an explicitly disposable, activated PostgreSQL catalog."""
import io
import json
import os
import subprocess
import uuid
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import main
import pytest
from jsonschema import Draft202012Validator
from fastapi.testclient import TestClient
from pypdf import PdfReader
from catalog_repository import ActivatedCatalogRepository
from test_production_economics_integration import activated_actual_catalog  # noqa: F401
from calculation.service import analyze_capacity
from calculation_contracts import CapacityAnalysisRequest
from test_economics_orchestrator import _capacity_request, _q
from test_evgeny_project import project_input

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='disposable PostgreSQL required')


def capacity_input(profile, snapshot, project_id):
    expected = 'CLEANING_AREA_V1' if profile == 'airport' else 'TRANSPORT_CYCLE_V1'
    positions = [p for p in snapshot.positions if p.model.capacity_runtime.calculation_ready
                 and p.model.capacity_runtime.calculation_profile in ([expected, 'DELIVERY_CYCLE_V1'] if profile == 'clinic' else [expected])]
    assert positions
    position = next((p for p in positions if p.procurement_option.amount), positions[0])
    raw = _capacity_request().model_dump(mode='json')
    raw.update(project_id=project_id, model_id=position.model.id, position_id=position.id)
    if profile != 'warehouse':
        process = raw['process']
        object_kind, code, scope, kind, unit, role = ('AIRPORT', 'airport_terminal_cleaning', 'CLEANING_AREA', 'SQUARE_METER', 'm2/day', 'terminal_cleaner') if profile == 'airport' else ('CLINIC', 'clinic_food', 'DELIVERY_CYCLE', 'PORTION', 'portion/day', 'catering_worker')
        process.update(object_kind=object_kind, process_code=code, scope=scope, quantity_kind=kind,
                       demand=_q('demand_per_day', '51000' if profile == 'airport' else '1950', unit, 'FLOW'))
        raw['role_pool']['object_kind'] = object_kind
        raw['role_pool']['roles'][0].update(object_scope=object_kind, role_code=role)
        if profile == 'airport':
            process.update(route_distance=None, exchange=None, explicit_batch=None)
            raw.update(cleaning_area=_q('cleaning_area','51000','m2','AREA'), cleaning_frequency=_q('cleaning_frequency','1','1/day','RATE'))
        else:
            process['explicit_batch'] = _q('units_per_trip', '65', 'unit/trip', 'RATE')
    errors = []
    for candidate in positions:
        raw.update(model_id=candidate.model.id,position_id=candidate.id)
        result = analyze_capacity(CapacityAnalysisRequest.model_validate(raw),snapshot,str(uuid.uuid4())).response
        if result.capacity.value is not None:
            return raw
        errors.append(result.capacity.model_dump(mode='json'))
    raise AssertionError(errors)


def values(result):
    comparison = result.get('comparison') or {}
    return {
        'scenarios': [(s['acquisition'], s['uncertainty'], {key:(m['status'],m.get('value'),m.get('unit')) for key,m in s['metrics'].items()},
                       [{key:value for key,value in f.items() if key not in {'source_ref','source_refs','basis'}} for f in s['annual_cashflows']]) for s in comparison.get('scenarios', [])],
        'labour': result.get('labour'), 'staffing': result.get('staffing_preview'),
        'sensitivity': [list(rows) for rows in (comparison.get('sensitivity') or {}).get('by_scenario', {}).values()],
    }


@pytest.mark.parametrize('profile', ['warehouse', 'airport', 'clinic'])
def test_preview_save_reopen_exports_history_and_independent_cashflow_matrix(activated_actual_catalog, profile, tmp_path):
    snapshot = ActivatedCatalogRepository(activated_actual_catalog, 'capacity').load()
    with TestClient(main.app) as client:
        # Each parametrized path owns a new local user; the production API is never opened.
        registration = client.post('/api/auth/register', json={'email':f'chain-{profile}-{uuid.uuid4()}@example.com','password':'local acceptance passphrase','name':'Acceptance'})
        assert registration.status_code == 201
        headers = {'X-CSRF-Token':registration.json()['csrf_token']}
        project = client.post('/api/projects', headers=headers, json={'name':f'Acceptance {profile}'}).json()
        scenario = next(s for s in project['scenarios'] if s['slot']=='BASE')
        response = client.post('/api/v2/capacity-analyses', headers=headers, json=capacity_input(profile,snapshot,project['id']))
        assert response.status_code == 201, response.text
        capacity = response.json()
        assert capacity['capacity']['value'] is not None, capacity
        endpoint = f"/api/v2/projects/{project['id']}/economics-runs"
        inputs = project_input()
        inputs.update(purchase_price_override_gross='2500000',purchase_price_source='Synthetic acceptance',calculation_depth='FULL')
        created = client.post(endpoint, headers=headers, json={'scenario_id':scenario['id'],'capacity_run_id':capacity['run_id'],'input':inputs})
        assert created.status_code == 201, created.text
        source = created.json(); before = deepcopy(source)
        matrix = [
            ('price', {'purchase_price_override_gross':'3300000'}),
            ('zero-service', {'annual_service_per_robot_gross':'0'}),
            ('implementation-fixed', {'implementation_cost_total_gross':'0'}),
            ('implementation-percent', {'implementation_mode':'PERCENT','implementation_percent':'15','implementation_cost_total_gross':None}),
            ('raas-percent', {'raas_mode':'PERCENT','raas_percent_monthly':'2','raas_monthly_per_robot_gross':None}),
            ('discount', {'discount_rate':'0.3'}),
            ('zero-discount', {'discount_rate':'0'}),
            ('horizon', {'horizon_years':3,'raas_contract_months':36}),
            ('zero-price', {'purchase_price_override_gross':'0'}),
            ('unknown-control-pay', {'control_monthly_gross':None}),
            ('advanced', {'calculation_depth':'ADVANCED','staffing_raas':None,'raas_monthly_per_robot_gross':None,'raas_contract_months':None,'raas_vendor_scope_confirmed':False}),
            ('negative', {'purchase_price_override_gross':'500000000','raas_monthly_per_robot_gross':'9000000'}),
            ('partial', {'calculation_depth':'BASIC','implementation_cost_total_gross':None,'staffing_raas':None,'raas_monthly_per_robot_gross':None,'raas_contract_months':None,'raas_vendor_scope_confirmed':False}),
        ]
        for name, edits in matrix:
            raw = {**deepcopy(inputs), **edits}
            payload = {'scenario_id':scenario['id'],'capacity_run_id':capacity['run_id'],'source_run_id':source['id'],
                       'expected_result_sha256':source['checksums']['result'],'input':raw}
            preview = client.post(endpoint+'/preview',headers=headers,json=payload)
            assert preview.status_code == 200, (profile,name,preview.text)
            data = preview.json()
            saved = client.post(endpoint,headers=headers,json={**payload,'preview_input_sha256':data['input_sha256'],'idempotency_key':str(uuid.uuid4())})
            assert saved.status_code == 201, (profile,name,saved.text)
            run = saved.json()
            assert values(run['result_snapshot']) == values(data['result'])
            if name == 'zero-price':
                result = run['result_snapshot']
                assert result['schema_version'] == 'commercial-scenarios-bundle-v4'
                schema = json.loads((Path(__file__).resolve().parents[1] / 'contracts' / 'commercial-scenarios-bundle-v4.schema.json').read_text())
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(result)
            if run['result_snapshot'].get('comparison'):
                target=Path(__file__).resolve().parents[1]/'.test-product-chain-implementation/session/money-client.json'
                target.write_text(json.dumps(run['result_snapshot']),encoding='utf-8')
                checked=subprocess.run(['node','--preserve-symlinks','--preserve-symlinks-main','frontend/tests/support/backend-money-client.mjs',str(target)],cwd=target.parents[2],capture_output=True,text=True)
                assert checked.returncode==0,checked.stdout+checked.stderr
            assert run['parent_run_id']==source['id'] and run['input_snapshot']['capacity_run_id']==capacity['run_id']
            reopened = client.get(f"/api/projects/{project['id']}/analysis-runs/{run['id']}").json()
            assert reopened['checksums']==run['checksums'] and reopened['result_snapshot']==run['result_snapshot']
            for s in (run['result_snapshot'].get('comparison') or {}).get('scenarios',[]):
                capex = Decimal(s['metrics']['capex']['value']); rate=Decimal(raw['discount_rate'])
                expected = -capex + sum(Decimal(f['effect'])/(1+rate)**f['year'] for f in s['annual_cashflows'])
                assert abs(expected-Decimal(s['metrics']['npv']['value'])) <= Decimal('.1'), (name,s['scenario_id'],expected)
            base = f"/api/projects/{project['id']}/analysis-runs/{run['id']}/exports/"
            pdf = client.get(base+'investor-report.pdf'); assert pdf.status_code==200
            assert pdf.headers['x-report-source-digest']=='sha256:'+run['checksums']['result']
            assert all(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
            for filename in ['result.xlsx','comparison.csv']:
                assert client.get(base+filename).status_code==200
            output=Path(__file__).resolve().parents[1]/'.test-product-chain-implementation/session/money-pdfs'
            output.mkdir(exist_ok=True)
            (output/f'{profile}-{name}.pdf').write_bytes(pdf.content)
        unchanged = client.get(f"/api/projects/{project['id']}/analysis-runs/{source['id']}").json()
        for key in ['checksums','input_snapshot','result_snapshot','scenario_spec_snapshot']:
            assert unchanged[key]==before[key]
        for field,value in [('discount_rate','0.1-0.2'),('purchase_price_override_gross','-1'),('horizon_years',0)]:
            response=client.post(endpoint+'/preview',headers=headers,json={**payload,'input':{**inputs,field:value}})
            assert response.status_code in {200,409,422},(field,response.text)
            if response.status_code==200:
                assert not response.json()['result'].get('comparison'),(field,response.json())
        # Physical changes go through another capacity run and preserve the former physical snapshot.
        physical = capacity_input(profile,snapshot,project['id'])
        physical['input_revision']='revision.physical.second'
        physical['process']['input_revision']='revision.physical.second'
        physical['provenance'][0]['confirmation_revision']='revision.physical.second'
        physical['process']['demand']['raw_value']=physical['process']['demand']['normalized_value']='102000' if profile=='airport' else '2200'
        changed = client.post('/api/v2/capacity-analyses',headers=headers,json=physical)
        assert changed.status_code==201 and changed.json()['run_id']!=capacity['run_id'],changed.text
        original = client.get(f"/api/projects/{project['id']}/analysis-runs/{capacity['run_id']}").json()
        assert original['result_snapshot']==capacity
