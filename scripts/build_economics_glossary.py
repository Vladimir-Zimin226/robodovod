"""Publish explanatory economics examples from the current calculation engines."""

from __future__ import annotations

import argparse
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

from build_warehouse_guest_demo import build_capture  # noqa: E402
from calculation.capacity.transport import ENGINE_VERSION as CAPACITY_ENGINE_VERSION  # noqa: E402
from calculation.economics.cashflow import FinancialAnalysisRequestV1  # noqa: E402
from calculation.economics.raas import RaasAnalysisRequestV1  # noqa: E402
from calculation.service import analyze_financials, analyze_raas_financials  # noqa: E402

TARGET = ROOT / "frontend/src/economicsGlossary.json"


def display(value: str | int) -> str:
    """Format an engine value for a Russian reader; never recalculate it."""
    return f"{Decimal(value):,.2f}".replace(",", " ").replace(".", ",")


def fixture(name: str) -> dict:
    return json.loads((ROOT / "contracts/fixtures" / name).read_text(encoding="utf-8"))


def entry(id: str, title: str, synonyms: list[str], notation: str, formula: str,
          units: str, inputs: list[tuple[str, str, str]], example: str,
          applicability: str, source: str, section: str, formula_ids: list[str],
          example_source: str) -> dict:
    return dict(id=id, title=title, synonyms=synonyms, notation=notation,
                formula=formula, units=units,
                inputs=[dict(field=field, label=label, source=origin) for field, label, origin in inputs],
                example=example, applicability=applicability, source=source,
                section=section, formula_ids=formula_ids, example_source=example_source)


def build() -> dict:
    demo, _, _, _, execution = build_capture()
    financial_fixture = fixture("financial-result-v2.warehouse.golden.json")
    financial = analyze_financials(FinancialAnalysisRequestV1.model_validate(financial_fixture["request"]))
    assert financial.model_dump(mode="json") == financial_fixture["result"], "financial golden fixture drift"
    raas_fixture = fixture("raas-financial-result-v1.warehouse.golden.json")
    raas = analyze_raas_financials(RaasAnalysisRequestV1.model_validate(raas_fixture["request"]))
    assert raas.model_dump(mode="json") == raas_fixture["result"], "RaaS golden fixture drift"
    f = financial_fixture["result"]
    r = raas_fixture["result"]
    fq = financial_fixture["request"]
    discount_percent = Decimal(fq["discount_rate"]["value"]) * 100
    discount_label = format(discount_percent.normalize(), "f").replace(".", ",")
    cap = demo["capacity"]["value"]
    first = f["annual_ledgers"][0]
    source_f = "financial-result-v2.warehouse.golden.json; пересчёт analyze_financials"
    source_r = "raas-financial-result-v1.warehouse.golden.json; пересчёт analyze_raas_financials"
    source_d = "склад 2 000 паллет/сутки, 120 м; пересчёт build_warehouse_guest_demo"
    entries = [
        entry("productivity", "Производительность", ["пропускная способность", "скорость обработки"], "Qном",
              "Qном = 3600 / время цикла × единиц за рейс. Время цикла учитывает маршрут и обмен.", "ед./ч на робота",
              [("process.route_distance", "Длина маршрута", "Расчёт → процесс"), ("process.exchange", "Время обмена", "Расчёт → процесс"), ("process.explicit_batch", "Единиц за рейс", "Расчёт → процесс")],
              f"Склад: номинальная производительность ≈ {display(cap['nominal_capacity']['value'])} ед./ч на робота; эффективная после доступности ≈ {display(cap['effective_capacity']['value'])} ед./ч.",
              "Для активного транспортного процесса с заданным циклом и вместимостью рейса.", "Профиль процесса, параметры робота, C11.", "Расчёт → парк и производительность", ["F02", "F03"], source_d),
        entry("fleet", "Потребный парк", ["количество роботов", "число роботов"], "N",
              "N = ⌈(спрос за сутки / рабочие часы × пик × (1 + резерв)) / (Qном × доступность)⌉.", "роботов",
              [("process.demand", "Поток за сутки", "Расчёт → процесс"), ("process.schedule", "Смены и часы", "Расчёт → график"), ("policy.capacity", "Доступность, пик и резерв", "Действующие правила C11 и подтверждённые допущения")],
              f"Склад: {cap['recommended_fleet']} роботов для 2 000 паллет/сутки; плечо 120 м.",
              "Округление вверх применяется после учёта доступности; выбранный парк может отличаться от рекомендации.", "C11, график, допущения о пике и резерве.", "Расчёт → парк и производительность", ["F01", "F04"], source_d),
        entry("baseline", "Базовый денежный поток", ["текущий сценарий", "денежный поток без роботов"], "CFбаза",
              "CFбаза,t = − расходы действующего процесса в году t. Проектный поток = CFроботы,t − CFбаза,t.", "₽/год",
              [("process.role_refs", "Роли, численность и зарплата gross", "Расчёт → процесс"), ("manual_units_per_shift", "Ручная производительность", "Расчёт → экономика → Труд")],
              f"Проверочный склад, год 1: базовый поток {display(first['primary_cf_base'])} ₽; разница с роботизацией {display(first['differential_cf'])} ₽.",
              "Только при известных затратах базового процесса; неизвестные суммы дают неполный результат.", "C14 труд и C16 денежные потоки; подтверждённые зарплаты и расходы.", "Отчёт → денежные потоки", ["F23", "F27"], source_f),
        entry("capex", "CAPEX", ["капитальные вложения", "первоначальные инвестиции"], "CAPEX",
              "CAPEX = сумма разовых капитальных строк + резерв на капитал. В денежном потоке года 0 это отток.", "₽ единовременно",
              [("implementation_cost_total_gross", "Внедрение и интеграция", "Расчёт → экономика → Покупка"), ("shared_site_capital_gross", "Общие разовые расходы площадки", "Расчёт → экономика → Покупка"), ("organizer_price_currency_rub_confirmed", "Подтверждение трактовки цены", "Расчёт → экономика → Покупка")],
              f"Проверочный склад, покупка: CAPEX {display(fq['purchase_ledger']['capex_gross'])} ₽.",
              "Покупка: оборудование и площадка; RaaS: только капитал заказчика по инфраструктуре.", "C15 коммерческие строки и подтверждённые условия.", "Расчёт → экономика → Покупка", ["F16", "F17"], source_f),
        entry("opex", "OPEX", ["операционные расходы", "эксплуатационные затраты"], "OPEX",
              "OPEX года = сервис + ПО + связь + энергия + страхование + расходники + ремонт + прочие годовые строки.", "₽/год",
              [("annual_service_per_robot_gross", "Сервис одного робота", "Расчёт → экономика → Покупка"), ("average_power_w", "Средняя мощность", "Расчёт → экономика → Покупка"), ("shared_annual_cost_gross", "Общие годовые расходы", "Расчёт → экономика → Покупка")],
              f"Проверочный склад, год 1: OPEX покупки ≈ {display(fq['purchase_ledger']['annual_ledgers'][0]['operating_total'])} ₽.",
              "Состав зависит от собственности, гарантии и подтверждённых договорных условий.", "C15 годовой реестр расходов и регистр тарифов.", "Расчёт → экономика → Покупка", ["F18", "F19", "F20", "F21"], source_f),
        entry("tco", "Стоимость владения", ["цена владения", "TCO", "совокупная стоимость владения"], "TCO",
              "TCO покупки = CAPEX + Σ OPEX за горизонт; TCO за вычетом остаточной стоимости = TCO − остаточная стоимость.", "₽ за горизонт",
              [("horizon_years", "Горизонт оценки", "Расчёт → экономика → Покупка"), ("annual_service_per_robot_gross", "Сервис одного робота", "Расчёт → экономика → Покупка"), ("shared_site_capital_gross", "Разовые расходы площадки", "Расчёт → экономика → Покупка")],
              f"Проверочный склад: TCO {display(f['tco_purchase_gross']['value'])} ₽; после остаточной стоимости {display(f['tco_purchase_net_of_residual']['value'])} ₽.",
              "Для покупки; налоговый эффект и базовый сценарий в эту метрику не входят.", "C15 расходы, C16 стоимость владения.", "Отчёт → экономика покупки", ["F30"], source_f),
        entry("labor", "Экономия труда", ["снижение ФОТ", "эффект от персонала"], "ΔФОТ",
              "ΔФОТ = стоимость труда базового процесса − стоимость оставшихся ролей и новых функций; изменения вводятся по ролям.", "₽/год",
              [("process.role_refs", "Роли, численность и зарплата gross", "Расчёт → процесс"), ("manual_units_per_shift", "Ручная производительность", "Расчёт → экономика → Труд"), ("control_headcount", "Диспетчеры", "Расчёт → экономика → Труд")],
              f"Проверочный склад, год 1: прямой труд базы {display(next(x['amount'] for x in first['base_lines'] if x['line_id'].endswith('base-direct-labour')))} ₽; оставшийся труд {display(next(x['amount'] for x in first['scenario_lines'] if x['line_id'].endswith('scenario-remaining-labour')))} ₽. Это две строки эффекта, без других расходов.",
              "Только для подтверждённых ролей и трудовых затрат; сокращение персонала не предполагается автоматически.", "C14 ролевая модель труда, C16 годовые строки.", "Расчёт → экономика → Труд", ["F23"], source_f),
        entry("payback", "Окупаемость", ["срок окупаемости", "возврат инвестиций"], "PBP",
              "Первый год, когда накопленная сумма разностных потоков CFроботы − CFбаза достигает нуля; внутри года — линейная интерполяция. Дисконтированная версия учитывает ставку.", "лет",
              [("horizon_years", "Горизонт оценки", "Расчёт → экономика → Покупка"), ("discount_rate", "Ставка для дисконтированной версии", "Расчёт → экономика → Покупка"), ("process.role_refs", "Затраты базового труда", "Расчёт → процесс")],
              f"Проверочный склад: простая окупаемость {display(f['simple_payback']['value'])} года; дисконтированная {display(f['discounted_payback']['value'])} года.",
              "Если накопленный эффект не перекрывает вложения за горизонт, показывается «не достигнута».", "C16 разностный денежный поток; metrics.payback.", "Отчёт → экономика покупки", ["F29"], source_f),
        entry("npv", "Чистая приведённая стоимость", ["NPV", "ЧПС", "дисконтированный эффект"], "NPV",
              "NPV проекта = Σ CFроботы,t / (1 + r)^t − Σ CFбаза,t / (1 + r)^t, начиная с года 0.", "₽",
              [("discount_rate", "Ставка дисконтирования r, доля", "Расчёт → экономика → Покупка"), ("horizon_years", "Горизонт оценки", "Расчёт → экономика → Покупка"), ("process.role_refs", "Расходы базового процесса", "Расчёт → процесс")],
              f"Проверочный склад, ставка {discount_label}%: NPV покупки {display(f['npv_project']['value'])} ₽.",
              "Требует полных денежных потоков обоих сценариев; при пропуске обязательных входов NPV не рассчитывается.", "C16 денежные потоки, metrics.npv; ставка из политики или пользователя.", "Отчёт → экономика покупки или RaaS", ["F28"], source_f),
        entry("discount", "Ставка дисконтирования", ["дисконт", "ставка приведения"], "r",
              "Приведённая стоимость потока года t = CFt / (1 + r)^t; r вводится долей: 0,15 = 15%.", "доля в год",
              [("discount_rate", "Ставка дисконтирования", "Расчёт → экономика → Покупка")],
              f"Проверочный склад: r = {fq['discount_rate']['value'].replace('.', ',')} ({discount_label}% годовых).",
              "Используется в NPV и дисконтированной окупаемости; диапазон серверной схемы 0–1.", "Финансовая политика или подтверждённое поле пользователя.", "Расчёт → экономика → Покупка", ["F28", "F29"], source_f),
        entry("sensitivity", "Чувствительность", ["анализ чувствительности", "что если", "what-if"], "ΔNPV",
              "ΔNPV = NPV пересчитанного варианта − NPV исходного варианта. Парк и численность могут меняться ступенчато.", "₽",
              [("equipment_price", "Цена оборудования", "Расчёт → конфигурация"), ("discount_rate", "Ставка дисконтирования", "Расчёт → экономика → Покупка")],
              f"Демо склада: уменьшение цены оборудования даёт ΔNPV {display(demo['sensitivity'][0]['npv_project']['delta_value'])} ₽.",
              "Только для разрешённых параметров и полного базового расчёта; каждый вариант пересчитывает сервер.", "C20 чувствительность и исходные зафиксированные входы.", "Отчёт → чувствительность", ["C20"], source_d),
        entry("purchase", "Покупка роботов", ["собственное оборудование", "приобретение"], "PURCHASE",
              "Год 0: −CAPEX. Далее разность затрат базового и роботизированного процесса с OPEX; остаточная стоимость учитывается в конце горизонта.", "₽ по годам",
              [("implementation_cost_total_gross", "Внедрение", "Расчёт → экономика → Покупка"), ("annual_service_per_robot_gross", "Сервис", "Расчёт → экономика → Покупка"), ("warranty_years", "Гарантия", "Расчёт → экономика → Покупка")],
              f"Проверочный склад: вложения {display(fq['purchase_ledger']['capex_gross'])} ₽, NPV {display(f['npv_project']['value'])} ₽.",
              "При подтверждённых капитальных и операционных строках; коммерческую цену нужно проверять у поставщика.", "C15 покупка и C16 финансовое сравнение.", "Отчёт → сценарий «Покупка»", ["F16", "F27", "F28"], source_f),
        entry("raas", "Роботы как услуга", ["RaaS", "раас", "аренда роботов", "сервисная модель"], "RaaS",
              "Годовой платёж = тариф × 12 × (число роботов при оплате за робота, иначе 1) × (коэффициент загрузки при поэтапном запуске, иначе 1). TCO RaaS = инфраструктурный CAPEX заказчика + Σ(платёж + OPEX заказчика).",
              "₽/год и ₽ за горизонт",
              [("raas_monthly_per_robot_gross", "Месячный тариф за робота", "Расчёт → экономика → RaaS"), ("raas_contract_months", "Срок договора", "Расчёт → экономика → RaaS"), ("raas_infrastructure_owner", "Владелец инфраструктуры", "Расчёт → экономика → RaaS")],
              f"Проверочный склад: платёж года 1 {display(r['annual_ledgers'][0]['raas_payment'])} ₽; TCO RaaS {display(r['tco_raas']['value'])} ₽.",
              "Нужен подтверждённый охват услуг и срок договора на весь горизонт; часть инфраструктуры может оставаться за заказчиком.", "C17 RaaS, тариф и договор; C16 база сравнения.", "Отчёт → сценарий «RaaS»", ["F32"], source_r),
    ]
    binding_paths = ["backend/calculation/capacity/quantities.py", "backend/calculation/capacity/transport.py",
                     "backend/calculation/labour.py",
                     "backend/calculation/economics/metrics.py",
                     "backend/calculation/economics/purchase.py", "backend/calculation/economics/cashflow.py",
                     "backend/calculation/economics/raas.py", "backend/calculation/economics/sensitivity.py",
                     "data/calculation/registry-v1.json"]
    return {
        "schema_version": "economics-glossary-v1",
        "versions": {"capacity": CAPACITY_ENGINE_VERSION, "capacity_result": demo["capacity"]["schema_version"],
                     "finance": financial.engine_version,
                     "purchase": fq["purchase_ledger"]["engine_version"], "raas": raas.engine_version,
                     "registry": financial.registry_version, "orchestrator": execution.result_snapshot["versions"]["orchestrator"]},
        "source_bindings": {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in binding_paths},
        "examples": {"warehouse_economics_result_digest": demo["result_digest"],
                     "financial_trace_digest": financial.replay.trace_content_digest,
                     "raas_trace_digest": raas.replay.trace_content_digest},
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = (json.dumps(build(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if args.check:
        return 0 if TARGET.is_file() and TARGET.read_bytes() == content else 1
    TARGET.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
