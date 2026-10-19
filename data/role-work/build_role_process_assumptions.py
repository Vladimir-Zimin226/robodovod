"""Rebuild the complete scenario table. All uncited splits and minutes are estimates."""

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import csv
import json


# staff, gross monthly RUB, staff source, salary source. A group may be split
# into distinct roles; a repeated role is then allocated among processes.
GROUPS = {
    ("WAREHOUSE", "forklift_driver"): (25, 120000, "Склад!C28, все 25 условно назначены на процесс", "Склад!C31"),
    ("WAREHOUSE", "loader"): (8, 80000, "Допущение, 8 сотрудников из прочего штата склада", "Допущение, 80000 gross"),
    ("WAREHOUSE", "storekeeper"): (8, 90000, "Допущение, 8 сотрудников из прочего штата склада", "Допущение, 90000 gross"),
    ("WAREHOUSE", "picker"): (80, 100000, "Склад!C27, условно 80 из 100", "Склад!C30"),
    ("WAREHOUSE", "sorter"): (20, 90000, "Склад!C27, условно 20 из 100", "Допущение, 90000 gross"),
    ("WAREHOUSE", "packer"): (20, 90000, "Склад!C29", "Допущение, 90000 gross"),
    ("WAREHOUSE", "cleaner"): (6, 65000, "Допущение, 6 сотрудников из прочего штата склада", "Допущение, 65000 gross"),
    ("WAREHOUSE", "inventory_worker"): (8, 90000, "Допущение, 8 сотрудников из прочего штата склада", "Допущение, 90000 gross"),
    ("AIRPORT", "baggage_handler"): (100, 100000, "Аэропорт!C31, условно 100 из 320", "Аэропорт!C33"),
    ("AIRPORT", "special_equipment_driver"): (30, 100000, "Аэропорт!C31, условно 30 из 320", "Аэропорт!C33"),
    ("AIRPORT", "perron_cleaner"): (30, 100000, "Аэропорт!C31, условно 30 из 320", "Аэропорт!C33"),
    ("AIRPORT", "ramp_worker"): (100, 100000, "Аэропорт!C31, условно 100 из 320", "Аэропорт!C33"),
    ("AIRPORT", "ground_support_worker"): (60, 100000, "Аэропорт!C31, условно 60 из 320", "Аэропорт!C33"),
    ("AIRPORT", "trolley_operator"): (80, 80000, "Аэропорт!C32, условно 80 из 180", "Допущение, 80000 gross"),
    ("AIRPORT", "terminal_cleaner"): (30, 65000, "Аэропорт!C32, условно 30 из 180", "Аэропорт!C34"),
    ("AIRPORT", "passenger_assistant"): (20, 70000, "Аэропорт!C32, условно 20 из 180", "Допущение, 70000 gross"),
    ("AIRPORT", "courier"): (20, 70000, "Аэропорт!C32, условно 20 из 180", "Допущение, 70000 gross"),
    ("AIRPORT", "security_guard"): (30, 80000, "Допущение, отдельная группа 30 вне двух групп датасета", "Допущение, 80000 gross"),
    ("AIRPORT", "runway_inspector"): (10, 100000, "Допущение, отдельная группа 10 вне двух групп датасета", "Допущение, 100000 gross"),
    ("CLINIC", "catering_worker"): (6, 52000, "Медучреждение!C50, условно 6 из 28 на доставке", "Медучреждение!C53"),
    ("CLINIC", "laundry_worker"): (18, 50000, "Медучреждение!C51", "Допущение, 50000 gross"),
    ("CLINIC", "sanitary"): (40, 55000, "Медучреждение!C49, условно 40 из 65", "Медучреждение!C52"),
    ("CLINIC", "porter"): (25, 55000, "Медучреждение!C49, условно 25 из 65", "Медучреждение!C52"),
    ("CLINIC", "lab_assistant"): (12, 65000, "Допущение, отдельная группа 12", "Допущение, 65000 gross"),
    ("CLINIC", "sterile_supply_worker"): (10, 55000, "Допущение, отдельная группа 10", "Допущение, 55000 gross"),
    ("CLINIC", "consumable_worker"): (6, 55000, "Допущение, отдельная группа 6", "Допущение, 55000 gross"),
    ("CLINIC", "lab_result_courier"): (4, 50000, "Допущение, отдельная группа 4", "Допущение, 50000 gross"),
    ("CLINIC", "cleaner"): (12, 45000, "Допущение, отдельная группа 12", "Допущение, 45000 gross"),
    ("CLINIC", "inventory_worker"): (4, 50000, "Допущение, отдельная группа 4", "Допущение, 50000 gross"),
}


def seed(spec, workload, residual):
    """kind process role allocation manual unit minutes status; paid=600/420."""
    kind, process, role, allocation, manual, unit, minutes, status = spec.split()
    return kind, process, role, Decimal(allocation), Decimal(manual), unit, Decimal(minutes), status, workload, residual


SEEDS = [
    seed("WAREHOUSE warehouse_receiving_shipping forklift_driver 1 100 pallet/person/shift 480 CALCULABLE", "Склад!C18+C19 = 2000 паллет/сутки, 25×100 = 2500 с резервом", "Приёмка, проверка и нестандартные паллеты"),
    seed("WAREHOUSE warehouse_receiving_shipping loader 1 250 pallet/person/shift 150 CALCULABLE", "Склад!C18+C19 = 2000 паллет/сутки, 2000/8 = 250", "Погрузка, крепление, сканирование и приёмка"),
    seed("WAREHOUSE warehouse_storage storekeeper 1 250 pallet/person/shift 90 REFERENCE_ONLY", "Те же 2000 паллет/сутки условно распределены на 8 кладовщиков", "Адресное хранение, учёт и инвентаризация"),
    seed("WAREHOUSE warehouse_picking picker 1 1250 pick/person/shift 210 REFERENCE_ONLY", "Склад!C20 = 100000 строк/сутки, 80×1250 = 100000, PICK принят равным строке заказа", "Выбор товара и проверка исключений"),
    seed("WAREHOUSE warehouse_picking sorter 1 5000 pick/person/shift 120 REFERENCE_ONLY", "Склад!C20 = 100000 строк/сутки, 20×5000 = 100000 при допущении конвейерной сортировки", "Контроль сортировки и повреждённых товаров"),
    seed("WAREHOUSE warehouse_palletizing packer 1 100 pallet/person/shift 270 CALCULABLE", "Склад!C18+C19 = 2000 паллет/сутки, 20×100 = 2000", "Упаковочные материалы, маркировка и проверка"),
    seed("WAREHOUSE warehouse_cleaning cleaner 1 1700 m2/person/shift 300 CALCULABLE", "Склад!C5 = 10000 м², 6×1700 = 10200 с малым резервом", "Кромки, разливы и ручная дезинфекция"),
    seed("WAREHOUSE warehouse_inventory inventory_worker 1 500 item/person/shift 120 REFERENCE_ONLY", "Условно принято 4000 единиц учёта/сутки, в датасете поток инвентаризации отсутствует", "Сверка расхождений и повреждённого товара"),
    seed("AIRPORT airport_baggage baggage_handler 1 350 item/person/shift 147 CALCULABLE", "Аэропорт!C20 = 35000 мест багажа/сутки, 100×350 = 35000", "Идентификация, сканирование и погрузка нестандартного багажа"),
    seed("AIRPORT airport_catering trolley_operator 0.4 700 portion/person/shift 147 CALCULABLE", "Аэропорт!C23 = 22000 порций/сутки, 32×700 = 22400", "Загрузка тележек, контроль температуры и передача"),
    seed("AIRPORT airport_fuelling special_equipment_driver 1 10 delivery/person/shift 42 REFERENCE_ONLY", "Аэропорт!C24 = 280 рейсов/сутки, 30×10 = 300, DELIVERY условно равен рейсу", "Саму заправку и контроль безопасности выполняет человек"),
    seed("AIRPORT airport_internal_logistics trolley_operator 0.4 14 cart/person/shift 210 CALCULABLE", "Аэропорт!C26 = 420 рейсов тележек/сутки, 32×14 = 448", "Загрузка, проверка доступа и приёмка"),
    seed("AIRPORT airport_terminal_cleaning terminal_cleaner 1 1700 m2/person/shift 252 CALCULABLE", "Аэропорт!C28 = 51000 м²/сутки, 30×1700 = 51000", "Кромки, лестницы и ручная санитарная обработка"),
    seed("AIRPORT airport_apron_cleaning perron_cleaner 1 3400 m2/person/shift 105 SAFETY_BLOCKED", "Аэропорт!C5 = 100000 м², 30×3400 = 102000, допуск робота на перрон не подтверждён", "Ручная уборка сложных участков; эксплуатация робота требует допуска"),
    seed("AIRPORT airport_waste trolley_operator 0.2 140 kg/person/shift 168 CALCULABLE", "Аэропорт!C29 = 85 контейнеров/сутки × условные 25 кг = 2125 кг, 16×140 = 2240", "Сортировка, закрытие контейнера и санитарная проверка"),
    seed("AIRPORT airport_inspection runway_inspector 1 10 item/person/shift 63 REFERENCE_ONLY", "Условно 10 проверок/смену, в датасете поток инспекций отсутствует", "Решение о состоянии ВПП остаётся за инспектором"),
    seed("AIRPORT airport_inspection security_guard 1 20 item/person/shift 42 REFERENCE_ONLY", "Условно 20 проверок/смену, в датасете поток проверок охраны отсутствует", "Контроль доступа и реагирование остаются за охраной"),
    seed("AIRPORT airport_passenger_assistance passenger_assistant 1 8 delivery/person/shift 42 REFERENCE_ONLY", "Условно 8 запросов помощи/смену, в датасете поток запросов отсутствует", "Непосредственная помощь пассажиру остаётся за человеком"),
    seed("AIRPORT airport_passenger_assistance courier 1 10 delivery/person/shift 147 REFERENCE_ONLY", "Условно 10 доставок/смену, в датасете поток доставок отсутствует", "Проверка документов и передача адресату"),
    seed("AIRPORT airport_ground_service ramp_worker 1 3 delivery/person/shift 63 REFERENCE_ONLY", "Аэропорт!C16 = 280 рейсов/сутки, 100×3 = 300, DELIVERY условно равен рейсу", "Обслуживание борта и погрузку выполняют люди"),
    seed("AIRPORT airport_ground_service ground_support_worker 1 5 delivery/person/shift 63 REFERENCE_ONLY", "Аэропорт!C16 = 280 рейсов/сутки, 60×5 = 300, DELIVERY условно равен рейсу", "Подключение оборудования и контроль выполняют люди"),
    seed("CLINIC clinic_food catering_worker 1 325 portion/person/shift 168 CALCULABLE", "Медучреждение!C19 = 1950 порций/сутки, 6×325 = 1950", "Приготовление, загрузка, раздача, контроль питания и санитарии"),
    seed("CLINIC clinic_linen laundry_worker 1 200 kg/person/shift 168 CALCULABLE", "Медучреждение!C25+C26 = 3600 кг/сутки, 18×200 = 3600", "Стирка, сортировка, упаковка и санитарный контроль"),
    seed("CLINIC clinic_medicines sanitary 0.5 20 delivery/person/shift 63 CALCULABLE", "Медучреждение!C32 = 340 заявок/сутки, 20×20 = 400", "Комплектация, проверка назначения и срочные заявки"),
    seed("CLINIC clinic_medicines porter 0.6 25 delivery/person/shift 210 CALCULABLE", "Медучреждение!C32 = 340 заявок/сутки, 15×25 = 375", "Передача, проверка получателя и срочные заявки"),
    seed("CLINIC clinic_biomaterials lab_assistant 1 100 sample/person/shift 126 CALCULABLE", "Медучреждение!C39 = 1200 проб/сутки, 12×100 = 1200", "Забор, маркировка, температурный режим и приёмка лабораторией"),
    seed("CLINIC clinic_sterile_sets sterile_supply_worker 1 12 set/person/shift 105 CALCULABLE", "Условно 12 операционных × 10 комплектов = 120 комплектов/сутки, 10×12 = 120", "Стерилизация, упаковка и прослеживаемость"),
    seed("CLINIC clinic_consumables consumable_worker 1 75 item/person/shift 168 CALCULABLE", "Медучреждение!C37 = 45 рейсов/сутки × условные 10 предметов = 450, 6×75 = 450", "Комплектация, учёт материалов и передача отделению"),
    seed("CLINIC clinic_waste_a sanitary 0.3 75 kg/person/shift 63 CALCULABLE", "Медучреждение!C44 = 850 кг/сутки, 12×75 = 900", "Сортировка, герметизация и проверка контейнеров"),
    seed("CLINIC clinic_waste_a porter 0.32 110 kg/person/shift 189 CALCULABLE", "Медучреждение!C44 = 850 кг/сутки, 8×110 = 880", "Передача контейнеров и дезинфекция"),
    seed("CLINIC clinic_waste_b sanitary 0.2 30 kg/person/shift 42 SAFETY_BLOCKED", "Медучреждение!C45 = 220 кг/сутки, 8×30 = 240, маршрут робота не согласован", "Сортировка, герметизация и санитарный контроль остаются за человеком"),
    seed("CLINIC clinic_waste_b porter 0.08 110 kg/person/shift 42 SAFETY_BLOCKED", "Медучреждение!C45 = 220 кг/сутки, 2×110 = 220, маршрут робота не согласован", "Передача контейнера и дезинфекция остаются за человеком"),
    seed("CLINIC clinic_results lab_result_courier 1 7 delivery/person/shift 105 CALCULABLE", "Медучреждение!C42 = 28 рейсов/сутки, 4×7 = 28", "Передача, проверка получателя и срочные случаи"),
    seed("CLINIC clinic_cleaning cleaner 1 1500 m2/person/shift 189 CALCULABLE", "Активная зона 18000 м² из типового сценария, 12×1500 = 18000", "Контактные поверхности, палаты и инфекционные зоны"),
    seed("CLINIC clinic_inventory inventory_worker 1 125 item/person/shift 84 REFERENCE_ONLY", "Условно 500 единиц учёта/сутки, 4×125 = 500", "Сверка остатков, списание и расхождения"),
]

IDS = {
    ("warehouse_receiving_shipping", "forklift_driver"): "RW-WH-FORKLIFT-01",
    ("warehouse_receiving_shipping", "loader"): "RW-WH-LOADER-01",
    ("airport_terminal_cleaning", "terminal_cleaner"): "RW-AP-CLEANER-01",
    ("clinic_food", "catering_worker"): "RW-CL-FOOD-01",
}

TECHNICAL_TASKS = {
    "forklift_driver": "Перевозка паллет между точками, погрузка проверяется отдельно",
    "loader": "Перевозка паллет к зоне ручной погрузки",
    "storekeeper": "Подача паллет к месту хранения",
    "picker": "Подвоз товара к станции ручного отбора",
    "sorter": "Перемещение и сортировка грузовых мест",
    "packer": "Паллетизация готовых упаковок",
    "cleaner": "Уборка доступной площади пола",
    "inventory_worker": "Считывание меток и сбор данных об остатках",
    "baggage_handler": "Перевозка стандартного багажа между узлами",
    "trolley_operator": "Перевозка тележек или контейнеров по указанному потоку",
    "special_equipment_driver": "Перевозка закрытого оборудования к пункту подготовки; без заправки",
    "terminal_cleaner": "Уборка доступной площади терминала",
    "perron_cleaner": "Уборка выделенного участка перрона при условном допуске",
    "runway_inspector": "Сбор изображений покрытия для решения инспектора",
    "security_guard": "Патрульная видеосъёмка без решения об охране",
    "passenger_assistant": "Перевозка багажа по запросу без сопровождения человека",
    "courier": "Доставка документов или вещей между разрешёнными точками",
    "ramp_worker": "Перевозка закрытого груза по разрешённому маршруту",
    "ground_support_worker": "Доставка оборудования между наземными точками",
    "catering_worker": "Перевозка готовых порций из пищеблока",
    "laundry_worker": "Перевозка упакованного белья",
    "sanitary": "Перевозка закрытого контейнера по выделенному маршруту",
    "porter": "Перевозка закрытого контейнера по выделенному маршруту",
    "lab_assistant": "Перевозка запечатанных проб с контролем условий",
    "sterile_supply_worker": "Перевозка запечатанных стерильных наборов",
    "consumable_worker": "Доставка упакованных расходников",
    "lab_result_courier": "Физическая доставка результатов; цифровой поток исключён",
}

SAFETY_CONDITIONS = {
    "airport_apron_cleaning": "Допуск на перрон, погода, зоны движения, пригодность модели и маршрут не подтверждены",
    "clinic_waste_b": "Санитарный режим, герметичный контейнер, маршрут, дезинфекция и пригодность модели не подтверждены",
}

HEADER = "object_kind;process_id;process_code;role_id;role_code;object_role_headcount;process_allocation_fraction;headcount_source_ref;monthly_amount_rub_per_person;monthly_amount_basis;salary_source_ref;manual_units_per_person_shift;manual_unit;robotizable_task_minutes_per_person_shift;paid_process_minutes_per_person_shift;robotizable_fraction;residual_operations;work_data_source;work_basis;measurement_date;evidence_ref;confirmed;calculation_status;technical_task;safety_conditions;scenario_purchase_price_rub;scenario_raas_monthly_rub;scenario_rate_source".split(";")


def render():
    allocations = defaultdict(Decimal)
    records = []
    for kind, process, role, fraction, manual, unit, minutes, status, workload, residual in SEEDS:
        count, gross, head_ref, salary_ref = GROUPS[kind, role]
        paid = Decimal(600 if kind == "WAREHOUSE" else 420)
        effective = Decimal(count) * fraction
        assert effective == int(effective) and 0 <= minutes <= paid and manual > 0
        allocations[kind, role] += fraction
        if status == "CALCULABLE" and fraction < 1:
            status = "ALLOCATION_REQUIRED"
        evidence = IDS.get((process, role), f"RW-{kind}-{process}-{role}".upper())
        object_id = f"draft.{kind.lower()}"
        work_basis = f"{evidence}: {workload.replace(';', ',')}. Доля {minutes}/{paid} — сценарное допущение, не замер"
        salary_basis = salary_ref.replace(";", ",")
        salary_detail = f"{salary_basis} × 1.302" if "gross" in salary_basis else f"{salary_basis} {gross} gross × 1.302"
        records.append([kind, f"zone.{object_id}.main.{process}", process, f"{object_id}.{role}", role,
                        str(count), str(fraction), head_ref.replace(";", ","),
                        str(int(Decimal(gross) * Decimal("1.302"))), "EMPLOYER_COST",
                        salary_detail,
                        str(manual), unit, str(minutes), str(paid), str(minutes / paid), residual.replace(";", ","),
                        "ASSUMPTION", work_basis, "", evidence,
                        str(status in {"CALCULABLE", "ALLOCATION_REQUIRED"}).lower(), status,
                        TECHNICAL_TASKS[role].replace(";", ","), SAFETY_CONDITIONS.get(process, ""),
                        "3000000", "120000", "ASSUMPTION: manual units per shift / hours per shift, supplier rate and price unconfirmed"])
    assert len(records) == 35
    assert all(value == 1 for value in allocations.values()), allocations
    assert 25 + 8 + 8 + 80 + 20 + 20 + 6 + 8 <= 180
    assert 100 + 30 + 30 + 100 + 60 == 320
    assert 80 + 30 + 20 + 20 <= 180
    assert 40 + 25 == 65
    return records


if __name__ == "__main__":
    records = render()
    with Path(__file__).with_name("role-process-measurement-template-v1.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter=";", lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(records)
    module_data = Path(__file__).parents[2] / "frontend" / "src" / "roleWorkScenarioData.json"
    module_data.write_text(json.dumps({"schema_version": "role-work-scenario-data-v2",
        "records": [dict(zip(HEADER, record, strict=True)) for record in records]},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage_file = Path(__file__).with_name("role-coverage-v2.csv")
    with coverage_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter=";", lineterminator="\n")
        writer.writerow(["object_kind", "process_code", "role_code", "calculation_status", "unit",
                         "technical_task", "demand_units_per_day", "robot_rate_source",
                         "purchase_price_source", "raas_tariff_source", "catalog_candidates",
                         "model_fallback", "safety_or_blocking_conditions"])
        for values in records:
            row = dict(zip(HEADER, values, strict=True))
            demand = Decimal(row["object_role_headcount"]) * Decimal(row["process_allocation_fraction"]) * Decimal(row["manual_units_per_person_shift"])
            writer.writerow([row["object_kind"], row["process_code"], row["role_code"],
                             row["calculation_status"], row["manual_unit"].split("/")[0],
                             row["technical_task"], str(demand), "SCENARIO_ASSUMPTION",
                             "SCENARIO_ASSUMPTION", "SCENARIO_ASSUMPTION",
                             "DISCOVERY_RUNTIME_FUNCTION_MATCH", "SCENARIO_TYPE_IF_NO_MATCH",
                             row["safety_conditions"] or ("C11 passport formula absent" if row["calculation_status"] == "REFERENCE_ONLY" else "Physical fit unconfirmed")])
    print(f"Wrote {len(records)} role-process rows and browser data")
