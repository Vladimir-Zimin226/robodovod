"""A standalone Russian report rendered only from verified immutable snapshots.

The embedded DejaVu font and its cmap keep Cyrillic text searchable without a
runtime font package or a browser-side calculation step.
"""

from __future__ import annotations

import io
import json
import zlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from calculation.evidence_export import EvidenceExportIntegrityError, EvidenceRunSnapshotV1, _verify_snapshots
from presentation import VERSION as PRESENTATION_VERSION, field as presentation_field, humanize


ASSETS = Path(__file__).with_name("assets")
FONT = (ASSETS / "DejaVuSans.ttf").read_bytes()
CMAP = {int(code): tuple(metrics) for code, metrics in json.loads(
    (ASSETS / "dejavu-cmap-v1.json").read_text(encoding="utf-8")
).items()}

UNKNOWN = "нет данных для оценки"
PROCESS_LABELS = {
    "warehouse_receiving_shipping": "Приёмка и отгрузка",
    "warehouse_storage": "Хранение",
    "warehouse_picking": "Комплектация",
    "warehouse_palletizing": "Паллетизация",
    "warehouse_cleaning": "Уборка склада",
    "warehouse_inventory": "Инвентаризация",
    "airport_baggage": "Обработка багажа",
    "airport_catering": "Бортовое питание",
    "airport_fuelling": "Заправка",
    "airport_internal_logistics": "Внутренняя логистика аэропорта",
    "airport_terminal_cleaning": "Уборка терминала",
    "airport_apron_cleaning": "Уборка перрона",
    "airport_waste": "Вывоз отходов",
    "airport_inspection": "Инспекция",
    "airport_passenger_assistance": "Помощь пассажирам",
    "airport_ground_service": "Наземное обслуживание",
    "clinic_food": "Доставка питания",
    "clinic_linen": "Транспорт белья",
    "clinic_medicines": "Доставка медикаментов",
    "clinic_biomaterials": "Доставка биоматериалов",
    "clinic_sterile_sets": "Стерильные наборы",
    "clinic_consumables": "Расходные материалы",
    "clinic_waste_a": "Отходы класса А",
    "clinic_waste_b": "Отходы класса Б",
    "clinic_results": "Доставка результатов",
    "clinic_cleaning": "Уборка клиники",
    "clinic_inventory": "Инвентаризация клиники",
    "clinic_safety_requirements": "Требования безопасности",
}
ROLE_LABELS = {
    "forklift_driver": "Водитель погрузчика", "loader": "Грузчик",
    "storekeeper": "Кладовщик", "picker": "Комплектовщик",
    "sorter": "Сортировщик", "packer": "Упаковщик",
    "cleaner": "Уборщик", "inventory_worker": "Сотрудник инвентаризации",
    "control_operator": "Оператор управления", "tech_support": "Технический специалист",
    "baggage_handler": "Сотрудник обработки багажа",
    "trolley_operator": "Оператор тележки",
    "special_equipment_driver": "Водитель спецтехники",
    "terminal_cleaner": "Уборщик терминала",
    "perron_cleaner": "Уборщик перрона",
    "runway_inspector": "Инспектор ВПП",
    "security_guard": "Сотрудник охраны",
    "passenger_assistant": "Помощник пассажиров",
    "courier": "Курьер",
    "ramp_worker": "Сотрудник перрона",
    "ground_support_worker": "Сотрудник наземного обслуживания",
    "catering_worker": "Сотрудник пищеблока",
    "laundry_worker": "Сотрудник прачечной",
    "sanitary": "Санитар",
    "porter": "Транспортировщик",
    "lab_assistant": "Лаборант",
    "sterile_supply_worker": "Сотрудник стерилизационной",
    "consumable_worker": "Сотрудник снабжения",
    "lab_result_courier": "Курьер лаборатории",
}
UNIT_LABELS = {
    "pallet/day": "паллет/день", "pick/day": "операций подбора/день",
    "item/day": "единиц/день", "portion/day": "порций/день",
    "cart/day": "тележек/день", "delivery/day": "доставок/день",
    "sample/day": "образцов/день", "set/day": "наборов/день",
    "kg/day": "кг/день", "m2/day": "м²/день", "unit/day": "единиц/день",
    "unit/h": "ед./ч", "pick/h": "операций подбора/час",
    "m2/h": "м²/час", "trip/h": "рейсов/час",
    "box/day": "коробок/день", "case/day": "коробов/день",
    "bin/day": "контейнеров/день",
    "robot": "роботов", "1": "",
}
SERVICE_LABELS = {
    "HARDWARE": "роботы", "BATTERY": "аккумуляторы", "CHARGING": "зарядка",
    "MAINTENANCE": "техническое обслуживание", "SOFTWARE": "программное обеспечение",
    "INTEGRATION": "интеграция", "INFRASTRUCTURE": "инфраструктура",
}


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, *, money: bool = False) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    rendered = format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ",.2f")
    if not money:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered.replace(",", " ").replace(".", ",")


def _money(value: Any) -> str:
    number = _number(value, money=True)
    return f"{number} ₽" if number is not None else UNKNOWN


def _plain(value: Any) -> str:
    return _number(value) or UNKNOWN


def _quantity(value: Any) -> str:
    item = _obj(value)
    raw = item.get("normalized_value", item.get("value"))
    if item.get("quantity_kind") == "FRACTION" and raw is not None:
        try:
            number = _number(Decimal(str(raw)) * 100)
        except (InvalidOperation, ValueError):
            number = None
        return f"{number} %" if number is not None else UNKNOWN
    number = _number(raw)
    if number is None:
        return UNKNOWN
    unit = UNIT_LABELS.get(item.get('unit'), item.get('unit') or 'единиц')
    return f"{number} {unit}".strip()


def _metric(value: Any) -> str:
    item = _obj(value)
    return _money(item.get("value")) if item.get("status") == "COMPLETE" else UNKNOWN


def _scenario(result: dict[str, Any], acquisition: str) -> dict[str, Any]:
    return next((item for item in _list(result.get("scenarios"))
                 if isinstance(item, dict) and item.get("acquisition") == acquisition
                 and item.get("uncertainty") == "BASE"), {})


def _facts(scenario: dict[str, Any]) -> dict[str, Any]:
    facts = _obj(scenario.get("report_facts"))
    if facts.get("schema_version") == "calculation-report-facts-v1":
        return facts
    # Partial runs keep the computed financial projection but omit the full
    # report_facts contract. Read only saved values; never infer missing costs.
    financial = _obj(scenario.get("financial"))
    return {"project_npv": financial.get("npv_project")} if financial.get("status") == "COMPLETE" else {}


def _cashflows(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    facts = _facts(scenario)
    if isinstance(facts.get("annual_cashflows"), list):
        return [item for item in facts["annual_cashflows"] if isinstance(item, dict)]
    financial = _obj(scenario.get("financial"))
    return [{"year": item.get("year"), "baseline": item.get("primary_cf_base"),
             "scenario": item.get("primary_cf_scenario"), "effect": item.get("differential_cf")}
            for item in _list(financial.get("annual_ledgers")) if isinstance(item, dict)]


def _text_width(value: str, size: float) -> float:
    return sum(CMAP.get(ord(char), CMAP[63])[1] for char in value) * size / 1000


def _wrap(value: str, size: float, width: float = 505) -> list[str]:
    words = value.split(" ")
    rows: list[str] = []
    row = ""
    for word in words:
        candidate = f"{row} {word}" if row else word
        if row and _text_width(candidate, size) > width:
            rows.append(row)
            row = word
        else:
            row = candidate
        while _text_width(row, size) > width:
            end = 1
            while end < len(row) and _text_width(row[:end + 1], size) <= width:
                end += 1
            rows.append(row[:end])
            row = row[end:]
    rows.append(row)
    return rows


def _pdf(lines: list[tuple[str, str]]) -> bytes:
    pages: list[list[str]] = [[]]
    used: dict[int, int] = {}
    y = 760.0

    def write(value: str, size: float, x: float, baseline: float, color: str) -> None:
        encoded = bytearray()
        for char in value:
            code = ord(char) if ord(char) in CMAP else 63
            gid = CMAP[code][0]
            used[gid] = code
            encoded.extend(gid.to_bytes(2, "big"))
        pages[-1].append(f"{color} rg BT /F1 {size} Tf {x:.1f} {baseline:.1f} Td <{encoded.hex().upper()}> Tj ET")

    def new_page(cover: bool = False) -> None:
        nonlocal y
        if pages[-1]:
            pages.append([])
        if cover:
            pages[-1].extend(["0.035 0.082 0.100 rg 0 0 595 842 re f",
                              "0.51 0.88 0.64 rg 45 712 88 5 re f"])
            y = 670.0
        else:
            pages[-1].extend(["0.972 0.981 0.975 rg 0 0 595 842 re f",
                              "0.035 0.082 0.100 rg 0 792 595 50 re f",
                              "0.51 0.88 0.64 rg 45 779 80 4 re f"])
            write("РОБОДОВОД  /  ОТЧЁТ ПО РАСЧЁТУ", 8.5, 45, 807, "0.96 0.98 0.96")
            y = 752.0

    new_page(cover=True)
    cover = True
    for value, kind in lines:
        if kind == "page":
            new_page()
            cover = False
            continue
        if kind == "diagram":
            if y < 310:
                new_page()
                cover = False
            top = y - 28
            pages[-1].extend([
                f"0.87 0.94 0.89 rg 55 {top - 142:.1f} 146 142 re f",
                f"0.87 0.94 0.89 rg 394 {top - 142:.1f} 146 142 re f",
                f"0.09 0.41 0.31 rg 201 {top - 76:.1f} 193 9 re f",
                f"0.09 0.41 0.31 rg 394 {top - 90:.1f} m 416 {top - 71:.1f} l 394 {top - 52:.1f} l f",
            ])
            write("Точка передачи A", 11, 68, top - 76, "0.035 0.082 0.100")
            write("Маршрут робота", 10, 251, top - 55, "0.035 0.082 0.100")
            write("Точка передачи B", 11, 407, top - 76, "0.035 0.082 0.100")
            write(value, 8.6, 55, top - 174, "0.21 0.27 0.27")
            y = top - 205
            continue
        if kind == "section" and y < 150:
            new_page()
            cover = False
        size, leading, before = {
            "brand": (11, 20, 0), "title": (27, 38, 10),
            "subtitle": (13, 23, 8), "cover": (11, 22, 12),
            "section": (15, 24, 16), "metric": (11, 20, 5),
            "body": (9.3, 15, 2), "note": (8.6, 14, 5),
        }.get(kind, (9.3, 15, 2))
        y -= before
        color = ("0.96 0.98 0.96" if cover else
                 "0.035 0.082 0.100" if kind in {"section", "metric"} else
                 "0.21 0.27 0.27")
        if kind == "brand":
            color = "0.51 0.88 0.64"
        if kind == "note" and not cover:
            color = "0.35 0.42 0.41"
        for row in _wrap(value, size, 500):
            if y < 60:
                new_page()
                cover = False
                color = "0.035 0.082 0.100" if kind in {"section", "metric"} else "0.21 0.27 0.27"
            write(row, size, 45, y, color)
            y -= leading

    for index in range(len(pages)):
        original = pages[-1]
        pages[-1] = pages[index]
        write(f"{index + 1} / {len(pages)}", 8, 520, 30,
              "0.65 0.77 0.71" if index == 0 else "0.35 0.42 0.41")
        pages[-1] = original

    cmap_lines = [
        "/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /DejaVuToUnicode def", "/CMapType 2 def",
        "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange",
    ]
    pairs = sorted(used.items())
    for start in range(0, len(pairs), 100):
        chunk = pairs[start:start + 100]
        cmap_lines.append(f"{len(chunk)} beginbfchar")
        cmap_lines.extend(f"<{gid:04X}> <{code:04X}>" for gid, code in chunk)
        cmap_lines.append("endbfchar")
    cmap_lines.extend(["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"])
    cmap_stream = "\n".join(cmap_lines).encode("ascii")
    font_stream = zlib.compress(FONT, level=9)
    widths = " ".join(f"{gid} [{CMAP[used[gid]][1]}]" for gid in sorted(used))
    page_ids = [8 + index * 2 for index in range(len(pages))]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R /Lang (ru-RU) >>",
        2: f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{page} 0 R' for page in page_ids)}] >>".encode("ascii"),
        3: b"<< /Type /Font /Subtype /Type0 /BaseFont /DejaVuSans /Encoding /Identity-H /DescendantFonts [4 0 R] /ToUnicode 7 0 R >>",
        4: f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /DejaVuSans /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 5 0 R /DW 600 /W [{widths}] /CIDToGIDMap /Identity >>".encode("ascii"),
        5: b"<< /Type /FontDescriptor /FontName /DejaVuSans /Flags 32 /FontBBox [-1021 -463 1793 1232] /ItalicAngle 0 /Ascent 928 /Descent -236 /CapHeight 729 /StemV 80 /FontFile2 6 0 R >>",
        6: f"<< /Length {len(font_stream)} /Length1 {len(FONT)} /Filter /FlateDecode >>\nstream\n".encode("ascii") + font_stream + b"\nendstream",
        7: f"<< /Length {len(cmap_stream)} >>\nstream\n".encode("ascii") + cmap_stream + b"\nendstream",
    }
    for index, commands in enumerate(pages):
        page_id = page_ids[index]
        stream = "\n".join(commands).encode("ascii")
        objects[page_id] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode("ascii")
        objects[page_id + 1] = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects) + 1):
        offsets.append(output.tell())
        output.write(f"{object_id} 0 obj\n".encode("ascii"))
        output.write(objects[object_id])
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return output.getvalue()



def _unknown(reason: str) -> str:
    return f"{UNKNOWN} — {reason}"


def _capacity_source(run: EvidenceRunSnapshotV1, linked: EvidenceRunSnapshotV1 | None) -> dict[str, Any]:
    requested = run.input_snapshot.get("capacity_run_id")
    if linked is None:
        if run.run_kind == "CAPACITY_ANALYSIS":
            if (run.input_snapshot.get("project_id") not in {None, run.project_id}
                    or run.result_snapshot.get("run_id") not in {None, run.run_id}):
                raise EvidenceExportIntegrityError("capacity run identity mismatch")
            return {"input": run.input_snapshot, "result": run.result_snapshot}
        return {}
    _verify_snapshots(linked)
    if (linked.run_kind != "CAPACITY_ANALYSIS"
            or linked.project_id != run.project_id
            or linked.run_id != requested
            or linked.input_snapshot.get("project_id") != run.project_id
            or _obj(linked.result_snapshot).get("run_id") != linked.run_id
            or _obj(run.result_snapshot).get("input_revision") != linked.input_snapshot.get("input_revision")):
        raise EvidenceExportIntegrityError("linked capacity run does not match economics run")
    return {"input": linked.input_snapshot, "result": linked.result_snapshot}


def _with_reason(value: str, reason: str) -> str:
    return _unknown(reason) if value == UNKNOWN else value


def build_readable_report(
    run: EvidenceRunSnapshotV1,
    capacity_run: EvidenceRunSnapshotV1 | None = None,
    *,
    presentation_version: str = "readable-presentation-v1",
) -> tuple[bytes, str]:
    """Return a searchable report from verified persisted values only."""
    digests = _verify_snapshots(run)
    if presentation_version not in {"readable-presentation-v1", PRESENTATION_VERSION}:
        raise ValueError("unsupported readable presentation version")

    def render(lines: list[tuple[str, str]]) -> bytes:
        if presentation_version == "readable-presentation-v1":
            return _pdf(lines)
        technical = False
        presented: list[tuple[str, str]] = []
        for value, kind in lines:
            if kind == "cover" and value.startswith("Дата расчёта:"):
                continue
            if kind == "section" and value in {"Источник и контроль", "Приложение: техническая проверка источника"}:
                technical = True
                value = "Технические подробности"
            if kind == "subtitle" and value.startswith("№ "):
                value = f"Сохранённый расчёт от {run.finished_at:%d.%m.%Y}"
            elif not technical:
                if value.startswith("Исходный расчёт мощности C11:"):
                    value = "Источник: сохранённый расчёт потребного парка."
                elif value.startswith("Связанный расчёт мощности:"):
                    value = "Исходный расчёт парка сохранён и связан с этой оценкой."
                elif value == "При аренде роботов (RaaS)":
                    value = "При аренде роботов"
                elif value == "Техническая основа C11":
                    value = "Расчёт потребного парка"
                else:
                    value = humanize(value)
            presented.append((value, kind))
        presented.extend([
            ("Технические подробности" if not technical else "Версия представления", "section"),
            (f"Версия представления: {PRESENTATION_VERSION}", "body"),
            (f"Идентификатор расчёта: {run.run_id}", "body"),
            (f"Версия движка: {run.versions.get('application') or UNKNOWN}", "body"),
        ])
        return _pdf(presented)
    linked = _capacity_source(run, capacity_run)
    result = _obj(run.result_snapshot)
    inputs = _obj(run.input_snapshot.get("economics"))
    process = _obj(_obj(linked.get("input")).get("process"))
    capacity = _obj(_obj(_obj(linked.get("result")).get("capacity")).get("value"))
    purchase = _scenario(result, "PURCHASE")
    raas = _scenario(result, "RAAS")
    purchase_facts = _facts(purchase)
    raas_facts = _facts(raas)
    purchase_flows = _cashflows(purchase)
    raas_flows = _cashflows(raas)
    date = run.finished_at.strftime("%d.%m.%Y")
    historical = run.versions.get("application") == "production-economics-orchestrator-v1"
    source_reason = ("исходные данные отсутствуют в сохранённом расчёте мощности"
                     if run.run_kind == "CAPACITY_ANALYSIS" else
                     "связанный расчёт мощности недоступен или отсутствует в старом расчёте")
    finance_reason = "показатель отсутствует в сохранённом результате"
    value = _obj(_obj(linked.get("result")).get("capacity")).get("value")
    fleet = purchase_facts.get("fleet_count")
    if fleet is None and isinstance(value, dict):
        fleet = value.get("selected_fleet")
    effective = _obj(capacity.get("effective_capacity"))
    effective_text = _quantity(effective) if effective else UNKNOWN
    process_name = PROCESS_LABELS.get(process.get("process_code"))
    pallet_scope = (process.get("process_code") == "warehouse_receiving_shipping"
                    and presentation_version == PRESENTATION_VERSION)
    if pallet_scope:
        process_name = "Перевозка подготовленных паллет между точками передачи"
    scope_line = ("Охват: учтена перевозка подготовленных паллет; отбор коробок и упаковка не рассчитаны. "
                  "Экономия комплектовщиков и упаковщиков не включена.")
    roles = _list(result.get("roles"))
    if run.run_kind == "CAPACITY_ANALYSIS":
        lines = [
            ("РОБОДОВОД", "brand"), ("Техническая мощность C11", "title"),
            (f"№ {run.run_id}", "subtitle"), (f"Дата расчёта: {date}", "cover"),
            ("Предварительная техническая оценка; пригодность и условия закупки требуют подтверждения.", "cover"),
            ("", "page"), ("Процесс и мощность", "section"),
            (f"Процесс: {process_name or _unknown(source_reason)}", "metric"),
            *([(scope_line, "note")] if pallet_scope else []),
            (f"Исходный объём работ: {_with_reason(_quantity(process.get('demand')), source_reason)}", "body"),
            (f"Рекомендованный парк: {_plain(capacity.get('recommended_fleet'))} роботов", "metric"),
            (f"Выбранный парк: {_plain(capacity.get('selected_fleet'))} роботов", "metric"),
            (f"Номинальная производительность: {_quantity(capacity.get('nominal_capacity'))}", "body"),
            (f"Эффективная производительность: {effective_text}", "metric"),
            (f"Покрытие требуемого объёма: {_quantity(capacity.get('coverage'))}", "body"),
            ("Покрытие — доля требуемого объёма, которую может выполнить выбранный парк.", "note"),
            (f"Фактическая загрузка: {_quantity(capacity.get('raw_load_ratio'))}", "body"),
            ("Загрузка — отношение требуемой работы к доступной мощности; более 100 % означает перегрузку.", "note"),
            ("Допущения и ограничения", "section"),
        ]
        capacity_result = _obj(_obj(linked.get("result")).get("capacity"))
        for name in ("warnings", "blockers"):
            for issue in _list(capacity_result.get(name)):
                if isinstance(issue, dict):
                    lines.append((f"{issue.get('code', 'Проверка')}: {issue.get('message') or issue.get('reason') or UNKNOWN}", "body"))
        assumptions = _list(_obj(_obj(linked.get("result")).get("trace")).get("assumptions"))
        for item in assumptions:
            if isinstance(item, dict):
                lines.append((f"Допущение {item.get('assumption_id', '')}: {item.get('rationale') or UNKNOWN}", "body"))
        if not assumptions and not capacity_result.get("warnings") and not capacity_result.get("blockers"):
            lines.append(("Отдельные ограничения не записаны в этом результате; паспорт модели и условия объекта требуют проверки.", "body"))
        lines.extend([
            ("Какие данные нужны дальше", "section"),
            ("Для экономики укажите ручную выработку, численность и оплату ролей, затраты внедрения и обслуживания, ставку и горизонт оценки, условия покупки и RaaS.", "body"),
            ("Для закупки подтвердите паспорт выбранной комплектации, цену, состав поставки и доступность.", "body"),
            ("Источник и контроль", "section"),
            (f"Расчёт мощности: {run.run_id}", "body"),
            (f"Результат: {digests.get('result') or UNKNOWN}", "body"),
            (f"Входные данные: {digests.get('input') or UNKNOWN}", "body"),
            ("Точные Decimal-значения и контрольные суммы сохранены в машинном ZIP без округления.", "body"),
        ])
        return render(lines), digests["result"] or ""
    partial = result.get("schema_version") == "economics-partial-result-v1"
    full = result.get("schema_version") in {"commercial-scenarios-bundle-v2", "commercial-scenarios-bundle-v3"}
    lines: list[tuple[str, str]] = [
        ("РОБОДОВОД", "brand"),
        ("Частичная экономика" if partial else "Экономика: baseline, покупка и RaaS" if full else "Исторический расчёт", "title"),
        (f"№ {run.run_id}", "subtitle"),
        (f"Дата расчёта: {date}", "cover"),
        *([(f"Глубина расчёта: { {'BASIC': 'Базовый', 'ADVANCED': 'Углублённый', 'FULL': 'Полный'}.get(inputs.get('calculation_depth'), 'Не указана') }", "cover")]
          if inputs.get("calculation_depth") else []),
        ("Предварительная оценка для выбора способа роботизации.", "cover"),
        ("Данные о цене, комплектации и работе на объекте требуют подтверждения.", "cover"),
        ("", "page"),
        (f"Исходный расчёт мощности C11: {run.input_snapshot.get('capacity_run_id') or UNKNOWN}", "body"),
        ("Какой процесс оцениваем", "section"),
        (f"Процесс: {process_name or _unknown(source_reason)}", "metric"),
        *([(scope_line, "note")] if pallet_scope else []),
        (f"Исходный объём работ: {_with_reason(_quantity(process.get('demand')), source_reason)}", "body"),
        (f"Смен в день: {_with_reason(_plain(_obj(_obj(process.get('schedule')).get('shifts_per_day')).get('normalized_value')), source_reason)}", "body"),
        (f"Часов в смене: {_with_reason(_plain(_obj(_obj(process.get('schedule')).get('shift_hours')).get('normalized_value')), source_reason)}", "body"),
        (f"Рабочих дней в год: {_with_reason(_plain(_obj(_obj(process.get('schedule')).get('days_per_year')).get('normalized_value')), source_reason)}", "body"),
        ("Сейчас", "section"),
    ]
    if not partial and not full:
        lines.extend([
            (_unknown("финансовые разделы этого формата не представлены в читаемом отчёте"), "body"),
            ("Исторический результат", "section"),
            ("Сохранённые числовые значения доступны без изменения в Snapshot.json и CSV архива доказательств.", "body"),
            (f"Связанный расчёт мощности: {run.input_snapshot.get('capacity_run_id') or _unknown(source_reason)}", "body"),
        ])
        if historical:
            lines.append(("ВНИМАНИЕ: исторический расчёт C16 v1 содержит известную ошибку повторного учёта стоимости дефицита персонала. Денежные результаты требуют нового расчёта.", "metric"))
        if "fte_cost_rub" in run.input_snapshot:
            lines.append(("Для старой суммы затрат на сотрудника не известна база начисления; месячная зарплата до удержаний из неё не выводится.", "body"))
        lines.extend([
            ("Источник и контроль", "section"),
            (f"Результат: {digests.get('result') or UNKNOWN}", "body"),
            (f"Входные данные: {digests.get('input') or UNKNOWN}", "body"),
        ])
        return render(lines), digests["result"] or ""
    if partial:
        lines.extend([
            ("Техническая основа C11", "section"),
            (f"Связанный расчёт мощности: {run.input_snapshot.get('capacity_run_id') or UNKNOWN}", "body"),
            (f"Выбранный парк: {_plain(fleet)} роботов", "metric"),
            (f"Эффективная мощность: {effective_text}", "body"),
            ("Рассчитанные ветки", "section"),
        ])
        visualization = _obj(result.get("visualization"))
        labour = _obj(result.get("labour"))
        if labour and inputs.get("calculation_depth"):
            lines.extend([
                ("Результат расчёта труда", "section"),
                (f"Высвобождение в выбранном процессе: {_plain(labour.get('total_released'))} чел.", "metric"),
                (f"Новые диспетчеры: {_plain(labour.get('total_additional_control'))} чел.", "body"),
                ("Высвобождение описывает занятость выбранной роли; NPV требует затрат покупки или аренды.", "note"),
            ])
        if visualization:
            if visualization.get("status") == "AVAILABLE" and _obj(run.scenario_spec_snapshot).get("schema_version") == "scenario-spec-v2":
                lines.append(("Техническая схема работы C23 доступна для этого run; денежный эффект проверяется отдельно. Геометрия без плана объекта условная.", "body"))
            else:
                missing_visual = ", ".join(str(field) for field in _list(visualization.get("required_fields")))
                lines.append((f"Техническая схема C23 не рассчитана. Нужны поля: {missing_visual or 'уточнение технических входов'}.", "body"))
        available = False
        for acquisition, scenario in (("Покупка", purchase), ("RaaS", raas)):
            facts = _facts(scenario)
            flows = _cashflows(scenario)
            if not scenario:
                continue
            available = True
            lines.append((f"{acquisition}: чистая приведённая стоимость {_metric(facts.get('project_npv'))}.", "metric"))
            for flow in flows:
                lines.append((f"Год {flow.get('year')}: без роботов {_money(flow.get('baseline'))}; {acquisition.lower()} {_money(flow.get('scenario'))}; эффект {_money(flow.get('effect'))}.", "body"))
        if not available:
            lines.append(("Денежные ветки пока не рассчитаны; сумма и NPV отсутствуют.", "body"))
        lines.append(("Что мешает остальным веткам", "section"))
        branches = _obj(result.get("branches"))
        for key, label in (("labour", "Труд"), ("purchase", "Покупка"), ("raas", "RaaS")):
            branch = _obj(branches.get(key))
            if branch.get("status") in {"CALCULATED", "AVAILABLE"}:
                continue
            missing = [str(field) for field in _list(branch.get("required_fields"))]
            if missing:
                lines.append((f"{label}: не рассчитано ({branch.get('reason_code') or 'MISSING_INPUT'}). Нужны поля: {', '.join(missing)}.", "body"))
                if presentation_version == PRESENTATION_VERSION:
                    for field_key in missing:
                        field_label, action = presentation_field(field_key)
                        lines.append((f"{field_label}: {action}", "body"))
            else:
                lines.append((f"{label}: не рассчитано ({branch.get('reason_code') or 'причина не сохранена'}).", "body"))
        for issue in _list(result.get("issues")):
            if isinstance(issue, dict):
                lines.append((f"{issue.get('field') or 'Вход'}: {issue.get('message') or issue.get('code') or UNKNOWN} {issue.get('next_step') or ''}", "body"))
        eligibility_text = {
            "ELIGIBLE": "по сохранённой проверке препятствий не выявлено; паспорт и объект требуют подтверждения",
            "NEEDS_VALIDATION": "нужна проверка паспортных данных и условий объекта",
            "INELIGIBLE": "обнаружены препятствия для применения",
        }.get(_obj(result.get("c05")).get("eligibility"), "статус не сохранён")
        procurement_text = {
            "VERIFIED": "условия закупки подтверждены в сохранённом расчёте",
            "UNVERIFIED": "условия закупки поставщиком не подтверждены",
            "INCOMPLETE": "данных об условиях закупки недостаточно",
        }.get(_obj(purchase.get("procurement")).get("procurement_status"), "статус не сохранён")
        lines.extend([
            ("Следующий шаг", "section"),
            ("Заполните недостающие поля и сохраните новый расчёт от исходного C11. Текущий run остаётся неизменным.", "body"),
            ("C05 и условия закупки требуют отдельного подтверждения; рассчитанный NPV сам по себе не является рекомендацией к закупке.", "body"),
            (f"Проверка технических ограничений: {eligibility_text}.", "body"),
            (f"Условия закупки: {procurement_text}.", "body"),
            ("Источник и контроль", "section"),
            (f"Результат: {digests.get('result') or UNKNOWN}", "body"),
            (f"Входные данные: {digests.get('input') or UNKNOWN}", "body"),
            ("Точные Decimal-значения и контрольные суммы сохранены в машинном ZIP без округления.", "body"),
        ])
        if capacity_run is not None:
            lines.append((f"Расчёт мощности: {capacity_run.run_id}; проверенный результат: {_verify_snapshots(capacity_run).get('result') or UNKNOWN}", "body"))
        return render(lines), digests["result"] or ""
    if roles:
        for role in roles:
            label = ROLE_LABELS.get(role.get("role_code"), "Сотрудник")
            salary = _with_reason(_money(_obj(role.get("monthly_gross_salary")).get("value")), "зарплата не сохранена")
            count = _with_reason(_plain(role.get("headcount")), "численность не сохранена")
            lines.append((f"{label}: {count} чел.; зарплата до удержаний {salary} на человека в месяц.", "body"))
    else:
        lines.append((_unknown("состав сотрудников не сохранён в этом расчёте"), "body"))
    baseline = purchase_flows[0].get("baseline") if purchase_flows else None
    lines.append((f"Денежный поток без роботов, первый год: {_with_reason(_money(baseline), finance_reason)}", "metric"))
    lines.append(("Это годовая база сценария, а не обещанная выручка.", "note"))

    lines.extend([
        ("После покупки роботов", "section"),
        (f"Расчётный парк: {_with_reason(_plain(fleet), 'не сохранён расчёт парка')} роботов", "metric"),
        (f"Расчётная мощность после внедрения: {_with_reason(effective_text, source_reason)}", "body"),
        (f"Первоначальные вложения проекта: {_with_reason(_money(purchase_facts.get('project_capex_cashflow')), finance_reason)}", "body"),
        (f"Эксплуатация роботов, первый год: {_with_reason(_money(purchase_facts.get('purchase_annual_robot_opex')), finance_reason)}", "body"),
        (f"Эффект против варианта без роботов, первый год: {_with_reason(_money(purchase_flows[0].get('effect') if purchase_flows else None), finance_reason)}", "metric"),
        (f"Чистая приведённая стоимость проекта: {_with_reason(_metric(purchase_facts.get('project_npv')), finance_reason)}", "metric"),
        ("При аренде роботов (RaaS)", "section"),
        (f"Тариф на робота в месяц: {_with_reason(_money(_obj(_obj(result.get('monetary_input_basis')).get('raas')).get('per_robot_month_gross_rub') if result.get('monetary_input_basis') else inputs.get('raas_monthly_per_robot_gross')), 'тариф не сохранён во входных условиях')}", "metric"),
    ])
    services = [SERVICE_LABELS.get(item.get("area"), item.get("area"))
                for item in _list(raas_facts.get("responsibilities"))
                if isinstance(item, dict) and item.get("responsible_party") == "VENDOR"]
    lines.append((f"Услуги поставщика по введённым условиям: {', '.join(services) if services else _unknown('обязанности сторон не подтверждены или не сохранены')}", "body"))
    lines.extend([
        (f"Первоначальные вложения заказчика: {_with_reason(_money(raas_facts.get('project_capex_cashflow')), finance_reason)}", "body"),
        (f"Арендные платежи, первый год: {_with_reason(_money(raas_facts.get('raas_annual_payment')), finance_reason)}", "body"),
        (f"Прочие расходы заказчика, первый год: {_with_reason(_money(raas_facts.get('raas_annual_customer_opex')), finance_reason)}", "body"),
        (f"Эффект против варианта без роботов, первый год: {_with_reason(_money(raas_flows[0].get('effect') if raas_flows else None), finance_reason)}", "metric"),
        (f"Чистая приведённая стоимость проекта: {_with_reason(_metric(raas_facts.get('project_npv')), finance_reason)}", "metric"),
        ("Сравнение денег по годам", "section"),
        ("Суммы ниже взяты из сохранённых годовых потоков проекта. Эффект — разница между сценарием и вариантом без роботов.", "note"),
    ])
    years = sorted({item.get("year") for item in purchase_flows + raas_flows if isinstance(item.get("year"), int)})
    if years:
        for year in years:
            p = next((item for item in purchase_flows if item.get("year") == year), {})
            r = next((item for item in raas_flows if item.get("year") == year), {})
            lines.append((f"Год {year}: без роботов {_with_reason(_money(p.get('baseline')), finance_reason)}; покупка {_with_reason(_money(p.get('scenario')), finance_reason)}; аренда {_with_reason(_money(r.get('scenario')), finance_reason)}.", "body"))
            lines.append((f"Изменение: покупка {_with_reason(_money(p.get('effect')), finance_reason)}; аренда {_with_reason(_money(r.get('effect')), finance_reason)}.", "body"))
    else:
        lines.append((_unknown("годовые денежные потоки отсутствуют в сохранённом результате"), "body"))
    evidence = _obj(inputs.get("assumption_evidence"))
    if inputs.get('schema_version') == 'economics-explicit-inputs-v6':
        lines.append(('Финансовые входы сохранённой версии', 'section'))
        labels = {'purchase_price_override_gross': 'Цена одного робота, ₽',
                  'implementation_mode': 'Режим внедрения', 'implementation_percent': 'Внедрение, % цены парка',
                  'implementation_cost_total_gross': 'Внедрение, ₽ всего', 'raas_mode': 'Режим RaaS',
                  'raas_percent_monthly': 'RaaS, % цены одного робота в месяц',
                  'raas_monthly_per_robot_gross': 'Введённая фиксированная аренда, ₽/робот/месяц',
                  'raas_contract_months': 'Срок договора, месяцев', 'manual_units_per_shift': 'Выработка человека выбранной роли, ед./смену',
                  'control_monthly_gross': 'Зарплата диспетчера gross, ₽/месяц', 'technician_monthly_gross': 'Зарплата техника gross, ₽/месяц',
                  'annual_service_per_robot_gross': 'Сервис, ₽/робот/год', 'average_power_w': 'Средняя мощность, Вт',
                  'shared_site_capital_gross': 'Общие вложения, ₽', 'shared_annual_cost_gross': 'Общие расходы, ₽/год',
                  'horizon_years': 'Горизонт, лет', 'discount_rate': 'Ставка дисконтирования, доля'}
        for key, label in labels.items():
            if key == 'implementation_cost_total_gross' and inputs.get('implementation_mode') == 'PERCENT':
                continue
            if key == 'raas_monthly_per_robot_gross' and inputs.get('raas_mode') == 'PERCENT':
                continue
            lines.append((f"{label}: {_plain(inputs.get(key))}; источник: {_obj(inputs.get('field_sources')).get(key) or 'сохранённый ввод'}", 'body'))
        basis = _obj(result.get('monetary_input_basis'))
        lines.append((f"Денежная база: цена робота {_money(basis.get('unit_price_gross_rub'))}; парк {_plain(basis.get('fleet'))}; внедрение {_money(_obj(basis.get('implementation')).get('amount_gross_rub'))}", 'body'))
    if evidence:
        lines.append(("Подтверждённые допущения сценария", "section"))
        lines.append(("Эти значения сохранены как предварительные условия пользователя, а не паспорт или предложение поставщика.", "note"))
        for field, item in sorted(evidence.items()):
            source = _obj(item)
            if source.get("confirmed") is True:
                lines.append((f"{field}: {_plain(source.get('confirmed_value'))}; набор {source.get('template_id') or source.get('version') or UNKNOWN}; источник {source.get('source') or UNKNOWN}; дата {source.get('published_on') or UNKNOWN}. {source.get('rationale') or UNKNOWN}.", "body"))
    c05 = _obj(result.get("c05"))
    eligibility = {
        "ELIGIBLE": "по сохранённой проверке препятствий не выявлено; паспорт модели и объект всё равно требуют подтверждения",
        "NEEDS_VALIDATION": "нужна проверка паспортных данных и условий объекта",
        "INELIGIBLE": "сохранённая проверка выявила препятствия для применения",
    }.get(run.diagnostics.get("constraint_eligibility") or c05.get("eligibility"), _unknown("статус проверки не сохранён"))
    procurement = {
        "VERIFIED": "условия закупки подтверждены в сохранённом расчёте",
        "UNVERIFIED": "условия закупки поставщиком не подтверждены",
        "INCOMPLETE": "данных об условиях закупки недостаточно",
    }.get(_obj(purchase.get("procurement")).get("procurement_status"), _unknown("статус закупки не сохранён"))
    lines.extend([
        ("Что известно и что ещё подтвердить", "section"),
        ("Расчёт использует сохранённые условия пользователя и версии правил на дату запуска. Параметры поставщика, доступность модели и условия внедрения следует подтвердить до закупки.", "body"),
        (f"Проверка технических ограничений: {eligibility}.", "body"),
        (f"Условия закупки: {procurement}.", "body"),
    ])
    if historical:
        lines.append(("ВНИМАНИЕ: исторический расчёт C16 v1 содержит известную ошибку повторного учёта стоимости дефицита персонала. Денежные результаты требуют нового расчёта.", "metric"))
    if "fte_cost_rub" in run.input_snapshot:
        lines.append(("Для старой суммы затрат на сотрудника не известна база начисления; месячная зарплата до удержаний из неё не выводится.", "body"))
    if not linked:
        lines.append((_unknown(source_reason), "body"))
    lines.extend([
        ("Источники и методика", "section"),
        ("Показатели взяты из неизменяемых сохранённых входов и результатов. Этот PDF не пересчитывает мощность или деньги и не использует показатели 3D-визуализации как фактическую производительность.", "body"),
        ("Чистая приведённая стоимость учитывает дисконтирование в расчётном движке. Положительное значение само по себе не подтверждает техническую пригодность или цену поставщика.", "body"),
        (f"Горизонт: {_with_reason(_plain(inputs.get('horizon_years')), 'не сохранён во входных условиях')} лет; ставка дисконтирования: {_with_reason(_plain(inputs.get('discount_rate')), 'не сохранена во входных условиях')}.", "body"),
        ("Приложение: техническая проверка источника", "section"),
        (f"Идентификатор расчёта: {run.run_id}; ревизия: {run.revision_id or 'не указана'}.", "body"),
        (f"Результат: {digests.get('result') or UNKNOWN}", "body"),
        (f"Входные данные: {digests.get('input') or UNKNOWN}", "body"),
        (f"Версия расчёта: {run.versions.get('application') or UNKNOWN}", "body"),
    ])
    if linked:
        source_run = capacity_run or run
        lines.append((f"Расчёт мощности: {source_run.run_id}; проверенный результат: {_verify_snapshots(source_run).get('result') or UNKNOWN}", "body"))
    lines.append(("Полные входы, результаты и контрольные суммы доступны в архиве доказательств этого расчёта.", "body"))
    return render(lines), digests["result"] or ""


__all__ = ["build_readable_report"]
