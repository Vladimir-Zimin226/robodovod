import test from 'node:test';
import assert from 'node:assert/strict';
import { buildObjectConstraintContext } from '../src/objectConstraintContext.js';

test('object context preserves metres and explicit outdoor requirement with confirmation', () => {
  const zone = { zoneId:'zone.test', objectConstraints:{values:{min_aisle_width_m:'0.8', outdoor_required:true, ceiling_height_m:''},confirmed:false} };
  const process = {object_kind:'WAREHOUSE',input_revision:'revision.2'};
  assert.throws(() => buildObjectConstraintContext(zone,process), /Подтвердите/);
  zone.objectConstraints.confirmed = true;
  const context = buildObjectConstraintContext(zone,process);
  assert.equal(context.min_aisle_width_m,'0.8');
  assert.equal(context.outdoor_required,true);
  assert.ok(context.requirement_sources.outdoor_required.source_ref.includes('revision.2'));
  assert.equal(context.ceiling_height_m,undefined);
});

test('contradictory load cannot silently differ between selection and calculation', () => {
  assert.throws(() => buildObjectConstraintContext({zoneId:'zone.test',objectConstraints:{values:{max_payload_kg:'10'},confirmed:true}},
    {object_kind:'WAREHOUSE',item_mass:{status:'KNOWN',normalized_value:'20'}}), /массы/);
  const derived = buildObjectConstraintContext({zoneId:'zone.test',objectConstraints:{values:{min_aisle_width_m:'1',temperature_min_c:'-10'},confirmed:true}},
    {object_kind:'WAREHOUSE',input_revision:'revision.2',item_mass:{status:'KNOWN',normalized_value:'20'},explicit_batch:{status:'KNOWN',normalized_value:'2'}});
  assert.equal(derived.max_payload_kg,'40');
  assert.equal(derived.temperature_min_c,'-10');
});

test('facility conditions apply to every zone and zone values override them', () => {
  const facility = { objectConstraints: { values: { temperature_min_c: '-15', floor_flatness_mm_2m: '4', max_slope_percent: '2' }, confirmed: true } };
  const zone = { zoneId: 'zone.1', objectConstraints: { values: { temperature_min_c: '-5' }, confirmed: true } };
  const process = { object_kind: 'WAREHOUSE', process_id: 'process.1', input_revision: 'revision.1' };
  const context = buildObjectConstraintContext(zone, process, facility);
  assert.equal(context.temperature_min_c, '-5');
  assert.equal(context.floor_flatness_mm_2m, '4');
  assert.match(context.requirement_sources.temperature_min_c.source_ref, /zone\.1/);
  assert.match(context.requirement_sources.floor_flatness_mm_2m.source_ref, /facility/);
  assert.throws(() => buildObjectConstraintContext(zone, process, { objectConstraints: { ...facility.objectConstraints, confirmed: false } }), /общие условия/);
});
