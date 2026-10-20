"""Evidence-aware physical constraints shared by role scenario engines."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

VERIFIED_STATUSES = frozenset({
    "CORROBORATED", "CROSS_DOCUMENT_ENRICHED", "VERIFIED_OFFICIAL",
    "VERIFIED_AUTHORIZED_PARTNER", "MANUALLY_APPROVED",
})


def check_payload(task_payload_kg: Decimal | None, facts: Any, *, applicable: bool = True) -> dict[str, Any]:
    """Return PASS/FAIL/UNKNOWN without inferring a passport value from a model name."""
    verified = None
    evidence_id = None
    for fact in facts:
        if (fact.code != "payload_kg" or fact.canonical_unit.lower() != "kg"
                or fact.resolution_status not in VERIFIED_STATUSES or not fact.evidence_id):
            continue
        try:
            value = Decimal(str(fact.value))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if value.is_finite() and value > 0:
            verified, evidence_id = value, fact.evidence_id
            break
    if not applicable:
        status, reason = "NOT_APPLICABLE", "Грузоподъёмность не относится к этой работе"
    elif task_payload_kg is None:
        status, reason = "UNKNOWN", "Не указана максимальная масса одной единицы груза"
    elif verified is None:
        status, reason = "UNKNOWN", "Нет подтверждённой паспортной грузоподъёмности"
    elif task_payload_kg > verified:
        status, reason = "FAIL", "Подтверждённая грузоподъёмность ниже массы единицы груза"
    else:
        status, reason = "PASS", "Подтверждённая грузоподъёмность достаточна"
    return {"physical_fit": status, "physical_fit_reason": reason,
            "task_payload_kg": f"{task_payload_kg:.2f}" if task_payload_kg is not None else None,
            "verified_payload_kg": f"{verified:.2f}" if verified is not None else None,
            "payload_evidence_id": evidence_id}
