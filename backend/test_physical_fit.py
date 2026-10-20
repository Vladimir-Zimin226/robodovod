"""Acceptance checks B01-B03 and B05 for catalog payload evidence."""

from decimal import Decimal
from types import SimpleNamespace

from calculation.physical_fit import check_payload


def fact(value="500", *, unit="kg", status="VERIFIED_OFFICIAL", evidence="passport-1"):
    return SimpleNamespace(code="payload_kg", value=value, canonical_unit=unit,
                           resolution_status=status, evidence_id=evidence)


def test_verified_capacity_is_a_hard_gate_and_excess_capacity_is_allowed():
    below = check_payload(Decimal("2500"), [fact()])
    assert below["physical_fit"] == "FAIL"
    assert below["payload_evidence_id"] == "passport-1"
    above = check_payload(Decimal("500"), [fact("2500")])
    assert above["physical_fit"] == "PASS"
    assert above["verified_payload_kg"] == "2500.00"


def test_missing_or_unverified_capacity_stays_unknown():
    assert check_payload(Decimal("500"), [])["physical_fit"] == "UNKNOWN"
    assert check_payload(Decimal("500"), [fact(evidence=None)])["physical_fit"] == "UNKNOWN"
    assert check_payload(Decimal("500"), [fact(status="ASSUMPTION")])["physical_fit"] == "UNKNOWN"
    assert check_payload(Decimal("500"), [fact(unit="lb")])["physical_fit"] == "UNKNOWN"
    assert check_payload(None, [fact()])["physical_fit"] == "UNKNOWN"


def test_cleaning_does_not_require_cargo_mass():
    assert check_payload(None, [], applicable=False)["physical_fit"] == "NOT_APPLICABLE"
