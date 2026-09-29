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
  assert.throws(() => buildObjectConstraintContext({zoneId:'zone.test',objectConstraints:{values:{min_aisle_width_m:'1'},confirmed:true}},
    {object_kind:'WAREHOUSE',item_mass:{status:'KNOWN',normalized_value:'20'}}), /Подтвердите требуемую грузоподъёмность/);
});
