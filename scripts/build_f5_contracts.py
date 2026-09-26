"""Regenerate the additive F5 JSON Schemas without changing v2/v3 contracts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def expected_outputs() -> dict[Path, bytes]:
    from calculation.evidence_export import EvidenceExportManifestV4

    old = json.loads((ROOT / "contracts/commercial-scenarios-bundle-v2.schema.json").read_text(encoding="utf-8"))
    old["$id"] = "commercial-scenarios-bundle-v3.schema.json"
    old["properties"]["schema_version"]["const"] = "commercial-scenarios-bundle-v3"
    old["required"].append("comparison")
    old["properties"]["comparison"] = {"$ref": "#/$defs/finalComparison"}
    metric = {
        "type": "object", "additionalProperties": False,
        "required": ["status", "value", "unit", "basis", "source_ref", "reason"],
        "properties": {
            "status": {"enum": ["COMPLETE", "N_A", "NOT_REACHED", "INCOMPLETE"]},
            "value": {"type": ["string", "null"]},
            "unit": {"type": "string"}, "basis": {"type": "string"},
            "source_ref": {"type": "string"}, "reason": {"type": ["string", "null"]},
        },
    }
    old["$defs"]["finalMetric"] = metric
    old["$defs"]["finalScenario"] = {
        "type": "object", "additionalProperties": False,
        "required": ["scenario_id", "acquisition", "uncertainty", "metrics", "capital_lines", "annual_cashflows"],
        "properties": {
            "scenario_id": {"type": "string"}, "acquisition": {"enum": ["BASELINE", "PURCHASE", "RAAS"]},
            "uncertainty": {"enum": ["BASE", "PESSIMISTIC", "OPTIMISTIC"]},
            "metrics": {"type": "object", "additionalProperties": {"$ref": "#/$defs/finalMetric"}, "minProperties": 12},
            "capital_lines": {"type": "array", "items": {"type": "object"}},
            "annual_cashflows": {"type": "array", "minItems": 5, "items": {"type": "object"}},
        },
    }
    old["$defs"]["finalComparison"] = {
        "type": "object", "additionalProperties": False,
        "required": ["schema_version", "horizon_years", "currency", "baseline", "scenarios", "sensitivity", "inputs", "limitations"],
        "properties": {
            "schema_version": {"const": "financial-comparison-v1"},
            "horizon_years": {"type": "integer", "minimum": 5, "maximum": 15},
            "currency": {"const": "RUB"},
            "baseline": {"$ref": "#/$defs/finalScenario"},
            "scenarios": {"type": "array", "minItems": 6, "maxItems": 6, "items": {"$ref": "#/$defs/finalScenario"}},
            "sensitivity": {
                "type": "object", "additionalProperties": False,
                "required": ["schema_version", "by_scenario"],
                "properties": {
                    "schema_version": {"const": "scenario-sensitivity-v1"},
                    "by_scenario": {"type": "object", "minProperties": 7,
                                    "additionalProperties": {"type": "array", "minItems": 6, "maxItems": 6,
                                                             "items": {"type": "object"}}},
                },
            },
            "inputs": {"type": "object"},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
    }
    manifest = EvidenceExportManifestV4.model_json_schema()
    manifest["$id"] = "https://robomera.local/contracts/calculation-evidence-export-manifest-v4.schema.json"
    return {
        ROOT / "contracts/commercial-scenarios-bundle-v3.schema.json": (json.dumps(old, ensure_ascii=False, indent=2) + "\n").encode(),
        ROOT / "contracts/calculation-evidence-export-manifest-v4.schema.json": (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
    }


if __name__ == "__main__":
    for path, payload in expected_outputs().items():
        path.write_bytes(payload)
        print(path.relative_to(ROOT))
