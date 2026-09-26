"""Request-scoped selection of explicitly activated catalog snapshots."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from catalog_repository import (
    ActivatedCatalogRepository,
    CatalogRepositoryError,
    CatalogSnapshotDTO,
    PostgresCatalogRepository,
)
from database import Database, DatabaseConfigurationError, get_database
from catalog_capacity_rollout import (
    CapacityRolloutPolicyError,
    CapacitySourceStatusV1,
    validate_capacity_source,
)


class CatalogRuntimeConfigurationError(RuntimeError):
    """Raised when a configured runtime snapshot is unavailable or unsafe."""

    def __init__(self, message: str, *, reason_code: str = "CATALOG_SOURCE_UNAVAILABLE"):
        super().__init__(message)
        self.reason_code = reason_code


class CatalogRuntime:
    def __init__(
        self,
        database_factory: Callable[[], Database] = get_database,
    ) -> None:
        self._database_factory = database_factory
        self._cache: dict[str, tuple[Database, tuple[str, str, str], CatalogSnapshotDTO]] = {}
        self._cache_lock = Lock()

    def _load_slot(self, slot: str) -> CatalogSnapshotDTO:
        database = self._database_factory()
        repository = ActivatedCatalogRepository(database, slot)
        if not hasattr(repository, "active_identity"):
            return repository.load()
        identity = repository.active_identity()
        with self._cache_lock:
            cached = self._cache.get(slot)
            if cached is not None and cached[0] is database and cached[1] == identity:
                return cached[2]
            snapshot = PostgresCatalogRepository(database, identity[0]).load()
            self._cache[slot] = (database, identity, snapshot)
            return snapshot

    def load_runtime(self) -> CatalogSnapshotDTO:
        try:
            snapshot = self._load_slot("runtime")
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
            return self._load_slot("discovery")
        except (CatalogRepositoryError, DatabaseConfigurationError) as exc:
            raise CatalogRuntimeConfigurationError(
                "activated discovery catalog is unavailable"
            ) from exc

    def load_capacity(self) -> CatalogSnapshotDTO:
        """Load only the separately approved capacity source; never fall back."""

        try:
            snapshot = self._load_slot("capacity")
        except (CatalogRepositoryError, DatabaseConfigurationError) as exc:
            raise CatalogRuntimeConfigurationError(
                "activated capacity catalog is unavailable",
                reason_code="CAPACITY_SOURCE_NOT_ACTIVE",
            ) from exc
        try:
            validate_capacity_source(snapshot)
        except CapacityRolloutPolicyError as exc:
            raise CatalogRuntimeConfigurationError(
                "activated capacity catalog violates rollout policy",
                reason_code="CAPACITY_SOURCE_INVALID",
            ) from exc
        return snapshot

    def capacity_status(self) -> CapacitySourceStatusV1:
        try:
            snapshot = self.load_capacity()
        except CatalogRuntimeConfigurationError as exc:
            invalid = exc.reason_code == "CAPACITY_SOURCE_INVALID"
            return CapacitySourceStatusV1(
                status="INVALID" if invalid else "UNAVAILABLE",
                reason_code="CAPACITY_SOURCE_INVALID" if invalid else "CAPACITY_SOURCE_NOT_ACTIVE",
                catalog_code=None,
                pool_models=None,
                pool_positions=None,
            )
        return CapacitySourceStatusV1(
            status="ACTIVE",
            reason_code="ACTIVE_APPROVED_SOURCE",
            catalog_code=snapshot.version.code,
            pool_models=len(snapshot.calculation_ready_models()),
            pool_positions=len(snapshot.calculation_ready_positions()),
        )
