from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation_contracts import (  # noqa: E402
    CalculationDecisionFixtures,
    CalculationParameterRegistry,
    CalculationSemanticsFixture,
    CalculationSemanticsManifest,
    CalculationTrace,
    CapacityAnalysisErrorResponse,
    CapacityAnalysisRequest,
    CapacityAnalysisResponse,
    CapacityResult,
    FinancialResult,
    NormalizedProcess,
    ParameterRegistryProposal,
    PartialCalculationResult,
    RolePool,
    calculation_trace_digest,
    semantic_digest,
)
from calculation.capacity.transport import TransportCapacityRequestV1  # noqa: E402

CONTRACTS = ROOT / "contracts"
FIXTURES = CONTRACTS / "fixtures"
ZERO_DIGEST = "sha256:" + "0" * 64


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _q(
    name: str,
    value: str,
    unit: str,
    kind: str,
    provenance_ref: str,
    *,
    raw_value: str | None = None,
    raw_unit: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "KNOWN",
        "name": name,
        "raw_value": raw_value or value,
        "raw_unit": raw_unit or unit,
        "normalized_value": value,
        "unit": unit,
        "quantity_kind": kind,
        "numeric_encoding": "DECIMAL_STRING",
        "provenance_ref": provenance_ref,
    }


def _missing(name: str, unit: str, kind: str, reason: str) -> dict[str, Any]:
    return {
        "status": "MISSING",
        "name": name,
        "quantity_kind": kind,
        "expected_unit": unit,
        "missing_reason": reason,
        "provenance_ref": None,
    }


def _result(value: str, unit: str, kind: str) -> dict[str, str]:
    return {
        "value": value,
        "unit": unit,
        "quantity_kind": kind,
        "numeric_encoding": "DECIMAL_STRING",
    }


def build_process() -> NormalizedProcess:
    return NormalizedProcess.model_validate(
        {
            "schema_version": "normalized-process-v1",
            "process_id": "warehouse.receiving-shipping",
            "input_revision": "input.contract-fixture-v1",
            "object_kind": "WAREHOUSE",
            "process_code": "warehouse_receiving_shipping",
            "scope": "TRANSPORT_CYCLE",
            "active": True,
            "quantity_kind": "PALLET",
            "demand": _q(
                "demand_per_day", "2000", "pallet/day", "FLOW", "prov.user"
            ),
            "schedule": {
                "shifts_per_day": _q("shifts_per_day", "2", "shift", "COUNT", "prov.user"),
                "shift_hours": _q("shift_hours", "11", "h", "TIME", "prov.user"),
                "days_per_year": _q("days_per_year", "365", "day", "TIME", "prov.user"),
            },
            "route_distance": _q(
                "one_way_distance", "120", "m", "DISTANCE", "prov.user"
            ),
            "exchange": {
                "mode": "TOTAL",
                "total_time": _q(
                    "exchange_total_time", "90", "s", "TIME", "prov.user"
                ),
            },
            "item_mass": _q("item_mass", "800", "kg/unit", "RATE", "prov.user"),
            "explicit_batch": _q(
                "units_per_trip", "1", "unit/trip", "RATE", "prov.user"
            ),
            "role_refs": ["warehouse.forklift-driver"],
        }
    )


def build_role_pool() -> RolePool:
    return RolePool.model_validate(
        {
            "schema_version": "role-pool-v1",
            "pool_id": "warehouse.roles",
            "object_kind": "WAREHOUSE",
            "roles": [
                {
                    "role_id": "warehouse.forklift-driver",
                    "object_scope": "WAREHOUSE",
                    "role_code": "forklift_driver",
                    "label": "Водитель погрузчика",
                    "headcount": _q(
                        "role_headcount", "25", "person", "COUNT", "prov.user"
                    ),
                    "monthly_gross_salary": _missing(
                        "monthly_gross_salary",
                        "RUB/person/month",
                        "MONEY",
                        "MISSING_INPUT",
                    ),
                    "zero_cost_marker": None,
                    "process_ids": ["warehouse.receiving-shipping"],
                }
            ],
        }
    )


def _versions() -> dict[str, str]:
    synthetic = semantic_digest({"fixture": "calculation-semantics-v1"})
    return {
        "catalog_version_id": "synthetic-contract-catalog-v1",
        "catalog_content_digest": synthetic,
        "capacity_projection_version": "synthetic-capacity-projection-v1",
        "capacity_projection_digest": synthetic,
        "registry_version": "calculation-parameter-registry-v1",
        "registry_digest": synthetic,
        "process_catalog_version": "calculation-process-catalog-v1",
        "formula_bundle_version": "calculation-formulas-v1",
        "constraint_rules_version": "calculation-constraints-v1",
        "commercial_policy_version": "hackathon-commercial-policy-v1",
        "precision_policy_version": "decimal-context-28-half-even-v1",
        "calculation_policy_version": "hackathon-calculation-policy-v1",
    }


def _with_trace_digest(payload: dict[str, Any]) -> CalculationTrace:
    trace = CalculationTrace.model_validate(payload)
    updated = trace.model_dump(mode="json")
    updated["replay"]["trace_content_digest"] = calculation_trace_digest(trace)
    return CalculationTrace.model_validate(updated)


def build_complete_trace(process: NormalizedProcess) -> CalculationTrace:
    inputs = [
        process.schedule.shifts_per_day,
        process.schedule.shift_hours,
        process.schedule.days_per_year,
        process.demand,
        process.route_distance,
        process.exchange.total_time,
        process.item_mass,
        process.explicit_batch,
    ]
    inputs.extend(
        [
            _q("operating_speed", "1", "m/s", "SPEED", "prov.vendor.speed"),
            _q("availability", "0.70", "1", "FRACTION", "prov.assumption.availability"),
            _q("peak_factor", "1.5", "1", "FRACTION", "prov.assumption.availability"),
            _q("reserve_share", "0", "1", "FRACTION", "prov.assumption.availability"),
        ]
    )
    source_digest = semantic_digest({"sources": ["R03", "policy-v1"]})
    return _with_trace_digest(
        {
            "envelope": {
                "schema_version": "calculation-trace-v1",
                "engine_version": "contract-only-no-execution-v1",
                "run_id": "run.contract-complete",
                "input_revision": process.input_revision,
                "acquisition": "PURCHASE",
                "uncertainty": "BASE",
                "process_id": process.process_id,
                "model_id": "synthetic-contract-model",
                "position_id": "synthetic-contract-position",
            },
            "versions": _versions(),
            "provenance": [
                {
                    "provenance_id": "prov.user",
                    "kind": "USER",
                    "confirmation_revision": "confirmation.contract-v1",
                },
                {
                    "provenance_id": "prov.vendor.speed",
                    "kind": "VENDOR_FACT",
                    "fact_id": "fact.synthetic-speed",
                    "model_id": "synthetic-contract-model",
                    "position_id": "synthetic-contract-position",
                    "scope": "contract-fixture-only",
                    "evidence_ids": ["evidence.synthetic-speed"],
                    "evidence_status": "VERIFIED_OFFICIAL",
                    "permitted_for_matching": True,
                },
                {
                    "provenance_id": "prov.assumption.availability",
                    "kind": "ASSUMPTION",
                    "assumption_id": "assumption.synthetic-availability",
                    "assumption_version": "v1",
                    "rationale": "Contract fixture for explicit scenario assumption",
                    "permitted_scope": "synthetic contract fixture",
                    "confirmation_state": "POLICY_ACCEPTED",
                },
            ],
            "inputs": [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in inputs
            ],
            "formula_nodes": [
                {
                    "node_id": "node.f01",
                    "formula_id": "F01",
                    "formula_version": "v1",
                    "source_refs": ["R03§1.1", "K27"],
                    "source_digest": source_digest,
                    "template_id": "operating-hours-per-day",
                    "applicability_domain": "active scheduled process",
                    "dependency_node_ids": [],
                    "input_refs": ["shifts_per_day", "shift_hours"],
                },
                {
                    "node_id": "node.f02",
                    "formula_id": "F02",
                    "formula_version": "v1",
                    "source_refs": ["R03§1.1", "K02"],
                    "source_digest": source_digest,
                    "template_id": "transport-cycle-total-exchange",
                    "applicability_domain": "TRANSPORT_CYCLE",
                    "dependency_node_ids": ["node.f01"],
                    "input_refs": ["one_way_distance", "operating_speed", "exchange_total_time"],
                },
                {
                    "node_id": "node.f03",
                    "formula_id": "F03",
                    "formula_version": "v1",
                    "source_refs": ["R03§1.1", "K03"],
                    "source_digest": source_digest,
                    "template_id": "typed-batch-cap",
                    "applicability_domain": "pallet/unit batch",
                    "dependency_node_ids": ["node.f02"],
                    "input_refs": ["item_mass", "units_per_trip"],
                },
                {
                    "node_id": "node.f04",
                    "formula_id": "F04",
                    "formula_version": "v1",
                    "source_refs": ["R03§1.2", "K22"],
                    "source_digest": source_digest,
                    "template_id": "peak-availability-reserve",
                    "applicability_domain": "active capacity profile",
                    "dependency_node_ids": ["node.f01", "node.f03"],
                    "input_refs": [
                        "demand_per_day",
                        "peak_factor",
                        "reserve_share",
                        "availability",
                    ],
                },
                {
                    "node_id": "node.f07",
                    "formula_id": "F07",
                    "formula_version": "v1",
                    "source_refs": ["R03§1.4", "K04"],
                    "source_digest": source_digest,
                    "template_id": "fleet-coverage-utilization",
                    "applicability_domain": "selected fleet",
                    "dependency_node_ids": ["node.f04"],
                    "input_refs": ["fleet_selected"],
                },
            ],
            "conversions": [
                {
                    "conversion_id": "conversion.distance-identity",
                    "input_ref": "one_way_distance",
                    "from_unit": "m",
                    "to_unit": "m",
                    "exact_factor": "1",
                    "operation": "IDENTITY",
                    "before": "120",
                    "after": "120",
                    "unit_definition_version": "si-unit-definitions-v1",
                }
            ],
            "intermediates": [
                {
                    "value_id": "value.operating-hours",
                    "node_id": "node.f01",
                    "name": "operating_hours_per_day",
                    "value": _result("22", "h", "TIME"),
                    "parent_refs": ["shifts_per_day", "shift_hours"],
                },
                {
                    "value_id": "value.units-per-trip",
                    "node_id": "node.f03",
                    "name": "units_per_trip",
                    "value": _result("1", "unit/trip", "RATE"),
                    "parent_refs": ["units_per_trip", "item_mass"],
                },
                {
                    "value_id": "value.nominal-capacity",
                    "node_id": "node.f04",
                    "name": "nominal_capacity",
                    "value": _result("13.10924369747899159663865546", "unit/h", "RATE"),
                    "parent_refs": ["node.f02", "node.f03"],
                },
                {
                    "value_id": "value.effective-capacity",
                    "node_id": "node.f04",
                    "name": "effective_capacity",
                    "value": _result("9.176470588235294117647058822", "unit/h", "RATE"),
                    "parent_refs": ["value.nominal-capacity", "availability"],
                },
            ],
            "assumptions": [
                {
                    "assumption_id": "assumption.synthetic-availability",
                    "assumption_version": "v1",
                    "provenance_ref": "prov.assumption.availability",
                    "rationale": "Explicit capacity fixture assumption",
                    "permitted_scope": "synthetic contract fixture",
                    "mode": "DEFAULT",
                    "raw_user_override": None,
                    "applicable_scenario": "BASE",
                    "confirmation_state": "POLICY_ACCEPTED",
                }
            ],
            "constraints": [],
            "roundings": [
                {
                    "rounding_id": "rounding.recommended-fleet",
                    "node_id": "node.f04",
                    "operation": "CEIL",
                    "input_value": "17.97752808988764044943820225",
                    "output_value": "18",
                    "precision_policy_version": "decimal-context-28-half-even-v1",
                    "reason": "Fleet is an integer resource",
                    "source_ref": "K04",
                }
            ],
            "results": [
                {
                    "result_id": "result.recommended-fleet",
                    "status": "WITH_ASSUMPTIONS",
                    "value": _result("18", "robot", "COUNT"),
                    "supporting_node_ids": ["node.f04", "node.f07"],
                    "capacity_basis": "EFFECTIVE",
                }
            ],
            "issues": [],
            "replay": {
                "canonical_input_digest": semantic_digest(process),
                "trace_content_digest": ZERO_DIGEST,
                "deterministic_seed": None,
            },
            "runtime_metadata": {"build_id": None, "runtime_id": None},
        }
    )


def build_blocked_trace(process: NormalizedProcess) -> CalculationTrace:
    source_digest = semantic_digest({"sources": ["R03§1.1", "K02"]})
    return _with_trace_digest(
        {
            "envelope": {
                "schema_version": "calculation-trace-v1",
                "engine_version": "contract-only-no-execution-v1",
                "run_id": "run.contract-blocked",
                "input_revision": process.input_revision,
                "acquisition": "PURCHASE",
                "uncertainty": "BASE",
                "process_id": process.process_id,
                "model_id": "synthetic-contract-model",
                "position_id": "synthetic-contract-position",
            },
            "versions": _versions(),
            "provenance": [
                {
                    "provenance_id": "prov.user",
                    "kind": "USER",
                    "confirmation_revision": "confirmation.contract-v1",
                }
            ],
            "inputs": [
                process.schedule.shifts_per_day.model_dump(mode="json"),
                process.schedule.shift_hours.model_dump(mode="json"),
                _missing("operating_speed", "m/s", "SPEED", "MISSING_SAFE_FACT"),
            ],
            "formula_nodes": [
                {
                    "node_id": "node.f01",
                    "formula_id": "F01",
                    "formula_version": "v1",
                    "source_refs": ["R03§1.1"],
                    "source_digest": source_digest,
                    "template_id": "operating-hours-per-day",
                    "applicability_domain": "active scheduled process",
                    "dependency_node_ids": [],
                    "input_refs": ["shifts_per_day", "shift_hours"],
                },
                {
                    "node_id": "node.f02",
                    "formula_id": "F02",
                    "formula_version": "v1",
                    "source_refs": ["R03§1.1", "K02"],
                    "source_digest": source_digest,
                    "template_id": "transport-cycle-total-exchange",
                    "applicability_domain": "TRANSPORT_CYCLE",
                    "dependency_node_ids": ["node.f01"],
                    "input_refs": ["operating_speed"],
                },
            ],
            "conversions": [],
            "intermediates": [],
            "assumptions": [],
            "constraints": [],
            "roundings": [],
            "results": [
                {
                    "result_id": "result.recommended-fleet",
                    "status": "BLOCKED",
                    "value": None,
                    "supporting_node_ids": ["node.f02"],
                    "capacity_basis": "NOT_APPLICABLE",
                }
            ],
            "issues": [
                {
                    "code": "missing.safe-operating-speed",
                    "reason": "MISSING_SAFE_FACT",
                    "severity": "BLOCKER",
                    "field_refs": ["operating_speed"],
                    "node_refs": ["node.f02"],
                    "decision_refs": ["K02"],
                    "message": "No safe speed fact or explicit scenario operating speed",
                }
            ],
            "replay": {
                "canonical_input_digest": semantic_digest(process),
                "trace_content_digest": ZERO_DIGEST,
                "deterministic_seed": None,
            },
            "runtime_metadata": {"build_id": None, "runtime_id": None},
        }
    )


def build_result() -> PartialCalculationResult:
    finance_issue = {
        "code": "missing.role-salary",
        "reason": "MISSING_ROLE_SALARY",
        "severity": "BLOCKER",
        "field_refs": ["roles[warehouse.forklift-driver].monthly_gross_salary"],
        "node_refs": [],
        "decision_refs": [],
        "message": "Capacity is available; finance waits for an explicit role salary",
    }
    return PartialCalculationResult.model_validate(
        {
            "schema_version": "calculation-partial-result-v1",
            "result_status": "PARTIAL",
            "capacity": {
                "schema_version": "capacity-result-v1",
                "process_id": "warehouse.receiving-shipping",
                "status": "WITH_ASSUMPTIONS",
                "value": {
                    "recommended_fleet": 18,
                    "selected_fleet": 18,
                    "nominal_capacity": _result(
                        "13.10924369747899159663865546", "unit/h", "RATE"
                    ),
                    "effective_capacity": _result(
                        "9.176470588235294117647058822", "unit/h", "RATE"
                    ),
                    "coverage": _result("1", "1", "FRACTION"),
                    "raw_load_ratio": _result(
                        "0.9900990099009900990099009901", "1", "FRACTION"
                    ),
                    "utilization": _result(
                        "0.9900990099009900990099009901", "1", "FRACTION"
                    ),
                    "overloaded": False,
                },
                "blockers": [],
                "warnings": [],
                "trace_ref": "run.contract-complete",
            },
            "financial": {
                "schema_version": "financial-result-v1",
                "process_id": "warehouse.receiving-shipping",
                "status": "INCOMPLETE",
                "benefit_status": "UNKNOWN",
                "value": None,
                "blockers": [finance_issue],
                "warnings": [],
                "trace_ref": None,
            },
        }
    )


def build_capacity_only_result() -> PartialCalculationResult:
    result = build_result().model_dump(mode="json")
    result["result_status"] = "CAPACITY_ONLY"
    result["financial"] = None
    return PartialCalculationResult.model_validate(result)


def build_manifest() -> CalculationSemanticsManifest:
    proposal_fields = [
        "parameter_id",
        "semantic_name",
        "value",
        "unit",
        "quantity_kind",
        "source_refs",
        "source_digest",
        "decision_refs",
        "effective_version",
        "replaced_by",
        "applicability",
    ]
    optional = {"replaced_by"}
    formula_parameters = {
        "F01": ["shifts_per_day", "shift_hours", "operating_hours_per_day"],
        "F02": [
            "one_way_distance",
            "operating_speed",
            "exchange_total_time",
            "load_time",
            "unload_time",
        ],
        "F03": [
            "payload",
            "item_mass",
            "handling_batch_limit",
            "passport_batch_limit",
            "geometry_batch_limit",
            "units_per_trip",
        ],
        "F04": ["demand_per_day", "peak_factor", "reserve_share", "availability"],
        "F05": ["cleaning_area_per_day", "cleaning_frequency", "cleaning_rate", "availability"],
        "F06": ["demand_per_day", "cell_rate", "cell_efficiency", "availability"],
        "F07": [
            "fleet_selected",
            "fleet_recommended",
            "nominal_capacity",
            "effective_capacity",
            "coverage",
            "raw_load_ratio",
            "utilization",
        ],
    }
    decision_map = {
        "F01": ["K27"],
        "F02": ["K02"],
        "F03": ["K03"],
        "F04": ["K04"],
        "F05": ["K19"],
        "F06": ["K19"],
        "F07": ["K04"],
    }
    return CalculationSemanticsManifest.model_validate(
        {
            "schema_version": "calculation-semantics-manifest-v1",
            "calculation_policy_version": "hackathon-calculation-policy-v1",
            "decision_refs": ["K02", "K03", "K04", "K19", "K27"],
            "supported_contract_versions": [
                "normalized-process-v1",
                "role-pool-v1",
                "capacity-result-v1",
                "financial-result-v1",
                "calculation-partial-result-v1",
                "calculation-trace-v1",
            ],
            "precision_policy": {
                "version": "decimal-context-28-half-even-v1",
                "decimal_context_precision": 28,
                "rounding_mode": "ROUND_HALF_EVEN",
                "raw_numeric_encoding": "DECIMAL_STRING",
                "intermediate_rounding": "NONE",
                "money_display_digits": 2,
                "percent_score_payback_display_digits": 2,
                "event_time_unit": "microsecond",
                "score_tolerance": "0.000001",
                "ceil_epsilon": "FORBIDDEN",
            },
            "source_parameter_map": [
                {
                    "formula_id": formula_id,
                    "source_refs": ["R03", "policy v1"],
                    "parameter_names": parameter_names,
                    "decision_refs": decision_map[formula_id],
                }
                for formula_id, parameter_names in formula_parameters.items()
            ],
            "compatibility": [
                {
                    "rule_id": "legacy.dto.unchanged",
                    "from_contract": "calculation-response-v1/scenario-spec-v1",
                    "to_contract": "same",
                    "mode": "UNCHANGED",
                    "lossy": False,
                    "rule": "C01 adds DTOs and does not mutate legacy API payloads.",
                },
                {
                    "rule_id": "legacy.exchange-45",
                    "from_contract": "legacy provenance-known per-operation exchange",
                    "to_contract": "normalized total exchange",
                    "mode": "PROVENANCE_GATED_ADAPTER",
                    "lossy": False,
                    "rule": (
                        "Only a provenance-known legacy 45 seconds per operation "
                        "migrates to total 90 seconds."
                    ),
                },
                {
                    "rule_id": "new.capacity-independent",
                    "from_contract": "normalized-process-v1",
                    "to_contract": "capacity-result-v1",
                    "mode": "ADDITIVE",
                    "lossy": False,
                    "rule": "Capacity result never requires a financial payload.",
                },
            ],
            "registry_proposal": {
                "schema_version": "calculation-parameter-registry-v1-proposal",
                "target_registry_version": "calculation-parameter-registry-v1",
                "immutable_snapshot": True,
                "semantic_order": "parameter_id",
                "fields": [
                    {"name": name, "required": name not in optional}
                    for name in proposal_fields
                ],
            },
            "capacity_api": {
                "method": "POST",
                "path": "/api/v2/capacity-analyses",
                "request_schema_version": "capacity-analysis-request-v2",
                "response_schema_version": "capacity-analysis-response-v2",
                "error_schema_version": "capacity-analysis-error-v1",
                "legacy_path_unchanged": "/api/calculate",
            },
        }
    )


def build_decision_fixtures() -> CalculationDecisionFixtures:
    user_total = _q("exchange_total_time", "45", "s", "TIME", "prov.user")
    load = _q("load_time", "45", "s", "TIME", "prov.user")
    unload = _q("unload_time", "45", "s", "TIME", "prov.user")
    legacy_total = _q("exchange_total_time", "90", "s", "TIME", "prov.legacy")
    return CalculationDecisionFixtures.model_validate(
        {
            "schema_version": "calculation-decision-fixtures-v1",
            "calculation_policy_version": "hackathon-calculation-policy-v1",
            "k02_exchange": [
                {
                    "example_id": "k02.new-total-45",
                    "source_semantics": "NEW_TOTAL",
                    "normalized_exchange": {"mode": "TOTAL", "total_time": user_total},
                    "expected_total_seconds": "45",
                    "legacy_migration": False,
                },
                {
                    "example_id": "k02.raw-split-45-45",
                    "source_semantics": "RAW_SPLIT",
                    "normalized_exchange": {
                        "mode": "SPLIT",
                        "load_time": load,
                        "unload_time": unload,
                    },
                    "expected_total_seconds": "90",
                    "legacy_migration": False,
                },
                {
                    "example_id": "k02.legacy-per-operation-45",
                    "source_semantics": "LEGACY_PER_OPERATION",
                    "normalized_exchange": {"mode": "TOTAL", "total_time": legacy_total},
                    "expected_total_seconds": "90",
                    "legacy_migration": True,
                },
            ],
            "k03_batch": [
                {
                    "example_id": "k03.mass-cap",
                    "payload_kg": "10",
                    "item_mass_kg": "3",
                    "handling_limit": None,
                    "passport_limit": None,
                    "geometry_limit": None,
                    "expected_batch": 3,
                    "expected_reason": "RESOLVED",
                },
                {
                    "example_id": "k03.handling-limit",
                    "payload_kg": "10",
                    "item_mass_kg": "3",
                    "handling_limit": 2,
                    "passport_limit": None,
                    "geometry_limit": None,
                    "expected_batch": 2,
                    "expected_reason": "RESOLVED",
                },
                {
                    "example_id": "k03.zero-item-mass",
                    "payload_kg": "10",
                    "item_mass_kg": "0",
                    "handling_limit": None,
                    "passport_limit": None,
                    "geometry_limit": None,
                    "expected_batch": None,
                    "expected_reason": "INVALID_DOMAIN",
                },
            ],
            "k04_capacity": [
                {
                    "example_id": "k04.active-fleet-zero",
                    "active": True,
                    "demand": "100",
                    "selected_fleet": 0,
                    "expected_capacity": "0",
                    "expected_coverage": "0",
                    "expected_raw_load_ratio": None,
                    "expected_utilization": None,
                    "expected_status": "OVERLOADED",
                },
                {
                    "example_id": "k04.inactive",
                    "active": False,
                    "demand": "0",
                    "selected_fleet": 0,
                    "expected_capacity": "0",
                    "expected_coverage": None,
                    "expected_raw_load_ratio": None,
                    "expected_utilization": None,
                    "expected_status": "NOT_APPLICABLE",
                },
            ],
        }
    )


def expected_files() -> tuple[tuple[Path, bytes], ...]:
    process = build_process()
    role_pool = build_role_pool()
    result = build_result()
    trace = build_complete_trace(process)
    fixture = CalculationSemanticsFixture(
        normalized_process=process,
        role_pool=role_pool,
        result=result,
        trace=trace,
    )
    blocked = build_blocked_trace(process)
    manifest = build_manifest()
    decisions = build_decision_fixtures()
    schemas = (
        (CONTRACTS / "normalized-process-v1.schema.json", NormalizedProcess),
        (CONTRACTS / "role-pool-v1.schema.json", RolePool),
        (CONTRACTS / "calculation-partial-result-v1.schema.json", PartialCalculationResult),
        (CONTRACTS / "calculation-trace-v1.schema.json", CalculationTrace),
        (CONTRACTS / "calculation-semantics-fixture-v1.schema.json", CalculationSemanticsFixture),
        (CONTRACTS / "calculation-semantics-manifest-v1.schema.json", CalculationSemanticsManifest),
        (CONTRACTS / "calculation-decision-fixtures-v1.schema.json", CalculationDecisionFixtures),
        (
            CONTRACTS / "calculation-parameter-registry-v1.proposed.schema.json",
            CalculationParameterRegistry,
        ),
        (CONTRACTS / "capacity-analysis-request-v2.schema.json", CapacityAnalysisRequest),
        (CONTRACTS / "capacity-analysis-response-v2.schema.json", CapacityAnalysisResponse),
        (CONTRACTS / "capacity-analysis-error-v1.schema.json", CapacityAnalysisErrorResponse),
        (CONTRACTS / "transport-capacity-request-v1.schema.json", TransportCapacityRequestV1),
    )
    generated = tuple((path, _bytes(model.model_json_schema())) for path, model in schemas)
    return generated + (
        (
            CONTRACTS / "calculation-semantics-manifest-v1.json",
            _bytes(manifest.model_dump(mode="json")),
        ),
        (
            FIXTURES / "calculation-semantics-v1.complete.json",
            _bytes(fixture.model_dump(mode="json")),
        ),
        (
            FIXTURES / "calculation-trace-v1.blocked-missing-speed.json",
            _bytes(blocked.model_dump(mode="json")),
        ),
        (
            FIXTURES / "calculation-partial-result-v1.capacity-only.json",
            _bytes(build_capacity_only_result().model_dump(mode="json")),
        ),
        (
            FIXTURES / "calculation-decision-fixtures-v1.json",
            _bytes(decisions.model_dump(mode="json")),
        ),
        (
            FIXTURES / "capacity-analysis-error-v1.blocked.json",
            _bytes(
                CapacityAnalysisErrorResponse.model_validate(
                    {
                        "schema_version": "capacity-analysis-error-v1",
                        "request_id": "request.contract-blocked",
                        "run_id": "run.contract-blocked",
                        "error_code": "CALCULATION_BLOCKED",
                        "issues": blocked.issues,
                        "partial_capacity": {
                            "schema_version": "capacity-result-v1",
                            "process_id": process.process_id,
                            "status": "BLOCKED",
                            "value": None,
                            "blockers": blocked.issues,
                            "warnings": [],
                            "trace_ref": blocked.envelope.run_id,
                        },
                    }
                ).model_dump(mode="json")
            ),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = expected_files()
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, content in expected
            if not path.is_file() or path.read_bytes() != content
        ]
        if stale:
            raise SystemExit("generated calculation contracts differ: " + ", ".join(stale))
        return 0
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for path, content in expected:
        path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
