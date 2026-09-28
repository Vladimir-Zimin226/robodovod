# Принятые решения для автономного внедрения расчётной модели

Статус: **ACCEPTED_FOR_IMPLEMENTATION**, policy `hackathon-calculation-policy-v1`.
Дата: 2026-09-20. Основание полномочий: пользователь поручил самостоятельно
разрешить конфликты, ориентироваться на ТЗ и завершить план без ожидания Жени.
Это новые решения текущей сессии; они не приписываются авторам reference.
Изменения только документационные. Базовый аудит сохранён в коммите
`d2c6a4c62cca30a0169c092aebea66672d8524cb`.

Родительские документы: [план 19](19_ZHENYA_CALCULATION_IMPLEMENTATION_PLAN.md),
[карточки этапов](zhenya-phases.md). Этот документ определяет исполнение
спорных F/K/Q; исходные пары конфликтующих утверждений остаются в плане 19.

## 1. Приоритет и полное покрытие официальных источников

Прочитаны полностью оба файла рекурсивного списка папки
`Разобрать/Материалы от организаторов/ТЗ`: 13+7 PDF-страниц, включая обложку,
критерии, сдачу и определения оборудования. Ниже номера физических PDF-страниц.
Пути, размеры и SHA-256 закреплены в
[manifest официальных источников](official-requirements-coverage.json).

| ID | Источник | Применяемое требование |
|---|---|---|
| T1 | `1. ФЦ БАС.pdf`, стр.3, §2; стр.10, §5.4–5.7 | Полный сценарий на одном типе объекта; три типа представлены выбором, вводом и доступными решениями; честно указать глубину реализации |
| T2 | То же, стр.5–6, §3.2–3.4 | Единицы, defaults/source, каталог, причины включения/исключения; недостаток данных допускает «требует проверки»; hard impossibility запрещает рекомендацию |
| T3 | То же, стр.7–8, §3.5 | Прозрачные формулы и допущения, состав оборудования, CAPEX/OPEX/эффект/окупаемость/ROI/TCO≥5 лет, корректировки, ≥3 сценария и ≥3 sensitivity inputs |
| T4 | То же, стр.8–10, §3.6–3.8, §4 | Обязательная 2D с KPI и controls, exports, versions, Docker/СУБД, offline demo,10s/60s, security/isolation; 3D дополнительна |
| T5 | То же, стр.11, §7.5 | Неполные исходные данные разрешают обоснованные явно описанные допущения |
| A1 | `Дополнения для участников.pdf`, стр.1–2, §2 | Собственные средства по умолчанию; метод/срок амортизации, состав затрат и RaaS определяет команда |
| A2 | То же, стр.2–3, §3–4 | Дополнять существующие решения; новые модели опциональны; missing ТТХ отражать с допущениями и ограничениями |
| A3 | То же, стр.4, §5 | Допускаются явные предположения об инфраструктуре объекта |
| A4 | То же, стр.4, §6 | Цены включают НДС; доставка, пусконаладка и глубокая интеграция не включены; дубли — альтернативные предложения |
| A5 | То же, стр.4–5, §7 | Команда самостоятельно определяет exclusions, CAPEX/OPEX, missing-data policy, RaaS и глубину расширения каталога |
| A6 | То же, стр.5–7, §8 | Различать AMR, FMR, штабелёр, тягач, уборщик и стационарную систему; общая формула транспорта не доказывает полный цикл хранения/отбора |

Приоритет: **ТЗ → применимые дополнения → эти принятые решения в пределах
разрешённых допущений → непротиворечивая логика reference → прежний код/планы**.
Дополнения поясняют ТЗ, не отменяют его обязательные функции. Упоминание v5
в A4 не создаёт новую поставку: рабочий versioned каталог остаётся v4 с
187 identities/223 positions. Counts21/24 и отсутствие БАС в capacity pool
сохраняются; расширение не является зависимостью ни одного этапа.

Нет организационных ожиданий ответов, подписи Жени или внешнего исследования
перед C01–C29. Тестовый gate может выявить дефект, а пользовательский расчёт
может вернуть missing inputs — это необходимые функции системы. Они не
останавливают разработку и не подменяются фиктивными ТТХ. Все отсутствующие
вендорские данные имеют определённый исход resolver: известный safe fact,
scenario input/assumption с отдельным статусом либо локальный неполный результат.

## 2. Реестр принятых решений K01–K29

| ID | Решение для реализации | Основание и цена решения | Проверка |
|---|---|---|---|
| K01 | Создать registry из всех R02/R06 entries со стабильными semantic IDs; происхождение каждого поля и supersession explicit. Счётчики заголовков 70/85 не являются validation schema. | T3/T5; отсутствующий файл не мешает восстановить описанные значения. | Полное source coverage, unique IDs, no orphan coefficient. |
| K02 | Normalized exchange — total seconds; raw load+unload имеет приоритет. Legacy45 per operation мигрируется в total90 только в provenance-known legacy path; новое total45 остаётся 45. Speed: USER operating≤safe max; иначе safe operating fact; иначе safe max как раскрытый optimistic proxy без дополнительного коэффициента. | R03/R08 и T3. Разные semantics получают разные trace nodes; proxy не обещает deployment speed. | total45→cycle с 45; split45+45→90; old45→90; wrong/unsafe speed не используется. |
| K03 | Для boxes предел массы=floor(payload/item_mass); batch=min(предел массы, explicit user handling limit, safe passport batch, геометрический limit), отсутствующие дополнительные ограничения не входят в min и отмечаются unknown. Остальные единицы batch1, кроме явно введённого физического batch. | T3 разрешает overrides; нельзя нарушить массу. Без geometry вывод предварительный, не packing proof. | payload10/item3→3; handling2→2; mass0 недопустима для деления; override>masscap rejected. |
| K04 | Demand>0 у активного процесса; inactive→N0/N_A. Fleet0 допустим what-if: capacity0,coverage0,utilization null,OVERLOADED. При capacity>0 сохранять raw load ratio и clamp utilization≤1; ни coverage, ни utilization не равны SLA. | R11 validation и T2/T3. Нулевой парк — осмысленный контрсценарий. | Нулевые знаменатели не дают NaN/Infinity; ceil boundaries. |
| K05 | Capacity рассчитывается независимо от зарплаты. Labour/finance требуют зарплату активной роли; no-role процесс имеет NO_FOT_BENEFIT. Tech/control без зарплаты дают INCOMPLETE для соответствующей статьи, не 0. Demo wages — отдельный явно принятый scenario input из официального dataset, не USER и не vendor fact. | T1/T3/T5; отделяем технический результат от неизвестной статьи труда. | Missing salary не уничтожает capacity и не делает finance COMPLETE. |
| K06 | applied=floor(robot_replacement×limit); demand_pult=max(floor(applied×share),shifts×min_per_shift); transferred=min(applied,demand_pult); released=applied−transferred; additional=demand_pult−transferred. | R03 текст о переводе из высвобожденных + conservation. Исправляет расхождение между текстом и формулой operators_from_released. | applied1,min2→transfer1,release0,extra1; applied10,share.25,min2→2/8/0. |
| K07 | Default unit_deficit_cost=annual_direct как видимое scenario assumption, пользователь 0 отключает. Deficit benefit отдельной строкой от savings; remaining_deficit_t=max(0,deficit−floor(growth×ramp_t)); annual cost indexed8%. | Явная замена R04 №57/R13 п.39; T3 требует измеримый и объяснимый эффект. | Нельзя одновременно считать одного человека released и growth; default/off traces отличаются. |
| K08 | Base equipment=input integer иначе ceil(role_drivers/shifts), иначе unknown. Withdrawal по роли=min(base,ceil(released_driver/shifts)); fallback=min(base,ceil(released×.30/shifts)). Если base unknown, equipment savings неизвестна, не размер всей fleet. | Ричтрак — актив, используется несколькими сменами; conservation важнее неоднозначного сокращения R03. | released4,shifts2,base3→withdraw2; withdrawal≤base. |
| K09 | Ramp из R02, с 6-го года 1. Годовой released=ceil(released_final×ramp), savings выводится из difference role ledger, не linear savings×ramp. Service после warranty масштабируется ramp один раз. Severance=положительный прирост released_t против t−1 × monthly×2.5 во все годы прироста. | T3/A1: временные потоки должны сходиться; изменяем правило «только первый год» явно. Остальные line-specific ramp сохранены. | released10,ramp.5/.85/1→5/9/10; severance на 5/4/1, не 5/9/10. |
| K10 | Повторные батареи по накопленным циклам с ramp: cumulative_cycles_t=Σannual_cycles×ramp_t; события, когда k×resource_cycles строго меньше cumulative до конца года. Exact crossing в конце horizon не покупает батарею без последующей работы. Cost=count_events×N×battery_price×hw×1.05^(t−1), без второго ramp. | TCO учитывает замены основных компонентов; ramp уже в износе. Новый explicit lifecycle policy, не vendor lifetime. | Несколько replacements в год допустимы; resource=100,cumulative250→2; exact terminal200→1. |
| K11 | Percent base=equipment only, depreciation=capital without reserve/5; reserve не актив. R03 life/liquidity для перечисленных classes; cleaner/неизвестный class без safe/user life → residual0 с conservative-assumption. Explicit validated residual curve имеет приоритет. | A1 разрешает единый выбранный метод; не придумываем asset lifetime. | residual не отрицателен, curve monotone0..1; no unknown lifetime→10 years. |
| K12 | Основной конкурсный результат — собственные средства, денежные потоки до налога на прибыль. Налоговые сценарии R13 — дополнительная иллюстративная модель с явными 25%/режимами, не юридическое обещание. Алгоритм ниже; внешний legal sign-off не prerequisite. | A1/T3 не требуют налоговой консультации или займа. Показываются operating effect, depreciation и accounting effect отдельно. | Основные результаты не зависят от неуказанного tax mode; tax supplement не изменяет их. |
| K13 | Primary simple payback — пересечение накопленного differential CF с учётом−CAPEX в t0; при постоянном CF совпадает с CAPEX/effect ТЗ. ROI=ΣdiffCF1..h/CAPEX; для RaaS denominator=TCO. CAPEX0 → payback0 лишь при неотрицательном потоке и положительном эффекте, иначе N_A; ROI denominator0→N_A. Нелогичный дополнительный profitability_TCO не публикуется. | T3 задаёт рекомендуемую, не единственную формулу PB; динамический CF учитывает ramp. Показываем отдельно net benefit after investment. | Constant10,CAPEX25→2.5; no crossing null; zero investment cases. |
| K14 | Piecewise linear interpolation по узлам R03. Payload margin выше.5 линейно падает до.5 при margin1; availability сохраняет немонотонные узлы R03 как model preference. N/A компоненты исключаются с перенормировкой весов; UNKNOWN=0 без перенормировки; no required integrations=1. | T2/T3 требуют объяснимость; сохраняем максимум описанного и задаём конечные точки. Отдельно подписать, что score не reliability probability. | Все knots, N/A vs UNKNOWN, weight sum, all-negative не favorable recommendation. |
| K15 | Checks имеют process/route/zone/time scope; clinic sterilization только при требуемом sanitization; этажи — реально пересекаемые маршрутом. Class-B требует cleaning/containment compatibility, не универсальную взрывозащиту. Airside — отдельное требование operational permission, не вымышленный «сертификат EASA/ICAO». | T2/A5: команда формирует контекстные ограничения; нормы не объявляются установленным законом. | Known FAIL исключает recommendation; UNKNOWN/ASSUMED только preliminary/needs validation. |
| K16 | Поля R08 — источник перечня:12critical+17important+7useful, полный вес 77. N/A исключается. Intake completeness отдельно: weights sum100; <40 basic,40≤x<70 working,≥70 high. Missing salary делает labour completeness0, capacity completeness считается по своим inputs. | T2/T3: не путать готовность формулы с completeness карточки. |77 full, allN/A=N_A;70 high; salary missing не ready economics. |
| K17 | Shared site CAPEX распределяется по прямому capital без shared/reserve; если сумма 0 — поровну между активными процессами, remainder по stable ID. Shared staff распределяется один раз по явным shares или required person-shifts, largest-remainder; правила cohort ниже. | Conservation R00/R13 и T3; деление на 0 закрыто, исходный персонал не копируется по блокам. | Σalloc=total до копейки; Σpeople=rolepool; reorder invariant. |
| K18 | Детерминированный event scheduler, FIFO, fixed calendar/measurement и SLA definitions из §4 ниже. Availability применяется один раз как service-time dilation; неизвестные failure rates/зарядные циклы не выдумываются. | T4/R12 требуют meaningful simulation, не откалиброванного digital twin. | Analytical no-congestion golden, bottleneck fixture,±10%boundary, same revision. |
| K19 | Role dictionary — union R11 схем 3 и 9/R10, role code scoped object; mapping28blocks закреплён §3. Unsupported physical operations получают REFERENCE_ONLY, generic user-configured cycle доступен как SCENARIO_ONLY. | T1/A6: глубину выбираем явно; все три объекта доступны, один full golden path. |28 rows, no missing enum/role, no silent portions→deliveries. |
| K20 | Основная денежная база — CASH_GROSS_RUB, цены organizer уже включают НДС (A4). Ставку не угадываем и НДС повторно не добавляем. NET_RUB — отдельный режим только при explicit rate/basis для каждой применимой строки; недостающий rate не мешает gross result. | Прямой приоритет A4 над reference «без НДС». VAT-neutrality и вычет не обещаются. | Raw price сохранён; gross не делится на 1.2/1.22; нельзя суммировать net и gross без conversion. |
| K21 | RaaS .02/month как scenario tariff; contract horizon=h, renewal автоматически до h на тех же условиях, buyout0/off; phased/all_fleet по R03. Responsibility tableR02 сохраняется как model assumption. Payment отдельной строкой и один раз входит total OPEX/CF/TCO. | A1/A5 явно поручают модель RaaS команде; это не oferta vendor. | sum operating=service subtotal+payment; no doublepayment; term covers horizon. |
| K22 | Capacity=ceil((daily/H)×1.25×(1+reserve)/(nominal×availability)); extra target utilization multiplier отсутствует. Formula trace показывает все три понятия ТЗ: пик, availability и reserve. | T3 dependency рекомендательная; R03 даёт определённую прозрачную реализацию. | Baseline syntheticN18; reserve/availability не повторяются. |
| K23 | Общий transport route — USER input. Для demowarehouse120m — видимый scenario assumption из R09,25m остаётся picking distance. Defaults разрешены только с explicit source/priority; никакого скрытого sourcefact. | T5 и R09 позволяют такой резерв; конфликт mandatory решён разделением demo и custom input. | Custom missingL→field error; demoL120→assumption trace. |
| K24 | Порядок DAG: input→constraints→capacity→labour→cost/CF→allocation→NPV→score. Предварительная техническая сортировка называется отдельно. | Зависимости самой формулы Score; T2/T3. | Score не исполняется до candidate CF; frozen cohort ID. |
| K25 | CostBasis union FIXED_TOTAL/PER_ROBOT/PERCENT_BASE, ровно один вариант/line. Spares по умолчанию разовый CAPEX; recurring supplies отдельная line, не дубль. Service fixedannual приоритетнее percent только если legacy source содержит оба; для нового input оба запрещены. | A1/A5 позволяют определить статьи; размерности R08/R03 становятся совместимыми. | Different bases normalize sameamount; fixed repair не×N повторно; doublebasis rejected. |
| K26 | Active-block объём required, inactiveblock неошибка. Automatic object requirements — policy-derived, не доказанные capabilities робота. Обязательные поля не заполняются hiddendefaults; optionaldefault сохраняет trace без interrupt. | T2 и R10 четыре приоритета. | No mandatory default leakage; overrides versioned. |
| K27 | Хранить 1.090/1.55/1.302 как принятые exactdecimal assumptions; пояснения≈, не альтернативные вычисления. Rotation промежуточно не округлять:1.4×1.090×1.25=1.9075. Human cleaning300m²/h относится к механизированному baseline; ручной baseline требует user rate. | T3/T5, R09 предупреждает неверный manual benchmark. |14×1.9075→ceil27; raw manual не получает 300 автоматически. |
| K28 | Supersession: R04 D9 и замены 51/58/64/66, R07§72 вытесняют ранние inconsistent строки. Архивные документы не правятся, registry хранит replaced_by. | R00 versioning и явные исправления; T3 воспроизводимость. | Нельзя одновременно применять старый penalty и новый component. |
| K29 | Default10picks/min/800m²/h/2yr/MTBF никогда не заполняют vendor fact. Safe mandatory fact отсутствует→модель вне соответствующего vendor calculation profile; параметры generic scenario вводятся отдельно с explicit assumptions. Research улучшает data позже, но не блокирует merge. | T2/A2/A5 и сохранение evidence gates. | Synthetic scenarios не входят в 187/223 или 21/24; no automatic admission. |

Все K01–K29 приняты. Вопросы Q01–Q12 закрыты для разработки этими решениями
и следующими разделами. Проверка с Женей после внедрения — review backlog,
не dependency или acceptance signature.

## 3. Границы процесса и роли: готовый process catalog

Полный обязательный golden path — warehouse receiving/shipping, с отдельным cleaning capacity сценарием,
с source-safe выбранной моделью, purchase/RaaS, sensitivity,2D, сохранением
и экспортом. C09 реализует fixed-cell формулы на synthetic fixtures; реальная
модель не появляется в pool без facts. Airport/clinic имеют все формы,
discovery/constraints и transport/cleaning scenario calculations при вводе
batch/route. Не обещаются автономная заправка, лечение, airside deployment,
полный ASRS/picking motion или управление настоящим оборудованием.

| C10 row | Code | Роль по умолчанию для предложения UI | Расчётный scope |
|---|---|---|---|
|01|warehouse_receiving_shipping|forklift_driver, loader|TRANSPORT_CYCLE; отдельные inbound/outbound, daily суммируется только для общей fleet |
|02|warehouse_storage|storekeeper|Только напольный transport; полный vertical storage REFERENCE_ONLY |
|03|warehouse_picking|picker, sorter|Транспортная подоперация отдельно; полный picking REFERENCE_ONLY |
|04|warehouse_palletizing|packer|FIXED_CELL; упаковка вне формулы |
|05|warehouse_cleaning|cleaner|CLEANING_AREA |
|06|warehouse_inventory|inventory_worker|REFERENCE_ONLY; ввод/каталог/constraints |
|07|airport_baggage|baggage_handler|TRANSPORT_CYCLE; bags/cart capacity explicit |
|08|airport_catering|trolley_operator|TRANSPORT_CYCLE; boxes/cart или weight/cart explicit |
|09|airport_fuelling|special_equipment_driver|REFERENCE_ONLY |
|10|airport_internal_logistics|trolley_operator|TRANSPORT_CYCLE |
|11|airport_terminal_cleaning|terminal_cleaner|CLEANING_AREA |
|12|airport_apron_cleaning|perron_cleaner|CLEANING_AREA; только подходящие outdoor facts/requirements |
|13|airport_waste|trolley_operator|TRANSPORT_CYCLE; kg/bin explicit |
|14|airport_inspection|runway_inspector, security_guard|REFERENCE_ONLY; БАС вне pool |
|15|airport_passenger_assistance|passenger_assistant, courier|REFERENCE_ONLY |
|16|airport_ground_service|ramp_worker, ground_support_worker|REFERENCE_ONLY; transport suboperation может быть отдельным процессом |
|17|clinic_food|catering_worker|DELIVERY_CYCLE; portions/cart explicit |
|18|clinic_linen|laundry_worker|DELIVERY_CYCLE; clean/dirty отдельные потоки,kg/container |
|19|clinic_medicines|sanitary, porter|DELIVERY_CYCLE; deliveries/day либо items/container |
|20|clinic_biomaterials|lab_assistant|DELIVERY_CYCLE; samples/container explicit |
|21|clinic_sterile_sets|sterile_supply_worker|DELIVERY_CYCLE; sets/container explicit |
|22|clinic_consumables|consumable_worker|DELIVERY_CYCLE; explicit batch |
|23|clinic_waste_a|sanitary, porter|DELIVERY_CYCLE; kg/container |
|24|clinic_waste_b|sanitary, porter|DELIVERY_CYCLE плюс containment/sanitization checks |
|25|clinic_results|lab_result_courier|Физические доставки DELIVERY_CYCLE; digital flow N_A |
|26|clinic_cleaning|cleaner|CLEANING_AREA |
|27|clinic_inventory|inventory_worker|REFERENCE_ONLY |
|28|clinic_safety_requirements|none|CONSTRAINT_ONLY, не независимый fleet |

Коды ролей R11 не считать уникальными across objects: общий `cleaner`
scoped объектом, `tech_support` и `control_operator` — site operating roles.
Строка таблицы предлагает role, но не назначает автоматически весь штат этой
роли процессу. Пользователь может поменять mapping с trace; unknowncode
отвергается, новое custom label использует existing role ID+label, не keywords.

Batch conversion: demand trips/day=ceil(raw demand/items_per_container),
без fractional trip. Для mass: container capacity≤robot payload и user tare
вычитается из payload; если tare неизвестна, показывать assumption tare0
только в explicit scenario, cargo fit UNKNOWN. Для mixed dimensions требуется
явный conversion, например kg/portion; ни 120kg, ни 55kg не определяют число порций.
No-role costs baseline может содержать явно введённые current operating costs;
экономия труда в таком случае N_A, а не весь object FOT.

Для REFERENCE_ONLY можно добавить generic scenario `USER_CYCLE`:
cycle_s пользовательский total, units_per_cycle пользовательские,
q=3600×units/cycle, N=ceil(required/(q×availability)). Это не профиль
подтверждённой производительности конкретного SKU. Реализация такого
parameterized calculator входит C10; product не выдумывает заправочный
или инспекционный алгоритм. Нет обязательства заполнить его за пользователя.

## 4. Полностью определённая simulation/SLA policy

Event model `deterministic-queue-v1`; единица времени integer microseconds,
входные секунды округляются один раз half-even доµs. Очередь FIFO;
sort key `(time,event_priority,process_id,resource_id,job_seq)`; завершение
работы раньше следующего arrival на той же отметке. Работа вне calendar windows приостанавливается и продолжается в следующем
окне; остаток service time и очередь сохраняются. Dispatch выбирает
свободного робота с минимальным ID, route tie — stable edge IDs.

- Default workday starts00:00, shifts contiguous, H≤24; per-process calendar
  может задаваться явно. Schedule repeats daily; timezone snapshot explicit.
- Batch jobs целые, `jobs_day=ceil(daily_units/batch)`; последнее задание
  несёт остаток demand. Default arrivals равномерны по рабочему окну:
  release_j=window_start+j×H/jobs_day, j=0..jobs_day−1. Это assumption
  UNIFORM_ARRIVALS, не наблюдаемый реальный график.
- Проводить два отчёта: DAILY при фактическом demand и PEAK_STRESS при
  demand×peak. Peak reserve используется только для capacity sizing и stress;
  daily salary/energy demand не увеличивается автоматически.
- Nominal service time — cycle transport/cell или microtask area/rate cleaning.
  Effective service time=nominal/availability. Разница — агрегированный
  NONPRODUCTIVE_ALLOWANCE; не накладывать поверх неё случайные поломки,
  charging delays или ещё один коэффициент availability.
- Для route/resource bottleneck включён explicit ресурс: segments с заданной
  пропускной способностью, loading station slots, elevator service time.
  Неизвестные lifts/chargers не получают скрытого времени: bottleneck verdict
  CONDITIONAL_MODEL с перечислением неучтённого; nominal/no-contention run исполним.
  При отсутствии графа маршрут — synthetic corridor длины L, без inferred turns.
- Задание проходит последовательность load → outbound edges → unload → return
  edges → nonproductive allowance; робот занят до конца этой последовательности.
  На каждом шаге захватывается только один ресурс, освобождаемый перед следующим;
  capacity ресурса — целое ≥1, локальная очередь FIFO. Это предотвращает deadlock
  модели, но не доказывает отсутствие дорожного deadlock настоящей техники.
  Маршрут выбирается по минимальной сумме длин; равенство разрешается по edge IDs.
  Длины графа заменяют synthetic L с новым trace/revision, не добавляются к 2L.
  Lift service — отдельное явно заданное время, вместо travel соответствующего
  lift edge. При заданном только total exchange его деление пополам между load
  и unload — раскрытая simulation assumption; analytical total сохраняется.
  Allowance=сумма nominal stage times×(1/availability−1); ожидание ресурсов
  добавляется отдельно и не масштабируется availability повторно.
- Для cleaning simulation microtask=100m² по явной настройке
  `SIMULATION_AREA_BATCH`, последняя задача содержит остаток; service=area/rate.
  Это дискретизация модели, не ТТХ. Для fixed cell task=одна output pallet,
  service берётся из F06, включая cell_eff ровно один раз. Параметризация batch
  сохраняется в ScenarioSpec и не изменяется при ускорении воспроизведения.
- Зарядные точки визуализируются из spec. При неизвестном physical charge
  cycle UI показывает «в составе агрегированного простоя», не fake battery%.
  Полная battery/charge simulation не входит v1; refinement после конкурса.
- Warm-up=один полный календарный день, measurement=следующий полный день;
  измеряются arrivals measurement cohort и их completion/deadline. Перенос
  начальной очереди сохраняется. Для перегрузки warm-up не объявляется steady state.
  Завершения после measurement для SLA отслеживаются до следующего рабочего
  дня, незавершённые jobs получают censored/missed, а не исчезают из denominator.
- Throughput=завершённые units в measurement work windows / H; required=daily/H.
  Service capacity probe: saturated queue отдельно, denominator theoretical
  fleet_effective_capacity. Deviation=abs(observed−expected)/expected×100%;
  строго>10% warning. Expected0/observed0→N_A, expected0/observed>0→INPUT_MISMATCH.
- Utilization busy/worktime и productive nominal/worktime — разные поля;
  queue wait=service_start−release; turnaround=completion−release.
  SLA input minutes>0; on_time=jobs(completed_by_deadline)/measurement_jobs,
  deadline=release+SLA. Target default100%; mean и p95 (nearest-rank) отдельно.
  Не заданы SLA или resource requirements — SLA N_A/CONDITIONAL, не PASS.
- Seed42 зафиксирован, v1 без random distributions. Visualization speed не
  меняет event ordering/числа. Scenario/geometry changes создают новую revision.
- Статусы report: CONSISTENT/DEVIATION/OVERLOADED/CONDITIONAL_MODEL/NOT_EVALUATED;
  они не называются инженерной верификацией. CFD/physics/FAT/SAT не обещаются.

Performance fixture:10 processes,100 robots,≤10 000 jobs/day,3 calendar days,
≤100route nodes,≤500edges,4vCPU/8GiB,CPU only. Economy≤10s, simulation≤60s;
progress каждую 1s или batch1 000events, cancel проверяется на каждой пачке.
За лимитами — явный LIMIT_EXCEEDED с сохранением проекта; не снижать silently
число jobs и не заявлять проверенным больший масштаб. Реализация может
обрабатывать больше, но конкурсный acceptance benchmark фиксирован.

## 5. Точность, финансы и shared allocation

Для исторического Q4 из docs/11 сохраняется enum docs/09: resolver выбирает
первое применимое состояние в порядке DISCONTINUED (явное снятие), SUPPLY_RISK
(известное препятствие нужной поставке), CONFIRMED_AVAILABLE (совпадающая
комплектация/условия и действующее подтверждение), QUOTE_REQUIRED (известен
канал, требуется предложение), LIKELY_AVAILABLE (есть подтверждённый канал,
нет подтверждения заказа), UNVERIFIED (иначе). Все основания сохраняются,
а не только победившее. Срок действия берётся из источника; без него нельзя
автоматически выдать CONFIRMED_AVAILABLE. Supply risk — отдельный
LOW/MEDIUM/HIGH/UNKNOWN по явным source/user оценкам; неизвестные dimensions
сохраняются UNKNOWN. Нет искусственного score 90/70 и автоматического LOW
из отсутствия плохих новостей. C13 фиксирует этот контракт; procurement не
становится условием получения предварительного capacity/economics результата.

Дополнение к K20: raw `currency=UNKNOWN` у organizer price сохраняется.
Для demo используется `currency_assumption=RUB` из явно выбранной конкурсной
policy; resolved money получает provenance ASSUMPTION, а не VERIFIED_RUB.
Для custom проекта неизвестная валюта требует ввода валюты/бюджета; это
не влияет на исполнение автоматического demo. Исходный каталог не изменяется.

Дополнение к K06/K09: годовой staffing ledger сохраняет
`released_t=ceil(released_final×ramp_t)` как источник savings. Затем
`remaining_role_t=base_role−released_t`; пульт обслуживается из оставшихся
eligible людей до принятого site minimum/share, недостающее — additional
operators в OPEX. Переведённый человек остаётся в remaining FOT, а не в двух
расходных строках. Ограничение замены применяется к числу уволенных/заменённых
людей, не исключает временный перевод оставшихся в первый год ramp.
Ни отдельное `ceil(applied×ramp)`, ни `ceil(transferred×ramp)` не создают
вторую несовместимую численность. При fleet0 операторы/tech0.

Decimal context28; raw values decimal strings, units explicit; internal CF
без display rounding. Целые people/fleet/chargers только описанными ceil/floor.
Money output2 decimals HALF_EVEN, percent/score2, payback2, intermediate trace
полная precision. Σdisplayed financial lines сверяется с displayed total:
расхождение округлений показывать отдельной строкой, не терять копейки.
Численный tolerance тестов exact Decimal для money/internal,1µs для event;
score normalized допускает≤0.000001 до display. Никаких произвольных epsilon
у ceil. Domain:shifts1..3;shift_hours6/8/10/11/12;days1..366;horizon5..15;
discount0..1;share0..1;availability>0..1;salary≥0 explicit,0 требует
`ZERO_COST_ROLE` marker и не даёт экономии. Negative prices/volumes rejected.

Tax supplement: mode NONE (основной), ILLUSTRATIVE_OTHER_INCOME,
ILLUSTRATIVE_NO_OTHER_INCOME. Для other_income tax=.25×EBIT, включая отрицательный;
для no_other_income: losses FIFO, срок 10 лет model policy; при EBIT>0 deduct
min(lossstock,.5×EBIT), tax=.25×(EBIT−deduct); при EBIT<0 налог 0, убыток
добавляется. Это явно параметры иллюстрации R03, не утверждение о действующем
НК. Tax supplement по gross суммам маркируется simplified non-tax-accounting
base; для точной налоговой базы нужен отдельный future verified financeprofile.
Default cash flow CF=EBITDA−battery+residual−severance; supplement вычитает tax.
Depreciation только accounting effect/EBIT; второй cashout запрещён.

Рекомендация по finances использует cashflow primary, NPV проекта и риски,
а не один payback. Scenario assumptions позволяют conditional recommendation,
но неизвестная обязательная costline делает INCOMPLETE и исключает безусловную положительную рекомендацию.
Для неизменного annual effect дополнительно показать simple reference ratio
CAPEX/annual effect с отдельным названием; основной payback остаётся CF crossing.

Shared roles: сначала compute required person-shifts perprocess; явные shares
имеют приоритет, sum≤1, остаток людей stays unallocated baseline. Без shares
веса=person_shifts процесса среди процессов той роли, zero sum→equal;
allocate integerpool largest-remainder, tie processID. После allocation
labour→finance; не переносить employees между ролями без explicit mapping.
Pult общий по site: requirement=max(sum(floor(applied_i×share)),
simultaneous_shifts×min_pult), затем transfer из eligible role pools по stableID;
salaryTransferred остаётся зарплатой исходной роли, extraoperators по controlsalary.
Нет overlaps calendars → default contiguous shifts из§4, staffing shift count
max active shifts, не сумма смен процессов. Общие tech считаются от sumfleet. При N=0 control/tech requirement0,
минимум пульта не создаёт людей без работающего парка.

Ranking без цикла: прямые candidate costs→technical ordered anchor configuration
(первый допустимый modelID/positionID в стабильном порядке)→фиксированные allocation weights
anchor→NPV всех кандидатов при этих весах→score. Cohort,anchor,weights сохраняются.
После выбора пользователя combinedledger пересчитывается фактически; independent
candidate scores не являются математическим обещанием глобального optimum.
Re-ranking — explicit newrun, не итерация до «сходимости». SiteCAPEX0→equalallocation.
Общая стоимость infrastructure — явный siteinput, не max разных предложений модели.

## 6. Данные и демонстрация без внешнего ожидания

Проверка локальных данных при редакции 1.1: существует concrete candidate MULE,
model `ecd7d582-b342-449a-b43b-66288d159a32`, price offer
`price-v4-row-0020`, amount3000000.00 с raw currencyUNKNOWN.
Enrichment содержит matching-safe payload1500kg и max_speed1.3m/s;
WMS/navigation также заданы. Он пригоден для capacity golden при 800kg,
при этом недоказанные deployment constraints остаются UNKNOWN.
При L120m, exchange total90s, 2000 pallets/day и 22h/day cycle равен
274.615384615…s; ожидаемый парк PESSIMISTIC/BASE/OPTIMISTIC — 20/15/13.
Это отдельный golden от примера R03 с operating speed1m/s и парком18.
Для baseline fixture закрепить именно эту identity/position; универсальный
selection тест отдельно проверяет deterministic sorting и hard exclusions.
Его suitability не переопределяется синтетическим бюджетом.

RoboCV тоже имеет safe payload/speed, но aisle2.9m не проходит рабочий
warehouse aisle2.8m; он используется как hard-rejection fixture. Эти наблюдения
получены из committed bundle, не создают новый vendor evidence и не меняют pool.

C02/C06/C13 используют committed bundle и scenario inputs. Live vendor,
коммерческий ответ и registry от Жени не являются prerequisites. Research
возможен после реализации отдельным data update. Discovery187/223 и pool21/24
не меняются; generic fixtures не становятся catalog positions.

Полный автоматический golden path задан следующей политикой:

1. Официальный warehouse:2000 pallets/day,2×11h,365 days,25forklift drivers,
   salary120000RUB/month из R05 как `DEMO_ASSUMPTION_FROM_DATASET`.
   L120m — explicit assumption R09; не picking25m. Общий штат 180 не назначается
   транспортному процессу целиком. Custom project требует собственную зарплату.
2. MULE из текущего transport pool с payload≥800kg и organizer price закреплён
   для baseline fixture; общий подбор сортируется по modelID/positionID.
   Known hard FAIL исключает; UNKNOWN оставляет
   conditional assessment. Полный proof всех deployment constraints не
   требуется для численного предварительного расчёта.
3. В автоматическом тесте применяется `synthetic-commercial-budget-v1` ниже.
   Эти значения — данные теста/пример пользовательского бюджета, не оценки
   рынка, не источник ТТХ и не незаметные defaults custom проекта. Роботная
   цена сохраняется из исходной organizer position с НДС. Операционный бюджет
   не редактирует factual catalog и не даёт procurement/deployment-ready.

| Fixture input | Значение | Семантика |
|---|---|---|
| robot purchase price | exact selected organizer position amount | FILE amount, POLICY tax basis, ASSUMPTION currency; исходная row identity |
| charger ratio / charger budget |0.25 /100000 RUB each| SYNTHETIC_SCENARIO_INPUT, не карточка vendor |
| integration per robot / site infrastructure |100000 /500000 RUB| Синтетический бюджет подключения и инфраструктуры |
| delivery / commissioning / training |100000 /100000 /50000 RUB total| Отдельные FIXED_TOTAL lines; A4 не включает их в hardware price |
| annual service / annual software |50000 /10000 RUB per robot| Синтетические расходы для теста |
| working power / autonomy / battery cycles / battery budget |500W /8h /1000 cycles /100000RUB| Сценарные входы energy/wear, не vendor facts |
| warranty |0 years| Консервативно не считать бесплатный сервис; assumption |
| tech / extra control salaries |100000 /100000 RUB monthly gross| Синтетический пользовательский бюджет, не региональная статистика |
| explicit Wi-Fi/ERP/floor/fleet licence/spares |0, `EXCLUDED_BY_SCENARIO`| В тестовом контексте расходы не включены; если понадобятся, пересчёт |
| other R02 policies |tariff8,efficiency.85,comm500; insurance1%/consumables2%/repair1%; discount.15| Versioned assumptions reference |
| horizon / acquisition / uncertainty |5 years; purchase+RaaS; все 3 scenarios| Сопоставление на одинаковой базе |

0 EXCLUDED не означает неизвестную бесплатную vendor услугу. Если реальному
проекту нужна исключённая статья, обязательность определяется requirements,
её UNKNOWN делает finance INCOMPLETE. Test scenario требует точное перечисление
границ, а не безусловный favorable recommendation. Procurement остаётся UNKNOWN.
Синтетический бюджет показывается отдельным явным выбором «Пример бюджета»;
он не заменяет реальные цены в каталоге и не назначается обычному проекту.
Маркеры `SYNTHETIC_SCENARIO_INPUT` и `DEMO_ASSUMPTION_FROM_DATASET` являются
подтипами/причинами provenance ASSUMPTION, а не новыми классами vendor facts.

C13 генерирует immutable fixture по этой таблице; C16/C17 независимо проверяют
полный ledger и R13 reconciliation. Для cleaning и fixed-cell используются
отдельные synthetic input fixtures с их quantity kinds; main contest full flow
достаточно транспортного warehouse, а cleaning capacity проверяется отдельно.
Если runtime pool не имеет fully evidenced deployment model, это ожидаемый
conditional результат, а не повод выдумать такую модель. Missing inputs,
unknown quote и hard failure имеют отдельные успешные негативные тесты.

## 7. Закрытие вопросов, этапов и поздний review

| Q | Закрытое решение | Runtime outcome при недостаточном пользовательском вводе |
|---|---|---|
| Q01 | K01, registry создаётся нами | Нет dependency на внешний registry |
| Q02 | K04/K13/K16/K27 и§5 | Валидация полей/N_A вместо ожидания policy |
| Q03 | K19 и 28 строк §3 | Определённый scope каждого процесса |
| Q04 | K02/K03/K23 и batch §3 | Missing input с перечнем нужных преобразований единиц |
| Q05 | K29/§6; текущий pool фиксирован | Missing safe fact локально исключает SKU/profile |
| Q06 | K06–08/K27/§5 | Labour INCOMPLETE при недостающей зарплате/ставке |
| Q07 | K12/K20/K21/K25 | Gross budget работает без ставки НДС и vendor quote |
| Q08 | K18/§4 | Определённые scheduler/SLA/conditional statuses |
| Q09 | K19/§3 | REFERENCE_ONLY/CONSTRAINT_ONLY — принятые product scopes |
| Q10 | K09–11/§5 | Повторные циклы, ramp и неизвестный residual определены |
| Q11 | K14/K16 | Все scoring curves/denominators определены |
| Q12 | K17/§5 | Allocation и cohort имеют конечный алгоритм |

C01–C29 сохраняют ветки. Их gates проверяют принятые решения, а не ответы
владельцев. C10.01–28 — independently tested mappings/scopes; REFERENCE_ONLY
завершается после form/catalog/reason tests и не называется готовой физической
формулой. C29 требует warehouse full flow, минимум для трёх объектов,
trace/versions/security, обязательную 2D и exports. Новые process algorithms,
реальные налоговые/коммерческие/санитарные проверки и review с Женей идут
после C29 и не влияют на его acceptance.

Если при реализации обнаружится ещё одна техническая неоднозначность,
исполнитель принимает решение в рамках ТЗ и этого scope, записывает основание,
новую версию затронутой policy и проверяемый пример в том же этапе. Ожидание
внешнего ответа не добавляется. При отсутствии доказанного свойства выбирается
явный scenario input либо предусмотренный неполный результат; evidence gates,
tenant isolation и неизменность старых runs сохраняются. Новая физическая
область и расширение catalog pool остаются отдельным последующим объёмом работ.

Замены бывших внешних зависимостей:

- Решение Жени → конкретный принятый K и его проверяемый пример.
- Получение vendor fact → safe resolver, missing-data outcome и негативный тест.
- Недостающая физическая формула → принятый scope либо USER_CYCLE с явными inputs.
- Legal review → основной pretax расчёт и обозначенный model tax supplement.

Агент исправляет ошибки тестов и нарушения evidence; эти gates не отменяются.
C27/C28 включают disposable DB rehearsal и local dual-run с rollback.
Production runtime activation не выполняется в этой документационной сессии.
При реализации релиз производится в уже авторизованной среде; отсутствие
внешнего стенда не мешает проверяемому Docker local release. Изменение pool
membership исключено из этапов, поэтому отдельное согласование новых counts
не является скрытой зависимостью плана.
