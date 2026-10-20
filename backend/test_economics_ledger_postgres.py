"""Persisted v7 economics on a disposable, activated PostgreSQL database."""

import io
import os
import uuid

import main
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from catalog_repository import ActivatedCatalogRepository
from test_product_chain_money_postgres import capacity_input
from test_production_economics_integration import activated_actual_catalog  # noqa: F401
from test_evgeny_project import project_input

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='disposable PostgreSQL required')


def test_v7_cost_lines_survive_api_save_reopen_and_pdf(activated_actual_catalog):
    snapshot = ActivatedCatalogRepository(activated_actual_catalog, 'capacity').load()
    with TestClient(main.app) as client:
        registration = client.post('/api/auth/register', json={
            'email': f'ledger-{uuid.uuid4()}@example.com', 'password': 'local acceptance passphrase',
            'name': 'Ledger acceptance', 'privacy_consent': True, 'privacy_policy_version': 'privacy-draft-2026-10-20'})
        assert registration.status_code == 201, registration.text
        headers = {'X-CSRF-Token': registration.json()['csrf_token']}
        project_response = client.post('/api/projects', headers=headers, json={'name': 'Ledger acceptance'})
        assert project_response.status_code == 201, project_response.text
        project = project_response.json()
        scenario = next(item for item in project['scenarios'] if item['slot'] == 'BASE')
        capacity_response = client.post('/api/v2/capacity-analyses', headers=headers,
                                        json=capacity_input('warehouse', snapshot, project['id']))
        assert capacity_response.status_code == 201, capacity_response.text
        capacity = capacity_response.json()
        raw = project_input()
        raw.update(schema_version='economics-explicit-inputs-v7', implementation_cost_total_gross='0',
                   role_work_profiles=[{
                       'role_id': 'role.driver', 'robotizable_fraction': '0.5',
                       'manual_units_per_shift': raw['manual_units_per_shift'],
                       'process_allocation_fraction': '1',
                       'residual_operations': 'Manual inspection remains',
                       'source': 'ASSUMPTION',
                       'basis': 'RW-WH-FORKLIFT-01: confirmed scenario assumption, not a site measurement',
                       'confirmed': True,
                   }],
                   implementation_lines={
                       'DELIVERY': {'status': 'USER_ESTIMATE', 'amount': '150000', 'source_ref': 'Смета 17.10.2026'},
                       'COMMISSIONING': {'status': 'EXPLICIT_ZERO', 'amount': '0', 'explanation': 'Свой персонал'},
                       'INTEGRATION': {'status': 'POLICY_ASSUMPTION', 'amount': '220000',
                                       'source_ref': 'Допущение проекта', 'explanation': 'Согласовать с ИТ'},
                   })
        endpoint = f"/api/v2/projects/{project['id']}/economics-runs"
        created = client.post(endpoint, headers=headers, json={
            'scenario_id': scenario['id'], 'capacity_run_id': capacity['run_id'], 'input': raw})
        assert created.status_code == 201, created.text
        run = created.json()
        assert run['input_snapshot']['schema_version'] == 'economics-run-input-v8'
        assert run['versions']['application'] == 'production-economics-orchestrator-v6'
        assert run['result_snapshot']['role_work_profiles'][0]['process_allocation_fraction'] == '1'
        assert run['result_snapshot']['role_labour']['roles'][0]['role_id'] == 'role.driver'
        assert run['result_snapshot']['implementation_coverage']['known_subtotal_gross_rub'] == '370000.00'
        assert run['result_snapshot']['implementation_coverage']['status'] == 'COMPLETE'
        reopened = client.get(f"/api/projects/{project['id']}/analysis-runs/{run['id']}")
        assert reopened.status_code == 200
        assert reopened.json()['result_snapshot'] == run['result_snapshot']
        replay = client.post(f"{endpoint}/{run['id']}/replay", headers=headers)
        assert replay.status_code == 200 and replay.json()['status'] == 'MATCH', replay.text
        assert replay.json()['result_sha256'] == run['checksums']['result']
        pdf = client.get(f"/api/projects/{project['id']}/analysis-runs/{run['id']}/exports/investor-report.pdf")
        assert pdf.status_code == 200, pdf.text if pdf.status_code != 200 else ''
        pdf_text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
        assert 'Пусконаладка' in pdf_text and '370' in pdf_text
        raw['implementation_lines']['COMMISSIONING'] = {'status': 'UNKNOWN', 'amount': None}
        partial = client.post(endpoint, headers=headers, json={
            'scenario_id': scenario['id'], 'capacity_run_id': capacity['run_id'], 'input': raw})
        assert partial.status_code == 201, partial.text
        result = partial.json()['result_snapshot']
        assert result['implementation_coverage']['status'] == 'PARTIAL'
        assert result['branches']['purchase']['status'] == 'NOT_CALCULATED'
