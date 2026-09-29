// Read-only verification of the latest saved 15-robot warehouse artifact.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createSafePlan, createSafePlayback, safeFrameAt } from '../robcraft/src/integration/safe-playback-v2.js';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const backup = join(root, 'backup');
const manifest = JSON.parse(readFileSync(join(backup, 'manifest.json'), 'utf8'));
for (const [name, details] of Object.entries(manifest.members)) {
  const digest = createHash('sha256').update(readFileSync(join(backup, name))).digest('hex');
  assert.equal(digest, details.sha256, `backup/${name} changed`);
}
const artifacts = readFileSync(join(backup, 'database/simulation_artifacts.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
const warehouse = artifacts.filter(row => row.request_snapshot.scenario_spec.template === 'warehouse'
  && row.request_snapshot.scenario_spec.fleet.reduce((sum, fleet) => sum + fleet.selected_fleet, 0) === 15)
  .sort((a, b) => b.created_at.localeCompare(a.created_at));
assert.ok(warehouse.length, 'No saved 15-robot warehouse artifact');
const artifact = warehouse[0], spec = artifact.request_snapshot.scenario_spec, report = artifact.report_snapshot;
const original = JSON.stringify({ spec, report });
const plan = createSafePlan(spec), playback = createSafePlayback(plan, spec, report);
assert.equal(plan.robots.length, 15);
assert.equal(plan.furniture.filter(item => item.type === 'rack').length, 15);
assert.equal(plan.environment.filter(item => item.type === 'rack').length, 15);
assert.equal(playback.jobs.length, report.workload.jobs_per_day * 2);
assert.equal(playback.unscheduledJobs, 0);
assert.equal(playback.noPath.size, 0);
const jobsPerRobot = playback.byRobot.map(rows => rows.length);
assert.ok(Math.min(...jobsPerRobot) > 0 && Math.max(...jobsPerRobot) - Math.min(...jobsPerRobot) <= 1);
const cycle = [['left', 'far'], ['right', 'far'], ['left', 'near'], ['right', 'near']];
for (const rows of playback.byRobot) assert.deepEqual(rows.slice(0, 4).map(job =>
  [job.route.pickupSide, job.route.pickupCorner]), cycle);
let maximumWorking = 0;
for (let second = 0; second < 15 * 3600; second += 60) {
  const frame = safeFrameAt(playback, second);
  maximumWorking = Math.max(maximumWorking, frame.robots.filter(robot =>
    ['TO_LOAD', 'LOAD', 'OUTBOUND', 'UNLOAD', 'RETURN'].includes(robot.stage)).length);
}
assert.equal(JSON.stringify({ spec, report }), original);
console.log(JSON.stringify({ artifact_id: artifact.id, saved_created_at: artifact.created_at,
  manifest_members_verified: Object.keys(manifest.members).length, robots: plan.robots.length, racks: plan.furniture.length,
  jobs: playback.jobs.length, jobs_per_robot: jobsPerRobot, maximum_working_at_minute_samples: maximumWorking,
  first_robot_approaches: playback.byRobot[0].slice(0, 4).map(job =>
    [job.route.pickupSide, job.route.pickupCorner]), report_utilization: report.utilization }, null, 2));
