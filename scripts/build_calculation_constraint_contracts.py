"""Build/check C05 constraint schemas and profile golden fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.constraints import (
    ConstraintEvaluationRequest,
    ConstraintReportV2,
    ConstraintRules,
    evaluate_constraints,
    load_constraint_rules,
)


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _evidence(fields: list[str], profile: str) -> dict[str, dict[str, str]]:
    return {
        field: {
            "evidence_status": "MATCHING_SAFE",
            "source_ref": f"catalog:{profile}:{field}",
            "fact_id": f"fact.{profile}.{field.replace('_', '-')}",
        }
        for field in fields
    }


def _fixture(profile: str) -> ConstraintEvaluationRequest:
    common_candidate = {
        "model_id": f"model.{profile}",
        "position_id": f"position.{profile}",
        "availability": "0.9",
        "technical_passport_available": True,
    }
    if profile == "warehouse":
        context = {
            "object_kind": "WAREHOUSE",
            "route_zones": ["receiving", "storage"],
            "route_floors": [1],
            "max_payload_kg": "500",
            "min_aisle_width_m": "2.2",
            "requirement_sources": {
                "max_payload_kg": {"kind": "FILE", "source_ref": "input:warehouse:payload"},
                "min_aisle_width_m": {"kind": "FILE", "source_ref": "input:warehouse:aisle"},
            },
        }
        candidate = {
            **common_candidate,
            "supported_object_kinds": ["WAREHOUSE"],
            "supported_process_scopes": ["TRANSPORT_CYCLE"],
            "payload_kg": "1000",
            "min_aisle_width_m": "1.8",
        }
        process_code, process_scope = "warehouse_receiving_shipping", "TRANSPORT_CYCLE"
    elif profile == "airport":
        context = {
            "object_kind": "AIRPORT",
            "route_zones": ["apron"],
            "route_floors": [1],
            "time_scope": "NIGHT",
            "temperature_min_c": "-25",
            "temperature_max_c": "40",
            "max_noise_dba": "75",
            "outdoor_required": True,
            "airside_required": True,
            "apron_required": True,
            "requirement_sources": {
                "temperature_min_c": {"kind": "FILE", "source_ref": "input:airport:temperature-min"},
                "temperature_max_c": {"kind": "FILE", "source_ref": "input:airport:temperature-max"},
                "max_noise_dba": {"kind": "USER", "source_ref": "input:airport:noise", "user_confirmed": True},
                "outdoor_required": {"kind": "POLICY", "source_ref": "input:airport:outdoor"},
                "airside_required": {"kind": "POLICY", "source_ref": "input:airport:airside"},
                "apron_required": {"kind": "POLICY", "source_ref": "input:airport:apron"},
            },
        }
        candidate = {
            **common_candidate,
            "supported_object_kinds": ["AIRPORT"],
            "supported_process_scopes": ["TRANSPORT_CYCLE"],
            "temperature_min_c": "-30",
            "temperature_max_c": "45",
            "noise_dba": "70",
            "allowed_time_scopes": ["NIGHT"],
            "allowed_zones": ["apron"],
            "outdoor_supported": True,
            "airside_operational_permission": True,
            "apron_operational_permission": True,
        }
        process_code, process_scope = "airport_baggage", "TRANSPORT_CYCLE"
    else:
        context = {
            "object_kind": "CLINIC",
            "route_zones": ["ward", "waste-room"],
            "route_floors": [1],
            "time_scope": "NIGHT",
            "max_noise_dba": "45",
            "sanitization_required": True,
            "class_b_containment_required": True,
            "requirement_sources": {
                "max_noise_dba": {"kind": "USER", "source_ref": "input:clinic:noise", "user_confirmed": True},
                "sanitization_required": {"kind": "POLICY", "source_ref": "input:clinic:sanitization"},
                "class_b_containment_required": {"kind": "POLICY", "source_ref": "input:clinic:class-b"},
            },
        }
        candidate = {
            **common_candidate,
            "supported_object_kinds": ["CLINIC"],
            "supported_process_scopes": ["TRANSPORT_CYCLE"],
            "noise_dba": "40",
            "allowed_time_scopes": ["NIGHT"],
            "allowed_zones": ["ward", "waste-room"],
            "sterilization_supported": True,
            "class_b_containment_supported": True,
            "cleanable_surface": True,
            "material_disinfection_supported": True,
        }
        process_code, process_scope = "clinic_waste_b", "TRANSPORT_CYCLE"
    candidate["evidence"] = _evidence(
        [key for key in candidate if key not in {"model_id", "position_id", "evidence"}], profile
    )
    return ConstraintEvaluationRequest.model_validate({
        "input_revision": f"revision.{profile}.golden",
        "process_id": f"process.{profile}.golden",
        "process_code": process_code,
        "process_scope": process_scope,
        "context": context,
        "candidate": candidate,
    })


def outputs() -> dict[Path, str]:
    rules = load_constraint_rules()
    result = {
        ROOT / "contracts" / "constraint-evaluation-request-v2.schema.json": encoded(ConstraintEvaluationRequest.model_json_schema()),
        ROOT / "contracts" / "constraint-report-v2.schema.json": encoded(ConstraintReportV2.model_json_schema()),
        ROOT / "contracts" / "constraint-rules-v2.schema.json": encoded(ConstraintRules.model_json_schema()),
    }
    for profile in ("warehouse", "airport", "clinic"):
        request = _fixture(profile)
        report = evaluate_constraints(request, rules)
        result[ROOT / "contracts" / "fixtures" / f"constraint-report-v2.{profile}.json"] = encoded({
            "request": request.model_dump(mode="json"),
            "report": report.model_dump(mode="json"),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift: list[str] = []
    for path, content in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if drift:
        print("C05 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
