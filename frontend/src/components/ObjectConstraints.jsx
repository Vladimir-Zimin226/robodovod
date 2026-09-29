import { OBJECT_CONSTRAINT_FIELDS } from '../objectConstraintContext';

export default function ObjectConstraints({ zone, onChange }) {
  const data = zone.objectConstraints || { values: {}, confirmed: false };
  const edit = (field, value) => onChange({ values: { ...data.values, [field]: value }, confirmed: false });
  return <details className="mt-3" open={data.confirmed ? undefined : true}><summary>Условия пригодности в зоне</summary>
    <p>Пустое поле означает отсутствие заданного требования. Неизвестный паспорт модели требует проверки. Свободная заметка выше сохраняется отдельно.</p>
    <div className="grid gap-2 sm:grid-cols-2">{OBJECT_CONSTRAINT_FIELDS.map(([field, label]) => <label key={field}>{label}<input type="number" min="0" step="any" aria-label={label} value={data.values[field] ?? ''} onChange={event => edit(field, event.target.value)} /></label>)}
      <label>Покрытие пола<input aria-label="Покрытие пола" value={data.values.floor_covering || ''} onChange={event => edit('floor_covering', event.target.value)} /></label>
      <label><input type="checkbox" checked={data.values.outdoor_required === true} onChange={event => edit('outdoor_required', event.target.checked)} /> На маршруте требуется работа на улице</label>
    </div><label><input type="checkbox" checked={data.confirmed} onChange={event => onChange({ ...data, confirmed: event.target.checked })} /> Подтверждаю значения требований этой зоны</label>
  </details>;
}
