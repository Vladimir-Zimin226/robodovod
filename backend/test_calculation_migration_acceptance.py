from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from calculation.economics.cashflow import FinancialAnalysisRequestV1, calculate_financial_result
from calculation.intake import CalculationIntakeRequestV2, ProcessCode
from calculation.process_profiles.catalog import load_process_profile_catalog
from calculation.scheduling import SimulationReportV1, SimulationRequestV1, run_simulation


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts/calculation-acceptance-manifest-v1.json"


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_release_manifest_pins_sources_goldens_and_complete_reference_coverage():
    manifest = _load("contracts/calculation-acceptance-manifest-v1.json")
    assert manifest["schema_version"] == "calculation-acceptance-manifest-v1"
    assert manifest["policy_version"] == "hackathon-calculation-policy-v1"
    pinned = [*manifest["object_fixtures"].values(), *manifest["release_fixtures"]]
    for item in pinned:
        path = ROOT / item["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    assert set(manifest["reference_coverage"]) == {f"R{i:02d}" for i in range(14)}
    for paths in manifest["reference_coverage"].values():
        assert paths and all((ROOT / path).is_file() for path in paths)
    assert manifest["accepted_decisions"] == {"K": [1, 29], "Q": [1, 12]}


def test_three_object_fixtures_cover_exactly_all_28_policy_scopes():
    manifest = _load("contracts/calculation-acceptance-manifest-v1.json")
    observed: set[str] = set()
    expected_counts = {"WAREHOUSE": 6, "AIRPORT": 10, "CLINIC": 12}
    for object_kind, pin in manifest["object_fixtures"].items():
        fixture = _load(pin["path"])
        request = CalculationIntakeRequestV2.model_validate(fixture["request"])
        assert request.object_kind == object_kind
        codes = {str(item.process_code) for item in request.processes}
        assert len(codes) == expected_counts[object_kind]
        assert not observed.intersection(codes)
        observed.update(codes)
    catalog_codes = {str(item.process_code) for item in load_process_profile_catalog().profiles}
    assert observed == catalog_codes == {str(item) for item in ProcessCode}


def test_golden_path_repeats_five_times_and_engines_remain_offline_and_deterministic():
    financial = _load("contracts/fixtures/financial-result-v1.warehouse.golden.json")
    financial_request = FinancialAnalysisRequestV1.model_validate(financial["request"])
    simulation_request = SimulationRequestV1.model_validate(
        _load("contracts/fixtures/simulation-request-v1.capacity-only.golden.json")
    )
    expected_financial = financial["result"]
    expected_simulation = _load("contracts/fixtures/simulation-report-v1.capacity-only.golden.json")
    for _ in range(5):
        economy_started = time.monotonic()
        economy = calculate_financial_result(financial_request, engine_version="full-cashflows-reconciliation-v1").model_dump(mode="json")
        assert time.monotonic() - economy_started <= 10
        simulation_started = time.monotonic()
        simulation = run_simulation(simulation_request, engine_version="deterministic-queue-v1")
        assert time.monotonic() - simulation_started <= 60
        assert economy == expected_financial
        assert isinstance(simulation, SimulationReportV1)
        assert simulation.model_dump(mode="json") == expected_simulation


def test_corrected_c16_and_c23_release_goldens_repeat_without_changing_legacy():
    financial = _load("contracts/fixtures/financial-result-v2.warehouse.golden.json")
    financial_request = FinancialAnalysisRequestV1.model_validate(financial["request"])
    simulation_request = SimulationRequestV1.model_validate(
        _load("contracts/fixtures/simulation-request-v1.capacity-only.golden.json")
    )
    expected_simulation = _load("contracts/fixtures/simulation-report-v2.capacity-only.golden.json")
    for _ in range(5):
        economy_started = time.monotonic()
        economy = calculate_financial_result(
            financial_request, engine_version="full-cashflows-reconciliation-v2"
        ).model_dump(mode="json")
        assert time.monotonic() - economy_started <= 10
        simulation_started = time.monotonic()
        simulation = run_simulation(simulation_request, engine_version="deterministic-queue-v2")
        assert time.monotonic() - simulation_started <= 60
        assert economy == financial["result"]
        assert simulation.model_dump(mode="json") == expected_simulation


def test_50_concurrent_economics_users_are_deterministic_within_request_sla():
    fixture = _load("contracts/fixtures/financial-result-v1.warehouse.golden.json")
    request = FinancialAnalysisRequestV1.model_validate(fixture["request"])
    expected = fixture["result"]

    def execute(_: int) -> tuple[float, dict]:
        started = time.monotonic()
        result = calculate_financial_result(request, engine_version="full-cashflows-reconciliation-v1").model_dump(mode="json")
        return time.monotonic() - started, result

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(execute, range(50)))
    assert max(elapsed for elapsed, _ in results) <= 10
    assert all(result == expected for _, result in results)


def test_calculation_runtime_has_no_external_service_dependency():
    forbidden = ("import requests", "import httpx", "import openai", "yandex", "anthropic")
    for path in (ROOT / "backend/calculation").rglob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert not any(token in source for token in forbidden), path
