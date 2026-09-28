"""Read-only E1/E10 evidence audit; never restores or writes the backup."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from calculation_contracts import semantic_digest

OUT = ROOT / 'docs/delivery/evgeny-feedback-2026-09-28'

def protected_hashes():
    roots = ['backup', 'backend/fixtures', 'data/golden', 'frontend/public/demo',
             'docs/delivery/f8', 'Разобрать/Материалы от организаторов']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in roots for p in (ROOT / root).rglob('*') if p.is_file()}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    hashes = protected_hashes()
    target = OUT / 'protected-hashes.json'
    if target.exists():
        expected = json.loads(target.read_text('utf-8'))
        assert all(hashes.get(k) == v for k, v in expected.items()), 'protected source changed'
    else:
        target.write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    manifest = json.loads((ROOT / 'backup/manifest.json').read_text('utf-8'))
    for name, item in manifest['members'].items():
        content = (ROOT / 'backup' / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item['sha256'], name
        if 'rows' in item:
            assert len(content.splitlines()) == item['rows'], name
    runs = [json.loads(line) for line in (ROOT / 'backup/database/analysis_runs.jsonl').read_text('utf-8').splitlines()]
    successful = [r for r in runs if r['status'] == 'SUCCEEDED']
    for row in successful:
        for field in ['input', 'result', 'scenario_spec', 'trace', 'version_bindings']:
            if row.get(field + '_sha256'):
                assert semantic_digest(row[field + '_snapshot']).removeprefix('sha256:') == row[field + '_sha256'], (row['id'], field)
    artifacts = [json.loads(line) for line in (ROOT / 'backup/database/simulation_artifacts.jsonl').read_text('utf-8').splitlines()]
    for row in artifacts:
        for field in ['request', 'report']:
            assert semantic_digest(row[field + '_snapshot']).removeprefix('sha256:') == row[field + '_sha256']
    cases = []
    for row in successful:
        source = row['input_snapshot']
        if row['run_kind'] != 'CAPACITY_ANALYSIS':
            continue
        process = source['process']
        value = row['result_snapshot'].get('capacity', {}).get('value')
        cases.append({'process': process['process_code'], 'demand': process['demand'].get('normalized_value'),
                      'schedule': {k: v.get('normalized_value') for k, v in (process.get('schedule') or {}).items()},
                      'distance': (process.get('route_distance') or {}).get('normalized_value'),
                      'batch': (process.get('explicit_batch') or {}).get('normalized_value'),
                      'capacity': value})
    report = {'backup_date': manifest['generated_at'], 'members_verified': len(manifest['members']),
              'successful_runs_verified': len(successful), 'runs': len(runs),
              'simulation_artifacts_verified': len(artifacts), 'protected_files': len(hashes), 'capacity_cases': cases}
    (OUT / 'baseline-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'capacity_cases'}))

if __name__ == '__main__':
    main()
