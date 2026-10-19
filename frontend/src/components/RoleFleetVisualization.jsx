import { useState } from 'react';
import './RoleFleetVisualization.css';

const count = (value) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value || 0));

function assignments(report) {
  if (report?.kind) return report.roles.flatMap((role) => role.works
    .filter((work) => !work.safety_conditions || report.conditional_total.work_count > report.base_total.work_count)
    .map((work) => ({
    key: `${role.role_code}:${work.process_code}`, role: role.label, task: work.technical_task,
    fleet: work.fleet, demand: work.target_units_per_day, unit: work.unit,
    model: work.selected_model_name || 'Сценарный тип', safety: Boolean(work.safety_conditions),
  })));
  return (report?.roles || []).map((role) => {
    const selected = role.candidates.find((item) => item.position_id === role.selected_position_id);
    return { key: role.role_code, role: role.label, task: role.label, fleet: selected?.fleet || 0,
      demand: selected?.target_units_per_day, unit: selected?.unit, model: selected?.name || 'Робот не выбран', safety: false };
  });
}

export default function RoleFleetVisualization({ report }) {
  const items = assignments(report);
  const [selectedKey, setSelectedKey] = useState(items[0]?.key || '');
  const selected = items.find((item) => item.key === selectedKey) || items[0];
  if (!selected) return null;
  const total = report?.kind ? report.conditional_total.fleet : report.portfolio.selected_robot_allocations;
  return <section className="role-visual" aria-label="Схема парка по ролям">
    <div className="role-visual-heading"><div><p className="wr-kicker">ВИЗУАЛИЗАЦИЯ ПАРКА</p><h2>Работы и роботы на объекте</h2></div>
      <strong>{count(total)} роботов по назначениям</strong></div>
    <p>Выберите работу, чтобы увидеть её поток и парк. Геометрия условная: план объекта и маршруты не загружены. Числа взяты из этого расчёта.{report?.kind && report.conditional_total.work_count === report.base_total.work_count && report.roles.some((role) => role.works.some((work) => work.safety_conditions)) ? ' Работы с неподтверждённым допуском исключены из показанного парка.' : ''} Физический 3D-прогон недоступен: для выбранной работы нет подтверждённого маршрута и входов симулятора.</p>
    <div className="role-visual-layout"><div className="role-visual-list" aria-label="Назначения роботов">
      {items.map((item) => <button key={item.key} type="button" className={item.key === selected.key ? 'active' : ''}
        aria-pressed={item.key === selected.key} onClick={() => setSelectedKey(item.key)}>
        <span>{item.role}<small>{item.task}</small></span><strong>{item.fleet}</strong>
      </button>)}
    </div><div className="role-visual-scene"><svg viewBox="0 0 800 350" role="img" aria-label={`Условная схема работы ${selected.task}: ${selected.fleet} роботов`}>
      <defs><pattern id="role-visual-grid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M 36 0 L 0 0 0 36" fill="none" stroke="#43605a" strokeWidth="1" opacity=".35" /></pattern></defs>
      <rect width="800" height="350" rx="22" fill="#102428" /><rect width="800" height="350" rx="22" fill="url(#role-visual-grid)" />
      <path d="M 150 175 C 290 75 510 275 650 175" fill="none" stroke="#699381" strokeWidth="42" opacity=".2" />
      <path d="M 150 175 C 290 75 510 275 650 175" fill="none" stroke="#b2ed72" strokeWidth="5" strokeDasharray="14 12" />
      <circle cx="150" cy="175" r="55" fill="#294d3c" stroke="#9fdc71" strokeWidth="3" />
      <circle cx="650" cy="175" r="55" fill="#294d3c" stroke="#9fdc71" strokeWidth="3" />
      <text x="150" y="181" textAnchor="middle" fill="#eef9e6" fontSize="20">Задача</text>
      <text x="650" y="181" textAnchor="middle" fill="#eef9e6" fontSize="20">Результат</text>
      {selected.fleet > 0 && <g className="role-visual-marker"><rect x="364" y="137" width="72" height="72" rx="16" fill="#a9df68" stroke="#ecffc7" strokeWidth="3" />
        <circle cx="381" cy="213" r="9" fill="#1a3025" /><circle cx="419" cy="213" r="9" fill="#1a3025" />
        <text x="400" y="181" textAnchor="middle" fill="#17311c" fontWeight="800" fontSize="18">×{selected.fleet}</text></g>}
    </svg><div className="role-visual-facts"><strong>{selected.role}: {selected.task}</strong><span>{selected.model} · парк {selected.fleet}</span>
      <span>Роботизируемый объём: {selected.demand == null ? 'не рассчитан' : `${count(selected.demand)} ${selected.unit || ''}/сутки`}</span>
      {selected.safety && <span role="alert">Условная работа: допуск и безопасность не подтверждены.</span>}</div></div></div>
  </section>;
}
