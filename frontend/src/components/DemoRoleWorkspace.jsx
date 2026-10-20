import { useEffect, useRef, useState } from 'react';
import { buildShowcaseInput, SHOWCASE_PRESETS } from '../showcasePresets.js';

const API = import.meta.env.VITE_API_URL || '';
const money = (value) => value == null ? 'Не рассчитано' : `${Math.round(Number(value)).toLocaleString('ru-RU')} ₽`;

export default function DemoRoleWorkspace({ objectType, onPreview, onContinue }) {
  const [state, setState] = useState({ loading: true, input: null, report: null, error: '' });
  const onPreviewRef = useRef(onPreview);
  useEffect(() => { onPreviewRef.current = onPreview; }, [onPreview]);
  useEffect(() => {
    let active = true;
    const kind = SHOWCASE_PRESETS[objectType].input.kind;
    (async () => {
      const input = buildShowcaseInput(objectType);
      const previewResponse = await fetch(`${API}/api/v2/object-roles/${kind}/preview`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });
      if (!previewResponse.ok) {
        const body = await previewResponse.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : `Расчёт примера недоступен: HTTP ${previewResponse.status}`);
      }
      const report = await previewResponse.json();
      if (active) { setState({ loading: false, input, report, error: '' }); onPreviewRef.current(report, input); }
    })().catch((error) => { if (active) setState({ loading: false, input: null, report: null, error: error.message }); });
    return () => { active = false; };
  }, [objectType]);

  if (state.loading) return <section className="wr-panel" role="status">Загружаем и рассчитываем готовый пример…</section>;
  if (state.error) return <section className="wr-panel" role="alert">{state.error}</section>;
  const { input, report } = state;
  const preset = SHOWCASE_PRESETS[objectType];
  const role = input.roles[0];
  const work = role.works[0];
  const total = report.conditional_total;
  return <main className="wr-workspace demo-role-workspace" aria-label="Готовый пример">
    <header className="wr-hero"><div><p className="wr-kicker">ГОТОВЫЙ ПРИМЕР · ТОЛЬКО ПРОСМОТР · ВЕРСИЯ {preset.revision}</p>
      <h1>{work.technical_task}</h1><p>Один выбранный процесс. Все входные значения зафиксированы; расчёт выполнен сервером по активному каталогу.</p></div></header>
    <section className="wr-panel"><h2>Работа и исходные данные</h2>
      <dl className="demo-role-facts">
        <div><dt>Сотрудники этой роли</dt><dd>{role.headcount} человек</dd></div>
        <div><dt>Объём</dt><dd>{Number(work.daily_volume).toLocaleString('ru-RU')} {work.unit}/сутки</dd></div>
        <div><dt>Масса единицы</dt><dd>{work.task_payload_kg} кг · сценарное допущение</dd></div>
        <div><dt>Доля роботизации</dt><dd>{Math.round(Number(work.robotizable_share) * 100)}%</dd></div>
        <div><dt>Рабочий график</dt><dd>{input.general.shifts_per_day} смен × {input.general.hours_per_shift} ч · {input.general.days_per_year} дней/год</dd></div>
        <div><dt>Расходы работодателя</dt><dd>{money(role.monthly_employer_cost_rub)} на человека в месяц</dd></div>
        <div><dt>Сценарный парк</dt><dd>{total.fleet} роботов</dd></div>
        <div><dt>Предварительный NPV покупки</dt><dd>{money(total.purchase.npv_rub)}</dd></div>
      </dl>
      <p role="note">Учебный сценарий: модель, цена поставщика и техническая пригодность не подтверждены. Деньги показывают результат заданных допущений, а не закупочную рекомендацию.</p>
      {report.catalog_version !== preset.catalog_version_at_authoring && <p role="alert">С момента подготовки примера каталог изменился. Показанные суммы пересчитаны по текущей версии; исходные допущения примера не изменялись.</p>}
      <details><summary>Все допущения и источники</summary><p>{work.basis}</p>
        <p>Цена робота: {money(work.scenario_purchase_price_rub)} (сценарное допущение). Доступность: {input.general.robot_availability}; резерв: {input.general.fleet_reserve_share}; дисконт: {input.general.discount_rate}; горизонт: {input.general.horizon_years} лет.</p>
        <p>Маршрут: {work.simulation.speed_loaded_mps} м/с с грузом, {work.simulation.speed_empty_mps} м/с без груза; обслуживание {work.simulation.pickup_service_s} + {work.simulation.dropoff_service_s} с. Это физическая скорость сценария; ускорение просмотра её не меняет.</p>
      </details>
      <div className="wr-actions"><button type="button" className="wr-primary" onClick={onContinue}>Далее: роботы →</button></div>
    </section>
  </main>;
}
