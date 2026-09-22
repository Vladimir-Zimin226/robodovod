from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation.process_profiles.catalog import ProcessProfileCatalogV1  # noqa: E402
from calculation.process_profiles.router import ProcessRouteDecisionV1  # noqa: E402
from calculation.process_profiles.user_cycle import (  # noqa: E402
    UserCycleCapacityResultV1,
    UserCycleRequestV1,
)
from calculation_contracts import semantic_digest  # noqa: E402

CATALOG_PATH = ROOT / "data/calculation/process-profile-catalog-v1.json"
SCHEMA_PATH = ROOT / "contracts/process-profile-catalog-v1.schema.json"
COVERAGE_PATH = ROOT / "data/review/process-profile-coverage-v1.json"
ROUTE_SCHEMA_PATH = ROOT / "contracts/process-route-decision-v1.schema.json"
USER_CYCLE_REQUEST_SCHEMA_PATH = ROOT / "contracts/user-cycle-request-v1.schema.json"
USER_CYCLE_RESULT_SCHEMA_PATH = ROOT / "contracts/user-cycle-capacity-result-v1.schema.json"


def _row(index, code, obj, scope, roles, kinds, handler, note, *, checks=()):
    requirements = {
        "TRANSPORT": ["DEMAND", "SCHEDULE", "ROUTE", "BATCH"],
        "CLEANING": ["DEMAND", "SCHEDULE", "AREA", "FREQUENCY"],
        "PALLETIZING": ["DEMAND", "SCHEDULE", "CELL_RATE"],
        "NONE": ["CONSTRAINT_CONTEXT"] if scope == "CONSTRAINT_ONLY" else ["DISCOVERY_INPUTS"],
    }[handler]
    formulas = {
        "TRANSPORT": ["F01", "F02", "F03", "F04", "F07"],
        "CLEANING": ["F01", "F05", "F07"],
        "PALLETIZING": ["F01", "F06", "F07"],
        "NONE": [],
    }[handler]
    base_checks = ["object-kind", "process-scope", "passport-availability"]
    handler_checks = {
        "TRANSPORT": ["cargo", "payload", "aisle", "route-floors", "temperature", "slope", "availability"],
        "CLEANING": ["cleanable-surface", "floor-covering", "noise", "availability"],
        "PALLETIZING": ["cargo", "payload", "aisle", "availability"],
        "NONE": [],
    }[handler]
    required_codes = [f"requirement.{item.lower().replace('_', '-')}" for item in requirements]
    error_codes = [f"error.missing-{item.lower().replace('_', '-')}" for item in requirements]
    unsupported = None
    user_cycle = False
    if scope == "REFERENCE_ONLY":
        unsupported = f"unsupported-{code.replace('_', '-')}-physical-profile"
        user_cycle = True
    elif scope == "CONSTRAINT_ONLY":
        unsupported = "constraint-only-no-fleet"
    return {
        "microstage_id": f"C10.{index:02d}",
        "process_code": code,
        "object_kind": obj,
        "scope": scope,
        "capacity_handler": handler,
        "default_role_codes": roles,
        "allowed_quantity_kinds": kinds,
        "has_fot_savings": bool(roles),
        "formula_ids": formulas,
        "required_inputs": requirements,
        "applicable_checks": list(dict.fromkeys([*base_checks, *handler_checks, *checks])),
        "requirement_codes": required_codes,
        "error_codes": error_codes,
        "user_cycle_allowed": user_cycle,
        "unsupported_reason_code": unsupported,
        "ui": {
            "label_key": f"process.{code}.label",
            "description_key": f"process.{code}.description",
            "demand_label_key": f"process.{code}.demand",
            "show_capacity_action": handler != "NONE",
        },
        "source_refs": ["POLICY_V1:K19", "R10:intake", "R11:logic", f"C10.{index:02d}"],
        "decision_refs": ["K15", "K19"],
        "note": note,
    }


def build_catalog() -> ProcessProfileCatalogV1:
    rows = [
        _row(1, "warehouse_receiving_shipping", "WAREHOUSE", "TRANSPORT_CYCLE", ["forklift_driver", "loader"], ["PALLET"], "TRANSPORT", "Inbound/outbound stay separate; only total fleet may sum their daily pallet demand."),
        _row(2, "warehouse_storage", "WAREHOUSE", "REFERENCE_ONLY", ["storekeeper"], ["PALLET"], "NONE", "Vertical/lift storage has no accepted physical formula; floor cycle requires explicit USER_CYCLE.", checks=["lift-height", "ceiling-clearance"]),
        _row(3, "warehouse_picking", "WAREHOUSE", "REFERENCE_ONLY", ["picker", "sorter"], ["PICK", "BOX"], "NONE", "Full picking is reference-only; a transport suboperation is configured separately."),
        _row(4, "warehouse_palletizing", "WAREHOUSE", "FIXED_CELL", ["packer"], ["PALLET", "CASE"], "PALLETIZING", "F06 covers pallet output; packaging motion remains outside the formula."),
        _row(5, "warehouse_cleaning", "WAREHOUSE", "CLEANING_AREA", ["cleaner"], ["SQUARE_METER"], "CLEANING", "C08 requires explicit area and frequency."),
        _row(6, "warehouse_inventory", "WAREHOUSE", "REFERENCE_ONLY", ["inventory_worker"], ["ITEM"], "NONE", "Scan quantity/rate is preserved for discovery; no accepted inventory formula."),
        _row(7, "airport_baggage", "AIRPORT", "TRANSPORT_CYCLE", ["baggage_handler"], ["ITEM", "CART"], "TRANSPORT", "Bags per cart and route are explicit; item and cart dimensions are not interchangeable.", checks=["airside", "restricted-zone"]),
        _row(8, "airport_catering", "AIRPORT", "TRANSPORT_CYCLE", ["trolley_operator"], ["PORTION", "BOX", "KILOGRAM"], "TRANSPORT", "Portion/box/weight per cart requires explicit dimensional conversion.", checks=["airside", "restricted-zone"]),
        _row(9, "airport_fuelling", "AIRPORT", "REFERENCE_ONLY", ["special_equipment_driver"], ["DELIVERY"], "NONE", "Fuel volume/rate/safety has no accepted fleet formula.", checks=["airside", "apron", "restricted-zone"]),
        _row(10, "airport_internal_logistics", "AIRPORT", "TRANSPORT_CYCLE", ["trolley_operator"], ["CART", "DELIVERY"], "TRANSPORT", "C07 applies only after explicit cargo, batch, and route mapping.", checks=["airside", "restricted-zone"]),
        _row(11, "airport_terminal_cleaning", "AIRPORT", "CLEANING_AREA", ["terminal_cleaner"], ["SQUARE_METER"], "CLEANING", "The 51000 m2 robotized area is explicitly derived from 85000 × 0.6.", checks=["restricted-zone"]),
        _row(12, "airport_apron_cleaning", "AIRPORT", "CLEANING_AREA", ["perron_cleaner"], ["SQUARE_METER"], "CLEANING", "C08 needs outdoor/apron-compatible facts and requirements.", checks=["airside", "apron", "outdoor"]),
        _row(13, "airport_waste", "AIRPORT", "TRANSPORT_CYCLE", ["trolley_operator"], ["KILOGRAM", "BIN"], "TRANSPORT", "Kilograms per bin/trip are explicit; no mass-to-bin guess.", checks=["airside", "restricted-zone"]),
        _row(14, "airport_inspection", "AIRPORT", "REFERENCE_ONLY", ["runway_inspector", "security_guard"], ["ITEM"], "NONE", "Scan coverage/rate is unknown; BAS remains outside the pool.", checks=["airside", "apron", "outdoor"]),
        _row(15, "airport_passenger_assistance", "AIRPORT", "REFERENCE_ONLY", ["passenger_assistant", "courier"], ["DELIVERY"], "NONE", "Passenger service and SLA have no accepted physical capacity formula.", checks=["restricted-zone"]),
        _row(16, "airport_ground_service", "AIRPORT", "REFERENCE_ONLY", ["ramp_worker", "ground_support_worker"], ["DELIVERY"], "NONE", "Ground service is an operation set; transport suboperations are separate processes.", checks=["airside", "apron"]),
        _row(17, "clinic_food", "CLINIC", "DELIVERY_CYCLE", ["catering_worker"], ["PORTION"], "TRANSPORT", "Portions per cart are explicit; SLA 20 minutes is evaluated later.", checks=["restricted-zone", "sanitization"]),
        _row(18, "clinic_linen", "CLINIC", "DELIVERY_CYCLE", ["laundry_worker"], ["KILOGRAM"], "TRANSPORT", "Clean and dirty flows remain separate; kg per container is explicit.", checks=["restricted-zone", "sanitization"]),
        _row(19, "clinic_medicines", "CLINIC", "DELIVERY_CYCLE", ["sanitary", "porter"], ["DELIVERY", "ITEM"], "TRANSPORT", "Deliveries/day or items/container need explicit batch and route.", checks=["restricted-zone", "access-protocols"]),
        _row(20, "clinic_biomaterials", "CLINIC", "DELIVERY_CYCLE", ["lab_assistant"], ["SAMPLE"], "TRANSPORT", "Samples per container are explicit; SLA 30 minutes is evaluated later.", checks=["restricted-zone", "sanitization", "access-protocols"]),
        _row(21, "clinic_sterile_sets", "CLINIC", "DELIVERY_CYCLE", ["sterile_supply_worker"], ["SET"], "TRANSPORT", "Sets per container are explicit and sterilization scope is checked.", checks=["restricted-zone", "sanitization"]),
        _row(22, "clinic_consumables", "CLINIC", "DELIVERY_CYCLE", ["consumable_worker"], ["ITEM"], "TRANSPORT", "Item batch and route are explicit.", checks=["restricted-zone"]),
        _row(23, "clinic_waste_a", "CLINIC", "DELIVERY_CYCLE", ["sanitary", "porter"], ["KILOGRAM"], "TRANSPORT", "Kilograms per container and sanitation are explicit.", checks=["restricted-zone", "sanitization", "material-disinfection"]),
        _row(24, "clinic_waste_b", "CLINIC", "DELIVERY_CYCLE", ["sanitary", "porter"], ["KILOGRAM"], "TRANSPORT", "Class-B containment/sanitization applies; explosion protection is not assumed.", checks=["restricted-zone", "sanitization", "class-b-containment", "material-disinfection"]),
        _row(25, "clinic_results", "CLINIC", "DELIVERY_CYCLE", ["lab_result_courier"], ["DELIVERY", "DIGITAL_FLOW"], "TRANSPORT", "Physical delivery can use C07; digital flow has no physical fleet."),
        _row(26, "clinic_cleaning", "CLINIC", "CLEANING_AREA", ["cleaner"], ["SQUARE_METER"], "CLEANING", "C08 applies with noise, time, cleanable-surface and material requirements.", checks=["restricted-zone", "sanitization", "material-disinfection"]),
        _row(27, "clinic_inventory", "CLINIC", "REFERENCE_ONLY", ["inventory_worker"], ["ITEM"], "NONE", "Scan throughput is not available; discovery and constraints remain visible."),
        _row(28, "clinic_safety_requirements", "CLINIC", "CONSTRAINT_ONLY", [], ["ITEM"], "NONE", "Safety requirements constrain other processes and never size an independent fleet.", checks=["restricted-zone", "sanitization", "class-b-containment", "cleanable-surface", "material-disinfection", "access-protocols"]),
    ]
    return ProcessProfileCatalogV1(profiles=rows)


def _bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def expected_files():
    catalog = build_catalog()
    coverage = {
        "schema_version": "process-profile-coverage-v1",
        "catalog_version": catalog.catalog_version,
        "catalog_digest": semantic_digest(catalog),
        "profile_count": len(catalog.profiles),
        "object_counts": {obj: sum(row.object_kind == obj for row in catalog.profiles) for obj in ("WAREHOUSE", "AIRPORT", "CLINIC")},
        "scope_counts": {scope: sum(row.scope == scope for row in catalog.profiles) for scope in sorted({row.scope for row in catalog.profiles})},
        "handler_counts": {handler: sum(row.capacity_handler == handler for row in catalog.profiles) for handler in ("TRANSPORT", "CLEANING", "PALLETIZING", "NONE")},
        "microstages": [row.microstage_id for row in catalog.profiles],
        "candidate_pool_models": 21,
        "candidate_pool_positions": 24,
        "pool_membership_changed": False,
    }
    return (
        (CATALOG_PATH, _bytes(catalog.model_dump(mode="json"))),
        (SCHEMA_PATH, _bytes(ProcessProfileCatalogV1.model_json_schema())),
        (COVERAGE_PATH, _bytes(coverage)),
        (ROUTE_SCHEMA_PATH, _bytes(ProcessRouteDecisionV1.model_json_schema())),
        (USER_CYCLE_REQUEST_SCHEMA_PATH, _bytes(UserCycleRequestV1.model_json_schema())),
        (USER_CYCLE_RESULT_SCHEMA_PATH, _bytes(UserCycleCapacityResultV1.model_json_schema())),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = expected_files()
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, content in expected if not path.is_file() or path.read_bytes() != content]
        if stale:
            raise SystemExit("generated process profiles differ: " + ", ".join(stale))
        return 0
    for path, content in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
