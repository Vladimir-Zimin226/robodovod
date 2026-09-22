"""Typed, lossless unit normalization for calculation intake v2.

Only physical unit definitions live here.  Container/batch conversions are
deliberately excluded because they require process inputs and later formulas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class UnitNormalizationError(ValueError):
    """Stable validation error for unsupported or malformed quantities."""


@dataclass(frozen=True)
class UnitRule:
    canonical_unit: str
    factor: Decimal
    quantity_kind: str


UNIT_RULES: dict[str, UnitRule] = {
    "s": UnitRule("s", Decimal("1"), "TIME"),
    "sec": UnitRule("s", Decimal("1"), "TIME"),
    "min": UnitRule("s", Decimal("60"), "TIME"),
    "h": UnitRule("h", Decimal("1"), "TIME"),
    "day": UnitRule("day", Decimal("1"), "TIME"),
    "m": UnitRule("m", Decimal("1"), "DISTANCE"),
    "km": UnitRule("m", Decimal("1000"), "DISTANCE"),
    "kg": UnitRule("kg", Decimal("1"), "MASS"),
    "t": UnitRule("kg", Decimal("1000"), "MASS"),
    "m2": UnitRule("m2", Decimal("1"), "AREA"),
    "person": UnitRule("person", Decimal("1"), "COUNT"),
    "shift": UnitRule("shift", Decimal("1"), "COUNT"),
    "RUB/person/month": UnitRule("RUB/person/month", Decimal("1"), "MONEY"),
    "pallet/day": UnitRule("pallet/day", Decimal("1"), "FLOW"),
    "box/day": UnitRule("box/day", Decimal("1"), "FLOW"),
    "case/day": UnitRule("case/day", Decimal("1"), "FLOW"),
    "cart/day": UnitRule("cart/day", Decimal("1"), "FLOW"),
    "delivery/day": UnitRule("delivery/day", Decimal("1"), "FLOW"),
    "portion/day": UnitRule("portion/day", Decimal("1"), "FLOW"),
    "kg/day": UnitRule("kg/day", Decimal("1"), "FLOW"),
    "sample/day": UnitRule("sample/day", Decimal("1"), "FLOW"),
    "set/day": UnitRule("set/day", Decimal("1"), "FLOW"),
    "bin/day": UnitRule("bin/day", Decimal("1"), "FLOW"),
    "item/day": UnitRule("item/day", Decimal("1"), "FLOW"),
    "pick/day": UnitRule("pick/day", Decimal("1"), "FLOW"),
    "m2/day": UnitRule("m2/day", Decimal("1"), "FLOW"),
}


def canonical_decimal(value: str) -> str:
    """Return a non-exponent canonical decimal without rounding."""

    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise UnitNormalizationError("INVALID_DECIMAL") from exc
    if not parsed.is_finite():
        raise UnitNormalizationError("INVALID_DECIMAL")
    if parsed == 0:
        return "0"
    result = format(parsed, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return result


def normalize_unit(value: str, raw_unit: str, *, expected_kind: str) -> tuple[str, str]:
    """Normalize a value and return ``(canonical value, canonical unit)``."""

    rule = UNIT_RULES.get(raw_unit)
    if rule is None:
        raise UnitNormalizationError("UNIT_UNSUPPORTED")
    if rule.quantity_kind != expected_kind:
        raise UnitNormalizationError("UNIT_KIND_MISMATCH")
    normalized = Decimal(canonical_decimal(value)) * rule.factor
    return canonical_decimal(format(normalized, "f")), rule.canonical_unit
