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
