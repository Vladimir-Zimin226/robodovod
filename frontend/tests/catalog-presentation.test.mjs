import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  catalogItemKey,
  catalogMedia,
  formatCatalogPrice,
  matchesCatalogQuery,
  normalizeOfficialModel,
} from '../src/catalogPresentation.js';

const officialPosition = {
  id: 'model-shared',
  position_id: 'position-223',
  name: 'Робот-погрузчик',
  manufacturer: 'Завод Роботов',
  system_family: 'BRS',
  type_code: 'WAREHOUSE',
  source_record_key: 'catalog-row-223',
  industries: ['Складская логистика'],
  use_cases: ['Перемещение паллет'],
  regions: ['Россия'],
  facts: [{ code: 'payload_kg', value: 1200, unit: 'кг' }],
  purchase: { amount: 5_500_000, evidence_id: 'evidence-1' },
  media: { url: '/api/catalog/media/asset-1', width_px: 800, height_px: 600, media_type: 'image/png' },
};

test('catalog position identity does not collapse duplicate canonical models', () => {
  assert.equal(catalogItemKey(officialPosition), 'position-223');
  assert.notEqual(catalogItemKey(officialPosition), officialPosition.id);
});

test('official item normalization preserves position, evidence and facts', () => {
  const normalized = normalizeOfficialModel(officialPosition);
  assert.equal(normalized.catalog_key, 'position-223');
  assert.equal(normalized.category, 'BRS');
  assert.equal(normalized.specs.payload_kg, 1200);
  assert.equal(normalized.price.basis, 'official_catalog');
});

test('search covers manufacturer, industry, use case and source identity', () => {
  const normalized = normalizeOfficialModel(officialPosition);
  assert.equal(matchesCatalogQuery(normalized, 'завод'), true);
  assert.equal(matchesCatalogQuery(normalized, 'паллет'), true);
  assert.equal(matchesCatalogQuery(normalized, 'row-223'), true);
  assert.equal(matchesCatalogQuery(normalized, 'медицина'), false);
});

test('media metadata and official prices are presentation-only projections', () => {
  const normalized = normalizeOfficialModel(officialPosition);
  assert.deepEqual(catalogMedia(normalized), {
    src: '/api/catalog/media/asset-1',
    width: 800,
    height: 600,
    type: 'image/png',
  });
  assert.equal(formatCatalogPrice(normalized), '5,5 млн ₽');
  assert.equal(catalogMedia({}), null);
  assert.equal(formatCatalogPrice({ price: { basis: 'quote_required' } }), 'По запросу');
});

test('catalog component keeps media and interactive controls accessible', async () => {
  const source = await readFile(new URL('../src/components/CatalogScreen.jsx', import.meta.url), 'utf8');
  assert.match(source, /loading="lazy"/);
  assert.match(source, /aria-pressed=\{selected\}/);
  assert.match(source, /aria-label="Фильтры каталога"/);
  assert.match(source, /aria-modal="true"/);
  assert.match(source, /event\.key === 'Escape'/);
  assert.match(source, /closeButton\.current\?\.focus\(\)/);
});
