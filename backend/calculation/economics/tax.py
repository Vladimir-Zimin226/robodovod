"""Illustrative C16 profit-tax supplement; never the primary result."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

TaxMode = Literal["NONE", "ILLUSTRATIVE_OTHER_INCOME", "ILLUSTRATIVE_NO_OTHER_INCOME"]


@dataclass(frozen=True)
class TaxYear:
    tax: Decimal
    loss_open: Decimal
    loss_used: Decimal
    loss_close: Decimal


def illustrative_tax(ebits: list[Decimal], mode: TaxMode, *, rate: Decimal,
                     carry_years: int, deduction_cap: Decimal) -> list[TaxYear]:
    """Apply K12 independently to one full-flow EBIT series."""

    lots: list[tuple[int, Decimal]] = []
    result: list[TaxYear] = []
    for year, ebit in enumerate(ebits, start=1):
        lots = [(origin, amount) for origin, amount in lots if year - origin <= carry_years]
        opening = sum((amount for _, amount in lots), Decimal(0))
        used = Decimal(0)
        if mode == "NONE":
            tax = Decimal(0)
        elif mode == "ILLUSTRATIVE_OTHER_INCOME":
            tax = ebit * rate
        elif ebit <= 0:
            tax = Decimal(0)
            if ebit < 0:
                lots.append((year, -ebit))
        else:
            available = sum((amount for _, amount in lots), Decimal(0))
            used = min(available, ebit * deduction_cap)
            remainder = used
            updated: list[tuple[int, Decimal]] = []
            for origin, amount in lots:
                consumed = min(amount, remainder)
                remainder -= consumed
                if amount > consumed:
                    updated.append((origin, amount - consumed))
            lots = updated
            tax = (ebit - used) * rate
        closing = sum((amount for _, amount in lots), Decimal(0))
        result.append(TaxYear(tax=tax, loss_open=opening, loss_used=used, loss_close=closing))
    return result
