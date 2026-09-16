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
- Организаторы подтвердили, что `catalog_export_v4.csv` — актуальная версия.
  Для проекта принято продуктовое решение обрабатывать его цены в RUB, хотя
  валюта не написана в исходном CSV; это решение должно иметь собственный
  provenance и не маскироваться под source fact. Неопределённым остаётся смысл
  отдельных duplicate rows.
- Коммит derived organizer bundle разрешён. Девять выбранных машинных файлов
  staging занимают суммарно около 1,84 MiB, максимальный — около 0,79 MiB.
- Staging исключён из Git и не является production-источником или runtime
  fallback.

## 3. Границы хранения

| Данные | Хранилище и правило |
|---|---|
| Каталог, применимость, typed facts, procurement и evidence | PostgreSQL, только через версионированный repository |
| Raw source rows и неоднородные snapshots | JSONB рядом с нормализованной записью, но не как единственный источник для фильтрации |
| Пользователи, проекты, сценарии, AnalysisRun и audit | PostgreSQL |
| XLSX/CSV/PDF/планы пользователей | Локальный filesystem в named volume; в БД — имя, media type, размер, SHA-256, storage key и владелец |
| Миграции, import schema, validators и разрешённый derived bundle | Git; bundle состоит из текстовых JSON/CSV, schema, manifest и README |
| Исходники организаторов и текущий staging | Локально, вне Git; импорт только явной командой |
| Секреты | Серверное окружение/secret store; никогда не frontend bundle и не Git |

SQLite не используется как production-compatible fallback: JSONB, partial
indexes, ограничения и транзакционные сценарии должны тестироваться на той же
СУБД. Локальный запуск без Docker использует внешний PostgreSQL через
`DATABASE_URL`; допустим Compose-профиль, поднимающий только БД.

### 3.1. Состав committed derived bundle

Целевой каталог: `data/import/organizer-catalog-v4/`. Bundle генерируется
детерминированно и коммитится только после validate-only. В него входят:

- `manifest.json` с schema/catalog version, hashes, sizes, counts и source
  artifact metadata;
- `catalog_products.json`, `catalog_applicability.csv`,
  `catalog_prices.csv`, `catalog_field_evidence.csv`;
- `object_profiles.json`;
- `catalog_external_enrichment.json` и
  `catalog_external_evidence.csv`;
- import JSON Schema, `README.md` с provenance/status policy и при
  необходимости machine-readable review decisions.

Исторические Markdown-отчёты, staging manifests как runtime truth, PDF/XLSX/
DOCX/CSV-исходники организаторов и внутренний audit document в bundle не
копируются. Их имена, размеры и SHA-256 находятся в manifest. Bundle хранится
как текст, не ZIP: это даёт нормальный Git diff и не требует Git LFS.

## 4. Модель данных и границы сущностей

### 4.1. Идентификаторы и natural keys

- Внутренние PK — UUID, генерируемые приложением; импорт не зависит от
  расширений PostgreSQL и последовательностей.
- `organizer_id` сохраняется отдельным nullable UUID; для `equipment_models` он
  уникален внутри версии каталога, но не является PK и не переиспользуется между
  версиями. Это ограничение не применяется к source/applicability/price rows.
- Для записи без organizer ID natural key — `(catalog_version_id,
  source_namespace, source_record_key)`.
- Исходная строка имеет ключ `(source_artifact_id, source_row_number)` и не
  схлопывается. Это сохраняет все 223 строки при 187 моделях.
- В v4 повторяются 23 `organizer_id`, охватывая 59 строк; как минимум три
  группы имеют разные цены. Поэтому `equipment_applicability` и
  `procurement_options` ссылаются на конкретную `catalog_source_row`, а их
  source-row key уникален в своей таблице. Одинаковые суммы не дедуплицируются.
  Выбранная `SolutionConfiguration` фиксирует не только model ID, но и
  applicability/offer ID, использованные в расчёте.
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

Для organizer v4 `ProcurementOption` хранит исходное текстовое значение цены,
нормализованный amount, `currency=RUB`, source row/evidence и
`vat_status=ORGANIZER_ASSUMPTION_INCLUDED`. RUB — подтверждённая владельцем
продукта политика этого набора, но не утверждение исходного CSV; manifest
derived bundle обязан это различие зафиксировать. Официальное дополнение (стр.
4) рекомендует считать цены указанными с учётом НДС до иного ответа Q&A, однако
не задаёт ставку: `vat_rate` и рассчитанная сумма НДС остаются `NULL`, а UI и
отчёт явно маркируют допущение. Доставка, пусконаладка и глубокая интеграция в
ИТ-ландшафт не включены в цену и учитываются отдельными статьями. Для других
источников валюта и VAT status не наследуются автоматически.

Полиморфная пара `target_type/target_id` не вводится. Каталожное предложение
ссылается на модель, а системное — через явную link-таблицу на конфигурацию.

## 5. Evidence gate: защита от ложных ТТХ

Импорт хранит два разных слоя:

1. `spec_observations` — все найденные утверждения, включая конфликт,
   неоднозначное совпадение модели и отрицательный результат поиска;
2. `resolved_spec_facts` — только выбранные типизированные факты, которые
   repository вообще имеет право передать matching engine.

Для resolved fact обязательны ровно одно typed value, canonical unit, источник,
дата/версия evidence, `resolution_status` и `usable_for_matching`.

«Допустить к hard matching» означает разрешить числу участвовать в проверке и
дать результат `PASS` или `FAIL`. Политика фиксируется данными:

| Evidence status | Автоматический hard matching | Условие |
|---|---|---|
| `CORROBORATED` | Да | Два официальных artifact дают одно значение |
| `CROSS_DOCUMENT_ENRICHED` | Да | Exact model mapping и прямое поле официального DOCX |
| `ORGANIZER_NAME` | Да, только для literal field | Значение и unit явно написаны в имени; без вывода новых ТТХ |
| `VERIFIED_OFFICIAL` | Да | Exact model/revision match, URL/source/date сохранены |
| `VERIFIED_AUTHORIZED_PARTNER` | После review | Reviewer, reason и timestamp обязательны |
| `MANUALLY_APPROVED` | После review | Выбран конкретный variant/evidence, сохранено решение |
| `CONFLICT`, `AMBIGUOUS_MODEL_MATCH`, `NOT_FOUND`, `UNKNOWN` | Никогда | Observation остаётся видимой, но не попадает в matching view |
| `ASSUMED` | Не как catalog fact | Хранится в проекте и даёт constraint status `ASSUMED`, не evidence `PASS` |

БД запрещает unsafe status при `usable_for_matching = true`. Организаторский
слой не перезаписывается overlay. Repository читает
`matching_spec_facts`, а не observations. При отсутствии разрешённого
critical fact constraint engine возвращает `UNKNOWN/NEEDS_VALIDATION`.

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
- текущие 179 backend, 4 contract, 8 frontend и 77 RobCraft тестов, lint и build
  остаются зелёными;
- `git diff` не содержит staging или исходников организаторов.

## 9. Следующие миграции и переключение

### 0002 — catalog domain и importer

Практическая реализация разделена на две малые итерации: сначала только
`data/catalog-domain-schema` (migration/ORM/constraints), затем отдельно
`data/catalog-validator-importer`. Наличие таблиц 0002 само по себе не включает
import и не переключает runtime repository.

`manufacturers`, `catalog_source_rows`, `equipment_models`,
`equipment_applicability`, `spec_observations`, `field_evidence`,
`resolved_spec_facts`, `procurement_options` и при необходимости link-таблицы
includes/excludes. После schema/import contract выполняются validate-only,
BASE import, затем ENRICHMENT overlay и сверка 187/223/223/3635/140/156.
`resolved_spec_facts` проверяет `num_nonnulls(numeric_value, text_value,
boolean_value, json_value) = 1`, unique model/spec/scope и safe-status policy.
Пользовательские допущения хранятся отдельно от catalog facts и дают
`ASSUMED`, а не `PASS`.

Importer tests отдельно проверяют, что v4 price сохраняет raw value, получает
RUB только с decision provenance, имеет
`ORGANIZER_ASSUMPTION_INCLUDED`, но `vat_rate=NULL`, и не включает delivery,
commissioning или deep integration в catalog price. Ни RUB, ни VAT policy не
применяются к другому source dataset без явного versioned decision.

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
`audit_entries`. Guest — неперсистентный demo-flow без сохранения
коммерчески чувствительных данных. У зарегистрированной учётной записи:
`email_normalized` unique, Argon2id password hash, optional `name`, роль
`USER|ADMIN` и status `ACTIVE|DISABLED`.

Self-registration всегда создаёт `USER`; роль нельзя выбрать в публичном API.
Admin создаёт, редактирует, отключает/удаляет пользователей и выполняет password
reset, но никогда не видит пароль/hash. Нельзя удалить/понизить последнего
активного admin. Project sharing отсутствует; каждый project имеет одного owner.
Первый ADMIN создаётся отдельным one-shot bootstrap после migration 0003 из
`BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` и optional
`BOOTSTRAP_ADMIN_NAME`. Команда идемпотентна: создаёт account только при
отсутствии ADMIN и никогда не меняет пароль существующего пользователя. Пароль
не передаётся аргументом процесса и не логируется, сохраняется только Argon2id
hash. Реальные значения находятся в локальном игнорируемом `.env`/deployment
secret; tracked `.env.example` содержит placeholders. Bootstrap без обязательных
переменных завершается ошибкой; совпадение email с существующим USER не повышает
его роль автоматически и также завершается безопасной ошибкой. Integration
tests покрывают первый запуск, повторный no-op, параллельный запуск, collision и
отсутствие секрета в логах.
Удаление пользователя сначала запускает тот же проверяемый процесс удаления его
projects/files. Затем сохраняются run snapshots и version references. Только
после этого выполняются catalog activation/switch и официальный XLSX/CSV intake.

## 10. Файлы, backup, rollback и demo reset

- Файл сначала пишется во временный storage key, вычисляется SHA-256 и проходит
  size/extension/MIME/magic-byte validation; metadata коммитится атомарно,
  затем объект становится видимым. Сироты удаляет безопасный cleanup job.
- Имя пользователя не используется как путь; storage key генерируется сервером.
- Удаление проекта немедленно переводит его в `DELETING` и закрывает чтение,
  создаёт transactional deletion/outbox record, затем идемпотентно удаляет
  локальные файлы и hard-deletes scenarios, runs, file metadata и project.
  Неуспех остаётся `DELETE_FAILED` без доступа пользователя и допускает retry.
- Full project payload, snapshots, filename, storage key и file hash из audit
  удаляются. Остаётся минимальный tombstone `PROJECT_DELETED`: opaque project
  UUID, actor UUID, timestamp и агрегированные counts без email/name/content.
  Для прототипа retention — 30 дней, затем purge; значение конфигурируется.
  Тест с управляемым временем проверяет сохранение до границы, purge после неё и
  отсутствие восстановления связи с удалённым payload/file metadata.
- Перед production/demo migration и activation выполняется `pg_dump` и backup
  локального uploads volume. Alembic downgrade — проверка разработки, не основная
  production rollback-стратегия.
- Rollback релиза: вернуть приложение, атомарно активировать предыдущую
  опубликованную CatalogVersion; при несовместимой schema восстановить backup.
- Demo reset — allowlisted идемпотентная команда только для demo tenant/seed;
  она не делает `dropdb` и не трогает каталожные версии.

Operational recovery backup создаётся серверной/CLI-командой в локальный backup
volume и не скачивается из браузера. Отдельно admin может скачать
`diagnostic-bundle.zip`: migration head, версии приложения/rules/catalog,
manifest активного bundle, import counts/status/diagnostics, integrity-check
results, redacted errors и агрегированные user/project/run/file counts.
Диагностический пакет не содержит password hashes, secret values, email/name,
uploaded binaries, filenames/storage keys или полные пользовательские snapshots;
это проверочный artifact, а не restore backup.

## 11. Секреты и пользовательские данные

- Пароли БД и приложения только в environment/secret store; production CORS и
  trusted hosts ограничены фактическим origin.
- Регистрация: обязательные email/password, optional name. Email trim/lowercase
  нормализуется и уникален; исходный пароль нигде не логируется.
- Пароли пользователей хешируются Argon2id; browser session использует
  secure/HttpOnly/SameSite cookie и CSRF. Admin/user authorization проверяется
  в service/repository, не только UI.
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

## 14. Неблокирующее открытое решение

- Точная семантика отдельных duplicate rows сверх требования сохранить каждую
  source row и рассматривать дубли как альтернативные предложения. Она не
  блокирует 0002: модель уникальна по organizer ID внутри версии, а applicability
  и procurement offer имеют identity конкретной исходной строки.

Закрыто: v4 актуален; его цены обрабатываются как RUB по продуктовому решению;
НДС считается включённым только как organizer assumption без известной ставки;
первый ADMIN создаётся one-shot bootstrap из локального `.env`; deletion
tombstone без PII/content хранится 30 дней. Ни одно из этих решений не расширяет
scope migration 0001.

Безопасно отложить: live scraper, scheduler автообновления, temporal history
каждого mutable user field, full IAM, S3/object storage, все ТТХ 223
моделей, CAD/BIM и единое физическое 3D-здание. Нельзя откладывать СУБД,
project/run persistence, evidence gate, официальный intake, обязательную 2D,
commercial scenarios, exports и минимальную административную актуализацию.
