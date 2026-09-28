"""Read backup snapshots in memory and render new investor PDFs into a new folder.

No database connections or writes to backup, saved reports or artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

from pypdf import PdfReader
from calculation.evidence_export import EvidenceRunSnapshotV1
from calculation.final_export import build_final_export
from calculation.investor_report import build_investor_report


def saved_run(row):
    return EvidenceRunSnapshotV1.model_validate({
        'run_id':row['id'],'project_id':row['project_id'],'run_kind':row['run_kind'],
        'status':row['status'],'revision_id':row['revision_id'],
        'created_at':row['created_at'],'finished_at':row['finished_at'],
        'versions':{key:row.get(column) for key,column in [
            ('catalog','catalog_version_code'),('rules','rules_version'),('economics','economics_version'),
            ('object_profile','object_profile_version'),('application','application_version')]},
        'checksums':{key:row.get(column) for key,column in [
            ('input','input_sha256'),('result','result_sha256'),('scenario_spec','scenario_spec_sha256'),
            ('trace','trace_sha256'),('version_bindings','version_bindings_sha256')]},
        **{key:row[key] for key in ['input_snapshot','result_snapshot','scenario_spec_snapshot','trace_snapshot',
                                   'version_bindings_snapshot','diagnostics']},
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup',type=Path,default=ROOT/'backup')
    parser.add_argument('--output',type=Path,default=ROOT/'.tmp/investor-review')
    args = parser.parse_args()
    source_files = [p for p in args.backup.rglob('*') if p.is_file()]
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    rows = [json.loads(line) for line in (args.backup/'database/analysis_runs.jsonl').read_text('utf-8').splitlines()]
    by_id = {r['id']:r for r in rows}
    args.output.mkdir(parents=True,exist_ok=True)
    results = []
    for code in ['warehouse_receiving_shipping','airport_terminal_cleaning','clinic_food']:
        candidates = [r for r in rows if r['status']=='SUCCEEDED' and r['run_kind']=='FULL_ANALYSIS'
            and by_id.get(r['input_snapshot'].get('capacity_run_id'),{}).get('input_snapshot',{}).get('process',{}).get('process_code')==code]
        if not candidates:
            continue
        # Prefer a complete comparison, then the most recent persisted calculation.
        row = max(candidates,key=lambda r:(r['result_snapshot'].get('schema_version')=='commercial-scenarios-bundle-v3',r['finished_at']))
        run = saved_run(row)
        linked = saved_run(by_id[row['input_snapshot']['capacity_run_id']])
        old = build_final_export(run,linked)
        pdf,digest = build_investor_report(run,linked)
        assert build_investor_report(run,linked)[0] == pdf
        assert build_final_export(run,linked).archive == old.archive
        target = args.output/(code+'.pdf')
        target.write_bytes(pdf)
        results.append({'process':code,'run':run.run_id,'depth':run.input_snapshot.get('economics',{}).get('calculation_depth'),
            'result_digest':digest,'pages':len(PdfReader(io.BytesIO(pdf)).pages),'pdf':str(target)})
    assert before == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},'backup changed'
    print(json.dumps({'backup_files_unchanged':len(before),'reports':results},ensure_ascii=False,indent=2))
    (args.output/'verification.json').write_text(json.dumps({'backup_files_unchanged':len(before),'reports':results},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
