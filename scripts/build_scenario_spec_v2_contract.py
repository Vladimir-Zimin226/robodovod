"""Generate the committed ScenarioSpec v2 JSON Schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation_contracts import semantic_digest  # noqa: E402
from scenario_spec_v2 import ScenarioSpecV2  # noqa: E402


TARGET = ROOT / "contracts" / "scenario-spec-v2.schema.json"
FIXTURE_TARGET = ROOT / "contracts" / "fixtures" / "scenario-spec-v2.capacity-only-cleaner.golden.json"


def expected_bytes() -> bytes:
    schema = ScenarioSpecV2.model_json_schema(
        ref_template="#/$defs/{model}",
        mode="serialization",
    )
    schema["$id"] = "https://robomera.local/contracts/scenario-spec-v2.schema.json"
    schema["title"] = "Robomera ScenarioSpec v2"
    return (json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def fixture_bytes() -> bytes:
    digest_a = "sha256:" + "a" * 64
    digest_b = "sha256:" + "b" * 64
    digest_c = "sha256:" + "c" * 64
    body = {
        "schema_version": "scenario-spec-v2",
        "source": "capacity-analysis",
        "template": "airport",
        "seed": "scenario-0000000000000000",
        "analysis": {
            "project_id": "project.c22.cleaner", "tenant_id": "tenant.c22",
            "capacity_run_id": "run.c22.cleaner", "input_revision": "revision.c22.cleaner",
            "capacity_request_digest": digest_a, "capacity_result_digest": digest_b,
            "capacity_trace_digest": digest_c,
        },
        "versions": {
            "scenario_contract_version": "scenario-spec-v2",
            "scenario_policy_version": "scenario-spec-policy-v2",
            "capacity_result_version": "capacity-result-v1",
            "capacity_trace_version": "calculation-trace-v1",
            "calculation": {
                "catalog_version_id": "catalog.c22", "catalog_content_digest": digest_a,
                "capacity_projection_version": "formula-executability-profiles-v3",
                "capacity_projection_digest": digest_b,
                "registry_version": "hackathon-calculation-parameter-registry-v1",
                "registry_digest": digest_c,
                "process_catalog_version": "calculation-process-catalog-v1",
                "formula_bundle_version": "calculation-formulas-v1",
                "constraint_rules_version": "calculation-constraint-rules-v2",
                "commercial_policy_version": "hackathon-commercial-policy-v1",
                "precision_policy_version": "decimal-context-28-half-even-v1",
                "calculation_policy_version": "hackathon-calculation-policy-v1",
            },
        },
        "profile": {
            "process_id": "process.airport.cleaning", "process_code": "airport_terminal_cleaning",
            "process_scope": "CLEANING_AREA", "calculation_profile": "CLEANING_AREA_V1",
            "quantity_kind": "SQUARE_METER", "capacity_status": "WITH_ASSUMPTIONS",
        },
        "operating_windows": [{
            "window_id": "window.day", "start_time": {"value": "0", "unit": "s", "quantity_kind": "TIME", "numeric_encoding": "DECIMAL_STRING"},
            "duration": {"value": "24", "unit": "h", "quantity_kind": "TIME", "numeric_encoding": "DECIMAL_STRING"},
            "timezone": "Europe/Moscow", "source": "PRESET", "provenance_ref": "prov.schedule",
        }],
        "zones": [{
            "zone_id": "zone.terminal", "label": "Терминал", "geometry_source": "SYNTHETIC",
            "geometry_ref": None, "assumption_ref": "assumption.synthetic-geometry",
        }],
        "routes": [],
        "fleet": [{
            "fleet_id": "fleet.process.airport.cleaning", "zone_id": "zone.terminal",
            "process_id": "process.airport.cleaning", "model_id": "model.cleaner",
            "position_id": "position.cleaner", "selected_fleet": 4, "recommended_fleet": 4,
            "nominal_capacity": {"value": "76800", "unit": "m2/day", "quantity_kind": "FLOW", "numeric_encoding": "DECIMAL_STRING"},
            "effective_capacity": {"value": "53760", "unit": "m2/day", "quantity_kind": "FLOW", "numeric_encoding": "DECIMAL_STRING"},
            "coverage": {"value": "1", "unit": "1", "quantity_kind": "FRACTION", "numeric_encoding": "DECIMAL_STRING"},
            "raw_load_ratio": {"value": "0.9486607142857142857142857143", "unit": "1", "quantity_kind": "FRACTION", "numeric_encoding": "DECIMAL_STRING"},
            "utilization": {"value": "0.9486607142857142857142857143", "unit": "1", "quantity_kind": "FRACTION", "numeric_encoding": "DECIMAL_STRING"},
            "overloaded": False,
        }],
        "tasks": [{
            "task_id": "task.process.airport.cleaning", "zone_id": "zone.terminal",
            "process_id": "process.airport.cleaning",
            "demand": {"value": "51000", "unit": "m2/day", "quantity_kind": "FLOW", "numeric_encoding": "DECIMAL_STRING"},
            "operating_window_refs": ["window.day"], "exchange": {"mode": "NOT_APPLICABLE", "total_time": None, "load_time": None, "unload_time": None},
            "batch": {"semantics": "AREA_MICROTASK", "units_per_cycle": {"value": "100", "unit": "m2", "quantity_kind": "AREA", "numeric_encoding": "DECIMAL_STRING"}, "provenance_ref": "prov.simulation-area-batch"},
            "route_ref": None,
        }],
        "finance": None,
        "assumptions": [{
            "assumption_id": "assumption.synthetic-geometry", "version": "synthetic-geometry-v1",
            "provenance_ref": "prov.synthetic-geometry", "scope": "VISUALIZATION_ONLY",
            "message": "Синтетическая геометрия не заменяет расчётный маршрут или обследование объекта.",
        }],
        "trace_node_refs": ["node.f05.cleaning-rate", "node.f07.coverage"],
        "warnings": ["Финансовый snapshot отсутствует; capacity остаётся воспроизводимым."],
    }
    seed_digest = semantic_digest(body).removeprefix("sha256:")
    body["seed"] = f"scenario-{seed_digest[:16]}"
    revision_digest = semantic_digest(body).removeprefix("sha256:")
    payload = ScenarioSpecV2(revision_id=f"calc_{revision_digest[:16]}", **body).model_dump(mode="json")
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def expected_files() -> tuple[tuple[Path, bytes], ...]:
    return ((TARGET, expected_bytes()), (FIXTURE_TARGET, fixture_bytes()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return 0 if all(path.is_file() and path.read_bytes() == expected for path, expected in expected_files()) else 1
    for path, expected in expected_files():
        path.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
