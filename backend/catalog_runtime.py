"""Request-scoped selection of explicitly activated catalog snapshots."""

from __future__ import annotations

from collections.abc import Callable

from catalog_repository import (
    ActivatedCatalogRepository,
    CatalogRepositoryError,
    CatalogSnapshotDTO,
)
from database import Database, DatabaseConfigurationError, get_database


class CatalogRuntimeConfigurationError(RuntimeError):
    """Raised when a configured runtime snapshot is unavailable or unsafe."""


class CatalogRuntime:
    def __init__(
        self,
        database_factory: Callable[[], Database] = get_database,
    ) -> None:
        self._database_factory = database_factory

    def load_runtime(self) -> CatalogSnapshotDTO:
        try:
            snapshot = ActivatedCatalogRepository(
                self._database_factory(), "runtime"
            ).load()
        except (CatalogRepositoryError, DatabaseConfigurationError) as exc:
            raise CatalogRuntimeConfigurationError(
                "activated runtime catalog is unavailable"
            ) from exc
        if not snapshot.runtime_robots():
            raise CatalogRuntimeConfigurationError(
                "activated runtime catalog has no selectable models"
            )
        return snapshot

    def load_discovery(self) -> CatalogSnapshotDTO:
        try:
            return ActivatedCatalogRepository(
                self._database_factory(), "discovery"
            ).load()
        except (CatalogRepositoryError, DatabaseConfigurationError) as exc:
            raise CatalogRuntimeConfigurationError(
                "activated discovery catalog is unavailable"
            ) from exc
