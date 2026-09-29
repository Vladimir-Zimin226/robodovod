from __future__ import annotations

import hashlib
import io
import re
import uuid
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from auth import require_auth_context
from calculation.evidence_export import EvidenceExportIntegrityError, EvidenceRunSnapshotV1
from calculation.final_export import build_final_export
from calculation.investor_report import VERSION, _assumption_source, _input_value, amount, build_investor_report, metric_text
from calculation.scheduling import SimulationRequestV1, run_simulation
from calculation_contracts import semantic_digest
from database import database_session
from evidence_export_api import create_evidence_export_router
from simulation_artifacts import StoredSimulationEvidence
from test_final_economics import _run
from test_readable_report import _full_runs


def text(pdf):
    return '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(pdf)).pages)


def updated(run, *, inputs=None, result=None):
    raw = run.model_dump(mode='json')
    if inputs is not None:
        raw['input_snapshot'] = inputs
    if result is not None:
        raw['result_snapshot'] = result
    for key in ('input','result'):
        raw['checksums'][key] = semantic_digest(raw[f'{key}_snapshot']).removeprefix('sha256:')
    return EvidenceRunSnapshotV1.model_validate(raw)


@pytest.fixture(scope='module')
def full():
    run, linked, _ = _run(presentation_v4=True)
    inputs = deepcopy(run.input_snapshot)
    inputs['economics']['calculation_depth'] = 'FULL'
    return updated(run,inputs=inputs), linked


def test_new_v6_report_discloses_staffing_work_share_and_money_basis(full):
    run, linked = full
    inputs = deepcopy(run.input_snapshot)
    inputs['economics']['schema_version'] = 'economics-explicit-inputs-v6'
    result = deepcopy(run.result_snapshot)
    result['staffing_preview'] = {'PURCHASE': {'control_required':4,'control_transferred':0,
        'control_additional':4,'technicians_required':1,'technicians_billable':1},
        'RAAS': {'control_required':4,'control_transferred':0,'control_additional':4,
        'technicians_required':1,'technicians_billable':0}}
    result['work_share'] = {'fraction':'0.6','residual_operations':'Ручная проверка'}
    result['monetary_input_basis'] = {'unit_price_gross_rub':'3000000','fleet':10,
        'implementation':{'mode':'PERCENT','amount_gross_rub':'4500000'},
        'raas':{'mode':'PERCENT','per_robot_month_gross_rub':'60000'}}
    new_run = updated(run, inputs=inputs, result=result)
    pdf,_ = build_investor_report(new_run, linked)
    content = text(pdf)
    assert 'Персонал и денежные базы проекта' in content
    assert 'Ручная проверка' in content
    assert '4 500 000,00 ₽' in content and '60 000,00 ₽' in content
    assert '60 %' in content and 'PERCENT' not in content


def test_visual_report_reads_saved_values_and_does_not_change_historical_exports(full):
    run,linked = full
    before = deepcopy(run.model_dump(mode='json'))
    old = build_final_export(run,linked)
    pdf,digest = build_investor_report(run,linked)
    assert build_investor_report(run,linked)[0] == pdf
    assert digest == 'sha256:'+run.checksums['result']
    assert run.model_dump(mode='json') == before
    assert build_final_export(run,linked).archive == old.archive
    reader = PdfReader(io.BytesIO(pdf))
    assert all(p.mediabox.width == 842 and p.mediabox.height == 595 for p in reader.pages)
    assert all('Глубина расчёта: Полный' in p.extract_text() for p in reader.pages)
    content = text(pdf)
    for scenario in run.result_snapshot['comparison']['scenarios']:
        assert amount(scenario['metrics']['npv']['value'],millions=True) in content
    assert 'Шесть вариантов' in content and 'чувствительность результата' in content
    assert 'Денежные потоки по годам' in content and 'ROI на первоначальные вложения' in content
    assert 'NPV собственных потоков без роботов' in content
    assert 'NPV собственных потоков сценария' in content
    # The graphics contain paths, strokes and filled bars, beyond text rows.
    streams = b'\n'.join(p.get_contents().get_data() for p in reader.pages)
    assert streams.count(b' l S') > 10 and streams.count(b' re f') > 80
    main = content.split('Приложение:')[0]
    for code in ['COMPLETE','NOT_AVAILABLE','NOT_REACHED','C11','C18','scenario.purchase','sha256:']:
        assert code not in main


@pytest.mark.parametrize('depth,label',[('BASIC','Базовый'),('ADVANCED','Углублённый'),('FULL','Полный')])
def test_every_page_labels_persisted_depth_even_when_economics_is_incomplete(depth,label):
    run,linked = _full_runs()
    inputs = deepcopy(run.input_snapshot)
    inputs['economics']['calculation_depth'] = depth
    result = {'schema_version':'economics-partial-result-v1','input_revision':'revision.report.v1',
              'labour':{'total_released':'2.5','total_additional_control':'1'},'scenarios':[],
              'branches':{'purchase':{'required_fields':['implementation_cost_total_gross']}}}
    selected = updated(run,inputs=inputs,result=result)
    pdf,_ = build_investor_report(selected,linked)
    assert all(f'Глубина расчёта: {label}' in p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    content = text(pdf)
    assert '2,5 чел.' in content and 'Инвестиционный вывод пока недоступен' in content
    assert 'Шесть вариантов' not in content
    assert 'implementation_cost_total_gross' not in content


def test_advanced_does_not_present_full_sensitivity_and_missing_depth_is_not_guessed(full):
    run,linked = full
    inputs = deepcopy(run.input_snapshot)
    inputs['economics']['calculation_depth'] = 'ADVANCED'
    content = text(build_investor_report(updated(run,inputs=inputs),linked)[0])
    assert 'Глубина расчёта: Углублённый' in content
    assert 'Шесть вариантов' not in content and 'чувствительность результата' not in content
    del inputs['economics']['calculation_depth']
    assert 'Не указана в сохранённом расчёте' in text(build_investor_report(updated(run,inputs=inputs),linked)[0])


def test_negative_npv_and_not_reached_are_preserved(full):
    run,linked = full
    result = deepcopy(run.result_snapshot)
    for s in result['comparison']['scenarios']:
        s['metrics']['npv']['value'] = '-1000000.00'
        s['metrics']['discounted_payback'].update(status='NOT_REACHED',value=None)
    content = text(build_investor_report(updated(run,result=result),linked)[0])
    assert '-1,00 млн ₽' in content
    assert 'не показывают положительного' in content
    assert 'За горизонт не достигнута' in content
    assert metric_text({'metrics':{'roi':{'status':'NOT_APPLICABLE','value':None}}},'roi') == 'Не применяется'
    assert metric_text({'metrics':{'roi':{'status':'N_A','value':None}}},'roi') == 'Не применяется'


def test_npv_table_labels_saved_increment_without_inventing_absolute_scenario(full):
    run, linked = full
    result = deepcopy(run.result_snapshot)
    for scenario in result['comparison']['scenarios']:
        for key in ('npv_base', 'npv_scenario', 'npv_project'):
            scenario['metrics'].pop(key, None)
    content = text(build_investor_report(updated(run, result=result), linked)[0])
    assert 'NPV проекта (инкремент)' in content
    assert 'NPV собственных потоков сценария' not in content


def test_new_comparison_persists_all_three_npv_values(full):
    from decimal import Decimal

    run, linked = full
    for scenario in run.result_snapshot['comparison']['scenarios']:
        values = scenario['metrics']
        assert all(values[key]['status'] == 'COMPLETE' for key in ('npv_base', 'npv_scenario', 'npv_project'))
        assert abs(Decimal(values['npv_scenario']['value']) - Decimal(values['npv_base']['value']) - Decimal(values['npv_project']['value'])) <= Decimal('0.01')
        assert values['npv_project'] == values['npv']
    content = text(build_investor_report(run, linked)[0])
    assert 'NPV собственных потоков сценария' in content


def test_npv_table_uses_three_consistent_saved_metrics_when_present(full):
    from decimal import Decimal

    run, linked = full
    result = deepcopy(run.result_snapshot)
    result['comparison']['baseline']['metrics']['npv']['value'] = '-100000000'
    for scenario in result['comparison']['scenarios']:
        project = Decimal(scenario['metrics']['npv']['value'])
        base = Decimal('-100000000')
        for key, value in [('npv_base', base), ('npv_scenario', base + project), ('npv_project', project)]:
            scenario['metrics'][key] = {'status': 'COMPLETE', 'value': str(value), 'unit': 'RUB'}
    content = text(build_investor_report(updated(run, result=result), linked)[0])
    assert 'NPV собственных потоков базы' in content
    assert 'NPV собственных потоков сценария' in content
    assert 'NPV проекта (инкремент)' in content


def test_assumptions_use_human_sources_units_and_a_role_scope_for_partial_finance():
    assert _input_value('discount_rate','0.15') == '15 %'
    assert _input_value('purchase_price_override_gross','1200000') == '1 200 000,00 ₽'
    assert _assumption_source({'source':'USER','rationale':'Авторское допущение для типового аэропорта'}) == 'Авторское допущение'
    run,linked = _full_runs()
    result = {'schema_version':'economics-partial-result-v1','input_revision':'revision.report.v1','scenarios':[
        {'acquisition':'PURCHASE','uncertainty':'BASE','financial':{'status':'COMPLETE',
            'npv_project':{'status':'COMPLETE','value':'1000000','unit':'RUB'},'annual_ledgers':[
                {'year':1,'primary_cf_base':'-1000','primary_cf_scenario':'-800','differential_cf':'200'}]}}]}
    content = text(build_investor_report(updated(run,result=result),linked)[0])
    assert 'NPV выбранной роли' in content
    assert 'общий эффект объекта здесь не оценён' in ' '.join(content.split())
    assert 'NPV проекта' not in content


@pytest.mark.parametrize('depth',['BASIC','ADVANCED'])
def test_real_depth_engine_results_export_without_filling_hidden_fields(depth,tmp_path):
    from economics_partial import execute_partial_economics_v2
    from test_economics_partial import _context, _staffing_input
    from scripts.build_evidence_export_contract import golden_run
    snapshot,context = _context()
    inputs = {**_staffing_input(),'calculation_depth':depth,'staffing_raas':None,
              'raas_monthly_per_robot_gross':None,'raas_contract_months':None,'raas_vendor_scope_confirmed':False}
    if depth == 'BASIC':
        inputs['implementation_cost_total_gross'] = None
    execution = execute_partial_economics_v2(inputs,snapshot,context)
    raw = golden_run().model_dump(mode='json')
    raw.update(run_id=context.run_id,project_id=context.project_id)
    run = updated(EvidenceRunSnapshotV1.model_validate(raw),
        inputs={'capacity_run_id':context.capacity_response.run_id,'economics':inputs},result=execution.result_snapshot)
    capacity_raw = golden_run().model_dump(mode='json')
    capacity_raw.update(run_id=context.capacity_response.run_id,project_id=context.project_id,run_kind='CAPACITY_ANALYSIS')
    linked = updated(EvidenceRunSnapshotV1.model_validate(capacity_raw),
        inputs=context.capacity_request.model_dump(mode='json'),result=context.capacity_response.model_dump(mode='json'))
    pdf,_ = build_investor_report(run,linked)
    (tmp_path/f'{depth}.pdf').write_bytes(pdf)
    content = text(pdf)
    assert ('Глубина расчёта: Базовый' if depth=='BASIC' else 'Глубина расчёта: Углублённый') in content
    assert 'Шесть вариантов' not in content
    assert 'Труд: изменение занятости' in content
    if depth=='ADVANCED':
        scenario = next(s for s in execution.result_snapshot['scenarios'] if s['uncertainty']=='BASE')
        assert amount(scenario['financial']['npv_project']['value'],millions=True) in content
        assert 'NPV выбранной роли' in content
    else:
        assert 'Инвестиционный вывод пока недоступен' in content


def test_capacity_report_and_very_long_horizon_remain_readable(full):
    run,linked = full
    capacity = text(build_investor_report(linked)[0])
    assert 'Техническая оценка; экономика не рассчитана' in capacity
    assert 'Не указана в сохранённом расчёте' not in capacity
    result = deepcopy(run.result_snapshot)
    for s in result['comparison']['scenarios']:
        first = s['annual_cashflows'][0]
        s['annual_cashflows'] = [{**first,'year':year} for year in range(1,31)]
    result['comparison']['horizon_years'] = 30
    pdf,_ = build_investor_report(updated(run,result=result),linked)
    content = text(pdf)
    assert content.count('Денежные потоки по годам') == 3
    assert re.search(r'\n30\s',content)


def test_report_rejects_tampered_sources_and_foreign_capacity(full):
    run,linked = full
    raw = run.model_dump(mode='json')
    raw['result_snapshot']['comparison']['scenarios'][0]['metrics']['npv']['value'] = '1'
    with pytest.raises(EvidenceExportIntegrityError):
        build_investor_report(EvidenceRunSnapshotV1.model_validate(raw),linked)
    with pytest.raises(EvidenceExportIntegrityError):
        build_investor_report(run,linked.model_copy(update={'project_id':str(uuid.uuid4())}))


def test_material_technical_constraints_are_explained_without_raw_codes(full):
    run,linked = full
    diagnostics = {**run.diagnostics,'constraint_eligibility':'INELIGIBLE'}
    selected = run.model_copy(update={'diagnostics':diagnostics})
    result = deepcopy(linked.result_snapshot)
    result['capacity'].setdefault('warnings',[]).append({'code':'speed-safe-max-proxy'})
    source = updated(linked,result=result)
    content = text(build_investor_report(selected,source)[0])
    assert 'препятствия для применения' in content
    assert 'оптимистичное допущение' in ' '.join(content.split())
    assert 'INELIGIBLE' not in content and 'speed-safe-max-proxy' not in content


def test_saved_simulation_is_bound_and_not_replaced_by_capacity_values(full):
    run,linked = full
    request = SimulationRequestV1.model_validate({
        'schema_version':'simulation-request-v1','request_id':'simulation.investor.test',
        'tenant_id':run.result_snapshot['tenant_id'],'project_id':run.project_id,
        'scenario_spec':run.scenario_spec_snapshot,'mode':'DAILY','peak_factor':None,'sla':None,'resources':[],
        'limits':{'max_jobs_per_day':10000,'max_fleet':100,'max_runtime_seconds':60,'progress_event_batch':1000},
    })
    report = run_simulation(request)
    artifact = StoredSimulationEvidence(artifact_id=uuid.uuid4(),analysis_run_id=uuid.UUID(run.run_id),
        project_id=uuid.UUID(run.project_id),request=request,report=report,request_digest=semantic_digest(request),
        report_digest=semantic_digest(report),scenario_spec_digest=semantic_digest(request.scenario_spec))
    content = text(build_investor_report(run,linked,artifact)[0])
    assert 'Завершено до конца окна' in content and artifact.report_digest not in content
    assert 'Выбранный сохранённый прогон проверен по источнику' in ' '.join(content.split())
    with pytest.raises(EvidenceExportIntegrityError):
        build_investor_report(run,linked,replace(artifact,analysis_run_id=uuid.uuid4()))
    with pytest.raises(EvidenceExportIntegrityError):
        build_investor_report(run,linked,replace(artifact,report_digest='sha256:'+'0'*64))


def test_investor_pdf_api_is_owner_scoped_integrity_bound_and_preserves_old_routes(full):
    run,linked = full
    owner = uuid.uuid4()
    def loader(_db,project_id,run_id,owner_id):
        if owner_id != owner or str(project_id)!=run.project_id:
            return None
        return {run.run_id:run,linked.run_id:linked}.get(str(run_id))
    app = FastAPI()
    app.include_router(create_evidence_export_router(loader,loader))
    app.dependency_overrides[require_auth_context] = lambda: SimpleNamespace(user=SimpleNamespace(id=owner))
    app.dependency_overrides[database_session] = lambda: object()
    client = TestClient(app)
    base = f'/api/projects/{run.project_id}/analysis-runs/{run.run_id}/exports'
    old = client.get(base+'/report.pdf').content
    download = client.get(base+'/investor-report.pdf')
    preview = client.get(base+'/investor-report-preview.pdf')
    assert download.status_code == preview.status_code == 200
    assert download.content == preview.content and download.content != old
    assert download.headers['X-Report-Depth'] == 'FULL'
    assert download.headers['X-Report-Presentation'] == VERSION
    assert download.headers['ETag'] == '"sha256:'+hashlib.sha256(download.content).hexdigest()+'"'
    assert download.headers['X-Report-Source-Digest'] == 'sha256:'+run.checksums['result']
    assert preview.headers['Content-Disposition'].startswith('inline')
    assert download.headers['Content-Disposition'].startswith('attachment')
    assert client.get(base+'/report.pdf').content == old
    assert client.get(base+'/investor-report.pdf?simulation_request_id=missing').status_code == 404
    app.dependency_overrides[require_auth_context] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    assert client.get(base+'/investor-report.pdf').status_code == 404
