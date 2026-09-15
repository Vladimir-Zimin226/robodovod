import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

const fmt = (n) =>
  Math.abs(n) >= 1e6 ? `${(n / 1e6).toFixed(1)} млн ₽` : `${Math.round(n / 1e3)} тыс ₽`;

const OBJ_LABELS = {
  retail: 'Торговля: склад',
  airport: 'Логистика: аэропорт',
  clinic: 'Соц. сфера: медучреждение',
  other: 'Произвольный объект',
};

const PROC_LABELS = {
  transport: 'Транспортировка',
  palletizing: 'Паллетизация',
  cleaning: 'Уборка',
  delivery: 'Доставка',
};

function buildHeader(title, today) {
  return `
    <div style="border-bottom:3px solid #2563eb;padding-bottom:15px;margin-bottom:25px;">
      <div style="font-size:28px;font-weight:bold;color:#2563eb;">РобоМера</div>
      <div style="font-size:14px;color:#64748b;margin-top:4px;">AI-платформа предварительного ТЭО роботизации</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:6px;">${title} · ${today}</div>
    </div>`;
}

function buildSummaryCard(label, robot, isBest) {
  const border = isBest ? 'border:2px solid #2563eb;background:#eff6ff;' : 'border:1px solid #e2e8f0;background:#fff;';
  return `
    <div style="${border}border-radius:12px;padding:20px;margin-bottom:15px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <div style="font-size:11px;color:${isBest ? '#2563eb' : '#64748b'};text-transform:uppercase;letter-spacing:1px;font-weight:bold;">
          ${isBest ? '★ ' : ''}${label}
        </div>
        <div style="font-size:12px;color:#94a3b8;">Readiness: ${robot.readiness_score}/100</div>
      </div>
      <div style="font-size:18px;font-weight:bold;margin-bottom:8px;">
        ${robot.robot_name} × ${robot.quantity}
      </div>
      <div style="display:flex;gap:25px;margin-top:10px;">
        <div>
          <div style="font-size:9px;color:#64748b;">CAPEX</div>
          <div style="font-size:17px;font-weight:bold;">${fmt(robot.capex)}</div>
        </div>
        <div>
          <div style="font-size:9px;color:#64748b;">Экономия/год</div>
          <div style="font-size:17px;font-weight:bold;color:#16a34a;">${fmt(robot.savings_per_year)}</div>
        </div>
        <div>
          <div style="font-size:9px;color:#64748b;">Окупаемость</div>
          <div style="font-size:17px;font-weight:bold;color:#2563eb;">${robot.payback_years > 10 ? '> 10 лет' : robot.payback_years + ' лет'}</div>
        </div>
        <div>
          <div style="font-size:9px;color:#64748b;">NPV</div>
          <div style="font-size:17px;font-weight:bold;color:${robot.npv > 0 ? '#16a34a' : '#dc2626'};">${robot.npv > 0 ? '+' : ''}${fmt(robot.npv)}</div>
        </div>
        <div>
          <div style="font-size:9px;color:#64748b;">FTE</div>
          <div style="font-size:17px;font-weight:bold;">${robot.fte_displaced}</div>
        </div>
      </div>
      <div style="font-size:10px;color:#94a3b8;margin-top:8px;">${robot.price_note || ''}</div>
      <div style="font-size:10px;color:#64748b;margin-top:4px;">
        Роботы ${fmt(robot.capex_breakdown.robots)} → проект ${fmt(robot.capex_breakdown.total)} → TCO ${fmt(robot.tco)}
      </div>
    </div>`;
}

function buildScenarioTable(robot) {
  const sc = robot.scenarios || [];
  return `
    <div style="margin-bottom:15px;">
      <div style="font-size:11px;color:#64748b;font-weight:600;margin-bottom:6px;">Сценарии</div>
      <table style="width:100%;border-collapse:collapse;font-size:11px;">
        <tr style="background:#f1f5f9;">
          <th style="padding:6px 10px;text-align:left;border:1px solid #e2e8f0;">Показатель</th>
          ${sc.map((s) => `<th style="padding:6px 10px;text-align:center;border:1px solid #e2e8f0;">${s.label}</th>`).join('')}
        </tr>
        <tr>
          <td style="padding:5px 10px;border:1px solid #e2e8f0;">Роботов</td>
          ${sc.map((s) => `<td style="padding:5px 10px;text-align:center;border:1px solid #e2e8f0;"><b>${s.quantity}</b></td>`).join('')}
        </tr>
        <tr>
          <td style="padding:5px 10px;border:1px solid #e2e8f0;">CAPEX</td>
          ${sc.map((s) => `<td style="padding:5px 10px;text-align:center;border:1px solid #e2e8f0;">${fmt(s.capex)}</td>`).join('')}
        </tr>
        <tr>
          <td style="padding:5px 10px;border:1px solid #e2e8f0;">Экономия/год</td>
          ${sc.map((s) => `<td style="padding:5px 10px;text-align:center;border:1px solid #e2e8f0;">${fmt(s.savings_annual)}</td>`).join('')}
        </tr>
        <tr>
          <td style="padding:5px 10px;border:1px solid #e2e8f0;">Окупаемость</td>
          ${sc.map((s) => `<td style="padding:5px 10px;text-align:center;border:1px solid #e2e8f0;"><b>${s.payback_years > 10 ? '> 10 лет' : s.payback_years + ' лет'}</b></td>`).join('')}
        </tr>
        <tr>
          <td style="padding:5px 10px;border:1px solid #e2e8f0;">NPV</td>
          ${sc.map((s) => `<td style="padding:5px 10px;text-align:center;border:1px solid #e2e8f0;color:${s.npv > 0 ? '#16a34a' : '#dc2626'};"><b>${s.npv > 0 ? '+' : ''}${fmt(s.npv)}</b></td>`).join('')}
        </tr>
      </table>
    </div>`;
}

function buildWarningsList(warnings) {
  if (!warnings || warnings.length === 0) return '';
  return `
    <div style="margin-bottom:15px;">
      <div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;">Предупреждения и риски</div>
      <ul style="font-size:10px;color:#475569;line-height:1.7;padding-left:18px;margin:0;">
        ${warnings.slice(0, 8).map((w) => `<li>${w}</li>`).join('')}
      </ul>
    </div>`;
}

function buildRejectedTable(rejected) {
  if (!rejected || rejected.length === 0) return '';
  return `
    <div style="margin-bottom:15px;">
      <div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;">Отклонённые решения</div>
      <table style="width:100%;border-collapse:collapse;font-size:10px;">
        <tr style="background:#f1f5f9;">
          <th style="padding:5px 10px;text-align:left;border:1px solid #e2e8f0;">Решение</th>
          <th style="padding:5px 10px;text-align:left;border:1px solid #e2e8f0;">Причина</th>
        </tr>
        ${rejected.map((r) => `
          <tr>
            <td style="padding:5px 10px;border:1px solid #e2e8f0;">${r.robot_name}</td>
            <td style="padding:5px 10px;border:1px solid #e2e8f0;color:#64748b;">${r.reason}</td>
          </tr>
        `).join('')}
      </table>
    </div>`;
}

function buildAssumptionsTable(assumptions) {
  return `
    <div style="margin-bottom:15px;">
      <div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;">Допущения модели</div>
      <table style="width:100%;border-collapse:collapse;font-size:10px;">
        <tr style="background:#f1f5f9;">
          <th style="padding:4px 10px;text-align:left;border:1px solid #e2e8f0;">Параметр</th>
          <th style="padding:4px 10px;text-align:left;border:1px solid #e2e8f0;">Значение</th>
        </tr>
        <tr><td style="padding:4px 10px;border:1px solid #e2e8f0;">Горизонт</td><td style="padding:4px 10px;border:1px solid #e2e8f0;">${assumptions.horizon_years} лет</td></tr>
        <tr><td style="padding:4px 10px;border:1px solid #e2e8f0;">Утилизация (база)</td><td style="padding:4px 10px;border:1px solid #e2e8f0;">${assumptions.scenario_params?.base?.utilization || '—'}</td></tr>
        <tr><td style="padding:4px 10px;border:1px solid #e2e8f0;">Тариф электроэнергии</td><td style="padding:4px 10px;border:1px solid #e2e8f0;">${assumptions.electricity_tariff_rub_kwh} ₽/кВт·ч</td></tr>
        <tr><td style="padding:4px 10px;border:1px solid #e2e8f0;">Ротация бригад</td><td style="padding:4px 10px;border:1px solid #e2e8f0;">${assumptions.rotation_formula || '—'}</td></tr>
        <tr><td style="padding:4px 10px;border:1px solid #e2e8f0;">Ричтрак TCO</td><td style="padding:4px 10px;border:1px solid #e2e8f0;">~${Math.round((assumptions.forklift_annual_tco_rub || 700000) / 1000)} тыс ₽/год</td></tr>
        <tr><td style="padding:4px 10px;border:1px solid #e2e8f0;">Усталость (смены 10/12 ч)</td><td style="padding:4px 10px;border:1px solid #e2e8f0;">${assumptions.fatigue || '—'}</td></tr>
        <tr><td style="padding:4px 10px;border:1px solid #e2e8f0;">Курс USD</td><td style="padding:4px 10px;border:1px solid #e2e8f0;">90 ₽</td></tr>
      </table>
    </div>`;
}

function buildNextSteps() {
  return `
    <div style="margin-bottom:15px;">
      <div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;">Рекомендуемые следующие шаги</div>
      <div style="font-size:11px;line-height:1.9;color:#475569;">
        1. Запросить коммерческие предложения у 2-3 интеграторов<br>
        2. Провести натурный замер проходов и геометрии объекта<br>
        3. Замерить пиковые потоки в наиболее загруженную смену<br>
        4. Проверить Wi-Fi покрытие по маршрутам движения<br>
        5. Уточнить стоимость интеграции с WMS/MES<br>
        6. Рассмотреть поэтапное внедрение (частичная роботизация)
      </div>
    </div>`;
}

function buildFooter(assumptions) {
  return `
    <div style="border-top:2px solid #e2e8f0;padding-top:12px;margin-top:20px;">
      <div style="font-size:9px;color:#94a3b8;line-height:1.6;">
        <b>РобоМера</b> — AI-платформа предварительного ТЭО роботизации.<br>
        ${assumptions?.note || 'Предварительное ТЭО. Не заменяет инженерное обследование.'}<br>
        Все цены являются оценками (sourced estimate) и требуют подтверждения коммерческими предложениями.
      </div>
    </div>`;
}

const recommendedOf = (result) =>
  result?.recommendations?.find((item) => item.is_best === true) || null;

function buildCombinedCard(processes) {
  if (processes.length < 2) return '';

  const totalCapex = processes.reduce((s, p) => s + (recommendedOf(p.result)?.capex || 0), 0);
  const totalSavings = processes.reduce((s, p) => s + (recommendedOf(p.result)?.savings_per_year || 0), 0);
  const totalOpex = processes.reduce((s, p) => s + (recommendedOf(p.result)?.opex || 0), 0);
  const totalDisplaced = processes.reduce((s, p) => s + (recommendedOf(p.result)?.fte_displaced || 0), 0);
  const totalRobots = processes.reduce((s, p) => s + (recommendedOf(p.result)?.quantity || 0), 0);
  const net = totalSavings - totalOpex;
  const payback = net > 0 ? Math.round((totalCapex / net) * 10) / 10 : 99;
  const labels = processes.map((p) => p.label).join(' + ');

  return `
    <div style="background:linear-gradient(135deg,#2563eb,#1d4ed8);color:white;border-radius:12px;padding:22px;margin-bottom:20px;">
      <div style="font-size:13px;font-weight:bold;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:12px;">
        Комбинированное ТЭО
      </div>
      <div style="font-size:10px;color:#93c5fd;margin-bottom:10px;">${labels}</div>
      <div style="display:flex;gap:25px;">
        <div>
          <div style="font-size:9px;color:#93c5fd;">Роботов</div>
          <div style="font-size:18px;font-weight:bold;">${totalRobots}</div>
        </div>
        <div>
          <div style="font-size:9px;color:#93c5fd;">CAPEX</div>
          <div style="font-size:18px;font-weight:bold;">${fmt(totalCapex)}</div>
        </div>
        <div>
          <div style="font-size:9px;color:#93c5fd;">Экономия/год</div>
          <div style="font-size:18px;font-weight:bold;">${fmt(totalSavings)}</div>
        </div>
        <div>
          <div style="font-size:9px;color:#93c5fd;">Высвобождено</div>
          <div style="font-size:18px;font-weight:bold;">${Math.round(totalDisplaced)} FTE</div>
        </div>
        <div>
          <div style="font-size:9px;color:#93c5fd;">Окупаемость</div>
          <div style="font-size:18px;font-weight:bold;">${payback > 10 ? '> 10' : payback} лет</div>
        </div>
      </div>
      <div style="font-size:9px;color:#93c5fd;margin-top:10px;">
        Фиксированные затраты инфраструктуры могут частично пересекаться между процессами
      </div>
    </div>`;
}

export async function generateReport(result, userInput, extraProcesses = []) {
  const best = recommendedOf(result);
  if (!result || !best) {
    alert('Рекомендованный экономический вариант не назначен. PDF с ложной рекомендацией не формируется.');
    return;
  }
  const mb = result.manual_baseline;
  const dq = result.data_quality;
  const obj = OBJ_LABELS[userInput?.object_type] || '—';
  const proc = PROC_LABELS[userInput?.process_type] || '—';
  const today = new Date().toLocaleDateString('ru-RU');
  const horizon = best.horizon_years || userInput?.horizon_years || 5;
  const isPartial = userInput?.fleet_override && userInput.fleet_override < best.quantity;

  const processes = [
    { input: userInput, result, label: proc },
    ...extraProcesses,
  ];
  const hasMultiple = processes.length > 1;

  // ═══ PAGE 1 ═══
  const p1 = document.createElement('div');
  p1.style.cssText =
    'width:794px;min-height:1050px;background:#fff;padding:50px 60px;box-sizing:border-box;font-family:Arial,sans-serif;color:#1e293b;position:fixed;left:-9999px;top:0;';

  p1.innerHTML = `
    ${buildHeader(hasMultiple ? 'Комбинированное ТЭО' : 'Предварительное ТЭО', today)}

    <div style="display:flex;gap:15px;margin-bottom:20px;">
      <div style="flex:1;background:#f1f5f9;border-radius:8px;padding:12px;">
        <div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">Объект</div>
        <div style="font-size:14px;font-weight:600;margin-top:3px;">${obj}</div>
      </div>
      <div style="flex:1;background:#f1f5f9;border-radius:8px;padding:12px;">
        <div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">Процесс</div>
        <div style="font-size:14px;font-weight:600;margin-top:3px;">${proc}</div>
      </div>
      <div style="flex:1;background:#f1f5f9;border-radius:8px;padding:12px;">
        <div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">Детализация</div>
        <div style="font-size:14px;font-weight:600;margin-top:3px;color:${dq.level === 'Высокая' ? '#16a34a' : dq.level === 'Рабочая' ? '#2563eb' : '#d97706'};">${dq.level} · ${dq.completeness_pct}%</div>
      </div>
    </div>

    ${buildCombinedCard(processes)}

    ${buildSummaryCard(proc, best, true)}
    ${isPartial ? `<div style="font-size:10px;color:#d97706;margin:-10px 0 15px 20px;">Частичная роботизация: ${userInput.fleet_override} из расчётных ${best.quantity} роботов</div>` : ''}

    <div style="display:flex;gap:15px;margin-bottom:20px;">
      <div style="flex:1;border:1px solid #e2e8f0;border-radius:8px;padding:15px;">
        <div style="font-size:10px;color:#64748b;font-weight:600;margin-bottom:8px;">Лестница цены</div>
        <div style="font-size:12px;line-height:1.9;">
          <div>Роботы: <b>${fmt(best.capex_breakdown.robots)}</b></div>
          <div>Зарядки: <b>${fmt(best.capex_breakdown.chargers)}</b></div>
          <div>Интеграция: <b>${fmt(best.capex_breakdown.integration)}</b></div>
          <div>Инфраструктура: <b>${fmt(best.capex_breakdown.site_fixed)}</b></div>
          <div>Резерв: <b>${fmt(best.capex_breakdown.contingency)}</b></div>
          <div style="border-top:1px solid #e2e8f0;margin-top:4px;padding-top:4px;">Проект: <b>${fmt(best.capex_breakdown.total)}</b></div>
          <div>TCO (${horizon} лет): <b>${fmt(best.tco)}</b></div>
        </div>
      </div>
      <div style="flex:1;border:1px solid #e2e8f0;border-radius:8px;padding:15px;">
        <div style="font-size:10px;color:#64748b;font-weight:600;margin-bottom:8px;">Без роботизации</div>
        <div style="font-size:12px;line-height:1.9;">
          <div>Персонал: <b>${mb.manual_fte} FTE</b></div>
          <div>Ричтраки: <b>${mb.forklifts || 0} шт</b></div>
          <div>Стоимость/год: <b>${fmt(mb.total_cost_annual)}</b></div>
          <div>За ${horizon} лет: <b>${fmt(mb.total_horizon)}</b></div>
          <div style="border-top:1px solid #e2e8f0;margin-top:4px;padding-top:4px;">
            ₽/операция вручную: <b>${mb.cost_per_move} ₽</b>
          </div>
          <div>₽/операция роботом: <b style="color:#16a34a;">${best.cost_per_move} ₽</b></div>
        </div>
      </div>
    </div>

    ${buildScenarioTable(best)}

    ${hasMultiple ? extraProcesses.map((ep, i) => {
      const eb = recommendedOf(ep.result);
      if (!eb) return '';
      return buildSummaryCard(ep.label || `Процесс ${i + 2}`, eb, false);
    }).join('') : ''}
  `;

  // ═══ PAGE 2 ═══
  const p2 = document.createElement('div');
  p2.style.cssText =
    'width:794px;min-height:900px;background:#fff;padding:50px 60px;box-sizing:border-box;font-family:Arial,sans-serif;color:#1e293b;position:fixed;left:-9999px;top:0;';

  const allWarnings = [
    ...(best.warnings || []),
    ...extraProcesses.flatMap((ep) => recommendedOf(ep.result)?.warnings || []),
  ];

  const allRejected = [
    ...(result.rejected || []),
    ...extraProcesses.flatMap((ep) => ep.result?.rejected || []),
  ];

  p2.innerHTML = `
    <div style="border-bottom:2px solid #2563eb;padding-bottom:10px;margin-bottom:20px;">
      <div style="font-size:15px;font-weight:bold;color:#2563eb;">Детали расчёта и допущения</div>
    </div>

    ${buildRejectedTable(allRejected)}

    ${buildWarningsList(allWarnings)}

    ${buildAssumptionsTable(result.assumptions)}

    ${hasMultiple ? buildCombinedCard(processes) : ''}

    ${buildNextSteps()}

    ${buildFooter(result.assumptions)}
  `;

  // ═══ Рендер и захват ═══
  document.body.appendChild(p1);
  document.body.appendChild(p2);

  try {
    const canvas1 = await html2canvas(p1, { scale: 2, useCORS: true, logging: false });
    const canvas2 = await html2canvas(p2, { scale: 2, useCORS: true, logging: false });

    document.body.removeChild(p1);
    document.body.removeChild(p2);

    const pdf = new jsPDF('p', 'mm', 'a4');

    const img1 = canvas1.toDataURL('image/jpeg', 0.95);
    pdf.addImage(img1, 'JPEG', 0, 0, 210, 297);

    pdf.addPage();
    const img2 = canvas2.toDataURL('image/jpeg', 0.95);
    pdf.addImage(img2, 'JPEG', 0, 0, 210, 297);

    const filename = hasMultiple
      ? 'РобоМера_Комбинированное_ТЭО.pdf'
      : 'РобоМера_Предварительное_ТЭО.pdf';

    pdf.save(filename);
  } catch (err) {
    if (p1.parentNode) document.body.removeChild(p1);
    if (p2.parentNode) document.body.removeChild(p2);
    console.error('PDF generation error:', err);
    alert('Ошибка генерации PDF: ' + err.message);
  }
}
