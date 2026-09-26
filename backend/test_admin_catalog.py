"""F3 transaction/security/lifecycle acceptance against a disposable PostgreSQL."""

import copy
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import main
import pytest
from admin_catalog import project_document, validate_document
from alembic import command
from alembic.config import Config
from catalog_activation import activate_catalog_version, publish_catalog_version
from catalog_capacity_rollout import (
    CapacityRolloutPolicyError,
    validate_capacity_source,
)
from catalog_importer import run_catalog_import
from catalog_repository import PostgresCatalogRepository
from database import dispose_database, get_database
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import make_url
from test_persistence_integration import _create_project, _register

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="requires disposable TEST_DATABASE_URL")


@pytest.fixture(scope="module", autouse=True)
def storage():
    target = make_url(URL)
    assert target.host in {"127.0.0.1", "localhost"} and target.database in {
        "f1_tests", "f6_acceptance", "f8_acceptance",
    }, "only explicitly named local disposable test databases are permitted"
    patch = pytest.MonkeyPatch()
    patch.setenv("DATABASE_URL", URL)
    patch.setenv("SESSION_COOKIE_SECURE", "false")
    dispose_database()
    engine = create_engine(URL)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE catalog_versions, users CASCADE"))
    command.downgrade(Config(str(ROOT / "backend/alembic.ini")), "base")
    command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
    database = get_database()
    for phase in ("BASE", "ENRICHMENT"):
        run_catalog_import(
            database,
            ROOT / "data/import/organizer-catalog-v4",
            phase=phase,
            mode="COMMIT",
        )
    publish_catalog_version(database, "organizer-catalog-v4")
    activate_catalog_version(
        database, "organizer-catalog-v4", slot="discovery", actor_subject="f3-test"
    )
    yield engine
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE catalog_versions, users CASCADE"))
    engine.dispose()
    dispose_database()
    patch.undo()


@pytest.fixture
def admin(storage):
    client = TestClient(main.app)
    auth, headers = _register(client, f"admin-{uuid.uuid4()}@example.com")
    with storage.begin() as conn:
        conn.execute(
            text("UPDATE users SET role='ADMIN' WHERE id=:id"),
            {"id": auth["user"]["id"]},
        )
    yield client, headers
    client.close()


def draft(admin):
    client, headers = admin
    code = "f3-test-" + uuid.uuid4().hex
    response = client.post(
        "/api/admin/catalog/versions",
        headers=headers,
        json={"code": code, "parent_code": "organizer-catalog-v4"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def save(admin, record, document):
    client, headers = admin
    return client.put(
        f"/api/admin/catalog/versions/{record['code']}",
        headers=headers,
        json={"expected_revision": record["revision"], "document": document},
    )


def publish(admin, record):
    client, headers = admin
    url = f"/api/admin/catalog/versions/{record['code']}"
    checked = client.post(
        url + "/validate",
        headers=headers,
        json={"expected_revision": record["revision"]},
    )
    assert checked.status_code == 200, checked.text
    response = client.post(
        url + "/publish",
        headers=headers,
        json={"expected_revision": record["revision"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_guest_user_csrf_owner_and_published_db_guard(admin, storage):
    record = draft(admin)
    with TestClient(main.app) as guest:
        assert guest.get("/api/admin/catalog").status_code == 401
        assert (
            guest.post(
                "/api/admin/catalog/versions",
                json={"code": "new", "parent_code": "old"},
            ).status_code
            == 401
        )
    with TestClient(main.app) as user:
        _, headers = _register(user, f"user-{uuid.uuid4()}@example.com")
        assert user.get("/api/admin/catalog").status_code == 403
        assert (
            user.put(
                f"/api/admin/catalog/versions/{record['code']}",
                headers=headers,
                json={"expected_revision": 1, "document": record["document"]},
            ).status_code
            == 403
        )
    client, headers = admin
    assert (
        client.post(
            f"/api/admin/catalog/versions/{record['code']}/validate",
            json={"expected_revision": 1},
        ).status_code
        == 403
    )
    with TestClient(main.app) as other:
        auth, other_headers = _register(other, f"other-{uuid.uuid4()}@example.com")
        with storage.begin() as conn:
            conn.execute(
                text("UPDATE users SET role='ADMIN' WHERE id=:id"),
                {"id": auth["user"]["id"]},
            )
        assert (
            other.post(
                f"/api/admin/catalog/versions/{record['code']}/publish",
                headers=other_headers,
                json={"expected_revision": 1},
            ).status_code
            == 403
        )
    published = publish(admin, record)
    assert save(admin, published, published["document"]).status_code == 409
    with pytest.raises(SQLAlchemyError), storage.begin() as conn:
        conn.execute(
            text(
                "UPDATE admin_catalog_documents SET document='{}'::jsonb WHERE catalog_version_id=:id"
            ),
            {"id": published["id"]},
        )


def test_concurrent_edit_and_revalidation(admin):
    record = draft(admin)
    left, right = copy.deepcopy(record["document"]), copy.deepcopy(record["document"])
    left["models"][0]["name"] = "First concurrent edit"
    right["models"][0]["name"] = "Second concurrent edit"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda doc: save(admin, record, doc), (left, right)))
    assert sorted(response.status_code for response in results) == [200, 409]
    winner = next(
        response.json() for response in results if response.status_code == 200
    )
    client, headers = admin
    client.post(
        f"/api/admin/catalog/versions/{record['code']}/validate",
        headers=headers,
        json={"expected_revision": winner["revision"]},
    )
    changed = copy.deepcopy(winner["document"])
    changed["models"][0]["name"] += " after validation"
    edited = save(admin, winner, changed).json()
    assert (
        client.post(
            f"/api/admin/catalog/versions/{record['code']}/publish",
            headers=headers,
            json={"expected_revision": edited["revision"]},
        ).status_code
        == 409
    )
    assert publish(admin, edited)["status"] == "PUBLISHED"


def test_duplicate_offers_import_idempotence_diff_and_discovery(admin):
    record = draft(admin)
    doc = copy.deepcopy(record["document"])
    model = copy.deepcopy(doc["models"][0])
    model.update(key="new-model", name="F3 informational solution")
    doc["models"].append(model)
    offer = copy.deepcopy(doc["offers"][0])
    offer.update(key="new-offer-a", model_key="new-model", amount="123", currency="RUB")
    doc["offers"].extend([offer, {**offer, "key": "new-offer-b", "amount": "456"}])
    body = {
        "code": "f3-import-" + uuid.uuid4().hex,
        "parent_code": "organizer-catalog-v4",
        "document": doc,
    }
    client, headers = admin
    first = client.post("/api/admin/catalog/import", headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert first.json()["idempotent"] is False
    assert (
        client.post("/api/admin/catalog/import", headers=headers, json=body).json()[
            "idempotent"
        ]
        is True
    )
    conflict = copy.deepcopy(body)
    conflict["document"]["models"][-1]["name"] = "different"
    assert (
        client.post(
            "/api/admin/catalog/import", headers=headers, json=conflict
        ).status_code
        == 409
    )
    published = publish(admin, first.json())
    active = client.get("/api/admin/catalog").json()["active"]
    old = next(item["catalog_code"] for item in active if item["slot"] == "discovery")
    switched = client.post(
        f"/api/admin/catalog/versions/{published['code']}/activate",
        headers=headers,
        json={"slots": ["discovery"], "expected_active": {"discovery": old}},
    )
    assert switched.status_code == 200, switched.text
    items = client.get("/api/catalog/models?q=F3%20informational").json()["items"]
    assert len(items) == 2
    assert all(not item["calculation_ready"] for item in items)
    snapshot = PostgresCatalogRepository(get_database(), published["code"]).load()
    offers = [
        p.procurement_option.amount
        for p in snapshot.positions
        if p.model.source_record_key == "new-model"
    ]
    assert list(map(str, offers)) == ["123", "456"]
    validate_capacity_source(
        snapshot
    )  # informational additions cannot enter the approved pool


@pytest.mark.parametrize(
    "damage",
    [
        "unit",
        "unknown",
        "checkbox",
        "base",
        "locked_default",
        "currency",
        "duplicate",
        "source",
        "bounds",
    ],
)
def test_invalid_document_fails_atomically(admin, damage):
    record = draft(admin)
    doc = copy.deepcopy(record["document"])
    model = next(item for item in doc["models"] if item["specs"])
    spec = model["specs"][0]
    if damage == "unit":
        spec["unit"] = "incompatible-unit"
    if damage == "unknown":
        spec["value"] = None  # confirmed missing value is rejected
    if damage == "checkbox":
        model["calculation_ready"] = True
    if damage == "base":
        doc["base_content_sha256"] = "0" * 64
    if damage == "currency":
        doc["offers"][0]["currency"] = "ruble"
    if damage == "duplicate":
        doc["offers"].append(copy.deepcopy(doc["offers"][0]))
    if damage == "source":
        spec["source"] = "missing"
    if damage in {"locked_default", "bounds"}:
        doc["defaults"] = [
            {
                "key": "fleet_reserve"
                if damage == "locked_default"
                else "exchange_seconds",
                "value": "999999",
                "unit": "s",
                "lower": "1",
                "upper": "999999",
                "source": doc["sources"][0]["key"],
                "comment": "review",
            }
        ]
    assert save(admin, record, doc).status_code == 422
    current = admin[0].get(f"/api/admin/catalog/versions/{record['code']}").json()
    assert current["sha256"] == record["sha256"] and current["revision"] == 1


def test_changed_physical_fact_cannot_activate_capacity_and_compatible_restoration(
    admin,
):
    record = draft(admin)
    doc = copy.deepcopy(record["document"])
    root = PostgresCatalogRepository(get_database(), "organizer-catalog-v4").load()
    key = root.calculation_ready_models()[0].source_record_key
    model = next(item for item in doc["models"] if item["key"] == key)
    # Removing a required confirmed fact leaves unknown, not zero.
    model["specs"][0].update(value=None, status="UNKNOWN")
    response = save(admin, record, doc)
    assert response.status_code == 200, response.text
    changed = response.json()
    assert not changed["capacity_activation_ready"]
    projected = project_document(
        validate_document(doc, root),
        root,
        replace(root.version, schema_version="admin-catalog-v1"),
    )
    assert not projected.by_source_key()[key].capacity_runtime.calculation_ready
    with pytest.raises(CapacityRolloutPolicyError):
        validate_capacity_source(projected)
    restored = save(admin, changed, record["document"])
    assert restored.status_code == 200
    assert restored.json()["capacity_activation_ready"]


def test_sources_defaults_new_profile_only_and_audit(admin):
    record = draft(admin)
    doc = copy.deepcopy(record["document"])
    doc["sources"].append(
        {
            "key": "f3-review",
            "url": "https://example.com/spec",
            "document": "Local norm approval",
            "received_on": "2026-09-26",
            "updated_on": "2026-09-26",
            "comment": "reviewed",
        }
    )
    doc["defaults"] = [
        {
            "key": "exchange_seconds",
            "value": "40",
            "unit": "s",
            "lower": "1",
            "upper": "60",
            "source": "f3-review",
            "comment": "Scenario proposal, user confirmation required",
        }
    ]
    edited = save(admin, record, doc).json()
    published = publish(admin, edited)
    client, headers = admin
    active = client.get("/api/admin/catalog").json()["active"]
    old = next(item["catalog_code"] for item in active if item["slot"] == "discovery")
    response = client.post(
        f"/api/admin/catalog/versions/{published['code']}/activate",
        headers=headers,
        json={
            "slots": ["discovery", "capacity"],
            "expected_active": {"discovery": old, "capacity": None},
        },
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/catalog/defaults").json()["defaults"][0]["value"] == "40"
    project = _create_project(client, headers)
    original = client.get(f"/api/brain/projects/{project['id']}").json()
    original = client.post(
        f"/api/brain/projects/{project['id']}/edit",
        headers=headers,
        json={
            "expected_version": original["profile"]["profile_version"],
            "field": "exchange_seconds",
            "value": "30",
            "provenance": "expert_assumption",
            "confirmed": False,
        },
    ).json()
    original = client.get(f"/api/brain/projects/{project['id']}").json()
    result = client.post(
        f"/api/brain/projects/{project['id']}/catalog-default",
        headers=headers,
        json={
            "expected_version": original["profile"]["profile_version"],
            "catalog_code": published["code"],
            "field": "exchange_seconds",
        },
    )
    assert result.status_code == 200, result.text
    field = result.json()["profile"]["fields"]["exchange_seconds"]
    assert (
        field["value"] == "40"
        and not field["confirmed_by_user"]
        and field["provenance"] == "expert_assumption"
    )
    reloaded = client.get(f"/api/brain/projects/{project['id']}").json()
    assert reloaded["versions"][0] == original["versions"][0]
    assert field["catalog_default"]["catalog_code"] == published["code"]
    assert client.get("/api/admin/catalog/audit").json()["entries"]
    confirmed = client.post(
        f"/api/brain/projects/{project['id']}/confirm",
        headers=headers,
        json={
            "expected_version": result.json()["profile"]["profile_version"],
            "fields": ["exchange_seconds"],
            "preflight": False,
        },
    ).json()
    assert (
        client.post(
            f"/api/brain/projects/{project['id']}/catalog-default",
            headers=headers,
            json={
                "expected_version": confirmed["profile"]["profile_version"],
                "catalog_code": published["code"],
                "field": "exchange_seconds",
            },
        ).status_code
        == 409
    )


def test_atomic_switch_stale_pointer_and_rollback(admin):
    client, headers = admin
    record = publish(admin, draft(admin))
    active = {
        item["slot"]: item["catalog_code"]
        for item in client.get("/api/admin/catalog").json()["active"]
    }
    response = client.post(
        f"/api/admin/catalog/versions/{record['code']}/activate",
        headers=headers,
        json={
            "slots": ["discovery", "capacity"],
            "expected_active": {
                "discovery": "stale-version",
                "capacity": active.get("capacity"),
            },
        },
    )
    assert response.status_code == 409
    assert {
        item["slot"]: item["catalog_code"]
        for item in client.get("/api/admin/catalog").json()["active"]
    } == active
    response = client.post(
        f"/api/admin/catalog/versions/{record['code']}/activate",
        headers=headers,
        json={
            "slots": ["discovery", "capacity"],
            "expected_active": {
                "discovery": active["discovery"],
                "capacity": active.get("capacity"),
            },
        },
    )
    assert response.status_code == 200, response.text
    rollback = client.post(
        f"/api/admin/catalog/versions/{active['discovery']}/activate",
        headers=headers,
        json={"slots": ["discovery"], "expected_active": {"discovery": record["code"]}},
    )
    assert rollback.status_code == 200, rollback.text
    assert (
        client.get(f"/api/admin/catalog/versions/{record['code']}").json()["sha256"]
        == record["sha256"]
    )


def test_sources_defaults_section_api_revision_and_validation(admin):
    record = draft(admin)
    client, headers = admin
    url = f"/api/admin/catalog/versions/{record['code']}/sections/sources"
    sources = client.get(url).json()
    response = client.put(
        url,
        headers=headers,
        json={"expected_revision": sources["revision"], "entries": sources["entries"]},
    )
    assert response.status_code == 200 and response.json()["revision"] == 1
    locked = client.put(
        f"/api/admin/catalog/versions/{record['code']}/sections/defaults",
        headers=headers,
        json={
            "expected_revision": 1,
            "entries": [
                {
                    "key": "fleet_reserve",
                    "value": "1",
                    "unit": "ratio",
                    "lower": "0",
                    "upper": "1",
                    "source": sources["entries"][0]["key"],
                    "comment": "invalid locked constant",
                }
            ],
        },
    )
    assert locked.status_code == 422


def test_browser_json_number_roundtrip_preserves_approved_pool(admin):
    record = draft(admin)

    def javascript_numbers(value):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [javascript_numbers(item) for item in value]
        if isinstance(value, dict):
            return {key: javascript_numbers(item) for key, item in value.items()}
        return value

    response = save(admin, record, javascript_numbers(record["document"]))
    assert response.status_code == 200, response.text
    assert response.json()["capacity_activation_ready"]


def test_import_size_format_rejected(admin):
    client, headers = admin
    for payload in (
        b"not json",
        b"[]",
        b'{"code":"nope"}',
        b'{"code":"first","code":"second"}',
    ):
        assert (
            client.post(
                "/api/admin/catalog/import", headers=headers, content=payload
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/api/admin/catalog/import",
            headers=headers,
            content=b" " * (4 * 1024 * 1024 + 1),
        ).status_code
        == 413
    )
