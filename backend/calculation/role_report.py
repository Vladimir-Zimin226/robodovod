"""A4 investment PDF rendered entirely from the shared role ReportViewModel."""

from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter

from calculation.readable_report import FONT, _pdf
from calculation.role_report_view import build_role_report_view


def _known(value: Any, suffix: str = "") -> str:
    if value is None:
        return "Нужны данные"
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return f"{value}{suffix}"
    if not number.is_finite():
        return "Нужны данные"
    pattern = ",.0f" if number == number.to_integral_value() else ",.2f"
    return f"{format(number, pattern).replace(',', ' ').replace('.', ',')}{suffix}"


FIT_LABELS = {"PASS": "пригодность по известным данным", "UNKNOWN": "паспортные данные не подтверждены",
              "FAIL": "не подходит по известным ограничениям"}
SIM_STATUS_LABELS = {"MODELED": "маршрут рассчитан", "CAPACITY_SHORTFALL": "мощности сценария недостаточно",
                     "NO_ROUTE": "проезд между зонами невозможен", "NEEDS_INPUT": "нужны параметры"}
SIM_FLAG_LABELS = {
    "SHARED_EDGE_QUEUE_NOT_MODELED": "очереди на общих участках не рассчитаны",
    "OTHER_SHARED_EDGES_NOT_MODELED": "прочие общие участки не рассчитаны",
    "CHARGING_NOT_MODELED": "зарядка не моделируется",
    "SAFETY_NOT_VERIFIED": "безопасность требует проверки",
    "ROBOT_TTH_NOT_VERIFIED": "характеристики робота не подтверждены",
    "SCENARIO_ROBOT_ONLY": "робот в маршруте сценарный",
    "DEMAND_SAMPLED_FOR_GEOMETRY": "поток ограничен только для показа маршрута",
    "CAPACITY_SHORTFALL": "производительности недостаточно",
    "QUEUE_UNSTABLE": "очередь растёт в течение расчётного периода",
    "NO_ROUTE": "проезд отсутствует",
}


def _cover_money(value: Any) -> str:
    if value is None:
        return "Нужны данные"
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return "Нужны данные"
    if abs(amount) >= 1_000_000:
        shown = (amount / Decimal(1_000_000)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return f"{shown:,.1f}".replace(",", " ").replace(".", ",") + " млн ₽"
    return f"{amount:,.0f}".replace(",", " ") + " ₽"


def _source_text(value: Any, fallback: str) -> str:
    if not value:
        return fallback
    text = str(value)
    for raw, readable in (
        ("SCENARIO_ASSUMPTION", "сценарное допущение"),
        ("SCENARIO_TYPE", "сценарный тип"),
        ("ASSUMPTION", "допущение"),
        ("manual units per shift / hours per shift, supplier rate and price unconfirmed",
         "ручная выработка и часы смены; ставка и цена не подтверждены"),
        ("rate and price unconfirmed", "ставка и цена не подтверждены"),
    ):
        text = text.replace(raw, readable)
    return text


def _snapshot_page(data_url: str, caption: str) -> bytes:
    if not data_url.startswith("data:image/png;base64,") or len(data_url) > 8_000_000:
        raise ValueError("invalid scene snapshot")
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
        image = Image.open(BytesIO(raw))
        if image.format != "PNG" or max(image.size) > 4096:
            raise ValueError("invalid scene snapshot")
        image.load()
    except (ValueError, OSError) as exc:
        raise ValueError("invalid scene snapshot") from exc
    canvas = Image.new("RGB", (1190, 1684), "white")
    pen = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(BytesIO(FONT), 27)
    pen.text((86, 75), caption, fill="#17333d", font=font)
    pen.text((86, 125), "Демонстрационная сцена; не подтверждает реальный объект.",
             fill="#536d70", font=ImageFont.truetype(BytesIO(FONT), 17))
    image = image.convert("RGB")
    scale = min(1018 / image.width, 1415 / image.height)
    image = image.resize((max(1, round(image.width * scale)),
                          max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    canvas.paste(image, ((1190 - image.width) // 2, 195))
    output = BytesIO()
    canvas.save(output, format="PDF", resolution=144)
    return output.getvalue()


def role_report_pdf(result: dict[str, Any], comparison: dict[str, Any] | None = None,
                    scene_snapshots: dict[str, str | None] | None = None) -> bytes:
    view = result.get("report_view") or build_role_report_view(result)
    purchase = view["economics"]["purchase"]
    lines: list[tuple[Any, str]] = [
        ("РОБОДОВОД", "brand"),
        ("Инвестиционная оценка", "title"),
        ("Сценарная оценка роботизации", "cover"),
        (view["object"], "subtitle"),
        (view["evidence_status"], "cover"),
        (f"Дата UTC: {view['date_utc']}. Каталог: {view['catalog_version']}.", "cover"),
        (f"Версия расчёта: {view['calculation_version']}. Версия отчёта: {view['schema_version']}.", "cover"),
        ("Ключевые показатели сценария", "subtitle"),
        (f"Парк: {view['fleet']} · эквивалент ставок: {view['fte_equivalent']}", "metric"),
        (f"CAPEX покупки: {_cover_money(purchase['capex_rub'])}", "metric"),
        (f"Годовой чистый эффект: {_cover_money(purchase['annual_net_rub'])}", "metric"),
        (f"NPV за {view['active_horizon_years']} лет: {_cover_money(purchase['npv_rub'])}", "metric"),
        ("Существенные ограничения", "subtitle"),
        *((risk, "cover") for risk in view["risks"][:2]),
        ("Управленческий вывод", "page"),
        (view["executive_conclusion"], "metric"),
        (f"Горизонт: {view['active_horizon_years']} лет. Ставка дисконтирования: {view['discount_rate']}.", "body"),
        (f"Парк: {view['fleet']}. Реализуемый эквивалент ставок: {view['fte_equivalent']}.", "body"),
        ("Работы, люди и назначенные модели", "section"),
        (("Работа", "Люди", "Объём/сут", "Парк"), "tablehead"),
    ]
    for work in view["works"]:
        lines.extend([
            ((work["role"], work["headcount"], f"{work['volume_per_day']} {work['unit']}", work["fleet"]), "tablerow"),
            (f"Задача: {work['task']}; модель: {work['model'] or 'сценарный тип / не выбрана'}; "
             f"ФОТ работодателя: {_known(work['salary_rub_month'])} ₽/мес.; "
             f"физическая проверка: {FIT_LABELS.get(work['physical_fit'], 'не подтверждена')}.", "detail"),
        ])
        if work["safety_conditions"]:
            lines.append((f"Допуск не подтверждён: {work['safety_conditions']}", "note"))
    lines.extend([("Симуляция: маршрут и корректировка парка", "section"),
        ("Геометрия демонстрационная; расстояния и узкие места не подтверждают реальный объект.", "note")])
    if not view["simulations"]:
        lines.append(("Маршрутная симуляция не включена; выработка остаётся сценарной.", "body"))
    for sim in view["simulations"]:
        lines.append((f"{sim['role']}. Маршрут: {SIM_STATUS_LABELS.get(sim['status'], 'требует проверки')}; с грузом {_known(sim['distance_loaded_m'], ' м')}; пустой ход {_known(sim['distance_empty_m'], ' м')}; ожидание {_known(sim['time_wait_s'], ' с')}.", "body"))
        limits = list(dict.fromkeys(SIM_FLAG_LABELS.get(flag, "требуется дополнительная проверка") for flag in sim["flags"]))
        lines.append((f"Цикл: {_known(sim['cycle_s'], ' с')}; парк после симуляции: {_known(sim['fleet_required'])}; ограничения: {', '.join(limits) or 'не выявлены'}.", "note"))
        if sim["shared_lane"]:
            lane = sim["shared_lane"]
            lines.append((f"Узкий участок: ожидание {lane['mean_wait_s']} с; проездов {lane['events']}; пропускная способность {lane['capacity_per_hour']} рейсов/ч.", "note"))
    if scene_snapshots:
        lines.append(("Снимки текущей 2D/3D демонстрационной сцены помещены в конце PDF.", "note"))
    else:
        lines.append(("Снимки текущей сцены не получены в этом сеансе.", "note"))
    lines.append(("Экономика: покупка и аренда", "section"))
    lines.append((("Вариант", "CAPEX, ₽", "NPV, ₽", "ROI, %"), "tablehead"))
    for mode, label in (("purchase", "Покупка"), ("raas", "Аренда")):
        money = view["economics"][mode]
        lines.extend([
            ((label, _known(money["capex_rub"]), _known(money["npv_rub"]),
              _known(money["roi_percent"])), "tablerow"),
            (f"{label}: CAPEX {_known(money['capex_rub'])} руб.; чистый годовой эффект {_known(money['annual_net_rub'])} руб.; NPV {_known(money['npv_rub'])} руб.; ROI {_known(money['roi_percent'], '%')}.", "body"),
            (f"{label}: окупаемость {_known(money['payback_years'], ' лет') if mode == 'purchase' else 'не применяется'}.", "body"),
        ])
        for horizon in money["horizons"]:
            lines.append((f"{label}, {horizon['years']} лет: NPV {_known(horizon['npv_rub'])} руб.; ROI {_known(horizon['roi_percent'], '%')}.", "body"))
    lines.append(("Разложение дисконтированного NPV покупки", "section"))
    waterfall = view["waterfall"]
    if not waterfall:
        lines.append(("Диаграмма недоступна: нужны цена и ФОТ.", "note"))
    else:
        extrema = [float(value) for row in waterfall for value in (row["start_rub"], row["end_rub"])]
        minimum, maximum = min(0, *extrema), max(0, *extrema)
        for row in waterfall:
            lines.append(((row["label"], f"{row['amount_rub']} ₽", row["start_rub"],
                           row["end_rub"], minimum, maximum), "waterfall"))
    lines.append(("Чувствительность к реализуемой доле ФОТ", "section"))
    lines.append((("Доля ФОТ", "NPV покупки", "NPV аренды", "Горизонт"), "tablehead"))
    for row in view["sensitivity"]:
        lines.append(((f"{float(row['labor_share']) * 100:.0f}%", _known(row["purchase_npv_rub"]),
                       _known(row["raas_npv_rub"]), f"{view['active_horizon_years']} лет"), "tablerow"))
    purchase_flows = view["economics"]["purchase"]["cashflows"]
    lines.extend([(95 + 36 * len(purchase_flows), "keep"),
                  ("Денежный поток: накопленный эффект, ₽", "section")])
    for mode, label in (("purchase", "Покупка"), ("raas", "Аренда")):
        cashflows = view["economics"][mode]["cashflows"]
        if mode == "raas":
            lines.append((65 + 36 * len(cashflows), "keep"))
            lines.append(("Денежный поток: продолжение", "section"))
        if not cashflows:
            lines.append((f"{label}: график недоступен, нужны цена или тариф.", "note"))
            continue
        lines.append((label, "metric"))
        maximum = max(abs(float(row["cumulative_rub"])) for row in cashflows) or 1
        for row in cashflows:
            lines.append(((f"Год {row['year']}", f"{row['cumulative_rub']} ₽",
                           abs(float(row["cumulative_rub"])) / maximum), "chartbar"))
    lines.append(("Сценарии, ограничения и источники", "section"))
    conditional = view["conditional"]
    if conditional:
        lines.append((f"Условный сценарий: парк {conditional['fleet']}; NPV покупки {_known(conditional['purchase_npv_rub'])} руб. {conditional['warning'] or ''}", "body"))
    if comparison is None:
        lines.append((view["what_if"], "note"))
    else:
        changed = comparison.get("report_view") or build_role_report_view(comparison)
        lines.append(("Временная ветка «Что если?»; каталог и базовый расчёт не изменены.", "note"))
        lines.append((("Показатель", "База", "Что если?", "Единицы"), "tablehead"))
        lines.append((("Парк", view["fleet"], changed["fleet"], "роботов"), "tablerow"))
        for mode, label in (("purchase", "Покупка"), ("raas", "Аренда")):
            for key, metric in (("capex_rub", "CAPEX"), ("npv_rub", "NPV"),
                                ("roi_percent", "ROI")):
                lines.append(((f"{label} {metric}", _known(view["economics"][mode][key]),
                    _known(changed["economics"][mode][key]), "%" if key == "roi_percent" else "руб."), "tablerow"))
        lines.append((f"Горизонт базы: {view['active_horizon_years']} лет; горизонт ветки: {changed['active_horizon_years']} лет.", "body"))
    lines.append(("Риски и проверки перед закупкой", "section"))
    lines.extend((risk, "body") for risk in view["risks"])
    lines.extend([("Источники и происхождение чисел", "section"),
                  ("Ниже приведены сохранённые основания для выработки, цены и допустимого груза каждой выбранной работы. Сценарные допущения требуют подтверждения до закупки.", "note")])
    for source in view["sources"]:
        heading = f"{source['role']} · позиция {_source_text(source['position_id'], 'не выбрана')}"
        detail = (f"Выработка {_source_text(source['rate'], 'неизвестна')} [{_source_text(source['rate_evidence_ref'], 'сценарная')}]; "
            f"цена {_source_text(source['price'], 'неизвестна')} [{_source_text(source['price_evidence_ref'], 'сценарная')}]; "
            f"груз {_source_text(source['payload_evidence_id'], 'нет подтверждения')}; "
            f"основание {_source_text(source['evidence'], 'сценарное допущение')}.")
        lines.append(((heading, detail), "sourceentry"))
    document = _pdf(lines)
    if not scene_snapshots:
        return document
    writer = PdfWriter()
    for page in PdfReader(BytesIO(document)).pages:
        writer.add_page(page)
    for key, caption in (("two_d_png", "Текущая сцена · план 2D"),
                         ("three_d_png", "Текущая сцена · WebGL 3D")):
        data_url = scene_snapshots.get(key)
        if data_url:
            for page in PdfReader(BytesIO(_snapshot_page(data_url, caption))).pages:
                writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
