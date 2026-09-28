"""Read-only evidence for the 28 September review; no database or engine writes."""
from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'scripts')]
from calculation.evidence_export import _verify_snapshots
from calculation_contracts import semantic_digest
from investor_report_smoke import saved_run


def main():
    backup = ROOT / 'backup'
    paths = [p for p in backup.rglob('*') if p.is_file()]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    manifest = json.loads((backup / 'manifest.json').read_text('utf-8'))
    assert all(before[backup / name] == meta['sha256'] for name, meta in manifest['members'].items())
    runs = [json.loads(line) for line in (backup / 'database/analysis_runs.jsonl').read_text('utf-8').splitlines()]
    by_id = {run['id']: run for run in runs}
    completed = [run for run in runs if run['status'] == 'SUCCEEDED']
    for run in completed:
        _verify_snapshots(saved_run(run))
    artifacts = [json.loads(line) for line in (backup / 'database/simulation_artifacts.jsonl').read_text('utf-8').splitlines()]
    for artifact in artifacts:
        for key, snapshot in [('request', 'request_snapshot'), ('report', 'report_snapshot')]:
            assert semantic_digest(artifact[snapshot]) == 'sha256:' + artifact[key + '_sha256']
        assert semantic_digest(artifact['request_snapshot']['scenario_spec']) == 'sha256:' + artifact['scenario_spec_sha256']
    c = by_id['55400598-a004-45c8-ba1d-19b85049f841']
    e = by_id['135d7eaf-2543-44d3-9302-182f656ea627']
    trace = {item['name']: item['normalized_value'] for item in c['result_snapshot']['trace']['inputs']}
    recommended = (Decimal(trace['cleaning_area']) * Decimal(trace['cleaning_frequency']) /
                   (Decimal(trace['cleaning_rate']) * Decimal(trace['shifts_per_day']) * Decimal(trace['shift_hours']) * Decimal(trace['availability']))).to_integral_value(rounding=ROUND_CEILING)
    assert int(recommended) == c['result_snapshot']['capacity']['value']['recommended_fleet'] == 2
    manual_per_shift = Decimal('300') * Decimal('8') * Decimal('0.85')
    person_shifts = (Decimal(trace['demand_per_day']) / manual_per_shift).to_integral_value(rounding=ROUND_CEILING)
    rotation = max(Decimal(1), Decimal(7) / (Decimal(40) / Decimal(8)) * Decimal('1.090')) * Decimal('1.35')
    people_required = (person_shifts * rotation).to_integral_value(rounding=ROUND_CEILING)
    actual_fot = Decimal('30') * Decimal('65000') * Decimal(12) * Decimal('1.55')
    deficit_cost = (people_required - 30) * Decimal('65000') * Decimal(12) * Decimal('1.302')
    purchase = next(s for s in e['result_snapshot']['scenarios'] if s['acquisition'] == 'PURCHASE' and s['uncertainty'] == 'BASE')
    comparison = next(s for s in e['result_snapshot']['comparison']['scenarios'] if s['acquisition'] == 'PURCHASE' and s['uncertainty'] == 'BASE')
    assert -(actual_fot + deficit_cost) == Decimal(purchase['financial']['annual_ledgers'][0]['primary_cf_base'])
    assert -actual_fot == Decimal(purchase['report_facts']['annual_cashflows'][0]['baseline'])
    summary = {'backup_generated_at': manifest['generated_at'], 'backup_files_unchanged': len(before),
               'runs': len(runs), 'verified_succeeded_runs': len(completed), 'verified_simulation_artifacts': len(artifacts),
               'airport': {'capacity_run_id': c['id'], 'economics_run_id': e['id'], 'capacity_trace_inputs': trace,
                           'capacity': c['result_snapshot']['capacity']['value'],
                           'role_conservation': purchase['allocation']['role_conservation'],
                           'control_required': purchase['allocation']['control_required_once'],
                           'technicians_required': purchase['allocation']['technicians_required_once'],
                           'manual_per_person_per_shift_m2': str(manual_per_shift),
                           'person_shifts': str(person_shifts), 'rotation': str(rotation),
                           'normative_required_people': str(people_required), 'hypothetical_deficit_cost': str(deficit_cost),
                           'direct_process_discounted_payback': purchase['financial']['discounted_payback'],
                           'project_discounted_payback': comparison['metrics']['discounted_payback'],
                           'direct_process_npv': purchase['financial']['npv_project'], 'project_npv': comparison['metrics']['npv'],
                           'direct_baseline_first_year': purchase['financial']['annual_ledgers'][0]['primary_cf_base'],
                           'project_baseline_first_year': purchase['report_facts']['annual_cashflows'][0]['baseline']}}
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    target = ROOT / '.tmp/evgeny-review-evidence.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
