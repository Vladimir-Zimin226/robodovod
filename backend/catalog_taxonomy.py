"""Stable runtime category metadata independent of catalog records."""

from __future__ import annotations

CATEGORY_ORDER: tuple[str, ...] = (
    "internal_mobile",
    "service_delivery",
    "cleaning_robot",
    "fixed_cell",
    "aerial",
)

CATEGORY_LABELS: dict[str, str] = {
    "internal_mobile": "Мобильные транспортные роботы",
    "service_delivery": "Роботы доставки",
    "cleaning_robot": "Уборочные роботы",
    "fixed_cell": "Стационарные ячейки паллетизации",
    "aerial": "Летательные системы",
}
