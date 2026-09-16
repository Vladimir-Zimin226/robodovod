"""Request-scoped catalog selection with an explicit legacy rollback switch."""

from __future__ import annotations

import os
from collections.abc import Callable

from catalog_repository import (
    ActivatedCatalogRepository,
    CatalogRepositoryError,
    CatalogSnapshotDTO,
    LegacyFleetCatalogRepository,
)
from database import Database, get_database


class CatalogRuntimeConfigurationError(RuntimeError):
    """Raised when a configured runtime snapshot is unavailable or unsafe."""


class CatalogRuntime:
    def __init__(
        self,
        database_factory: Callable[[], Database] = get_database,
    ) -> None:
        self._database_factory = database_factory

    @staticmethod
    def configured_source() -> str:
        source = os.getenv("CATALOG_RUNTIME_SOURCE", "legacy").strip().lower()
        if source not in {"legacy", "activated"}:
            raise CatalogRuntimeConfigurationError(
                "CATALOG_RUNTIME_SOURCE must be legacy or activated"
            )
        return source

    def load_runtime(self) -> CatalogSnapshotDTO:
        source = self.configured_source()
        if source == "legacy":
            return LegacyFleetCatalogRepository().load()
        try:
            snapshot = ActivatedCatalogRepository(
                self._database_factory(), "runtime"
            ).load()
        except CatalogRepositoryError as exc:
            raise CatalogRuntimeConfigurationError(
                "activated runtime catalog is unavailable"
            ) from exc
        if not snapshot.runtime_robots():
            raise CatalogRuntimeConfigurationError(
                "activated runtime catalog has no selectable models"
            )
        return snapshot

    def load_discovery(self) -> tuple[CatalogSnapshotDTO, str]:
        """Prefer the activated discovery slot and expose an explicit fallback."""

        try:
            return (
                ActivatedCatalogRepository(
                    self._database_factory(), "discovery"
                ).load(),
                "activated",
            )
        except CatalogRepositoryError:
            return LegacyFleetCatalogRepository().load(), "legacy-fallback"
