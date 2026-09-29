"""Synthetic UI acceptance, local Vite on port 5189; never submits production forms."""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from local_browser import LocalBrowser, ROOT

sys.path[:0] = [str(ROOT / 'backend'), str(ROOT)]
from calculation.labour import manual_productivity_estimate
from economics_partial import execute_partial_economics_v2
from test_economics_partial import _context
from test_evgeny_project import project_input
from test_candidate_comparison_api import cohort, request
from candidate_comparison_api import CompareRequest, compare_candidates

OUT = ROOT / '.test-product-chain-implementation/session/ui'
HARNESS = ROOT / 'frontend/.test-product-chain'
TECHNICAL = re.compile(r'\b(?:[CFRK]\d{2}|UNKNOWN|NORMALIZED|N_A)\b|sha256:|[0-9a-f]{8}-[0-9a-f]{4}-|backend/test_|registry[./]|conversion[./]')


def prepare(baseline=False):
    HARNESS.mkdir(parents=True, exist_ok=True)
    snapshot, context = _context()
    inputs = project_input()
    inputs['work_share'].update(fraction='0.8', residual_operations='Ручная проверка, приём груза и работа с исключениями')
    inputs['purchase_price_override_gross'] = '2500000'
    inputs['purchase_price_source'] = 'Авторский пример от 29.09.2026'
    execution = execute_partial_economics_v2(inputs, snapshot, context)
    result = execution.result_snapshot
    source = context.capacity_request.model_dump(mode='json')
    fixture = {'input': inputs, 'result': result, 'capacityInput': source,
        'capacityResult': context.capacity_response.model_dump(mode='json'),
        'estimate': {**manual_productivity_estimate(context.capacity_request.process),
            'source_run_id': 'capacity', 'input_revision': source['input_revision']}}
    catalog = cohort()
    fixture['comparison'] = compare_candidates(request(), catalog, CompareRequest(source_run_id='00000000-0000-4000-8000-000000000001',
        position_ids=[p.id for p in catalog.positions][:3]))
    fixture['options'] = {'source_position_id': catalog.positions[0].id, 'items': [
        {'position_id': p.id, 'name': p.model.name, 'maturity_status': p.model.maturity_status,
            'calculation_ready': p.model.capacity_runtime.calculation_ready, 'price_status': p.procurement_option.price_status,
            'comparison_note': 'Пригодность и ограничения требуют проверки',
            'media': {'url': './thumbnail.svg', 'width_px': 100, 'height_px': 80} if i == 0 else None}
        for i, p in enumerate(catalog.positions)], 'finance_options': []}
    (HARNESS / 'fixture.json').write_text(json.dumps(fixture, ensure_ascii=False), encoding='utf-8')
    (HARNESS / 'thumbnail.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><rect x="20" y="20" width="60" height="40" rx="8" fill="#059669"/></svg>', encoding='utf-8')
    modules = ['SavedEconomicsEditor', 'CommercialScenariosV2', 'CandidateComparisonPanel']
    if baseline:
        for module in modules + ['EconomicsInputsV2']:
            body = subprocess.check_output(['git', '-c', f'safe.directory={ROOT.as_posix()}', 'show',
                f'9d6f1ce:frontend/src/components/{module}.jsx']).decode('utf-8')
            body = re.sub(r"from '([.][.]/[^']+)'", lambda m: "from '/src/" + m[1][3:] + "'", body)
            body = re.sub(r"from '[.](/[^']+)'", lambda m: "from '/src/components" + m[1] + "'", body)
            if module == 'SavedEconomicsEditor':
                body = body.replace("'/src/components/EconomicsInputsV2'", "'./EconomicsInputsV2.jsx'")
            (HARNESS / f'{module}.jsx').write_text(body, encoding='utf-8')
    imports = '\n'.join(f"import {module} from '{'./' if baseline else '/src/components/'}{module}.jsx';" for module in modules)
    (HARNESS / 'harness.html').write_text('''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><body><div id="root"></div><script type="module">
import React from 'react'; import {createRoot} from 'react-dom/client'; import '/src/index.css';
''' + imports + '''
const root=createRoot(document.getElementById('root')); const realFetch=window.fetch.bind(window);
const fixture=await (await realFetch('./fixture.json')).json(); window.calls=[];
window.fetch=async(url,opts={})=>{window.calls.push(url);let body;
 if(url.endsWith('/manual-productivity-estimate')) body=fixture.estimate;
 else if(url.includes('/candidate-comparisons/')&&opts.method==='POST')body=fixture.comparison;
 else if(url.includes('/candidate-comparisons/'))body=fixture.options;
 else if(url.endsWith('/capacity'))body={id:'capacity',run_kind:'CAPACITY_ANALYSIS',input_snapshot:fixture.capacityInput,result_snapshot:fixture.capacityResult};
 else return realFetch(url,opts); return new Response(JSON.stringify(body),{status:200});};
const project={id:'project',name:'Учебный склад',scenarios:[{id:'scenario',slot:'BASE'}]};
const run={id:'run',input_snapshot:{capacity_run_id:'capacity',economics:fixture.input},result_snapshot:fixture.result};
window.show=kind=>root.render(React.createElement('main',{style:{maxWidth:'1120px',margin:'0 auto',padding:'16px'}},
kind==='editor'?React.createElement(SavedEconomicsEditor,{project,run,autoOpen:true}):
kind==='compare'?React.createElement(CandidateComparisonPanel,{project,capacityRunId:'capacity'}):
React.createElement(CommercialScenariosV2,{bundle:fixture.result,projectName:'Учебный склад'})));
window.ready=true;
</script></body></html>''', encoding='utf-8')


def main():
    baseline = '--baseline' in sys.argv
    prepare(baseline)
    browser = LocalBrowser('http://127.0.0.1:5189/.test-product-chain/harness.html', OUT / ('baseline' if baseline else 'acceptance'))
    evidence = {'baseline': baseline, 'checks': []}
    try:
        browser.until('window.ready')
        for screen in ['editor', 'commercial', 'compare']:
            browser.js(f"window.show('{screen}')")
            browser.until("!!document.querySelector('section')")
            if screen == 'editor':
                browser.until("!!document.querySelector('.economics-inputs-v2')")
                browser.until("document.querySelector('[aria-label=\"Оценка ручной выработки\"]')?.innerText.includes('≈')")
            elif screen == 'compare':
                browser.until("document.body.innerText.includes('Оценить выбранные')")
                browser.js("[...document.querySelectorAll('input[type=checkbox]')].forEach(x=>{if(!x.checked&&!x.disabled)x.click()});[...document.querySelectorAll('button')].find(x=>x.textContent==='Оценить выбранные позиции').click()")
                browser.until("document.body.innerText.includes('Технический вывод:')")
            browser.js("document.querySelectorAll('details').forEach(x=>x.open=true)")
            time.sleep(.2)
            text = browser.js('document.body.innerText')
            tokens = TECHNICAL.findall(text)
            evidence['checks'].append({'screen': screen, 'technical_tokens': tokens})
            (browser.output / f'{screen}.txt').write_text(text, encoding='utf-8')
            if not baseline:
                assert not tokens, (screen, tokens)
            for width in [390, 768, 1366]:
                for zoom in [1, 1.25, 2]:
                    browser.viewport(width, zoom)
                    time.sleep(.1)
                    geometry = browser.js("(()=>{const bad=[...document.querySelectorAll('.labour-field')].filter(x=>{const l=x.querySelector('label').getBoundingClientRect(),v=x.querySelector('input,select,textarea').getBoundingClientRect();return l.bottom>v.top+.1});return {pageOverflow:document.documentElement.scrollWidth>window.innerWidth+1,overlaps:bad.length,linked:[...document.querySelectorAll('.labour-field label')].every(x=>document.getElementById(x.htmlFor))}})()")
                    evidence['checks'].append({'screen': screen, 'width': width, 'zoom': zoom, **geometry})
                    if not baseline:
                        if geometry['pageOverflow'] or geometry['overlaps'] or not geometry['linked']:
                            browser.screenshot(f'failure-{screen}-{width}-{zoom}.png')
                            print(browser.js("({bodyMin:getComputedStyle(document.body).minWidth,htmlMin:getComputedStyle(document.documentElement).minWidth,styles:[...document.querySelectorAll('style')].map(x=>x.textContent.includes('Browser zoom')),offenders:[...document.querySelectorAll('body *')].filter(x=>x.getBoundingClientRect().right>window.innerWidth+1).map(x=>({tag:x.tagName,cls:x.className,right:x.getBoundingClientRect().right,text:x.innerText?.slice(0,90)})).slice(0,12)})"), flush=True)
                        assert not geometry['pageOverflow'] and not geometry['overlaps'] and geometry['linked'], evidence['checks'][-1]
                browser.viewport(width)
                browser.screenshot(f'{screen}-{width}.png')
        if baseline:
            assert any(x.get('technical_tokens') for x in evidence['checks'])
        else:
            assert not any('/positions/' in url for url in browser.js('window.calls'))
        (browser.output / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'baseline': baseline, 'checks': len(evidence['checks'])}))
    finally:
        browser.close()


if __name__ == '__main__':
    main()
