import test from 'node:test';
import assert from 'node:assert/strict';
import { dxfToFacilityLayout, parseAsciiDxf } from '../src/dxfLayout.js';
import { estimateFacilityRoute } from '../src/facilityLayout.js';

const dxf = (parts) => ['0', 'SECTION', '2', 'HEADER', '9', '$INSUNITS', '70', '6', '0', 'ENDSEC',
  '0', 'SECTION', '2', 'ENTITIES', ...parts, '0', 'ENDSEC', '0', 'EOF'].join('\n');
const line = (layer, x1, y1, x2, y2) => ['0', 'LINE', '8', layer, '10', x1, '20', y1, '11', x2, '21', y2].map(String);

test('ASCII DXF imports selected orthogonal layers with explicit units and origin', () => {
  const parsed = parseAsciiDxf(dxf([
    ...line('WALL', 0, 0, 60, 0), ...line('WALL', 30, 0, 30, 36),
    ...line('ANNOTATION', 0, 36, 60, 36),
  ]));
  assert.equal(parsed.unit, 'meter');
  assert.deepEqual(parsed.layers, ['ANNOTATION', 'WALL']);
  assert.throws(() => dxfToFacilityLayout(parsed, { layers: ['WALL'] }), /единицы/);
  const layout = dxfToFacilityLayout(parsed, { unit: 'meter', layers: ['WALL'], sourceName: 'test.dxf' });
  assert.equal(layout.items.length, 2);
  assert.equal(layout.items[0].provenance, 'PROVIDED');
  assert.equal(layout.cad_metadata.selected_layers[0], 'WALL');
  assert.equal(estimateFacilityRoute(layout).status, 'NEEDS_ENDPOINTS');
});

test('diagonal lines and unsupported entities are counted instead of silently treated as walls', () => {
  const parsed = parseAsciiDxf(dxf([...line('WALL', 0, 0, 50, 0),
    ...line('WALL', 0, 0, 50, 30), '0', 'CIRCLE', '8', 'WALL', '10', '10', '20', '10', '40', '2']));
  const layout = dxfToFacilityLayout(parsed, { unit: 'meter', layers: ['WALL'] });
  assert.equal(layout.cad_metadata.skipped_diagonal_segments, 1);
  assert.equal(layout.cad_metadata.unsupported_entities, 1);
  assert.equal(layout.items.length, 1);
});
