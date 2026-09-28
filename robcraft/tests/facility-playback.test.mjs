import test from 'node:test';
import assert from 'node:assert/strict';
import { facilityCase } from './support/facility-case.js';
import { createFacilityPlan, createFacilityPlayback, facilityFrameAt, facilityRoute, pointAlong } from '../src/integration/facility-playback.js';
import { applyFacilityPlayback, updateFacilityCamera } from '../src/integration/facility-renderer.js';
import { generateWorldsFromScenarioSpec } from '../src/world/generator.js';
import { createSimulation, buildRendererReport } from '../src/simulation.js';
import { circleIntersectsSolid } from '../src/editor/collisions.js';
import { CameraDirector } from '../src/camera-director.js';

for (const template of ['airport', 'hospital']) {
  test(`${template}: plan binds saved task/fleet/route and does not mutate inputs`, () => {
    const { spec, report } = facilityCase(template), before = JSON.stringify({ spec, report });
    const plan = createFacilityPlan(spec), playback = createFacilityPlayback(plan, spec, report);
    assert.equal(plan.robots.length, spec.fleet[0].selected_fleet);
    assert.equal(plan.robots[0].taskId, spec.tasks[0].task_id);
    assert.equal(plan.robots[0].routeId, spec.tasks[0].route_ref);
    assert.equal(playback.jobs.length, report.workload.jobs_per_day * 2);
    facilityFrameAt(playback, 35000);
    assert.equal(JSON.stringify({ spec, report }), before);
  });
  test(`${template}: paths stay in facility, cross doors and avoid furniture in both views`, () => {
    const { spec } = facilityCase(template);
    const scene = generateWorldsFromScenarioSpec(spec, { facilityPlans: true }).zones[0].scene;
    const plan = scene.facilityPlan;
    for (let sequence = 0; sequence < 12; sequence++) for (const robot of plan.robots) {
      const route = facilityRoute(plan, robot.ordinal, sequence);
      for (const points of [route.outbound, route.work, route.returning]) for (let step = 0; step <= 100; step++) {
        const pose = pointAlong(points, step / 100);
        assert.ok(pose.x >= 0 && pose.x <= plan.width && pose.y >= 0 && pose.y <= plan.height);
        assert.equal(scene.solids.some(solid => circleIntersectsSolid(pose.x-24, pose.y-16, .61, solid)), false, JSON.stringify(pose));
      }
    }
  });
  test(`${template}: 3D matches 2D at any time, after pause, restart and a long seek`, () => {
    const { spec, report } = facilityCase(template);
    const scene = generateWorldsFromScenarioSpec(spec, { facilityPlans: true }).zones[0].scene;
    const sim = createSimulation(scene), playback = createFacilityPlayback(scene.facilityPlan, spec, report);
    for (const time of [0, 120, 300, 540, 900, 3600, 86400, 175000, 0, 300, 300]) {
      const frame = applyFacilityPlayback(sim, scene, report, time);
      assert.deepEqual(frame, facilityFrameAt(playback, time));
      sim.robots.forEach((robot,i) => {
        assert.deepEqual(robot.position, [frame.robots[i].x-24,.42,frame.robots[i].y-16]);
        assert.equal(robot.carrying, frame.robots[i].carrying);
      });
      assert.equal(buildRendererReport(sim, report).bindings.authoritative_report_digest, report.replay.report_content_digest);
    }
  });
}

test('clinic receives cargo, delivers through corridor, hands off and returns; targets rotate', () => {
  const { spec, report } = facilityCase('hospital'), plan = createFacilityPlan(spec);
  const playback = createFacilityPlayback(plan, spec, report);
  const at = time => facilityFrameAt(playback,time).robots[0];
  assert.equal(at(30).stage, 'LOAD');
  assert.equal(at(180).stage, 'OUTBOUND'); assert.equal(at(180).carrying, true);
  assert.equal(at(300).stage, 'UNLOAD');
  assert.equal(at(400).stage, 'RETURN'); assert.equal(at(400).carrying, false);
  assert.equal(at(700).stage, 'ALLOWANCE'); assert.equal(at(900).stage, 'WAITING');
  assert.equal(at(900).nextStartSeconds, 2880);
  assert.notEqual(at(180).areaLabel, at(3060).areaLabel);
  assert.equal(facilityFrameAt(playback,86400).completedJobs,30);
});

test('airport cleans serpentine strips across functional halls rather than a perimeter', () => {
  const { spec, report } = facilityCase(), plan = createFacilityPlan(spec);
  const playback = createFacilityPlayback(plan, spec, report);
  assert.equal(new Set(plan.robots.map(robot => facilityRoute(plan,robot.ordinal).areaId)).size,3);
  const cleaning = facilityFrameAt(playback,200).robots[0];
  assert.equal(cleaning.stage,'WORK'); assert.equal(cleaning.cleaning,true);
  assert.ok(cleaning.route.work.length >= 6);
  assert.ok(cleaning.x < 15);
  assert.deepEqual(facilityRoute(plan,0,0).home,facilityRoute(plan,0,plan.robots.length).home);
  assert.notEqual(facilityRoute(plan,0,0).areaId,facilityRoute(plan,0,plan.robots.length).areaId);
});

test('shift gaps freeze work and partial batches keep their actual units', () => {
  const { spec, report } = facilityCase('hospital');
  spec.operating_windows[0].duration.value = '1';
  spec.operating_windows.push({ ...structuredClone(spec.operating_windows[0]), window_id:'window.second', start_time: { ...spec.operating_windows[0].start_time, value:'7200' } });
  report.workload.jobs_per_day = 3; report.workload.simulated_units_per_day = '150';
  const playback = createFacilityPlayback(createFacilityPlan(spec),spec,report);
  assert.equal(playback.jobs[2].units,20);
  assert.equal(facilityFrameAt(playback,4000).robots[0].stage,'OFF_SHIFT');
  assert.deepEqual(facilityFrameAt(playback,4000).robots.map(r=>[r.x,r.y]),facilityFrameAt(playback,6000).robots.map(r=>[r.x,r.y]));
  assert.equal(playback.calendar.offsetAt(3600),7200);
});

test('Monday 09 start orders overnight windows and FIFO honors fleet saturation and resource capacity', () => {
  const { spec, report } = facilityCase('hospital');
  spec.operating_windows[0].start_time.value = '32400'; spec.operating_windows[0].duration.value = '15';
  spec.operating_windows.push({ ...structuredClone(spec.operating_windows[0]), window_id:'window.night', start_time: { ...spec.operating_windows[0].start_time, value:'0' }, duration: { ...spec.operating_windows[0].duration, value:'9' } });
  report.model_start = { seconds_from_midnight:32400, weekday:'MONDAY', timezone:'Europe/Moscow' };
  report.workload.jobs_per_day = 1000; report.workload.simulated_units_per_day = '65000';
  const playback = createFacilityPlayback(createFacilityPlan(spec),spec,report);
  assert.equal(playback.calendar.hours,86400); assert.equal(playback.calendar.isOpen(23*3600),true);
  assert.ok(playback.jobs[1].start > playback.jobs[1].release);
  assert.equal(playback.jobs[1].start,playback.jobs[0].end);
  spec.fleet[0].selected_fleet = 2;
  report.resources = [{ stage:'LOAD', capacity:1 }];
  const shared = createFacilityPlayback(createFacilityPlan(spec),spec,report);
  assert.ok(shared.jobs[1].timeline[0].start >= shared.jobs[0].timeline[0].end);
  report.resources = [{ stage:'UNLOAD', capacity:1 }];
  const handoff = createFacilityPlayback(createFacilityPlan(spec),spec,report);
  const second = handoff.jobs[1], unloading = second.timeline.find(stage=>stage.stage==='UNLOAD');
  const waiting = facilityFrameAt(handoff,handoff.calendar.offsetAt(unloading.start)-1).robots[second.robot];
  assert.equal(waiting.stage,'WAIT_RESOURCE'); assert.equal(waiting.carrying,true);
  assert.deepEqual([waiting.x,waiting.y],[waiting.route.handoff.x,waiting.route.handoff.y]);
});

test('zero fleet and zero demand show no fabricated work; camera frames operations inside facility', () => {
  const { spec, report } = facilityCase('hospital');
  report.workload.jobs_per_day = 0; report.workload.simulated_units_per_day = '0';
  const playback = createFacilityPlayback(createFacilityPlan(spec),spec,report);
  const frame = facilityFrameAt(playback,500);
  assert.equal(frame.robots[0].stage,'WAITING'); assert.equal(frame.completedJobs,0);
  const camera = new CameraDirector(); updateFacilityCamera(camera,frame,1);
  assert.ok(camera.position[1] >= 8); assert.ok(camera.caption.includes('Ожидание'));
  spec.fleet[0].selected_fleet = 0;
  const empty = facilityFrameAt(createFacilityPlayback(createFacilityPlan(spec),spec,report),0);
  assert.deepEqual(empty.robots,[]); assert.ok(empty.reason);
});
