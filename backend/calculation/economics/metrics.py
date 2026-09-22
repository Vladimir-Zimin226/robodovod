"""C16 financial metrics over differential cash flows."""

from __future__ import annotations

from decimal import Decimal


def npv(flows: list[Decimal], discount_rate: Decimal) -> Decimal:
    return sum((value / ((Decimal(1) + discount_rate) ** year)
                for year, value in enumerate(flows)), Decimal(0))


def payback(flows: list[Decimal], discount_rate: Decimal | None = None) -> Decimal | None:
    """First cumulative zero crossing, linearly interpolated within a year."""

    cumulative = flows[0]
    if cumulative >= 0:
        return Decimal(0)
    for year, raw in enumerate(flows[1:], start=1):
        value = raw if discount_rate is None else raw / ((Decimal(1) + discount_rate) ** year)
        previous = cumulative
        cumulative += value
        if cumulative >= 0 and value > 0:
            return Decimal(year - 1) + (-previous / value)
    return None
