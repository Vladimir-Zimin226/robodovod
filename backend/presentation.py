"""Versioned human-facing labels shared with the frontend; no calculation rules."""

from __future__ import annotations

import json
import re
from pathlib import Path

GLOSSARY = json.loads((Path(__file__).resolve().parents[1] / "contracts/presentation-v2.json").read_text(encoding="utf-8"))
VERSION = GLOSSARY["version"]
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
CODE = re.compile(r"\bC\d{2}\b")


def subsystem(code: str) -> str:
    return GLOSSARY["subsystems"].get(code, "раздел расчёта")


def status(code: str | None) -> str:
    return GLOSSARY["statuses"].get(code, "статус требует уточнения")


def field(key: str) -> tuple[str, str]:
    if key.startswith("role_pool."):
        return "зарплата роли процесса", "Уточните месячную зарплату этой роли во вводе процесса и сохраните новый расчёт парка."
    data = GLOSSARY["fields"].get(key)
    if data is None:
        return "дополнительное условие", "Откройте технические подробности и сверьте исходное поле."
    return data["label"], data["action"]


def section(code: str) -> str:
    return GLOSSARY["sections"].get(code, "Раздел данных")


def humanize(text: str, *, technical: bool = False) -> str:
    if technical:
        return text
    rendered = text.replace("исходного C11", "исходного расчёта парка").replace("от исходного C11", "от исходного расчёта парка")
    for key, value in GLOSSARY.get("terms", {}).items():
        rendered = rendered.replace(key, value)
    rendered = CODE.sub(lambda match: subsystem(match.group()), rendered)
    for code, label in GLOSSARY["statuses"].items():
        rendered = re.sub(rf"\b{re.escape(code)}\b", label, rendered)
    for key, value in sorted(GLOSSARY["fields"].items(), key=lambda item: -len(item[0])):
        rendered = re.sub(rf"(?<![\w.]){re.escape(key)}(?!\w)", value["label"], rendered)
    rendered = re.sub(r"role_pool\.[\w.-]+", "зарплата роли процесса", rendered)
    rendered = UUID.sub("идентификатор в технических подробностях", rendered)
    rendered = re.sub(r"\brun\b", "расчёт", rendered, flags=re.I)
    return rendered
