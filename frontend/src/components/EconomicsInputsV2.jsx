import { useState } from 'react';
import { readCsrfCookie } from '../persistenceApi';
import { buildEconomicsRunRequest } from '../economicsInputV2';

const API = import.meta.env.VITE_API_URL || '';
const today = () => new Date().toISOString().slice(0, 10);

const initialValues = (capacityRunId) => ({
  capacityRunId, evaluationDate: today(), horizonYears: '5', discountRate: '0.15',
  primaryRoleId: '', manualUnitsPerShift: '', grossConfirm: false,
  controlHeadcount: '', controlMonthlyGross: '', technicianHeadcount: '', technicianMonthlyGross: '',
  currencyConfirm: false, implementationCost: '', annualService: '', warrantyYears: '', averagePowerW: '',
  initialBatteryConfirm: false, batteryServiceConfirm: false,
  sharedSiteCapital: '', sharedAnnualCost: '', raasMonthly: '', raasContractMonths: '60',
  raasInfrastructureOwner: 'VENDOR', raasScopeConfirm: false,
  startSeconds: '0', timezone: 'Europe/Moscow',
});

export default function EconomicsInputsV2({ capacityRequest, capacityRunId, project, onComplete }) {
  const [values, setValues] = useState(() => initialValues(capacityRunId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const scenario = project?.scenarios?.find((item) => item.slot === 'BASE');
  const set = (key) => (event) => setValues((current) => ({
    ...current, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
  }));

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const body = buildEconomicsRunRequest({
        values: { ...values, capacityRunId }, capacityRequest, project, scenario,
      });
      const response = await fetch(`${API}/api/v2/projects/${encodeURIComponent(project.id)}/economics-runs`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'Серверный расчёт экономики не выполнен.');
      onComplete(payload);
    } catch (submitError) {
      setError(submitError.message || 'Не удалось выполнить расчёт.');
    } finally {
      setBusy(false);
    }
  };

  if (!project || !scenario || !capacityRunId) return null;
  const roleRefs = capacityRequest?.process?.role_refs || [];
  return <form className="economics-inputs-v2 mx-auto my-6 max-w-6xl rounded-2xl border p-5 shadow-sm space-y-5" onSubmit={submit} aria-label="Экономика C13–C21">
    <header>
      <h2 className="text-xl font-semibold">Продолжить серверный расчёт: C13–C21</h2>
      <p className="mt-1 text-sm text-amber-900">Для полного C13–C21 все поля пока обязательны. Заполняйте их только известными значениями или осознанными сценарными допущениями. Это не техпаспорт и не коммерческое предложение; цена каталога останется organizer dataset, procurement — UNVERIFIED без оферты.</p>
    </header>
    <section>
      <h3 className="font-semibold">Труд и текущий процесс</h3>
      <div className="mt-2 grid gap-3 md:grid-cols-4">
        {roleRefs.length > 1 && <Field label="Основная роль"><select value={values.primaryRoleId} onChange={set('primaryRoleId')} className="w-full border rounded p-2"><option value="">Выберите</option>{roleRefs.map((id) => <option key={id} value={id}>{id}</option>)}</select></Field>}
        {capacityRequest?.process?.scope !== 'CLEANING_AREA' && <Field label="Ручная производительность, ед./смену"><Input value={values.manualUnitsPerShift} onChange={set('manualUnitsPerShift')} /></Field>}
        <Field label="Текущие диспетчеры, чел."><Input value={values.controlHeadcount} onChange={set('controlHeadcount')} /></Field>
        <Field label="Gross диспетчера, ₽/мес."><Input value={values.controlMonthlyGross} onChange={set('controlMonthlyGross')} /></Field>
        <Field label="Текущие техники, чел."><Input value={values.technicianHeadcount} onChange={set('technicianHeadcount')} /></Field>
        <Field label="Gross техника, ₽/мес."><Input value={values.technicianMonthlyGross} onChange={set('technicianMonthlyGross')} /></Field>
      </div>
      <Check checked={values.grossConfirm} onChange={set('grossConfirm')}>Подтверждаю: введённые в C03 зарплаты и значения выше — monthly gross, не неизвестный legacy fte_cost.</Check>
    </section>
    <section>
      <h3 className="font-semibold">Покупка и эксплуатация</h3>
      <div className="mt-2 grid gap-3 md:grid-cols-4">
        <Field label="Внедрение/интеграция gross, ₽"><Input value={values.implementationCost} onChange={set('implementationCost')} /></Field>
        <Field label="Сервис на робота gross, ₽/год"><Input value={values.annualService} onChange={set('annualService')} /></Field>
        <Field label="Гарантия, лет"><Input value={values.warrantyYears} onChange={set('warrantyYears')} /></Field>
        <Field label="Средняя мощность, W"><Input value={values.averagePowerW} onChange={set('averagePowerW')} /></Field>
        <Field label="Общеплощадочный CAPEX gross, ₽"><Input value={values.sharedSiteCapital} onChange={set('sharedSiteCapital')} /></Field>
        <Field label="Общеплощадочный OPEX gross, ₽/год"><Input value={values.sharedAnnualCost} onChange={set('sharedAnnualCost')} /></Field>
        <Field label="Горизонт, лет"><Input value={values.horizonYears} onChange={set('horizonYears')} /></Field>
        <Field label="Ставка дисконтирования, 0…1"><Input value={values.discountRate} onChange={set('discountRate')} step="0.01" /></Field>
      </div>
      <Check checked={values.currencyConfirm} onChange={set('currencyConfirm')}>Для этого сценария подтверждаю трактовку исходной цены организаторов как RUB. Это не подтверждает оферту, НДС или состав поставки.</Check>
      <Check checked={values.initialBatteryConfirm} onChange={set('initialBatteryConfirm')}>Подтверждаю для этого сценария: начальная батарея включена в цену робота.</Check>
      <Check checked={values.batteryServiceConfirm} onChange={set('batteryServiceConfirm')}>Подтверждаю для этого сценария: замены батареи включены в указанную стоимость сервиса.</Check>
    </section>
    <section>
      <h3 className="font-semibold">RaaS</h3>
      <div className="mt-2 grid gap-3 md:grid-cols-4">
        <Field label="Тариф gross, ₽/робот/мес."><Input value={values.raasMonthly} onChange={set('raasMonthly')} /></Field>
        <Field label="Срок договора, мес."><Input value={values.raasContractMonths} onChange={set('raasContractMonths')} /></Field>
        <Field label="Инфраструктура оплачивается"><select value={values.raasInfrastructureOwner} onChange={set('raasInfrastructureOwner')} className="w-full border rounded p-2"><option value="VENDOR">поставщиком</option><option value="CUSTOMER">заказчиком</option></select></Field>
      </div>
      <Check checked={values.raasScopeConfirm} onChange={set('raasScopeConfirm')}>Подтверждаю для сценария: RaaS-тариф включает оборудование, батареи, зарядку, обслуживание, ПО и интеграцию. Без договора это пользовательское допущение, не vendor fact.</Check>
    </section>
    <section>
      <h3 className="font-semibold">Версия сценария</h3>
      <div className="mt-2 grid gap-3 md:grid-cols-4">
        <Field label="Дата оценки"><input type="date" value={values.evaluationDate} onChange={set('evaluationDate')} className="w-full border rounded p-2" required /></Field>
        <Field label="Начало окна, секунд от 00:00"><Input value={values.startSeconds} onChange={set('startSeconds')} /></Field>
        <Field label="Часовой пояс"><input value={values.timezone} onChange={set('timezone')} className="w-full border rounded p-2" required /></Field>
      </div>
    </section>
    {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
    <button type="submit" disabled={busy} className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white disabled:bg-slate-300">{busy ? 'Сервер считает C13–C21…' : 'Рассчитать экономику и сохранить immutable run'}</button>
  </form>;
}

function Field({ label, children }) { return <label className="text-xs text-slate-700"><span className="mb-1 block">{label}</span>{children}</label>; }
function Input(props) { return <input type="number" min="0" step={props.step || 'any'} className="w-full border rounded p-2" required {...props} />; }
function Check({ checked, onChange, children }) { return <label className="mt-3 flex gap-2 text-xs text-amber-900"><input type="checkbox" checked={checked} onChange={onChange} />{children}</label>; }
