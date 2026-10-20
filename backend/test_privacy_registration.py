import pytest
from pydantic import ValidationError

from persistence_api import PublicRegisterRequest


def test_public_registration_requires_explicit_current_policy_consent():
    base = {"email": "person@example.com", "password": "a long local passphrase"}
    for extra in ({}, {"privacy_consent": False, "privacy_policy_version": "privacy-draft-2026-10-20"},
                  {"privacy_consent": True, "privacy_policy_version": "obsolete"}):
        with pytest.raises(ValidationError):
            PublicRegisterRequest.model_validate({**base, **extra})
    accepted = PublicRegisterRequest.model_validate({**base, "privacy_consent": True,
        "privacy_policy_version": "privacy-draft-2026-10-20"})
    assert accepted.privacy_consent is True
