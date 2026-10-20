"""One isolated local backend registration, consent, logout and login smoke."""

import json
import uuid
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001/api/auth"
VERSION = "robodovod-privacy-v1-2026-10-20"
OUT = Path(__file__).resolve().parent / "evidence/rc-auth-local.json"


def main():
    session = requests.Session()
    email = f"rc-privacy-{uuid.uuid4().hex[:12]}@example.com"
    password = "local smoke only passphrase 2026"
    payload = {"email": email, "password": password, "privacy_consent": True,
               "privacy_policy_version": VERSION}
    old = session.post(BASE + "/register", json={**payload,
                        "privacy_policy_version": "privacy-draft-2026-10-20"}, timeout=10)
    missing = session.post(BASE + "/register", json={**payload,
                            "privacy_consent": False}, timeout=10)
    assert old.status_code == missing.status_code == 422
    registration = session.post(BASE + "/register", json=payload, timeout=15)
    assert registration.status_code == 201, registration.text[:200]
    csrf = registration.json()["csrf_token"]
    consent = session.get(BASE + "/privacy-consent", timeout=10)
    assert consent.status_code == 200 and consent.json()["policy_version"] == VERSION
    logout = session.post(BASE + "/logout", headers={"X-CSRF-Token": csrf}, timeout=10)
    assert logout.status_code == 204
    assert session.get(BASE + "/me", timeout=10).status_code == 401
    login = session.post(BASE + "/login", json={"email": email, "password": password}, timeout=15)
    assert login.status_code == 200
    assert session.get(BASE + "/me", timeout=10).status_code == 200
    result = {"source": "LOCAL_FASTAPI_PUBLISHED_BUNDLE_POSTGRESQL",
              "production_verified": False, "old_policy_status": old.status_code,
              "missing_consent_status": missing.status_code,
              "registration_status": registration.status_code,
              "consent_version": VERSION, "logout_status": logout.status_code,
              "login_status": login.status_code}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: old policy and missing consent rejected; register/consent/logout/login against local FastAPI")


if __name__ == "__main__":
    main()
