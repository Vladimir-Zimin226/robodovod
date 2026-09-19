"""Synthetic equipment used by engine unit tests.

These records are deliberately not importable by production catalog code and
must never be treated as catalog, vendor, pricing, or runtime facts.
"""

from __future__ import annotations

import copy

from catalog_repository import CatalogModelDTO, CatalogSnapshotDTO, CatalogVersionDTO


def _robot(
    robot_id: str,
    category: str,
    *,
    payload: float,
    speed: float,
    aisle: float,
    object_types: list[str],
    cargo: list[str],
    cleaning_rate: float | None = None,
) -> dict:
    specs = {
        "payload_kg": payload,
        "max_speed_m_s": speed,
        "min_aisle_width_m": aisle,
        "autonomy_hours": 8.0,
        "navigation_type": "SYNTHETIC_TEST_NAVIGATION",
    }
    if cleaning_rate is not None:
        specs["cleaning_rate_m2_h"] = cleaning_rate
    return {
        "id": robot_id,
        "category": category,
        "type_label": "Synthetic test equipment",
        "object_types": object_types,
        "name": robot_id,
        "description": "Synthetic record for deterministic engine tests only.",
        "purpose": ["Engine unit tests", "Contract regression tests"],
        "specs": specs,
        "compatible_cargo": cargo,
        "transport_profile": {"units_per_trip": 1, "exchange_time_s": 45},
        "economics": {
            "robot_capex_rub": 5_000_000,
            "charger_cost_rub": 300_000,
            "chargers_per_robot": 0.34,
            "integration_per_robot_rub": 600_000,
            "site_fixed_warehouse_rub": 1_200_000,
            "site_fixed_zone_rub": 300_000,
            "annual_service_rub": 250_000,
            "annual_software_rub": 100_000,
            "avg_power_w": 300,
            "battery_cost_rub": 300_000,
            "battery_cycles": 3_000,
            "runtime_h": 8,
            "fte_replace_per_shift": 1.2,
            "residual_share": 0.35,
        },
        "price": {
            "basis": "synthetic_test_value",
            "confidence": 1.0,
            "note": "Not a market or vendor value.",
        },
        "visual_profile": {
            "internal_mobile": "pallet-amr",
            "service_delivery": "service-delivery",
            "cleaning_robot": "service-cleaner",
            "fixed_cell": "palletizer-cell",
        }.get(category, category),
    }


_ROBOTS = (
    _robot(
        "synthetic-transport-light",
        "internal_mobile",
        payload=250,
        speed=1.2,
        aisle=0.8,
        object_types=["retail", "other"],
        cargo=["pallets", "boxes"],
    ),
    _robot(
        "synthetic-transport-heavy",
        "internal_mobile",
        payload=1_350,
        speed=1.0,
        aisle=1.5,
        object_types=["retail", "airport", "other"],
        cargo=["pallets", "boxes", "carts"],
    ),
    _robot(
        "synthetic-delivery",
        "service_delivery",
        payload=15,
        speed=0.9,
        aisle=0.7,
        object_types=["clinic", "other"],
        cargo=["deliveries"],
    ),
    _robot(
        "synthetic-cleaner",
        "cleaning_robot",
        payload=0,
        speed=1.0,
        aisle=0.9,
        object_types=["airport", "clinic", "other"],
        cargo=[],
        cleaning_rate=850,
    ),
)


def synthetic_robots() -> list[dict]:
    return copy.deepcopy(list(_ROBOTS))


def synthetic_robot(kind: str = "heavy") -> dict:
    index = {"light": 0, "heavy": 1, "delivery": 2, "cleaner": 3}[kind]
    return copy.deepcopy(_ROBOTS[index])


def synthetic_snapshot() -> CatalogSnapshotDTO:
    models = tuple(
        CatalogModelDTO(
            id=robot["id"],
            source_namespace="synthetic-tests",
            source_record_key=robot["id"],
            organizer_id=None,
            manufacturer=None,
            name=robot["name"],
            system_family=robot["category"],
            type_code=robot["type_label"],
            subtype_code=None,
            maturity_status=None,
            trl=None,
            description=robot["description"],
            attributes={"test_only": True},
            facts=(),
            applicability=(),
            procurement_options=(),
            runtime_robot=copy.deepcopy(robot),
            runtime_blockers=(),
        )
        for robot in _ROBOTS
    )
    return CatalogSnapshotDTO(
        version=CatalogVersionDTO(
            id="synthetic-tests-v1",
            code="synthetic-tests-v1",
            status="TEST_ONLY",
            schema_version="test-only-v1",
        ),
        models=models,
    )
