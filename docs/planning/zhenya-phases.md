# Исполнительные карточки внедрения расчётной логики

План от 2026-09-19, baseline `f77c32c2fde86cd1450aa96d43dc6273059c57d4`.
Родительский документ: [план 19](../19_ZHENYA_CALCULATION_IMPLEMENTATION_PLAN.md).
Rxx/Fxx/Gxx/Kxx/Qxx определены в нём. Новые пути ниже — предложения для
реализации, не утверждение о существующих файлах. Все Cxx пока **PLANNED**.

Общие gates каждого этапа: strict contracts, no unsafe vendor facts,
tenant/owner predicates, immutable old runs, deterministic results,
документированный rollback, отсутствие скрытой арифметики во frontend.
Unit/integration/frontend/golden проверки запускаются только для затронутого
слоя; «frontend — нет» означает отсутствие UI-изменений в данном PR.
Изменение schema не разрешает активировать runtime или менять pool.

## C01 — `contracts/calculation-semantics-v1`

- **Цель / источники:** устранить блокирующую неоднозначность до первой формулы;
  R00, R02–04, R08, R10–13. Закрыть semantics часть K02–04/K19 и Q02–04;
  остальные вопросы имеют owner и блокируемую ветку, а не произвольный default.
- **Модули / backend:** проектные schemas в `contracts/` и DTO specifications
  для `backend/models.py`; в этом этапе только контрактные определения,
  без исполнения формул, endpoint переключений и изменения legacy DTO.
- **Контракты / API:** `NormalizedProcess`, `Quantity`, `RolePool`,
  `CapacityResult`, `FinancialResult`, `CalculationTrace`, VersionBindings,
  независимые statuses; семантика partial results и compatibility v1→v2.
- **Frontend:** согласованный presentation contract ошибок/partial; код UI не меняется.
- **Данные / migration:** source-to-parameter map, decision records,
  proposed registry schema, precision policy; production bundle неизменен.
- **Observability / trace:** required DAG fields, единицы, rejection trace,
  content digest/order, redaction; fixture с USER/VENDOR_FACT/ASSUMPTION.
- **Тесты:** schema positive/negative, extra fields, unknown versions,
  units/kinds, null blocked result, forbidden fact statuses; integration —
  Python/JS serialization examples; golden — schema fixtures, не vendor cards.
- **Acceptance / зависимости:** все inputs F01–07 имеют тип/семантику;
  API capacity не требует economics; K02/03/04 либо решены, либо конкретные
  профили закрыты от исполнения. Нет неявных defaults. Вход — этот аудит.
- **Вне этапа:** численные формулы, runtime activation, изменение counts,
  закупочное исследование, salary benchmarks, полноценная simulation schema.

## C02 — `data/calculation-parameter-registry-v1`

- **Цель / источники:** materialize R02/R06 assumptions и R04 decisions с R00 provenance.
- **Backend:** новый `backend/calculation/registry.py`: loader/validator,
  без вычислений, без чтения ignored reference в runtime.
- **Контракты / API:** versioned registry schema, parameter ID/unit/domain,
  scope/scenario/overrideability, source digest/status, effective version;
  публичные endpoints пока без изменений.
- **Frontend:** нет; labels/localization keys в contract metadata.
- **Данные:** новый immutable `data/calculation/registry-v1.json` и manifest;
  constants с unresolved policy не разрешены как executable default.
- **Trace:** каждый использованный коэффициент ссылается на registry entry;
  различить unit definition, assumption и verified commercial fact.
- **Тесты:** schema/domain/hash, repeated load/idempotency, полный scenario
  table, no salary default, no duplicate/orphan IDs,75/77 conflict не скрыт.
  Golden — registry snapshot; frontend — нет.
- **Acceptance / зависимости:** C01; traceable values для всех поддержанных
  формул, sources совпадают с manifest; K01 принят. Ни одного bare magic number.
- **Вне этапа:** vendor enrichment, новые fleet rows, формулы, UI.

## C03 — `intake/process-role-normalization-v2`

- **Цель / источники:** R05/R10/R11 семантика объектов, ролей, quantities;
  зарплата по роли USER/FILE monthly gross, сохранение raw provenance.
- **Backend:** `object_profiles.py`, `project_file_intake.py`, `auditor.py`,
  новые `backend/calculation/intake.py` и `units.py`; v1 import adapter сохраняется.
- **Контракты / API:** versioned normalization/validation response и новый
  intake request; API не вычисляет capacity/finance, LLM извлекает raw input.
  Unknown extra fields запрещены; process/block identity не теряется.
- **Frontend:** нет; ответ содержит field errors, required inputs и units.
- **Данные:** versioned preset projection v2; исходные 42/39/57 profile parameters,
  source hashes и старые import runs сохраняются; salary preset не автоподтверждается.
- **Trace:** conversion nodes, file hash/sheet/row/cell, aliases и user confirmation.
- **Тесты:** unit conversions,28 block input roundtrip, union roles, H>24,
  no batches, salary missing, duplicate roles, invalid CSV/XLSX atomic rollback;
  API strict tests; golden warehouse/airport/clinic mappings; frontend — нет.
- **Acceptance / зависимости:** C01–02 и Q03/04 mappings; одинаковый смысл
  ручного/файлового/LLM ввода; portions≠deliveries; existing upload security сохранена.
- **Вне этапа:** расчёт N/NPV, UI, новый формат исходного organizer dataset.

## C04 — `frontend/process-role-intake-v2`

- **Цель / источники:** R10 формы, R11 activation/validation, R00 provenance.
- **Backend:** нет новой domain logic; исправления server contract отдельным PR.
- **Контракты / API:** использовать C03; input_revision, server-derived values,
  per-block status. Старый form/run presentation остаётся для v1 snapshots.
- **Frontend:** `ParamsPanel.jsx`, `ZonalPanel.jsx`, `App.jsx`; object→blocks→roles,
  подтверждение assumptions, no-role/no-FOT и missing salary объяснения.
  Удалить локальные ×15.624/обратные salary conversions только в v2 flow.
- **Данные:** никакой DB migration; draft UI имеет schema version, не меняет old run.
- **Trace:** раскрытие raw/source/normalized values, override event с input revision.
- **Тесты:** frontend activation каждой role, empty optional block, salary required,
  stale request, keyboard/accessibility, одинаковые displayed units; API mocked
  contracts + один integration intake path; golden — presentation fixture C03.
- **Acceptance / зависимости:** C03; клиент не рассчитывает стоимость труда,
  не подставляет зарплаты, не отправляет hidden normalized quantities.
- **Вне этапа:** financial dashboard, capacity algorithms, catalog filters redesign.

## C05 — `engine/applicability-constraints-v2`

- **Цель / источники:** R03 §5, R08 и R10 environment/process scope.
- **Backend:** `readiness.py`, новый `backend/calculation/constraints.py`;
  `economics.py:check_constraints` остаётся только legacy adapter до C28.
- **Контракты / API:** constraint report v2; per check applicability, units,
  PASS/FAIL/UNKNOWN/ASSUMED/N_A, evidence/reason; один report для исполнения.
- **Frontend:** нет; localization/reason codes контракта готовятся к C12.
- **Данные:** versioned constraint rules и applicable scopes; не «29» как магическая длина.
- **Trace:** обе стороны сравнения, normative/source policy version;
  исследовательски неподтверждённая норма не становится hardcoded law.
- **Тесты:** unit truth tables каждого check; budget/power/life warning без штрафа;
  unknown fact, airside, clinic waste, floors, temperature/noise scope;
  integration readiness=execution eligibility; golden constraint snapshots.
- **Acceptance / зависимости:** C01–03/K15; E и RD больше не расходятся в новом
  path. Необоснованный autonomy×.8 исключён из v2 с migration note.
- **Вне этапа:** score, deployment certification, formula execution, изменения v1.

## C06 — `catalog/formula-executability-audit-v3`

- **Цель / источники:** R03 formula dependencies + R08 evidence; проверить G37.
- **Backend:** `catalog_repository.py`, отдельный audit/resolver под
  `backend/calculation/`; безопасный DTO не требует legacy economics.
- **Контракты / API:** additive executability report v3 поверх readinessv 2:
  profile/version, available facts, unit/domain validation, required scenario
  inputs, assumptions, blockers. Catalog label и run executability разделены.
- **Frontend:** нет; C12 покажет различие.
- **Данные:** новый report для всех 187/223 и отдельный diff pool 21/24;
  не переписывать contractv 2/старый audit задним числом.
- **Trace:** fact/evidence binding, assumption scope, unsupported profile reason.
- **Тесты:** unsafe statuses, valid fact/wrong unit, unknown identity, exact sets,
  deterministic order, no BAS; integration DTO without Robot costs;
  golden fullaudit. Frontend — нет.
- **Acceptance / зависимости:** C02–03/C05; все inputs каждой разрешённой
  формулы закрываются facts или явно требуемыми scenario inputs.
  Любой count change отдельно согласован; иначе baseline unchanged.
- **Вне этапа:** source research completion, runtime activation, новые формулы.

## C07 — `engine/capacity-formula-trace`

- **Цель / источники:** R03 §1.1/1.4, R02 §3–5; подробный scope в плане 19 §7.1.
- **Backend:** `backend/calculation/capacity/transport.py`, quantities/resolver/trace.
  F01–04/F07, pure functions, без legacy Robot и коммерческих prerequisites.
- **Контракты / API:** исполнение CapacityResult/CalculationTrace C01;
  transport/delivery typed profile; endpoints ещё не переключаются.
- **Frontend:** нет.
- **Данные:** новые source/decision-bound goldens, registry version pinned;
  текущий pool не расширяется delivery synthetic fixture.
- **Trace:** total/split cycle, speed origin, batch, peak, availability,
  ceil N, selectedN и overload; всё воспроизводимо.
- **Тесты:** Golden-Transport-Synthetic, manual 17/18/19, boxfloor,
  ceil boundaries, total 45 vs 45+45, v0/H0/domain; properties monotonicity;
  integration resolver rejects unsafe facts; front — нет.
- **Acceptance / зависимости:** C06, K02–04; trace replay byte-stable и
  каждый numerical input имеет unit/provenance; no hidden.90 reserve.
- **Вне этапа:** cleaning/cell, finance, UI, activation, scheduling/SLA.

## C08 — `engine/cleaning-capacity-trace`

- **Цель / источники:** R03 §1.2/1.4, R02 defaults, R05 cleaning areas.
- **Backend:** `backend/calculation/capacity/cleaning.py`; F05/F07
  с m²/day и frequency; общий trace/runtime из C07.
- **Контракты / API:** CleaningProcess/CapacityResult; нет транспортного payload/batch.
- **Frontend:** нет; future unit labels m²/h/day определены контрактом.
- **Данные:** six-model profile audit version pinned; не приписывать cleaner autonomy/cost.
- **Trace:** area source, frequency, rate safe fact, H,availability,N.
- **Тесты:** area 0/negative,frequency 0/missing,H24,ceil andmanualfleet,
  no transportpeak; integration all 6 readycleaning DTOs; golden airport area derivation.
- **Acceptance / зависимости:** C06–07, zero policyC01; cleaning complete без
  финполя/зарплаты и без чужой единицы «паллеты».
- **Вне этапа:** manual cleaning labour, cleaning vendor research, UI, finance.

## C09 — `engine/palletizing-capacity-trace`

- **Цель / источники:** R03 §1.3, R02 cell efficiency, R05 boxes/pallet semantics.
- **Backend:** `backend/calculation/capacity/palletizing.py`, F06/F07.
- **Контракты / API:** explicit picks/min и output boxes/pallet; throughput
  с другим quantity kind не конвертируется автоматически.
- **Frontend:** нет.
- **Данные:** synthetic fixtures вне catalog, realmodels admission отдельным audit.
- **Trace:** picks→boxes→pallets, efficiency и availability отдельно.
- **Тесты:**20 output vs 33 receiving,0 denominator,rate unknown,manualN,
  unsupported fixed profile blocked; integration resolver; golden dimensional check.
- **Acceptance / зависимости:** C06–07/Q04, подтверждённый смысл rate;
  Python formula test не меняет нынешнее отсутствие cells в pool.
- **Вне этапа:** manipulator motion/safety simulation, новые vendor facts, economics.

## C10 — `contracts/process-profile-coverage-v1`

- **Цель / источники:** R10/R11 все 6+10+12 blocks; R03 имеет лишь несколько
  формульных семейств. Закрыть Q03/Q09 о полном обещанном объёме продукта.
- **Backend:** process router/registry binding к C07–09; явное
  `UNSUPPORTED_PROCESS_PROFILE` или `NOT_APPLICABLE` по смыслу блока.
- **Контракты / API:** complete process_catalog с role codes, quantity kind,
  has_fot_savings, formula profile/version, checks, missing inputs/policies.
- **Frontend:** нет; metadata используется C04/C12, отсутствие формулы видно.
- **Данные:** versioned 28-row map, без подмены process semantics generic transport.
- **Trace:** источник каждого mapping, required conversion/batch/route inputs.
- **Тесты:** exact 28 blocks, no-code collisions, no-role valid,
  safetyblock N/A не нулевой capacity, unsupported profile errors; golden mappings.
- **Acceptance / зависимости:** C03,C07–09; каждая строка classified и
  утверждён её продуктовый scope. Q09 закрыт перед заявлением full rollout.
- **Вне этапа:** изобретение недостающих функций, BAS admission, scope
  reduction без решения владельца. Если требуются новые алгоритмы,
  сначала Женя утверждает формулу/units/domains/examples, затем отдельный
  microstage из таблицы ниже. Blocked row не считается внедрённым процессом.

### Независимые process microstages C10.01–C10.28

Точные ветки для полного покрытия перечислены ниже. Это не 28 обязательных
новых алгоритмов: при применимости C07–09 PR содержит только проверенный
mapping/normalizer и golden, при отсутствии формулы он **блокируется Q09**.
Каждый microstage наследует контракты/API/data/trace/tests/gate C10, меняет
только свой process profile и adapter; backend module
`backend/calculation/process_profiles/<code>.py` создаётся только если нужна
отдельная нормализация. UI/economics/procurement в них не входят.
Приёмка каждого: raw official inputs → typed units → approved profile → trace,
plus negative missing conversion и все applicable constraints. Нормативные
claims должны иметь отдельный research gate. Новая fleet membership не входит.

| ID | Ветка | Блок R11 схема 4 / что мешает немедленному mapping |
|---|---|---|
| C10.01 | `profiles/warehouse-receiving-shipping-v1` | Приёмка/отгрузка; inbound/outbound flow и pallet route |
| C10.02 | `profiles/warehouse-storage-v1` | Размещение; vertical/lift cycle не задан транспортной формулой |
| C10.03 | `profiles/warehouse-picking-v1` | Отбор; order/line/box units и ручной/robot pick cycle |
| C10.04 | `profiles/warehouse-palletizing-v1` | Паллетизация/упаковка; C09 не описывает отдельный packaging cycle |
| C10.05 | `profiles/warehouse-cleaning-v1` | Уборка; C08 при корректной площади/частоте |
| C10.06 | `profiles/warehouse-inventory-v1` | Инвентаризация; scan quantity/rate, нет формулы |
| C10.07 | `profiles/airport-baggage-v1` | Багаж; carts/bags, batching и route scope |
| C10.08 | `profiles/airport-catering-v1` | Бортпитание; контейнеры/порции, airside и loading |
| C10.09 | `profiles/airport-fuelling-v1` | Заправка; rate/volume/safety, нет профильной формулы |
| C10.10 | `profiles/airport-internal-logistics-v1` | Внутрипортовая логистика; C07 после cargo/route mapping |
| C10.11 | `profiles/airport-terminal-cleaning-v1` | Уборка терминала; C08, derive 51 000m² явно |
| C10.12 | `profiles/airport-apron-cleaning-v1` | Уборка перрона; C08 только при применимом rate/outdoor facts |
| C10.13 | `profiles/airport-waste-v1` | Мусор; kg/container/trip и условия |
| C10.14 | `profiles/airport-inspection-v1` | Инспекция ВПП/перрона; scan coverage/rate, нет формулы, BAS не добавлять |
| C10.15 | `profiles/airport-passenger-assistance-v1` | Сопровождение; passenger service/SLA, нет полной формулы |
| C10.16 | `profiles/airport-ground-service-v1` | Наземное обслуживание; набор операций и cycle не задан |
| C10.17 | `profiles/clinic-food-v1` | Питание; portions→cart, SLA20 min |
| C10.18 | `profiles/clinic-linen-v1` | Бельё; clean/dirty flows,55 kgcontainer |
| C10.19 | `profiles/clinic-medicines-v1` | Медикаменты; batch, role и route mapping |
| C10.20 | `profiles/clinic-biomaterials-v1` | Биоматериалы; samples→container, SLA30 min |
| C10.21 | `profiles/clinic-sterile-sets-v1` | Наборы; containers/delivery и sterilization scope |
| C10.22 | `profiles/clinic-consumables-v1` | Расходники; batch/route, role mapping |
| C10.23 | `profiles/clinic-waste-a-v1` | ОтходыА; kg/container, sanitation |
| C10.24 | `profiles/clinic-waste-b-v1` | ОтходыБ; дополнительно K15, не взрывозащита по умолчанию |
| C10.25 | `profiles/clinic-results-v1` | Результаты анализов; physical/digital delivery distinction |
| C10.26 | `profiles/clinic-cleaning-v1` | Уборка; C08, noise/time/material scope |
| C10.27 | `profiles/clinic-inventory-v1` | Инвентаризация; scan throughput отсутствует |
| C10.28 | `profiles/clinic-safety-requirements-v1` | Требования безопасности; constraint profile, не fleet-sizing formula |

Наличие skeleton для 28 rows достаточно для API partial flow C11; обещанные
расчётные rows должны пройти свои microstage gates до C29. N/A safetyblock
может быть полностью внедрён без самостоятельного capacity output, если так
утверждено Q09. Неизвестная формула не становится N/A ради зелёной приёмки.

## C11 — `api/capacity-analysis-snapshots-v2`

- **Цель / источники:** R00 reproducibility и R03 capacity без вымышленной экономики.
- **Backend:** `main.py`, `catalog_repository.py`, persistence service/models,
  новый `backend/calculation/service.py`; CapacityRuntimeDTO direct consumption.
- **Контракты / API:** предлагается `POST /api/v2/capacity-analyses` и persisted
  run kind/schema; C01 фиксирует URL и error contract, `/api/calculate` сохраняется.
  Readiness/executability возвращаются из того же snapshot/revision.
- **Frontend:** нет, consumer в C12.
- **Данные:** additive schema/version fields для traces/bindings;
  миграция в disposable DB, old runs untouched; source published snapshot explicit.
- **DB invariants:** `persistence_models.py:AnalysisRun` сейчас требует economics
  version и ScenarioSpec для каждого SUCCEEDED. Добавить run kind и строгие
  payload/version checks по kind: для capacity обязательны input/result/trace
  и их hashes; требования старого full run сохраняются. Не делать все поля
  nullable общей миграцией и не записывать фиктивный ScenarioSpec (G57).
- **Trace:** run stores full normalized input + versions + trace, replay offline.
- **Тесты:** API schemas,503/no active capacity source, safe DTO without price,
  snapshot persistence,reopen, cross-user deny,CSRF, immutable content;
  golden JSON and trace; existing v1 endpoint regression.
- **Acceptance / зависимости:** C05–10; persisted capacity run не требует
  `RobotEconomics`/v1 ScenarioSpec; activation в этом PR не производится.
- **Вне этапа:** slot switch, UI, economics, role baseline calculations.

## C12 — `frontend/capacity-results-trace`

- **Цель / источники:** R00 assumptions и R03 selected/recommended fleet.
- **Backend:** нет; API C11 считается авторитетом чисел.
- **Контракты / API:** C11 result status/units/revision; no client fallback.
- **Frontend:** `App.jsx`, `dashboardModel.js`, result components;
  capacity pane, blockers/rejections, nominal/effective, coverage/overload,
  drilldown trace; unavailable economics не прячется за fictitious KPI.
- **Данные:** нет; сохранять v1 presentation для old runs.
- **Trace:** человекочитаемые steps с input sources; no display-only formula.
- **Тесты:** frontend complete/partial/blocked, manualfleet, missing economics,
  stale request; API integration read snapshot; golden presentation values.
- **Acceptance / зависимости:** C04,C11; same numbers/units in all panes;
  label «Участвует в расчёте» не равен SLA/deployment-ready.
- **Вне этапа:** ranking/economics, catalogue membership, simulation UI.

## C13 — `procurement/commercial-inputs-v1`

- **Цель / источники:** R00/R01/R08 commercial facts, R02 netRUB; docs 09 gates сохраняются.
- **Backend:** commercial resolver рядом с catalog repository; price/terms
  normalization, quote validity/scope, service responsibilities.
- **Контракты / API:** CommercialMoney(raw amount,currency,taxbasis,rate,date,
  source,scope), contract terms PURCHASE/RAAS; procurement report независимо
  от economics. USER scenario price допустима, но не vendor quote.
- **Frontend:** нет; формы коммерческих inputs в C21, API доступен для tests.
- **Данные:** additive versioned commercial inputs, organizer raw price intact;
  procurement research отдельно, недоказанные цены/availability blocked.
- **Trace:** raw→net normalization; rule/quote/evidence IDs; assumption override.
- **Тесты:** known/unknown VATrate, user net, wrong currency, stale quote,
  vendor identity mismatch, price 0 explicit semantics, ambiguoussource;
  API/golden commercial report; frontend — нет.
- **Acceptance / зависимости:** C01–03/K20; нет automatic VATdivision или
  обещания procurement-ready по capacity pool.
- **Вне этапа:** NPV, service cost defaults, реальное приобретение/отправка запросов.

## C14 — `engine/role-labor-baseline-v1`

- **Цель / источники:** R03 §2, R02/R06, R10–11; закрытые K05–08.
- **Backend:** `backend/calculation/labour.py`; F08–15, role baseline,
  replacement/deficit, pult ledger, forklifts; no whole-staff-per-process.
- **Контракты / API:** LabourResult/RoleAllocation, monetary input units и
  partial statuses. API exposes result through versioned analysis service.
- **Frontend:** нет; отображение в C21.
- **Данные:** policies/role mapping pinned; зарплата не seed/default.
- **Trace:** each floor/ceil,personshifts/rotation,role cap,withdrawals,
  salary gross/direct/full separately; operator conservation.
- **Тесты:** goldenrotation 27, missing roles/salary, limit 0/1, smallpult,
  deficit disabled, withdrawal≤base, no cleaning useful double factor;
  integration typedintpeople and blockedsubtree; frontend — нет.
- **Acceptance / зависимости:** C03,C07–10 и K05–08; baseline counts от user,
  освобождение и deficit coverage не суммируются как одно увольнение.
- **Вне этапа:** CF, taxes, RaaS, shared process allocation algorithm C18.

## C15 — `economics/purchase-cost-ledger-v1`

- **Цель / источники:** R03 §3.1–3.4, R02 scenario tables, R08, R13 bases.
- **Backend:** `backend/calculation/economics/purchase.py`, typed capital/
  operating ledger, F16–22, battery schedule после решения K10.
- **Контракты / API:** year-indexed CostLedger, amount/source/scope/ownership,
  incomplete required cost line; snapshot monetary data сохраняет precision.
- **Frontend:** нет.
- **Данные:** versioned expense policies, life/liquidity mapping и decisions;
  no invented power/warranty/price; old economic fixtures stay.
- **Trace:** reserve/equipment/depreciable bases отдельно, one energypath,
  warranty/ramp/index policy perline, battery events.
- **Тесты:** chargerceil, optionals/reserve, repairnot×N, warranty 0/3,
  tech 20/21, W→kW/kWh, batteryhorizon, missing commercial inputs,
  residual 30/18/15%; integration/golden itemledger; frontend — нет.
- **Acceptance / зависимости:** C02,C13–14/K09–11; sumlines exact, no unknown
  treatedzero, ledger trace replay. Сложный battery policy выделить отдельным PR
  в этой ветке после basic cost ledger, без изменения financial flow.
- **Вне этапа:** tax/NPV/ROI, RaaS, UI, combined allocation.

## C16 — `economics/full-cashflows-reconciliation-v1`

- **Цель / источники:** R03 §3.5–3.6, все 49 rules R13; K09/K12/K13 решены.
- **Backend:** `cashflow.py`, `tax.py`, `metrics.py` в новом economics package;
  F23–31, base/scenario/difference annualledger, residual only terminal.
- **Контракты / API:** FinancialResult, explicit tax mode, nullable payback,
  NPVbase/scenario/project, namedROI/TCO/effect, reconciliation findings.
- **Frontend:** нет; dashboard ещё использует legacy до C21.
- **Данные:** tax policy effective version/assumptions/research refs,
  annual ramp and rounding decision snapshots; no old run recomputation.
- **Trace:** EBIT/EBITDA/depreciation/tax/CF per year; eachtotal referenceslines;
  negative tax allowed only applicable mode; no extra shield.
- **Тесты:**−80−(−100)=+20, identical flows give zero, reserve notdepreciated,
  no_other_income/loss carry,overheadcancel,latepayback/interpolation,
  CAPEX0, nonmonotonicCF; integration/goldenR13 table; front — нет.
- **Acceptance / зависимости:** C15, research Q07; everyR13 rule has test/check
  or approved explanation ifnotapplicable, metric definitions versioned.
- **Вне этапа:** RaaS, ranking, sensitivity, procurement claims, UI.

## C17 — `economics/raas-cashflows-v1`

- **Цель / источники:** R02 §3.3, R03 §3, R11 схема 10, R13/K21.
- **Backend:** `economics/raas.py`; responsibility policy, F32 plusfullledger.
- **Контракты / API:** acquisition orthogonal to uncertainty; phased/all_fleet
  payment mode, source-backed/explicit scenario terms, RaaS ROI denominator.
- **Frontend:** нет.
- **Данные:** versioned zeroing/payment policies; .02/month clearly assumption.
- **Trace:** zeroedline reason/vendor responsibility, infraremaining reserve,
  separate payment subtotal, no hidden index/hwmultiplier.
- **Тесты:** all 3 uncertainty×2 contractmodes, zeroing every line,
  warranty irrelevant, battery/residual 0,payment once, missingterms;
  integration/golden purchasevsRaaS samefleet; frontend — нет.
- **Acceptance / зависимости:** C13,C16/K21; RaaS has remaining infra CAPEX
  and may have incomplete economics; model policy not advertised vendor offer.
- **Вне этапа:** vendor contracts research completion, UI, ranking.

## C18 — `economics/multiprocess-allocation-v1`

- **Цель / источники:** R11 схема 6 и R13 project reconciliation; K17.
- **Backend:** `allocation.py`, replace combined calculation only v2;
  single sitecapital + shared role pools + annual ledger aggregation.
- **Контракты / API:** SelectedConfiguration/cohort ID, allocation basis,
  per process and project cost/FOT, zero-denominator policy.
- **Frontend:** нет.
- **Данные:** sharedresources metadata/policy version, stableprocess IDs;
  v1 zonal snapshots remain rendering-compatible.
- **Trace:** direct cost→allocation→combined flow, conservation equations,
  order-independent allocation/remainders per agreedprecision policy.
- **Тесты:**2+processes same role,zeroCAPEX, same site fixed different models,
  reorder inputs, single zone identity, no rounded cost sum;
  integration/golden combinedR13 ledger; front — нет.
- **Acceptance / зависимости:** C14–17/K17; sumallocations=project costs,
  released within role pools, projectpayback derived differentialCF.
- **Вне этапа:** новый optimizer перебора mixedfleets, UI, scheduling.

## C19 — `engine/ranking-v2`

- **Цель / источники:** R03 §4–5, R02 §7/9, R08; K14–16.
- **Backend:** `backend/calculation/ranking.py`, explicit component curves,
  eligibility before score, economy normalization afterCF.
- **Контракты / API:** ScoreBreakdown with cohort/version, separate technical
  and financial recommendation, no full score for incomplete finance.
- **Frontend:** нет; existingno-falsebest policy preserved inC21.
- **Данные:** acceptedknots/weights/applicability lists, notliteral 75 iflist 77.
- **Trace:** every component, knots/interpolation, numerator/denominator,
  all negative cohort warning, remaining−5 penalty only whereapplicable.
- **Тесты:** boundary table §8, identicalNPV→50,all negative no false best,
  hard fail scoreabsent, unverifieddata completeness≠safe use,
  deterministic ties; integration/golden score table; front — нет.
- **Acceptance / зависимости:** C05–06,C18; approved piecewise functions no
  invented endpoint; selected best traceable, no legacyfloor 45.
- **Вне этапа:** procurement rubric invention, sensitivity, UI.

## C20 — `economics/sensitivity-v1`

- **Цель / источники:** R00 reproducibility, R02 orthogonal scenarios,
  R03 metrics, R04 решение 7 tornado ±10%; docs 12 минимум price/volume/labour sensitivity.
- **Backend:** orchestrator повторно вызывает pure engine для явных overrides;
  no second implementation of financial math.
- **Контракты / API:** SensitivityRequest/Result with parentrun, changedinputs,
  new versions/digests and delta metrics; baseline immutable.
- **Frontend:** нет; controls C21.
- **Данные:** derivedruns or immutable sensitivity bundle; salary change remainsUSER.
- **Trace:** base/variant node links, reasons of discretefleet/headcount steps.
- **Тесты:** ±10% по трём параметрам, threshold ceil, invalid override,
  blockedvariant,price change not capacity,volume can change N;
  integration/golden deltas; frontend — нет.
- **Acceptance / зависимости:** C18–19; eachdelta explainable, no assumption
  becomes vendor fact, canonical base trace unchanged.
- **Вне этапа:** MonteCarlo/probability distributions absent inreference, UI.

## C21 — `frontend/commercial-scenarios-v2`

- **Цель / источники:** R10/R11 acquisition flow, R13 reconciliation table.
- **Backend:** только существующий versionedAPI C13–20; no browser finance.
- **Контракты / API:** Financial/Procurement/SensitivityResult independent statuses.
- **Frontend:** purchase/RaaS ×3 uncertainty, monthly gross per role,
  commercial input form, baseline/scenario/delta,expenses,roles,pult,
  paybacknull, NPVproject and sensitivity; oldrunviewer retained.
- **Данные:** никаких catalog/runtime mutations из scenarioform.
- **Trace:** show assumptions,uncertainprice/tax, per year cashflow/source drilldown.
- **Тесты:** frontend all 6 combinations, partial finance, no false best,
  noVATguess, only server metrics, user edits invalidate old result;
  contract integration and golden displayedmoney; unit math — нет.
- **Acceptance / зависимости:** C12,C13,C18–20; весь financial flow explained,
  procurement unknown does not look ready; role_salarymissing visible.
- **Вне этапа:** simulation, exports implementation, realpayments/procurement actions.

## C22 — `contracts/scenario-spec-v2`

- **Цель / источники:** R00/R03 §6/R12, same resolved inputs across subsystems.
- **Backend:** `scenario_spec.py`, new models/schemas; preservev 1 builder/replay.
- **Контракты / API:** ScenarioSpecv 2, explicit profile, typedquantity,
  operating windows, batch/exchange semantics, nominal/effective capacity,
  fleet/route bindings, optional financial summary, full VersionBindings.
- **Frontend:** protocoladapter only version negotiation, no simulation UI here.
- **Данные:** v2 golden fixtures, immutable input seed/body digest;
  publishedoldv 1 specimens remainvalid.
- **Trace:** spec references analysisresult nodes/catalog/registry/formula version;
  synthetic geometry explicitly labelled, no overwriting realroute.
- **Тесты:** Python/JS schema parity,unknown version/extra fields,
  capacity-only cleaner without payload, revision changes on version changes,
  v1 compatibility; integration protocol fixture; frontend contract tests.
- **Acceptance / зависимости:** C11; with financial C18; same-origin/source/
  two-phase stale request protections preserved, no forcedeconomics.
- **Вне этапа:** scheduler algorithms, new geometry UI, activation.

## C23 — `simulation/scheduling-kpi-report-v1`

- **Цель / источники:** R12, R03 §6 и R10 SLA; **сначала** approved Q08/K18
  method sheet с equations/event policy и independent examples.
- **Backend:** отдельный deterministic eventkernel/report service;
  capacity formula не заменяется queueheuristic.
- **Контракты / API:** SimulationReportv 1: spec revision, seed, timebasis,
  warmup/window, completedunits/queue/wait/downtime, utilization definitions,
  SLAverdict, deviation denominator, comparableunits/diagnostic limits.
- **Frontend:** нет; endpoint/progress consumer в C24.
- **Данные:** event model/distributions version, reference workload fixtures,
  approved typicalproject size for≤60s target; no invented failure rates.
- **Trace:** nominal operations vs operational availability decomposition;
  demand schedule alignedH/peak; simulation report immutable derived artifact.
- **Тесты:** event ordering/seed replay,22 hvs 24h, zero demand/expected,
  overloaded queues,SLA20/30 min,10%boundary, unavailable failure data,
  cancel/progress; integration report schema and independent queue fixture.
- **Acceptance / зависимости:** C22/Q08; test method demonstrates no double
  charging/wait factor, no claim engineering verification; timeoutreported.
- **Вне этапа:** inferred SLA formula, new equipment facts, browser renderer,
  automatic economics mutation, calibrated industrial digital twin.

## C24 — `visualization/2d-simulation-report`

- **Цель / источники:** R12 обязательная 2D; R03 geometry is synthetic.
- **Backend:** использовать C23 service; no local alternative business formulas.
- **Контракты / API:** ScenarioSpecv 2/SimulationReportv 1 andprogress/cancel.
- **Frontend:** 2D zones/routes/fleet/operations/charging, start/pause/stop,
  restart,speed,scenario selection; KPI/report and explicit divergence.
- **Данные:** savedscene/report/assets bound run revision; geometry changes newpatch.
- **Trace:** visualevents have report time/seed; controlsdon'trewritesnapshot.
- **Тесты:** frontend controls/restart/speed deterministic timeline,
  metric units, stale/cancel/error, nofakeSLApass;
  integration run→spec→report; golden 2D/report capture.
- **Acceptance / зависимости:** C23; mandatory 2D available offline,
  progress≤60 sprofileverified, >10%warningvisible per approved comparison.
- **Вне этапа:** RobCraft migration, improved economic recommendation fromanimation.

## C25 — `robcraft/scenario-v2-reconciliation`

- **Цель / источники:** R12 same inputs + existing secure integration protocol.
- **Backend:** no new capacity/finance; report comparison adapter only.
- **Контракты / API:** versionedScenarioSpecv 2 and report message, origin/source/
  revisionbound; v1 support remains for historical runs.
- **Frontend / RobCraft:** `integration/scenario-spec.js`, `simulation.js`,
  embeddingbridge: replace 24 hdemand shortcuts, tag moving vs productive utilization,
  returnreport instead of treating local stats aseconomicproof.
- **Данные:** fixed seed/event/profile versions, archived reports with geometry modified.
- **Trace:** eachcomparison uses same measurement basis; renderer local energy
  arbitraryunits cannot becomeRUB/kWh without approved model.
- **Тесты:** Python/JS/parsing,maliciousorigin, staleLOAD/PREPARED/APPLY,
  v1/v2 negotiation,shortshifts,10%warning,geometrypatch leaves CF unchanged;
  integration and golden reports; frontend message tests.
- **Acceptance / зависимости:** C22–23; metrics honest/compatible, same-origin
  revision protocol regression passes, live loop doesn'tcalculatefinance.
- **Вне этапа:** replacing RobCraft physics with asserted engineering model,
  motion optimization without specification.

## C26 — `report/calculation-evidence-exports`

- **Цель / источники:** R00 auditability/R13 reconciliation, docs 12 exports.
- **Backend:** snapshot export builder, source/trace references, access control.
- **Контракты / API:** export manifest withrun/versions/digests; PDF plus
  XLSX или equivalent CSV bundle: Inputs,Selection,Scenarios,CashFlow,
  Sensitivity,Sources,Trace,Simulation.
- **Frontend:** download/export status, client renderer only; replace remotefonts
  withlocalassets, no calculation in `generateZonalReport.js`/reportutilities.
- **Данные:** export artifact metadata/policies; no liveprice refresh during export.
- **Trace:** every display figure points to source node; unavailable parts visible.
- **Тесты:** golden CSV amounts=run,PDFtext completeness,offlineassets,
  maliciouscells spreadsheet escaping, other user denied, oldrunexport;
  frontend download/error and integration hash binding.
- **Acceptance / зависимости:** C21,C24–25; reviewer can reconstruct key metrics,
  missing commercial facts not omitted, no leaked private inputs acrossusers.
- **Вне этапа:** admin catalog editing, scrapedresearch, marketingclaims.

## C27 — `catalog/capacity-runtime-dual-run-rollout`

- **Цель / источники:** R00 reproducibility, docs 17/18 evidence/activation contract.
- **Backend:** `catalog_runtime.py`, repository/service rolloutselector;
  new capacity reader separate from legacy full Robot path.
- **Контракты / API:** explicit capacity source/activation policy, versioned
  availability/error status; verifyUIv2 route maps to correct snapshot.
- **Frontend:** rollout configuration only, no newmath or newfeaturepanel.
- **Данные:** validate-only/DRAFT→publish→candidate dualrun→approved activation;
  this is **future** migration, not authorization to activate in this audit.
  Rollback target/version persisted; no destructiveDB commands.
- **Trace:** old/new diffs grouped by intendedGxx/decision, unmatched changes block.
- **Тесты:** disposableDB imports/idempotency/checksums, full 187/223,
  pool 21/24 baseline+no BAS,6/15 models, mapping modelvsposition,
  runtime invalid/no active/fallbackblocked; API/frontend smoke; golden dualrunreport.
- **Acceptance / зависимости:** C11–12, C06 actualbundleaudit; realcapacity
  outputs can be partial finance. Countschange only with approved evidence delta.
- **Вне этапа:** economics/deployment activation, fictitious full Robot,
  full project completion. Может выполняться сразу после C12.

## C28 — `catalog/economics-runtime-migration`

- **Цель / источники:** reference 3.2 canon, docs 17 persistence, все Gxx migrations.
- **Backend:** route version switch/migrator and legacy isolation;
  `economics.py` moved/retained as versioned legacy replay only after approved step.
- **Контракты / API:** deprecation policy v1, active v2, explicit re-run semantics;
  nevertranslateoldfte_cost into exact gross without known old basis.
- **Frontend:** new run→v2, historicalrun→versionedviewer; migration notice.
- **Данные:** additive migration/version mapping, no overwriting old runs or
  originalbundle; backup/restore verified disposable environment.
- **Trace:** migration report before/after byGxx, approved differences,
  rollback restores route config not old data rewrite.
- **Тесты:** dualrun old/new goldens, reopen/copy/delete/exports,
  cross-user and CSRF regressions, invalid migrations rollback,
  schema and frontend compatibility. DBtests disposableonly.
- **Acceptance / зависимости:** C21,C26–27; all numeric deltas explained,
  rollback rehearsed; no legacy deletion before compatibility proof.
- **Вне этапа:** deployment-readinessclaim, BASpool, silent historical recalculation.

## C29 — `qa/calculation-migration-acceptance`

- **Цель / источники:** complete accepted reference coverage, R12 timing,
  R13 reconciliation и docs 12 конкурсные/security gates.
- **Backend / API:** фиксы только обнаруженныхдефектов отдельными маленькими PR;
  все layers tested end-to-end, no test-only bypass в production.
- **Frontend:** полный flow user/file→constraints→capacity→purchase/RaaS→
  sensitivity→2D/3D→reopen/export, versionedoldrun тожеоткрывается.
- **Данные:** pinned release fixtures/manifests и fullcoverage report; realpool
  counts explained evidence diff, full catalog retained.
- **Trace:** no orphan result/source, no hidden client calculation, deterministic reruns,
  redacted diagnostics sufficient to identifyversion/blocker/performance failure.
- **Тесты:** full unit/integration/frontend/golden/contracts, security isolation,
  uploadlimits, malformedunits/sources, backup/restore, offlineLLM/vendor,
  50 users andeconomy≤10s/model≤60s on defined environment; repeatgoldenpath 5 times.
- **Acceptance / зависимости:** C28; Q08/Q09 обещанные process profiles resolved,
  allrequiredC10 microstages pass. Каждый Rxx rule mapped to implemented test,
  explicitN_A or approved product decision; blocked required formula not«done».
- **Вне этапа:** weakening evidence tohitdeadline, unexplained scope reduction,
  pretending simulation is deployment certification.

## Как считать план завершённым

Аудит и roadmap готовы уже сейчас. Внедрение считается полным только после
C29 и всех утверждённых process microstages, закрытия K/Q, необходимых для
обещанных сценариев, и release gate. Partial capacity release C27 полезен
самостоятельно, но не подменяет готовность всей экономики, SLA или внедрения
оборудования на объекте. Работы admin/catalog publish и операционной сдачи,
не связанные с расчётным каноном, остаются в верхнеуровневом docs 12.
