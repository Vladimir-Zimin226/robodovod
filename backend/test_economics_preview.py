from decimal import Decimal
import jsonschema
import json
from pathlib import Path
from economics_preview import preview_charts
from economics_final import execute_economics_v4
from economics_partial import execute_partial_economics_v2
from test_economics_partial import _context
from test_evgeny_project import project_input


def test_server_chart_reconciles_cashflows_capex_and_net_benefit():
    snapshot, context = _context()
    result = execute_partial_economics_v2(project_input(), snapshot, context, full_engine=execute_economics_v4).result_snapshot
    charts = preview_charts(result)
    schema = json.loads((Path(__file__).resolve().parents[1] / 'contracts/economics-preview-charts-v1.schema.json').read_text('utf-8'))
    jsonschema.validate(charts, schema)
    for series in charts['series']:
        row = next(item for item in [result['comparison']['baseline'], *result['comparison']['scenarios']] if item['scenario_id'] == series['scenario_id'])
        points = series['points']
        assert points[0]['year'] == 0
        if row['metrics']['capex']['status'] == 'COMPLETE':
            assert Decimal(points[0]['cashflow']) == -Decimal(row['metrics']['capex']['value'])
        else:
            assert points[0]['cashflow'] is None
        assert [point['cashflow'] for point in points[1:]] == [flow['scenario'] for flow in row['annual_cashflows']]
        if row['acquisition'] != 'BASELINE':
            assert Decimal(points[-1]['cumulative_effect']) == Decimal(row['metrics']['net_benefit']['value'])


def test_partial_chart_does_not_invent_rows():
    assert preview_charts({'issues': []})['series'] == []
