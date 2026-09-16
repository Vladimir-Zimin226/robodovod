# Хранение данных и интеграция официального каталога

Статус: архитектурное решение повторно проверено по коду, официальному ТЗ и
staging; готово для первой малой реализации. Дата: 16 сентября 2026 года.

## 1. Итог повторной проверки

Направление `ADR → PostgreSQL → SQLAlchemy/Alembic → каталог → importer →
repository → dual-run` подтверждено, но не как один большой этап. Нужны две
поправки к прежнему порядку:

1. первая миграция создаёт только control-plane версий, источников, импортов и
   активаций; предметные таблицы каталога появляются во второй миграции;
2. минимальные проекты, сценарии и immutable `AnalysisRun` реализуются после
   dual-run repository, но **до** переключения runtime на официальный каталог и
   до XLSX/CSV intake. Тогда новый расчёт сразу сохраняет точную версию данных,
   а file intake не приходится временно привязывать к состоянию React.

Создавать новый `/api/v1/analysis`, полностью дробить доменное ядро или менять
frontend одновременно с инфраструктурой БД не следует: это увеличит область
регрессии без пользы для первой миграции. Текущие `/api/calculate`, экономика,
`ScenarioSpec`, same-origin iframe и двухфазный revision protocol остаются
неизменными до отдельной итерации.

## 2. Проверенные исходные факты

- Runtime-каталог сейчас загружается при импорте `backend/fleet` из 13 локальных
  JSON-записей и хранится в process-global структурах; repository boundary нет.
- PostgreSQL, SQLAlchemy, Alembic, `DATABASE_URL`, миграционный service, CI и
  `.env.example` отсутствуют. Compose поднимает только backend и frontend.
- Проекты, пользователи, файлы и расчёты не сохраняются; состояние находится в
  React. PDF создаётся на клиенте.
- Нормализация staging содержит 187 продуктов, 223 applicability rows, 223
  price rows, 3635 field-evidence rows и профили объектов 42/39/57.
- Enrichment-run-1 содержит 11 продуктов, 140 overlay-полей и 156 evidence rows:
  75 `VERIFIED_OFFICIAL`, 52 `NOT_FOUND`, 7 `AMBIGUOUS_MODEL_MATCH`, 6
  `CONFLICT` на уровне overlay. Все контрольные SHA-256 его входов совпадают.
- `PARTIAL` enrichment означает неполное покрытие источников, а не ошибку QA.
  Базовый correction QA и self-check enrichment имеют `PASS`.
- 91-страничный официальный PDF-каталог присутствует сейчас и содержит девять
  разделов и 223 карточки. Он не входил в старый normalization run, поэтому его
  нужно зарегистрировать новым artifact, а не переписывать старый manifest.
- Staging исключён из Git и не является production-источником или runtime
  fallback.

## 3. Границы хранения

| Данные | Хранилище и правило |
|---|---|
| Каталог, применимость, typed facts, procurement и evidence | PostgreSQL, только через версионированный repository |
| Raw source rows и неоднородные snapshots | JSONB рядом с нормализованной записью, но не как единственный источник для фильтрации |
| Пользователи, проекты, сценарии, AnalysisRun и audit | PostgreSQL |
| XLSX/CSV/PDF/планы | Файловое/object storage; в БД — имя, media type, размер, SHA-256, storage key и владелец |
| Миграции, import schema, validators и разрешённый derived bundle | Git после отдельного решения о лицензии и составе |
| Исходники организаторов и текущий staging | Локально, вне Git; импорт только явной командой |
| Секреты | Серверное окружение/secret store; никогда не frontend bundle и не Git |

SQLite не используется как production-compatible fallback: JSONB, partial
indexes, ограничения и транзакционные сценарии должны тестироваться на той же
СУБД. Локальный запуск без Docker использует внешний PostgreSQL через
`DATABASE_URL`; допустим Compose-профиль, поднимающий только БД.

## 4. Модель данных и границы сущностей

### 4.1. Идентификаторы и natural keys

- Внутренние PK — UUID, генерируемые приложением; импорт не зависит от
  расширений PostgreSQL и последовательностей.
- `organizer_id` сохраняется отдельным nullable UUID и уникален внутри версии
  каталога, но не является PK и не переиспользуется между версиями.
- Для записи без organizer ID natural key — `(catalog_version_id,
  source_namespace, source_record_key)`.
- Исходная строка имеет ключ `(source_artifact_id, source_row_number)` и не
  схлопывается. Это сохраняет все 223 строки при 187 моделях.
- SHA-256 хранится lowercase hex и проверяется `CHECK`; `source_artifacts.sha256`
  уникален по содержимому.

### 4.2. Что является колонками

Отдельными типизированными колонками хранятся идентичность и связи, lifecycle,
статусы, даты, деньги/валюта, units, source/evidence references и значения,
участвующие в hard filtering. Для mixed-каталога не нужна широкая таблица с
десятками nullable колонок: критические ТТХ хранятся как typed facts с
`spec_code`, одним типизированным value, canonical unit и evidence status.

JSONB используется только для:

- неизменённой исходной строки и import diagnostics;
- неоднородных необязательных атрибутов для показа;
- immutable input/result/ScenarioSpec snapshots AnalysisRun;
- структурированных списков includes/excludes и отчётов сверки.

JSONB не заменяет FK, lifecycle, цену, валюту, checksum или typed hard
constraint. Часто фильтруемые `spec_code + numeric_value` индексируются; если
объём вырастет, можно добавить materialized view, не меняя import contract.

### 4.3. EquipmentModel, SolutionConfiguration, ProcurementOption

- `EquipmentModel` — физическая модель/семейство с идентичностью, производителем
  и доказанными характеристиками. Это не расчётный парк и не цена.
- `SolutionConfiguration` — результат конкретного сценария: набор моделей,
  количества, зарядки, ПО, интеграция и допущения. Он относится к проекту/run,
  поэтому появляется с persistence сценариев, а не в первой каталожной миграции.
- `ProcurementOption` — коммерческое предложение/канал приобретения для модели
  либо позднее для конфигурации: purchase, RaaS, managed service или quote.
  Цена не является полем `EquipmentModel`.

Полиморфная пара `target_type/target_id` не вводится. Каталожное предложение
ссылается на модель, а системное — через явную link-таблицу на конфигурацию.

## 5. Evidence gate: защита от ложных ТТХ

Импорт хранит два разных слоя:

1. `spec_observations` — все найденные утверждения, включая конфликт,
   неоднозначное совпадение модели и отрицательный результат поиска;
2. `resolved_spec_facts` — только выбранные типизированные факты, которые
   repository вообще имеет право передать matching engine.

Для resolved fact обязательны ровно одно typed value, canonical unit, источник,
дата/версия evidence, `resolution_status` и `usable_for_matching`. Ограничение
БД запрещает `usable_for_matching = true` для `CONFLICT`,
`AMBIGUOUS_MODEL_MATCH`, `NOT_FOUND`, `UNKNOWN` и `ASSUMED`. Для внешнего
overlay автоматическое разрешение допустимо только для
`VERIFIED_OFFICIAL`/`VERIFIED_AUTHORIZED_PARTNER`; ручное решение требует
отдельного reviewer, времени и причины. `NOT_FOUND` не содержит factual value.

Организаторский и DOCX-derived канонический слой использует собственные
статусы (`ORGANIZER_PROVIDED`, `CORROBORATED`) и не перезаписывается overlay.
Repository читает представление `matching_spec_facts`, а не observations. При
отсутствии разрешённого critical fact constraint engine обязан вернуть
`UNKNOWN/NEEDS_VALIDATION`, не скрытый default.

## 6. Lifecycle и immutable snapshots

### CatalogVersion

`DRAFT → VALIDATED → PUBLISHED → RETIRED`.

- Импорт изменяет только `DRAFT`.
- `VALIDATED` закрывает content hash и контрольные counts.
- `PUBLISHED` неизменяем; исправление создаёт новую версию с `parent_version_id`.
- Активная версия — отдельная атомарная activation record, не mutable-флаг на
  содержимом. Ошибка импорта относится к `ImportRun`, а не к CatalogVersion.
- Старая версия не удаляется, пока на неё ссылается AnalysisRun.

### AnalysisRun

`PENDING → RUNNING → SUCCEEDED | FAILED | CANCELLED`.

Вход фиксируется при создании. Успешный run после завершения не изменяется;
повторный расчёт создаёт новую запись. Сохраняются input/result/ScenarioSpec
snapshots и их checksums, `catalog_version_id`, версии rules, economics,
object profiles и приложения. Failed run хранит diagnostics, но не выдаётся как
успешный результат.

Повторное открытие читает сохранённый snapshot, а не пересчитывает его на новой
активной версии. Явный rerun показывает diff версий и создаёт новый AnalysisRun.

## 7. Транзакционность и идемпотентность импорта

1. `validate-only` проверяет JSON Schema/Pydantic contract, enum/status policy,
   natural keys, FK references, hashes и ожидаемые counts без записи доменных
   строк.
2. Попытка `ImportRun` создаётся короткой отдельной транзакцией, чтобы ошибка
   основного импорта оставила диагностический след.
3. Все domain rows одного phase (`BASE` или `ENRICHMENT`) пишутся одной
   транзакцией только в `DRAFT`.
4. При ошибке domain transaction целиком откатывается, затем ImportRun
   фиксируется как `FAILED` с безопасной диагностикой.
5. Успех фиксирует counts/content hash и `SUCCEEDED`. Partial unique index на
   `(catalog_version_id, phase, bundle_sha256)` для
   `status=SUCCEEDED AND mode=COMMIT` делает повтор тем же результатом, а не
   вторым набором строк. Успешный `VALIDATE_ONLY` не считается импортом.
6. Overlay добавляет observations/resolutions и никогда не делает update
   organizer observation. Публикация и activation выполняются отдельно.

Импортёр не запускается автоматически при старте backend и не сканирует
`data/staging/`. Разрешённый bundle и его checksum указываются явно.

## 8. Первая малая реализационная итерация

Название: `infra/postgres-storage-control-plane`.

### Scope

- ADR/настройки `DATABASE_URL`; фиксированные совместимые версии SQLAlchemy 2,
  Alembic и psycopg 3.
- PostgreSQL в Compose с named volume, non-root application role и healthcheck.
- Одноразовый `migrate` service; backend стартует после успешного upgrade.
- SQLAlchemy engine/session boundary без перевода текущих endpoint на БД.
- Alembic `0001_storage_control_plane` и миграционные тесты на реальном
  PostgreSQL.
- Liveness остаётся лёгким; отдельная readiness-проверка проверяет БД без вывода
  DSN/секретов.
- `.env.example` только с placeholders, документированные команды полного
  Compose и локального backend с внешним PostgreSQL.
- Минимальный CI workflow: поднять PostgreSQL, `alembic upgrade head`, тест
  schema constraints, downgrade/upgrade только на disposable DB, затем текущий
  regression suite.

В итерацию **не входят** import staging, catalog rows, repository switch,
проекты, auth, новый analysis API или frontend.

### Таблицы миграции 0001

| Таблица | Основные поля и ограничения |
|---|---|
| `catalog_versions` | UUID PK; unique non-empty `code`; optional self-FK `parent_version_id RESTRICT`; `status` CHECK из DRAFT/VALIDATED/PUBLISHED/RETIRED; `schema_version`; nullable `content_sha256` с hex CHECK; timestamps; CHECK для validated/published timestamps; transition trigger разрешает только прямое продвижение lifecycle |
| `source_artifacts` | UUID PK; unique SHA-256; `original_name`, `media_type`, positive `byte_size`, nullable `storage_key`; provenance/license statuses с CHECK; `observed_at`, `created_at`; бинарное содержимое не хранится |
| `catalog_version_sources` | FK version/artifact с `ON DELETE RESTRICT`; role CHECK BASE/ENRICHMENT/REFERENCE/IMPORT_BUNDLE; non-negative ordinal; composite PK и unique `(version_id, role, ordinal)` |
| `import_runs` | UUID PK; FK version; phase BASE/ENRICHMENT, mode VALIDATE_ONLY/COMMIT и status PENDING/RUNNING/SUCCEEDED/FAILED через CHECK; `bundle_sha256`; optional unique request key; timestamps; JSONB counts/diagnostics; partial unique successful-commit index по version/phase/bundle hash; согласованность finished/status через CHECK |
| `catalog_activations` | UUID PK; `slot`, FK version RESTRICT, activated/deactivated timestamps и actor; partial unique index на один active row в slot; CHECK порядка timestamps; deferred constraint trigger требует PUBLISHED version; запись неизменяема кроме однократного заполнения `deactivated_at` |

Ссылки на пользователя в 0001 не нужны: actor временно хранится как nullable
subject string. Это избегает преждевременной auth-схемы. Активация версии до
появления содержимого не используется, но контракт и история фиксируются сразу.

### Definition of Done итерации

- чистая PostgreSQL поднимается и `alembic upgrade head` проходит одной
  документированной командой;
- backend текущего API работает с пустой БД без изменения ответов;
- Compose гарантирует порядок `db healthy → migrate success → backend`;
- повторный upgrade — no-op; downgrade/upgrade проходит на disposable DB;
- constraint tests отклоняют неверный lifecycle, checksum и вторую активную
  запись в одном slot;
- авария миграции не запускает backend;
- локальный запуск с внешним PostgreSQL и Compose-путь проверены;
- в логах/образах/frontend нет пароля или полного DSN;
- текущие 175 backend, 3 contract, 8 frontend и 77 RobCraft тестов, lint и build
  остаются зелёными;
- `git diff` не содержит staging или исходников организаторов.

## 9. Следующие миграции и переключение

### 0002 — catalog domain и importer

`manufacturers`, `catalog_source_rows`, `equipment_models`,
`equipment_applicability`, `spec_observations`, `field_evidence`,
`resolved_spec_facts`, `procurement_options` и при необходимости link-таблицы
includes/excludes. После schema/import contract выполняются validate-only,
BASE import, затем ENRICHMENT overlay и сверка 187/223/223/3635/140/156.
`resolved_spec_facts` проверяет `num_nonnulls(numeric_value, text_value,
boolean_value, json_value) = 1`, unique model/spec/scope и safe-status policy.
Пользовательские допущения хранятся отдельно от catalog facts и дают
`ASSUMED`, а не `PASS`.

### Repository и dual-run

- Ввести domain DTO и `CatalogRepository` без ORM-объектов за границей data
  layer.
- Оставить `backend/fleet` reference adapter; PostgreSQL adapter включать feature
  flag только в тесте/служебном dual-run.
- Сравнивать пересечение моделей, причины hard rejection, fleet/economics и
  canonical ScenarioSpec. Ожидаемые различия из официальных данных фиксировать,
  а не принудительно добиваться побайтового равенства разных каталогов.
- Runtime остаётся на legacy adapter, пока нет объяснённого отчёта и golden
  fixtures.

### 0003 — project/run persistence

Минимум: `users`, `projects`, `project_files`, `scenarios`, `analysis_runs` и
`audit_entries`; роли guest/user/admin без enterprise IAM. Затем сохраняются
run snapshots и version references. Только после этого выполняются catalog
activation/switch и официальный XLSX/CSV intake.

## 10. Файлы, backup, rollback и demo reset

- Файл сначала пишется во временный storage key, вычисляется SHA-256 и проходит
  size/extension/MIME/magic-byte validation; metadata коммитится атомарно,
  затем объект становится видимым. Сироты удаляет безопасный cleanup job.
- Имя пользователя не используется как путь; storage key генерируется сервером.
- Удаление проекта создаёт transactional deletion/outbox record; физическое
  удаление файла идемпотентно. Проверяется отсутствие доступа после удаления.
- Перед production/demo migration и activation выполняется `pg_dump` и backup
  каталога файлов. Alembic downgrade — проверка разработки, не основная
  production rollback-стратегия.
- Rollback релиза: вернуть приложение, атомарно активировать предыдущую
  опубликованную CatalogVersion; при несовместимой schema восстановить backup.
- Demo reset — allowlisted идемпотентная команда только для demo tenant/seed;
  она не делает `dropdb` и не трогает каталожные версии.

## 11. Секреты и пользовательские данные

- Пароли БД и приложения только в environment/secret store; production CORS и
  trusted hosts ограничены фактическим origin.
- Пароли пользователей хешируются Argon2id; сессии используют secure/HttpOnly/
  SameSite cookies и CSRF либо явно спроектированный bearer flow.
- Изоляция проекта обеспечивается owner predicate в каждом repository query и
  негативными integration tests; одного скрытия кнопки недостаточно.
- Upload имеет лимиты размера/типа, безопасный parser и нейтральные сообщения
  ошибок. В demo seed нет реальных персональных данных.
- HTTPS завершается на deployment proxy; секреты и uploaded content не
  попадают в image, логи, PDF без явного выбора или Git.

## 12. Сохранение ScenarioSpec и revision protocol

`analysis_run_id` и `revision_id` — разные идентификаторы. Revision остаётся
детерминированным hash канонического расчётного результата и включает версии
catalog/rules/economics/object-profile, но исключает DB UUID, timestamps и
storage keys. Это сохраняет воспроизводимость.

Последовательность iframe не меняется:

`READY → LOAD_SCENARIO(request_id, revision_id) → PREPARED →
APPLY_REVISION → APPLIED`.

Проверяются `origin`, `source`, protocol version, request и revision; старые
ответы игнорируются. Parent скрывает старую сцену до `APPLIED`. Перенос каталога
не должен менять same-origin `/robcraft/`, strict schema или визуальный статус
экономически неприемлемого кандидата.

Фактическая граница текущей реализации точнее: после HTTP response React уже
может показать новый экономический result, пока viewport закрыт opaque overlay
до `APPLIED`. Поэтому пользователь не видит старую 3D-сцену рядом с новыми
числами, но весь dashboard не коммитится атомарно одной операцией. Если позже
потребуется строгая атомарность всего экрана, result следует держать pending до
`APPLIED`; storage migration не должна менять это поведение скрыто.

## 13. Подтверждённый порядок работ

1. Зафиксированный baseline и traceability — текущий аудит.
2. Первая малая итерация storage control-plane (0001), без business switch.
3. Catalog domain 0002, import contract, validate-only и транзакционный importer.
4. Repository boundary и dual-run; legacy runtime остаётся default.
5. Project/scenario/AnalysisRun/file metadata 0003 и минимальные роли.
6. Atomic catalog activation/switch, официальные presets и XLSX/CSV intake.
7. Readiness, architecture и hard constraints с evidence gate.
8. Baseline/purchase/RaaS и отдельная uncertainty/sensitivity ось.
9. Обязательная 2D-визуализация и SimulationReport reconciliation.
10. PDF + Excel/CSV, сохранение визуализации и минимальная admin update/publish.
11. Security, deletion, performance, backup/reset и deployment acceptance.

Этот порядок минимизирует повторную работу: версии каталога существуют до
catalog rows; runs ссылаются на версии до runtime switch; file intake сразу
принадлежит проекту; подбор не может обойти evidence gate; 2D строится после
стабилизации расчётного и persisted ScenarioSpec.

## 14. Открытые решения перед 0002/0003

- Разрешено ли коммитить derived organizer bundle и в каком составе; до ответа
  исходники и staging остаются вне Git.
- Является ли v4 актуальной версией, какова валюта и точная семантика дублей;
  импорт обязан сохранить неопределённость.
- Какие organizer/CORROBORATED статусы допускаются к hard matching после
  reviewer approval; policy должна быть таблицей, а не условием в handler.
- Локальный filesystem volume достаточен для защиты или нужен S3-compatible
  adapter; DB contract от выбора не зависит.
- Какой минимальный auth flow показывается на защите. Роли обязательны, но
  совместный project sharing и enterprise RBAC можно отложить.
- Точные правила удаления audit metadata после удаления пользовательского
  проекта с учётом требования удалить связанные файлы.

Безопасно отложить: live scraper, scheduler автообновления, temporal history
каждого mutable user field, full IAM, object storage в облаке, все ТТХ 223
моделей, CAD/BIM и единое физическое 3D-здание. Нельзя откладывать СУБД,
project/run persistence, evidence gate, официальный intake, обязательную 2D,
commercial scenarios, exports и минимальную административную актуализацию.
