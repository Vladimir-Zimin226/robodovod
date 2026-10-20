import pytest
from pathlib import Path
from pydantic import ValidationError

from persistence_api import PRIVACY_POLICY_VERSION, PublicRegisterRequest


def test_public_registration_requires_explicit_current_policy_consent():
    base = {"email": "person@example.com", "password": "a long local passphrase"}
    for extra in ({}, {"privacy_consent": False, "privacy_policy_version": "robodovod-privacy-v1-2026-10-20"},
                  {"privacy_consent": True, "privacy_policy_version": "obsolete"}):
        with pytest.raises(ValidationError):
            PublicRegisterRequest.model_validate({**base, **extra})
    accepted = PublicRegisterRequest.model_validate({**base, "privacy_consent": True,
        "privacy_policy_version": "robodovod-privacy-v1-2026-10-20"})
    assert accepted.privacy_consent is True


def test_public_policy_matches_registration_version_and_operator():
    document = (Path(__file__).resolve().parents[1] / "frontend/public/privacy-policy.html").read_text(encoding="utf-8-sig")
    assert PRIVACY_POLICY_VERSION in document
    assert "Зимин Владимир Андреевич" in document
    assert "751902969999" in document
    assert "325650000029609" in document
    assert "FLYFORECAST" not in document
