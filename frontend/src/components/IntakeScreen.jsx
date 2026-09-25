import { useState } from 'react';
import ParamsPanel from './ParamsPanel';
import ZonalPanel from './ZonalPanel';
import ProjectFileIntake from './ProjectFileIntake';
import ProcessRoleIntakeV2 from './ProcessRoleIntakeV2';

const API = import.meta.env.VITE_API_URL || '';

const WELCOME = {
  retail: 'Вы выбрали «Торговля: склад». Опишите процесс внутрискладской логистики.\n\nНапример: «800 паллет в сутки, 3 смены, плечо 180 м, зарплата 90 тысяч, 12 человек».',
  airport: 'Вы выбрали «Логистика: аэропорт». Опишите процесс — багажные тележки, уборка.\n\nНапример: «480 тележко-рейсов в сутки, плечо 600 м, 3 смены, 12 водителей по 70 тысяч».',
  clinic: 'Вы выбрали «Соц. сфера: медучреждение». Опишите доставку или уборку.\n\nНапример: «300 доставок в сутки, дальность 300 м, 2 смены, 10 курьеров по 70 тысяч».',
  other: 'Опишите ваш объект и процесс роботизации своими словами.',
};

const PROCESS_DEFAULTS = {
  retail: ['transport', 'pallets'],
  airport: ['transport', 'carts'],
  clinic: ['delivery', 'deliveries'],
  other: ['transport', 'pallets'],
};

export default function IntakeScreen({ objectType, initialCollected, initialSources, initialPrompt = '', activeProject, user, authChecked, projectChoices, projectStatus, onChooseProject, onOpenProjects, onOpenAccount, onFileApplied, onReady, onIntakeV2Normalized, onCapacityResult }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: WELCOME[objectType] || WELCOME.other },
  ]);
  const [input, setInput] = useState(initialPrompt);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState(objectType === 'other' ? 'whole' : 'process-role-v2');
  const [zones, setZones] = useState(initialCollected?.zones || []);
  const [collected, setCollected] = useState(
    initialCollected || {
      object_type: objectType,
      process_type: PROCESS_DEFAULTS[objectType][0],
      cargo_type: PROCESS_DEFAULTS[objectType][1],
    }
  );
  const [sources, setSources] = useState(
    initialCollected
      ? Object.fromEntries(Object.keys(initialCollected).map((k) => [k, initialSources?.[k] || 'preset']))
      : {}
  );
  const [fileContext, setFileContext] = useState(null);
  const [v2FileInput, setV2FileInput] = useState(null);

  const setManual = (field, value) => {
    setCollected((c) => ({ ...c, [field]: value }));
    setSources((s) => ({ ...s, [field]: 'manual' }));
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', text }]);
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: messages.slice(-6).map(({ role, text }) => ({
            role,
            content: text,
          })),
          collected,
        }),
      });
      const data = await res.json();
      setMessages((m) => [...m, { role: 'assistant', text: data.reply }]);
      if (data.collected) {
        const merged = { ...collected, ...data.collected };
        setCollected(merged);
        setSources((s) => {
          const ns = { ...s };
          Object.keys(data.collected).forEach((k) => {
            if (k !== '_hv_asked') ns[k] = 'ai';
          });
          return ns;
        });
        if (data.ready) setTimeout(() => handleReady(merged), 900);
      }
    } catch {
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: '⚠️ Нет связи с сервером' },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const handleReady = (clean) => {
    const base = { ...clean };
    delete base._hv_asked;
    base.mode = mode;
    if (mode === 'zonal') {
      base.zones = zones;
    }
    onReady(base, sources, fileContext);
  };

  const setShared = (k, v) => setCollected((c) => ({ ...c, [k]: v }));

  const applyFile = (normalized, provenance, imported) => {
    setCollected(normalized);
    setMode(normalized.mode || 'whole');
    setZones(normalized.zones || []);
    setSources(Object.fromEntries(
      Object.entries(provenance || {}).map(([field, item]) => [field, item.kind.toLowerCase()]),
    ));
    setFileContext(imported || null);
    if (objectType === 'retail' && mode === 'process-role-v2') setV2FileInput({ normalized, imported });
    onFileApplied?.(normalized);
  };

  return (
    <div className="intake-screen flex min-h-full">
      <div className="flex-1 flex flex-col max-w-3xl mx-auto p-6">
        <header className="mb-3">
          <h1 className="text-xl font-bold">Расчёт сценария роботизации</h1>
          <p className="text-slate-500 text-sm">
            Опишите процесс или введите параметры справа
          </p>
        </header>

        <ProjectFileIntake
          objectType={objectType}
          project={activeProject}
          scenario={activeProject?.scenarios?.find((item) => item.slot === 'BASE')}
          onApplied={applyFile}
        />
        {v2FileInput && mode === 'process-role-v2' && <p className="mb-3 text-xs text-amber-800">Файл перенесён в v2: объём, график, маршрут и численность. Укажите единиц за рейс и подтвердите зарплату monthly gross вручную: старый fte_cost_rub не имеет известной базы.</p>}

        {/* ─── Переключатель режима ─── */}
        <div className="flex gap-1 mb-4 bg-slate-100 rounded-xl p-1 w-fit">
          <button
            onClick={() => setMode('whole')}
            className={`px-4 py-1.5 text-sm rounded-lg transition ${
              mode === 'whole'
                ? 'bg-white shadow font-semibold text-slate-800'
                : 'text-slate-600 hover:text-slate-800'
            }`}
          >
            🏭 Весь объект · старый расчёт
          </button>
          <button
            onClick={() => setMode('zonal')}
            className={`px-4 py-1.5 text-sm rounded-lg transition ${
              mode === 'zonal'
                ? 'bg-white shadow font-semibold text-slate-800'
                : 'text-slate-600 hover:text-slate-800'
            }`}
          >
            🗂 По зонам · старый расчёт
          </button>
          {objectType !== 'other' && <button
            type="button"
            onClick={() => setMode('process-role-v2')}
            className={`px-4 py-1.5 text-sm rounded-lg transition ${
              mode === 'process-role-v2'
                ? 'bg-white shadow font-semibold text-slate-800'
                : 'text-slate-600 hover:text-slate-800'
            }`}
          >
            ⚙ Процессы и роли v2
          </button>}
        </div>

        {mode === 'zonal' && (
          <div className="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 mb-3">
            <b>Зональный режим:</b> каждая зона рассчитывается независимо.
            Парк роботов суммируется, складские интеграции (Wi-Fi, WMS,
            контроллеры) учитываются один раз на весь склад.
          </div>
        )}

        {mode === 'process-role-v2' ? <div className="flex-1 rounded-xl border bg-white p-5 text-sm text-slate-700 space-y-3">
          <h2 className="font-semibold">Новый расчётный путь</h2>
          <p>Заполните процесс и роли справа. Сервер нормализует ввод, считает физическую производительность выбранной модели и сохраняет неизменяемый C11 run.</p>
          <p className="text-amber-800">После C11 сервис запросит явные зарплатные и коммерческие условия, выполнит C13–C21 и сохранит отдельный economics run. Авторские demo-профили и цены организаторов остаются предварительными данными, а не техпаспортом, офертой или C05 PASS. AI-чат старого расчёта здесь отключён.</p>
        </div> : <><div className="flex-1 overflow-auto space-y-3">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'ml-auto bg-blue-600 text-white'
                  : 'bg-white border'
              }`}
            >
              {m.text}
            </div>
          ))}
          {busy && <div className="text-xs text-slate-400">аудитор печатает…</div>}
        </div>

        <div className="flex gap-2 mt-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="Опишите процесс…"
            disabled={busy}
            className="flex-1 border rounded-xl px-4 py-2 text-sm"
          />
          <button
            onClick={send}
            className="bg-blue-600 text-white px-5 rounded-xl text-sm"
          >
            Отправить
          </button>
        </div></>}
      </div>

      {mode === 'process-role-v2' ? (
        <ProcessRoleIntakeV2 key={`${objectType}:${v2FileInput?.imported?.id || 'manual'}`} objectType={objectType} importedFile={v2FileInput} activeProject={activeProject} user={user} authChecked={authChecked} projectChoices={projectChoices} projectStatus={projectStatus} onChooseProject={onChooseProject} onOpenProjects={onOpenProjects} onOpenAccount={onOpenAccount} onNormalized={onIntakeV2Normalized} onCapacityResult={onCapacityResult} />
      ) : mode === 'whole' ? (
        <ParamsPanel
          collected={collected}
          setManual={setManual}
          sources={sources}
          objectType={objectType}
          onReady={() => handleReady(collected)}
        />
      ) : (
        <ZonalPanel
          zones={zones}
          setZones={setZones}
          shared={collected}
          setShared={setShared}
          objectType={objectType}
          onReady={() => handleReady(collected)}
        />
      )}
    </div>
  );
}
