from __future__ import annotations

import catalog_runtime
import pytest
from catalog_repository import (
    CatalogRepositoryError,
    CatalogSnapshotDTO,
    CatalogVersionDTO,
    LegacyFleetCatalogRepository,
)
from catalog_runtime import CatalogRuntime, CatalogRuntimeConfigurationError


def test_runtime_uses_legacy_by_default(monkeypatch):
    monkeypatch.delenv("CATALOG_RUNTIME_SOURCE", raising=False)

    snapshot = CatalogRuntime(
        lambda: pytest.fail("database must not be used")
    ).load_runtime()

    assert snapshot.version.code == "legacy-fleet-v1"
    assert len(snapshot.runtime_robots()) == 13


def test_activated_runtime_is_explicit_and_fails_closed_without_models(monkeypatch):
    monkeypatch.setenv("CATALOG_RUNTIME_SOURCE", "activated")
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
    monkeypatch.setenv("CATALOG_RUNTIME_SOURCE", "activated")
    expected = LegacyFleetCatalogRepository().load()

    class ReadyRepository:
        def __init__(self, database, slot):
            assert slot == "runtime"

        def load(self):
            return expected

    monkeypatch.setattr(catalog_runtime, "ActivatedCatalogRepository", ReadyRepository)

    assert CatalogRuntime(lambda: object()).load_runtime() is expected


def test_discovery_falls_back_explicitly_when_slot_is_absent(monkeypatch):
    class MissingRepository:
        def __init__(self, database, slot):
            assert slot == "discovery"

        def load(self):
            raise CatalogRepositoryError("missing")

    monkeypatch.setattr(
        catalog_runtime, "ActivatedCatalogRepository", MissingRepository
    )

    snapshot, source = CatalogRuntime(lambda: object()).load_discovery()

    assert source == "legacy-fallback"
    assert snapshot.version.code == "legacy-fleet-v1"


def test_unknown_runtime_source_is_rejected(monkeypatch):
    monkeypatch.setenv("CATALOG_RUNTIME_SOURCE", "automatic")

    with pytest.raises(CatalogRuntimeConfigurationError, match="legacy or activated"):
        CatalogRuntime(lambda: object()).load_runtime()
