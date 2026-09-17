import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  catalogDetailView,
  catalogItemKey,
  catalogMedia,
  formatCatalogFact,
  formatCatalogPrice,
  matchesCatalogQuery,
  normalizeOfficialModel,
  runtimeBlockerLabel,
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
  applicability: [{ industry: 'Складская логистика', scenario: 'Перемещение паллет', region: 'Россия', case: 'Внедрено 10 роботов.' }],
  enrichment: {
    fields: { trl: 8, lifecycle_stage: 'Эксплуатация', market_potential: 4, service_labels: ['Есть в каталоге'], source_url: 'https://example.test/source' },
    provenance: { source_page: 6, source_slot: 1, limitation: 'external transcription' },
  },
  runtime_blockers: ['runtime_projection'],
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

test('detail view preserves row-specific text and presentation-only enrichment', () => {
  const detail = catalogDetailView(officialPosition);
  assert.equal(detail.description, 'Описание модели в исходном каталоге не указано.');
  assert.equal(detail.caseText, 'Внедрено 10 роботов.');
  assert.equal(detail.trl, '8/9');
  assert.equal(detail.lifecycleStage, 'Эксплуатация');
  assert.equal(detail.marketPotential, '4/5');
  assert.equal(detail.sourceLocation, 'страница 6, слот 1');
  assert.deepEqual(detail.serviceLabels, ['Есть в каталоге']);
  assert.deepEqual(detail.runtimeBlockers, ['runtime_projection']);
});

test('detail presentation does not invent absent values', () => {
  const detail = catalogDetailView({ name: 'Без данных' });
  assert.equal(detail.trl, null);
  assert.equal(detail.marketPotential, null);
  assert.equal(detail.sourceUrl, null);
  assert.equal(detail.caseText, null);
  assert.deepEqual(detail.facts, []);
  assert.equal(formatCatalogFact({ value: 1200, unit: 'кг' }), '1200 кг');
  assert.equal(runtimeBlockerLabel('runtime_projection'), 'Нет утверждённой runtime-проекции');
});

test('catalog component keeps media and interactive controls accessible', async () => {
  const source = await readFile(new URL('../src/components/CatalogScreen.jsx', import.meta.url), 'utf8');
  assert.match(source, /loading="lazy"/);
  assert.match(source, /aria-pressed=\{selected\}/);
  assert.match(source, /aria-label="Фильтры каталога"/);
  assert.match(source, /aria-modal="true"/);
  assert.match(source, /event\.key === 'Escape'/);
  assert.match(source, /closeButton\.current\?\.focus\(\)/);
  assert.match(source, /CatalogPositionDialog/);
  assert.match(source, /aria-label=\{`Подробнее о позиции/);
});

test('position dialog fetches the position endpoint and traps keyboard focus', async () => {
  const source = await readFile(new URL('../src/components/CatalogPositionDialog.jsx', import.meta.url), 'utf8');
  assert.match(source, /\/api\/catalog\/positions\//);
  assert.match(source, /event\.key === 'Escape'/);
  assert.match(source, /event\.key !== 'Tab'/);
  assert.match(source, /runtimeBlockers/);
  assert.match(source, /transcript_sha256/);
  assert.match(source, /aria-modal="true"/);
});
