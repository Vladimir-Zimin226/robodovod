"""Build the public, immutable warehouse demo from one authored engine capture.

No database or production run is read or written. The ZIP and PDF are derived
from the same validated package that the guest page imports.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

from calculation.readable_report import _pdf  # noqa: E402
from calculation.scheduling import SimulationReportV3, SimulationRequestV2, run_simulation  # noqa: E402
from calculation_contracts import semantic_digest  # noqa: E402
from build_warehouse_guest_demo import build_capture  # noqa: E402
from presentation import field as presentation_field, status as presentation_status  # noqa: E402

VERSION = "warehouse-pallet-demo-v1"
FRONTEND = ROOT / "frontend/src/warehouseGuestPackage.json"
PUBLIC = ROOT / "frontend/public/demo/warehouse-pallet-v1"
ARCHIVE_DATE = (2026, 9, 25, 0, 0, 0)
CHAIN = [
    {"operation": "Перевозка подготовленных паллет", "role": "Водитель погрузчика", "status": "MODELED"},
    {"operation": "Отбор строк и штук", "role": "Комплектовщик", "status": "NOT_MODELED"},
    {"operation": "Передача тары", "role": "Сортировщик", "status": "NOT_MODELED"},
    {"operation": "Упаковка", "role": "Оператор упаковочной линии", "status": "NOT_MODELED"},
    {"operation": "Паллетизация", "role": "Укладчик паллет", "status": "NOT_MODELED"},
]
LIMITATIONS = [
    "Схема 2D/3D условная: геометрия объекта и фактическая телеметрия не предоставлены.",
    "C05 требует проверки на объекте; пригодность и закупка робота не подтверждены.",
    "Цена, RaaS и прочие денежные входы являются сценарными, не предложением поставщика.",
    "Труд комплектовщиков, сортировщиков и упаковщиков не включён в денежный эффект.",
    "Отбор, передача тары, упаковка и паллетизация не моделировались из паллетного потока.",
]


def encode(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_package() -> dict:
    demo, assumptions, capacity_request, inputs, execution = build_capture()
    spec = execution.scenario_spec_snapshot
    primary = next(item for item in spec["operating_windows"] if item["window_id"] == "window.primary")
    request = SimulationRequestV2.model_validate({
        "schema_version": "simulation-request-v2",
        "request_id": "simulation.public.warehouse.pallet.v1",
        "tenant_id": execution.result_snapshot["tenant_id"],
        "project_id": execution.result_snapshot["project_id"],
        "scenario_spec": spec,
        "mode": "DAILY", "peak_factor": None, "sla": None, "resources": [],
        "limits": {"max_jobs_per_day": 10000, "max_fleet": 100,
                   "max_runtime_seconds": 60, "progress_event_batch": 1000},
        "model_start": {"weekday": "MONDAY", "seconds_from_midnight": int(primary["start_time"]["value"]),
                        "timezone": primary["timezone"]},
        "process_chain": None,
    })
    report = run_simulation(request)
    if not isinstance(report, SimulationReportV3):
        raise ValueError(f"public simulation failed: {report}")
    request_json = request.model_dump(mode="json")
    report_json = report.model_dump(mode="json")
    if demo["input_digest"] != semantic_digest({"capacity": capacity_request.model_dump(mode="json"), "economics": inputs}):
        raise ValueError("capacity/economics input digest mismatch")
    if demo["result_digest"] != semantic_digest(execution.result_snapshot):
        raise ValueError("economics result digest mismatch")
    if (spec["analysis"]["capacity_run_id"] != "run.demo.warehouse.c11"
            or spec["analysis"]["capacity_request_digest"] != semantic_digest(capacity_request)
            or report_json["scenario_revision_id"] != spec["revision_id"]
            or report_json["replay"]["canonical_request_digest"] != semantic_digest(request)
            or report_json["replay"]["scenario_spec_digest"] != semantic_digest(request.scenario_spec)
            or report_json["workload"]["daily_units"] != "2000"
            or report_json["workload"]["fleet_units"] != demo["capacity"]["value"]["selected_fleet"]
            or spec["routes"][0]["one_way_distance"]["value"] != "120"
            or len(demo["scenarios"]) != 6):
        raise ValueError("public package has inconsistent scenario bindings")
    if any(stage["status"] != "EXTERNAL_BOUNDARY" for stage in report_json["stages"]):
        raise ValueError("unconfirmed warehouse stages became modeled")
    return {
        "schema_version": VERSION,
        "title": "Паллетная перевозка на типовом складе",
        "as_of": demo["as_of"],
        "demo": demo,
        "assumptions": assumptions,
        "simulation": {"request": request_json, "report": report_json},
        "chain": CHAIN,
        "limitations": LIMITATIONS,
        "bindings": {
            "assumptions_version": assumptions["schema_version"],
            "capacity_economics_input_digest": demo["input_digest"],
            "economics_result_digest": demo["result_digest"],
            "scenario_revision_id": spec["revision_id"],
            "simulation_request_digest": report_json["replay"]["canonical_request_digest"],
            "simulation_report_digest": report_json["replay"]["report_content_digest"],
        },
        "provenance": {
            "capacity": "scripts/build_warehouse_guest_demo.py; backend/calculation/service.py; авторский профиль backend/test_economics_orchestrator.py",
            "economics": "backend/economics_orchestrator.py; data/scenarios/warehouse-economics-demo-v1.json",
            "simulation": "backend/calculation/scheduling.py; сохранённый offline результат для этого же ScenarioSpec",
            "geometry": "Синтетическая схема по ScenarioSpec; план объекта не предоставлен",
            "financial_inputs": "Авторский проверочный сценарий; условия объекта и поставщика не подтверждены",
        },
    }


def pdf_bytes(package: dict) -> bytes:
    demo = package["demo"]
    report = package["simulation"]["report"]
    lines = [
        ("РОБОДОВОД / ПУБЛИЧНОЕ ДЕМО", "brand"),
        (package["title"], "title"),
        (f"Сценарий от {package['as_of']} · пакет {VERSION}", "subtitle"),
        ("Предварительный расчёт: 2 000 паллет/сутки, 2 × 11 ч, маршрут 120 м, обмен 90 с.", "cover"),
        ("Числа относятся только к перевозке подготовленных паллет.", "cover"),
        ("page", "page"),
        ("Основные результаты", "section"),
        (f"Потребный парк: {demo['capacity']['value']['selected_fleet']} роботов.", "metric"),
        (f"Эффективная мощность: {demo['capacity']['value']['effective_capacity']['value']} паллет/ч.", "body"),
        (f"Симуляция: {report['workload']['daily_units']} паллет/сутки; парк {report['workload']['fleet_units']} роботов.", "body"),
        (f"Выполнено до конца окна: {report['queue']['completed_by_measurement_end']} заданий; максимум очереди: {report['queue']['maximum_jobs']}.", "body"),
        ("Денежные сценарии · NPV проекта", "section"),
    ]
    labels = {"PURCHASE": "Покупка", "RAAS": "Аренда роботов", "PESSIMISTIC": "пессимистичный", "BASE": "базовый", "OPTIMISTIC": "оптимистичный"}
    baseline = next(item for item in demo["scenarios"] if item["uncertainty"] == "BASE")["annual_ledgers"][0]["primary_cf_base"]
    lines.append((f"Денежный поток без роботов, год 1: {baseline} ₽.", "body"))
    for item in demo["scenarios"]:
        value = item["npv_project"]
        lines.append((f"{labels[item['acquisition']]}, {labels[item['uncertainty']]}: {value['value'] if value['status'] == 'COMPLETE' else 'не рассчитано'} ₽.", "body"))
    lines += [
        ("Чувствительность NPV · тестовые отклонения ±10 %", "section"),
        *((f"{presentation_field(item['override']['parameter_id'])[0]}, {'увеличение' if item['override']['direction'] == 'UPPER' else 'уменьшение'}: {item['npv_project']['delta_value']} ₽."
           if item['status'] != 'BLOCKED' else f"{presentation_field(item['override']['parameter_id'])[0]}: не рассчитано.", "body") for item in demo["sensitivity"]),
        ("Границы применимости", "section"),
        (f"Проверка пригодности на объекте: {presentation_status(demo['c05'])}; закупка: {presentation_status(demo['procurement'])}.", "body"),
        *((value, "body") for value in package["limitations"]),
        ("Охват складской цепочки", "section"),
        *((f"{item['operation']}: {'рассчитано' if item['status'] == 'MODELED' else 'не рассчитано'}; роль — {item['role']}.", "body") for item in package["chain"]),
        ("Допущения и источники", "section"),
        (package["assumptions"]["source"], "body"),
        *((f"{name}: {value['value']} {value['unit']}. {value['rationale']}. Источник: авторский сценарий.", "body") for name, value in package["assumptions"]["fields"].items()),
        *((f"{name}: {value}. Источник: авторский сценарий.", "body") for name, value in package["assumptions"]["other_inputs"].items()),
        ("Техническая привязка", "section"),
        (f"Сценарий: {package['bindings']['scenario_revision_id']}.", "body"),
        (f"Вход расчёта: {package['bindings']['capacity_economics_input_digest']}.", "body"),
        (f"Результат экономики: {package['bindings']['economics_result_digest']}.", "body"),
        (f"Отчёт симуляции: {package['bindings']['simulation_report_digest']}.", "body"),
        ("JSON входов и полный сохранённый отчёт симуляции находятся в ZIP.", "note"),
    ]
    return _pdf(lines)


def archive_bytes(files: dict[str, bytes]) -> bytes:
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, ARCHIVE_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return result.getvalue()


def expected_files() -> dict[Path, bytes]:
    package = build_package()
    payload = encode(package)
    pdf = pdf_bytes(package)
    assumptions = encode(package["assumptions"])
    request = encode(package["simulation"]["request"])
    report = encode(package["simulation"]["report"])
    manifest = encode({
        "schema_version": "warehouse-guest-package-manifest-v1",
        "package_version": VERSION,
        "bindings": package["bindings"],
        "files": {name: {"sha256": digest(data), "bytes": len(data)} for name, data in {
            "package.json": payload, "report.pdf": pdf, "assumptions.json": assumptions,
            "simulation-request.json": request, "simulation-report.json": report,
        }.items()},
    })
    zip_data = archive_bytes({
        "README.txt": ("Паллетная перевозка на типовом складе. Предварительный публичный пример.\n"
                       "Начните с report.pdf. Сверьте файлы с manifest.json; условия и ограничения описаны в PDF.\n").encode("utf-8"),
        "manifest.json": manifest, "package.json": payload, "report.pdf": pdf,
        "assumptions.json": assumptions, "simulation-request.json": request,
        "simulation-report.json": report,
    })
    return {
        FRONTEND: payload,
        PUBLIC / "manifest.json": manifest,
        PUBLIC / "report.pdf": pdf,
        PUBLIC / "evidence.zip": zip_data,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = expected_files()
    if args.check:
        mismatches = [str(path.relative_to(ROOT)) for path, data in files.items() if not path.is_file() or path.read_bytes() != data]
        if mismatches:
            print("Guest package out of date:", ", ".join(mismatches))
        return int(bool(mismatches))
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for path, data in files.items():
        path.write_bytes(data)
        print(f"{path.relative_to(ROOT)}: {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
