"""Presentation series derived from saved server cashflows, never client finance."""
from decimal import Decimal


def preview_charts(result: dict) -> dict:
    comparison = result.get('comparison') or {}
    series = []
    for row in [comparison.get('baseline'), *comparison.get('scenarios', [])]:
        if not row:
            continue
        capex = row.get('metrics', {}).get('capex', {})
        cumulative = -Decimal(capex['value']) if capex.get('status') == 'COMPLETE' else None
        points = [{'year': 0, 'cashflow': str(cumulative) if cumulative is not None else None,
                   'cumulative_effect': str(cumulative) if cumulative is not None else None}]
        for flow in row.get('annual_cashflows', []):
            effect = flow.get('effect')
            if cumulative is not None and effect is not None:
                cumulative += Decimal(effect)
            else:
                cumulative = None
            points.append({'year': flow['year'], 'cashflow': flow['scenario'],
                           'cumulative_effect': format(cumulative, '.2f') if cumulative is not None else None})
        series.append({'scenario_id': row['scenario_id'], 'points': points})
    return {'schema_version': 'economics-preview-charts-v1', 'currency': 'RUB', 'series': series,
            'basis': 'Год 0: денежный CAPEX; далее сохранённые годовые потоки. Накопленный эффект против baseline, без дисконтирования.'}
