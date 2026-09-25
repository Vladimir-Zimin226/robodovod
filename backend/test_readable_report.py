from __future__ import annotations

import io
import uuid
from copy import deepcopy

import pytest
from pypdf import PdfReader

from calculation.evidence_export import EvidenceExportIntegrityError, EvidenceRunSnapshotV1
from calculation.readable_report import _money, build_readable_report
from scripts.build_evidence_export_contract import _checksum, golden_run


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)


def _full_runs():
    raw = golden_run().model_dump(mode="json")
    capacity_id = str(uuid.uuid4())
    raw["versions"]["application"] = "production-economics-orchestrator-v2"
    raw["input_snapshot"] = {
        "capacity_run_id": capacity_id,
        "economics": {"discount_rate": "0.15", "horizon_years": 5, "raas_monthly_per_robot_gross": "120000"},
    }
    raw["checksums"]["input"] = _checksum(raw["input_snapshot"])
    facts = {
        "schema_version": "calculation-report-facts-v1",
        "fleet_count": 10,
        "project_capex_cashflow": "3000000.00",
        "project_npv": {"status": "COMPLETE", "value": "12345.67", "unit": "RUB"},
        "purchase_annual_robot_opex": "500000.00",
        "raas_annual_customer_opex": "100000.00",
        "raas_annual_payment": "1440000.00",
        "responsibilities": [{"area": "MAINTENANCE", "responsible_party": "VENDOR"}],
        "annual_cashflows": [{"year": 1, "baseline": "-100.00", "scenario": "-70.00", "effect": "30.00"}],
    }
    raw["result_snapshot"] = {
        "schema_version": "commercial-scenarios-bundle-v2",
        "input_revision": "revision.report.v1",
        "roles": [{"role_code": "forklift_driver", "headcount": "20", "monthly_gross_salary": {"value": "100000"}}],
        "scenarios": [
            {"acquisition": acquisition, "uncertainty": "BASE", "report_facts": facts}
            for acquisition in ("PURCHASE", "RAAS")
        ],
    }
    raw["checksums"]["result"] = _checksum(raw["result_snapshot"])
    linked = golden_run().model_dump(mode="json")
    linked["run_id"] = capacity_id
    linked["run_kind"] = "CAPACITY_ANALYSIS"
    linked["input_snapshot"] = {
        "project_id": raw["project_id"], "input_revision": "revision.report.v1",
        "process": {
            "process_code": "warehouse_receiving_shipping",
            "demand": {"normalized_value": "1000", "unit": "pallet/day"},
            "schedule": {
                "shifts_per_day": {"normalized_value": "2"},
                "shift_hours": {"normalized_value": "10"},
                "days_per_year": {"normalized_value": "365"},
            },
        },
    }
    linked["result_snapshot"] = {
        "run_id": capacity_id,
        "capacity": {"value": {"selected_fleet": 10, "effective_capacity": {"value": "1100", "unit": "pallet/day"}}},
    }
    linked["checksums"]["input"] = _checksum(linked["input_snapshot"])
    linked["checksums"]["result"] = _checksum(linked["result_snapshot"])
    return EvidenceRunSnapshotV1.model_validate(raw), EvidenceRunSnapshotV1.model_validate(linked)


def test_full_report_has_readable_source_bound_financial_values():
    run, linked = _full_runs()
    first, digest = build_readable_report(run, linked)
    second, _ = build_readable_report(run, linked)
    assert first == second and first.startswith(b"%PDF-")
    text = _text(first)
    for heading in ("Какой процесс оцениваем", "Сейчас", "После покупки роботов", "При аренде роботов (RaaS)",
                    "Сравнение денег по годам", "Что известно и что ещё подтвердить", "Источники и методика"):
        assert heading in text
    assert run.run_id in text and "01.01.2026" in text
    assert "1 000 паллет/день" in text and "1 100 паллет/день" in text
    assert "3 000 000,00 ₽" in text and "12 345,67 ₽" in text
    assert "техническое обслуживание" in text
    assert "Год 1: без роботов -100,00 ₽" in text
    assert digest in text


def test_full_report_discloses_confirmed_versioned_assumptions_from_saved_input():
    run, linked = _full_runs()
    raw = run.model_dump(mode="json")
    raw["input_snapshot"]["economics"]["assumption_evidence"] = {
        "implementation_cost_total_gross": {
            "schema_version": "scenario-assumption-evidence-v1", "template_id": "warehouse-economics-demo-v1",
            "version": "v1", "source": "Авторский тест", "rationale": "Условная смета",
            "published_on": "2026-09-25", "confirmed_value": "500000", "confirmed": True,
        }
    }
    raw["checksums"]["input"] = _checksum(raw["input_snapshot"])
    pdf, _ = build_readable_report(EvidenceRunSnapshotV1.model_validate(raw), linked)
    text = _text(pdf)
    assert "Подтверждённые допущения сценария" in text
    assert "implementation_cost_total_gross: 500 000" in text
    assert "не паспорт или предложение поставщика" in " ".join(text.split())
    assert "источник Авторский тест" in " ".join(text.split())


def test_partial_report_explains_missing_values_and_historical_error():
    raw = golden_run().model_dump(mode="json")
    raw["versions"]["application"] = "production-economics-orchestrator-v1"
    raw["input_snapshot"]["fte_cost_rub"] = "100000"
    raw["checksums"]["input"] = _checksum(raw["input_snapshot"])
    saved_input = deepcopy(raw["input_snapshot"])
    saved_result = deepcopy(raw["result_snapshot"])
    pdf, digest = build_readable_report(EvidenceRunSnapshotV1.model_validate(raw))
    text = _text(pdf)
    assert "C16 v1" in text and "известную ошибку" in text
    assert "нет данных для оценки" in text and "связанный расчёт мощности" in text
    assert "не известна база начисления" in text
    assert digest == "sha256:" + raw["checksums"]["result"]
    assert raw["input_snapshot"] == saved_input and raw["result_snapshot"] == saved_result


def test_partial_v2_report_reads_saved_purchase_finance_without_inventing_raas():
    run, linked = _full_runs()
    raw = run.model_dump(mode="json")
    raw["input_snapshot"]["economics"]["raas_monthly_per_robot_gross"] = None
    raw["checksums"]["input"] = _checksum(raw["input_snapshot"])
    raw["result_snapshot"] = {
        "schema_version": "economics-partial-result-v1",
        "input_revision": "revision.report.v1",
        "c05": {"eligibility": "NEEDS_VALIDATION", "procurement_ready": False},
        "capacity_run_id": linked.run_id,
        "branches": {"purchase": {"status": "CALCULATED"}, "raas": {"status": "NOT_CALCULATED", "reason_code": "MISSING_INPUT", "required_fields": ["raas_monthly_per_robot_gross"]}},
        "issues": [{"field": "raas_monthly_per_robot_gross", "code": "MISSING_INPUT", "message": "Тариф не сохранён.", "next_step": "Укажите тариф RaaS."}],
        "scenarios": [{
            "acquisition": "PURCHASE", "uncertainty": "BASE",
            "procurement": {"procurement_status": "UNVERIFIED"},
            "financial": {"status": "COMPLETE", "npv_project": {"status": "COMPLETE", "value": "12345.67", "unit": "RUB"},
                          "annual_ledgers": [{"year": 1, "primary_cf_base": "-100.00", "primary_cf_scenario": "-70.00", "differential_cf": "30.00"}]},
        }],
    }
    raw["checksums"]["result"] = _checksum(raw["result_snapshot"])
    pdf, _ = build_readable_report(EvidenceRunSnapshotV1.model_validate(raw), linked)
    text = _text(pdf)
    assert "12 345,67 ₽" in text
    assert "Год 1: без роботов -100,00 ₽" in text
    assert "нужна проверка паспортных данных" in text
    assert "условия закупки поставщиком не подтверждены" in text
    assert "Тариф не сохранён" in text
    assert "raas_monthly_per_robot_gross" in text
    assert "При аренде роботов (RaaS)" not in text


def test_capacity_only_report_uses_its_own_verified_snapshot():
    _, linked = _full_runs()
    pdf, _ = build_readable_report(linked)
    text = _text(pdf)
    assert "Приёмка и отгрузка" in text
    assert "1 000 паллет/день" in text
    assert "нет данных для оценки" in text
    assert "Расчёт мощности:" in text
    assert "Техническая мощность C11" in text
    assert "После покупки роботов" not in text
    assert "Сравнение денег по годам" not in text


def test_capacity_display_rounds_only_pdf_and_keeps_exact_snapshot():
    _, linked = _full_runs()
    raw = linked.model_dump(mode="json")
    value = raw["result_snapshot"]["capacity"]["value"]
    value["selected_fleet"] = 15
    value["nominal_capacity"] = {"value": "196.635", "unit": "unit/h"}
    value["effective_capacity"] = {"value": "137.650001", "unit": "unit/h"}
    value["coverage"] = {"value": "1", "unit": "1", "quantity_kind": "FRACTION"}
    value["raw_load_ratio"] = {"value": "0.990675", "unit": "1", "quantity_kind": "FRACTION"}
    raw["checksums"]["result"] = _checksum(raw["result_snapshot"])
    run = EvidenceRunSnapshotV1.model_validate(raw)
    saved = deepcopy(run.result_snapshot)
    pdf, digest = build_readable_report(run)
    text = _text(pdf)
    for value in ("15 роботов", "196,64 ед./ч", "137,65 ед./ч", "100 %", "99,07 %"):
        assert value in text
    assert run.result_snapshot == saved
    assert run.result_snapshot["capacity"]["value"]["effective_capacity"]["value"] == "137.650001"
    assert digest == "sha256:" + run.checksums["result"]


def test_linked_run_requires_matching_binding_and_verified_digest():
    run, linked = _full_runs()
    raw = linked.model_dump(mode="json")
    raw["project_id"] = str(uuid.uuid4())
    with pytest.raises(EvidenceExportIntegrityError):
        build_readable_report(run, EvidenceRunSnapshotV1.model_validate(raw))
    raw = linked.model_dump(mode="json")
    raw["result_snapshot"]["capacity"]["value"]["selected_fleet"] = 100
    with pytest.raises(EvidenceExportIntegrityError):
        build_readable_report(run, EvidenceRunSnapshotV1.model_validate(raw))


def test_report_consumes_real_orchestrator_values_without_new_finance_math():
    from calculation.service import analyze_capacity
    from economics_orchestrator import EconomicsExecutionContextV1, execute_economics_v2
    from persistence_api import _canonical_sha256, _comparable_economics_result
    from test_economics_orchestrator import _capacity_request, _inputs, _snapshot

    request = _capacity_request()
    snapshot = _snapshot()
    capacity_id = str(uuid.uuid4())
    capacity = analyze_capacity(request, snapshot, capacity_id)
    raw = golden_run().model_dump(mode="json")
    context = EconomicsExecutionContextV1(
        run_id=raw["run_id"], project_id=request.project_id, tenant_id="tenant.report",
        capacity_request=request, capacity_response=capacity.response,
        constraint_report=capacity.constraints.model_dump(mode="json"),
        executability=capacity.executability.model_dump(mode="json"),
    )
    calculated = execute_economics_v2(_inputs(), snapshot, context)
    saved_old = deepcopy(calculated.result_snapshot)
    for item in saved_old["scenarios"]:
        item.pop("report_facts")
    assert _canonical_sha256(_comparable_economics_result(calculated.result_snapshot, saved_old)) == _canonical_sha256(saved_old)
    assert "report_facts" in calculated.result_snapshot["scenarios"][0]
    tampered = deepcopy(saved_old)
    tampered["scenarios"][0]["financial"]["status"] = "INCOMPLETE"
    assert _canonical_sha256(_comparable_economics_result(calculated.result_snapshot, tampered)) != _canonical_sha256(tampered)
    raw["project_id"] = request.project_id
    raw["versions"]["application"] = calculated.application_version
    raw["input_snapshot"] = {"capacity_run_id": capacity_id, "economics": _inputs()}
    raw["result_snapshot"] = calculated.result_snapshot
    raw["checksums"]["input"] = _checksum(raw["input_snapshot"])
    raw["checksums"]["result"] = _checksum(raw["result_snapshot"])
    linked = golden_run().model_dump(mode="json")
    linked["run_id"] = capacity_id
    linked["project_id"] = request.project_id
    linked["run_kind"] = "CAPACITY_ANALYSIS"
    linked["input_snapshot"] = request.model_dump(mode="json")
    linked["result_snapshot"] = capacity.response.model_dump(mode="json")
    linked["checksums"]["input"] = _checksum(linked["input_snapshot"])
    linked["checksums"]["result"] = _checksum(linked["result_snapshot"])
    pdf, _ = build_readable_report(
        EvidenceRunSnapshotV1.model_validate(raw), EvidenceRunSnapshotV1.model_validate(linked)
    )
    text = _text(pdf)
    assert "Приёмка и отгрузка" in text
    assert "1 000 паллет/день" in text
    assert "Год 1: без роботов" in text
    assert "Чистая приведённая стоимость проекта:" in text
    for scenario in calculated.result_snapshot["scenarios"]:
        if scenario["uncertainty"] == "BASE":
            facts = scenario["report_facts"]
            assert _money(facts["project_capex_cashflow"]) in text
            assert _money(facts["project_npv"]["value"]) in text
