from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from catalog_import_contract import (
    CapacityEnrichmentContract,
    CapacityRuntimeContract,
    load_catalog_bundle,
)
from catalog_repository import (
    CapacityRuntimeDTO,
    CatalogApplicabilityDTO,
    CatalogFactDTO,
    CatalogModelDTO,
    CatalogPositionDTO,
    ProcurementOptionDTO,
    _capacity_runtime,
)
from main import _discovery_position

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_catalog_capacity_runtime import (  # noqa: E402
    OUTPUT,
    SCHEMA,
    ENRICHMENT_OUTPUT,
    ENRICHMENT_SCHEMA,
    _bytes,
    build,
    build_enrichment,
)

BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"


def test_capacity_runtime_is_schema_valid_deterministic_and_exact():
    generated = build()
    committed = CapacityRuntimeContract.model_validate(
        json.loads(OUTPUT.read_text(encoding="utf-8"))
    )

    assert _bytes(generated.model_dump(mode="json")) == OUTPUT.read_bytes()
    assert committed == generated
    assert SCHEMA.read_bytes() == _bytes(CapacityRuntimeContract.model_json_schema())
    statuses = Counter(item.calculation_readiness_status for item in committed.models)
    assert statuses == {
        "CALCULATION_READY": 6,
        "CALCULATION_READY_WITH_ASSUMPTIONS": 15,
        "CALCULATION_BLOCKED": 19,
        "UNSUPPORTED_CAPACITY_PROFILE": 143,
        "NOT_EQUIPMENT": 4,
    }
    assert committed.counts["calculation_pool_positions"] == 24
    assert committed.counts["deployment_ready_models"] == 0


def test_reviewed_capacity_enrichment_is_versioned_and_exact():
    generated = build_enrichment()
    committed = CapacityEnrichmentContract.model_validate(
        json.loads(ENRICHMENT_OUTPUT.read_text(encoding="utf-8"))
    )

    assert committed == generated
    assert _bytes(generated.model_dump(mode="json")) == ENRICHMENT_OUTPUT.read_bytes()
    assert ENRICHMENT_SCHEMA.read_bytes() == _bytes(
        CapacityEnrichmentContract.model_json_schema()
    )
    assert committed.counts == {
        "facts": 131,
        "matching_facts": 129,
        "evidence_rows": 154,
        "models": 26,
    }
    assert sum(fact.resolution_status == "MANUALLY_APPROVED" for fact in committed.facts) == 15


def test_capacity_pool_contains_only_brs_and_keeps_assumptions_separate():
    bundle = load_catalog_bundle(BUNDLE)
    products = {item["organizer_id"]: item for item in bundle.products}
    ready = [item for item in bundle.capacity_runtime.models if item.calculation_ready]

    assert len(ready) == 21
    assert {products[item.model_id]["system_family"] for item in ready} == {"BRS"}
    assert sum(item.calculation_requires_assumptions for item in ready) == 15
    assumptions = [value for item in ready for value in item.scenario_assumptions]
    assert assumptions
    assert all(value.vendor_fact is False for value in assumptions)
    assert all(value.provenance for value in assumptions)


def test_repository_capacity_projection_uses_only_evidence_gated_facts():
    fact = CatalogFactDTO(
        code="payload",
        scope_code="GLOBAL",
        value=1200,
        canonical_unit="kg",
        resolution_status="VERIFIED_OFFICIAL",
        evidence_id="evidence-1",
    )
    attributes = {
        "capacity_runtime": {
            "calculation_readiness_status": "CALCULATION_READY_WITH_ASSUMPTIONS",
            "calculation_ready": True,
            "calculation_requires_assumptions": True,
            "calculation_profile": "TRANSPORT_CYCLE_V1",
            "calculation_model_fields": ["specs.payload"],
            "calculation_blockers": [],
            "scenario_assumptions": [
                {
                    "field": "capacity.units_per_trip",
                    "input_path": "UserInput.units_per_trip",
                    "fallback_value": 1,
                    "unit": "unit/trip",
                    "policy": "SCENARIO_INPUT_THEN_EXPLICIT_FALLBACK",
                    "provenance": "backend/economics.py:_fleet_sizing",
                    "vendor_fact": False,
                }
            ],
            "deployment_readiness_status": "DEPLOYMENT_REVIEW_REQUIRED",
            "runtime_catalog_version": "organizer-catalog-v4-capacity-runtime-v1",
            "provenance": {"contract_version": "runtime-calculation-readiness-contract-v2"},
        }
    }

    projected = _capacity_runtime(attributes, (fact,))
    assert projected.calculation_ready is True
    assert projected.vendor_facts == (fact,)
    assert projected.scenario_assumptions[0]["vendor_fact"] is False

    fail_closed = _capacity_runtime(attributes, ())
    assert fail_closed.calculation_ready is False
    assert fail_closed.calculation_readiness_status == "CALCULATION_BLOCKED"
    assert fail_closed.calculation_blockers == ("matching_fact:payload",)


def test_non_materialized_catalog_never_becomes_calculation_ready():
    missing = _capacity_runtime({}, ())
    assert missing.calculation_ready is False
    assert missing.runtime_catalog_version is None
    assert missing.calculation_blockers == ("capacity_runtime",)


def test_discovery_api_contract_exposes_capacity_readiness_without_selectability():
    fact = CatalogFactDTO(
        code="cleaning_rate_m2_h",
        scope_code="GLOBAL",
        value=1800,
        canonical_unit="m2/h",
        resolution_status="VERIFIED_OFFICIAL",
        evidence_id="evidence-1",
    )
    capacity = CapacityRuntimeDTO(
        calculation_readiness_status="CALCULATION_READY",
        calculation_ready=True,
        calculation_requires_assumptions=False,
        calculation_profile="CLEANING_AREA_V1",
        calculation_blockers=(),
        runtime_catalog_version="organizer-catalog-v4-capacity-runtime-v1",
        calculation_model_fields=("capacity.cleaning_rate_m2_h",),
        vendor_facts=(fact,),
        provenance={"contract_version": "runtime-calculation-readiness-contract-v2"},
        deployment_readiness_status="DEPLOYMENT_REVIEW_REQUIRED",
    )
    model = CatalogModelDTO(
        id="model",
        source_namespace="test",
        source_record_key="org-model",
        organizer_id="00000000-0000-0000-0000-000000000001",
        manufacturer="Vendor",
        name="Cleaner",
        system_family="BRS",
        type_code="Cleaning",
        subtype_code=None,
        maturity_status=None,
        trl=None,
        description=None,
        attributes={},
        facts=(fact,),
        applicability=(),
        procurement_options=(),
        runtime_robot=None,
        runtime_blockers=("runtime_projection",),
        capacity_runtime=capacity,
    )
    position = CatalogPositionDTO(
        id="position",
        source_record_key="catalog-v4-row-0002",
        source_row_number=2,
        model=model,
        applicability=CatalogApplicabilityDTO(None, None, None, None),
        procurement_option=ProcurementOptionDTO(
            "PURCHASE", None, None, "UNKNOWN", "UNKNOWN", (), (), None
        ),
        media=None,
        runtime_robot=None,
        runtime_blockers=("runtime_projection",),
    )

    payload = _discovery_position(position, "organizer-catalog-v4")
    assert payload["selectable"] is False
    assert payload["calculation_readiness_status"] == "CALCULATION_READY"
    assert payload["calculation_ready"] is True
    assert payload["calculation_requires_assumptions"] is False
    assert payload["calculation_profile"] == "CLEANING_AREA_V1"
    assert payload["calculation_blockers"] == []
    assert payload["runtime_catalog_version"] == (
        "organizer-catalog-v4-capacity-runtime-v1"
    )
    assert payload["calculation_vendor_facts"][0]["evidence_id"] == "evidence-1"
