import { readFileSync } from 'node:fs';

// Synthetic identities; published regression fixture is read, never rewritten.
export function facilityCase(template = 'airport') {
  const request = JSON.parse(readFileSync(new URL('../../../contracts/fixtures/simulation-request-v1.capacity-only.golden.json', import.meta.url)));
  const report = JSON.parse(readFileSync(new URL('../../../contracts/fixtures/simulation-report-v2.capacity-only.golden.json', import.meta.url)));
  const spec = request.scenario_spec, fleet = spec.fleet[0], task = spec.tasks[0];
  if (template === 'hospital') {
    spec.template = 'hospital';
    Object.assign(spec.profile, { calculation_profile: 'DELIVERY_CYCLE_V1', process_code: 'clinic_food', process_scope: 'DELIVERY_CYCLE', quantity_kind: 'PORTION' });
    fleet.selected_fleet = fleet.recommended_fleet = 1;
    Object.assign(fleet.nominal_capacity, { value: '433.3333333333333333333333334', unit: 'unit/h' });
    Object.assign(fleet.effective_capacity, { value: '303.3333333333333333333333334', unit: 'unit/h' });
    Object.assign(task.batch, { semantics: 'PHYSICAL_BATCH' });
    Object.assign(task.batch.units_per_cycle, { value: '65', unit: 'unit/cycle', quantity_kind: 'COUNT' });
    Object.assign(task.demand, { value: '1950', unit: 'portion/day' });
    task.exchange = { mode: 'TOTAL', total_time: { value: '180', unit: 's', quantity_kind: 'TIME', numeric_encoding: 'DECIMAL_STRING' }, load_time: null, unload_time: null };
    task.route_ref = 'route.food';
    spec.routes = [{ route_id: 'route.food', one_way_distance: { value: '180', unit: 'm', quantity_kind: 'DISTANCE', numeric_encoding: 'DECIMAL_STRING' }, geometry_source: 'SYNTHETIC', geometry_ref: null, assumption_ref: 'assumption.synthetic-geometry' }];
    Object.assign(report.workload, { batch_units: '65', daily_units: '1950', simulated_units_per_day: '1950', jobs_per_day: 30, fleet_units: 1, quantity_unit: 'portion/day' });
    report.trace.find(node => node.output_ref === 'service.effective-seconds').value = '771.4285714285714285714285714';
  }
  return { request, spec, report };
}
