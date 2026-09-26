from __future__ import annotations

import os
from copy import deepcopy

import main
import pytest
from fastapi.testclient import TestClient
from project_workbook import build_workbook
from test_persistence_integration import (  # noqa: F401
    _create_project,
    _register,
    clean_persistence,
    migrated_database,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="disposable PostgreSQL required"
)


def test_guest_templates_preview_versions_confirmation_and_tenant_isolation():
    with TestClient(main.app) as guest:
        for profile in ["warehouse", "airport", "medical_facility"]:
            for variant, extension in [
                ("blank", "xlsx"),
                ("demo", "xlsx"),
                ("blank", "csv"),
                ("interview", "txt"),
            ]:
                result = guest.get(
                    f"/api/project-workbooks/{profile}/{variant}.{extension}"
                )
                assert result.status_code == 200 and len(result.content) > 100
        assert guest.get("/api/project-workbooks/fake/blank.xlsx").status_code == 404
    with TestClient(main.app) as owner, TestClient(main.app) as other:
        _, headers = _register(owner, "workbook-owner@example.com")
        _, intruder = _register(other, "workbook-other@example.com")
        project = _create_project(owner, headers)
        pid = project["id"]
        endpoint = f"/api/projects/{pid}/files"
        name, payload = build_workbook("warehouse", True)
        files = {
            "file": (
                name,
                payload,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        data = {"profile_code": "warehouse"}
        before = owner.get(f"/api/projects/{pid}").json()
        preview = owner.post(endpoint + "/preview", data=data, files=files)
        assert preview.status_code == 200 and preview.json()["valid"]
        assert (
            preview.json()["diff"]
            and preview.json()["previous_import_id"] == "__none__"
        )
        assert owner.get(f"/api/projects/{pid}").json() == before
        stale_profile = owner.post(
            endpoint + "/apply",
            data={
                "profile_code": "warehouse",
                "scenario_id": next(
                    s["id"] for s in project["scenarios"] if s["slot"] == "BASE"
                ),
                "expected_profile_sha256": "0" * 64,
            },
            files=files,
            headers=headers,
        )
        assert stale_profile.status_code == 409
        wrong_file = owner.post(
            endpoint + "/apply",
            data={
                "profile_code": "warehouse",
                "scenario_id": next(
                    s["id"] for s in project["scenarios"] if s["slot"] == "BASE"
                ),
                "expected_file_sha256": "0" * 64,
            },
            files=files,
            headers=headers,
        )
        assert wrong_file.status_code == 409
        data.update(
            scenario_id=next(
                s["id"] for s in project["scenarios"] if s["slot"] == "BASE"
            ),
            expected_import_id="__none__",
        )
        assert (
            other.post(
                endpoint + "/apply", data=data, files=files, headers=intruder
            ).status_code
            == 404
        )
        assert (
            owner.post(endpoint + "/apply", data=data, files=files).status_code == 403
        )
        applied = owner.post(
            endpoint + "/apply", data=data, files=files, headers=headers
        )
        assert applied.status_code == 201, applied.text
        first_id = applied.json()["import"]["id"]
        brain = owner.get(f"/api/brain/projects/{pid}").json()
        assert (
            brain["profile"]["profile_version"] == 1
            and not brain["profile"]["preflight_confirmed"]
        )
        assert all(
            not f["confirmed_by_user"] for f in brain["profile"]["fields"].values()
        )
        original = deepcopy(brain["versions"][0])
        assert (
            owner.post(
                endpoint + "/apply", data=data, files=files, headers=headers
            ).status_code
            == 409
        )
        bad = owner.post(
            endpoint + "/apply",
            data={**data, "expected_import_id": first_id},
            files={
                "file": ("invalid.csv", b"schema_version,invalid\nabc,def", "text/csv")
            },
            headers=headers,
        )
        assert bad.status_code == 422
        assert owner.get(f"/api/brain/projects/{pid}").json()["profile"] == original
        assert (
            owner.post(
                endpoint + "/apply",
                data={**data, "expected_import_id": first_id},
                files=files,
                headers=headers,
            ).status_code
            == 201
        )
        brain = owner.get(f"/api/brain/projects/{pid}").json()
        assert (
            brain["profile"]["profile_version"] == 2
            and brain["versions"][0] == original
        )
        assert (
            owner.get(endpoint).json()["items"][0]["import"]["normalized_input"][
                "records"
            ]["Экономика"]["main"]["discount_rate"]["value"]
            == "0.15"
        )
