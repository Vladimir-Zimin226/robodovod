# План доработки «РОБОДОВОДА» до финала хакатона

Статус: проверенный операционный план команды. Версия: 1.3 от 16 сентября
2026 года.

План повторно сопоставлен с фактическим кодом, официальными материалами,
нормализованным staging и текущими тестами. Официальное ТЗ имеет приоритет.
`16_OFFICIAL_MATERIALS_AUDIT_AND_PLAN.md` содержит traceability, а
`17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md` — обязательный storage contract,
схему первой миграции и правила импорта. `13_ROBCRAFT_ENGINE.md` и
`15_ROBCRAFT_INTEGRATION_PLAN.md` описывают реализованную 3D-подсистему, но не
задают порядок оставшихся конкурсных работ.

## 1. Цель финальной версии

За 3–5 минут пользователь и жюри должны увидеть доказуемую цепочку:

`официальные данные/файл → качество входа → readiness → архитектура →
hard constraints → конфигурация → procurement → экономика →
sensitivity → 2D/3D → сохранённый расчёт → PDF и Excel/CSV`.

Warehouse — полный golden path. Аэропорт и медучреждение подтверждают
расширяемость на официальных preset и более узком расчёте. Продукт является
экспресс-предынвестиционной оценкой, а не инженерным digital twin.

## 2. Непереговорные инварианты

1. Критический `UNKNOWN` не становится `PASS` через default.
2. `CONFLICT`, `AMBIGUOUS_MODEL_MATCH`, `NOT_FOUND` и `UNKNOWN` не
   становятся достоверным ТТХ.
3. Техническая пригодность, procurement, экономика и доказательность — разные
   измерения. Нельзя рекомендовать только по payback.
4. Формулы остаются в domain, не в ORM, API handler или frontend.
5. Опубликованные версии каталога и успешные AnalysisRun неизменяемы.
6. Любое число имеет USER/FILE/PRESET/CALCULATED/ASSUMED либо source/evidence.
7. Текущий `ScenarioSpec v1`, same-origin `/robcraft/` и двухфазный
   revision protocol сохраняются до отдельной совместимой версии.
8. 2D обязательно; RobCraft 3D — дополнительный доказательный/wow-режим.
9. Runtime не читает `data/staging/`; live vendor/LLM не является точкой отказа.
10. После каждой итерации текущий demo path и regression suite работают.

## 3. Проверенная исходная точка

- Backend — FastAPI и Pydantic, без SQLAlchemy/Alembic; каталог из 13 JSON
  загружается `backend/fleet` в память при импорте модуля.
- API реализует legacy `/api/*`; документированный будущий `/api/v1` пока
  отсутствует. FastAPI генерирует базовый OpenAPI автоматически.
- Frontend — React/Vite, состояние не сохраняется. Есть client-side PDF, но нет
  Excel/CSV export и обязательной 2D-визуализации.
- RobCraft встроен same-origin, поддерживает multi-zone representative scenes,
  движение, редактор, KPI и строгий двухфазный обмен. Telemetry/SimulationReport
  не возвращается в основной расчёт.
- Экономическое ядро уже защищает от ложной рекомендации и считает CAPEX/OPEX,
  TCO, ROI, NPV и payback, но его pessimistic/base/optimistic — uncertainty, а
  не обязательные baseline/purchase/RaaS.
- Compose содержит backend/frontend, но не БД, migrations, backup/reset или CI.
- Проверенный baseline: 175 backend, 3 contract, 8 frontend и 77 RobCraft
  тестов; frontend lint/build и `docker compose config` проходят.
- Staging QA согласован по counts/checksums, но исключён из Git и ещё не
  production-источник.

## 4. Приоритеты

### P0 — обязательно к защите

- официальный warehouse preset и XLSX/CSV intake с валидацией;
- PostgreSQL/Alembic, воспроизводимые migrations и versioned import;
- официальный discovery-каталог и 8–12 demo-curated моделей с provenance;
- guest/user/admin, CRUD проектов, минимум три сценария и immutable AnalysisRun;
- readiness, architecture и `PASS/FAIL/UNKNOWN/ASSUMED` для hard constraints;
- traceable fleet sizing/capacity без скрытых critical defaults;
- baseline/purchase/RaaS и отдельная uncertainty axis;
- sensitivity минимум по equipment price, volume и labor cost;
- обязательная 2D-схема с zones/routes/robots/operations/charging и controls;
- SimulationReport и честная сверка required/observed KPI;
- PDF + Excel/CSV и сохранение визуализации;
- минимальная ручная admin-актуализация/публикация каталога;
- security, deletion, backup/demo reset, performance smoke, Docker и HTTPS.

### P1 после стабильного P0

- более глубокие airport/clinic calculation profiles;
- расширенные evidence inspector и admin workflow;
- дополнительные региональные профили;
- searchable/server-side PDF при надёжном текущем варианте;
- object storage/cloud adapter вместо локального volume;
- автоматическое плановое обновление каталога.

### CUT до защиты

- ROS/Gazebo/Isaac, инженерная калибровка и управление реальными роботами;
- CAD/BIM import и полноценный route optimizer;
- единая физическая 3D-геометрия всех зон;
- live scraper, RAG/ML ради презентации и полный TTX всех 223 моделей;
- ERP/WMS integration, billing, совместная работа и enterprise IAM;
- одинаковая глубина трёх отраслей.

## 5. Подтверждённая последовательность

### Этап 0 — baseline и traceability

Статус: аудит завершён; перед первым merge остаётся прогнать полный Compose на
чистой машине/volume.

- Зафиксировать warehouse golden fixtures, API responses, economy и ScenarioSpec.
- Сохранить список официальных requirements и фактические evidence files/tests.
- Не коммитить staging и исходники организаторов.

Gate: regression baseline воспроизводим, dirty user changes сохранены, а
изменения плана не объявляют отсутствующие функции реализованными.

### Этап 1 — storage control-plane, migration 0001

Scope строго ограничен:

- PostgreSQL, SQLAlchemy 2, psycopg 3, Alembic и `DATABASE_URL`;
- Compose `db → migrate → backend`, named volume, readiness и `.env.example`;
- таблицы версий, source artifacts, version-source links, import runs и
  activation history;
- PostgreSQL integration tests и минимальный CI;
- локальный backend с внешней PostgreSQL.

Не входят catalog rows, staging import, repository switch, projects, auth,
новый API или frontend. Поля/constraints и DoD — в docs/17.

Gate: чистая БД мигрирует до head; повторный upgrade безопасен; текущий API и
все baseline tests не меняют результат.

### Этап 2 — catalog domain и транзакционный importer, migration 0002

- `manufacturers`, `catalog_source_rows`, `equipment_models`,
  applicability, observations, evidence, resolved facts и procurement options;
- import schema, validate-only и отчёт counts/checksums;
- BASE и ENRICHMENT как раздельные phase;
- evidence gate: matching читает только разрешённые resolved facts;
- 187 products, 223 applicability, 223 prices, 3635 base evidence, 140 overlay
  fields и 156 external evidence сверяются независимо;
- новый 91-страничный PDF регистрируется source artifact; старый manifest не
  переписывается;
- ошибочный импорт полностью откатывается, повтор committed bundle не создаёт
  дублей.

Gate: DRAFT version проходит validation и reconciliation; publish/activation и
runtime switch ещё не выполняются.

### Этап 3 — repository boundary и dual-run

- Domain DTO не зависит от SQLAlchemy.
- Legacy `backend/fleet` остаётся reference adapter и default runtime.
- PostgreSQL adapter включается feature flag только для dual-run.
- Для пересечения моделей сравниваются identity, rejection reasons, fleet,
  economics и canonical ScenarioSpec.
- Различия от официальных данных классифицируются как ожидаемые/дефект/blocked
  by evidence; их нельзя замаскировать под равенство.

Gate: warehouse golden fixtures не регрессируют; PostgreSQL adapter не
использует unsafe statuses; отчёт dual-run объясняет каждое различие.

### Этап 4 — проекты, роли и AnalysisRun, migration 0003

- Минимальные `users`, `projects`, `project_files`, `scenarios`,
  `analysis_runs`, `audit_entries`;
- guest/user/admin без enterprise IAM; owner-based project isolation;
- CRUD/copy/delete проектов и минимум три scenario slots;
- immutable input/result/ScenarioSpec snapshots и version references;
- file metadata/checksum/storage key; физические файлы вне БД;
- повторное открытие читает snapshot, rerun создаёт новую запись;
- password hashing, protected cookies/token flow и negative authorization tests.

Gate: старый run воспроизводимо открывается после появления новой CatalogVersion;
удаление проекта делает недоступными проект и связанные файлы.

### Этап 5 — catalog activation, официальные profiles и file intake

- Atomic activation проверенной CatalogVersion и controlled runtime switch.
- Официальные 42/39/57 параметров становятся metadata-driven presets с
  default/min/max/unit/source.
- XLSX/CSV upload: preview, type/unit/range validation и понятный report;
  невалидный файл не повреждает сохранённый проект.
- Значения получают provenance USER/FILE/PRESET/CALCULATED/ASSUMED.
- Discovery UX: hierarchy, search, filters, sort, compare; selectable только
  curated модели с достаточными facts.

Gate: официальный warehouse файл даёт тот же нормализованный input, что preset;
ошибки атомарны; legacy catalog можно вернуть activation/feature flag.

### Этап 6 — readiness, architecture, constraints и capacity

- Process readiness: dimensions, blockers, preconditions и confidence; hard stop
  отдельно от score.
- Architecture selector до SKU: для warehouse достаточно AMR/AGV/autonomous
  forklift/tugger/partial automation/not-ready taxonomy.
- Constraint result содержит required, available, status, evidence/assumption и
  reason code.
- Critical FAIL блокирует; critical UNKNOWN даёт NEEDS_VALIDATION.
- Capacity использует mission cycle, operating window, utilization,
  availability, charging и reserve; паспортная max speed не является рабочей.
- Formula trace и monotonicity tests обязательны.
- Legacy `/api/calculate` остаётся adapter; versioned endpoint добавляется
  только когда DTO стабилизированы.

Gate: payload/aisle создают hard reject, missing critical geometry — UNKNOWN,
а fleet size объясняется промежуточными величинами.

### Этап 7 — procurement, economics и две оси сценариев

- Коммерческая ось: current baseline, purchase, RaaS.
- Uncertainty: conservative/base/optimistic — независимо от коммерческой оси.
- Purchase учитывает equipment/software/integration/commissioning/training и
  явно описанный reserve; RaaS — setup/recurring/usage fee и срок договора.
- Currency UNKNOWN/QUOTE_REQUIRED не превращается в достоверный CAPEX.
- Gross avoided cost, OPEX и net effect показываются отдельно; TCO ≥5 лет,
  payback, ROI и cash flow сохраняются.
- Амортизация отображается отдельно от cash flow.
- Sensitivity минимум по equipment price, operation volume и labor cost;
  manual overrides журналируются.
- Ranking: hard gates → procurement eligibility → evidence/confidence →
  economics, но не payback alone.

Gate: все три коммерческих сценария сравнимы по одинаковым метрикам; изменение
одного sensitivity-параметра имеет объяснимый delta.

### Этап 8 — обязательная 2D и SimulationReport

- 2D читает тот же ScenarioSpec: zones, routes, fleet, operations и charging.
- Controls: start/stop или pause, restart, speed и scenario selection.
- Фиксированные seed, warm-up и measurement window.
- 2D и RobCraft возвращают versioned SimulationReport во frontend.
- Сопоставляются required/observed throughput, queue, utilization,
  availability, downtime и safety stops.
- Verdict только VERIFIED/BORDERLINE/NOT_CONFIRMED; симуляция не меняет
  экономическую рекомендацию без нового AnalysisRun.
- Сохраняются PNG/SVG и telemetry JSON; ScenePatch остаётся revision-bound.

Gate: визуализация не декоративна, но и не называется инженерной верификацией;
расхождение KPI явно видно и не скрывается.

### Этап 9 — отчёты и минимальная admin-актуализация

- PDF: inputs/provenance, selection/rejections, configuration, formulas,
  commercial scenarios, sensitivity, SimulationReport, versions и limitations.
- Excel: Inputs, Selection, Scenarios, CashFlow, Sensitivity, Sources; либо
  эквивалентный CSV bundle.
- Локальные assets/fonts, без CDN как точки отказа.
- Admin может вручную создать/изменить DRAFT, проверить, опубликовать и
  активировать новую версию; опубликованная версия не редактируется.
- Автоматический scraper/scheduler остаётся P1.

Gate: PDF и таблицы восстанавливают ключевые числа run; старый run не меняется
после новой публикации каталога.

### Этап 10 — security, operations и конкурсная приёмка

- Compose на чистой машине, migrations, health/readiness, backup/restore и
  allowlisted demo reset.
- HTTPS, secrets, upload limits/type checks, project isolation и deletion tests.
- Нагрузка до 50 пользователей; economy ≤10 s; model/recalc ≤60 s со статусом.
- 1366×768, keyboard/basic accessibility и русский пользовательский flow.
- E2E официального warehouse: project → file/preset → selection → scenarios →
  2D/3D → reopen → exports.
- Demo accounts, user/admin guide, sources/libraries, backup PDF/video.

Gate: golden path проходит пять раз подряд локально и на публичном стенде;
отказ LLM/live sources не ломает demo.

## 6. Порядок небольших PR/итераций

1. `infra/postgres-storage-control-plane`
2. `data/catalog-domain-schema`
3. `data/catalog-validator-importer`
4. `data/catalog-repository-dual-run`
5. `persistence/projects-analysis-runs`
6. `data/catalog-activation-official-presets`
7. `intake/xlsx-csv-project-files`
8. `engine/readiness-architecture-constraints`
9. `engine/capacity-formula-trace`
10. `economics/commercial-scenarios-sensitivity`
11. `visualization/2d-simulation-report`
12. `report/pdf-xlsx-csv`
13. `admin/catalog-draft-publish`
14. `qa/security-performance-deploy`

Первой следующей сессии разрешён только пункт 1. Нельзя объединять его с
catalog importer или переносом endpoint: это уничтожит диагностическую ценность
малой итерации.

## 7. Тестовая стратегия

| Слой | Обязательные проверки |
|---|---|
| Migration | upgrade head, repeat upgrade, disposable downgrade/upgrade, CHECK/FK/partial unique |
| Import | schema, checksum, exact counts, dangling refs, duplicate natural key, rollback, idempotency, base/overlay isolation |
| Evidence | запрещённые статусы не появляются в matching view; UNKNOWN не получает value/default |
| Repository | contract tests обоих adapters и dual-run fixtures |
| Persistence | immutable run, version refs, reopen, copy/delete, cross-user denial, file cleanup |
| Domain | hard FAIL/UNKNOWN, forced warning, monotonicity, purchase/RaaS, sensitivity |
| Contracts | Python/JS ScenarioSpec, unknown fields/version, two-phase revision and stale request |
| Visualization | deterministic 2D/3D, controls, SimulationReport schema and revision binding |
| Export | PDF/XLSX/CSV content against AnalysisRun snapshot; offline assets |
| E2E/ops | official XLSX happy/error paths, Compose, reset/restore, 50-user smoke and timing |

Golden fixtures минимум:

1. официальный warehouse base;
2. тот же warehouse с изменённым объёмом/сменами;
3. hard reject по payload/aisle;
4. critical UNKNOWN → NEEDS_VALIDATION;
5. purchase vs RaaS;
6. SimulationReport below required throughput;
7. старый AnalysisRun после новой catalog activation;
8. invalid XLSX не повреждает проект.

## 8. Реалистичная оценка и безопасные сокращения

Прежние 15–20 человеко-дней не подтверждаются полным ТЗ: только persistence,
intake, auth, 2D, commercial scenarios, exports, admin и deployment образуют
несколько независимых вертикальных срезов. До завершения первой итерации
разумный диапазон полного P0 — 25–40 человеко-дней с повторной оценкой после
каждого gate.

При нехватке времени сокращаются глубина airport/clinic, число curated моделей,
региональные профили, технология PDF, облачный storage и красота admin UI.
Нельзя сокращать correctness/evidence gate, СУБД и AnalysisRun, официальный
intake, baseline/purchase/RaaS, sensitivity ≥3, обязательную 2D, exports,
минимальные роли/admin, security и воспроизводимую сдачу.

## 9. Ответственность и research routing

| Область | Владимир | Женя | Внешний reviewer |
|---|---|---|---|
| Contracts/engine/API/storage | Responsible | Consulted | — |
| Readiness/architecture rules | Implementation | Product owner | Sanity check |
| Catalog schema/import | Responsible | Data owner | Review |
| Procurement/evidence | Support | Responsible | Review |
| Economics | Implementation | Assumptions/copy | Domain check |
| Frontend/visualization | Implementation | UX/copy | — |
| Reports/pitch | Technical | Content owner | Review |
| Tests/deployment | Responsible | Acceptance | — |

Research-файлы остаются справочным слоем. Ни один research вывод не заменяет
официальное ТЗ или первичный source artifact; demo-visible факт повторно
проверяется по исходной ссылке.

## 10. Финальный Definition of Done

Проект готов к сдаче, когда официальный warehouse flow позволяет:

1. войти как guest либо demo user и создать проект;
2. выбрать официальный preset или загрузить XLSX/CSV с валидацией;
3. получить объяснимый подбор из published catalog без unsafe ТТХ;
4. сравнить минимум три сценария: baseline, purchase и RaaS;
5. изменить минимум три sensitivity-параметра;
6. запустить обязательную 2D и дополнительную 3D и увидеть
   required/observed KPI;
7. сохранить и повторно открыть immutable AnalysisRun с версиями;
8. выгрузить PDF и Excel/CSV и сохранить визуализацию;
9. выполнить минимальную admin-актуализацию новой catalog version;
10. удалить проект и связанные файлы;
11. воспроизвести результат через Compose без LLM/live vendor dependency.

Команда при этом может показать источник, формулу, unit, status и limitation
каждого главного числа и не обещает инженерную точность, которой продукт не
доказывает.
