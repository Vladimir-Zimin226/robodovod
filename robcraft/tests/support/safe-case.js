import { facilityCase } from './facility-case.js';
export function playbackCase(template, count) {
  const bundle = facilityCase(template === 'hospital' ? 'hospital' : 'airport');
  const {spec, report} = bundle;
  spec.template = template;
  if (template === 'warehouse' || template === 'baggage') {
    spec.template = template === 'baggage' ? 'airport' : 'warehouse';
    spec.profile.calculation_profile = 'TRANSPORT_CYCLE_V1';
    spec.profile.process_code = template === 'baggage' ? 'airport_baggage' : 'warehouse_receiving_shipping';
    spec.tasks[0].exchange = {mode:'TOTAL',total_time:{value:'40',unit:'s',quantity_kind:'TIME',numeric_encoding:'DECIMAL_STRING'},load_time:null,unload_time:null};
    spec.fleet[0].nominal_capacity.value = '100'; spec.fleet[0].effective_capacity.value = '70';
    report.trace.find(x=>x.output_ref==='service.effective-seconds').value='300';
    Object.assign(report.workload,{batch_units:'1',simulated_units_per_day:'2000',jobs_per_day:2000});
  }
  spec.fleet[0].selected_fleet = count; report.workload.fleet_units=count;
  return bundle;
}
