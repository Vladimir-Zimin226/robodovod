import test from 'node:test';
import assert from 'node:assert/strict';
import { facilityCase } from '../../robcraft/tests/support/facility-case.js';
import { FACILITY_TIME_SCALE } from '../../robcraft/src/integration/facility-playback.js';
import { createTimelineState, reduceTimeline, buildSimulationScene, parseSimulationBundle, frameAt } from '../src/simulation2dModel.js';

test('facility speed immediately multiplies model time, pause freezes, restart and seek are deterministic', () => {
  let state = reduceTimeline(createTimelineState('test'),{type:'START'});
  const tick = s => reduceTimeline(s,{type:'TICK',deltaMs:1000,modelSecondsPerRealSecond:FACILITY_TIME_SCALE});
  state = tick(state); assert.equal(state.simulationTimeUs,60_000_000);
  state = reduceTimeline(state,{type:'SET_SPEED',speed:4}); state=tick(state);
  assert.equal(state.simulationTimeUs,300_000_000);
  state = reduceTimeline(state,{type:'PAUSE'}); assert.deepEqual(tick(state),state);
  state = reduceTimeline(state,{type:'SEEK',simulationTimeUs:180_000_000});
  assert.equal(state.status,'PAUSED');
  state = reduceTimeline(state,{type:'RESTART'}); assert.equal(state.simulationTimeUs,0);
  assert.equal(state.speed,4); assert.equal(state.restart,1);
  assert.throws(()=>reduceTimeline(state,{type:'SEEK',simulationTimeUs:-1}));
});

test('live plans bind both templates to saved report and preserve analytical distance, legacy captures remain separate', () => {
  for (const template of ['airport','hospital']) {
    const {request,report} = facilityCase(template), bundle = parseSimulationBundle(request,report);
    const scene = buildSimulationScene(bundle.spec,{facilityPlans:true,report});
    assert.equal(scene.kind,'FACILITY_PROCESS');
    const frame = frameAt(scene,bundle,180_000_000);
    assert.equal(frame.reportDigest,report.replay.report_content_digest);
    assert.equal(frame.robots.length,bundle.spec.fleet[0].selected_fleet);
    assert.equal(scene.plans[0].route?.one_way_distance?.value,template==='hospital'?'180':undefined);
    assert.equal(buildSimulationScene(bundle.spec).kind,undefined);
  }
});
