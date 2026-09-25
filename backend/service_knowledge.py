"""Versioned, deterministic answers about the current service UI."""

from __future__ import annotations

import json
import re
from pathlib import Path


KNOWLEDGE = json.loads(
    (Path(__file__).resolve().parents[1] / "contracts/service-assistant-knowledge-v1.json").read_text(encoding="utf-8")
)
ACTION_LABELS = {
    "demo": "Открыть демо",
    "calculation": "Перейти к расчёту",
    "catalog": "Открыть библиотеку решений",
    "projects": "Открыть мои проекты",
    "result": "Вернуться к результату",
}
_STOP = {"а", "в", "во", "где", "для", "и", "или", "как", "мне", "мой", "моя", "на", "по", "с", "со", "у", "что", "это", "этот", "я"}


def _words(value: str) -> set[str]:
    text = value.casefold().replace("ё", "е")
    return {word[:6] if len(word) > 6 else word for word in re.findall(r"[а-яa-z0-9]+", text)
            if word not in _STOP}


def _topic_for(message: str) -> dict | None:
    query = _words(message)
    if not query:
        return None
    ranked = []
    for topic in KNOWLEDGE["topics"]:
        for phrase in topic["questions"]:
            terms = _words(phrase)
            common = query & terms
            if len(common) < min(2, len(terms)):
                continue
            score = len(common) / len(terms) * 0.75 + len(common) / len(query) * 0.25
            if score >= 0.56:
                ranked.append((score, len(common), topic))
    return max(ranked, key=lambda item: (item[0], item[1]))[2] if ranked else None


def answer_service_question(message: str) -> dict:
    topic = _topic_for(message)
    entry = topic or KNOWLEDGE["fallback"]
    return {
        "schema_version": KNOWLEDGE["version"],
        "topic_id": topic["id"] if topic else "unknown",
        "reply": entry["answer"],
        "actions": [{"id": key, "label": ACTION_LABELS[key]} for key in entry["actions"]],
    }
