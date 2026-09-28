"""Versioned investor view of verified saved data; never changes an export or run.

Charts only scale saved values onto the page. No financial engine runs here.
The existing embedded font keeps the PDF portable, searchable and deterministic.
"""
from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from calculation_contracts import semantic_digest

from calculation.evidence_export import EvidenceExportIntegrityError, EvidenceRunSnapshotV1, _verify_snapshots
from calculation.final_export import SENSITIVITY_LABELS, _comparison
from calculation.readable_report import (
    CMAP, PROCESS_LABELS, ROLE_LABELS, _capacity_source, _cashflows, _facts,
    _number, _obj, _pdf, _quantity, _text_width, _wrap,
)
from presentation import field as field_label
from simulation_artifacts import StoredSimulationEvidence

VERSION = "investor-presentation-v1"
DEPTHS = {"BASIC": "Базовый", "ADVANCED": "Углублённый", "FULL": "Полный"}
INK, GREEN, BLUE, AMBER = "0.05 0.14 0.16", "0.04 0.52 0.36", "0.14 0.39 0.72", "0.72 0.32 0.09"
MUTED, PALE, WHITE = "0.35 0.44 0.48", "0.94 0.97 0.96", "1 1 1"
MISSING = "Не рассчитано"


def decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def amount(value: Any, *, millions: bool = False) -> str:
    number = decimal(value)
    if number is None:
        return MISSING
    if millions:
        return (_number(number / 1_000_000, money=True) or MISSING) + " млн ₽"
    return (_number(number, money=True) or MISSING) + " ₽"


def metric(scenario: dict, key: str) -> dict:
    return _obj(_obj(scenario.get("metrics")).get(key))


def metric_number(scenario: dict, key: str) -> Decimal | None:
    item = metric(scenario, key)
    return decimal(item.get("value")) if item.get("status") == "COMPLETE" else None


def metric_text(scenario: dict, key: str, *, millions: bool = True) -> str:
    item = metric(scenario, key)
    if item.get("status") == "NOT_REACHED":
        return "За горизонт не достигнута"
    if item.get("status") in {"NOT_APPLICABLE", "N_A"}:
        return "Не применяется"
    value = metric_number(scenario, key)
    if value is None:
        return MISSING
    if item.get("unit") == "YEAR":
        return (_number(value) or MISSING) + " лет"
    if item.get("unit") == "PERCENT":
        return (_number(value) or MISSING) + " %"
    return amount(value, millions=millions)


class Deck:
    """Small vector layout engine. Coordinates use a top-left page origin."""
    def __init__(self, depth: str, date: str):
        self.depth, self.date = depth, date
        self.pages: list[list[str]] = []
        self.characters: set[str] = set()

    def rect(self, x, y, w, h, color=WHITE):
        self.pages[-1].append(f"{color} rg {x:.2f} {595-y-h:.2f} {w:.2f} {h:.2f} re f")

    def line(self, x1, y1, x2, y2, color=MUTED, width=1):
        self.pages[-1].append(f"{color} RG {width} w {x1:.2f} {595-y1:.2f} m {x2:.2f} {595-y2:.2f} l S")

    def text(self, value, x, y, size=10, color=INK):
        value = str(value)
        self.characters.update(value)
        encoded = ''.join(f"{CMAP.get(ord(c), CMAP[63])[0]:04X}" for c in value)
        self.pages[-1].append(f"{color} rg BT /F1 {size} Tf {x:.2f} {595-y-size:.2f} Td <{encoded}> Tj ET")

    def paragraph(self, value, x, y, width=762, size=10, color=INK):
        for row in _wrap(str(value), size, width):
            if y + size*1.45 > 548:
                self.page('Продолжение: пояснения')
                y = 139
            self.text(row, x, y, size, color)
            y += size * 1.45
        return y

    def page(self, title, subtitle=""):
        self.pages.append([])
        self.rect(0, 0, 842, 595, PALE)
        self.rect(0, 0, 842, 43, INK)
        self.text("РОБОДОВОД", 40, 13, 12, WHITE)
        depth = f"Глубина расчёта: {self.depth}"
        self.text(depth, 802-_text_width(depth, 9), 16, 9, WHITE)
        y = self.paragraph(title, 40, 61, size=22)
        if subtitle:
            self.paragraph(subtitle, 40, y+6, size=10, color=MUTED)
        self.rect(40, 115, 78, 3, GREEN)

    def card(self, x, y, label, value, note="", color=GREEN, width=180):
        self.rect(x, y, width, 108)
        self.rect(x, y, width, 4, color)
        self.paragraph(label, x+12, y+13, width-24, size=9, color=MUTED)
        size = 21
        while _text_width(str(value), size) > width-24 and size > 11:
            size -= 1
        self.paragraph(value, x+12, y+38, width-24, size=size, color=INK)
        if note:
            self.paragraph(note, x+12, y+77, width-24, size=8, color=MUTED)

    def table(self, headers, rows, x=40, y=139, widths=None, size=10):
        widths = widths or [762/len(headers)] * len(headers)
        total = sum(widths)
        self.rect(x, y, total, 29, INK)
        offset = x
        for header, width in zip(headers, widths):
            self.paragraph(header, offset+9, y+7, width-18, size=9, color=WHITE)
            offset += width
        y += 29
        for index, row in enumerate(rows):
            row_height = max(len(_wrap(str(value), size, width-18)) for value, width in zip(row, widths)) * size*1.45+16
            if y+row_height > 548:
                self.page('Продолжение: таблица')
                y = self.table(headers, [], x=x, y=139, widths=widths, size=size)
            self.rect(x, y, total, row_height, WHITE if index % 2 == 0 else "0.90 0.94 0.93")
            offset = x
            for value, width in zip(row, widths):
                self.paragraph(value, offset+9, y+8, width-18, size=size)
                offset += width
            y += row_height
        return y

    def bars(self, rows, x, y, width, height, *, money=True):
        """Signed horizontal bars with a visible zero and explicit missing data."""
        self.rect(x, y, width, height)
        numbers = [float(v) for _, v, _ in rows if v is not None]
        low, high = min([0, *numbers]), max([0, *numbers])
        if low == high:
            high = low+1
        left, right = x+155, x+width-100
        scale = (right-left)/(high-low)
        zero = left-low*scale
        self.line(zero, y+15, zero, y+height-16, MUTED, .8)
        row_height = min(40, (height-24)/max(1, len(rows)))
        for i, (label, value, color) in enumerate(rows):
            top = y+12+i*row_height
            self.paragraph(label, x+12, top+4, 137, size=9)
            if value is not None:
                endpoint = zero+float(value)*scale
                self.rect(min(zero, endpoint), top+4, max(1, abs(endpoint-zero)), min(18,row_height-9), color)
            display = amount(value, millions=True) if money else (_number(value) or MISSING)
            self.paragraph(display, right+8, top+4, 87, size=8, color=MUTED)

    def lines(self, series, x=40, y=148, width=762, height=220):
        self.rect(x, y, width, height)
        points = [(float(year), float(value)/1e6) for _, rows, _ in series for year,value in rows if value is not None]
        if not points:
            self.text("Нет сохранённых денежных потоков для графика", x+18, y+40, color=MUTED)
            return
        years = sorted({p[0] for p in points})
        lo, hi = min([0, *(p[1] for p in points)]), max([0, *(p[1] for p in points)])
        if hi == lo:
            hi = lo+1
        left, right, top, bottom = x+65, x+width-28, y+25, y+height-38
        px = lambda year: left+(float(year)-years[0])*(right-left)/max(1, years[-1]-years[0])
        py = lambda value: bottom-(float(value)/1e6-lo)*(bottom-top)/(hi-lo)
        for i in range(5):
            val = lo+(hi-lo)*i/4
            yy = bottom-(bottom-top)*i/4
            self.line(left, yy, right, yy, "0.82 0.87 0.86", .5)
            self.text(_number(val) or "0", x+8, yy-6, 8, MUTED)
        self.line(left, py(0), right, py(0), MUTED, 1)
        for year in years:
            if len(years) <= 12 or year in {years[0],years[-1]} or int(year) % 5 == 0:
                self.text(str(int(year)), px(year)-5, bottom+8, 8, MUTED)
        self.text("млн ₽", x+8, y+6, 8, MUTED)
        self.text("год", right-20, bottom+21, 8, MUTED)
        for _, rows, color in series:
            previous = None
            for year,value in sorted(rows):
                if value is None:
                    previous = None
                    continue
                point = (px(year),py(value))
                if previous:
                    self.line(*previous,*point,color,2.2)
                self.rect(point[0]-2,point[1]-2,4,4,color)
                previous = point

    def finish(self) -> bytes:
        count = len(self.pages)
        for i in range(count):
            current = self.pages[i]
            self.pages[i], self.pages[-1] = self.pages[-1], current
            self.text(f"Расчёт от {self.date} · предварительная оценка",40,570,8,MUTED)
            self.text(f"{i+1} / {count}",755,570,8,MUTED)
            self.pages[i], self.pages[-1] = self.pages[-1], self.pages[i]
        # Reuse the existing font package and Unicode map without changing its renderer.
        font_pdf = PdfReader(io.BytesIO(_pdf([(''.join(sorted(self.characters)), 'body')])))
        writer = PdfWriter()
        resources = font_pdf.pages[0]['/Resources'].clone(writer)
        for commands in self.pages:
            page = writer.add_blank_page(width=842,height=595)
            page[NameObject('/Resources')] = resources
            stream = DecodedStreamObject()
            stream.set_data('\n'.join(commands).encode('ascii'))
            page[NameObject('/Contents')] = writer._add_object(stream)
        writer.add_metadata({'/Title':'Рободовод — инвестиционная оценка роботизации', '/Author':'Рободовод / ZMNCRAFT', '/Subject':f'Глубина расчёта: {self.depth}', '/Creator':VERSION})
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()


def _scenario_view(scenario: dict) -> dict:
    if scenario.get('metrics'):
        return scenario
    facts = _facts(scenario)
    metrics = {'npv':facts.get('project_npv') or {}}
    financial = _obj(scenario.get('financial'))
    role_scope = _obj(scenario.get('report_facts')).get('schema_version') != 'calculation-report-facts-v1'
    if role_scope and financial.get('status') == 'COMPLETE':
        for key in ('simple_payback','discounted_payback'):
            metrics[key] = _obj(financial.get(key))
    if facts.get('project_capex_cashflow') is not None:
        metrics['capex'] = {'status':'COMPLETE','value':facts['project_capex_cashflow'],'unit':'RUB'}
    return {**scenario,'metrics':metrics,'annual_cashflows':_cashflows(scenario),
            'scope':'ROLE' if role_scope else 'PROJECT'}


def _input_value(key: str, value: Any) -> str:
    numeric = decimal(value)
    if numeric is None:
        return str(value) if value is not None else 'Не указано'
    if key == 'discount_rate':
        return (_number(numeric*100) or MISSING)+' %'
    if key == 'start_seconds_from_midnight':
        seconds = int(numeric)
        return f'{seconds//3600:02d}:{seconds%3600//60:02d}'
    unit = {'horizon_years':'лет','warranty_years':'лет','raas_contract_months':'мес.',
            'control_headcount':'чел.','technician_headcount':'чел.','average_power_w':'Вт',
            'manual_units_per_shift':'ед./чел./смену'}.get(key)
    if key.endswith('_gross'):
        return amount(numeric)
    return (_number(numeric) or MISSING)+(f' {unit}' if unit else '')


def _assumption_source(item: dict) -> str:
    source = str(item.get('source') or '')
    if source in {'USER','ASSUMPTION','ORGANIZER','FILE'}:
        source = 'Авторское допущение' if str(item.get('rationale') or '').startswith('Авторское') else {
            'USER':'Условия пользователя','ASSUMPTION':'Допущение','ORGANIZER':'Материалы организаторов','FILE':'Введено из файла'}[source]
    return (source or 'Допущение')+(f" · {item['published_on']}" if item.get('published_on') else '')


def _base(scenarios: list[dict], acquisition: str) -> dict:
    return next((s for s in scenarios if s.get('acquisition') == acquisition and s.get('uncertainty') == 'BASE'), {})


def _verdict(purchase: dict, raas: dict) -> str:
    values = [('Покупка',metric_number(purchase,'npv')),('Аренда',metric_number(raas,'npv'))]
    known = [(label,value) for label,value in values if value is not None]
    if not known:
        return 'Инвестиционный вывод пока недоступен: для него нужны сохранённые денежные расчёты.'
    parts = [f'{label}: NPV {amount(value,millions=True)}' for label,value in known]
    if all(value <= 0 for _,value in known):
        conclusion = 'Рассчитанные базовые варианты не показывают положительного дисконтированного эффекта.'
    else:
        conclusion = 'Есть вариант с положительным дисконтированным эффектом на введённых условиях.'
    return '; '.join(parts)+'. '+conclusion+' Перед инвестиционным решением подтвердите объект и предложение поставщика.'


def build_investor_report(run: EvidenceRunSnapshotV1, linked: EvidenceRunSnapshotV1 | None = None,
                          simulation: StoredSimulationEvidence | None = None) -> tuple[bytes,str]:
    digests = _verify_snapshots(run)
    source = _capacity_source(run,linked)
    if simulation is not None and (str(simulation.analysis_run_id) != run.run_id
            or str(simulation.project_id) != run.project_id
            or run.scenario_spec_snapshot != simulation.request.scenario_spec.model_dump(mode='json')
            or f"sha256:{run.checksums.get('scenario_spec')}" != simulation.scenario_spec_digest
            or semantic_digest(simulation.report) != simulation.report_digest
            or semantic_digest(simulation.request) != simulation.request_digest):
        raise EvidenceExportIntegrityError('simulation does not match investor report source')
    comparison = _comparison(run)
    result = run.result_snapshot
    inputs = _obj(run.input_snapshot.get('economics'))
    depth_code = inputs.get('calculation_depth')
    depth = DEPTHS.get(depth_code,'Не указана в сохранённом расчёте') if run.run_kind != 'CAPACITY_ANALYSIS' else 'Техническая оценка; экономика не рассчитана'
    deck = Deck(depth,run.finished_at.strftime('%d.%m.%Y'))
    process = _obj(_obj(source.get('input')).get('process'))
    capacity = _obj(_obj(_obj(source.get('result')).get('capacity')).get('value'))
    capacity_report = _obj(_obj(source.get('result')).get('capacity'))
    eligibility = run.diagnostics.get('constraint_eligibility') or _obj(result.get('c05')).get('eligibility')
    obstructed = eligibility == 'INELIGIBLE' or bool(capacity_report.get('blockers'))
    scenarios = [_scenario_view(s) for s in (comparison['scenarios'] if comparison else result.get('scenarios',[]))]
    purchase,raas = _base(scenarios,'PURCHASE'),_base(scenarios,'RAAS')
    role_scope = any(s.get('scope') == 'ROLE' for s in (purchase,raas))
    baseline = _obj(comparison.get('baseline')) if comparison else {}
    process_name = PROCESS_LABELS.get(process.get('process_code'),'Процесс не указан в сохранённых данных')
    if process.get('process_code') == 'warehouse_receiving_shipping':
        process_name = 'Перевозка подготовленных паллет'
    fleet = capacity.get('selected_fleet')
    labour = _obj(result.get('labour'))
    partial_note = ' · Представлены доступные разделы' if result.get('schema_version') == 'economics-partial-result-v1' and depth_code != 'BASIC' else ''
    deck.page('Роботизация: сценарии и экономика',process_name+partial_note)
    deck.card(40,137,'Расчётный парк',f'{fleet} роботов' if fleet is not None else MISSING,'Один процесс в одной зоне')
    deck.card(234,137,'Требуемый объём',_quantity(process.get('demand')),'Из сохранённого ввода')
    if run.run_kind == 'CAPACITY_ANALYSIS' or depth_code == 'BASIC' or not scenarios:
        deck.card(428,137,'Высвобождение труда',(_number(labour.get('total_released'))+' чел.') if decimal(labour.get('total_released')) is not None else MISSING,'Только занятость выбранных ролей',BLUE)
        deck.card(622,137,'Покрытие объёма',_quantity(capacity.get('coverage')),'Доля обеспеченной работы',GREEN)
    else:
        for x,label,scenario,color in [(428,'Покупка: базовый NPV',purchase,GREEN),(622,'Аренда: базовый NPV',raas,BLUE)]:
            npv = metric_number(scenario,'npv')
            deck.card(x,137,label,metric_text(scenario,'npv'),'Для выбранной роли процесса' if role_scope else 'Эффект против работы без роботов',color if npv is None or npv>=0 else AMBER)
    verdict = _verdict(purchase,raas)
    if role_scope:
        verdict += ' Частичный денежный расчёт относится к выбранной роли; общий эффект объекта здесь не оценён.'
    if obstructed:
        verdict += ' Сохранённые проверки выявили препятствия для применения; денежный эффект их не устраняет.'
    deck.paragraph(verdict,40,271,size=12)
    if run.versions.get('application') == 'production-economics-orchestrator-v1':
        deck.paragraph('Историческая версия содержит известную ошибку учёта затрат персонала. Для денежного вывода нужен новый расчёт.',40,348,size=12,color=AMBER)
    if scenarios:
        deck.text('Дисконтированный эффект базовых вариантов',40,380,14)
        deck.bars([('Покупка',metric_number(purchase,'npv'),GREEN),('Аренда',metric_number(raas,'npv'),BLUE)],40,411,762,121)
    else:
        deck.text('Как читать оценку',40,390,14)
        for x,label,note in [(40,'01 · Объём и парк','Что роботизируем и какую нагрузку закрываем'),(300,'02 · Деньги и варианты','Покупка и аренда на общих исходных условиях'),(560,'03 · Проверка условий','Какие допущения нужно подтвердить до сделки')]:
            deck.rect(x,421,242,94)
            deck.text(label,x+14,437,12,GREEN)
            deck.paragraph(note,x+14,463,212,10)

    deck.page('Объект, процесс и потребный парк','Расчёт охватывает выбранный процесс; общий персонал и другие зоны не суммируются автоматически.')
    demand = _obj(process.get('demand'))
    nominal,effective = _obj(capacity.get('nominal_capacity')),_obj(capacity.get('effective_capacity'))
    demand_value = decimal(demand.get('normalized_value',demand.get('value')))
    n_value,e_value = decimal(nominal.get('value')),decimal(effective.get('value'))
    comparable = demand.get('unit') == nominal.get('unit') == effective.get('unit') and demand_value is not None
    if comparable:
        deck.text(f"Объём и мощность · {demand.get('unit','').replace('m2/day','м²/день').replace('pallet/day','паллет/день')}",40,137,12)
        deck.bars([('Требуется',demand_value,AMBER),('Эффективная мощность',e_value,GREEN),('Номинальная мощность',n_value,BLUE)],40,163,762,138,money=False)
        y = 320
    else:
        y = 139
    schedule = _obj(process.get('schedule'))
    rows = [['Процесс',process_name],['Объём',_quantity(demand)],['Рекомендованный / выбранный парк',f"{_number(capacity.get('recommended_fleet')) or MISSING} / {_number(fleet) or MISSING}"],
            ['Номинальная / эффективная мощность',f'{_quantity(nominal)} / {_quantity(effective)}'],
            ['Покрытие / фактическая загрузка',f"{_quantity(capacity.get('coverage'))} / {_quantity(capacity.get('raw_load_ratio'))}"],
            ['График',f"{_number(_obj(schedule.get('shifts_per_day')).get('normalized_value')) or MISSING} смен × {_number(_obj(schedule.get('shift_hours')).get('normalized_value')) or MISSING} ч; {_number(_obj(schedule.get('days_per_year')).get('normalized_value')) or MISSING} дней/год"]]
    end = deck.table(['Параметр','Сохранённое значение'],rows,y=y,widths=[280,482],size=9)
    if process.get('process_code') == 'warehouse_receiving_shipping':
        deck.paragraph('Отбор коробок и упаковка не рассчитаны. Экономия относится к перевозке подготовленных паллет.',40,end+13,size=9,color=MUTED)
    elif process.get('process_code') == 'clinic_food':
        deck.paragraph('Приготовление пищи, лифты и санитарные режимы отдельно не моделируются. Требуется обследование клиники.',40,end+13,size=9,color=MUTED)

    deck.page('От ручной работы к роботизированному процессу','Схема показывает границы оцениваемой операции; расположение зон здесь условное.')
    stages = {
        'warehouse_receiving_shipping': [('Точка передачи','Подготовленная паллета'),('Перевозка','Роботы между точками передачи'),('Точка назначения','Передача паллеты персоналу')],
        'airport_terminal_cleaning': [('Рабочие зоны','Заданный объём уборки терминала'),('Уборка','Роботы проходят рабочие полосы'),('Контроль','Зарядка и обслуживание по условиям')],
        'clinic_food': [('Пищеблок','Подготовленные порции'),('Доставка','Роботы по маршрутам к отделениям'),('Отделения','Передача питания персоналу')],
    }.get(process.get('process_code'), [('Ввод','Объём и режим работы'),('Процесс','Расчётный парк роботов'),('Результат','Оценка мощности и экономики')])
    for i,(label,note) in enumerate(stages):
        x = 40+i*265
        deck.card(x,177,label,note,'В пределах выбранного процесса',GREEN if i==1 else BLUE,width=232)
        if i < 2:
            deck.line(x+238,231,x+258,231,GREEN,3)
            deck.line(x+251,224,x+258,231,GREEN,3)
            deck.line(x+251,238,x+258,231,GREEN,3)
    deck.paragraph('Карта объекта, реальные маршруты и условия взаимодействия требуют отдельной проверки. Схема объясняет операцию и не является инженерным планом.',40,332,size=12,color=MUTED)
    roles = result.get('roles') or []
    route = _obj(process.get('route_distance'))
    batch = _obj(process.get('explicit_batch'))
    if decimal(route.get('normalized_value')) is not None or decimal(batch.get('normalized_value')) is not None:
        deck.paragraph('Одностороннее плечо: '+(_number(route.get('normalized_value')) or 'Не указано')+' м; единиц груза за рейс: '+(_number(batch.get('normalized_value')) or 'Не указано')+'.',40,381,size=10,color=MUTED)
    if roles:
        deck.table(['Роль в оценке','Сотрудников','Месячная зарплата до удержаний'],[
            [ROLE_LABELS.get(r.get('role_code'),'Роль процесса'),_number(r.get('headcount')) or MISSING,amount(_obj(r.get('monthly_gross_salary')).get('value'))] for r in roles
        ],y=407,widths=[330,130,302],size=10)

    if scenarios:
        deck.page('Покупка и аренда: базовые условия','Суммы в млн ₽. NPV — дисконтированный эффект против варианта без роботов.'+(' Оценена выбранная роль процесса.' if role_scope else ''))
        rows = []
        for key,label in [('capex','Первоначальные вложения'),('opex_year_1','Годовые затраты · год 1'),('fot_year_1','Фонд оплаты труда · год 1'),('effect_year_1','Денежный эффект · год 1'),('effect_total','Эффект за горизонт до вложений'),('npv','NPV выбранной роли' if role_scope else 'NPV проекта'),('discounted_payback','Дисконтированная окупаемость')]:
            # The baseline stores NPV of its own flows; robotic scenarios store
            # incremental NPV. Do not compare these different bases in one row.
            rows.append([label,'База сравнения' if key == 'npv' else metric_text(baseline,key),metric_text(purchase,key),metric_text(raas,key)])
        end = deck.table(['Показатель','Без роботов','Покупка','Аренда'],rows,widths=[285,159,159,159],size=10)
        deck.paragraph('Годовые затраты и денежный эффект — разные показатели. Денежный поток учитывает дополнительные сохранённые условия модели. Нулевой срок при нулевых вложениях не означает положительный поток первого года. Отсутствующие значения не заменены нулями.',40,end+17,size=10,color=MUTED)

        if comparison:
            deck.page('Вложения и стоимость на горизонте','Суммы в млн ₽. ROI относится к первоначальным вложениям; для нулевых вложений показатель не применяется.')
            rows = [[label,metric_text(baseline,key),metric_text(purchase,key),metric_text(raas,key)] for key,label in [
                ('net_benefit','Чистый эффект после вложений'),('tco','Совокупные затраты на горизонте'),('roi','ROI на первоначальные вложения'),('simple_payback','Простая окупаемость')]]
            end = deck.table(['Показатель','Без роботов','Покупка','Аренда'],rows,widths=[285,159,159,159],size=10)
            deck.text('Годовые затраты первого года',40,end+21,13)
            deck.bars([('Без роботов',metric_number(baseline,'opex_year_1'),MUTED),('Покупка',metric_number(purchase,'opex_year_1'),GREEN),('Аренда',metric_number(raas,'opex_year_1'),BLUE)],40,end+53,762,145)
            deck.paragraph('ROI по модели: эффект за горизонт до вычета вложений / первоначальные вложения × 100 %. Сумма эффекта без дисконтирования показана отдельно от NPV.',40,end+210,size=9,color=MUTED)

        flows = [s.get('annual_cashflows',[]) for s in (purchase,raas)]
        years = sorted({f['year'] for fs in flows for f in fs if isinstance(f.get('year'),int)})
        if years:
            series = []
            for label,scenario,color in [('Покупка',purchase,GREEN),('Аренда',raas,BLUE)]:
                series.append((label,[(f['year'],decimal(f.get('effect'))) for f in scenario.get('annual_cashflows',[])],color))
            deck.page('Как меняется годовой денежный эффект','Разность годовых потоков против варианта без роботов. Первоначальные вложения в график не включены.'+(' Оценена выбранная роль.' if role_scope else ''))
            deck.lines(series)
            deck.text('Покупка',70,378,10,GREEN); deck.text('Аренда',190,378,10,BLUE)
            firsts = [(label,next(iter(s.get('annual_cashflows',[])),{})) for label,s in [('Покупка',purchase),('Аренда',raas)]]
            for i,(label,first) in enumerate(firsts):
                deck.card(40+i*390,412,f'{label}: эффект первого года',amount(first.get('effect'),millions=True),'Отрицательное значение означает ухудшение к базе',GREEN if i==0 else BLUE,width=372)
            # A paginated numerical companion is readable even over a long horizon.
            for offset in range(0,len(years),10):
                deck.page('Денежные потоки по годам','Все суммы в млн ₽; строки содержат только сохранённые значения. Полная точность — в XLSX и архиве.'+(' Оценена выбранная роль.' if role_scope else ''))
                rows = []
                for year in years[offset:offset+10]:
                    p = next((f for f in flows[0] if f.get('year')==year),{})
                    r = next((f for f in flows[1] if f.get('year')==year),{})
                    base_value = p.get('baseline') if p.get('baseline') is not None else r.get('baseline')
                    rows.append([str(year),amount(base_value,millions=True),amount(p.get('scenario'),millions=True),amount(r.get('scenario'),millions=True),amount(p.get('effect'),millions=True),amount(r.get('effect'),millions=True)])
                deck.table(['Год','Без роботов','Покупка','Аренда','Эффект покупки','Эффект аренды'],rows,widths=[45,143,143,143,144,144],size=9)

    if comparison and depth_code not in {'BASIC','ADVANCED'}:
        deck.page('Шесть вариантов: диапазон результата','Базовый профиль сценария отличается от базового уровня глубины. Суммы в млн ₽.')
        rows = []
        for s in scenarios:
            label = ('Покупка' if s.get('acquisition')=='PURCHASE' else 'Аренда')+' · '+{'PESSIMISTIC':'пессимистичный','BASE':'базовый','OPTIMISTIC':'оптимистичный'}.get(s.get('uncertainty'),'')
            rows.append([label,metric_text(s,'capex'),metric_text(s,'npv'),metric_text(s,'net_benefit'),metric_text(s,'discounted_payback')])
        end = deck.table(['Вариант','Вложения','NPV','Чистый эффект','Окупаемость'],rows,widths=[225,125,125,125,162],size=9)
        deck.paragraph('Профили отражают заданные изменения условий, а не вероятность исхода. Чистый эффект не дисконтирован; NPV учитывает ставку и время.',40,end+16,size=10,color=MUTED)

        for label,s,color in [('Покупка',purchase,GREEN),('Аренда',raas,BLUE)]:
            variants = _obj(_obj(comparison.get('sensitivity')).get('by_scenario')).get(s.get('scenario_id'),[])
            if not variants:
                continue
            deck.page(f'{label}: чувствительность результата','Изменение NPV при изменении одного условия на ±10%. Остальные условия соответствуют сохранённому варианту.')
            bars = [(SENSITIVITY_LABELS.get(v.get('parameter'),'Условие')+(' −10%' if v.get('direction')=='LOWER' else ' +10%'),decimal(v.get('delta_npv')) if v.get('status')=='COMPLETE' else None,color) for v in variants]
            deck.bars(bars,40,139,762,280)
            unavailable = [SENSITIVITY_LABELS.get(v.get('parameter'),'Условие') for v in variants if v.get('status') != 'COMPLETE']
            deck.paragraph('График показывает изменение, а не сам NPV. '+('Не рассчитаны варианты: '+', '.join(sorted(set(unavailable)))+'. Их технические или входные ограничения нужно уточнить.' if unavailable else 'Все показанные изменения взяты из сохранённого расчёта чувствительности.'),40,440,size=11,color=MUTED)

    if labour:
        deck.page('Труд: изменение занятости','Высвобождение — оценка работы выбранных ролей; оно не означает увольнение сотрудников.')
        deck.card(40,145,'Расчётное высвобождение',(_number(labour.get('total_released')) or MISSING)+' чел.','В пределах выбранного процесса',GREEN,width=372)
        deck.card(430,145,'Дополнительное управление',(_number(labour.get('total_additional_control')) or MISSING)+' чел.','Новая потребность в диспетчерах',BLUE,width=372)
        deck.paragraph('Для денежного решения дополните оценку условиями покупки или аренды, внедрением, эксплуатацией и горизонтом. При неполных данных стоимость и окупаемость остаются не рассчитанными.',40,286,size=12)
        branches = _obj(result.get('branches'))
        missing = [(label,branch) for key,label in [('purchase','Покупка'),('raas','Аренда')] if (branch:=_obj(branches.get(key))).get('required_fields')]
        y = 362
        for label,branch in missing:
            names = list(dict.fromkeys(field_label(str(key))[0] for key in branch['required_fields']))
            y = deck.paragraph(label+': уточните '+', '.join(names)+'.',40,y,size=10,color=MUTED)+14

    if inputs.get('schema_version') == 'economics-explicit-inputs-v6':
        staffing = _obj(result.get('staffing_preview'))
        work_share = _obj(result.get('work_share'))
        monetary = _obj(result.get('monetary_input_basis'))
        deck.page('Персонал и денежные базы проекта','Новые функции отделены от исходного штата; числа относятся к сохранённому сценарию.')
        rows = []
        for acquisition,label in [('PURCHASE','Покупка'),('RAAS','RaaS')]:
            item = _obj(staffing.get(acquisition))
            rows.append([label,_number(item.get('control_required')) or MISSING,
                _number(item.get('control_transferred')) or MISSING,
                _number(item.get('control_additional')) or MISSING,
                _number(item.get('technicians_required')) or MISSING,
                _number(item.get('technicians_billable')) or MISSING])
        y = deck.table(['Вариант','Пульт: нужно','Перевод','Найм','Техники','Оплачено'],rows,
                       widths=[145,130,110,110,130,137],size=9)
        share = work_share.get('fraction')
        y = deck.paragraph('Доля роботизируемой работы: '+(str(share) if share is not None else MISSING)+
            '. Остаточные операции: '+str(work_share.get('residual_operations') or 'неизвестно')+'.',40,y+20,size=10)
        implementation = _obj(monetary.get('implementation'))
        raas_basis = _obj(monetary.get('raas'))
        deck.paragraph('Цена робота: '+str(monetary.get('unit_price_gross_rub') or MISSING)+' ₽ gross; парк: '+str(monetary.get('fleet') if monetary.get('fleet') is not None else MISSING)+
            '. Внедрение: '+str(implementation.get('mode') or MISSING)+' / '+str(implementation.get('amount_gross_rub') or MISSING)+' ₽. RaaS: '+
            str(raas_basis.get('mode') or MISSING)+' / '+str(raas_basis.get('per_robot_month_gross_rub') or MISSING)+' ₽/робот/мес.',40,y+25,size=10)

    deck.page('Перед инвестиционным решением','Предварительная оценка помогает выбрать условия пилота. Она не подтверждает готовность объекта к внедрению.')
    risk_rows = [
        ['Объект и производительность','Замеры нагрузки, маршруты, сменность, рабочие покрытия, зарядку и связь.'],
        ['Персонал и источник экономии','Численность именно выбранной роли, оплату труда и возможность перераспределения работы.'],
        ['Цена и состав поставки','Коммерческое предложение, паспорт комплектации, сервис, батареи и интеграцию.'],
        ['Условия аренды','Тариф, срок договора, индексацию и распределение ответственности.'],
        ['Пилот','Проверку фактической мощности и безопасности на объекте перед масштабированием.'],
    ]
    if obstructed:
        risk_rows.insert(0,['Препятствия для применения','Закрыть ограничения сохранённой технической проверки до закупки. Положительный NPV не подтверждает допустимость внедрения.'])
    if any(w.get('code') == 'speed-safe-max-proxy' for w in capacity_report.get('warnings',[]) if isinstance(w,dict)):
        risk_rows.insert(0,['Рабочая скорость','Использован верхний безопасный предел как оптимистичное допущение. Подтвердить паспортную и фактическую скорость.'])
    end = deck.table(['Что проверить','Что получить'],risk_rows,widths=[248,514],size=10)
    if end+88 > 548:
        deck.page('Следующий шаг','Переход от предварительной оценки к проверке на объекте.')
        end=140
    deck.text('Следующий шаг',40,end+19,13,GREEN)
    deck.paragraph('Обследование → коммерческая проверка → пилот → решение о масштабе. Сроки и бюджет этих работ в отчёте не обещаны.',40,end+48,size=11)

    # Explicit assumptions, including basic/partial reports, without raw field/status codes.
    evidence = _obj(inputs.get('assumption_evidence'))
    assumption_rows = []
    for key,item in sorted(evidence.items()):
        if _obj(item).get('confirmed') is True:
            label = 'Цена робота' if key == 'purchase_price_override_gross' else field_label(key)[0]
            assumption_rows.append([label,_input_value(key,item.get('confirmed_value')),_assumption_source(item)])
    for offset in range(0,len(assumption_rows),7):
        deck.page('Приложение: подтверждённые допущения','Принятые пользователем условия сценария; подтверждение не делает их ценами или нормативами организаторов.')
        deck.table(['Условие','Значение','Источник'],assumption_rows[offset:offset+7],widths=[280,160,322],size=9)

    deck.page('Приложение: условия и источник расчёта','Числа читаются из сохранённого результата; формулы и ставки при экспорте не пересчитываются.')
    rows = [['Глубина расчёта',depth],['Дата сохранённого расчёта',run.finished_at.strftime('%d.%m.%Y')],
            ['Горизонт / ставка дисконтирования',f"{_number(inputs.get('horizon_years')) or 'Не указано'} лет / {(_number(decimal(inputs['discount_rate'])*100)+' %') if decimal(inputs.get('discount_rate')) is not None else 'Не указана'}"],
            ['Цена робота',amount(_obj(_obj(comparison).get('inputs')).get('price',{}).get('value')) if comparison else amount(inputs.get('purchase_price_override_gross'))],
            ['Тариф аренды на робота в месяц',amount(inputs.get('raas_monthly_per_robot_gross'))],
            ['Источники', 'Данные организаторов и введённые пользователем условия. Авторские допущения требуют проверки; источники каждого входа сохранены в архиве.']]
    if comparison:
        rows.insert(-1,['NPV собственных потоков без роботов',metric_text(baseline,'npv')+'; это база затрат, а не эффект роботизации.'])
    end = deck.table(['Параметр','Значение / пояснение'],rows,widths=[280,482],size=9)
    y = deck.paragraph('Источник цены: '+str(_obj(_obj(_obj(comparison).get('inputs')).get('price')).get('source_note') or inputs.get('purchase_price_source') or 'Источник цены не указан в сохранённом результате.'),40,end+14,size=9,color=MUTED)
    y = deck.paragraph(f'Идентификатор расчёта: {run.run_id}',40,y+10,size=8,color=MUTED)
    y = deck.paragraph(f"Контрольная сумма результата: {digests['result']}",40,y+6,size=8,color=MUTED)
    deck.paragraph(f'Версия представления: {VERSION}. Полная точность, трассировка и прежний PDF доступны в техническом архиве ZIP.',40,y+9,size=9,color=MUTED)
    if simulation:
        deck.page('Сохранённая симуляция: выполнение объёма','Результат модельного прогона на заданных условиях; геометрия условная, пригодность объекта подтверждается отдельно.')
        queue = simulation.report.queue
        deck.card(40,145,'Задач в измеряемом окне',str(queue.measurement_jobs),'Из сохранённой симуляции',BLUE,width=372)
        deck.card(430,145,'Завершено до конца окна',str(queue.completed_by_measurement_end),'К завершению измеряемого окна',GREEN,width=372)
        deck.paragraph('Симуляция связана с этим сохранённым расчётом. Модель очереди и движения не заменяет обследование, санитарную или эксплуатационную проверку.',40,288,size=12)
        deck.paragraph(f'Источник симуляции: {simulation.report_digest}',40,389,size=8,color=MUTED)
    return deck.finish(),digests['result'] or ''
