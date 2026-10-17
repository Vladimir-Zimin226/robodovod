"""V7 implementation coverage. Missing commercial lines never become zero."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

REQUIRED_LINES = ("DELIVERY", "COMMISSIONING", "INTEGRATION")
AMOUNT_STATUSES = {"USER_ESTIMATE", "USER_MEASURED", "POLICY_ASSUMPTION"}
EXCLUDED_STATUSES = {"EXPLICIT_ZERO", "NOT_APPLICABLE", "INCLUDED"}
VALID_STATUSES = AMOUNT_STATUSES | EXCLUDED_STATUSES | {"UNKNOWN"}
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?\Z")


def parse_implementation_lines(raw: Any, extra_amount: str | None) -> tuple[dict[str, dict], list[str], list[dict]]:
    """Return normalized rows, blocking fields and user-facing validation issues."""
    lines: dict[str, dict] = {}
    missing: list[str] = []
    issues: list[dict] = []
    source = raw if isinstance(raw, dict) else {}
    for category in REQUIRED_LINES:
        field = f"implementation_lines.{category.lower()}"
        row = source.get(category)
        row = row if isinstance(row, dict) else {}
        status = row.get("status", "UNKNOWN")
        amount = row.get("amount")
        explanation = str(row.get("explanation") or "").strip()
        source_ref = str(row.get("source_ref") or "").strip()
        included_in = row.get("included_in")
        invalid = status not in VALID_STATUSES
        if status in AMOUNT_STATUSES:
            valid_amount = isinstance(amount, str) and bool(_DECIMAL.fullmatch(amount))
            invalid |= not valid_amount or (valid_amount and Decimal(amount) <= 0)
            invalid |= len(source_ref) < 3
            if status == "POLICY_ASSUMPTION":
                invalid |= len(explanation) < 3
        elif status == "EXPLICIT_ZERO":
            invalid |= amount != "0" or len(explanation) < 3
        elif status == "NOT_APPLICABLE":
            invalid |= amount is not None or len(explanation) < 3
        elif status == "INCLUDED":
            invalid |= amount is not None or included_in != "implementation_cost_total_gross" or extra_amount is None or Decimal(extra_amount or "0") <= 0 or len(explanation) < 3
        elif status == "UNKNOWN":
            invalid |= amount is not None
        if invalid:
            status = "UNKNOWN"
            issues.append({"field": field, "code": "COST_LINE_INVALID",
                           "message": "Проверьте сумму, статус и основание статьи сметы.",
                           "next_step": "Укажите источник для суммы, объяснение для нуля или оставьте неизвестным."})
        if status == "UNKNOWN":
            missing.append(field)
        lines[category] = {"status": status,
                           "amount": amount if status in AMOUNT_STATUSES | {"EXPLICIT_ZERO"} else None,
                           "source_ref": source_ref or None, "explanation": explanation or None,
                           "included_in": included_in if status == "INCLUDED" else None}
    return lines, missing, issues


def known_implementation_subtotal(lines: dict[str, dict], extra_amount: str | None) -> str:
    total = Decimal(extra_amount or "0")
    for row in lines.values():
        if row["status"] in AMOUNT_STATUSES:
            total += Decimal(row["amount"])
    return format(total.quantize(Decimal("0.01")), "f")
