from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_catalog_calculation_readiness_v2 import (  # noqa: E402
    CONTRACT_SCHEMA,
    REPORT,
    REPORT_SCHEMA,
    SUMMARY,
    ContractV2,
    ReadinessReport,
    _bytes,
    build_report,
    load_contract,
    schema_bytes,
    summary,
)


def test_contract_v2_keeps_assumptions_separate_from_vendor_facts():
    contract = load_contract()

    assert contract.policy.calculation_scope == "PRELIMINARY_CAPACITY_ONLY"
    assert contract.policy.materialization_into_runtime_required is True
    assert contract.policy.economics_in_scope is False
    assert contract.policy.runtime_switch_allowed is False
    assert contract.policy.capacity_formulas_changed is False
    transport = next(
        item for item in contract.equipment_classes if item.code == "MOBILE_TRANSPORT"
    )
    assert transport.calculation_model_fields == ["specs.max_speed", "specs.payload"]
    assert [item.field for item in transport.scenario_inputs] == [
        "capacity.exchange_time_s",
        "capacity.units_per_trip",
    ]
    assert [item.fallback_value for item in transport.scenario_inputs] == [45, 1]


def test_readiness_v2_has_exact_full_catalog_and_research_cohort_counts():
    report = build_report()

    assert report.counts == {"models": 187, "positions": 223}
    assert report.model_calculation_status_counts == {
        "CALCULATION_READY": 6,
        "CALCULATION_READY_WITH_ASSUMPTIONS": 15,
        "CALCULATION_BLOCKED": 19,
        "UNSUPPORTED_CAPACITY_PROFILE": 143,
        "NOT_EQUIPMENT": 4,
    }
    assert report.position_calculation_status_counts == {
        "CALCULATION_READY": 6,
        "CALCULATION_READY_WITH_ASSUMPTIONS": 18,
        "CALCULATION_BLOCKED": 19,
        "UNSUPPORTED_CAPACITY_PROFILE": 176,
        "NOT_EQUIPMENT": 4,
    }
    assert report.accepted_research_cohort_counts == {
        "models": 26,
        "CALCULATION_READY": 6,
        "CALCULATION_READY_WITH_ASSUMPTIONS": 13,
        "CALCULATION_BLOCKED": 6,
        "UNSUPPORTED_CAPACITY_PROFILE": 1,
        "NOT_EQUIPMENT": 0,
    }
    assert report.model_deployment_status_counts["DEPLOYMENT_READY"] == 0
    assert report.model_deployment_status_counts["DEPLOYMENT_REVIEW_REQUIRED"] == 40


def test_local_adapter_recovers_h1500_surface_without_hiding_other_gaps():
    report = build_report()
    h1500 = next(
        item
        for item in report.models
        if item.model_id == "5760e938-9a43-45a7-b8e8-f4f2e6383930"
    )

    assert report.local_adapter_facts == 1
    assert "specs.surface_requirements" not in h1500.missing_deployment_fields
    assert h1500.calculation_status == "CALCULATION_READY_WITH_ASSUMPTIONS"
    assert h1500.deployment_status == "DEPLOYMENT_REVIEW_REQUIRED"
    assert {item.field for item in h1500.calculation_assumptions} == {
        "capacity.exchange_time_s",
        "capacity.units_per_trip",
    }
    assert all(item.vendor_fact is False for item in h1500.calculation_assumptions)


def test_generated_v2_artifacts_are_schema_valid_and_idempotent():
    contract = load_contract()
    report = build_report()

    assert CONTRACT_SCHEMA.read_bytes() == schema_bytes(ContractV2)
    assert REPORT_SCHEMA.read_bytes() == schema_bytes(ReadinessReport)
    assert REPORT.read_bytes() == _bytes(report)
    assert SUMMARY.read_text(encoding="utf-8") == summary(report)
    ReadinessReport.model_validate(json.loads(REPORT.read_text(encoding="utf-8")))
    assert _bytes(build_report()) == _bytes(build_report())
    assert contract.schema_version == "runtime-calculation-readiness-contract-v2"
