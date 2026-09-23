from __future__ import annotations

import catalog_runtime
import pytest
from catalog_repository import (
    CatalogModelDTO,
    CatalogRepositoryError,
    CatalogSnapshotDTO,
    CatalogVersionDTO,
)
from catalog_runtime import CatalogRuntime, CatalogRuntimeConfigurationError


def _snapshot(*, populated: bool = False) -> CatalogSnapshotDTO:
    models = ()
    if populated:
        models = (
            CatalogModelDTO(
                id="catalog-model",
                source_namespace="tests",
                source_record_key="catalog-model",
                organizer_id=None,
                manufacturer=None,
                name="Catalog model",
                system_family="MOBILE_TRANSPORT",
                type_code="TEST",
                subtype_code=None,
                maturity_status=None,
                trl=None,
                description=None,
                attributes={},
                facts=(),
                applicability=(),
                procurement_options=(),
                runtime_robot={"id": "catalog-model"},
                runtime_blockers=(),
            ),
        )
    return CatalogSnapshotDTO(
        version=CatalogVersionDTO(
            id="00000000-0000-0000-0000-000000000001",
            code="catalog-ready-v1",
            status="PUBLISHED",
            schema_version="2",
        ),
        models=models,
    )


def test_runtime_uses_activated_slot_without_feature_flag(monkeypatch):
    expected = _snapshot(populated=True)

    class ReadyRepository:
        def __init__(self, database, slot):
            assert slot == "runtime"

        def load(self):
            return expected

    monkeypatch.setattr(catalog_runtime, "ActivatedCatalogRepository", ReadyRepository)
    snapshot = CatalogRuntime(lambda: object()).load_runtime()
    assert snapshot.version.code == "catalog-ready-v1"


def test_activated_runtime_fails_closed_without_models(monkeypatch):
    empty = CatalogSnapshotDTO(
        version=CatalogVersionDTO(
            id="00000000-0000-0000-0000-000000000001",
            code="published-empty",
            status="PUBLISHED",
            schema_version="2",
        ),
        models=(),
    )

    class EmptyRepository:
        def __init__(self, database, slot):
            assert slot == "runtime"

        def load(self):
            return empty

    monkeypatch.setattr(catalog_runtime, "ActivatedCatalogRepository", EmptyRepository)

    with pytest.raises(CatalogRuntimeConfigurationError, match="no selectable"):
        CatalogRuntime(lambda: object()).load_runtime()


def test_activated_runtime_returns_one_request_snapshot(monkeypatch):
    expected = _snapshot(populated=True)

    class ReadyRepository:
        def __init__(self, database, slot):
            assert slot == "runtime"

        def load(self):
            return expected

    monkeypatch.setattr(catalog_runtime, "ActivatedCatalogRepository", ReadyRepository)

    assert CatalogRuntime(lambda: object()).load_runtime() is expected


def test_discovery_fails_closed_when_slot_is_absent(monkeypatch):
    class MissingRepository:
        def __init__(self, database, slot):
            assert slot == "discovery"

        def load(self):
            raise CatalogRepositoryError("missing")

    monkeypatch.setattr(
        catalog_runtime, "ActivatedCatalogRepository", MissingRepository
    )

    with pytest.raises(CatalogRuntimeConfigurationError, match="discovery"):
        CatalogRuntime(lambda: object()).load_discovery()


def test_runtime_repository_errors_are_sanitized(monkeypatch):
    class MissingRepository:
        def __init__(self, database, slot):
            assert slot == "runtime"

        def load(self):
            raise CatalogRepositoryError("database detail")

    monkeypatch.setattr(catalog_runtime, "ActivatedCatalogRepository", MissingRepository)
    with pytest.raises(CatalogRuntimeConfigurationError, match="runtime catalog"):
        CatalogRuntime(lambda: object()).load_runtime()


def test_capacity_uses_its_own_slot_and_never_falls_back(monkeypatch):
    expected = _snapshot(populated=True)

    class CapacityRepository:
        def __init__(self, database, slot):
            assert slot == "capacity"

        def load(self):
            return expected

    monkeypatch.setattr(catalog_runtime, "ActivatedCatalogRepository", CapacityRepository)
    monkeypatch.setattr(catalog_runtime, "validate_capacity_source", lambda snapshot: None)
    runtime = CatalogRuntime(lambda: object())
    assert runtime.load_capacity() is expected
    assert runtime.capacity_status().status == "ACTIVE"


def test_capacity_missing_or_invalid_is_versioned_and_fail_closed(monkeypatch):
    class MissingRepository:
        def __init__(self, database, slot):
            assert slot == "capacity"

        def load(self):
            raise CatalogRepositoryError("private detail")

    monkeypatch.setattr(catalog_runtime, "ActivatedCatalogRepository", MissingRepository)
    runtime = CatalogRuntime(lambda: object())
    with pytest.raises(CatalogRuntimeConfigurationError) as error:
        runtime.load_capacity()
    assert error.value.reason_code == "CAPACITY_SOURCE_NOT_ACTIVE"
    assert runtime.capacity_status().model_dump() == {
        "schema_version": "capacity-source-status-v1",
        "policy_version": "capacity-runtime-rollout-policy-v1",
        "status": "UNAVAILABLE",
        "reason_code": "CAPACITY_SOURCE_NOT_ACTIVE",
        "catalog_code": None,
        "pool_models": None,
        "pool_positions": None,
        "fallback_mode": "FAIL_CLOSED",
    }
