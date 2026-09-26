import { useEffect, useMemo, useRef, useState } from 'react';
import { catalogItemKey, catalogMedia, formatCatalogPrice, normalizeOfficialModel } from '../catalogPresentation';
import CatalogPositionDialog from './CatalogPositionDialog';

const API = import.meta.env.VITE_API_URL || '';
const INITIAL_ITEMS_PER_FAMILY = 12;
const MAX_COMPARE = 3;

const FAMILY_META = {
  BRS: { label: 'Наземные робототехнические системы', short: 'БРС', accent: 'lime' },
  BAS: { label: 'Беспилотные авиационные системы', short: 'БАС', accent: 'cyan' },
  SOFTWARE: { label: 'Программные решения', short: 'ПО', accent: 'violet' },
};
function familyMeta(key, index = 0) {
  if (FAMILY_META[key]) return FAMILY_META[key];
  return { label: key || 'Другие решения', short: 'РТК', accent: ['lime', 'cyan', 'violet'][index % 3] };
}

function readResponse(response) {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export default function CatalogScreen({ objectType, onContinue, onBack, focusPositionId, projectContext }) {
  const [robots, setRobots] = useState([]);
  const [objectFilter, setObjectFilter] = useState(({ retail: 'warehouse', airport: 'airport', clinic: 'clinic' })[objectType] || '');
  const [processFilter, setProcessFilter] = useState(projectContext?.process_code || '');
  const [maturity, setMaturity] = useState('');
  const [quality, setQuality] = useState('');
  const [availability, setAvailability] = useState('');
  const [includeUnknown, setIncludeUnknown] = useState(false);
  const [bounds, setBounds] = useState(projectContext?.constraints || {});
  const [selectedItems, setSelectedItems] = useState({});
  const [options, setOptions] = useState({});
  const [catalog, setCatalog] = useState(null);
  const [hierarchy, setHierarchy] = useState([]);
  const [status, setStatus] = useState('loading');
  const [loadedSignature, setLoadedSignature] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [family, setFamily] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [manufacturer, setManufacturer] = useState('');
  const [calculationParticipation, setCalculationParticipation] = useState('all');
  const [sort, setSort] = useState('name');
  const [selected, setSelected] = useState([]);
  const [expandedFamilies, setExpandedFamilies] = useState([]);
  const [showCompare, setShowCompare] = useState(false);
  const [detailPosition, setDetailPosition] = useState(null);
  const signature = JSON.stringify({ query, family, typeFilter, manufacturer, calculationParticipation, sort,
    objectFilter, processFilter, maturity, quality, availability, includeUnknown, bounds });

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ q: query, system_family: family, type_code: typeFilter,
      manufacturer, calculation_participation: calculationParticipation, sort, include_unknown: String(includeUnknown) });
    for (const [key, value] of Object.entries({ object_kind: objectFilter, process_code: processFilter,
      maturity, quality, availability, ...bounds })) if (value !== '' && value != null) params.set(key, value);
    fetch(`${API}/api/catalog/models?${params}`, { signal: controller.signal })
      .then(readResponse)
      .then((payload) => {
        setCatalog({
          ...payload.catalog,
          model_count: payload.model_count,
          position_count: payload.position_count,
          calculation_ready_model_count: payload.calculation_ready_model_count,
          calculation_ready_position_count: payload.calculation_ready_position_count,
        });
        setHierarchy(payload.hierarchy || []);
        setOptions({ manufacturers: payload.manufacturers || [], maturities: payload.maturities || [], availabilities: payload.availabilities || [], processes: payload.processes || [] });
        setRobots((payload.items || []).map(normalizeOfficialModel));
        if (focusPositionId) {
          const found = (payload.items || []).find((item) => item.id === focusPositionId);
          if (found) setDetailPosition(normalizeOfficialModel(found));
        }
        setLoadedSignature(signature);
        setStatus('ready');
      })
      .catch((catalogError) => {
        if (catalogError.name === 'AbortError') return;
        setError('Каталог недоступен или границы фильтра некорректны. Проверьте диапазоны и соединение.');
        setLoadedSignature(signature);
        setStatus('error');
      });
    return () => controller.abort();
  }, [focusPositionId, signature, query, family, typeFilter, manufacturer, calculationParticipation, sort,
    objectFilter, processFilter, maturity, quality, availability, includeUnknown, bounds]);

  const visible = loadedSignature === signature ? robots : [];
  const viewStatus = loadedSignature === signature ? status : 'loading';

  const categories = useMemo(
    () => hierarchy.map((item, index) => ({ key: item.system_family, ...familyMeta(item.system_family, index) })),
    [hierarchy],
  );
  const types = family ? hierarchy.find((item) => item.system_family === family)?.types || [] : hierarchy.flatMap((item) => item.types || []);
  const manufacturers = options.manufacturers || [];
  const selectedRobots = selected.map((key) => selectedItems[key] || robots.find((robot) => catalogItemKey(robot) === key)).filter(Boolean);
  const toggle = (robot) => { const key = catalogItemKey(robot); setSelectedItems((old) => ({ ...old, [key]: robot })); setSelected((current) => current.includes(key) ? current.filter((item) => item !== key) : current.length < MAX_COMPARE ? [...current, key] : current); };
  const resetFilters = () => { setQuery(''); setFamily(''); setTypeFilter(''); setManufacturer(''); setCalculationParticipation('all'); setSort('name'); setObjectFilter(''); setProcessFilter(''); setMaturity(''); setQuality(''); setAvailability(''); setIncludeUnknown(false); setBounds({}); };
  const objectLabel = ({ warehouse: 'Склад', airport: 'Аэропорт', clinic: 'Клиника' })[objectFilter] || 'Все объекты';

  return (
    <main className="catalog-screen" aria-labelledby="catalog-title">
      <div className="catalog-shell">
        <header className="catalog-heading">
          <div><span className="catalog-eyebrow">БИБЛИОТЕКА РЕШЕНИЙ</span><h1 id="catalog-title">Доступные решения</h1><p>{viewStatus === 'ready' ? `${visible.length} позиций` : 'Загружаем позиции'} · объект: <strong>{objectLabel}</strong></p></div>
          {catalog && <div className="catalog-version" aria-label={`Версия каталога ${catalog.code}`}><span className="catalog-live-dot" aria-hidden="true" /><div><small>АКТИВНЫЙ КАТАЛОГ</small><strong>{catalog.code}</strong></div></div>}
        </header>
        {catalog && <p className="catalog-notice">Полный discovery-каталог: <strong>{catalog.model_count} моделей</strong> / <strong>{catalog.position_count} позиций</strong>. Участвуют в предварительном capacity-расчёте: <strong>{catalog.calculation_ready_model_count} модель</strong> / <strong>{catalog.calculation_ready_position_count} позиции</strong>. Это не означает готовность к внедрению или закупке.</p>}

        <p className="catalog-notice">Подборка учитывает объект и процесс. Отрасль — поисковая подсказка; закупочная рекомендация требует обследования. Склад поддерживает полный расчёт; аэропорт и клиника — паспорт объекта и поддержанные процессы.</p>
        <section className="catalog-filters" aria-label="Фильтры каталога">
          <label>Объект<select aria-label="Объект подбора" value={objectFilter} onChange={(e) => { setObjectFilter(e.target.value); setProcessFilter(''); }}><option value="">Все объекты</option><option value="warehouse">Склад</option><option value="airport">Аэропорт</option><option value="clinic">Клиника</option></select></label>
          <label>Процесс<select aria-label="Процесс подбора" value={processFilter} onChange={(e) => setProcessFilter(e.target.value)}><option value="">Все процессы</option>{(options.processes || []).filter((p) => p.object_kind === objectFilter).map((p) => <option key={p.code} value={p.code}>{p.code} · {p.calculation_supported ? 'формула' : 'справочно'}</option>)}</select></label>
          <button type="button" onClick={resetFilters}>Сбросить фильтры · весь каталог</button>
          <label className="catalog-search"><span className="sr-only">Поиск по каталогу</span><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, производитель, отрасль или сценарий" type="search" /></label>
          <label><span className="sr-only">Семейство систем</span><select value={family} onChange={(event) => { setFamily(event.target.value); setTypeFilter(''); }}><option value="">Все семейства</option>{hierarchy.map((item) => <option key={item.system_family} value={item.system_family}>{familyMeta(item.system_family).label}</option>)}</select></label>
          <label><span className="sr-only">Тип решения</span><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">Все типы</option><option value="__unknown">Тип не указан</option>{Array.from(new Map(types.map((item) => [item.type_code, item])).values()).map((item) => <option key={item.type_code} value={item.type_code}>{item.type_code} ({item.count})</option>)}</select></label>
          <label><span className="sr-only">Производитель</span><select value={manufacturer} onChange={(event) => setManufacturer(event.target.value)}><option value="">Все производители</option><option value="__unknown">Производитель не указан</option>{manufacturers.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <label><span className="sr-only">Участие в расчёте</span><select aria-label="Участие в расчёте" value={calculationParticipation} onChange={(event) => setCalculationParticipation(event.target.value)}><option value="all">Все</option><option value="participating">Участвуют</option><option value="requires_data">Требуют данных</option></select></label>
          <label><span className="sr-only">Сортировка</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="name">По названию</option><option value="manufacturer">По производителю</option><option value="type">По типу</option></select></label>
          <details className="catalog-advanced"><summary>Дополнительные фильтры и ограничения</summary><div className="catalog-advanced-grid">
          <label>Зрелость<select value={maturity} onChange={(e) => setMaturity(e.target.value)}><option value="">Все стадии</option><option value="__unknown">Неизвестна</option>{(options.maturities || []).map((v) => <option key={v}>{v}</option>)}</select></label>
          <label>Доступность<select value={availability} onChange={(e) => setAvailability(e.target.value)}><option value="">Любая</option><option value="unknown">Неизвестна</option>{(options.availabilities || []).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Качество ТТХ<select value={quality} onChange={(e) => setQuality(e.target.value)}><option value="">Любое</option><option value="verified">Есть проверенные числовые ТТХ</option><option value="unknown">ТТХ требуют проверки</option></select></label>
          {[["price_min", "Цена от, ₽"], ["price_max", "Цена до, ₽"], ["payload_min", "Грузоподъёмность от, кг"], ["payload_max", "Грузоподъёмность до, кг"], ["aisle_max", "Проход робота до, м"], ["max_payload_kg", "Масса груза объекта, кг"], ["min_aisle_width_m", "Проход объекта, м"], ["required_integrations", "Интеграции, через запятую"], ["required_access_protocols", "Протоколы доступа, через запятую"]].map(([key, label]) => <label key={key}>{label}<input aria-label={label} type={key.startsWith('required_') ? 'text' : 'number'} min="0" step="any" value={bounds[key] || ''} onChange={(e) => setBounds((old) => ({ ...old, [key]: e.target.value }))} /></label>)}
          {[["outdoor_required", "Работа вне помещения"], ["airside_required", "Аэродромная зона"], ["restricted_zone_required", "Ограниченная зона"], ["sanitization_required", "Санитарная обработка"]].map(([key, label]) => <label key={key}><input type="checkbox" checked={Boolean(bounds[key])} onChange={(e) => setBounds((old) => ({ ...old, [key]: e.target.checked }))} /> {label}</label>)}
          <label><input type="checkbox" checked={includeUnknown} onChange={(e) => setIncludeUnknown(e.target.checked)} /> Включить неизвестные данные (требуют проверки)</label>
          </div></details>
        </section>

        {viewStatus === 'loading' && <CatalogSkeleton />}
        {viewStatus === 'error' && <CatalogEmpty title="Не удалось загрузить каталог" text={error} />}
        {viewStatus === 'ready' && visible.length === 0 && <CatalogEmpty title="Ничего не найдено" text="Измените объект, процесс или диапазон. Неизвестные значения можно включить отдельно; сброс возвращает весь каталог." action={resetFilters} />}

        {viewStatus === 'ready' && categories.map((category) => {
          const items = visible.filter((robot) => robot.category === category.key);
          if (!items.length) return null;
          const expanded = expandedFamilies.includes(category.key);
          const shown = expanded ? items : items.slice(0, INITIAL_ITEMS_PER_FAMILY);
          return <section className={`catalog-family catalog-accent-${category.accent}`} key={category.key} aria-labelledby={`family-${category.key}`}>
            <div className="catalog-family-heading"><span className="catalog-family-mark" aria-hidden="true">{category.short}</span><div><h2 id={`family-${category.key}`}>{category.label}</h2><p>Официальный каталог · {items.length} позиций</p></div></div>
            <div className="catalog-grid">{shown.map((robot) => { const key = catalogItemKey(robot); return <RobotCard key={key} robot={robot} family={category} selected={selected.includes(key)} compareFull={selected.length >= MAX_COMPARE} onOpen={() => setDetailPosition(robot)} onToggle={() => toggle(robot)} />; })}</div>
            {items.length > INITIAL_ITEMS_PER_FAMILY && <button className="catalog-show-more" onClick={() => setExpandedFamilies((current) => expanded ? current.filter((key) => key !== category.key) : [...current, category.key])} aria-expanded={expanded}>{expanded ? 'Свернуть раздел' : `Показать ещё ${items.length - INITIAL_ITEMS_PER_FAMILY}`}</button>}
          </section>;
        })}

        <footer className="catalog-footer"><p>Выберите 2–3 позиции для сравнения. Только позиции с тегом «Участвует в расчёте» входят в capacity-пул; остальные доступны для discovery и сравнения.</p><div className="catalog-footer-actions">{selected.length >= 2 && <button type="button" className="secondary-action" onClick={() => setShowCompare(true)}>Сравнить позиции ({selected.length})</button>}{onBack && <button type="button" className="secondary-action" onClick={onBack}>Назад</button>}<button type="button" className="catalog-primary" onClick={onContinue}>Перейти к расчёту <span aria-hidden="true">→</span></button></div></footer>
      </div>
      {showCompare && selectedRobots.length >= 2 && <CompareDialog robots={selectedRobots} onClose={() => setShowCompare(false)} />}
      {detailPosition && <CatalogPositionDialog position={detailPosition} official={Boolean(catalog)} onClose={() => setDetailPosition(null)} />}
    </main>
  );
}

function RobotCard({ robot, family, selected, compareFull, onOpen, onToggle }) {
  const [imageFailed, setImageFailed] = useState(false);
  const media = catalogMedia(robot);
  const facts = (robot.fact_list || []).slice(0, 3);
  const usages = (robot.purpose || []).slice(0, 2);
  const compareDisabled = !selected && compareFull;
  const openFromKeyboard = (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onOpen(); } };
  return <article className={`catalog-card ${selected ? 'is-selected' : ''}`}>
    <div className="catalog-card-open" role="button" tabIndex="0" aria-label={`Подробнее о позиции ${robot.name}`} onClick={onOpen} onKeyDown={openFromKeyboard}>
      <div className="catalog-media">{media && !imageFailed ? <img src={media.src} width={media.width} height={media.height} alt={`Официальное изображение: ${robot.name}`} loading="lazy" decoding="async" onError={() => setImageFailed(true)} /> : <div className="catalog-media-fallback" role="img" aria-label={imageFailed ? `Изображение ${robot.name} не загрузилось` : `Изображение ${robot.name} отсутствует`}><span>{family.short}</span><small>{imageFailed ? 'НЕ УДАЛОСЬ ЗАГРУЗИТЬ' : 'НЕТ ИЗОБРАЖЕНИЯ'}</small></div>}<span className="catalog-position">ПОЗИЦИЯ {robot.source_row_number || '—'}</span><span className="catalog-readiness-tags"><span className={`catalog-state ${robot.calculation_ready ? 'is-ready' : ''}`}>{robot.calculation_ready ? 'Участвует в расчёте' : 'Требует данных'}</span>{robot.calculation_requires_assumptions && <span className="catalog-state is-assumption">С допущениями</span>}</span></div>
      <div className="catalog-card-body"><div className="catalog-card-title"><div><p>{robot.manufacturer || 'Производитель не указан'}</p><h3>{robot.name}</h3></div><span>{family.short}</span></div><p className="catalog-description">{robot.selection?.status}: {robot.selection?.reasons?.join("; ")}</p><p className="catalog-description">{robot.description || 'Описание в исходном каталоге не указано.'}</p>{usages.length > 0 && <div className="catalog-tags" aria-label="Назначение">{usages.map((usage) => <span key={usage}>{usage}</span>)}</div>}{facts.length > 0 && <dl className="catalog-facts">{facts.map((fact) => <div key={fact.code}><dt>{fact.code.replaceAll('_', ' ')}</dt><dd>{typeof fact.value === 'object' ? JSON.stringify(fact.value) : String(fact.value)}{fact.unit ? ` ${fact.unit}` : ''}</dd></div>)}</dl>}<span className="catalog-card-more">Подробнее <span aria-hidden="true">→</span></span></div>
    </div>
    <div className="catalog-card-footer"><div><strong>{formatCatalogPrice(robot)}</strong><small>{robot.type_label || 'Тип не указан'}</small></div><button type="button" onClick={onToggle} disabled={compareDisabled} aria-pressed={selected} title={compareDisabled ? 'Можно сравнить не более трёх позиций' : undefined}>{selected ? 'В сравнении' : compareDisabled ? 'Выбрано 3' : 'Сравнить'}</button></div>
  </article>;
}

function CatalogSkeleton() {
  return <div className="catalog-skeleton" aria-live="polite"><span className="sr-only">Каталог загружается</span>{[1, 2, 3, 4, 5, 6].map((item) => <div key={item}><i /><b /><em /></div>)}</div>;
}

function CatalogEmpty({ title, text, action }) {
  return <section className="catalog-empty" aria-live="polite"><span aria-hidden="true">⌕</span><h2>{title}</h2><p>{text}</p>{action && <button onClick={action}>Сбросить фильтры</button>}</section>;
}

function CompareDialog({ robots, onClose }) {
  const dialog = useRef(null);
  const closeButton = useRef(null);
  const facts = new Map();
  robots.forEach((robot) => (robot.fact_list || []).forEach((fact) => { if (!facts.has(fact.code)) facts.set(fact.code, fact); }));
  useEffect(() => {
    const trigger = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButton.current?.focus();
    const closeOnNavigation = () => onClose();
    window.addEventListener('popstate', closeOnNavigation);
    return () => {
      window.removeEventListener('popstate', closeOnNavigation);
      document.body.style.overflow = previousOverflow;
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    };
  }, [onClose]);
  const handleKeyDown = (event) => {
    if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
    if (event.key !== 'Tab') return;
    const focusable = [...dialog.current.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')];
    if (!focusable.length) return;
    if (event.shiftKey && document.activeElement === focusable[0]) { event.preventDefault(); focusable.at(-1).focus(); }
    else if (!event.shiftKey && document.activeElement === focusable.at(-1)) { event.preventDefault(); focusable[0].focus(); }
  };
  return <div className="catalog-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section ref={dialog} className="catalog-dialog" role="dialog" aria-modal="true" aria-labelledby="compare-title" onKeyDown={handleKeyDown}><header><div><span className="catalog-eyebrow">СРАВНЕНИЕ</span><h2 id="compare-title">Выбранные позиции</h2><p>Информационное сравнение. Исключения сохраняются. Это не рекомендация к закупке; разные классы не имеют общего числового рейтинга.</p></div><button ref={closeButton} type="button" onClick={onClose} aria-label="Закрыть сравнение">×</button></header><div className="catalog-compare-scroll"><table><thead><tr><th>Параметр</th>{robots.map((robot) => <th key={catalogItemKey(robot)}>{robot.name}<small>{robot.manufacturer}</small></th>)}</tr></thead><tbody><tr><td>Пригодность</td>{robots.map((robot) => <td key={catalogItemKey(robot)}>{robot.selection?.status} · {robot.selection?.reasons?.join("; ")}</td>)}</tr><tr><td>Цена, ₽</td>{robots.map((robot) => <td key={catalogItemKey(robot)}><strong>{formatCatalogPrice(robot)}</strong><small>Источник: {robot.purchase?.evidence_id || 'не указан'}</small></td>)}</tr><tr><td>Тип</td>{robots.map((robot) => <td key={catalogItemKey(robot)}>{robot.type_label || '—'}</td>)}</tr>{Array.from(facts.values()).map((fact) => <tr key={fact.code}><td>{fact.code.replaceAll('_', ' ')}</td>{robots.map((robot) => { const current = robot.fact_list?.find((item) => item.code === fact.code); return <td key={catalogItemKey(robot)}>{current ? `${typeof current.value === 'object' ? JSON.stringify(current.value) : current.value}${current.unit ? ` ${current.unit}` : ''} · источник ${current.evidence_id || 'не указан'} (${current.status || 'unknown'})` : '—'}</td>; })}</tr>)}</tbody></table></div></section></div>;
}
