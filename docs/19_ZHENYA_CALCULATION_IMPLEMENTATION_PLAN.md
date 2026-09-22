# Внедрение расчётной логики Жени: модель, расхождения и план

Версия плана 1.2, 2026-09-22. Статус: **готов к автономной реализации;
все K01–K29 и Q01–Q12 разрешены, ожидание внешних решений отсутствует**.
Исполнитель: агент. Основание — последующее поручение пользователя самостоятельно
принять решения по ТЗ. Исторический аудит 1.0 сохранён в коммите d2c6a4c.
Обязательная спецификация спорных мест: [принятые решения](planning/calculation-policy-decisions-v1.md).
Проверяемый baseline: `main`, `f77c32c2fde86cd1450aa96d43dc6273059c57d4`.
Рабочее дерево в начале аудита было чистым. Применимых `AGENTS.md` в дереве
проекта и его родительских каталогах не найдено.

Статус исполнения 2026-09-22: **C01–C02 COMPLETE**. Контракты C01 описаны в
[calculation semantics contract v1](planning/calculation-semantics-contract-v1.md),
реестр C02 — в [calculation parameter registry v1](planning/calculation-parameter-registry-v1.md).
Следующий этап — C03; формулы и runtime activation не выполнялись.

Поставка Жени `Референсы/reference v2` от 2026-09-22 прочитана и сохранена как
[deferred delta-register](planning/zhenya-reference-v2-delta.md). Она существенно
детализирует труд, CAPEX/OPEX, intake и reconciliation, но не supersede policy
v1: K01–K29 остаются основой, C03 не блокируется. Спорные уточнения возвращаются
на versioned review gates перед C14–C19; registry v1 и старые runs неизменны.

## 1. Решение о следующем этапе и границы

Этапы **`contracts/calculation-semantics-v1`** (C01) и
**`data/calculation-parameter-registry-v1`** (C02) завершены.
Непосредственный следующий этап — **`intake/process-role-normalization-v2`**
(C03), а не реализация `engine/capacity-formula-trace`.
Нынешний capacity contract не определяет однозначно суммарный exchange,
скорость, единицу потока, границы допущений и исполнимость формулы.
`CalculationResponse` требует экономику и `ScenarioSpec v1`; эти требования
не удовлетворяются доказанными capacity facts. Сначала нужен совместимый
контракт независимого capacity-результата и реестр решений.

`engine/capacity-formula-trace` остаётся первым этапом реализации
транспортных формул (C07), после C01–C03 и C05–C06. C04 — отдельный UI PR и
может идти параллельно backend-этапам после C03. Ни C01, ни этот документ не
активируют runtime, не меняют каталог и не разрешают добавлять вымышленные ТТХ.

Приоритет: ТЗ и дополнения организаторов → принятые решения версии1.1 →
непротиворечивая расчётная логика reference → текущий код и прежние планы.
Документальные evidence/provenance, tenant isolation и строгие contracts
сохраняются. Все алгоритмические решения принимает исполнитель по
[policy v1](planning/calculation-policy-decisions-v1.md), без ожидания Жени.
DTO и schema C01 реализованы аддитивно; остальные модули ниже остаются
запланированными. Production поведение и runtime slots не меняются.

Полнота исполнения: все этапы C01–C29 и все acceptance gates этого плана
обязательны. Они не переводятся в optional и не сокращаются из-за объёма или
сложности. Контроль scope означает только запрет бесконтрольно добавлять новую
логику сверх плана: уточнения `reference v2` сначала проходят назначенный
versioned review gate, после чего явно включаются в policy/registry и этапы.

Полностью прочитаны оба PDF официальной папки ТЗ, 20 страниц;
[source coverage ТЗ](planning/official-requirements-coverage.json) фиксирует hashes.
ТЗ§2/§5.5 требует полный путь для одного объекта и базовый доступ для трёх.
Выбран warehouse full flow; глубина28процессов определена policy§3.
Дополнения§7 разрешают команде определить ограничения, статьи затрат и RaaS.
Недостаток пользовательских данных остаётся нормальным runtime outcome,
не организационным blocker разработки. Каталог и его safe facts не подменяются.

## 2. Source coverage и исходное состояние

Полный рекурсивный список содержит **14 файлов**, все прочитаны целиком,
включая историю решений, миграцию и противоречивые разделы. Каждый заявляет
версию 3.2 от 2026-09-18. `registry.yaml` и заполненного `process_catalog`
в поставке нет. Инвентаризация назначения, входов/выходов, формул,
ограничений, вопросов и связей каждого файла находится в
[полном inventory](planning/zhenya-source-inventory.md).
[Coverage manifest](planning/zhenya-source-coverage.json) фиксирует точные
пути, размеры, строки и SHA-256; это плановый artifact, не runtime-данные.

| ID | Файл в reference | Область и роль в каноне | Coverage |
|---|---|---|---|
| R00 | `00_METHODOLOGY.md` | Методология, приоритеты, provenance, воспроизводимость | Полностью |
| R01 | `01_SOURCES.md` | Реестр заявленных источников; требования research | Полностью |
| R02 | `02_CONSTANTS.md` | Значения и единицы, сценарные defaults, веса | Полностью |
| R03 | `03_FORMULAS.md` | Основной каталог формул, checks и ranking | Полностью |
| R04 | `04_DECISIONS.md` | Явные замены и уточнения; история не удалена | Полностью |
| R05 | `05_DATASET_AUDIT.md` | Интерпретация официальных warehouse/airport/clinic данных | Полностью |
| R06 | `06_EXPERT.md` | Экспертные обоснования и допущения | Полностью |
| R07 | `07_MIGRATION.md` | Миграционные требования и списки изменений | Полностью |
| R08 | `08_FLEET_SCHEMA.md` | Поля оборудования, применимость и полнота evidence | Полностью |
| R09 | `09_OPEN_QUESTIONS.md` | Собственные незакрытые вопросы поставки | Полностью |
| R10 | `10_INTAKE_FORMS.md` | Объекты, процессы, роли и пользовательские поля | Полностью |
| R11 | `11_INTAKE_LOGIC.md` | Активация блоков, validation, агрегирование, RaaS | Полностью |
| R12 | `12_SIMULATION.md` | Обязательная 2D, одинаковые параметры, KPI и отклонение | Полностью |
| R13 | `13_RECONCILIATION.md` | Полные потоки база/сценарий/разница, 49 правил сверки | Полностью |

Внутри reference главные источники: R00 задаёт метод, R02/R03 — числа и формулы, R10/R11 —
пользовательскую семантику, R08 — потребность в equipment facts, R13 —
финансовую сверку. R04/R06/R07 объясняют изменения, но не устраняют молча
расхождения. R01/R05/R09/R12 также обязательны, а не вспомогательные исключения.

Проверены README, PROJECT_CONTEXT, docs/11, docs/12, docs/18, связанные
расчётные части docs/02, 05, 06, 09, 13–17, backend, frontend, RobCraft,
контракты, fixtures и versioned organizer bundle. Документы о реализации
сверялись с кодом, а не принимались за описание работающего endpoint.

| Проверенная величина baseline | Значение / ограничение |
|---|---|
| Discovery | 187 model identities / 223 отдельные catalog positions |
| Capacity pool v2 | 21 модель / 24 позиции; только БРС |
| Ready / with assumptions | 6 / 6 и 15 / 18 соответственно |
| Профили в текущем пуле | 15 транспортных моделей, 6 уборочных; delivery и fixed-cell отсутствуют |
| Deployment-ready | 0; capacity readiness не разрешает deployment claims |
| Accepted enrichment | 131 facts, 129 matching-safe, 154 evidence records, 26 моделей |
| Legacy fleet | Удалён; fallback-каталог восстанавливать нельзя |
| Production calculation path | `CatalogRuntime.load_runtime()` → legacy `runtime_robots()` → `Robot` → `economics.py` |
| Materialized capacity path | `CapacityRuntimeDTO` есть, независимого end-to-end capacity endpoint нет |
| Runtime slot | В этой сессии не читается/не переключается через БД; отсутствие безопасного runtime даёт 503 по существующему контракту |

21/24 — проверяемый **baseline**, не вечный лимит. Новая формула не добавляет
модель в пул автоматически. Изменение membership/counts требует отдельного
versioned audit: identities/positions before/after, facts и evidence,
assumptions, profile eligibility, тесты, согласование владельца и release step.
Discovery 187/223 сохраняется полностью; новые поставки каталога — отдельная
миграция. Упоминания дронов в reference не задают BAS capacity model и не
разрешают включать БАС в этот пул.

## 3. Canonical calculation model

Формулы F01–F35 ниже учитывают решения версии1.1. Точные алгоритмы
спорных веток, включая unit/default policy, находятся в policy v1.
Ссылки K/Q обозначают принятые решения, а не задачи согласования.

### 3.1. Порядок выполнения и границы ответственности

1. Зафиксировать raw intake, источник, object/process/role identities и версии.
2. Нормализовать units и смысл: день/смена, gross monthly, нетто/НДС,
   односторонняя дистанция, масса одной единицы, суммарный exchange.
3. Проверить диапазоны, полноту конкретной формулы и разрешённые assumptions.
4. Выбрать профиль процесса/оборудования; оценить readiness и применимость.
   Hard FAIL исключает кандидата, критический UNKNOWN не становится PASS.
5. Посчитать capacity, требуемый парк, capacity выбранного парка, coverage,
   utilization; сохранить trace. Ручной парк не заменяет demand.
6. Независимо оценить scheduling/SLA по policy§4; без SLA input результат
   N_A, при неполной ресурсной модели CONDITIONAL. Coverage=1 не означает SLA PASS.
7. Рассчитать ручной baseline и модель труда по ролям и общим пулам персонала.
8. Применить коммерческий контракт: цены, НДС, purchase/RaaS, обязанности сторон.
9. Рассчитать годовые статьи CAPEX/OPEX, полные baseline/scenario CF и их разницу.
10. Сверить ledger по R13; получить NPV, TCO, payback, ROI и sensitivity.
11. После NPV выполнить ranking в фиксированной когорте допустимых кандидатов.
12. Сохранить immutable AnalysisRun; сформировать ScenarioSpec новой версии,
    2D/RobCraft отчёт, сравнение KPI и экспорт из того же snapshot.

Это DAG зависимостей, а не требование дождаться экономики для показа capacity.
Capacity, labour, economics, procurement и simulation имеют независимую
полноту. Сквозной итог не скрывает отсутствующий слой.

### 3.2. Входы, units и provenance

| Класс | Канонический смысл и единицы | Разрешённое происхождение / отсутствие |
|---|---|---|
| Объект | warehouse/airport/clinic, регион, площадь m², этажи, зоны, режим | USER/FILE/PRESET; preset не выдаётся за user-confirmed |
| Процесс | стабильный process code, quantity kind, единиц/day, частота/day | R10/R11 mapping + пользователь; нельзя portions, kg, samples назвать deliveries |
| Режим | shifts/day, h/shift, days/year, H=h/day | Пользователь или явно предложенный registry default; H≤24 |
| Маршрут | L=m в одну сторону, load/unload или total exchange=s | USER/FILE; допущение только с явной областью и подтверждённой семантикой |
| Груз | kg/item, габариты, тип тары, items/trip | USER + доказанные payload/geometry; batch conversion отдельно |
| Среда | aisle=m, floor/grade, temperature=°C, noise=dBA и zone/time, lifts/protocols | USER/FILE и подтверждённые допустимые параметры оборудования |
| Оборудование | speed=m/s, payload=kg, cleaning=m²/h, picks/min, W, kWh, autonomy=h | Только matching-safe fact с model/position, evidence, original unit и scope |
| Персонал | role code, persons, monthly gross RUB/person/month | Custom: USER/FILE, без salary fallback; demo: явный ASSUMPTION из dataset по K05/§6 |
| Трудовые политики | полезное время, ротация, direct/full multipliers, replacement limit | Versioned ASSUMPTION/POLICY из R02/R06, не vendor fact |
| Экономика | RUB с НДС для CASH_GROSS_RUB, тариф RUB/kWh, стоимость за robot/year или site | USER/quote/source price с currency, tax basis, scope, датой и качеством |
| Сценарий | acquisition PURCHASE/RAAS × uncertainty PESSIMISTIC/BASE/OPTIMISTIC | Независимые оси; не смешивать RaaS со сценарием оптимизма |
| Derived | H, cycle, N, money lines, scores | Ссылки на формулы и все родительские inputs; не переименовывать в исходный fact |

Нормализация сохраняет raw value/unit/source; 3600 s/h, 1000 W/kW,
1000 kg/t, 3.6 km/h на m/s — unit definitions, а не эмпирические коэффициенты.
Разрешённые конверсии типизированы. kg/day → trips/day требует груз/рейс;
RUB gross → direct cost требует отдельной формулы. НДС неизвестной ставки
не удаляется делением на предполагаемый коэффициент.

Границы fallback: отсутствующий обязательный vendor fact → локальный missing-fact
результат для SKU/profile; эксплуатационный выбор → scenario input;
экспертное значение R02/R06 → versioned assumption с override. Для неописанной
физической операции действует принятый scope K19, для новой технической
неоднозначности — порядок самостоятельного решения из policy §7.
Исследование улучшает данные впоследствии и не является gate разработки.
Строка оборудования выше описывает факты каталога; сценарные power/autonomy,
operating speed и бюджеты хранятся отдельно и не заменяют обязательные safe facts.
Нулевое подтверждённое значение, unknown и not applicable — разные состояния.
Optional cost, отключённый пользователем, равен 0 с причиной, а не с потерей provenance.

### 3.3. Реестр основных формул

Идентификаторы Fxx ниже — traceability этого плана. Формальные runtime IDs и
версии утверждаются C01/C02. Спорные части помечены Kxx в разделе 5;
их реализация однозначно задана принятой policy v1.

| ID / источник | Целевая формула и результат | Применимость / недостающее |
|---|---|---|
| F01 R03 §1.1 | `H = shifts × shift_hours`, h/day; `q_avg = daily_units / H`, units/h | H>0 и ≤24, не clamp |
| F02 R03 §1.1 | `cycle_s = 2×L_m/v_m_s + load_s + unload_s`; при total exchange `2L/v + exchange_total_s` | Транспорт/доставка; выбор скорости K02; total exchange учитывается один раз |
| F03 R02 §5, R03 §1.1; K03 | `trips_h=3600/cycle_s`; `q_nominal=trips_h×units_per_trip`; boxes batch=min(floor(payload/item_mass), применимые user/passport/geometry limits) | Остальные batch1 либо явно заданный physical batch; unknown geometry раскрывается, масса не превышается |
| F04 R02 §3, R03 §1.1 | `peak=1.25×(1+reserve_peak)`; `q_required=q_avg×peak`; `q_effective=q_nominal×availability`; `N=ceil(q_required/q_effective)` | Пик и availability независимы; дополнительного деления на target utilization 0.90 нет |
| F05 R03 §1.2 | `daily_area=area×frequency`; `daily_robot=cleaning_rate×H×availability`; `N=ceil(daily_area/daily_robot)` | m²/day; транспортный peak здесь не указан |
| F06 R03 §1.3 | `boxes_day=picks_min×60×H×cell_eff`; `pallets_day=boxes_day/boxes_per_pallet`; `N=ceil(demand_pallets_day/(pallets_day×availability))` | Cell_eff=.65 assumption; 20 output boxes/pallet против 33 receiving, не смешивать |
| F07 R03 §1.4 | `fleet_capacity=N_manual×q_effective`; `utilization=min(required/fleet_capacity,1)`; `coverage=min(fleet_capacity/required,1)` | Одинаковые units/window; recommended и selected N отдельно; zero/overload K04 |
| F08 R03 §2.1 | `human_cycle=2L/human_speed + human_exchange_total`; `manual_per_shift=3600/human_cycle×shift_hours×useful_time` | Единица перемещения явно задана; cleaning отдельно: `300×shift_hours×.85` m²/shift |
| F09 R03 §2.2–2.4 | `person_shifts=max(shifts,ceil(daily_units/manual_per_shift))`; `rotation=max(1,(7×days/365)/(40/shift_hours)×1.090)×(1+loss)`; `required_people=ceil(person_shifts×rotation)` | Не умножать shifts повторно; warehouse/airport/clinic loss=.25/.35/.45 |
| F10 R03 §2.6 | `gross_annual=monthly_gross×12`; `direct=gross_annual×1.302`; `full=gross_annual×1.55`; `fixed_overhead=gross_annual×.248` | Это допущения модели, не доказанные ставки для любого работодателя; зарплата обязательна для labour/finance, demo exception K05 |
| F11 R03 §2.6 | `replacement=min(required_people,role_pool)`; `deficit=max(0,required_people-role_pool)`; `robot_people=floor(required_people×coverage)`; `robot_replacement=min(robot_people,replacement)`; `growth=min(robot_people-robot_replacement,deficit)` | Рост/покрытие дефицита не равно увольнению; общий role pool не расходуется дважды |
| F12 R03 §2.6 | `applied=floor(robot_replacement×replacement_limit)`; `pult_share=floor(applied×supervision)`; `pult_min=shifts×min_pult_per_shift`; `pult_remain=max(pult_share,pult_min)`; `released=max(0,applied-pult_remain)`; `saving=released×direct` | replacement_limit default 1; min_pult 1; conservation и годовой staffing заданы K06/policy §5 |
| F13 R03 §2.6/3.2; K06 | `transferred=min(applied,pult_remain)`; `additional=pult_remain-transferred`; `released=applied-transferred`; technicians=`ceil(N×ramp_t/20)` | Исправленная conservation модель; дополнительные operators поcontrol salary; missing salary → INCOMPLETE |
| F14 R03 §2.7; K08 | `base_equipment=input_count`, иначе `ceil(drivers/shifts)`; `withdraw=min(base,ceil(released_driver/shifts))`; fallback `min(base,ceil(released×.30/shifts))` | Не более исходного парка; неизвестная база не даёт автоматической экономии |
| F15 R03 §2.8/3.5 | Baseline по реально указанным ролям; `deficit_cost=deficit×unit_deficit_cost` | Default unit_deficit_cost=direct по R02/R04/R13; user 0 отключает; противоречия K07 |
| F16 R03 §3.1 | `robots=N×price×hw`; `chargers=ceil(N×charger_ratio)×charger_price×hw`; `integration=N×per_robot×hw`; `infrastructure=(site_fixed+zone_fixed)×hw` | Purchase; commercial facts/explicit scenario inputs, без вымышленных цен |
| F17 R03 §3.1; K25 | Optional: `N×price×commission_fraction`, `N×price×training_fraction`, user amounts delivery/Wi-Fi/ERP/fleet licence/electric/floor/spares; `reserve=sum(all_capital_lines)×reserve_capex`; `CAPEX=base+reserve` | Optional статьи не получают hw автоматически; FIXED_TOTAL/PER_ROBOT/PERCENT_BASE взаимно исключаются для одной статьи; общие статьи один раз |
| F18 R03 §3.1–3.2 | `equipment_CAPEX=robots+chargers+batteries_in_CAPEX`; insurance/consumables/repair=`equipment_CAPEX×.01/.02/.01` | Без инфраструктуры/резерва; не умножать repair ещё раз на N |
| F19 R03 §3.2; K09 | Service=0 при `t≤warranty`, иначе `N×annual_service×service_mult×ramp_t×1.05^(t−1)`; software=N×annual_software; comm=N×monthly_comm×12 | Каждая строка получает ramp один раз; warranty неизвестна → нужный scenario input |
| F20 R03 §3.2 | `energy_kWh=N×(power_W/1000)×H×availability×days/efficiency`; `energy_RUB=energy_kWh×tariff` | Если battery_kWh и autonomy_h заданы, заменить power path на `N×H×availability/autonomy×battery_kWh×days/efficiency`; выбрать один путь, затем tariff |
| F21 R03 §3.3; K10 | `annual_cycles=H×days×availability/autonomy_h`; накопленный wear=Σannual_cycles×ramp; replacement events при пересечении k×resource; cost=events×N×battery_price×hw×1.05^(t−1) | Повторные события; exact terminal crossing без будущей работы не покупает батарею; ramp второй раз не применяется |
| F22 R03 §3.4 | `residual=N×price×hw×max(0,1-horizon/life)×liquidity` | AMR/fork lift/shuttle 10yr/.6; cell/manipulator 8yr/.4; mapping остальных K11; только terminal CF |
| F23 R03 §3.5 | `released_t=ceil(released×ramp_t)`; `headcount_scenario_t=base_headcount-released_t`; direct/overhead ×1.08^(t−1); equipment `(base_count-withdraw×ramp_t)×cost×1.05^(t−1)` | По каждой роли; overhead остаётся на base headcount; saving×ramp против ceil K09 |
| F24 R03 §3.5.2; K09 | `severance_t=max(0,released_t-released_(t−1))×monthly_gross×2.5`; released_0=0 | Во все годы нового высвобождения; явно принятая корректировка правила толькоyear1 |
| F25 R03 §3.5.1–3.5.3 | `EBITDA_base=−(direct_labour+fixed_overhead+equipment+deficit_cost)`; `EBITDA_scenario=−(remaining_labour+same_overhead+remaining_equipment+remaining_deficit+OPEX_excluding_RaaS_payment+RaaS_payment)` | Full ledger; в отображаемом total OPEX платёж уже включён; savings отдельно не прибавлять к CF повторно |
| F26 R03 §3.5; K12 | `depreciation=CAPEX_without_reserve/5` первые5лет; EBIT=EBITDA−depreciation. Primary tax=0 в pretax CF; optional illustrative tax modes25% поpolicy§5 | Model tax supplement не юридический/бухгалтерский расчёт и не dependency основного результата |
| F27 R03 §3.5; K12 | Primary `CF=EBITDA−battery+terminal_residual−severance`; supplement вычитает model tax; `CF_scenario_0=−CAPEX` | Separate primary/supplement ledgers; не смешивать денежные базы |
| F28 R03 §3.5.3/3.6 | `NPV_base=Σ CF_base_t/(1+r)^t`; `NPV_scenario=−CAPEX+Σ CF_scenario_t/(1+r)^t`; `NPV_project=NPV_scenario−NPV_base` | Отрицательные два NPV не означают отрицательный эффект; example −80−(−100)=+20 млн |
| F29 R03 §3.6; K13 | Simple/discounted payback — первое пересечение cumulative differential CF с 0, с интерполяцией внутри года | При постоянном эффекте совпадает с `CAPEX/annual_effect`; no crossing → null+NOT_REACHED, не 99; CAPEX0 K13 |
| F30 R03 §3.6 | `TCO_purchase=CAPEX+ΣOPEX+Σbattery`; `TCO_RaaS=infra_CAPEX+ΣOPEX_excluding_RaaS_payment+ΣRaaS_payment`; `effect=Σ(CF_scenario_t−CF_base_t)` за t1..h | TCO без остатка/базового ФОТ; RaaS payment один раз; effect по тексту без t0, отличать от NPV |
| F31 R03 §3.6; K13 | `ROI_purchase=effect/CAPEX×100`; `ROI_RaaS=effect/TCO×100`; net benefit after investment=effect−CAPEX | Zero denominator N_A; дополнительный profitability_TCO исключён как неоднозначный необязательный показатель |
| F32 R02 §3.3, R11 схема 10 | RaaS zeroing по таблице ниже; `payment=N×price×.02×12×ramp_t` для phased, без ramp для all_fleet | Не индексируется, hw multiplier не указан; контракт и ставка — assumption/input |
| F33 R03 §4, R08 §9 | Applicability, data completeness, economy normalization и итоговый score ниже | Только после hard gates и NPV; K14–K16 |
| F34 R03 §6 | `width=sqrt(area×aspect)`; `height=width/aspect`; aspect warehouse .60, airport .35, clinic .75; коридоры 2/3/4/5 по площади | Только synthetic visualization geometry, не фактическая планировка или новая длина расчётного маршрута; K18 |
| F35 R03 §7, R02 §9; K16 | Intake completeness поscope: labour безsalary0; capacity поrequiredinputs; data score77maximumweights доN_A; basic<40, working40≤x<70, high≥70 | Readiness/полнота ввода/полнотакарточки — разные показатели |

### 3.4. Значения сценариев и правила данных

| Параметр (R02/R06) | Pessimistic | Base | Optimistic |
|---|---|---|---|
| Availability | .55 | .70 | .80 |
| Peak reserve; итоговый peak | .25; 1.5625 | .20; 1.5 | .15; 1.4375 |
| Hardware multiplier | 1.15 | 1.00 | .95 |
| Service multiplier | 1.20 | 1.00 | .90 |
| CAPEX reserve | .15 | .10 | .05 |
| Supervision share | .35 | .25 | .15 |
| Ramp по годам 1–5 | .40/.70/.90/1/1 | .50/.85/1/1/1 | .70/.95/1/1/1 |

Horizon 5–15 лет; после пятого года ramp=1 по принятому K09.
Discount default .15, labour index .08, energy index .07,
other expenses .05, model tax .25,
energy tariff 8 RUB/kWh, efficiency .85, comm 500 RUB/robot/month,
tech service norm 20 robots/person, severance 2.5 monthly gross.
Эти числа не vendor facts; registry сохраняет source, статус и пользовательское
переопределение. Правовые величины нельзя объявлять универсально обязательными
на основании R01 без research и applicable policy.

Годовая энергия из F20 умножается на `ramp_t×1.07^(t−1)`;
прочие software/insurance/comm/consumables/repair — на
`ramp_t×1.05^(t−1)`. Service, technicians и control operators используют
свои отдельные годовые строки; повторное умножение общего OPEX на ramp
запрещено. CAPEX и depreciation не масштабируются ramp. Дефицит индексируется
как труд на 8%; его remaining quantity и ramp согласуются в K07/K09.

Human speed для pallets/boxes/carts/cases/delivery: 1/1.2/.8/1/1 m/s;
exchange_total: 90/30/120/60/60 s. Useful time для 6–8h=.80,
9–10h=.75, 11h=.72, 12h=.68. Для cleaning используются 300 m²/h и .85,
без дополнительного useful-time множителя. Неописанные дробные смены и
пограничные интервалы требуют validation policy C01, не интерполяции наугад.

R05 задаёт реальные контексты, но не полностью готовые финансовые fixtures:
warehouse 20 000 m², active 10 000, 2×11h, 2 000 паллет/day inbound+outbound;
25m относятся к picking, не автоматически к паллетному маршруту.
Airport cleaning 51 000m² из 85 000×.6 — derived assumption, не иной source fact.
Clinic: 1 950 portions, 1 200 samples, linen 1 800+1 800kg/day,
120kg food cart и 55kg linen container. Порции/пробы/килограммы нельзя
преобразовать в число доставок без batch/packaging input; food SLA20 min и
biomaterial SLA30 min не проверяются только среднесуточной capacity.

### 3.5. Purchase/RaaS, общий труд и инфраструктура

| Статья | Purchase | RaaS target из R02/R03/R11 |
|---|---|---|
| Robots, chargers, integration/robot, commissioning, training, spares, fleet licence | По отдельным подтверждённым ценам/inputs | 0, ответственность vendor по выбранной модельной политике |
| Site/zone infrastructure, Wi-Fi, ERP, electric, floor | CAPEX, общий объект один раз | Остаются, reserve на оставшиеся статьи |
| Service, software, insurance, consumables, repair, tech | OPEX и warranty policy | 0 |
| Energy, communication, extra control operators | OPEX | Остаются в OPEX_RaaS |
| RaaS payment | 0 | Отдельная operating line; один раз в EBITDA, tax base и TCO |
| Battery replacement, residual | По формулам | 0 |
| Depreciation | CAPEX без reserve, 5 лет | Только оставшиеся capital assets без reserve |

Коммерческий договор может расходиться с модельной политикой RaaS. Тогда
нужен явный contract override с trace и новым расчётом, не ложное утверждение,
что vendor предоставляет сервис бесплатно. Procurement оценивается отдельно:
применимость, availability in Russia, freshness/quote, service и evidence.
Нет подтверждения закупки — нет procurement-ready, даже при численном NPV.

Общая инфраструктура распределяется один раз по прямому CAPEX без
shared/reserve; при нулевой сумме — поровну. Role pools распределяются по
явным shares либо person-shifts методом largest-remainder. Anchor cohort
фиксируется до экономического ranking; окончательный combined ledger
пересчитывается после выбора. Алгоритм принят в K17/policy§5.

### 3.6. Применимость, ranking и ограничения

R03 §5 задаёт восемь базовых checks: process/category, cargo, object,
payload, aisle, ceiling≥lift+1m, floors/lift, clinic sterilization.
Расширение: noise по зоне/времени, temperature, airside certificate,
apron permission, class-B waste handling, material disinfection, restricted
zone, access/lift protocols, WMS/1C/EMIAS/LIS, floor flatness/type, grade,
outdoor, passport availability, asset life, budget, charging power.
Life<horizon, budget<CAPEX и insufficient charging power — warnings без
score penalty. Остальные применимые failures исключают кандидата.
Scoped requirements определены K15; неизвестные нормы/возможности не
объявляются установленными, UNKNOWN сохраняется без ожидания research.
Объединённая sterilization означает, что заявленное «29» нельзя использовать
как количество уникальных check IDs. Неприменимые checks помечаются N/A,
не фиктивным PASS с выдуманным evidence.

`Applicability=100×(.30×availability_norm+.25×integration_fraction+
.20×aisle_margin_norm+.15×TRL_norm+.10×payload_margin_norm)`.
Это паспортная availability для score, не автоматически operational .55/.70/.80.
Узлы availability: 40%=0,55%=.5,70%=.8,85%=1,92%=.9,100%=.5; <40% hard fail.
Aisle margin — **абсолютная разность в метрах** `aisle−min_aisle`:
0→0,.15m→.3,.40m→.7,≥.60m→1.
TRL1–6→0,7→.3,8→.7,9→1.
Payload margin `(payload-weight)/payload`: <0 fail,0→0,.15→.5,.5→1,
выше .5 линейно снижается до.5 при margin1 по K14.
Integration fraction — доля поддержанных требуемых интеграций; если
требуемых нет, **1.0** (R03 §4). Между узлами используется линейная интерполяция;
N/A-компоненты исключаются с перенормировкой весов, UNKNOWN=0 (K14).

`Data=100×Σ(weight×status)/Σ(applicable weights)`; status=1 verified,
.5 filled-unverified,0 missing. Такой completeness не разрешает использовать
unverified поле в matching. Приняты77весов по перечню R08 (K16); историческое75 не используется.
`Economy=100×(NPV−min)/(max−min)` в одной process cohort, при равенстве 50.
Все NPV<0 могут дать лидеру 100; это **ранг**, не положительное ТЭО.
`Score=clamp(.50×Applicability+.35×Economy+.15×Data+penalty,0,100)`;
остаётся penalty−5 для указанного AMR-потока >5 000, не старые штрафы.
Нет NPV → нет полного Score, возможен отдельно названный technical ordering.

### 3.7. Статусы, precision и исполнимость

| Измерение | Принятый целевой контракт | Запрет |
|---|---|---|
| Catalog eligibility | Сохранить READY/WITH_ASSUMPTIONS и blockers v2, добавить отдельный formula-executability report | Не менять статус всех 21 строк по факту наличия Python функции |
| Formula execution | COMPLETE / WITH_ASSUMPTIONS / BLOCKED / NOT_APPLICABLE | BLOCKED не содержит подставленного 0 |
| Technical | PASS / FAIL / UNKNOWN / ASSUMED + scope; общий ELIGIBLE/NEEDS_VALIDATION/REJECTED | Assumed не даёт deployment-ready |
| Financial | COMPLETE / INCOMPLETE / NOT_APPLICABLE; benefit отдельно POSITIVE/NON_POSITIVE | Отсутствующая зарплата не становится «окупается» |
| Payback | REACHED + years / NOT_REACHED / NOT_APPLICABLE / BLOCKED | Не 99 и не Infinity в JSON |
| Procurement | Существующие evidence gates + missing quote/terms | Calculation readiness не есть procurement readiness |
| Scheduling/SLA | NOT_EVALUATED / evaluated verdict с методикой | Coverage 1 не означает SLA pass |
| Simulation | Версионированный report и diagnostic verdict | Не certification/deployment, не изменение сохранённой экономики |

Причины BLOCKED типизированы: MISSING_INPUT, UNIT_MISMATCH,
UNSUPPORTED_PROCESS_PROFILE, MISSING_SAFE_FACT, CONFLICTING_FACT,
UNAPPROVED_ASSUMPTION, INVALID_DOMAIN, UNKNOWN_POLICY_VERSION,
MISSING_COMMERCIAL_TERMS, MISSING_ROLE_SALARY, UNKNOWN_TAX_BASIS.
Отсутствие economics не блокирует независимый COMPLETE capacity.

Принята precision policy§5: Decimal context28, без промежуточного display
rounding; money output2digits HALF_EVEN, score/percent/payback2digits.
Каждый ceil/floor имеет trace node; canonical digest использует полную
precision. Event time integerµs, threshold tolerance score1e-6; epsilon
для ceil запрещён. Раннее округление10 000RUB сохраняется только при replay
legacy runs. Это собственное решение K27/Q02, не приписанное reference.

R11 схема 5 требует **volume>0, weight≥0, distance>0** для активного блока,
replacement limit в[0,1], shifts×hours≤24; R10 предлагает shifts 1/2/3,
hours 6/8/10/11/12. Нулевая масса допустима как field value, но не знаменатель
box batch. Нулевые speed/cycle/batch недопустимы для исполнения. Пустой
неактивный блок отличается от активного с invalid demand 0.
Принято K04: при отключении процесса показывать N0 и NOT_APPLICABLE
utilization, не запускать формулы. Fleet 0 при demand>0 даёт coverage 0 и
overload без деления на 0. Это решение K04 не отменяет validation
положительного спроса для активного блока.

R08 §3.5 задаёт приоритет: если raw карточка содержит load+unload и total,
используются отдельные load/unload; total остаётся справочным и discrepancy
показывается. Нормализованный discriminated union содержит ровно один путь.
Одна заполненная половина split без total не разрешает придумать вторую.

Дополнительные defaults R02/R10: aisle 2.5m, warehouse ceiling 10m, floors 1,
frequency 1/day,days 365; object schedules 2×11/3×8/3×8 и horizon 5/7/7;
available power 500/300/80kW, other 100kW; otherarea 6000m², active area=.5 total.
Они имеют field priority и provenance; не подменяют фактическую ширину/мощность
объекта. Указанные там fallback 10 picks/min,800m²/h, warranty 2 years и
class-based MTBF нельзя публиковать как безопасные vendor facts (K29).
Шум/температура/пол по объекту из R10 — versioned requirement/assumption с
zone/time/applicability, а не автоматическая верификация норм.
Input completeness weights R02 §9: headcount 20, salary 19, demand 14,
distance 10, aisle 10, shifts 8, area 5, weight 5, discount 5, hours 4; sum 100.
Поведение блока без salary принято в K16: capacity отдельно, labour completeness0.

## 4. As-is / target gap matrix

Обозначения типа: **CONFLICT** прямое противоречие; **PARTIAL** частичное
покрытие; **MISSING** отсутствует; **LEGACY** изолировать/мигрировать;
**CONTRACT** несовместимость; **ASSUMPTION** скрытое допущение.
P0 — может изменить рекомендацию/доказательность; P1 — неполный flow/проверка.
Миграции: A API, D versioned data/snapshot, U UI; «—» означает отсутствие
миграции в данном пункте, а не разрешение пропустить regression.

Точные пути реализации, используемые в таблице:

- E: [backend/economics.py](../backend/economics.py), в частности
  `_fleet_sizing`, `_labor_model`, `_calc_scenario`, `check_constraints`,
  `calc_recommendation`, `calc_zone`, `calc_combined`.
- M: [backend/models.py](../backend/models.py): `UserInput`, `Zone`, `Robot`,
  `ScenarioResult`, `StaffBreakdown`, `CalculationResponse`, `ScenarioSpec`.
- CR: [backend/catalog_repository.py](../backend/catalog_repository.py):
  `CapacityRuntimeDTO`, `_capacity_runtime`, `_project_runtime_robot`,
  `CatalogSnapshotDTO.runtime_robots`, `calculation_ready_models`;
  [backend/catalog_runtime.py](../backend/catalog_runtime.py): `load_runtime`.
- API: [backend/main.py](../backend/main.py): `/api/calculate`,
  `/api/readiness`, catalog positions;
  [backend/persistence_api.py](../backend/persistence_api.py): persisted runs,
  `RULES_VERSION`, create/get/rerun analysis;
  [backend/persistence_models.py](../backend/persistence_models.py):
  `AnalysisRun` и DB invariants.
- I: [backend/object_profiles.py](../backend/object_profiles.py),
  [backend/project_file_intake.py](../backend/project_file_intake.py),
  [backend/auditor.py](../backend/auditor.py).
- RD: [backend/readiness.py](../backend/readiness.py): `ReadinessRequest`,
  `ReadinessReport`, process/technical checks.
- UI: [frontend/src/App.jsx](../frontend/src/App.jsx),
  [ParamsPanel.jsx](../frontend/src/components/ParamsPanel.jsx),
  [ZonalPanel.jsx](../frontend/src/components/ZonalPanel.jsx),
  [dashboardModel.js](../frontend/src/dashboardModel.js).
- SS: [backend/scenario_spec.py](../backend/scenario_spec.py),
  [contracts/scenario-spec-v1.schema.json](../contracts/scenario-spec-v1.schema.json).
- SIM: [backend/simulation.py](../backend/simulation.py),
  [robcraft/src/integration/scenario-spec.js](../robcraft/src/integration/scenario-spec.js),
  [robcraft/src/simulation.js](../robcraft/src/simulation.js).
- BUNDLE: [data/import/organizer-catalog-v4](../data/import/organizer-catalog-v4),
  [runtime-calculation-readiness-contract-v2.json](../contracts/runtime-calculation-readiness-contract-v2.json),
  [catalog-capacity-runtime-v1.schema.json](../contracts/catalog-capacity-runtime-v1.schema.json).

| Gap / источник → target | As-is, точный модуль/участок | Тип; риск | Решение / этап | Миграции | Необходимые тесты | Принятое решение / dependency |
|---|---|---|---|---|---|---|
| G01 R00/R02: единый versioned registry | E constants и функции; отдельного registry нет; constants reference тоже расходятся | MISSING/ASSUMPTION; P0 | Source-bound registry, source/conflict IDs C01–02 | D,A | schema, no orphan constant, immutable replay | K01,Q01 |
| G02 R10/R11: object/process/role модель | M: retail/airport/clinic/other и 4 process enums; generic volume, один staff | CONTRACT; P0 | ProcessSpec/RolePool/quantity kind, compatibility adapter C03 | A,D,U | roundtrip всех 28 blocks, unknown enum, no salary default | K19,Q03 |
| G03 R05: warehouse 2000 total, picking 25m отдельно | I `_LEGACY_PARAMETER_MAP`: outbound 1000→volume, picking distance 25→transport, picker 100→staff | CONFLICT; P0 | Versioned semantic mapping с отдельными inbound/outbound/routes C03 | D,A,U | официальный fixture, source cell, no double flow | Q03,Q04 |
| G04 R05/R10: аэропорт/клиника units | I: clinic portions→generic deliveries; airport internal/ramp/staff смешаны | CONFLICT; P0 | batch/route/role mapping, unresolved conversion blocker C03/C10 | D,A,U | kg/portions/samples/cart sizes, missing batch | Q04 |
| G05 R10: общие+6/10/12 блоков, partial completion | I intake CSV строгий legacy profile; XLSX layout иной, mandatory profile completeness; UI один процесс/зоны | PARTIAL/CONTRACT; P1 | Сохранить v1 import, отдельный block-aware v2 C03–04 | A,D,U | пустой optional block, invalid atomically rejected, provenance | K19 |
| G06 R00/R10: salary USER gross monthly по роли | E `_fte_cost` fallback 80k×12×1.55; I preset salary; auditor money×12×1.55 | CONFLICT/ASSUMPTION; P0 | Убрать salary fallback только в v2, legacy raw сохранить C03/C14 | A,D,U | missing salary→partial, zero explicit, разных 2 роли | K05 |
| G07 R03 F10: gross/direct/full разные | UI salary conversion×15.624 (12×1.302); auditor×18.6; M одно `fte_cost_year` | CONFLICT backend/frontend; P0 | MonthlyGrossMoney; server derivations, UI только presentation C03–04/C14 | A,D,U | одинаковый ручной/LLM/file ввод, no client arithmetic | Q02 |
| G08 R03 F01: H≤24 validation | E `_operating_hours` clamps to 24; RD сообщает invalid; API может считать независимо | CONFLICT readiness/execution; P0 | Общая domain validation, никаких clamp C03/C05 | A,U | 2×12 valid,3×12 rejected, absent H | Q02 |
| G09 R03 F02: total exchange один раз | E `_fleet_sizing`: `2×exchange`; contract v2 default 45 с legacy provenance | CONFLICT/ASSUMPTION; P0 | exchange_total vs load/unload mutually exclusive; migrate 45 только с решением C01/C07 | A,D,U | cycle total vs split, cannot double count | K02 |
| G10 R03/R08: speed semantic | E и BUNDLE используют max_speed; R08 хочет operational speed | CONFLICT; P0 | Operating speed input либо раскрытый паспортный scenario proxy C01/C06–07 | A,D,U | max vs actual, unsafe fact rejected | K02 |
| G11 R03 F03: box batch floor(payload/item) | M manual units_per_trip 1..100; E произвольный override/грузовой fallback | CONFLICT; P0 | Typed derived batch; passport alternative только approved policy C07 | A,D,U | payload<item, exact floor, geometry unknown | K03 |
| G12 R03 F04: peak 1.25×reserve и availability | E `_peak_share`=1/.55/.45/.35, доп. target utilization.90 | CONFLICT/LEGACY; P0 | Transport capacity v2, old formulas только replay C07 | D,A,U | sensitivity, ceil boundary, peak not counted twice | — |
| G13 R03 F05: cleaning own units | E cleaning branch структурно близок, но общий Robot/экономика обязательны | PARTIAL/CONTRACT; P0 | Независимый cleaning profile C08 | A,D,U | m²/day,frequency, no transport peak | Q02 |
| G14 R03 F06: cell picks/min | E cell branch есть; BUNDLE требует generic throughput без доказанного picks/min mapping; current pool 0 cells | PARTIAL; P0 | Typed throughput semantics C09, synthetic fixtures; research before admission | A,D,U | picks≠pallets,20vs 33, missing rate | Q04,Q05 |
| G15 R03 F07: coverage from actual capacity | E `_labor_model`: N/N_required; UI hides selected/recommended distinction in downstream fields | CONFLICT; P0 | actual capacity coverage; clamp только display-util, raw overload C07–09/C12 | A,D,U | Nmanual ниже/равно/выше ceil, zero | K04 |
| G16 R03 F08: human cycle + useful time | E `_manual_rate_per_shift`: fixed 80/150/44/30, cleaning 700×6.8 | CONFLICT/ASSUMPTION; P0 | Role/process-specific manual capacity C14 | D,A,U | human distance monotonic, cleaning factor once | Q06 |
| G17 R03 F09: rotation 1.090×loss | E vacation 1.083, no losses; some scenarios no rotation; shifted crew shortcuts | CONFLICT; P0 | Full labour trace C14 | D,A,U |14×1.908→27, H ranges, losses eachobject | — |
| G18 R03 F11–13: role pool / replacement / pult | E vendor `fte_replace_per_shift`, fractional people, estimated staff, no role mapping | CONFLICT; P0 | Separate required/replace/deficit/released/additional, integer nodes C14 | A,D,U | small headcount, role_pool 0, limit 0, maxno double release | K06,K17 |
| G19 R03 F14: fork lift withdrawal | E takes whole equipment_count as avoided cost; fallback share.40 | CONFLICT; P0 | Active role + explicit equipment baseline C14 | D,A,U | withdrawal≤base, shifts, unknown equipment | K08 |
| G20 R03 F15/R13: baseline and deficit | E `manual_baseline` estimatesstaff, full cost×horizon without index; no full deficit ledger | CONFLICT/MISSING; P0 | Real role baseline, explicit deficit policy C14/C16 | A,D,U | no-role process, deficit 0/positive/off, fixed overhead unchanged | K07 |
| G21 R02/R03: scenario tables | E SCENARIOS different hw/reserve/supervision, single first year ramp.78/.90/.95 | CONFLICT; P0 | versioned scenario axis and annual ramp C02/C15–17 | D,A,U | all 3×2 acquisitions, horizon 5..15 | K09 |
| G22 R03 F16–18: full CAPEX and correct percentage base | E basics only; optional/site/zone expenses incomplete | PARTIAL; P0 | Separate capital ledger and ownership C15 | A,D,U | rounding chargers, reserveall, percent equipment only | K11,K17 |
| G23 R03 net-of-VAT economics | BUNDLE price/ docs 16–17 VAT_INCLUDED organizer assumption; no rate; E uses as purchase scalar | CONFLICT provenance; P0 | CASH_GROSS_RUB primary; optional NET_RUB требует explicit rate C13 | D,A,U | included known rate,unknown rate,not applicable, raw retained | K20,Q07 |
| G24 R03 F19: warranty, software/comm, tech/control | E service/software/energy only; no warranty or role salaries | MISSING; P0 | Itemized OPEX, missing wages incomplete C15 | A,D,U | warranty 0/3/h, no techsalary, 20/21 robots | K05,K09 |
| G25 R03 F20: energy kWh/efficiency | E `_energy_cost_per_robot`: fallback 250W, no charging efficiency | CONFLICT/ASSUMPTION; P0 | Typed mutually exclusive energy paths C15 | D,A,U | W/kW,capacity/autonomy, no charger doublecount | Q05 |
| G26 R03 F21: battery policy | E `_battery_replacement`: one event, no hw/index/ramp | PARTIAL; P0 | Explicit schedule policy before implementation C15 | D,A,U | exact horizon/year, zero cycles, repeated events K10 | K10 |
| G27 R03 F22: depreciating residual | E fixed .40×equipment; incomplete asset-class mapping | CONFLICT; P0 | Class life/liquidity assumptions, terminal once C15–16 | D,A,U | age=life, horizon 5/7/10/15 | K11 |
| G28 R03 F23–28/R13: full CF, tax/depreciation/severance | E `_calc_scenario` incremental saving−OPEX, no tax/full baseline | CONFLICT/MISSING; P0 | Separate finance ledger, reconciled differential CF C16 | A,D,U | NPV−80−(−100), single tax effect, fixed overhead cancel | K09,K12 |
| G29 R03 F29–31: payback/ROI/TCO/effect | E `_payback`99, ROI=(benefit−TCO)/TCO; zonal PB=CAPEX/annual | CONFLICT/CONTRACT; P0 | Versioned metrics, nullable state, distinct meanings C16/C18 | A,D,U | no crossing, CAPEX0, negative annual after positive, interpolation | K13 |
| G30 R02/R11 F32: RaaS orthogonal axis | M/E/API/UI no acquisition contract; scenarios only uncertainty | MISSING; P0 | RaaS ledger after purchase; explicit exclusions C17/C21 | A,D,U | payment once,zeroing,phased/allfleet,no residual | K21 |
| G31 R11 combined project | E `calc_combined`: sum rounded results, fixed=max(model fixed), role input lost | CONFLICT; P0 | Shared infra/roles allocation before combined CF C18 | A,D,U | order invariance, conserve costs, no double FOT | K17 |
| G32 R03 F33: ranking weights and NPV cohort | E score 85+shifts−penalties floor 45; sorts economicstatus/payback/NPV | CONFLICT/LEGACY; P0 | Gates→complete NPV→R03 score, deterministic ties C19 | A,D,U | equalNPV50,all negative,no false best, incomplete finance | K14–K16 |
| G33 R03/R08 technical checks | E `check_constraints`: service delivery omits payload, fixed only payload; RD separate larger checks | PARTIAL/CONFLICT; P0 | Single constraint service, separate architecture ranking C05 | A,D,U | all applicable checkIDs, conflicting readiness/calc impossible | K15 |
| G34 R03 availability/route constraints | E has unreferenced `trip>0.8×autonomy` hard reject; no trace | LEGACY/ASSUMPTION; P0 | Isolate legacy, no silent 0.8 in v2; validated charging policy C05/C23 | D,A,U | legacyreplay, remove unexplained reject only v2 | Q08 |
| G35 R08 evidence completeness vs matching | CR matching-safe facts retained; .5 score filled-unverified would weaken if used asgate | PARTIAL; P0 | Separate data score from safe value view C06/C19 | A,D,U | unsafe values cannot enter formulas regardless score | K16 |
| G36 R00 formula trace | E breakdowns but no expression/version/input DAG/provenance; early rounding 10k | MISSING; P0 | Trace contract and unrounded ledger C01/C07 onward | A,D,U | exact replay, every output node, units, no magicconstant | Q02 |
| G37 Formula executability beyond label | CR `_capacity_runtime` validates facts membership; profilev 2 no safe numericdomain/unit dependency closure | CONTRACT; P0 | Readinessv 3 alongsidev 2, perrun requirements C06 | D,A,U | ready label + invalid unit/missing input→blockedrun | Q05 |
| G38 Independent capacity endpoint | API `_runtime_snapshot` demands legacyruntime; CR `runtime_robots()` ignores CapacityRuntimeDTO | CONTRACT; P0 | Dedicated v2 analysis service consumes capacity DTO C11 | A,D | pool 21/24 no fake economics, unavailable active version explicit | — |
| G39 M strict contracts mismatched | Required Robot economics/autonomy/navigation; ScenarioResult floatpeople; horizon≤10 | CONTRACT; P0 | Separate CapacityResult/FinancialResult, horizon≤15, typed units C01/C11 | A,D,U | extra forbid, old response unchanged,new partial valid | Q02 |
| G40 Calculation/readiness sequencing | UI App uses Promise.all, readiness error tolerated; API calculate own constraints | CONFLICT; P0 | Server-owned shared constraints/executability, UI no alternate gate C05/C11–12 | A,U | readiness failure not silently full ready, stale input revision | — |
| G41 ScenarioSpec v1 coupling | SS economics mandatory, max speed/payload in everyfleet; seed input hash but no catalog/formula versions in body | CONTRACT; P0 | v2 capacity optional finance + complete version bindings C22 | A,D,U | v1 backward compatibility, version digest changes, unknown version | Q08 |
| G42 Scheduling vs capacity | SIM taskInterval 86400×batch/daily, report demand/day÷24; no shift/peak window | CONFLICT; P0 | Explicit operatingwindow/event schedule; approved SLA model C23 | A,D,U | 22h≠24h,20/30 minSLA, overloadqueue | K18,Q08 |
| G43 R12 2D+discrete event | RobCraft time-step engine, controls exist; required 2D and shared discreteevent report absent | PARTIAL/MISSING; P1 | Separate event/report service and 2D UI C23–24 | A,D,U | deterministic seed,controls,queues, progress≤60 sdefinition | K18 |
| G44 R12 deviation>10% | SIM getSimulationReport local movingutil / last 50 taskstats; no canonical parent report/denominator | CONTRACT/MISSING; P0 | Versioned comparison of same units/window, report immutable C23/C25 | A,D,U |9.99/10/10.01%,zero expected,warmup,revision | K18 |
| G45 Simulation availability | Capacity scenario already discounts wait/charge; simulation models these again | ASSUMPTION; P0 | Nominal/effective comparison + decomposition policy C23 | A,D,U | no doubled availability, energy arbitrary units excluded | Q08 |
| G46 Exports and presentation | UI report utils client PDF, no complete trace/R13 ledger/CSV; remote fonts | PARTIAL; P1 | Snapshot-driven exports/localassets C26 | A,U | exportedfigures=run, blocked fields labelled, no client recompute | — |
| G47 Immutable and tenant boundaries | API/persistence versionedruns and owner predicates exist; newregistry/trace versions missing | PARTIAL; P0 | Additive runversions, preserved owner/CSRF/upload checks C11/C28 | A,D | crossuser read/write/export denial,reopen old run,no livefetch | — |
| G48 Runtime/data gates | BUNDLE187/223,21/24 correct; calculation ready not deployment | PARTIAL; P0 | Keep counts until approved evidence delta; dualrun rollback C27–28 | D,A,U | BASabsence, exact sets,modelvsposition,unknown not default | Q05 |
| G49 R03 F34 geometry | SIM procedural scene dimensions/seed 42; no source-bound aspect/corridor profile | CONFLICT/ASSUMPTION; P1 | Synthetic geometry profile in ScenarioSpec/2D with label C22–24 | D,A,U | area conservation,boundaries 2000/10000/40000,no route mutation | K18 |
| G50 R03 F35 input completeness | RD weighted readiness dimensions; E dataquality otherfields; no exact R02 intake weights | CONTRACT; P1 | Separate readiness/evidence/input completeness metrics C03/C19 | D,A,U |40/70 boundaries,no salary weight,false highwithblocked avoided | K16 |
| G51 R09/R10 unsupported domains/BAS | M fourprocess profiles vs 28 blocks; no complete lifting/towing/manipulation/sterilization/BAS formulas | MISSING; P0 | Explicit UNSUPPORTED, process scope policy§3, C10 и microstages C10.01–28 | A,D,U | unsupported≠transport substitution; BAS outside pool | Q03,Q09 |
| G52 Historical docs/goldens | docs 14, economics fixturesv 1/v2 and ScenarioSpecv 1 encode oldbehavior | LEGACY; P1 | Keep immutable; new version fixtures and deprecation migration C28 | D,A,U | old runs still render, no accidental fixture overwrite | — |
| G53 R08 commercial field variants vs R03 formula units | M RobotEconomics scalar fields; E нет discriminated monetary basis/curve priority | CONTRACT; P0 | Per-robot amount vs price fraction, fixed repair vs percent, service amount vs fraction как явные альтернативы C13/C15 | A,D,U | no double line, wrong dimension rejected, explicit curve priority | K25 |
| G54 R10/R11 field priorities | I complete-profile validation, M defaults; UI нет field priority и automatic requirements | CONTRACT; P1 | Active-block required map, automatic requirements отдельно от supplied capabilities C03–05 | A,D,U | required no default, optional silent but traceable, auto cannot imply vendor fact | K26,K29 |
| G55 R02/R06 expert equipment priors | CR/BUNDLE сохраняют safe facts; разрешение 10 picks/min/800m²/h/2yr без evidence разрушило бы gates | CONFLICT evidence; P0 | Scenario-only generic exploration вне admitted vendor pool либо missing fact blocker C02/C06/C15 | D,A,U | no vendor admission through default; explicit exploratory label | K29 |
| G56 R00/R07 reproducibility vs stale roadmap statements | docs 12 §3 «состояние не сохраняется», docs 17 spec version claims, прежний nextstage; фактически persistence есть, SS body lacksbindings | CONFLICT docs/code; P1 | Датированное уточнение этого аудита; SS bindings только C22, historical docs не переписывать как прежние решения | D,U | old/new run compatibility, docslinks/sourcecoverage | K01,G41 |

Дополнительное расхождение контракта хранения:

| Gap / источник → target | As-is, точный модуль/участок | Тип; риск | Решение / этап | Миграции | Необходимые тесты | Принятое решение / dependency |
|---|---|---|---|---|---|---|
| G57 R00 независимый capacity snapshot | `backend/persistence_models.py:AnalysisRun`: `ck_analysis_runs_versions_nonempty` требует economics_version; `ck_analysis_runs_state_payload` требует ScenarioSpec для SUCCEEDED | CONTRACT; P0 | Новый run kind и additive per-kind invariants C11: capacity result/trace/version bindings обязательны, economics/ScenarioSpec обязательны только для соответствующего kind; старые constraints не ослаблять глобально | D,A | migration old/new run kinds, invalid payload rejected, missing trace rejected, old SUCCEEDED still valid, cross-user deny | K05,C01 |

Ни одно несоответствие evidence не лечится `extra=allow`, выдуманным Robot
или выдачей assumptions за vendor data. Несовместимые изменения получают
новую версию; legacy path сохраняется для replay до отдельной миграции.

## 5. Conflict register: решения приняты

Все конфликтующие источники сохранены. Статус всех K —
**ACCEPTED_FOR_IMPLEMENTATION** по поручению пользователя и полномочиям
команды из ТЗ§7.5/дополнений§7. Внешнего подтверждения перед исполнением нет.
Подробности, основания, trade-offs и checks (включая raw UNKNOWN currency,
годовой staffing ledger и конкретный offline demo budget):
[policy v1](planning/calculation-policy-decisions-v1.md).

| ID | Оба источника / противоречие | Принятое решение | Статус |
|---|---|---|---|
| K01 | R00: registry — единый источник; registry отсутствует. R04/R07 заголовки/счётчики не совпадают с R13 п.34 (70/85) | Создать registry из всех R02/R06 entries со стабильными semantic IDs; происхождение каждого поля и supersession explicit. Счётчики заголовков70/85 не являются validation schema. | ACCEPTED |
| K02 | R03 §1.1 passport speed vs R08 §3.2 working speed; R03 total exchange vs contractv 2 legacy 45 per-operation | Normalized exchange — total seconds; raw load+unload имеет приоритет. Legacy45 per operation мигрируется в total90 только в provenance-known legacy path; новое total45 остаётся45. Speed: USER operating≤safe max; иначе safe operating fact; иначе safe max как раскрытый optimistic proxy без дополнительного коэффициента. | ACCEPTED |
| K03 | R02 §5 boxes=floor(payload/item), не manual; R03 §1.1 допускает passport batch | Для boxes предел массы=floor(payload/item_mass); batch=min(предел массы, explicit user handling limit, safe passport batch, геометрический limit), отсутствующие дополнительные ограничения не входят в min и отмечаются unknown. Остальные единицы batch1, кроме явно введённого физического batch. | ACCEPTED |
| K04 | R03 §1.4 clamp utilization/coverage vs отсутствие zero-domain и отдельного overload/SLA | Demand>0 у активного процесса; inactive→N0/N_A. Fleet0 допустим what-if: capacity0,coverage0,utilization null,OVERLOADED. При capacity>0 сохранять raw load ratio и clamp utilization≤1; ни coverage, ни utilization не равны SLA. | ACCEPTED |
| K05 | R00/R04/R10 missing salary→не рассчитывать весь блок; R11 no-role→нет ФОТ, другие процессы допустимы; R03 §3.2 tech/control absent→0+warning | Capacity рассчитывается независимо от зарплаты. Labour/finance требуют зарплату активной роли; no-role процесс имеет NO_FOT_BENEFIT. Tech/control без зарплаты дают INCOMPLETE для соответствующей статьи, не0. Demo wages — отдельный явно принятый scenario input из официального dataset, не USER и не vendor fact. | ACCEPTED |
| K06 | R03 §2.6 pult_remain=max(share,min), released subtraction; operators_from_released=min(share,remain), additional=remain-share; текст обещает минимум из высвобожденных | applied=floor(robot_replacement×limit); demand_pult=max(floor(applied×share),shifts×min_per_shift); transferred=min(applied,demand_pult); released=applied−transferred; additional=demand_pult−transferred. | ACCEPTED |
| K07 | R03 §2.8 deficit отдельно от base; §3.5.1 включает; R11 схема 5 unset не монетизируется; R02/R04 replacement 57/R13 п.39 default direct; R13 п.26 «если задано» | Default unit_deficit_cost=annual_direct как видимое scenario assumption, пользователь0 отключает. Deficit benefit отдельной строкой от savings; remaining_deficit_t=max(0,deficit−floor(growth×ramp_t)); annual cost indexed8%. | ACCEPTED |
| K08 | R03 §2.7 role withdrawal без division shifts, fallback с division и без cap; R06 доля.30 | Base equipment=input integer иначе ceil(role_drivers/shifts), иначеunknown. Withdrawal по роли=min(base,ceil(released_driver/shifts)); fallback=min(base,ceil(released×.30/shifts)). Если base unknown, equipment savings неизвестна, не размер всей fleet. | ACCEPTED |
| K09 | R03 §3.2 service no ramp vs §3.5.2 «уже масштабирован»; saving×ramp vs ceil(released×ramp); severance только year 1; R02 ramp только 5 years при horizon 15; R13 §2 упрощён без ramp vs п.45 | Ramp из R02, с6-го года1. Годовой released=ceil(released_final×ramp), savings выводится из difference role ledger, не linear savings×ramp. Service после warranty масштабируется ramp один раз. Severance=положительный прирост released_t против t−1 × monthly×2.5 во все годы прироста. | ACCEPTED |
| K10 | R03 §3.3 один battery year vs длительный horizon и rampwear; повторные замены не описаны | Повторные батареи по накопленным циклам с ramp: cumulative_cycles_t=Σannual_cycles×ramp_t; события, когда k×resource_cycles строго меньше cumulative до конца года. Exact crossing в конце horizon не покупает батарею без последующей работы. Cost=count_events×N×battery_price×hw×1.05^(t−1), без второго ramp. | ACCEPTED |
| K11 | R03 §3.2 «полный CAPEX для амортизации» vs §3.5.5 без reserve; R13 п.7 полный CAPEX для% vs п.46 equipmentonly; residual mapping не для cleaners | Percent base=equipment only, depreciation=capital without reserve/5; reserve не актив. R03 life/liquidity для перечисленных classes; cleaner/неизвестный class без safe/user life → residual0 с conservative-assumption. Explicit validated residual curve имеет приоритет. | ACCEPTED |
| K12 | R03 other_income позволяет negative tax; no_other_income/max и losses 50%/10 years; R01 нормативные ссылки без текущей верификации | Основной конкурсный результат — собственные средства, денежные потоки до налога на прибыль. Налоговые сценарии R13 — дополнительная иллюстративная модель с явными25%/режимами, не юридическое обещание. Алгоритм ниже; внешний legal sign-off не prerequisite. | ACCEPTED |
| K13 | R03 §3.6 effect excludes t0, ROI=effect/CAPEX; optional profitability ещё вычитает TCO; current E другой ROI; zeroCAPEX не определён | Primary simple payback — пересечение накопленного differential CF с учётом−CAPEX вt0; при постоянном CF совпадает с CAPEX/effect ТЗ. ROI=ΣdiffCF1..h/CAPEX; для RaaS denominator=TCO. CAPEX0 → payback0 лишь при неотрицательном потоке и положительном эффекте, иначеN_A; ROI denominator0→N_A. Нелогичный дополнительный profitability_TCO не публикуется. | ACCEPTED |
| K14 | R03 §4 availability высокие значения штрафует «нет резерва», хотя это не utilization; payload decline endpoint не дан; N/A-компоненты и interpolation заданы не полностью | Piecewise linear interpolation по узлам R03. Payload margin выше.5 линейно падает до.5 при margin1; availability сохраняет немонотонные узлы R03 как model preference. N/A компоненты исключаются с перенормировкой весов; UNKNOWN=0 без перенормировки; no required integrations=1. | ACCEPTED |
| K15 | R03 §5 «8+21=29» с объединением sterilization; clinic sterilization universal против допуска дневного cleaner в R08 §11 без неё/лифтов; wasteB приравнен explosion; EASA/ICAO названы certificate | Checks имеют process/route/zone/time scope; clinic sterilization только при требуемом sanitization; этажи — реально пересекаемые маршрутом. Class-B требует cleaning/containment compatibility, не универсальную взрывозащиту. Airside — отдельное требование operational permission, не вымышленный «сертификат EASA/ICAO». | ACCEPTED |
| K16 | R02/R03 Σ75=12×3+16×2+7; R08 фактически 17 important→77. R03 completeness «=70 high» vs 40–70 working; R02 §9 без salary полнота блока 0, R03 §7 только salaryweight 0 | Поля R08 — источник перечня:12critical+17important+7useful, полный вес77. N/A исключается. Intake completeness отдельно: weights sum100; <40 basic,40≤x<70 working,≥70 high. Missing salary делает labour completeness0, capacity completeness считается по своим inputs. | ACCEPTED |
| K17 | R11 allocation по processCAPEX, но selection зависит Score/NPV, зависящих от shared cost; нет zero CAPEX allocation; staff shared между blocks | Shared site CAPEX распределяется по прямому capital без shared/reserve; если сумма0 — поровну между активными процессами, remainder по stable ID. Shared staff распределяется один раз по явным shares или required person-shifts, largest-remainder; правила cohort ниже. | ACCEPTED |
| K18 | R12 sameparams и deviation>10%, но нет denominator/window/warmup/distributions; R03 synthetic geometry vs реальный L; operatinga уже включает downtime | Детерминированный event scheduler, FIFO, fixed calendar/measurement и SLA definitions из §4 ниже. Availability применяется один раз как service-time dilation; неизвестные failure rates/зарядные циклы не выдумываются. | ACCEPTED |
| K19 | R11 схема 3 новые 7 roles, схема 9/R10§8 их не перечисляют; process_catalog только schema; warehouse/airport/clinic 28 blocks и 4 формульныхсемейства | Role dictionary — union R11 схем3 и9/R10, role code scoped object; mapping28blocks закреплён §3. Unsupported physical operations получают REFERENCE_ONLY, generic user-configured cycle доступен как SCENARIO_ONLY. | ACCEPTED |
| K20 | R00/R02/R03 prices безНДС vs текущий raworganizerVAT_INCLUDED безставки; R01 не доказывает price facts | Основная денежная база — CASH_GROSS_RUB, цены organizer уже включают НДС (A4). Ставку не угадываем и НДС повторно не добавляем. NET_RUB — отдельный режим только при explicit rate/basis для каждой применимой строки; недостающий rate не мешает gross result. | ACCEPTED |
| K21 | R13 п.11 RaaS «в OPEX» vs п.40 отдельная line; R02 §2 OPEX_RaaS без operators vs §3.3 с ними; zeroing broad vs реальные vendor contracts неизвестны | RaaS .02/month как scenario tariff; contract horizon=h, renewal автоматически доh на тех же условиях, buyout0/off; phased/all_fleet поR03. Responsibility tableR02 сохраняется как model assumption. Payment отдельной строкой и один раз входит total OPEX/CF/TCO. | ACCEPTED |
| K22 | R01 описывает 43 решения и рекомендованную формулу ТЗ с резервом в знаменателе; R03 §1.1 применяет peak×reserve; фактический каталог 187/223 | Capacity=ceil((daily/H)×1.25×(1+reserve)/(nominal×availability)); extra target utilization multiplier отсутствует. Formula trace показывает все три понятия ТЗ: пик, availability и reserve. | ACCEPTED |
| K23 | R01/R00 обязательные поля без defaults; R01 и R09 §3 одновременно требуют ввод плеча и дают резерв 120m; R02 §5–6 defaults лишь optional/desirable | Общий transport route — USER input. Для demowarehouse120m — видимый scenario assumption изR09,25m остаётся picking distance. Defaults разрешены только с explicit source/priority; никакого скрытого sourcefact. | ACCEPTED |
| K24 | R11 схема 6 перечисляет ranking перед финансовыми показателями; R03 §4 Score требует NPV кандидатов и shared allocation | Порядок DAG: input→constraints→capacity→labour→cost/CF→allocation→NPV→score. Предварительная техническая сортировка называется отдельно. | ACCEPTED |
| K25 | R08 §6 commissioning/training RUB/robot vs R03 доля price; spares%CAPEX в OPEX vs разовый CAPEX; fixedrepair/service%/explicit residual curve не описаны полноценно в R03 | CostBasis union FIXED_TOTAL/PER_ROBOT/PERCENT_BASE, ровно один вариант/line. Spares по умолчанию разовыйCAPEX; recurring supplies отдельнаяline, не дубль. Service fixedannual приоритетнееpercent только если legacy source содержит оба; для новогоinput оба запрещены. | ACCEPTED |
| K26 | R10 §7.2 mandatory с defaults vs §2 mandatory без defaults; optional process volumes в §6/7 становятся mandatory §9; автоматические requirements vs редактируемые значения | Active-block объём required, inactiveblock неошибка. Automatic object requirements — policy-derived, не доказанные capabilities робота. Обязательные поля не заполняются hiddendefaults; optionaldefault сохраняет trace без interrupt. | ACCEPTED |
| K27 | R06:5 как «середина 5–7»;365/(365−30)≈1.089552 vs 1.090;1.302×1.19=1.54938 vs 1.55; обоснование pult 1/4 robots, формула sharepeople; краткий growth может быть negative | Хранить1.090/1.55/1.302 как принятые exactdecimal assumptions; пояснения≈, не альтернативные вычисления. Rotation промежуточно не округлять:1.4×1.090×1.25=1.9075. Human cleaning300m²/h относится к механизированному baseline; ручной baseline требует user rate. | ACCEPTED |
| K28 | R04 замены 18/24/32/34/46 vs D9/замены 51/58/64/66; R07 правка 64 зануляет отрицательный score vs 72 minmax; ранние R06§3/5 старые CAPEX/TRL penalties | Supersession: R04 D9 и замены51/58/64/66, R07§72 вытесняют ранние inconsistent строки. Архивные документы не правятся, registry хранит replaced_by. | ACCEPTED |
| K29 | R02 §8 defaults 10 picks/min/800m²/h, R06 class priors и R10 §12 warranty 2/MTBF vs R03/R08 passportfacts и действующие evidence gates | Default10picks/min/800m²/h/2yr/MTBF никогда не заполняют vendor fact. Safe mandatory fact отсутствует→модель вне соответствующего vendor calculation profile; параметры generic scenario вводятся отдельно с explicit assumptions. Research улучшает data позже, но не блокирует merge. | ACCEPTED |

## 6. Formula trace и воспроизводимость

### 6.1. Обязательный контракт

Реализованный в C01 контракт `CalculationTrace v1` — строгий JSON Schema/Pydantic контракт
с `additionalProperties=false`, явным discriminated union quantities и
nullable blocked result. Свободный текст не заменяет machine-readable узлы.

| Поле / структура | Обязательное содержимое |
|---|---|
| Envelope | schema_version, engine_version, run_id, input_revision, scenario axes, process_id, model_id и position_id отдельно |
| VersionBindings | catalog_version_id + content digest, capacity_projection_version/digest, registry_version/digest, process_catalog_version, formula_bundle_version, constraint_rules_version, commercial_policy_version, precision_policy_version |
| FormulaNode | node_id, formula_id, formula_version, source_refs(R03§1.1 и т.п.), source_digest, expression/template_id, applicability domain |
| InputQuantity | name, raw_value, raw_unit, normalized_value, unit, quantity_kind, numeric_encoding, provenance_ref; unknown value отсутствует, status и missing_reason обязательны |
| Provenance | USER/FILE/PRESET/VENDOR_FACT/ASSUMPTION/POLICY/DERIVED; user confirmation revision, file hash+sheet/cell или row, fact_id/model/position/scope, evidence IDs, evidence status, registry parameter ID, parent node IDs |
| UnitConversion | from/to unit, exact factor, operation, before/after, unit-definition version; каждая значимая конверсия видна |
| Intermediate | упорядоченные typed values и links: H, cycle, trips/h, batch, nominal/effective capacity, peak, unrounded ratio, ceil result и т.д. |
| AssumptionUse | assumption_id/version, source, rationale, permitted scope, default/override, raw user override, applicable scenario, consent/confirmation state |
| ConstraintEvaluation | check_id/version, required/available units and refs, PASS/FAIL/UNKNOWN/ASSUMED/N_A, criticality, reason_code, scope, prerequisite refs |
| Rounding | operation ceil/floor/quantize/display, input exact value, output, precision policy, reason/source; порядок относительно ramp/indexation |
| Result | typed value + unit либо null; execution status; supporting node IDs; capacity effective/nominal маркированы |
| Warnings / blockers | stable reason codes, severity, field/node refs, missing facts, research/decision IDs, human-readable localized message |
| Replay | canonical_input_digest, trace_content_digest, deterministic seed где нужен; build/runtime metadata отдельно от semantic digest |

Value provenance и разрешение использовать value — разные поля. Fact с
CONFLICT/UNKNOWN/AMBIGUOUS_MODEL_MATCH/NOT_FOUND не проходит resolver,
даже если trace способен его описать. В trace отказа можно ссылаться на
отклонённый fact, но не включать его число в исполняемую формулу.
Зарплата и персональные поля не попадают в общие application logs; доступ к
trace/snapshot/export ограничен владельцем проекта и существующей RBAC.

### 6.2. Детерминированность и наблюдаемость

- Входы проходят один server normalizer; browser/LLM не рассчитывают итоговые
  величины. Все quantities, включая display conversions, возвращаются API.
- Порядок: стабильные process/role/model/position IDs, scenario enum order,
  year ascending, topological formula order со стабильным node ID; tie-break
  рейтинга по model/position ID. Порядок dictionary/SQL rows результата не меняет.
- Canonical serialization фиксирует decimal strings, units, null/absent,
  Unicode normalization и порядок полей. Random UUID/timestamp сохраняются
  metadata, не используются как численный seed или content digest.
- Повторный расчёт использует immutable source snapshots; registry/catalog
  update создаёт новый run и revision, не меняет старый. Live vendor fetch/LLM
  отсутствует в численном execution path.
- Для каждой публичной цифры есть result→node→inputs→evidence/assumption.
  В blocked branch trace заканчивается причиной, не фиктивным вычислением.
- Метрики: executions и blockers по formula/profile/version, duration,
  missing input/evidence counts, divergence dual-run; correlation run/request
  IDs. Не логировать raw uploads, зарплаты, email, имена и access tokens.
- Для повторяемости simulation отдельно фиксируются seed, schedule,
  distributions/version, warm-up, measurement window и time/event ordering.
  Технический trace вычислений и событийный simulation trace не смешиваются.

Example contract fixture C01 должен содержать граф F01→F02→F03→F04→F07,
один USER distance, один VENDOR_FACT speed, один ASSUMPTION availability и
один BLOCKED пример без speed evidence. Это specification fixture,
не реализация формулы и не карточка реального робота с вымышленной ценой.

## 7. Phased plan

Подробные карточки с backend/API/frontend/data/trace/tests/acceptance,
границами и зависимостями каждой итерации:
[исполнительный план](planning/zhenya-phases.md).
Каждый этап — отдельная ветка и reviewable PR. Поведение production меняется
только после соответствующего rollout gate; feature flags не заменяют
owner/evidence/schema validation. Ветки Cxx — рекомендуемые точные имена.

| ID | Ветка / результат | Зависимости |
|---|---|---|
| C01 COMPLETE | `contracts/calculation-semantics-v1` — единицы, статусы, conflict decisions, trace skeleton | Этот аудит |
| C02 COMPLETE | `data/calculation-parameter-registry-v1` — versioned constants/policies | C01 |
| C03 COMPLETE | `intake/process-role-normalization-v2` — backend intake/roles/units | C01–02 |
| C04 | `frontend/process-role-intake-v2` — формы, input provenance, validation | C03 |
| C05 | `engine/applicability-constraints-v2` — общий constraint service | C01–03 |
| C06 | `catalog/formula-executability-audit-v3` — dependency closure по каждому profile | C02–03,C05 |
| C07 | `engine/capacity-formula-trace` — transport/delivery pure capacity | C06, policy K02–04 |
| C08 | `engine/cleaning-capacity-trace` — cleaning units/capacity | C06, trace infrastructure C07 |
| C09 | `engine/palletizing-capacity-trace` — fixed-cell math, без расширения pool | C06–07, picks mapping |
| C10 | `contracts/process-profile-coverage-v1` — все28scopes поpolicy§3 | C03,C07–09; K19 |
| C11 | `api/capacity-analysis-snapshots-v2` — независимый API и immutable trace | C05–10 |
| C12 | `frontend/capacity-results-trace` — partial results и объяснение N | C04,C11 |
| C13 | `procurement/commercial-inputs-v1` — цены/НДС/условия, отдельные gates | C01–03 |
| C14 | `engine/role-labor-baseline-v1` — baseline, rotation, pult, deficit | C03,C07–10; K05–08 |
| C15 | `economics/purchase-cost-ledger-v1` — capital и operating статьи | C02,C13–14; K09–11 |
| C16 | `economics/full-cashflows-reconciliation-v1` — налоги/CF/метрики | C15; K09,K12–13 |
| C17 | `economics/raas-cashflows-v1` — второй acquisition mode | C13,C16; K21 |
| C18 | `economics/multiprocess-allocation-v1` — общий объект и role pools | C14–17; K17 |
| C19 | `engine/ranking-v2` — R03 score после CF и gates | C05–06,C18; K14–16 |
| C20 | `economics/sensitivity-v1` — price/volume/labour deltas | C18–19 |
| C21 | `frontend/commercial-scenarios-v2` — финансовые сценарии и сверка | C12,C13,C18–20 |
| C22 | `contracts/scenario-spec-v2` — capacity snapshot и optional finance | C11; при наличии finance C18 |
| C23 | `simulation/scheduling-kpi-report-v1` — event model, SLA и report | C22 + policy K18/§4 |
| C24 | `visualization/2d-simulation-report` — обязательная 2D | C23 |
| C25 | `robcraft/scenario-v2-reconciliation` — v2 adapter и KPI comparison | C22–23 |
| C26 | `report/calculation-evidence-exports` — PDF/XLSX/CSV из run | C21,C24–25 |
| C27 | `catalog/capacity-runtime-dual-run-rollout` — независимый capacity rollout | C11–12; можно сразу после них, не ждать economics |
| C28 | `catalog/economics-runtime-migration` — полный v2 rollout, legacy isolation | C21,C26–27; replay/rollback |
| C29 | `qa/calculation-migration-acceptance` — сквозная приёмка | C28; scope T1/policy§3 |

Порядок C13–20 и C22–25 допускает независимые ветки по зависимостям.
C10 реализует принятые28scopes, включая REFERENCE_ONLY и CONSTRAINT_ONLY.
Неизвестные физические алгоритмы не являются release dependency. После C29
можно расширять их отдельными versioned профилями; сейчас обязательны T1–T4.

### 7.1. Подробный scope `engine/capacity-formula-trace`

Вход: `NormalizedProcess`, безопасный `CapacityRuntimeDTO`, registry snapshot,
constraint/executability report, выбранный uncertainty scenario и optional
manual N. Никаких обязательных price/service/autonomy/fte_replace полей.
Выход: typed cycle_s, trips/h, batch, nominal/effective units/h, demand/peak,
recommended/selected fleet, coverage/utilization, limits, trace/blockers.

Реализовать F01–04/F07, precision policy§5 и box batch K03. Delivery использует ту же математическую семью **только при
корректной единице доставки и input contract**. В текущем pool нет delivery
моделей: unit fixtures допустимы, добавлять synthetic vendor card нельзя.
Транспортный pool 15 моделей/18 позиций — фактический кандидат для нового path,
но утверждение executability выдаётся по inputs каждого run, не по числу 15.

Backend: предложенный пакет `backend/calculation/capacity/transport.py`,
общие quantity/resolver/trace modules; legacy `economics.py` пока не удаляется.
Новые fixtures с explicit synthetic identity вне каталога и независимыми
ожиданиями. Нет API route switch, economics, cleaning/cell algorithms,
frontend, procurement, SLA scheduler, pool expansion или runtime activation.
Golden trace обязан отличать total 90 от split 45+45 и от total 45; показать
1.5 peak и .70 availability в base, без скрытого .90 reserve. Повторный запуск
и перестановка input/fact rows не меняют semantic digest. Critical unknown
приводит к BLOCKED, а не fallback скорости.

## 8. Тестовая стратегия

### 8.1. Fixtures и проверяемые примеры

Новый namespace `zhenya-3.2-policy-v1` хранит source hashes, accepted decision
IDs, normalized input, registry/catalog versions, expected result, full trace
и tolerances. Старые `backend/fixtures/economics-warehouse-v1.json`,
`economics-warehouse-v2.json` и `contracts/fixtures/scenario-spec-v1*`
сохраняются. Новые golden expectations проверяются независимым ручным
разбором; запрещено получать «ожидаемое» тем же engine и просто закреплять.

| Fixture | Авторитетный пример / смысл | Ожидаемая проверка |
|---|---|---|
| Golden-Warehouse-Intake | R05 warehouse 20 000/10 000m²,2×11h,total 2 000/day, staff 180 | Раздельные inbound/outbound, picking 25m не паллетный route, salary missing financial blocked |
| Golden-Airport-Units | R05 terminal 85 000→clean 51 000; routes 200/400/300/300 | Derived factor.6 trace; cart≠kg; zone/time constraints |
| Golden-Clinic-Batches | R05 1 950 portions/1 200 samples/linen 1 800+1 800kg | Без portions/cart/samples/container — blocked conversion; SLA20/30 min NOT_EVALUATED до C23 |
| Golden-Rotation | R03 §2.4 пример 14 человеко-смен, rotation 1.908 | ceil(14×1.908)=27, не 26 и не умножение shifts второй раз |
| Golden-Residual | R03 §3.4 life 10/liquidity.6 | horizon 5 →30%,7→18%; cell 8/.4,h5→15%;h≥life→0 |
| Golden-Reconciliation | R03 §3.5.3/R13 −100 млн baseline,−80 млн scenario | NPVproject+20 млн; negative project flow не равно отрицательному эффекту |
| Golden-Transport-Synthetic | Новая явно synthetic fixture: L120m,v1m/s,total 90s,H22h,daily 2000,unit/trip 1,a.70,peak 1.5 | cycle 330s; nominal 120/11 units/h; effective 84/11; required 1500/11; ceil(125/7)=18; не vendor fact |
| Golden-ManualFleet | Тот же syntheticinput,selected 17/18/19 | Coverage вычисляется по фактическим units/h, не selected/recommended ratio |
| Golden-Purchase/RaaS | USER prices/roles + approved registry, same physicalfleet | zeroing/payment/single tax effect, complete capital/operating ledger |
| Golden-Partial | Capacityinputs полны, salary/price/tax unknown | Capacity complete, economics incomplete, no score/recommendation falsepositive |
| Golden-Gross | Все статьи и валюта заданы, ставки НДС нет | CASH_GROSS_RUB и primary pretax economics исполнимы; NET_RUB требует rate, исходная gross цена сохранена |
| Golden-Policies | Принятые K02/K06/K10/K14 | Exact outcomes policy: exchange90, pult conservation, repeatedwear, score knots; unknown policy version rejected |
| Golden-Shared | 2 processes, shared site cost и одна role pool | Общаяинфраструктура 1 раз, sumallocated=total, released≤shared pool |

### 8.2. Boundary tables и invariants

| Область | Граничные значения / негативные случаи |
|---|---|
| Capacity domain | demand 0/negative/missing;H0/24/>24;v0/negative;L0/negative;cycle 0;manualN0;availability 0/1/>1;ceil ratio k−ε/k/k+ε |
| Exchange/batch | total/split mutually exclusive; total 45 vs 45+45; payload=item/±ε;itemweight 0;boxes geometry unknown;units_per_trip fractional/unsupported |
| Labour | shifts 1/2/3;hours 6/8/9/10/11/12;rolecount 0;salary missing/explicit 0;limit 0/1/>1;applied<minimum_pult;tech 20/21 robots |
| Calendar/finance | days 0/365/366 policy;horizon 5/7/10/15/outside;discount 0/negative policy;CAPEX0;warranty 0/3/h;replacement year=h/h+1;life=h |
| Ranking | availability 39.99/40/55/70/85/92/100%;aislemargin 0/.15/.40/.60;payloadmargin 0/.15/.50/>.50;TRL6/7/8/9;equalNPV/all negative |
| Completeness | no applicable fields;salary absent;weights77 по принятому K16;39.99/40/69.99/70/70.01;unverified filled cannot become matching-safe |
| Constraints | noise day/night and required zone;floor thresholds;airsideknownfalse/unknown;actual routefloors;budget/chargingpower warnings not hard fail |
| Simulation | windows/warmup/seed, zeroexpected, deviation 9.99/10/10.01%;queue overload,paused/restarted,20/30 min SLA boundaries |
| Catalog/API | unsupportedBAS, unsafe/ambiguousfact,wrong unit,evidence wrong model, duplicate position IDs, unknown schema/field, stale input revision |

Property/invariant tests: N не убывает при росте demand/L и не растёт при
росте speed/availability при остальных фиксированных параметрах; coverage
в[0,1]; recommended N удовлетворяет ceil-условию; size не зависит от salary.
Ротация и смены не учитываются дважды. Person allocation консервативен,
released≤eligible pool; RaaS не имеет robotCAPEX/battery/residual;
equal baseline/scenario CF дают NPVproject 0. Fixed overhead одинаков в обоих
потоках. Payment/taxshield/charging losses не задваиваются. Allocation сохраняет
сумму независимо от порядка процессов. NPV и полный ranking **не обязаны**
быть глобально монотонными из-за ceil, ramp, налогов и изменения cohort.

Unit tests проверяют отдельные pure formulas и преобразования s/h,
W/kW/kWh, mm/m, km/h/m/s, g/kg/t, percent/fraction, ₽/month/year,
VAT basis, pallet/box и area/time. Несовместимые quantity kinds отвергаются.
Integration tests проверяют resolver→readiness→engine→trace→snapshot,
import/publish/activation только disposable DB, no evidence bypass,
rollback/replay, user isolation и CSRF. Live external services не требуются.

API contract tests: strictrequest/response, independent status layers,
optional economics, blocked outputs withoutfake 0, old/new versions,
model/position identities, same input revision между panes. Frontend tests:
нет локальной зарплатной/финансовой арифметики, источник каждого assumptions
виден, no false best при all negative/incomplete, no salary default,
partial flow, одинаковые числа dashboard/report, accessible inputs.
ScenarioSpec Python/JS и two-phase origin/source/revision protections сохраняются.

Catalog regression должен проверять exact identity **sets**, не только counts:
discovery 187/223, capacitybaseline 21/24,6/6 ready+15/18 assumptions,
deployment 0, БАС отсутствуют. На approved membership change обновляется новая
versioned fixture с decision/evidence diff; baseline fixture не переписывается.

## 9. Вопросы закрыты для реализации

Q01–Q12 больше не требуют ответа Жени или внешнего reviewer. Ниже конечное
поведение; более поздний review может выпустить policy v2 и новый расчёт,
но не изменяет старые runs и не является prerequisite C01–C29.

| Q | Закрытое решение | Runtime outcome при недостаточном пользовательском вводе |
|---|---|---|
| Q01 | K01, registry создаётся нами | Нет dependency на внешний registry |
| Q02 | K04/K13/K16/K27 и§5 | Валидация полей/N_A вместо ожидания policy |
| Q03 | K19 и28строк §3 | Определённый scope каждого процесса |
| Q04 | K02/K03/K23 иbatch §3 | Missing input с перечнем нужных преобразований единиц |
| Q05 | K29/§6; текущийpool фиксирован | Missing safe fact локально исключаетSKU/profile |
| Q06 | K06–08/K27/§5 | Labour INCOMPLETE при недостающей зарплате/ставке |
| Q07 | K12/K20/K21/K25 | Gross budget работает без ставки НДС и vendor quote |
| Q08 | K18/§4 | Определённые scheduler/SLA/conditional statuses |
| Q09 | K19/§3 | REFERENCE_ONLY/CONSTRAINT_ONLY — принятые product scopes |
| Q10 | K09–11/§5 | Повторные циклы, ramp и неизвестный residual определены |
| Q11 | K14/K16 | Все scoring curves/denominators определены |
| Q12 | K17/§5 | Allocation и cohort имеют конечный алгоритм |


## 10. Проверки аудита и условия коммита

Изменения этого аудита — только docs/README и planning artifacts; runtime
bundle, contracts production, backend/frontend, `.github`, секреты и
исторические fixtures не изменяются.

Исторические проверки аудита1.0 (новая редакция меняет только документы):

| Проверка | Результат / предел вывода |
|---|---|
| Reference coverage | 14/14, exact recursive path set, bytes, lines, SHA-256 совпадают с manifest |
| Плановые IDs | 35 формул, 57 gap rows, 29 conflict rows, 12 групп вопросов; 29 основных этапов и 28 process microstages |
| Markdown | Локальные file links, fences, согласованность нумерации и таблиц; специального Markdown/link checker в repository не найдено, использована локальная структурная проверка |
| Backend | 169 уникальных существующих тестов выбранных calculation/intake/readiness/catalog suites прошли: основной запуск 168passed+1setup error; этот тест отдельно 1passed с рабочим `--basetemp` |
| Причина rerun | Системный pytest temp под `C:\Temp` недоступен; rerun `backend/test_object_profiles.py::test_profile_checksum_mismatch_is_rejected` использовал собственную временную папку workspace, затем удалённую |
| Frontend | `npm.cmd test --prefix frontend`: 21passed |
| ScenarioSpec contracts | `node --test contracts/scenario-spec-v1.test.mjs`: 4passed |
| RobCraft | `node --test robcraft/tests/*.test.mjs`: 77passed |
| Git | Проверены diff, diff --check, allowlist документационных изменений и отсутствие случайных generated/secret/.github файлов |

Backend suites: `backend/test_economics.py`, `test_contract_stage_a.py`,
`test_readiness.py`, `test_object_profiles.py`, `test_project_file_intake.py`,
`test_catalog_repository.py`, `test_catalog_runtime.py`,
`test_catalog_calculation_readiness_v2.py`, `test_catalog_capacity_runtime.py`.
Запуск с `PYTHONDONTWRITEBYTECODE=1` и `pytest -p no:cacheprovider`.
В выводе был существующий deprecation warning Starlette/AnyIO; это не failure.
Node в sandbox получал EPERM при обходе пути профиля; существующие тесты
повторены вне sandbox с разрешением tool approval, без изменения кода.

DB migrations, Compose smoke, runtime activation, production deployments и
новые расчётные формулы в этой сессии не запускались. Зелёные существующие
тесты подтверждают baseline, **не соответствие будущему канону Жени**;
новые expected results и acceptance gates перечислены в §8 и карточках Cxx.

## 11. Проверки редакции 1.1

2026-09-20: полностью прочитаны 20 страниц двух официальных PDF. Повторная
проверка рекурсивных списков, размеров, SHA-256, количества строк/страниц:
14/14 reference и 2/2 официальных источника совпадают с manifests.
Все 29 K и 12 Q сопоставлены принятым решениям; также закрыты прежние Q1–Q8
из docs/11. Совпадают 29 веток/карточек этапов и 28 process scopes.

Структурная проверка восьми Markdown-файлов: 63 локальные ссылки, таблицы,
парность fences, IDs F01–35/G01–57/K01–29/Q01–12. Арифметическая проверка
плановых примеров: 18 групп, включая 3535 сочетаний для conservation персонала;
MULE при заданных inputs даёт парк 20/15/13 в трёх сценариях. Это независимая
проверка спецификации через Decimal, не реализация production engine.

SHA-256 всех 10 файлов committed catalog bundle совпадают с manifest;
discovery 187/223, pool 21/24, БАС в pool 0. Проверены safe payload/speed MULE
и исходная price position. Git allowlist содержит только девять документов
и плановых артефактов; diff/diff --check проверяются перед коммитом.
Backend/frontend/runtime данные не меняются. Исторические 169/21/4/77 tests
выше не выдаются за новый прогон; regression выполняется при реализации
соответствующего этапа.
