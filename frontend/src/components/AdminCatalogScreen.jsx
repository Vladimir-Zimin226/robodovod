import { useEffect, useState } from 'react';
import { persistenceRequest as request, readCsrfCookie } from '../persistenceApi';

const ROOT = '/api/admin/catalog';
const emptyModel = (key) => ({ key, name: 'Новое решение', manufacturer: '', system_family: 'OTHER', type_code: 'OTHER',
  purpose: '', country: '', availability: 'UNKNOWN', infrastructure: '', lifespan_years: null, specs: [] });
const emptyOffer = (key, model_key) => ({ key, model_key, industry: '', scenario: '', region: '', case_text: '', mode: 'PURCHASE',
  amount: null, currency: null, vat_status: 'UNKNOWN', vat_rate: null, price_unit: 'UNKNOWN', included_costs: [], excluded_costs: [], status: 'UNKNOWN', source: null, comment: '' });
const statuses = ['UNKNOWN', 'CONFLICT', 'VERIFIED_OFFICIAL', 'MANUALLY_APPROVED'];
const statusLabel = { UNKNOWN: 'Неизвестно', CONFLICT: 'Конфликт', VERIFIED_OFFICIAL: 'Официальный источник', MANUALLY_APPROVED: 'Проверено вручную' };

function Input({ label, value, onChange, type = 'text', ...props }) {
  return <label className="block text-sm">{label}<input className="mt-1 w-full rounded border p-2" type={type}
    value={value ?? ''} onChange={(event) => onChange(event.target.value)} {...props} /></label>;
}
function Select({ label, value, onChange, children }) {
  return <label className="block text-sm">{label}<select className="mt-1 w-full rounded border p-2" value={value ?? ''}
    onChange={(event) => onChange(event.target.value)}>{children}</select></label>;
}
function Evidence({ item, sources, onChange }) {
  return <>
    <Select label="Подтверждение" value={item.status} onChange={(status) => onChange({ status })}>
      {statuses.map((status) => <option key={status} value={status}>{statusLabel[status]}</option>)}
    </Select>
    <Select label="Источник" value={item.source} onChange={(source) => onChange({ source: source || null })}>
      <option value="">Не указан</option>{sources.map((source) => <option key={source.key} value={source.key}>{source.document || source.url}</option>)}
    </Select>
    <Input label="Комментарий проверки" value={item.comment} onChange={(comment) => onChange({ comment })} />
  </>;
}

function SpecValue({ spec, onChange }) {
  const encoded = typeof spec.value === 'object' && spec.value !== null ? JSON.stringify(spec.value) : String(spec.value ?? '');
  const [value, setValue] = useState(encoded);
  return <label className="block text-sm">Значение · пусто = неизвестно · {spec.datatype || 'NUMBER'}<input className="mt-1 w-full rounded border p-2" value={value}
    onChange={(event) => { setValue(event.target.value); event.target.setCustomValidity(''); }}
    onBlur={(event) => { try { const parsed = value === '' ? null : ['JSON', 'BOOLEAN'].includes(spec.datatype) ? JSON.parse(value) : value;
      onChange({ value: parsed, ...(parsed === null ? { status: 'UNKNOWN' } : {}) }); }
    catch { event.target.setCustomValidity('Укажите корректное JSON-значение'); event.target.reportValidity(); } }} /></label>;
}

export default function AdminCatalogScreen({ user }) {
  const [listing, setListing] = useState(null);
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState(null);
  const [selectedCode, setSelectedCode] = useState('');
  const [newCode, setNewCode] = useState('');
  const [modelKey, setModelKey] = useState('');
  const [offerKey, setOfferKey] = useState('');
  const [sourceKey, setSourceKey] = useState('');
  const [section, setSection] = useState('models');
  const [allSlots, setAllSlots] = useState(false);
  const [includeRuntime, setIncludeRuntime] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [audit, setAudit] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [dirty, setDirty] = useState(false);
  const loadListing = async () => { const value = await request(ROOT); setListing(value); return value; };
  useEffect(() => { let alive = true; request(ROOT).then((value) => { if (alive) setListing(value); })
    .catch((err) => { if (alive) setError(err.message); }); return () => { alive = false; }; }, []);
  const adopt = (value) => { setRecord(value); setDraft(structuredClone(value.document)); setSelectedCode(value.code);
    setModelKey(value.document.models[0]?.key || ''); setOfferKey(value.document.offers[0]?.key || '');
    setSourceKey(value.document.sources[0]?.key || ''); setDirty(false); setConfirmed(false); };
  const run = async (work, success) => { setBusy(true); setError(''); setNotice('');
    try { const result = await work(); if (result?.document) adopt(result); await loadListing(); setNotice(success); }
    catch (err) { setError(err.message); } finally { setBusy(false); } };
  const write = (route, body, method = 'POST') => request(`${ROOT}${route}`, { method,
    headers: { 'X-CSRF-Token': readCsrfCookie() }, body: JSON.stringify(body) });
  const update = (name, key, patch) => { setDraft((old) => ({ ...old, [name]: old[name].map((item) => item.key === key ? { ...item, ...patch } : item) }));
    setDirty(true); setConfirmed(false); };
  const add = (name, item) => { setDraft((old) => ({ ...old, [name]: [...old[name], item] })); setDirty(true); setConfirmed(false); };
  const remove = (name, key) => { setDraft((old) => ({ ...old, [name]: old[name].filter((item) => item.key !== key) })); setDirty(true); setConfirmed(false); };
  const editable = record && ['DRAFT', 'VALIDATED'].includes(record.status) && record.owner_id === user.id;
  const model = draft?.models.find((item) => item.key === modelKey);
  const offer = draft?.offers.find((item) => item.key === offerKey);
  const source = draft?.sources.find((item) => item.key === sourceKey);
  const readiness = record?.model_readiness.find((item) => item.key === modelKey);
  const slots = [...(allSlots ? ['discovery', 'capacity'] : ['discovery']), ...(includeRuntime ? ['runtime'] : [])];
  const active = Object.fromEntries((listing?.active || []).map((item) => [item.slot, item.catalog_code]));
  const activate = () => run(() => write(`/versions/${encodeURIComponent(record.code)}/activate`, {
    slots, expected_active: Object.fromEntries(slots.map((slot) => [slot, active[slot] || null])),
  }), 'Активная версия переключена. Сохранённые расчёты и симуляции используют прежние снимки.');
  const download = () => { const blob = new Blob([JSON.stringify({ code: newCode || `${record.code}-copy`, parent_code: record.status === 'PUBLISHED' ? record.code : draft.base_catalog_code,
    document: draft }, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'admin-catalog-v1.json'; anchor.click(); URL.revokeObjectURL(url); };
  const importFile = async (file) => { if (!file) return; if (file.size > 4 * 1024 * 1024) { setError('Максимальный размер — 4 МиБ.'); return; }
    await run(async () => { const text = await file.text(); const value = JSON.parse(text);
      if (value.document?.schema_version !== 'admin-catalog-v1') throw new Error('Ожидается файл admin-catalog-v1.json.');
      const result = await request(`${ROOT}/import`, { method: 'POST', headers: { 'X-CSRF-Token': readCsrfCookie() }, body: text });
      setNotice(result.idempotent ? 'Этот файл уже импортирован.' : 'Файл проверен и сохранён как черновик.'); return result;
    }, 'Импорт проверен. Просмотрите diff; публикация и активация выполняются отдельно.'); };

  return <section className="persistence-screen space-y-4" aria-label="Администрирование каталога">
    <div className="persistence-heading"><span className="eyebrow">АДМИНИСТРАТОР</span><h1>Каталог и источники</h1>
      <p>Редактируйте свою новую версию, проверьте изменения, опубликуйте и явно переключите каталог.</p></div>
    {error && <p role="alert" className="form-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="panel grid gap-3 p-4 md:grid-cols-2">
      <Select label="Версия для просмотра или возврата" value={selectedCode} onChange={(code) => run(() => request(`${ROOT}/versions/${encodeURIComponent(code)}`), 'Версия загружена.')}>
        <option value="">Выберите версию</option>{listing?.versions.map((item) => <option key={item.code} value={item.code}>{item.code} · {item.status}</option>)}
      </Select>
      <Input label="Код новой версии" value={newCode} onChange={setNewCode} placeholder="catalog-2026-09-26-01" />
      <button disabled={busy || record?.status !== 'PUBLISHED' || !newCode} className="secondary-action"
        onClick={() => run(() => write('/versions', { code: newCode, parent_code: record.code }), 'Черновик создан от опубликованной версии.')}>Создать черновик</button>
      <label className="secondary-action">Обновить каталог · JSON<input aria-label="Обновить каталог" type="file" accept=".json,application/json" disabled={busy}
        onChange={(event) => { importFile(event.target.files[0]); event.target.value = ''; }} /></label>
      <p className="text-sm md:col-span-2">Активные версии: {(listing?.active || []).map((item) => `${item.slot}: ${item.catalog_code}`).join(' · ') || 'Не назначены'}</p>
    </div>
    {draft && <>
      <div className="panel space-y-2 p-4"><h2 className="text-lg font-semibold">{record.code} · {record.status} · редакция {record.revision ?? 'исходная'}</h2>
        <p>Расчётные позиции: {record.calculation_ready_positions}. Переключение расчётного источника: {record.capacity_activation_ready ? 'проверенный физический пул сохранён' : record.capacity_activation_blockers.join('; ')}.</p>
        <p>Новая или изменённая физическая модель требует подтверждения источников и отдельного разрешения rollout. Пустое значение — неизвестно.</p>
        {!editable && <p>Просмотр опубликованной версии или черновика другого администратора. Для правки создайте собственный черновик.</p>}
        <nav className="flex flex-wrap gap-2">{[['models', 'Решения и ТТХ'], ['offers', 'Предложения'], ['sources', 'Источники'], ['defaults', 'Нормы'], ['dictionaries', 'Справочники']].map(([key, label]) =>
          <button key={key} className="secondary-action" aria-pressed={section === key} onClick={() => setSection(key)}>{label}</button>)}</nav>
      </div>
      <div className="panel p-4">
        {section === 'models' && <Select label="Решение" value={modelKey} onChange={setModelKey}>{draft.models.map((item) => <option key={item.key} value={item.key}>{item.name} · {item.key}</option>)}</Select>}
        {section === 'offers' && <Select label="Отдельное предложение" value={offerKey} onChange={setOfferKey}>{draft.offers.map((item) => <option key={item.key} value={item.key}>{item.key} · {item.amount ?? 'цена неизвестна'} {item.currency}</option>)}</Select>}
        {section === 'sources' && <Select label="Источник данных" value={sourceKey} onChange={setSourceKey}>{draft.sources.map((item) => <option key={item.key} value={item.key}>{item.document || item.url}</option>)}</Select>}
      </div>
      <fieldset disabled={!editable || busy} className="panel min-w-0 space-y-4 p-4">
        {section === 'models' && <>
          <button className="secondary-action" onClick={() => { const key = `model-${crypto.randomUUID()}`; add('models', emptyModel(key)); setModelKey(key); }}>Добавить решение</button>
          {model && <><p>Идентификатор: {model.key}. {readiness?.ready ? 'Расчётный профиль сохранён' : `Информационное решение: ${readiness?.blockers.join('; ') || 'требуется проверка'}`}</p>
            <p>Полнота обязательных ТТХ: {readiness?.completeness === 'COMPLETE' ? 'подтверждены' : 'неизвестна / нужны данные'}. Не хватает: {readiness?.missing_specs.join(', ') || 'проверяется поддержка профиля'}.</p>
            <div className="grid gap-3 md:grid-cols-2">{[['name', 'Название'], ['manufacturer', 'Производитель'], ['system_family', 'Семейство'], ['type_code', 'Тип'], ['purpose', 'Назначение'], ['country', 'Страна'], ['availability', 'Доступность'], ['infrastructure', 'Инфраструктура']].map(([key, label]) =>
              <Input key={key} label={label} value={model[key]} onChange={(value) => update('models', model.key, { [key]: value })} />)}
              <Input label="Срок службы, лет · пусто = неизвестно" type="number" min="0.01" max="100" step="any" value={model.lifespan_years} onChange={(value) => update('models', model.key, { lifespan_years: value === '' ? null : Number(value) })} />
            </div>
            <h3>Характеристики · известно {model.specs.filter((spec) => spec.value !== null).length} из {model.specs.length}; обязательность проверяет расчётный профиль</h3>
            {model.specs.map((spec, n) => { const change = (patch) => update('models', model.key, { specs: model.specs.map((item, i) => i === n ? { ...item, ...patch } : item) });
              return <div key={n} className="grid gap-2 rounded border p-3 md:grid-cols-3">
                <Input label="Код характеристики" value={spec.code} onChange={(code) => change({ code })} />
                <SpecValue key={`${record.code}:${record.revision}:${model.key}:${spec.code}:${n}:${JSON.stringify(spec.value)}`} spec={spec} onChange={change} />
                <Select label="Тип значения" value={spec.datatype || 'NUMBER'} onChange={(datatype) => change({ datatype })}>{['NUMBER', 'TEXT', 'BOOLEAN', 'JSON'].map((kind) => <option key={kind}>{kind}</option>)}</Select>
                <Input label="Каноническая единица" value={spec.unit} onChange={(unit) => change({ unit })} />
                <Input label="Область характеристики" value={spec.scope} onChange={(scope) => change({ scope })} />
                <Evidence item={spec} sources={draft.sources} onChange={change} />
                <button className="secondary-action" onClick={() => update('models', model.key, { specs: model.specs.filter((_, i) => i !== n) })}>Удалить характеристику</button>
              </div>; })}
            <button className="secondary-action" onClick={() => update('models', model.key, { specs: [...model.specs, { code: 'payload', value: null, datatype: 'NUMBER', unit: 'kg', scope: 'MODEL', status: 'UNKNOWN', source: null, comment: '' }] })}>Добавить характеристику</button>
          </>}
        </>}
        {section === 'offers' && <>
          <button className="secondary-action" onClick={() => { const key = `offer-${crypto.randomUUID()}`; add('offers', emptyOffer(key, modelKey)); setOfferKey(key); }}>Добавить предложение</button>
          {offer && <div className="grid gap-3 md:grid-cols-2"><p>Идентификатор предложения: {offer.key}</p>
            <Select label="Решение предложения" value={offer.model_key} onChange={(model_key) => update('offers', offer.key, { model_key })}>{draft.models.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}</Select>
            {[['industry', 'Отрасль'], ['scenario', 'Применимость / сценарий'], ['region', 'Регион'], ['case_text', 'Описание применения'], ['mode', 'Покупка / RaaS'], ['amount', 'Цена · пусто = неизвестно'], ['currency', 'Валюта, ISO'], ['vat_status', 'НДС · INCLUDED / EXCLUDED / UNKNOWN']].map(([key, label]) =>
              <Input key={key} label={label} value={offer[key]} onChange={(value) => update('offers', offer.key, { [key]: ['amount', 'currency'].includes(key) && value === '' ? null : value })} />)}
            {['included_costs', 'excluded_costs'].map((key) => <Input key={key} label={key === 'included_costs' ? 'Включённые услуги · через ;' : 'Исключённые услуги · через ;'} value={offer[key].join('; ')} onChange={(value) => update('offers', offer.key, { [key]: value.split(';').map((item) => item.trim()).filter(Boolean) })} />)}
            <Input label="Ставка НДС, доля 0–1 · пусто = неизвестно" value={offer.vat_rate} onChange={(value) => update('offers', offer.key, { vat_rate: value || null })} />
            <Select label="Период цены" value={offer.price_unit || 'UNKNOWN'} onChange={(price_unit) => update('offers', offer.key, { price_unit })}>{[['UNKNOWN','Неизвестен'],['ONE_TIME','Однократно'],['MONTH','Месяц'],['YEAR','Год'],['HOUR','Час']].map(([value,label]) => <option key={value} value={value}>{label}</option>)}</Select>
            <Evidence item={offer} sources={draft.sources} onChange={(patch) => update('offers', offer.key, patch)} />
          </div>}
        </>}
        {section === 'sources' && <>
          <button className="secondary-action" onClick={() => { const key = `source-${crypto.randomUUID()}`; const today = new Date().toISOString().slice(0, 10); add('sources', { key, url: '', document: 'Документ проверки', received_on: today, updated_on: today, comment: '' }); setSourceKey(key); }}>Добавить источник</button>
          {source && <div className="grid gap-3 md:grid-cols-2">{[['url', 'URL'], ['document', 'Документ / ссылка на хранилище'], ['received_on', 'Дата получения'], ['updated_on', 'Дата обновления'], ['comment', 'Комментарий источника']].map(([key, label]) =>
            <Input key={key} label={label} type={key.endsWith('_on') ? 'date' : 'text'} value={source[key]} onChange={(value) => update('sources', source.key, { [key]: value || (key.endsWith('_on') ? null : '') })} />)}</div>}
        </>}
        {section === 'defaults' && <>
          <p>Разрешены предложения: exchange_seconds (s, 0.001–86400), units_per_trip (pallet/trip, 1–100000), operating_days (day/year, 1–366). Пользователь применяет и подтверждает их в новой версии профиля. Формулы и константы registry закрыты для правки.</p>
          {draft.defaults.map((norm) => <div key={norm.key} className="grid gap-3 rounded border p-3 md:grid-cols-2">
            <p>{norm.key}</p>{['value', 'unit', 'lower', 'upper', 'comment'].map((key) => <Input key={key} label={{ value: 'Значение нормы', unit: 'Единица', lower: 'Нижняя граница', upper: 'Верхняя граница', comment: 'Основание нормы' }[key]} value={norm[key]} onChange={(value) => update('defaults', norm.key, { [key]: value })} />)}
            <Select label="Источник нормы" value={norm.source} onChange={(value) => update('defaults', norm.key, { source: value })}><option value="">Выберите источник</option>{draft.sources.map((item) => <option key={item.key} value={item.key}>{item.document || item.url}</option>)}</Select>
            <button className="secondary-action" onClick={() => remove('defaults', norm.key)}>Удалить норму</button>
          </div>)}
          {['exchange_seconds', 'units_per_trip', 'operating_days'].filter((key) => !draft.defaults.some((item) => item.key === key)).map((key) => <button key={key} className="secondary-action mr-2" onClick={() => add('defaults', { key, value: key === 'exchange_seconds' ? '30' : key === 'operating_days' ? '250' : '1', unit: key === 'exchange_seconds' ? 's' : key === 'operating_days' ? 'day/year' : 'pallet/trip', lower: '1', upper: key === 'exchange_seconds' ? '86400' : key === 'operating_days' ? '366' : '100000', source: sourceKey, comment: 'Укажите основание и границы допущения' })}>Добавить {key}</button>)}
        </>}
        {section === 'dictionaries' && <>
          {draft.dictionaries.map((entry, n) => <div key={n} className="grid gap-3 rounded border p-3 md:grid-cols-2">
            {['key', 'label', 'unit'].map((key) => <Input key={key} label={{ key: 'Код справочника', label: 'Название', unit: 'Единица для ТТХ' }[key]} value={entry[key]} onChange={(value) => update('dictionaries', entry.key, { [key]: value || (key === 'unit' ? null : '') })} />)}
            <Select label="Вид справочника" value={entry.kind} onChange={(kind) => update('dictionaries', entry.key, { kind })}>{['type', 'availability', 'industry', 'spec'].map((kind) => <option key={kind}>{kind}</option>)}</Select>
            <Select label="Источник справочника" value={entry.source} onChange={(value) => update('dictionaries', entry.key, { source: value })}><option value="">Выберите источник</option>{draft.sources.map((item) => <option key={item.key} value={item.key}>{item.document || item.url}</option>)}</Select>
            <button className="secondary-action" onClick={() => remove('dictionaries', entry.key)}>Удалить запись</button>
          </div>)}
          <button className="secondary-action" onClick={() => add('dictionaries', { key: `type-${crypto.randomUUID()}`, label: 'Новый тип', kind: 'type', unit: null, source: sourceKey })}>Добавить запись справочника</button>
        </>}
      </fieldset>
      <div className="panel space-y-3 p-4">
        <button className="primary-action" disabled={!editable || !dirty || busy} onClick={() => run(() => write(`/versions/${encodeURIComponent(record.code)}`, { expected_revision: record.revision, document: draft }, 'PUT'), 'Изменения сохранены. Проверьте diff.')}>Сохранить и показать diff</button>
        <button className="secondary-action ml-2" disabled={busy} onClick={download}>Скачать JSON для обновления</button>
        <h2>Изменения относительно родительской версии · {record.diff.length}</h2>
        {dirty && <p>Есть несохранённые правки. Diff и расчётная готовность обновятся после сохранения.</p>}
        <div className="max-h-80 overflow-auto">{record.diff.map((change) => <details key={`${change.section}:${change.key}`}><summary>{change.section} · {change.key} · {change.before ? 'изменено' : 'добавлено'}</summary>
          <pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify({ before: change.before, after: change.after }, null, 2)}</pre></details>)}</div>
        <button className="secondary-action" disabled={!editable || dirty || busy} onClick={() => run(() => write(`/versions/${encodeURIComponent(record.code)}/validate`, { expected_revision: record.revision }), 'Текущая редакция проверена.')}>Проверить версию</button>
        <label className="block"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> Я проверил diff и подтверждаю публикацию / переключение выбранной версии.</label>
        <button className="primary-action" disabled={!editable || record.status !== 'VALIDATED' || dirty || busy || !confirmed} onClick={() => run(() => write(`/versions/${encodeURIComponent(record.code)}/publish`, { expected_revision: record.revision }), 'Версия опубликована; активные указатели ещё не изменены.')}>Опубликовать версию</button>
        <label className="block"><input type="checkbox" checked={allSlots} onChange={(event) => { setAllSlots(event.target.checked); setConfirmed(false); }} /> Переключить discovery и capacity вместе (требуется сохранённый утверждённый физический пул).</label>
        <label className="block"><input type="checkbox" checked={includeRuntime} disabled={!record.runtime_activation_ready} onChange={(event) => { setIncludeRuntime(event.target.checked); setConfirmed(false); }} /> Также переключить legacy runtime · {record.runtime_activation_ready ? 'доступен' : 'нет подтверждённых legacy runtime позиций'}.</label>
        <button className="secondary-action" disabled={record.status !== 'PUBLISHED' || busy || !confirmed || (allSlots && !record.capacity_activation_ready) || (includeRuntime && !record.runtime_activation_ready)} onClick={activate}>Активировать выбранную версию / вернуть указатель</button>
      </div>
    </>}
    <div className="panel p-4"><button className="secondary-action" disabled={busy} onClick={() => run(async () => { const value = await request(`${ROOT}/audit`); setAudit(value.entries); }, 'Аудит загружен.')}>Показать аудит</button>
      <ul>{audit.map((item, i) => <li key={i}>{item.at} · {item.actor} · {item.event} · {item.change.catalog_code}<details><summary>Что изменилось</summary><pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(item.change, null, 2)}</pre></details></li>)}</ul></div>
  </section>;
}
