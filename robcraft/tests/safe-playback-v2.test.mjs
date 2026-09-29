import test from 'node:test';
import assert from 'node:assert/strict';
import { facilityCase } from './support/facility-case.js';
import { createSafePlan, createSafePlayback, safeFrameAt, sweptSeparation, sweptHitsRectangle, LIVE_TIME_SCALE } from '../src/integration/safe-playback-v2.js';
import { generateWorldsFromScenarioSpec } from '../src/world/generator.js';
import { createSimulation } from '../src/simulation.js';
import { applyFacilityPlayback } from '../src/integration/facility-renderer.js';

import { playbackCase } from './support/safe-case.js';

for (const [template, fleets] of [['warehouse',[1,2,6,11,25]],['airport',[1,3,6,12]],['hospital',[1,2,4,8]],['baggage',[1,6]]]) {
  for (const count of fleets) test(`${template} ${count}: whole horizon, swept safety, shared 2D/3D and immutable source`,()=>{
    const {spec,report}=playbackCase(template,count), before=JSON.stringify({spec,report});
    const plan=createSafePlan(spec), playback=createSafePlayback(plan,spec,report);
    assert.equal(playback.jobs.length,report.workload.jobs_per_day*2,'no silently dropped tasks');
    const scene=generateWorldsFromScenarioSpec(spec,{safePlayback:true}).zones[0].scene;
    const simulation=createSimulation(scene);
    assert.equal(simulation.trafficCapacity,count);
    const minimum=2*plan.footprint.radius+plan.footprint.clearance;
    let maxActive=0;
    for(let t=0;t<=3*86400;t+=113) {
      const frame=safeFrameAt(playback,t);maxActive=Math.max(maxActive,frame.robots.filter(r=>!['WAITING','OFF_SHIFT','WAIT_RESOURCE'].includes(r.stage)).length);
      for(let i=0;i<count;i++)for(let j=i+1;j<count;j++)assert.ok(Math.hypot(frame.robots[i].x-frame.robots[j].x,frame.robots[i].y-frame.robots[j].y)>=minimum-1e-6,`separation at ${t}`);
    }
    for(const job of playback.jobs)for(const segment of job.segments) {
      for(const rect of [...plan.walls,...plan.furniture,...plan.environment.filter(item=>!item.overhead)])assert.equal(sweptHitsRectangle(segment.a,segment.b,rect,plan.footprint.radius+plan.footprint.clearance),false);
      for(const person of plan.people) {
        const standing={start:segment.start,end:segment.end,a:{x:person.x,y:person.y},b:{x:person.x,y:person.y}};
        assert.ok(sweptSeparation(segment,standing)>=plan.footprint.radius+plan.footprint.clearance+person.radius-1e-6,'person clearance');
      }
    }
    // Between-frame crossings are tested over exact overlapping linear intervals, not just screenshots.
    for(let i=0;i<playback.jobs.length;i++)for(let j=i+1;j<playback.jobs.length;j++) {
      const a=playback.jobs[i],b=playback.jobs[j];
      if(a.robot===b.robot||a.end<b.start||b.end<a.start)continue;
      for(const x of a.segments)for(const y of b.segments)assert.ok(sweptSeparation(x,y)>=minimum-1e-6);
    }
    for(const t of [0,60,300,3600,86400,175000,0,300,300]) {
      const frame=safeFrameAt(playback,t), actual=applyFacilityPlayback(simulation,scene,report,t);
      assert.deepEqual(actual.robots,frame.robots);
      simulation.robots.forEach((r,i)=>assert.deepEqual(r.position,[frame.robots[i].x-plan.width/2,.42,frame.robots[i].y-plan.height/2]));
    }
    assert.ok(maxActive>0);
    if(template==='warehouse'&&count>=6)assert.ok(maxActive>2,'no global two-robot ceiling');
    assert.equal(JSON.stringify({spec,report}),before);
    assert.deepEqual(createSafePlan(spec).environment,plan.environment,'environment is deterministic');
    for(const object of plan.environment.filter(item=>!item.overhead)) {
      for(const home of plan.homes)assert.equal(sweptHitsRectangle(home,home,object,plan.footprint.radius+plan.footprint.clearance),false);
    }
  });
}
test('crossing between samples, rectangle sweep and speed contract',()=>{
  assert.equal(LIVE_TIME_SCALE,60);
  assert.equal(sweptSeparation({start:0,end:1,a:{x:-2,y:0},b:{x:2,y:0}},{start:0,end:1,a:{x:0,y:-2},b:{x:0,y:2}}),0);
  assert.equal(sweptHitsRectangle({x:-2,y:0},{x:2,y:0},{x:-.1,y:-.1,width:.2,height:.2},.75),true);
});
test('partial batch, shift gap, night start, multiple fleet binding and impossible path',()=>{
  const {spec,report}=playbackCase('hospital',4);
  spec.operating_windows[0].start_time.value='79200';spec.operating_windows[0].duration.value='1';
  spec.operating_windows.push({...structuredClone(spec.operating_windows[0]),window_id:'second',start_time:{value:'0'}});
  report.model_start={seconds_from_midnight:79200};Object.assign(report.workload,{jobs_per_day:3,simulated_units_per_day:'150'});
  const plan=createSafePlan(spec),playback=createSafePlayback(plan,spec,report);
  assert.equal(playback.jobs[2].units,20);
  assert.deepEqual(safeFrameAt(playback,4000).robots.map(r=>[r.x,r.y]),safeFrameAt(playback,6000).robots.map(r=>[r.x,r.y]));
  assert.equal(safeFrameAt(playback,4000).open,false);
  assert.equal(safeFrameAt(playback,7200).open,true);
  spec.fleet.push({...structuredClone(spec.fleet[0]),fleet_id:'second.fleet',selected_fleet:2});
  assert.equal(createSafePlan(spec).robots.length,6);
  plan.walls.push({x:0,y:31,width:48,height:2});
  const blocked=createSafePlayback(plan,spec,report);
  assert.equal(blocked.jobs.length,0);assert.ok(blocked.reason);
  assert.ok(safeFrameAt(blocked,100).robots.every(r=>r.stage==='NO_PATH'));
});
