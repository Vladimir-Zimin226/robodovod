import jsPDF from 'jspdf';

// ─── CDN шрифтов с поддержкой кириллицы ───
const FONT_REGULAR_URL =
  'https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/fonts/Roboto/Roboto-Regular.ttf';
const FONT_BOLD_URL =
  'https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/fonts/Roboto/Roboto-Medium.ttf';

// ─── Кэш base64-шрифтов в памяти ───
let fontRegularB64 = null;
let fontBoldB64 = null;
let fontRegularPromise = null;
let fontBoldPromise = null;

async function fetchBase64(url) {
  const resp = await fetch(url, { mode: 'cors' });
  if (!resp.ok) throw new Error(`Не удалось загрузить шрифт: HTTP ${resp.status}`);
  const buf = await resp.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    const end = Math.min(i + chunk, bytes.length);
    binary += String.fromCharCode.apply(null, bytes.subarray(i, end));
  }
  return btoa(binary);
}

async function ensureCyrillicFonts(doc) {
  // Regular
  if (!fontRegularB64) {
    if (!fontRegularPromise) {
      fontRegularPromise = fetchBase64(FONT_REGULAR_URL);
    }
    try {
      fontRegularB64 = await fontRegularPromise;
    } catch (error) {
      fontRegularPromise = null;
      throw new Error(
        'Не удалось загрузить шрифт для PDF. Проверьте интернет-соединение.',
        { cause: error }
      );
    }
  }
  doc.addFileToVFS('Roboto-Regular.ttf', fontRegularB64);
  doc.addFont('Roboto-Regular.ttf', 'Roboto', 'normal');

  // Bold (с fallback на Regular)
  if (!fontBoldB64) {
    if (!fontBoldPromise) {
      fontBoldPromise = fetchBase64(FONT_BOLD_URL);
    }
    try {
      fontBoldB64 = await fontBoldPromise;
    } catch {
      fontBoldPromise = null;
      fontBoldB64 = fontRegularB64;
    }
  }
  doc.addFileToVFS('Roboto-Bold.ttf', fontBoldB64);
  doc.addFont('Roboto-Bold.ttf', 'Roboto', 'bold');

  doc.setFont('Roboto', 'normal');
}

// ─── Форматирование ───
const money = (n) => {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)} млн ₽`;
  if (abs >= 1e3) return `${Math.round(n / 1e3)} тыс ₽`;
  return `${Math.round(n)} ₽`;
};

const num = (n, digits = 0) => {
  if (n == null || isNaN(n)) return '—';
  return Number(n).toFixed(digits);
};

const PROCESS_LABEL = {
  transport: 'Транспортировка',
  palletizing: 'Паллетизация',
  cleaning: 'Уборка',
  delivery: 'Доставка',
};

// ─── Главная функция ───
export async function generateZonalReport(result, userInput) {
  if (!result || result.mode !== 'zonal' || !result.combined) {
    throw new Error('Нет данных для формирования отчёта');
  }

  const c = result.combined;
  const h = c.horizon_years || 5;
  const now = new Date();
  const dateStr = now.toLocaleDateString('ru-RU');
  const timeStr = now.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

  // ─── Подключаем кириллический шрифт ───
  await ensureCyrillicFonts(doc);

  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 15;
  const contentW = pageW - margin * 2;

  let y = margin;

  // ═══════════════════════════════════════════════════════════
  // Хелперы
  // ═══════════════════════════════════════════════════════════
  const ensureSpace = (needed) => {
    if (y + needed > pageH - margin) {
      doc.addPage();
      y = margin;
      return true;
    }
    return false;
  };

  const h1 = (text) => {
    ensureSpace(12);
    doc.setFont('Roboto', 'bold');
    doc.setFontSize(15);
    doc.setTextColor(20, 30, 45);
    doc.text(text, margin, y);
    y += 7;
    doc.setDrawColor(40, 90, 200);
    doc.setLineWidth(0.6);
    doc.line(margin, y, margin + contentW, y);
    y += 5;
  };

  const h3 = (text) => {
    ensureSpace(7);
    doc.setFont('Roboto', 'bold');
    doc.setFontSize(10.5);
    doc.setTextColor(50, 60, 80);
    doc.text(text, margin, y);
    y += 5;
  };

  const kv = (key, value) => {
    ensureSpace(6);
    doc.setFont('Roboto', 'normal');
    doc.setFontSize(9.5);
    doc.setTextColor(110, 120, 135);
    doc.text(key, margin, y);
    doc.setFont('Roboto', 'bold');
    doc.setTextColor(30, 40, 60);
    doc.text(String(value), margin + contentW, y, { align: 'right' });
    y += 5;
  };

  const paragraph = (text, opts = {}) => {
    doc.setFont('Roboto', opts.bold ? 'bold' : 'normal');
    doc.setFontSize(opts.size || 9);
    doc.setTextColor(110, 120, 135);
    const lines = doc.splitTextToSize(text, contentW);
    ensureSpace(lines.length * 4.5);
    doc.text(lines, margin, y);
    y += lines.length * 4.5;
  };

  const divider = () => {
    ensureSpace(4);
    doc.setDrawColor(220, 225, 230);
    doc.setLineWidth(0.2);
    doc.line(margin, y, margin + contentW, y);
    y += 4;
  };

  const gap = (n = 4) => {
    y += n;
  };

  // ═══════════════════════════════════════════════════════════
  // Титул
  // ═══════════════════════════════════════════════════════════
  doc.setFillColor(30, 64, 175);
  doc.rect(0, 0, pageW, 30, 'F');
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(18);
  doc.setTextColor(255, 255, 255);
  doc.text('РобоМера', margin, 14);
  doc.setFont('Roboto', 'normal');
  doc.setFontSize(10);
  doc.text('Предварительное ТЭО роботизации · Зональный расчёт', margin, 21);
  doc.setFontSize(8.5);
  doc.text(`${dateStr} · ${timeStr}`, pageW - margin, 21, { align: 'right' });

  y = 40;

  // ═══════════════════════════════════════════════════════════
  // 1. Параметры проекта
  // ═══════════════════════════════════════════════════════════
  h1('Параметры проекта');

  kv('Тип объекта', userInput?.object_type || '—');
  kv('Режим расчёта', 'Зональный');
  kv('Количество зон', c.zones_count);
  kv('Горизонт расчёта', `${h} лет`);
  if (userInput?.fte_cost_rub) {
    const monthly = Math.round(userInput.fte_cost_rub / 15.624);
    kv(
      'Полная стоимость FTE',
      `${monthly.toLocaleString('ru-RU')} ₽/мес · ${money(userInput.fte_cost_rub)}/год`
    );
  }
  if (userInput?.discount_rate) {
    kv('Ставка дисконтирования', `${Math.round(userInput.discount_rate * 100)}%`);
  }
  if (userInput?.operating_days) {
    kv('Рабочих дней в году', userInput.operating_days);
  }

  gap(6);

  // ═══════════════════════════════════════════════════════════
  // 2. Комбинированная сводка
  // ═══════════════════════════════════════════════════════════
  h1('Комбинированная сводка');

  ensureSpace(40);
  doc.setFillColor(240, 245, 252);
  doc.roundedRect(margin, y, contentW, 38, 2, 2, 'F');
  const innerY = y + 6;

  doc.setFont('Roboto', 'bold');
  doc.setFontSize(22);
  doc.setTextColor(30, 64, 175);
  doc.text(
    `${c.combined_payback_years > 99 ? '> 10' : num(c.combined_payback_years, 1)} лет`,
    margin + contentW / 2,
    innerY + 4,
    { align: 'center' }
  );
  doc.setFontSize(9);
  doc.setFont('Roboto', 'normal');
  doc.setTextColor(110, 120, 135);
  doc.text('комбинированная окупаемость', margin + contentW / 2, innerY + 10, {
    align: 'center',
  });

  const cols = 4;
  const colW = contentW / cols;
  const metrics = [
    ['Роботов всего', `${c.total_robots} шт`],
    ['CAPEX проекта', money(c.total_capex)],
    ['Экономия/год', money(c.total_savings_annual)],
    ['Высвобождено FTE', `${num(c.total_released, 1)}`],
  ];
  metrics.forEach(([label, value], i) => {
    const cx = margin + colW * i + colW / 2;
    doc.setFont('Roboto', 'bold');
    doc.setFontSize(13);
    doc.setTextColor(30, 40, 60);
    doc.text(String(value), cx, innerY + 22, { align: 'center' });
    doc.setFont('Roboto', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(110, 120, 135);
    doc.text(label, cx, innerY + 28, { align: 'center' });
  });

  y += 42;

  h3('Финансовые показатели');
  kv('CAPEX', money(c.total_capex));
  kv('OPEX в год', money(c.total_opex_annual));
  kv('Экономия в год', money(c.total_savings_annual));
  kv('Чистая экономия в год', money(c.total_net_annual));
  kv(`NPV за ${h} лет`, money(c.total_npv));
  kv(`TCO за ${h} лет`, money(c.total_tco));
  kv('Warehouse-фикс (учтён 1×)', money(c.warehouse_fixed_rub));
  kv('Потенциал замены', `${num(c.total_displaced, 1)} FTE`);

  if (c.best_zone_id) {
    kv(
      'Лучшая зона по окупаемости',
      `${c.best_zone_id} (${num(c.best_zone_payback, 1)} лет)`
    );
  }

  gap(6);

  // ═══════════════════════════════════════════════════════════
  // 3. Разбивка по зонам
  // ═══════════════════════════════════════════════════════════
  doc.addPage();
  y = margin;

  h1('Разбивка по зонам');

  result.zones.forEach((z, idx) => {
    const best = z.recommendations.find((r) => r.robot_id === z.best_robot_id);

    ensureSpace(50);

    // Заголовок зоны
    doc.setFillColor(245, 247, 252);
    doc.roundedRect(margin, y - 4, contentW, 12, 1.5, 1.5, 'F');
    doc.setFont('Roboto', 'bold');
    doc.setFontSize(11);
    doc.setTextColor(30, 64, 175);
    doc.text(
      `Зона ${idx + 1}. ${z.zone_name || z.zone_id}`,
      margin + 3,
      y + 3.5
    );
    doc.setFontSize(8);
    doc.setFont('Roboto', 'normal');
    doc.setTextColor(110, 120, 135);
    doc.text(
      `${PROCESS_LABEL[z.process_type] || z.process_type} · ${z.shifts_count} см × ${z.shift_hours} ч`,
      margin + contentW - 3,
      y + 3.5,
      { align: 'right' }
    );
    y += 14;

    // Параметры зоны
    h3('Параметры зоны');
    if (z.volume_per_day) kv('Объём в сутки', `${z.volume_per_day}`);
    if (z.area_m2) kv('Площадь', `${z.area_m2} м²`);
    if (z.staff_headcount) kv('Штат в зоне', `${z.staff_headcount} чел`);
    if (z.cargo_type) kv('Тип груза', z.cargo_type);

    gap(3);

    // Рекомендация
    if (best) {
      h3('Рекомендуемое решение');
      doc.setFont('Roboto', 'bold');
      doc.setFontSize(10);
      doc.setTextColor(30, 40, 60);
      doc.text(`${best.robot_name} × ${best.quantity}`, margin, y);
      y += 5;
      doc.setFont('Roboto', 'normal');
      doc.setFontSize(8.5);
      doc.setTextColor(110, 120, 135);
      doc.text(`Readiness ${best.readiness_score}/100`, margin, y);
      y += 5;

      kv('CAPEX', money(best.capex));
      kv('OPEX в год', money(best.opex));
      kv('Экономия в год', money(best.savings_per_year));
      kv(
        'Окупаемость',
        best.payback_years > best.horizon_years
          ? `> ${best.horizon_years} лет`
          : `${num(best.payback_years, 1)} лет`
      );
      kv(`NPV за ${best.horizon_years} лет`, money(best.npv));
      kv(`TCO за ${best.horizon_years} лет`, money(best.tco));

      // Раскладка по персоналу
      const sb = best.staff_breakdown;
      if (sb && sb.slider_enabled) {
        gap(2);
        h3('Раскладка по персоналу');
        if (sb.staff_requested != null) {
          kv('Хотите заменить', `${sb.staff_requested} чел`);
        }
        kv('Робот может заменить', `${num(sb.staff_replaceable, 1)} FTE`);
        if (sb.is_clamped) {
          kv('Применено к расчёту', `${num(sb.staff_applied, 0)} чел`);
        }
        kv('Останется на пульте', `${num(sb.staff_on_pult, 1)} FTE`);
        kv('Реально высвободится', `${num(sb.staff_released, 1)} FTE`);
        if (sb.pult_shortage > 0) {
          kv(
            'Не хватает операторов для пульта',
            `${num(sb.pult_shortage, 0)} FTE`
          );
        }
      }

      // Альтернативы
      if (z.recommendations.length > 1) {
        gap(3);
        h3('Альтернативные решения');
        z.recommendations.slice(1, 4).forEach((r) => {
          ensureSpace(5);
          doc.setFont('Roboto', 'normal');
          doc.setFontSize(9);
          doc.setTextColor(50, 60, 80);
          doc.text(`${r.robot_name} × ${r.quantity}`, margin, y);
          doc.setTextColor(110, 120, 135);
          doc.text(
            `${
              r.payback_years > 10 ? '> 10' : num(r.payback_years, 1)
            } лет · ${money(r.capex)}`,
            margin + contentW,
            y,
            { align: 'right' }
          );
          y += 5;
        });
      }

      // Warnings
      const warns = (best.warnings || [])
        .filter(
          (w) =>
            !w.includes('Цена - оценка') &&
            !w.includes('Предварительное ТЭО') &&
            !w.includes('roi_pct')
        )
        .slice(0, 3);
      if (warns.length > 0) {
        gap(3);
        h3('Замечания');
        warns.forEach((w) => {
          paragraph(`• ${w}`, { size: 8.5 });
        });
      }
    } else {
      paragraph('Не подобрано ни одного робота для этой зоны.', {
        size: 9,
      });
      if (z.rejected.length > 0) {
        z.rejected.slice(0, 3).forEach((r) => {
          paragraph(`• ${r.reason}`, { size: 8 });
        });
      }
    }

    // Разделитель между зонами
    if (idx < result.zones.length - 1) {
      gap(6);
      divider();
      gap(4);
    }
  });

  // ═══════════════════════════════════════════════════════════
  // 4. Допущения и дисклеймер
  // ═══════════════════════════════════════════════════════════
  doc.addPage();
  y = margin;

  h1('Допущения модели');

  const assumptions = result.assumptions || {};
  const orderedKeys = [
    ['horizon_years', 'Горизонт расчёта'],
    ['labor_inflation', 'Инфляция ФОТ'],
    ['opex_inflation', 'Инфляция OPEX'],
    ['fully_loaded_mult', 'Полная стоимость FTE (множитель)'],
    ['target_fleet_utilization', 'Целевая загрузка парка'],
    ['cell_design_efficiency', 'Эффективность ячейки паллетизации'],
    ['min_area_per_robot_m2', 'Минимум площади на робота'],
    ['residual_share_default', 'Остаточная стоимость по умолчанию'],
  ];
  orderedKeys.forEach(([key, label]) => {
    if (assumptions[key] != null) {
      kv(label, String(assumptions[key]));
    }
  });

  gap(4);
  h3('Заметки');
  [
    assumptions.fully_loaded_note,
    assumptions.cell_efficiency_note,
    assumptions.fleet_sizing_note,
    assumptions.site_fixed_split_note,
    assumptions.zonal_mode_note,
    assumptions.savings_note,
    assumptions.roi_note,
    assumptions.note,
  ]
    .filter(Boolean)
    .forEach((note) => paragraph(`• ${note}`, { size: 8 }));

  gap(6);
  doc.setDrawColor(220, 225, 230);
  doc.line(margin, y, margin + contentW, y);
  y += 5;
  doc.setFont('Roboto', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(150, 155, 165);
  const disclaimer =
    'Отчёт носит характер предварительного технико-экономического обоснования. ' +
    'Цены — оценки (sourced estimate), не являются офертой. ' +
    'Не заменяет инженерное обследование и коммерческое предложение интегратора.';
  const lines = doc.splitTextToSize(disclaimer, contentW);
  doc.text(lines, margin, y);

  // ═══════════════════════════════════════════════════════════
  // Футер на всех страницах
  // ═══════════════════════════════════════════════════════════
  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFont('Roboto', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(170, 175, 185);
    doc.text(`РобоМера · Зональное ТЭО · ${dateStr}`, margin, pageH - 6);
    doc.text(`Стр. ${i} / ${totalPages}`, pageW - margin, pageH - 6, {
      align: 'right',
    });
  }

  // ═══════════════════════════════════════════════════════════
  // Сохранение
  // ═══════════════════════════════════════════════════════════
  const fileName = `RoboMera_Zonal_${now.toISOString().slice(0, 10)}.pdf`;
  doc.save(fileName);
}
