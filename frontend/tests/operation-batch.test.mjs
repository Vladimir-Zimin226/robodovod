import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateOperationBatch } from '../src/operationBatch.js';

const route = 'zone.main.warehouse_receiving_shipping';
const picking = 'zone.main.warehouse_picking';
const q = (value, unit) => ({ status:'KNOWN', normalized_value:value, unit });
const transport = { process_id:route, input_revision:'draft.4', active:true, object_kind:'WAREHOUSE',
  process_code:'warehouse_receiving_shipping', scope:'TRANSPORT_CYCLE',
  demand:q('2000','pallet/day'), route_distance:q('120','m'), explicit_batch:q('1','pallet/trip') };
const reference = { ...transport, process_id:picking, process_code:'warehouse_picking', scope:'REFERENCE_ONLY', demand:q('100','line/day') };
const normalized = { response:{ input_revision:'draft.4', normalized_processes:[transport, reference], role_pool:{ roles:[] } } };
const draft = { inputRevision:'draft.4', zones:[{ zoneId:'zone.main', label:'Главная' }],
  processes:[{ processId:route, exchangeSeconds:'90' }, { processId:picking }] };
const model = { position_id:'position.mule', model_id:'model.mule', calculation_profile:'TRANSPORT_CYCLE_V1', calculation_ready:true };

test('all selected operations enter one saved revision, unsupported picking stays visible', async () => {
  const calls = [];
  const fetcher = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    calls.push({ url, body });
    if (url.includes('/api/v2/capacity-catalog/positions')) return { ok:true, json:async () => ({items:[model]}) };
    if (url.includes('/candidate-comparisons/preview')) return { ok:true, json:async () => ({
      technical_recommendation:{position_id:model.position_id}, candidates:[{position_id:model.position_id,status:'SCORED'}]}) };
    if (url.endsWith('/capacity-analyses')) return { ok:true, json:async () => ({run_id:'run.transport'}) };
    return { ok:true, json:async () => ({operations:body.operations,project_id:'project.1'}) };
  };
  const result = await calculateOperationBatch({ fetcher, normalized, draft, projectId:'project.1', acknowledged:true, csrf:'token', batchId:'batch.1' });
  assert.equal(result.operations.length,2);
  assert.equal(result.operations[0].run_id,'run.transport');
  assert.match(result.operations[1].blocker,/формулы мощности/);
  assert.equal(calls.filter(item => item.url.endsWith('/capacity-analyses')).length,1);
  assert.deepEqual(calls.at(-1).body.operations.map(item => item.process.process_id),[route,picking]);
});

test('no technically admissible candidate blocks only its operation', async () => {
  let posted;
  const fetcher = async (url, options = {}) => {
    if (url.includes('/api/v2/capacity-catalog/positions')) return {ok:true,json:async () => ({items:[model]})};
    if (url.includes('/candidate-comparisons/preview')) return {ok:true,json:async () => ({candidates:[
      {position_id:model.position_id,status:'EXCLUDED',constraints:{checks:[{status:'FAIL',reason_code:'AISLE_TOO_NARROW'}]}}]})};
    if (url.includes('/capacity-analyses')) throw Error('Excluded candidate must never be saved');
    posted = JSON.parse(options.body);
    return {ok:true,json:async () => ({operations:posted.operations})};
  };
  const output = await calculateOperationBatch({fetcher,normalized,draft,projectId:'project.1',acknowledged:true,csrf:'token'});
  assert.equal(output.operations.length,2);
  assert.match(output.operations[0].blocker,/AISLE_TOO_NARROW/);
  assert.match(output.operations[1].blocker,/формулы мощности/);
});

test('airport cleaning and baggage both appear when baggage has no approved candidate', async () => {
  const clean = { ...transport, process_id:'zone.airport.airport_terminal_cleaning',
    object_kind:'AIRPORT', process_code:'airport_terminal_cleaning', scope:'CLEANING_AREA', demand:q('51000','m2/day') };
  const baggage = { ...transport, process_id:'zone.airport.airport_baggage',
    object_kind:'AIRPORT', process_code:'airport_baggage', demand:q('20000','item/day') };
  const input = { response:{ input_revision:'draft.4', normalized_processes:[clean,baggage], role_pool:{roles:[]} } };
  const local = { inputRevision:'draft.4', zones:[{zoneId:'zone.airport',label:'Терминал'}], processes:[
    {processId:clean.process_id,cleaningFrequency:'1'}, {processId:baggage.process_id,exchangeSeconds:'60'}] };
  const cleaner = {...model,position_id:'position.cleaner',calculation_profile:'CLEANING_AREA_V1'};
  let posted;
  const fetcher = async (url, options = {}) => {
    if (url.includes('/api/v2/capacity-catalog/positions')) return {ok:true,json:async () => ({items:url.includes('terminal_cleaning')?[cleaner]:[]})};
    if (url.includes('/candidate-comparisons/preview')) return {ok:true,json:async () => ({technical_recommendation:{position_id:cleaner.position_id},candidates:[{position_id:cleaner.position_id,status:'TECHNICAL_ONLY'}]})};
    if (url.endsWith('/capacity-analyses')) return {ok:true,json:async () => ({run_id:'run.cleaning'})};
    posted = JSON.parse(options.body);
    return {ok:true,json:async () => ({operations:posted.operations})};
  };
  const saved = await calculateOperationBatch({fetcher,normalized:input,draft:local,projectId:'project.airport',acknowledged:true,csrf:'token'});
  assert.deepEqual(saved.operations.map(item => item.process.process_id),[clean.process_id,baggage.process_id]);
  assert.equal(saved.operations[0].run_id,'run.cleaning');
  assert.match(saved.operations[1].blocker,/каталоге нет расчётной модели/);
});

test('warehouse transport and cleaning retain separate pallet and square-metre results', async () => {
  const cleaning = { ...transport, process_id:'zone.main.warehouse_cleaning',
    process_code:'warehouse_cleaning', scope:'CLEANING_AREA', demand:q('10000','m2/day') };
  const input = {response:{input_revision:'draft.4',normalized_processes:[transport,cleaning],role_pool:{roles:[]}}};
  const local = {...draft,processes:[draft.processes[0],{processId:cleaning.process_id,cleaningFrequency:'1'}]};
  const cleaner = {...model,position_id:'position.cleaner',calculation_profile:'CLEANING_AREA_V1'};
  let posted;
  const fetcher = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    if (url.includes('/api/v2/capacity-catalog/positions')) return {ok:true,json:async () => ({items:url.includes('warehouse_cleaning')?[cleaner]:[model]})};
    if (url.includes('/candidate-comparisons/preview')) return {ok:true,json:async () => ({
      technical_recommendation:{position_id:body.capacity_request.position_id},
      candidates:[{position_id:body.capacity_request.position_id,status:'TECHNICAL_ONLY'}]})};
    if (url.endsWith('/capacity-analyses')) return {ok:true,json:async () => ({run_id:`run.${body.position_id}`})};
    posted = body;
    return {ok:true,json:async () => ({operations:posted.operations})};
  };
  const saved = await calculateOperationBatch({fetcher,normalized:input,draft:local,projectId:'project.warehouse',acknowledged:true,csrf:'token'});
  assert.deepEqual(saved.operations.map(item => item.process.demand.unit),['pallet/day','m2/day']);
  assert.deepEqual(saved.operations.map(item => item.run_id),['run.position.mule','run.position.cleaner']);
});

test('retry reuses completed C11 rows and the same batch id after summary transport error', async () => {
  let capacityCalls = 0;
  let summaryCalls = 0;
  let checkpoint = [];
  const fetcher = async (url, options = {}) => {
    if (url.includes('/api/v2/capacity-catalog/positions')) return {ok:true,json:async () => ({items:[model]})};
    if (url.includes('/candidate-comparisons/preview')) return {ok:true,json:async () => ({technical_recommendation:{position_id:model.position_id},candidates:[{position_id:model.position_id,status:'TECHNICAL_ONLY'}]})};
    if (url.endsWith('/capacity-analyses')) { capacityCalls += 1; return {ok:true,json:async () => ({run_id:'run.once'})}; }
    summaryCalls += 1;
    if (summaryCalls === 1) throw Error('connection lost');
    return {ok:true,json:async () => JSON.parse(options.body)};
  };
  const args = {fetcher,normalized,draft,projectId:'project.1',acknowledged:true,csrf:'token',batchId:'batch.fixed',onCheckpoint:rows => { checkpoint = rows; }};
  await assert.rejects(calculateOperationBatch(args),/connection lost/);
  const saved = await calculateOperationBatch({...args,resumeOperations:checkpoint});
  assert.equal(capacityCalls,1);
  assert.equal(saved.batch_id,'batch.fixed');
  assert.equal(saved.operations[0].run_id,'run.once');
});
