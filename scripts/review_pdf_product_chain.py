"""Read-only diagnostic input; all real PDFs and raster evidence remain ignored."""
import hashlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'backend'),str(ROOT/'.test-product-chain-implementation/pdf-tools')]
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pypdf import PdfReader
from calculation.evidence_export import EvidenceRunSnapshotV1
from calculation.investor_report import build_investor_report
from calculation.investor_report_v2 import build_investor_report as build_v2
from calculation_contracts import semantic_digest

OUT = ROOT/'.test-product-chain-implementation/session/pdf-review'
TOKENS = re.compile(r'\b[CFRK]\d{2}\b|sha256:|[0-9a-f]{8}-[0-9a-f]{4}-|backend/test_|registry[./]|conversion[./]|\b(?:NORMALIZED|UNKNOWN|PERCENT|FIXED|N_A)\b')


def snapshot(row):
    return EvidenceRunSnapshotV1.model_validate({
        'run_id':row['id'], **{k:row[k] for k in ['project_id','run_kind','status','revision_id','created_at','finished_at','input_snapshot','result_snapshot','scenario_spec_snapshot','trace_snapshot','version_bindings_snapshot','diagnostics']},
        'versions':{k:row[v] for k,v in {'catalog':'catalog_version_code','rules':'rules_version','economics':'economics_version','object_profile':'object_profile_version','application':'application_version'}.items()},
        'checksums':{k:row[v] for k,v in {'input':'input_sha256','result':'result_sha256','scenario_spec':'scenario_spec_sha256','trace':'trace_sha256','version_bindings':'version_bindings_sha256'}.items()}})


def main():
    OUT.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'backup/manifest.json').read_text(encoding='utf-8'))
    for path,item in manifest['members'].items():
        assert hashlib.sha256((ROOT/'backup'/path).read_bytes()).hexdigest()==item['sha256']
    rows=[json.loads(line) for line in (ROOT/'backup/database/analysis_runs.jsonl').read_text(encoding='utf-8').splitlines()]
    runs={row['id']:snapshot(row) for row in rows}
    sources=[]
    for index,run in enumerate(runs.values()):
        linked=runs.get(run.input_snapshot.get('capacity_run_id')); before=run.model_dump_json()
        old=build_v2(run,linked)[0];pdf,digest=build_investor_report(run,linked)
        assert digest=='sha256:'+run.checksums['result'] and run.model_dump_json()==before
        assert build_v2(run,linked)[0]==old
        (OUT/f'historical-{index+1:02d}.pdf').write_bytes(pdf)
        sources.append(OUT/f'historical-{index+1:02d}.pdf')
    # Synthetic layout stress case. The saved source remains untouched.
    original=next(run for run in runs.values() if run.result_snapshot.get('comparison'))
    raw=original.model_dump(mode='json')
    long_source='Подтверждённый пользователем источник для проверки длинного описания цены и условий поставки на объекте. ' * 4
    long_operation='Осмотр упаковки и проверка документов при приёмке каждой партии остаются ручной работой персонала. ' * 4
    raw['result_snapshot']['comparison']['inputs']['price']['source_note']=long_source
    raw['result_snapshot']['work_share']={'fraction':'0.8','residual_operations':long_operation}
    raw['input_snapshot']['economics']['purchase_price_source']=long_source
    for key in ('input','result'):
        raw['checksums'][key]=semantic_digest(raw[f'{key}_snapshot']).removeprefix('sha256:')
    stressed=EvidenceRunSnapshotV1.model_validate(raw)
    content,_=build_investor_report(stressed,runs.get(stressed.input_snapshot.get('capacity_run_id')))
    assert 'Осмотр упаковки и проверка документов' in '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(content)).pages)
    long_path=OUT/'synthetic-long-source.pdf';long_path.write_bytes(content);sources.append(long_path)
    sources += sorted((ROOT/'.test-product-chain-implementation/session/money-pdfs').rglob('*.pdf'))
    pages=[]; records=[]
    for path in sources:
        data=path.read_bytes();reader=PdfReader(io.BytesIO(data));content='\n'.join(p.extract_text() or '' for p in reader.pages)
        assert not TOKENS.findall(content),(path.name,TOKENS.findall(content))
        for page in reader.pages:
            fonts=page['/Resources']['/Font']
            assert fonts, path.name
            for reference in fonts.values():
                font=reference.get_object()
                descendant=(font.get('/DescendantFonts') or [font])[0].get_object()
                descriptor=descendant.get('/FontDescriptor')
                assert descriptor and any(key in descriptor.get_object() for key in ('/FontFile','/FontFile2','/FontFile3')), (path.name,font.get('/BaseFont'))
                assert '/ToUnicode' in font, (path.name,font.get('/BaseFont'))
        document=pdfium.PdfDocument(data)
        for index,page in enumerate(document):
            assert page.get_size()==(842.0,595.0)
            text=page.get_textpage()
            assert text.count_chars()>30
            for character in range(text.count_chars()):
                left,bottom,right,top=text.get_charbox(character)
                assert left>=-1 and right<=843 and bottom>=-1 and top<=596,(path.name,index,left,bottom,right,top)
            bitmap=page.render(scale=1.4).to_pil()
            name=f'{path.stem}-{index+1:02d}.png';bitmap.save(OUT/name)
            pages.append((name,bitmap.copy()))
            text.close();page.close()
        records.append({'file':path.name,'pages':len(reader.pages),'sha256':hashlib.sha256(data).hexdigest(),'all_pages_rendered':True,'searchable':True,'embedded_fonts':True,'technical_tokens':0})
        document.close()
    # Every rendered page is included exactly once in a labelled contact sheet.
    for offset in range(0,len(pages),12):
        sheet=Image.new('RGB',(1260,1240),'#dbe5e7');draw=ImageDraw.Draw(sheet)
        for index,(name,bitmap) in enumerate(pages[offset:offset+12]):
            bitmap.thumbnail((412,291));x=(index%3)*420+4;y=(index//3)*310+18
            sheet.paste(bitmap,(x,y));draw.text((x,y-15),name,fill='black')
        sheet.save(OUT/f'contact-{offset//12+1:02d}.jpg',quality=90)
    (OUT/'evidence.json').write_text(json.dumps({'backup_members_verified':len(manifest['members']),'historical_runs':len(runs),'pdfs':records,'pages':len(pages)},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pdfs':len(sources),'pages':len(pages),'backup_members_verified':len(manifest['members'])}))


if __name__=='__main__':main()
