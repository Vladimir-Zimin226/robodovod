from __future__ import annotations

import inspect

import pytest
from fastapi import HTTPException

import main
from catalog_capacity_rollout import CapacitySourceStatusV1
from catalog_runtime import CatalogRuntimeConfigurationError
from test_catalog_runtime import _snapshot


def test_capacity_v2_route_is_bound_to_dedicated_capacity_snapshot():
    route = next(
        item
        for item in main.app.routes
        if getattr(item, "path", None) == "/api/v2/capacity-analyses"
        and "POST" in getattr(item, "methods", set())
    )
    bindings = inspect.getclosurevars(route.endpoint).nonlocals
    assert bindings["resolve_capacity_catalog"] is main._capacity_snapshot
    assert bindings["resolve_capacity_catalog"] is not main._discovery_snapshot


def test_capacity_snapshot_error_is_sanitized_and_keeps_reason_out_of_response(monkeypatch):
    class InvalidRuntime:
        def load_capacity(self):
            raise CatalogRuntimeConfigurationError(
                "private catalog detail", reason_code="CAPACITY_SOURCE_INVALID"
            )

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", InvalidRuntime())
    with pytest.raises(HTTPException) as error:
        main._capacity_snapshot()
    assert error.value.status_code == 503
    assert error.value.detail == "capacity source unavailable"


def test_catalog_status_exposes_versioned_capacity_availability(monkeypatch):
    snapshot = _snapshot(populated=True)

    class Runtime:
        def load_discovery(self):
            return snapshot

        def load_runtime(self):
            raise CatalogRuntimeConfigurationError("not active")

        def capacity_status(self):
            return CapacitySourceStatusV1(
                status="UNAVAILABLE",
                reason_code="CAPACITY_SOURCE_NOT_ACTIVE",
                catalog_code=None,
                pool_models=None,
                pool_positions=None,
            )

    monkeypatch.setattr(main, "_CATALOG_RUNTIME", Runtime())
    response = main.catalog_status()
    assert response["capacity"] == {
        "schema_version": "capacity-source-status-v1",
        "policy_version": "capacity-runtime-rollout-policy-v1",
        "status": "UNAVAILABLE",
        "reason_code": "CAPACITY_SOURCE_NOT_ACTIVE",
        "catalog_code": None,
        "pool_models": None,
        "pool_positions": None,
        "fallback_mode": "FAIL_CLOSED",
    }
    assert response["runtime"]["source"] == "unavailable"
