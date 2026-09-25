export const CAPACITY_RESPONSE_SCHEMA = 'capacity-analysis-response-v2';

const STATUS_LABELS = Object.freeze({
  COMPLETE: 'Расчёт выполнен',
  WITH_ASSUMPTIONS: 'Выполнен с допущениями',
  BLOCKED: 'Расчёт заблокирован',
  NOT_APPLICABLE: 'Расчёт неприменим',
});

const PROVENANCE_LABELS = Object.freeze({
  USER: 'Ввод пользователя',
  FILE: 'Файл проекта',
  PRESET: 'Набор исходных данных',
  VENDOR_FACT: 'Факт производителя',
  ASSUMPTION: 'Явное допущение',
  POLICY: 'Правило расчёта',
  DERIVED: 'Производное значение',
});

function contractError(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

export function isCapacityAnalysisResponse(value) {
  return value?.schema_version === CAPACITY_RESPONSE_SCHEMA;
}

export function assertCapacityResponse(response, expectedRevision = null) {
  if (!isCapacityAnalysisResponse(response)) throw contractError('UNKNOWN_CAPACITY_RESPONSE_SCHEMA');
  const trace = response.trace;
  if (!trace || response.run_id !== trace.envelope?.run_id) throw contractError('CAPACITY_RUN_ID_MISMATCH');
  if (response.input_revision !== trace.envelope?.input_revision) throw contractError('CAPACITY_REVISION_MISMATCH');
  if (response.capacity?.process_id !== trace.envelope?.process_id) throw contractError('CAPACITY_PROCESS_MISMATCH');
  if (expectedRevision && response.input_revision !== expectedRevision) throw contractError('STALE_CAPACITY_RESPONSE');
  return response;
}

import { formatDecimal, formatPercent } from './displayNumber.js';

const UNIT_LABELS = { 'unit/h': 'ед./ч', 'pallet/h': 'паллет/ч', 'unit/day': 'ед./день',
  'pallet/day': 'паллет/день', robot: 'роботов', '1': '' };

export function formatServerQuantity(quantity) {
  if (!quantity || quantity.value == null || !quantity.unit) return '—';
  if (quantity.quantity_kind === 'FRACTION') return formatPercent(quantity.value);
  const value = formatDecimal(quantity.value, quantity.quantity_kind === 'COUNT' || quantity.unit === 'robot' ? 0 : 2);
  if (value == null) return '—';
  const unit = UNIT_LABELS[quantity.unit] ?? quantity.unit;
  return unit ? `${value} ${unit}` : value;
}

function provenanceLabel(item) {
  if (!item) return 'Источник не указан';
  const base = PROVENANCE_LABELS[item.kind] || item.kind;
  const evidence = item.evidence_ids?.length ? ` · ${item.evidence_ids.join(', ')}` : '';
  return `${base}${evidence}`;
}

function traceSteps(trace) {
  const inputs = new Map((trace.inputs || []).map((item) => [item.name, item]));
  const provenance = new Map((trace.provenance || []).map((item) => [item.provenance_id, item]));
  const valuesByNode = new Map();
  for (const item of trace.intermediates || []) {
    const list = valuesByNode.get(item.node_id) || [];
    list.push({ name: item.name, value: item.value });
    valuesByNode.set(item.node_id, list);
  }
  return (trace.formula_nodes || []).map((node) => ({
    id: node.node_id,
    formulaId: node.formula_id,
    version: node.formula_version,
    title: node.template_id,
    sourceRefs: node.source_refs || [],
    inputs: (node.input_refs || []).map((name) => {
      const input = inputs.get(name);
      return {
        name,
        value: input?.status === 'KNOWN' ? formatServerQuantity({ value: input.normalized_value, unit: input.unit, quantity_kind: input.quantity_kind }) : 'Нет значения',
        source: provenanceLabel(provenance.get(input?.provenance_ref)),
      };
    }),
    outputs: valuesByNode.get(node.node_id) || [],
  }));
}

export function getCapacityResultsModel(response, expectedRevision = null) {
  assertCapacityResponse(response, expectedRevision);
  const { capacity, trace } = response;
  const value = capacity.value;
  return {
    schemaVersion: response.schema_version,
    runId: response.run_id,
    revision: response.input_revision,
    processId: capacity.process_id,
    modelId: trace.envelope.model_id,
    positionId: trace.envelope.position_id,
    status: capacity.status,
    statusLabel: STATUS_LABELS[capacity.status] || capacity.status,
    hasCapacity: Boolean(value),
    recommendedFleet: value?.recommended_fleet ?? null,
    selectedFleet: value?.selected_fleet ?? null,
    fleetMode: value && value.selected_fleet !== value.recommended_fleet ? 'MANUAL' : 'RECOMMENDED',
    nominalCapacity: value?.nominal_capacity || null,
    effectiveCapacity: value?.effective_capacity || null,
    coverage: value?.coverage || null,
    rawLoadRatio: value?.raw_load_ratio || null,
    utilization: value?.utilization || null,
    overloaded: value?.overloaded ?? null,
    blockers: capacity.blockers || [],
    warnings: capacity.warnings || [],
    steps: traceSteps(trace),
    assumptions: trace.assumptions || [],
    constraints: trace.constraints || [],
    versions: trace.versions,
    economics: null,
    economicsLabel: 'Экономика не рассчитана для этого capacity snapshot',
    participationLabel: 'Участвует в расчёте',
    participationHint: 'Это не означает готовность к внедрению, SLA или deployment-ready.',
  };
}
