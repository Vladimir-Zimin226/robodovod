# План доработки «РОБОДОВОДА» до финала хакатона

Статус: верхнеуровневый операционный план команды. Версия: 1.5 от 20 сентября
2026 года. Детальная расчётная последовательность уточнена отдельным аудитом;
исторические этапы и реализованные возможности сохранены.

План повторно сопоставлен с фактическим кодом, официальными материалами,
нормализованным staging и текущими тестами. Официальное ТЗ имеет приоритет.
`16_OFFICIAL_MATERIALS_AUDIT_AND_PLAN.md` содержит traceability, а
`17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md` — обязательный storage contract,
схему первой миграции и правила импорта. `13_ROBCRAFT_ENGINE.md` и
`15_ROBCRAFT_INTEGRATION_PLAN.md` описывают реализованную 3D-подсистему, но не
задают порядок оставшихся конкурсных работ.

Уточнение 2026-09-19: для целевой расчётной и продуктовой логики изучены
все 14 документов `Разобрать/Версии проекта от Жени/reference`
версии 3.2. [План 19](19_ZHENYA_CALCULATION_IMPLEMENTATION_PLAN.md) содержит
canonical model, source coverage, gap/conflict matrix, trace и исполнимые
итерации. Он уточняет расчётные части этапов 6–9 и будущую последовательность
ниже. Evidence/provenance, strict contracts и tenant isolation не ослабляются.
Источники не устраняют неизвестные ТТХ, коммерческие условия и нормативные
вопросы; разногласия с этим roadmap отражены в плане 19.


Уточнение 2026-09-20: после полного чтения ТЗ и дополнений агентом приняты
все K/Q плана19. Приоритет — ТЗ/дополнения и принятая policy; никаких внешних
решений для разработки не требуется. Test/evidence/security gates сохраняются.
Сквозной объект — warehouse; три типа доступны в каталоге/формах,28process
scopes заданы. Неизвестные входы вызывают штатный частичный результат.

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

Пункты этого раздела описывают исторический срез плана 1.3 от 16 сентября,
если в них явно не указана последующая миграция. На 19 сентября persistence,
PostgreSQL и production bundle реализованы; прежние утверждения об отсутствии
сохранения и БД не являются текущим статусом. Актуальный срез f77c32c,
разрыв capacity DTO/API и проверенный каталог приведены в плане 19 §2/§4.
Историческое число тестов ниже не является результатом нового аудита.

- Исходный baseline использовал 13 встроенных JSON-моделей; этот fleet удалён
  после ввода versioned catalog repository и activation slots.
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
- На исходной точке Compose содержал backend/frontend, но не БД, migrations,
  backup/reset или воспроизводимый автоматизированный прогон проверок.
- Проверенный baseline: 179 backend, 4 contract, 8 frontend и 77 RobCraft
  тестов; frontend lint/build и `docker compose config` проходят.
- Staging QA согласован по counts/checksums, но исключён из Git и ещё не
  production-источник.

## 4. Приоритеты

### P0 — обязательно к защите

- официальный warehouse preset и XLSX/CSV intake с валидацией;
- PostgreSQL/Alembic, воспроизводимые migrations и versioned import;
- официальный discovery-каталог и 8–12 demo-curated моделей с provenance;
- guest demo-flow; регистрация user по email/password с optional name; admin
  CRUD пользователей; CRUD проектов, минимум три сценария и immutable AnalysisRun;
- readiness, architecture и `PASS/FAIL/UNKNOWN/ASSUMED` для hard constraints;
- traceable fleet sizing/capacity без скрытых critical defaults;
- baseline/purchase/RaaS и отдельная uncertainty axis;
- sensitivity минимум по equipment price, volume и labor cost;
- обязательная 2D-схема с zones/routes/robots/operations/charging и controls;
- SimulationReport и честная сверка required/observed KPI;
- PDF + Excel/CSV и сохранение визуализации;
- минимальная ручная admin-актуализация/публикация каталога;
- локальные uploads/backup volumes, admin diagnostic bundle, security, deletion,
  demo reset, performance smoke, Docker и HTTPS.

### P1 после стабильного P0

- более глубокие airport/clinic calculation profiles;
- расширенные evidence inspector и admin workflow;
- дополнительные региональные профили;
- searchable/server-side PDF при надёжном текущем варианте;
- S3/object-storage adapter вместо локального volume;
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
- PostgreSQL integration tests и воспроизводимый локальный/Compose-прогон;
- локальный backend с внешней PostgreSQL.

Не входят catalog rows, staging import, repository switch, projects, auth,
новый API или frontend. Поля/constraints и DoD — в docs/17.

Gate: чистая БД мигрирует до head; повторный upgrade безопасен; текущий API и
все baseline tests не меняют результат.

### Этап 2 — catalog domain и транзакционный importer, migration 0002

Статус: выполнен двумя малыми итерациями `data/catalog-domain-schema` и
`data/catalog-validator-importer`; runtime switch намеренно не выполнен.

- `manufacturers`, `catalog_source_rows`, `equipment_models`,
  applicability, observations, evidence, resolved facts и procurement options;
- committed text bundle `data/import/organizer-catalog-v4/` с manifest,
  schema, normalized JSON/CSV и enrichment; source binaries остаются вне Git;
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

Статус: выполнен итерацией `data/catalog-repository-dual-run`, затем legacy
adapter удалён; production runtime использует только активированный PostgreSQL
slot, а dual-run сравнивает две явные версии каталога.

- Domain DTO не зависит от SQLAlchemy.
- Встроенных production/reference моделей нет.
- PostgreSQL adapter включается feature flag только для dual-run.
- Для пересечения моделей сравниваются identity, rejection reasons, fleet,
  economics и canonical ScenarioSpec.
- Различия от официальных данных классифицируются как ожидаемые/дефект/blocked
  by evidence; их нельзя замаскировать под равенство.

Gate: warehouse golden fixtures не регрессируют; PostgreSQL adapter не
использует unsafe statuses; отчёт dual-run объясняет каждое различие.

### Этап 4 — проекты, роли и AnalysisRun, migration 0003

Статус: выполнен итерацией `persistence/projects-analysis-runs`; гостевой
расчёт остаётся неперсистентным, а runtime-каталог требует activation slot.

- Минимальные `users`, `projects`, `project_files`, `scenarios`,
  `analysis_runs`, `audit_entries`;
- guest не хранится и работает только с demo; self-registration создаёт USER
  по email/password с optional name;
- ADMIN создаёт/редактирует/отключает/удаляет пользователей и сбрасывает
  пароль; нельзя создать admin через public registration, удалить или понизить
  последнего активного admin;
- первый ADMIN создаётся одноразовым идемпотентным bootstrap из
  `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` и optional
  `BOOTSTRAP_ADMIN_NAME` в локальном `.env`; `.env.example` содержит только
  placeholders, существующая учётная запись bootstrap не перезаписывается;
- owner-based project isolation без project sharing;
- CRUD/copy/delete проектов и минимум три scenario slots;
- immutable input/result/ScenarioSpec snapshots и version references;
- file metadata/checksum/storage key в БД; физические файлы в локальном named
  volume, S3 в P0 не используется;
- повторное открытие читает snapshot, rerun создаёт новую запись;
- password hashing, protected cookies/token flow и negative authorization tests.

Gate: старый run воспроизводимо открывается после появления новой CatalogVersion;
admin user CRUD и cross-user denial проходят integration tests; удаление проекта
делает недоступными project payload и локальные файлы, оставляя только
минимальный deletion tombstone на 30 дней с последующим purge.

### Этап 5 — catalog activation, официальные profiles и file intake

Статус: `data/catalog-activation-official-presets`, корректирующие срезы
`data/catalog-positions-media`, `frontend/catalog-theme-media` и
`data/catalog-description-enrichment`, `frontend/catalog-position-details` и
`intake/xlsx-csv-project-files`, `engine/readiness-architecture-constraints` и
`catalog/runtime-eligibility-contract-gap-audit-223`,
`catalog/official-source-enrichment` и
`catalog/calculation-readiness-contract-v2` и
`catalog/runtime-pool-materialization-ui-21` реализованы. Следующий этап —
`engine/capacity-formula-trace`, определённый после gate в `docs/18`.
Публикация проверяет
imports/checksums/counts, activation history
переключается атомарно, а `runtime` slot закрыт для версии без evidence-backed
runtime models. Встроенный legacy fleet удалён; rollback выполняется только
между явно опубликованными версиями PostgreSQL-каталога. Официальные
42/39/57 profiles и их PRESET/CALCULATED/ASSUMED provenance доступны через API;
discovery показывает все 223 позиции, но selectable только доказательно готовые.

- Atomic activation проверенной CatalogVersion и controlled runtime switch.
- Официальные 42/39/57 параметров становятся metadata-driven presets с
  default/min/max/unit/source.
- XLSX/CSV upload: preview, type/unit/range validation и понятный report;
  невалидный файл не повреждает сохранённый проект.
- Значения получают provenance USER/FILE/PRESET/CALCULATED/ASSUMED.
- Discovery UX: hierarchy, search, filters, sort, compare; selectable только
  curated модели с достаточными facts.

Gate: официальный warehouse файл даёт тот же нормализованный input, что preset;
ошибки атомарны; предыдущую опубликованную версию каталога можно вернуть через
activation history.

Для завершённой малой итерации пройдены atomic publication/activation,
profile-count/provenance и legacy rollback gates. Эквивалентность официального
warehouse файла и preset подтверждена строгими XLSX/CSV adapters и
contract/integration tests.

#### Уточнение кейсодателя от 2026-09-17: 223 позиции и catalog UX

Статус: срезы `data/catalog-positions-media`, `frontend/catalog-theme-media` и
`data/catalog-description-enrichment`, `frontend/catalog-position-details` и
`intake/xlsx-csv-project-files`, `engine/readiness-architecture-constraints` и
`catalog/runtime-eligibility-contract-gap-audit-223`, official-source
enrichment, calculation-readiness contract v2 и
`catalog/runtime-pool-materialization-ui-21` реализованы; далее идёт
`engine/capacity-formula-trace`.
Migration 0004 хранит append-only media metadata,
extractor проверяет SHA-256 restricted PDF и связывает 223 позиции со 189
уникальными content-addressed assets. Discovery API возвращает 223 позиции при
187 канонических моделях, row-specific applicability/price и media provenance.
Расчётный runtime не переключён.
На чистой PostgreSQL smoke-последовательность BASE → ENRICHMENT → publish →
activate подтверждает capacity counts 21 / 24; отдельный повторный
`catalog-media` восстанавливает 189 assets / 223 position links. Compose
tools-профиль после обновления checkout запускается с явным `--build`, поскольку
обычный `docker compose up --build` профильные образы не пересобирает.

Catalog UI использует position ID как key/selection identity, показывает
официальные assets лениво с устойчивым fallback, ограничивает сравнение тремя
позициями и не создаёт selectable-state на клиенте. Тёмные controls/cards,
читаемые placeholders, keyboard focus, loading/empty/error states и сетка
3→2→1 закрывают визуальный контракт desktop/mobile.

После демонстрации активированного discovery-каталога подтверждено, что
одинаковые `organizer_id` нельзя схлопывать на пользовательском и расчётном
уровне: повторные строки могут отличаться ценой, отраслью, сценарием применения,
регионом и кейсом. Поэтому 187 канонических `EquipmentModel` остаются слоем
идентичности и общих доказанных ТТХ, но единицей каталога, сравнения, подбора и
последующего расчёта становится каждая из 223 исходных catalog positions.

- Публичная проекция позиции фиксирует `source_row_id`, `model_id`, конкретные
  applicability и procurement option; ranking/AnalysisRun сохраняют все эти ID.
- Ни UI, ни matching не дедуплицируют 223 позиции по `organizer_id`, названию или
  одинаковой цене. Тесты отдельно покрывают повторные модели с разными ценами и
  областями применения.
- Изображения извлекаются из исходного официального каталога в локальное
  content-addressed media storage; БД хранит checksum, MIME, размер, provenance,
  source page/row и связь с позицией. Remote hotlink и выдуманные изображения не
  используются; для отсутствующего/непригодного изображения есть явный fallback.
- Экран каталога приводится к общей тёмной теме: контрастные cards/search/select,
  видимые focus/hover/disabled states, читаемые заголовки групп и адаптивная
  сетка. Контраст проверяется минимум на целевом 1366×768.

Gate полного корректирующего среза: API и UI возвращают ровно 223 позиции, при этом 187
канонических моделей не клонируются; различия duplicate rows сохраняются в
сравнении и расчётном snapshot; изображения имеют проверяемый source provenance;
поиск и фильтры читаемы на тёмном фоне и работают с клавиатуры.

Data-часть и визуальная/keyboard/contrast часть gate закрыты.

#### Уточнение после просмотра UI: описания и подробная карточка

В текущем discovery read-model описание есть у 108 из 223 позиций, у 115 оно
отсутствует. Проверка исходного 91-страничного PDF подтверждает, что эти тексты
присутствуют в карточках PDF вместе с УГТ, стадией внедрения, рыночным
потенциалом и кейсами. Предыдущий media pipeline извлекал только изображения;
обычный PDF text extraction повреждает часть кириллицы из-за font mapping.

17 сентября 2026 года рядом с исходным PDF подготовлены две полные текстовые
версии. Они являются локальными входными результатами, а не инструкциями и не
runtime truth:

- `ФЦ_БАС_Каталог_часть_1_стр_1-46_полная_текстовая_версия.md`: 110 карточек,
  SHA-256 `b0be869c049b95f493035f312ab83b99e4fda4caeec5ba828f0eb9587203bbe6`;
- `ФЦ_БАС_Каталог_внедрения_часть_2_стр_47-91_полная_текстовая_версия.md`:
  113 карточек, SHA-256
  `044feb0a1d40e750867a70c93b382a52f10c83e8847bcb94f433d885e9c710d2`.

Итого покрыты ровно 223 позиции. Первая часть page-oriented и сохраняет строки
карточек близко к визуальному порядку; вторая уже field-oriented. Во второй
части все 113 карточек имеют страницу, организацию, регион, сценарий, описание,
УГТ, статус и market potential; у 14 карточек отсутствует только не напечатанный
в PDF тип. Ссылки покрыты неравномерно: 54 URL в первой части и ни одного во
второй, поэтому отсутствие URL нельзя интерпретировать как отсутствие source.
Транскрипция заявляет двойную сверку, но не фиксирует OCR engine/model/version;
в системе она регистрируется как externally prepared transcription и проходит
нашу проверку, а не получает статус verified только на основании заявления.

Реализованная итерация `data/catalog-description-enrichment`:

- проверяет SHA-256 PDF и обеих транскрипций, запрещает незаметную подмену
  входных файлов и не включает локальные source-файлы в Git;
- содержит два строгих parser adapter для page-oriented и field-oriented
  Markdown и строит единый versioned normalized overlay на 223 позиции;
- сопоставляет 110 + 113 карточек в document order с существующими
  `source_page + source_slot -> catalog position`, затем подтверждает mapping
  anchors по названию и организации; номера проектов перезапускаются в каждом
  разделе и не служат глобальным ID;
- сохраняет verbatim text, normalized fields, transcript artifact/hash,
  страницу/slot, position ID и checksum изображения как provenance; отсутствие
  OCR engine/model в полученных файлах явно остаётся limitation metadata;
- отдельно извлекает только явно подписанные УГТ, lifecycle stage, market
  potential, case text и служебные метки; эти поля не становятся
  matching/runtime facts автоматически;
- не перезаписывает существующее качественное описание: расхождение становится
  observation/review item; исходные опечатки хранятся verbatim, а любые display
  corrections должны иметь отдельное review decision;
- не достраивает 14 отсутствующих типов и отсутствующие URL; `null` сохраняется
  отдельно от parser failure;
- выдаёт coverage/conflict report по всем 223 позициям и остаётся идемпотентной;
  publication/activation и расчётный runtime не переключаются.

Gate: все 223 карточки однозначно сопоставлены либо имеют явную диагностическую
причину; ни одна позиция не схлопнута; повторный запуск даёт тот же результат;
ручная сверка PDF включает границу частей, все девять разделов, существующие
описания, переносы строк, карточки без типа, source typos и duplicate models;
все 115 ранее пустых descriptions либо получают проверенный текст, либо явный
`REVIEW_REQUIRED`; UI получает только прошедшие evidence gate поля. Повторный
OCR всего PDF в scope не входит и допускается только как точечный fallback для
конкретного неразрешённого расхождения.

Следующая итерация `frontend/catalog-position-details` открывает по нажатию на
карточку доступный с клавиатуры drawer/modal: полное изображение и описание,
все use cases/industries/regions/facts, row-specific procurement/applicability,
УГТ/стадию/кейсы, source provenance и причины `discovery-only`. Она не считает
новые значения на клиенте и не меняет selection/runtime semantics.

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

Статус малой итерации: `engine/readiness-architecture-constraints`
реализована отдельным детерминированным `POST /api/readiness`.
Ответ `readiness-report-v1` содержит score отдельно от hard stop,
разрезы, blockers, preconditions, confidence, architecture candidates до
SKU и помодельные constraint results с required/available,
evidence, reason code и `PASS/FAIL/UNKNOWN/ASSUMED`. Неизвестные
payload/aisle не получают default и дают `NEEDS_VALIDATION`; превышение
даёт hard reject. После этой исторической итерации встроенный legacy runtime
удалён; capacity и economics не менялись. Оставшаяся часть этапа вынесена в
`engine/capacity-formula-trace`.

### Этап 7 — procurement, economics и две оси сценариев

- Коммерческая ось: current baseline, purchase, RaaS.
- Uncertainty: conservative/base/optimistic — независимо от коммерческой оси.
- Purchase учитывает equipment/software/integration/commissioning/training и
  явно описанный reserve; RaaS — setup/recurring/usage fee и срок договора.
- Для organizer v4 валюта цен — RUB по продуктовому решению. Raw value и
  provenance сохраняются; НДС считается включённым только как допущение
  организаторов без выдуманной ставки. Доставка, пусконаладка и глубокая
  ИТ-интеграция считаются отдельно. Для иных источников
  UNKNOWN/QUOTE_REQUIRED не превращается в достоверный CAPEX.
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

Статус: C23 scheduler/report, C24 обязательная offline 2D и C25 RobCraft
ScenarioSpec v2/report reconciliation завершены.

- 2D читает тот же ScenarioSpec: zones, routes, fleet, operations и charging.
- Controls: start/stop или pause, restart, speed и scenario selection.
- Фиксированные seed, warm-up и measurement window.
- 2D читает versioned SimulationReport v1 C23; RobCraft возвращает отдельный
  visual-only report C25, а same-basis comparison выполняет backend adapter.
- Сопоставляются required/expected/observed throughput, queue/wait,
  productive/busy/nonproductive utilization и conditional SLA. Failure и
  charging distributions без входов не выдумываются.
- Verdict соответствует C23: CONSISTENT/DEVIATION/OVERLOADED/
  CONDITIONAL_MODEL/NOT_EVALUATED; симуляция не меняет
  экономическую рекомендацию без нового AnalysisRun.
- Сохраняются PNG/SVG и telemetry JSON; ScenePatch остаётся revision-bound.

Gate: визуализация не декоративна, но и не называется инженерной верификацией;
расхождение KPI явно видно и не скрывается.

### Этап 9 — отчёты и минимальная admin-актуализация

Статус: snapshot-driven PDF/CSV evidence export C26 завершён. Admin catalog
актуализация остаётся отдельной последующей работой и в C26 не выполнялась.

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
- Operational `pg_dump` и backup uploads остаются server/CLI operation.
- Admin скачивает отдельный sanitized diagnostic bundle с версиями, manifests,
  import/integrity results, redacted errors и агрегированными counts, но без
  паролей, секретов, email/name, uploaded content и полных snapshots.
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
7. `data/catalog-positions-media`
8. `frontend/catalog-theme-media`
9. `data/catalog-description-enrichment` — реализован
10. `frontend/catalog-position-details` — реализован
11. `intake/xlsx-csv-project-files` — реализован
12. `engine/readiness-architecture-constraints` — реализован
13. `catalog/runtime-eligibility-contract-gap-audit-223` — реализован
14. `catalog/official-source-enrichment` — исследование и decision staging
    завершены: 131 accepted / 7 deferred / 318 missing; принятый срез перенесён
    в immutable ENRICHMENT bundle итерацией 16
15. `catalog/calculation-readiness-contract-v2` — реализован split calculation /
    deployment gates: 21 model / 24 position calculation pool, из них 19
    accepted-research identities; runtime activation не выполнена
16. `catalog/runtime-pool-materialization-ui-21` — реализован: полный
    discovery-каталог остаётся на 187 моделях / 223 позициях, а 21 расчётная
    модель / 24 позиции получают materialized capacity runtime, явный UI-тег и
    фильтр по участию в расчёте; обязательный контракт —
    `docs/18_RUNTIME_POOL_AND_CATALOG_UI.md`
17. `contracts/calculation-semantics-v1` — новый непосредственный этап C01:
    units, exchange/speed/batch semantics, независимые capacity/economics
    statuses, provenance и trace contract. Формулы ещё не реализуются.
18. C02–C06 плана 19 — registry, intake/roles, отдельный UI intake,
    applicability и повторный formula-executability audit.
19. `engine/capacity-formula-trace` (C07), отдельно cleaning C08 и cell C09;
    process coverage C10, capacity API/snapshots C11 и results UI C12.
20. C13–C20 — отдельно commercial/procurement inputs, labour, purchase cost
    ledger, full CF/reconciliation, RaaS, shared allocation, ranking, sensitivity.
    C13–C26 реализованы; следующий этап — C27
    `catalog/capacity-runtime-dual-run-rollout`.
21. C21–C25 — financial UI, ScenarioSpec v2, утверждённая scheduling/SLA модель,
    обязательная 2D и отдельный RobCraft adapter/report.
22. C26 — exports реализован; C27–C28 — capacity rollout и отдельная economics migration.
    Capacity rollout C27 можно выполнить после C12, не дожидаясь экономики.
23. `admin/catalog-draft-publish` — самостоятельная работа верхнего roadmap.
24. C29 `qa/calculation-migration-acceptance` и оставшиеся
    `qa/security-performance-deploy`/operations gates.
25. C30 `ops/production-domain-deployment-v1` — отдельная публикация принятого
    release на Selectel VDS: production Compose, закрытые внутренние порты,
    DNS/TLS для apex+www, secrets, migrations, backup/restore, observability и
    проверенный rollback. Production activation допускается только после C29.

Точные имена всех веток, dependencies, migrations и acceptance gates:
[карточки C01–C30](planning/zhenya-phases.md). Для 28 process blocks указаны
отдельные microstages C10.01–C10.28; scope каждого блока определён
[policy v1](planning/calculation-policy-decisions-v1.md): supported formula,
scenario-only cycle, reference-only или constraints. Ответ Жени не требуется. Прежние укрупнённые
пункты 17–23 пересмотрены этим датированным уточнением; реализация расчётного
движка в аудитную сессию не входила.

Каждый пункт выполняется отдельной малой итерацией. Нельзя объединять importer
или перенос endpoint с соседним пунктом: это уничтожает диагностическую
ценность и усложняет rollback.

Итерация 13 фиксирует обязательные runtime fields и capacity-profile
для каждого поддерживаемого класса, но не пишет сами capacity formulas.
Она должна детерминированно классифицировать каждую из 223 positions и
каждую из 187 model identities как минимум в `RUNTIME_READY`,
`NEEDS_FACTS`, `CONFLICT_REVIEW`, `UNSUPPORTED_CAPACITY_PROFILE` или
`NOT_EQUIPMENT`, показать missing fields/source coverage и выдать явную
рекомендацию `LOCAL_ADAPTER`, `DEEP_RESEARCH`, `HYBRID` или `NO_ACTION`.
Выходы — versioned machine-readable report, человекочитаемая сводка и
тесты exact coverage/counts/idempotency. Нельзя додумывать URL/ТТХ, склеивать
223 positions или переводить discovery facts в runtime facts.

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
региональные профили, технология PDF, S3 и красота admin UI.
Нельзя сокращать correctness/evidence gate, СУБД и AnalysisRun, официальный
intake, baseline/purchase/RaaS, sensitivity ≥3, обязательную 2D, exports,
минимальные роли/admin, security и воспроизводимую сдачу.

## 9. Ответственность и research routing

Таблица сохраняет исходное распределение ролей команды. По поручению
пользователя от 2026-09-20 агент самостоятельно исполняет C01–C29 и принятые
решения policy v1; Consulted/Review/Acceptance ниже не означают ожидание ответа
или подписи. Приёмку определяют автоматические и воспроизводимые локальные
gates карточек этапов. Внешний review возможен после завершения плана.

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

1. пройти несохраняемый demo как guest либо зарегистрироваться по email/password
   и создать private project;
2. выбрать официальный preset или загрузить XLSX/CSV с валидацией;
3. получить объяснимый подбор из published catalog без unsafe ТТХ;
4. сравнить минимум три сценария: baseline, purchase и RaaS;
5. изменить минимум три sensitivity-параметра;
6. запустить обязательную 2D и дополнительную 3D и увидеть
   required/observed KPI;
7. сохранить и повторно открыть immutable AnalysisRun с версиями;
8. выгрузить PDF и Excel/CSV и сохранить визуализацию;
9. под admin создать/редактировать/удалить пользователя и выполнить минимальную
   актуализацию новой catalog version;
10. скачать sanitized diagnostic bundle;
11. удалить проект и связанные файлы;
12. воспроизвести результат через Compose без LLM/live vendor dependency.

Команда при этом может показать источник, формулу, unit, status и limitation
каждого главного числа и не обещает инженерную точность, которой продукт не
доказывает.
