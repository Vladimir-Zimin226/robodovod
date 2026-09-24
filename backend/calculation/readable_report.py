"""A standalone Russian report rendered only from verified immutable snapshots.

The embedded DejaVu font and its cmap keep Cyrillic text searchable without a
runtime font package or a browser-side calculation step.
"""

from __future__ import annotations

import io
import json
import zlib
from pathlib import Path
from typing import Any

from calculation.evidence_export import EvidenceRunSnapshotV1, _verify_snapshots


ASSETS = Path(__file__).with_name("assets")
FONT = (ASSETS / "DejaVuSans.ttf").read_bytes()
CMAP = {int(code): tuple(metrics) for code, metrics in json.loads(
    (ASSETS / "dejavu-cmap-v1.json").read_text(encoding="utf-8")
).items()}


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
    y = 795.0
    for value, kind in lines:
        size = 16 if kind == "title" else 11 if kind == "heading" else 9
        leading = 24 if kind == "title" else 18 if kind == "heading" else 14
        if kind == "heading":
            y -= 8
        for row in _wrap(value, size):
            if y < 52:
                pages.append([])
                y = 795.0
            encoded = bytearray()
            for char in row:
                code = ord(char) if ord(char) in CMAP else 63
                gid = CMAP[code][0]
                used[gid] = code
                encoded.extend(gid.to_bytes(2, "big"))
            pages[-1].append(f"BT /F1 {size} Tf 45 {y:.1f} Td <{encoded.hex().upper()}> Tj ET")
            y -= leading

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


def _value(value: Any) -> str:
    if value is None:
        return "NOT_AVAILABLE"
    if isinstance(value, dict):
        return str(value.get("value") if value.get("value") is not None else value.get("status", "NOT_AVAILABLE"))
    return str(value)


def build_readable_report(run: EvidenceRunSnapshotV1) -> tuple[bytes, str]:
    """Return searchable PDF and its verified result snapshot digest."""
    digests = _verify_snapshots(run)
    result = run.result_snapshot
    scenarios = result.get("scenarios") if isinstance(result.get("scenarios"), list) else []
    lines: list[tuple[str, str]] = [
        ("РОБОДОВОД · Отчёт предварительного расчёта", "title"),
        (f"Run {run.run_id} · revision {run.revision_id or 'NOT_AVAILABLE'}", "body"),
        (f"Сохранён {run.finished_at.isoformat()} · {run.run_kind}", "body"),
        ("Предварительная оценка. Не является инженерной сертификацией, коммерческим предложением или рекомендацией к закупке.", "body"),
        ("Достоверность и ограничения", "heading"),
        (f"C05: {run.diagnostics.get('constraint_eligibility') or 'NOT_AVAILABLE'}. Данные паспорта и доступности требуют отдельного подтверждения.", "body"),
        ("Цены, зарплаты, RaaS и включённые услуги — введённые условия сценария; подтверждение поставщика не следует из расчёта.", "body"),
    ]
    if run.versions.get("application") == "production-economics-orchestrator-v1":
        lines.append(("ИСТОРИЧЕСКИЙ РАСЧЁТ: C16 v1 повторно умножал стоимость дефицита персонала. NPV и срок окупаемости этого run нельзя принимать как проверенное обоснование. Для исправления нужен новый run.", "body"))
    if "fte_cost_rub" in run.input_snapshot:
        lines.append(("Legacy fte_cost_rub: база неизвестна; значение не преобразовано в месячный gross.", "body"))
    inputs = run.input_snapshot.get("economics", {})
    if not isinstance(inputs, dict):
        inputs = {}
    lines.append(("Ключевые входные условия", "heading"))
    for key, label in (
        ("discount_rate", "Ставка дисконтирования"),
        ("horizon_years", "Горизонт, лет"),
        ("annual_service_per_robot_gross", "Сервис на робота, gross ₽/год"),
        ("raas_monthly_per_robot_gross", "RaaS на робота, gross ₽/мес"),
        ("implementation_cost_total_gross", "Внедрение, gross ₽"),
        ("warranty_years", "Гарантия, лет"),
    ):
        lines.append((f"{label}: {_value(inputs.get(key))}", "body"))
    if not isinstance(inputs, dict) or not inputs:
        lines.append(("Экономические входы: NOT_AVAILABLE в этом сохранённом run.", "body"))
    lines.append(("Сценарии · суммы взяты из сохранённого расчёта", "heading"))
    if not scenarios:
        lines.append(("Сценарии и финансовые показатели: NOT_AVAILABLE.", "body"))
    for scenario in scenarios:
        financial = scenario.get("financial") or {}
        procurement = scenario.get("procurement") or {}
        lines.append((f"{scenario.get('acquisition', '?')} · {scenario.get('uncertainty', '?')} · {scenario.get('scenario_id', '?')}", "heading"))
        lines.append((f"NPV: {_value(financial.get('npv_project'))} ₽ · простой срок окупаемости: {_value(financial.get('simple_payback'))} лет · статус: {financial.get('status', 'NOT_AVAILABLE')}", "body"))
        lines.append((f"Закупка: {procurement.get('procurement_status', 'NOT_AVAILABLE')} · recommendation: {(scenario.get('recommendation') or {}).get('status', 'NOT_AVAILABLE')}", "body"))
        lines.append((f"Источник финансов: {financial.get('source_digest', 'NOT_AVAILABLE')}", "body"))
    base = next((item for item in scenarios if item.get("acquisition") == "PURCHASE" and item.get("uncertainty") == "BASE"), None)
    lines.append(("Денежный поток · покупка, базовый профиль", "heading"))
    lines.append(("Разница = поток сценария минус поток базы. NPV и окупаемость рассчитаны серверным engine; PDF только переносит сохранённые значения.", "body"))
    for ledger in ((base or {}).get("financial") or {}).get("annual_ledgers", []):
        lines.append((f"Год {ledger.get('year')}: база {_value(ledger.get('primary_cf_base'))} ₽; сценарий {_value(ledger.get('primary_cf_scenario'))} ₽; разница {_value(ledger.get('differential_cf'))} ₽.", "body"))
    if base is None:
        lines.append(("Денежный поток: NOT_AVAILABLE.", "body"))
    lines.append(("Источники и проверка", "heading"))
    for key, digest in digests.items():
        lines.append((f"{key}: {digest or 'NOT_AVAILABLE'}", "body"))
    lines.append((f"Evidence ZIP: /api/projects/{run.project_id}/analysis-runs/{run.run_id}/exports/evidence.zip", "body"))
    lines.append((f"Manifest: /api/projects/{run.project_id}/analysis-runs/{run.run_id}/exports/manifest", "body"))
    lines.append(("Snapshot.json и CSV-разделы в ZIP содержат полный машинный след; отдельный PDF не заменяет его.", "body"))
    return _pdf(lines), digests["result"] or ""


__all__ = ["build_readable_report"]
