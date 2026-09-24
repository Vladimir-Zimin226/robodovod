"""Generate the C26 evidence export schema and deterministic golden capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation.evidence_export import (  # noqa: E402
    EvidenceExportManifestV1,
    EvidenceExportManifestV2,
    EvidenceRunSnapshotV1,
    build_evidence_export,
    build_evidence_export_v2,
)

SCHEMA_TARGET = ROOT / "contracts" / "calculation-evidence-export-manifest-v1.schema.json"
MANIFEST_TARGET = ROOT / "contracts" / "fixtures" / "calculation-evidence-export-v1.golden.json"
CASHFLOW_TARGET = ROOT / "contracts" / "fixtures" / "calculation-evidence-export-v1.cashflow.golden.csv"
SCHEMA_V2_TARGET = ROOT / "contracts" / "calculation-evidence-export-manifest-v2.schema.json"
MANIFEST_V2_TARGET = ROOT / "contracts" / "fixtures" / "calculation-evidence-export-v2.golden.json"


def _checksum(value):
    if value is None:
        return None
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def golden_run() -> EvidenceRunSnapshotV1:
    input_snapshot = {
        "object_type": "warehouse",
        "annual_demand": "120000.00",
        "customer_note": "=untrusted spreadsheet value",
        "operator_note": "  @untrusted command",
        "planner_note": "+untrusted formula",
        "route_note": "-untrusted formula",
    }
    result_snapshot = {
        "schema_version": "commercial-scenarios-v2",
        "selection": {"recommended_model": "amr-01", "required_fleet": 3, "source_ref": "trace.node.selection"},
        "scenarios": [{"name": "BASE", "status": "COMPLETE", "source_ref": "trace.node.base"}],
        "cash_flow": [
            {"year": 0, "net_cash_flow_rub": "-3000000.00", "source_ref": "trace.node.cashflow.0"},
            {"year": 1, "net_cash_flow_rub": "1250000.00", "source_ref": "trace.node.cashflow.1"},
        ],
        "sensitivity": {"status": "NOT_AVAILABLE", "source_ref": "trace.node.sensitivity"},
        "sources": [{"source_ref": "R03#6", "status": "VERIFIED_OFFICIAL"}],
        "simulation_report": {
            "schema_version": "simulation-report-v1",
            "report_id": "report.golden.c26",
            "report_digest": "sha256:" + "2" * 64,
            "sla": {"verdict": "NOT_EVALUATED"},
            "limitations": ["capacity-only-no-finance"],
        },
    }
    scenario = {"schema_version": "scenario-spec-v2", "revision_id": "calc_golden_c26"}
    trace = {
        "schema_version": "calculation-trace-v1",
        "formula_nodes": [{"node_id": "trace.node.cashflow.0", "formula_id": "F20"}],
    }
    bindings = {"calculation_policy_version": "hackathon-calculation-policy-v1"}
    return EvidenceRunSnapshotV1(
        run_id="00000000-0000-4000-8000-000000000026",
        project_id="00000000-0000-4000-8000-000000000001",
        run_kind="FULL_ANALYSIS",
        status="SUCCEEDED",
        revision_id="calc_golden_c26",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        versions={"catalog": "catalog-v1", "rules": "rules-v1", "economics": "economics-v2"},
        checksums={
            "input": _checksum(input_snapshot),
            "result": _checksum(result_snapshot),
            "scenario_spec": _checksum(scenario),
            "trace": _checksum(trace),
            "version_bindings": _checksum(bindings),
        },
        input_snapshot=input_snapshot,
        result_snapshot=result_snapshot,
        scenario_spec_snapshot=scenario,
        trace_snapshot=trace,
        version_bindings_snapshot=bindings,
        diagnostics={},
    )


def expected_outputs() -> dict[Path, bytes]:
    schema = EvidenceExportManifestV1.model_json_schema(ref_template="#/$defs/{model}", mode="serialization")
    schema["$id"] = "https://robomera.local/contracts/calculation-evidence-export-manifest-v1.schema.json"
    schema["title"] = "Robomera Calculation Evidence Export Manifest v1"
    package = build_evidence_export(golden_run())
    schema_v2 = EvidenceExportManifestV2.model_json_schema(ref_template="#/$defs/{model}", mode="serialization")
    schema_v2["$id"] = "https://robomera.local/contracts/calculation-evidence-export-manifest-v2.schema.json"
    schema_v2["title"] = "Robodovod Calculation Evidence Export Manifest v2"
    package_v2 = build_evidence_export_v2(golden_run())
    return {
        SCHEMA_TARGET: (json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        MANIFEST_TARGET: (json.dumps(package.manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        CASHFLOW_TARGET: package.files["CashFlow.csv"],
        SCHEMA_V2_TARGET: (json.dumps(schema_v2, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        MANIFEST_V2_TARGET: (json.dumps(package_v2.manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = expected_outputs()
    if args.check:
        return 0 if all(path.is_file() and path.read_bytes() == payload for path, payload in outputs.items()) else 1
    for path, payload in outputs.items():
        path.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
