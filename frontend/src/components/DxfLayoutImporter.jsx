import { useMemo, useState } from 'react';
import { dxfToFacilityLayout, parseAsciiDxf } from '../dxfLayout';

const UNITS = [
  ['millimeter', 'Миллиметры'], ['centimeter', 'Сантиметры'], ['meter', 'Метры'],
  ['inch', 'Дюймы'], ['foot', 'Футы'],
];

export default function DxfLayoutImporter({ onResult }) {
  const [parsed, setParsed] = useState(null);
  const [fileName, setFileName] = useState('');
  const [unit, setUnit] = useState('');
  const [layers, setLayers] = useState([]);
  const [thickness, setThickness] = useState(.2);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState('');
  const preview = useMemo(() => {
    if (!parsed || !unit || !layers.length) return null;
    try { return { layout: dxfToFacilityLayout(parsed, { unit, layers, wallThicknessM: thickness, sourceName: fileName }) }; }
    catch (failure) { return { error: failure.message }; }
  }, [parsed, unit, layers, thickness, fileName]);
  const readFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setParsed(null); setLayers([]); setConfirmed(false); setError(''); setFileName(file.name);
    if (!file.name.toLowerCase().endsWith('.dxf') || file.size > 5 * 1024 * 1024) {
      setError('Выберите текстовый DXF до 5 МБ. DWG сначала экспортируйте из AutoCAD в DXF.'); return;
    }
    try {
      const content = await file.text();
      const next = parseAsciiDxf(content);
      setParsed(next); setUnit(next.unit || '');
    } catch (failure) { setError(failure.message); }
  };
  const toggle = (layer) => { setConfirmed(false); setLayers((current) => current.includes(layer)
    ? current.filter((item) => item !== layer) : [...current, layer]); };
  return <details className="warehouse-dxf-importer"><summary>Импорт контура из AutoCAD DXF</summary>
    <p>Поддержаны текстовые DXF с прямыми LINE и LWPOLYLINE. Выберите только слои стен и крупных препятствий. Диагональные элементы и другие типы объектов не превращаются в препятствия автоматически.</p>
    <label>Файл .dxf<input type="file" accept=".dxf" onChange={readFile} /></label>
    {error && <p role="alert" className="warehouse-dxf-error">{error}</p>}
    {parsed && <div className="warehouse-dxf-options">
      <p>Найдено {parsed.segments.length} отрезков на {parsed.layers.length} слоях. Единицы в файле: {UNITS.find(([key]) => key === parsed.unit)?.[1] || 'не указаны'}. Неподдержанных объектов: {parsed.unsupported_entities}; повреждённых: {parsed.malformed_entities}.</p>
      <label>Подтвердите единицы<select value={unit} onChange={(event) => { setUnit(event.target.value); setConfirmed(false); }}><option value="">Не выбраны</option>{UNITS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <fieldset><legend>Слои с препятствиями</legend>{parsed.layers.map((layer) =>
        <label key={layer}><input type="checkbox" checked={layers.includes(layer)} onChange={() => toggle(layer)} />{layer} · {parsed.segments.filter((segment) => segment.layer === layer).length} отрезков</label>)}</fieldset>
      <label>Толщина линий препятствий, м<input type="number" min="0.05" max="2" step="0.05" value={thickness} onChange={(event) => { setThickness(Number(event.target.value) || .2); setConfirmed(false); }} /></label>
      {preview?.error && <p role="alert" className="warehouse-dxf-error">{preview.error}</p>}
      {preview?.layout && <div className="warehouse-dxf-preview"><strong>Предпросмотр: {preview.layout.width_m} × {preview.layout.depth_m} м · {preview.layout.items.length} препятствий.</strong>
        <span>Пропущено диагоналей: {preview.layout.cad_metadata.skipped_diagonal_segments}; других объектов: {preview.layout.cad_metadata.unsupported_entities}; повреждённых: {preview.layout.cad_metadata.malformed_entities}. Подтверждайте только после проверки этого списка и масштаба.</span>
        <label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />Я проверил единицы, выбранные слои и пропущенные элементы</label>
        <button type="button" disabled={!confirmed} onClick={() => { onResult(preview.layout); setConfirmed(false); }}>Использовать контуры на плане</button>
      </div>}
    </div>}
  </details>;
}
