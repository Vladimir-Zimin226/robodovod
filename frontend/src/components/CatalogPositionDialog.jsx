import { useEffect, useMemo, useRef, useState } from 'react';

import {
  catalogDetailView,
  catalogItemKey,
  catalogMedia,
  formatCatalogFact,
  formatCatalogPrice,
  normalizeOfficialModel,
  runtimeBlockerLabel,
} from '../catalogPresentation';

const API = import.meta.env.VITE_API_URL || '';

function readResponse(response) {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function DetailValue({ label, children }) {
  return <div><dt>{label}</dt><dd>{children ?? 'Не указано'}</dd></div>;
}

function DetailTags({ label, values }) {
  if (!values.length) return null;
  return <div className="catalog-detail-tags" aria-label={label}>{values.map((value) => <span key={value}>{value}</span>)}</div>;
}

export default function CatalogPositionDialog({ position, official, onClose }) {
  const [detail, setDetail] = useState(position);
  const [status, setStatus] = useState(official ? 'loading' : 'ready');
  const [error, setError] = useState('');
  const [imageFailed, setImageFailed] = useState(false);
  const dialog = useRef(null);
  const closeButton = useRef(null);

  useEffect(() => {
    if (!official) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/catalog/positions/${encodeURIComponent(catalogItemKey(position))}`, { signal: controller.signal })
      .then(readResponse)
      .then((payload) => {
        setDetail(normalizeOfficialModel(payload));
        setStatus('ready');
      })
      .catch((requestError) => {
        if (requestError.name === 'AbortError') return;
        setError('Подробные данные временно недоступны. Показана информация из каталога.');
        setStatus('error');
      });
    return () => controller.abort();
  }, [official, position]);

  useEffect(() => {
    const trigger = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButton.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (trigger instanceof HTMLElement) trigger.focus();
    };
  }, []);

  const view = useMemo(() => catalogDetailView(detail), [detail]);
  const media = catalogMedia(detail);
  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [...dialog.current.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="catalog-dialog-backdrop catalog-detail-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialog} className="catalog-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="catalog-detail-title" aria-describedby="catalog-detail-description" aria-busy={status === 'loading'} onKeyDown={handleKeyDown}>
        <header>
          <div><span className="catalog-eyebrow">ПОЗИЦИЯ {detail.source_row_number || '—'}</span><h2 id="catalog-detail-title">{detail.name}</h2><p>{detail.manufacturer || 'Производитель не указан'}</p></div>
          <button ref={closeButton} type="button" onClick={onClose} aria-label="Закрыть подробную карточку">×</button>
        </header>
        <div className="catalog-detail-scroll">
          {status === 'loading' && <p className="catalog-detail-loading" role="status">Загружаем полные данные позиции…</p>}
          {error && <p className="catalog-detail-error" role="alert">{error}</p>}

          <div className="catalog-detail-hero">
            <div className="catalog-detail-media">
              {media && !imageFailed
                ? <img src={media.src} width={media.width} height={media.height} alt={`Официальное изображение: ${detail.name}`} onError={() => setImageFailed(true)} />
                : <div className="catalog-media-fallback" role="img" aria-label={`Изображение ${detail.name} отсутствует`}><span>{detail.system_family || 'РТК'}</span><small>НЕТ ИЗОБРАЖЕНИЯ</small></div>}
            </div>
            <div className="catalog-detail-summary">
              <div className="catalog-detail-state-row"><div className="catalog-detail-state-tags"><span className={`catalog-detail-state ${detail.calculation_ready ? 'is-ready' : ''}`}>{detail.calculation_ready ? 'Участвует в расчёте' : 'Требует данных'}</span>{detail.calculation_requires_assumptions && <span className="catalog-detail-state is-assumption">С допущениями</span>}</div><strong>{formatCatalogPrice(detail)}</strong></div>
              <h3>Описание модели</h3>
              <p id="catalog-detail-description">{view.description}</p>
              <dl className="catalog-detail-metrics">
                <DetailValue label="Тип">{detail.type_code}</DetailValue>
                <DetailValue label="УГТ">{view.trl}</DetailValue>
                <DetailValue label="Стадия">{view.lifecycleStage}</DetailValue>
                <DetailValue label="Рыночный потенциал">{view.marketPotential}</DetailValue>
              </dl>
            </div>
          </div>

          <section className="catalog-detail-section" aria-labelledby="catalog-applicability-title">
            <div className="catalog-detail-section-heading"><span>01</span><div><h3 id="catalog-applicability-title">Применимость и кейс</h3><p>Данные относятся к этой исходной позиции каталога.</p></div></div>
            <DetailTags label="Отрасли" values={view.industries} />
            <DetailTags label="Сценарии" values={view.useCases} />
            <DetailTags label="Регионы" values={view.regions} />
            <div className="catalog-detail-copy"><h4>Кейс позиции</h4><p>{view.caseText || 'Кейс для этой позиции не указан.'}</p></div>
            {view.serviceLabels.length > 0 && <div className="catalog-detail-copy"><h4>Служебные метки источника</h4><DetailTags label="Служебные метки источника" values={view.serviceLabels} /></div>}
          </section>

          <section className="catalog-detail-section" aria-labelledby="catalog-facts-title">
            <div className="catalog-detail-section-heading"><span>02</span><div><h3 id="catalog-facts-title">Характеристики</h3><p>Только факты, прошедшие серверный evidence gate.</p></div></div>
            {view.facts.length > 0
              ? <dl className="catalog-detail-facts">{view.facts.map((fact) => <DetailValue key={fact.code} label={fact.code.replaceAll('_', ' ')}>{formatCatalogFact(fact)}</DetailValue>)}</dl>
              : <p className="catalog-detail-empty">Проверенные характеристики отсутствуют.</p>}
          </section>

          <section className="catalog-detail-section" aria-labelledby="catalog-procurement-title">
            <div className="catalog-detail-section-heading"><span>03</span><div><h3 id="catalog-procurement-title">Условия приобретения</h3><p>Row-specific данные, не общие для всех дублей модели.</p></div></div>
            <dl className="catalog-detail-list">
              <DetailValue label="Цена">{view.purchasePrice}</DetailValue>
              <DetailValue label="Статус цены">{view.purchase?.price_status}</DetailValue>
              <DetailValue label="НДС">{view.purchase?.vat_status}</DetailValue>
              <DetailValue label="Evidence ID">{view.purchase?.evidence_id}</DetailValue>
            </dl>
          </section>

          <section className="catalog-detail-section" aria-labelledby="catalog-runtime-title">
            <div className="catalog-detail-section-heading"><span>04</span><div><h3 id="catalog-runtime-title">Участие в предварительном расчёте</h3><p>Capacity readiness отделена от готовности к внедрению, закупке и economics.</p></div></div>
            <dl className="catalog-detail-list">
              <DetailValue label="Статус">{detail.calculation_readiness_status}</DetailValue>
              <DetailValue label="Capacity profile">{detail.calculation_profile}</DetailValue>
              <DetailValue label="Runtime version">{detail.runtime_catalog_version}</DetailValue>
              <DetailValue label="Deployment">{detail.deployment_readiness_status}</DetailValue>
            </dl>
            {view.calculationBlockers.length > 0
              ? <ul className="catalog-runtime-blockers">{view.calculationBlockers.map((blocker) => <li key={blocker}><strong>{runtimeBlockerLabel(blocker)}</strong><code>{blocker}</code></li>)}</ul>
              : <p className="catalog-detail-ready">Расчётные vendor facts прошли evidence gate.</p>}
            {view.calculationVendorFacts.length > 0 && <div className="catalog-detail-copy"><h4>Vendor facts для capacity</h4><dl className="catalog-detail-facts">{view.calculationVendorFacts.map((fact) => <DetailValue key={fact.field} label={fact.field}>{formatCatalogFact(fact)} · {fact.status} · evidence {fact.evidence_id}</DetailValue>)}</dl></div>}
            {view.calculationAssumptions.length > 0 && <div className="catalog-assumptions"><h4>Сценарные допущения</h4><p>Это входы сценария, а не характеристики производителя.</p><ul>{view.calculationAssumptions.map((assumption) => <li key={assumption.field}><strong>{assumption.field}</strong><span>Сначала {assumption.input_path}; fallback {String(assumption.fallback_value)} {assumption.unit}</span><code>{assumption.provenance}</code></li>)}</ul></div>}
          </section>

          <section className="catalog-detail-section" aria-labelledby="catalog-provenance-title">
            <div className="catalog-detail-section-heading"><span>05</span><div><h3 id="catalog-provenance-title">Источник и происхождение</h3><p>Проверяемая связь с исходной карточкой.</p></div></div>
            <dl className="catalog-detail-list catalog-provenance-list">
              <DetailValue label="Position ID">{detail.position_id || detail.id}</DetailValue>
              <DetailValue label="Source key">{detail.source_record_key}</DetailValue>
              <DetailValue label="PDF">{view.sourceLocation}</DetailValue>
              <DetailValue label="Mapping">{detail.enrichment?.mapping_status}</DetailValue>
              <DetailValue label="Описание">{detail.enrichment?.description_status}</DetailValue>
              <DetailValue label="Adapter">{detail.enrichment?.provenance?.adapter}</DetailValue>
              <DetailValue label="Transcript SHA-256"><code>{detail.enrichment?.provenance?.transcript_sha256}</code></DetailValue>
              <DetailValue label="Media SHA-256"><code>{detail.media?.sha256 || detail.enrichment?.provenance?.media_sha256}</code></DetailValue>
            </dl>
            {view.sourceUrl && <a className="catalog-source-link" href={view.sourceUrl} target="_blank" rel="noreferrer">Открыть ссылку из PDF <span aria-hidden="true">↗</span></a>}
            {view.limitation && <p className="catalog-detail-limitation"><strong>Ограничение источника:</strong> {view.limitation}</p>}
          </section>
        </div>
      </section>
    </div>
  );
}
