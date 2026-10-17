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
  const [layerKinds, setLayerKinds] = useState({});
  const [thickness, setThickness] = useState(.2);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState('');
  const preview = useMemo(() => {
    if (!parsed || !unit || !layers.length) return null;
    try { return { layout: dxfToFacilityLayout(parsed, { unit, layers, layerKinds, wallThicknessM: thickness, sourceName: fileName }) }; }
    catch (failure) { return { error: failure.message }; }
  }, [parsed, unit, layers, layerKinds, thickness, fileName]);
  const readFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setParsed(null); setLayers([]); setLayerKinds({}); setConfirmed(false); setError(''); setFileName(file.name);
    if (!file.name.toLowerCase().endsWith('.dxf') || file.size > 5 * 1024 * 1024) {
      setError('Выберите текстовый DXF до 5 МБ. DWG сначала экспортируйте из AutoCAD в DXF.'); return;
    }
    try {
      const content = await file.text();
      const next = parseAsciiDxf(content);
      setParsed(next); setUnit(next.unit || '');
      setLayerKinds(Object.fromEntries(next.layers.map((layer) => [layer, /rack|стеллаж/i.test(layer) ? 'rack' : 'obstacle'])));
    } catch (failure) { setError(failure.message); }
  };
  const loadSample = async () => {
    setError(''); setConfirmed(false);
    try {
      const response = await fetch('/examples/warehouse-training-plan.dxf');
      if (!response.ok) throw new Error('Учебный DXF недоступен. Обновите страницу и повторите попытку.');
      const next = parseAsciiDxf(await response.text());
      setParsed(next); setFileName('warehouse-training-plan.dxf'); setUnit(next.unit || 'meter');
      setLayers(next.layers.filter((layer) => ['WALLS', 'RACKS'].includes(layer)));
      setLayerKinds({ WALLS: 'obstacle', RACKS: 'rack' });
    } catch (failure) { setError(failure.message); }
  };
  const toggle = (layer) => { setConfirmed(false); setLayers((current) => current.includes(layer)
    ? current.filter((item) => item !== layer) : [...current, layer]); };
  return <details className="warehouse-dxf-importer"><summary>Импорт контура из AutoCAD DXF</summary>
    <p>В AutoCAD сохраните DWG как текстовый DXF. Поддержаны прямые LINE и LWPOLYLINE. Для каждого слоя выберите стены либо осевые линии стеллажей; диагонали и другие объекты не превращаются в препятствия автоматически.</p>
    <div className="warehouse-dxf-sample"><button type="button" onClick={loadSample}>Попробовать учебный DXF</button><a href="/examples/warehouse-training-plan.dxf" download="warehouse-training-plan.dxf">Скачать файл для проверки</a><small>Придуманный склад 72 × 48 м, метры; слои WALLS и RACKS. Не является планом реального объекта.</small></div>
    <label>Файл .dxf<input type="file" accept=".dxf" onChange={readFile} /></label>
    {error && <p role="alert" className="warehouse-dxf-error">{error}</p>}
    {parsed && <div className="warehouse-dxf-options">
      <p>Найдено {parsed.segments.length} отрезков на {parsed.layers.length} слоях. Единицы в файле: {UNITS.find(([key]) => key === parsed.unit)?.[1] || 'не указаны'}. Неподдержанных объектов: {parsed.unsupported_entities}; повреждённых: {parsed.malformed_entities}.</p>
      <label>Подтвердите единицы<select value={unit} onChange={(event) => { setUnit(event.target.value); setConfirmed(false); }}><option value="">Не выбраны</option>{UNITS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <fieldset><legend>Слои плана и их смысл</legend>{parsed.layers.map((layer) =>
        <div className="warehouse-dxf-layer" key={layer}><label><input type="checkbox" checked={layers.includes(layer)} onChange={() => toggle(layer)} />{layer} · {parsed.segments.filter((segment) => segment.layer === layer).length} отрезков</label>
          {layers.includes(layer) && <select aria-label={`Тип слоя ${layer}`} value={layerKinds[layer] || 'obstacle'} onChange={(event) => { setLayerKinds((current) => ({ ...current, [layer]: event.target.value })); setConfirmed(false); }}>
            <option value="obstacle">Стены и препятствия</option><option value="rack">Осевые линии стеллажей · ширина 1,2 м</option>
          </select>}</div>)}</fieldset>
      <label>Толщина линий препятствий, м<input type="number" min="0.05" max="2" step="0.05" value={thickness} onChange={(event) => { setThickness(Number(event.target.value) || .2); setConfirmed(false); }} /></label>
      {preview?.error && <p role="alert" className="warehouse-dxf-error">{preview.error}</p>}
      {preview?.layout && <div className="warehouse-dxf-preview"><strong>Предпросмотр: {preview.layout.width_m} × {preview.layout.depth_m} м · {preview.layout.items.length} объектов ({preview.layout.items.filter((item) => item.kind === 'rack').length} стеллажей).</strong>
        <span>Пропущено диагоналей: {preview.layout.cad_metadata.skipped_diagonal_segments}; других объектов: {preview.layout.cad_metadata.unsupported_entities}; повреждённых: {preview.layout.cad_metadata.malformed_entities}. Подтверждайте только после проверки этого списка и масштаба.</span>
        <label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />Я проверил единицы, типы слоёв и пропущенные элементы</label>
        <button type="button" disabled={!confirmed} onClick={() => { onResult(preview.layout); setConfirmed(false); }}>Использовать контуры на плане</button>
      </div>}
    </div>}
  </details>;
}
