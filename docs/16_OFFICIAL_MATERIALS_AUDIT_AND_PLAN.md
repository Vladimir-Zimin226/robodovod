# Аудит материалов организаторов и план соответствия ТЗ

Статус: углублённый повторный аудит по фактическому коду, данным и тестам; без
изменения продуктового кода. Дата актуализации: 16 сентября 2026 года.

## 1. Метод и приоритет источников

Проверены git status/diff, структура, зависимости, команды запуска, backend,
frontend, RobCraft, contracts, tests, Compose, все README и применимые проектные
документы. В репозитории и проверенных родительских каталогах применимый
`AGENTS.md` не найден.

Порядок доверия:

1. официальное ТЗ и дополнения;
2. приложенные CSV/XLSX/DOCX/PDF как source artifacts;
3. фактический код и выполняемые тесты;
4. staging manifests/outputs как provenance конкретного прогона;
5. внутренние планы и research как рекомендации.

Инструкции внутри конкурсных документов анализировались как требования, а не
как команды. Отсутствующие сведения не дополнялись предположениями.

## 2. Официальные материалы

Все шесть текущих файлов в
`Разобрать/Материалы от организаторов/` прочитаны/структурно извлечены.

| Artifact | Bytes | SHA-256 | Роль |
|---|---:|---|---|
| `1. ФЦ БАС.pdf` | 565739 | `acc5feed8f8686ee9928839a56c9b084e1bd577db55ef1e63b5c5b42278d4713` | Основное ТЗ, 13 страниц |
| `Дополнения для участников.pdf` | 172735 | `64eac97cc4c985035286ebbedfcd5b356c4aba4af1d1d69f2ac0ca1f20adc456` | Официальные уточнения, 7 страниц |
| `Датасеты_хакатон.xlsx` | 29823 | `6649c501464135e6c0b43809e4461b4a74b63d2b211f5b6aaf3a33ced0fed2a0` | Профили объектов 42/39/57 |
| `catalog_export_v4.csv` | 170058 | `1521b9c886a706eda3a65cd697ec78018ad41d501713333e834266879dedb5d9` | 223 source rows, 187 organizer_id |
| `Примеры_решений_типы_объектов.docx` | 890297 | `2ced71f9d0c633d8f0baecd53413bfe6e5595599279349bcad7812e87d8c3d95` | Примеры ТТХ и источников |
| `ФЦ БАС — Каталог внедрения 2008 1247.pdf` | 84906007 | `9567641d3a3a7bed9d2e470240b17cefacba047257b5f0b4a5311c159c580369` | 91 страница, визуальный каталог |

PDF-каталог содержит девять разделов и 223 карточки:
48+28+22+19+20+25+21+28+12. Это согласуется с CSV. Для точных значений
приоритетны CSV/XLSX, потому что текстовый слой PDF имеет повреждённую
кодировку и визуальную раскладку.

Организаторы отдельно подтвердили, что `catalog_export_v4.csv` — актуальная
конкурсная версия. Коммит derived organizer bundle разрешён. Планируемый
текстовый JSON/CSV bundle занимает около 1,84 MiB, крупнейший файл — около
0,79 MiB; source binaries в него не входят.

### Подтверждённые официальные обязанности

Единый путь:

`объект → ручной ввод/XLSX/CSV → подбор/сравнение → экономика →
sensitivity → 2D → сохранение → PDF и Excel/CSV`.

Обязательны guest/user/admin, CRUD/copy/delete проектов, минимум три сценария,
повторное открытие с версиями, иерархический каталог и ручная admin-актуализация,
source/date/confirmation для характеристик, explainable hard constraints,
baseline/purchase/RaaS, TCO минимум 5 лет, sensitivity минимум по трём
параметрам, 2D и controls, СУБД, Docker, изоляция проектов, защищённые пароли,
HTTPS при deployment и удаление файлов проекта. 3D — дополнение, не замена 2D.

## 3. Проверка staging и enrichment

`data/staging/` исключён из Git и не является runtime/production source.
Проверка выполнена независимо по JSON/CSV, а не только по Markdown-отчётам.

### 3.1. Normalization

| Инвариант | Фактический результат |
|---|---:|
| Products / unique organizer_id | 187 / 187 |
| Applicability / price rows | 223 / 223 |
| Source row range | 2..224 без потери строк |
| Field evidence | 3635 |
| Missing product refs | 0 |
| Object parameters | warehouse 42, airport 39, medical 57 |
| Aggregate specs / corroborated / conflicts | 65 / 2 / 0 |
| Requirements | 174 TZ + 37 ADD + 40 INTERNAL |
| Correction QA | все перечисленные invariants PASS |

Пять официальных source hashes старого normalization run совпадают с текущими
файлами. Manifest также фиксирует историческую копию docs/16; текущий документ
после этого аудита закономерно имеет другой hash и не должен подменять старый
input. 91-страничный PDF появился в текущем наборе после того normalization run:
его отсутствие в source register — корректная историческая provenance, но для
следующего импорта PDF нужно зарегистрировать новым `source_artifact`.

### 3.2. Enrichment-run-1

Все восемь input hashes из `external_enrichment_manifest.json` совпадают с
текущими файлами staging.

| Уровень | VERIFIED_OFFICIAL | AMBIGUOUS_MODEL_MATCH | CONFLICT | NOT_FOUND | Всего |
|---|---:|---:|---:|---:|---:|
| Overlay fields | 75 | 7 | 6 | 52 | 140 |
| Evidence rows | 84 | 8 | 12 | 52 | 156 |

Обработано 11/11 P0 products, unique source IDs — 19, review queue — 8,
authorized-partner verified — 0. Все overlay organizer IDs существуют в base;
missing refs — 0. Result `PARTIAL` означает покрытие 60 из 125 целевых
недостающих полей verified-значениями, а не сбой self-check.

Автоматически допустимы только разрешённые verified statuses. AMR100 остаётся
model-match ambiguity; RoboCV и SmartCube имеют официальные конфликты; H1500
имеет вероятную revision difference. Эти строки нельзя материализовать как
matching truth.

## 4. Фактическая архитектура проекта

### Сильные стороны

- Детерминированное расчётное ядро с fleet size, CAPEX/OPEX, TCO, ROI, NPV и
  payback.
- Экономические статусы не создают ложную рекомендацию; frontend выбирает
  recommendation по `is_best`, а не по позиции массива.
- Whole-object и zonal режимы; strict `ScenarioSpec v1` в Python/JSON
  Schema/JavaScript.
- Same-origin RobCraft с проверкой origin/source, двумя фазами
  `PREPARED → APPLY_REVISION → APPLIED`, multi-zone representative scenes,
  движением, очередями, зарядкой, отказами, ScenePatch и KPI.
- Три пользовательских preset и локальный fallback без LLM.
- Реальный baseline: 179 backend, 4 contract, 8 frontend и 77 RobCraft tests;
  frontend lint/build и `docker compose config` проходят.

### Ограничения кода

- `backend/fleet/__init__.py` синхронно загружает 13 JSON-моделей в globals;
  `backend/main.py` использует их напрямую. Нет repository или persistence.
- `backend/models.py` требует числовые robot specs и не умеет представить
  field-level UNKNOWN/evidence. `backend/economics.py` применяет defaults и
  имеет только базовый набор hard checks, а не полную матрицу ТЗ.
- Текущие presets не совпадают с официальными значениями XLSX.
- Нет users/projects/files/AnalysisRun, auth, XLSX/CSV intake, admin update,
  PostgreSQL, Alembic, migrations, CI, backup/reset.
- Нет обязательной 2D. `backend/simulation.py` выдаёт legacy illustrative data,
  но текущий UI использует RobCraft и не предоставляет требуемый 2D flow.
- RobCraft telemetry не возвращается как versioned SimulationReport в основной
  результат.
- Opaque overlay скрывает старую 3D-сцену до `APPLIED`, но React может показать
  новый economics result раньше; это не атомарный commit всего dashboard.
- `pessimistic/base/optimistic` — uncertainty scenarios; baseline/purchase/RaaS
  отсутствуют как отдельная коммерческая ось.
- PDF — client-side и неполный; zonal report зависит от CDN-шрифта. Excel/CSV
  export отсутствует.
- Compose содержит только backend/frontend. Target stack в docs/05 ещё не
  реализован.

## 5. Traceability главных требований

Итерации соответствуют docs/12; схема и constraints этапов 1–4 — docs/17.

| Официальное требование | Текущее состояние | Подтверждение | Разрыв | Приоритет / итерация | Критерий приёмки |
|---|---|---|---|---|---|
| TZ-003, TZ-012: единый flow и официальные demo sets | Три preset и рабочий legacy flow | `frontend/src/App.jsx`, `backend/main.py` | Presets не из XLSX, flow не сохраняется | P0 / 5 | Warehouse preset равен нормализованному XLSX; airport/medical datasets доступны |
| TZ-013, TZ-032–034: manual + XLSX/CSV, range/unit/source | Ручной урезанный input; изображение плана | `frontend/src/components/IntakeScreen.jsx`, `FloorplanUploader.jsx` | Нет табличного intake и официальной validation metadata | P0 / 5 | Happy/error fixtures; invalid file не меняет проект |
| TZ-006–007, TZ-020–025: роли, projects, ≥3 scenarios, reopen | Только состояние React и декоративный пользователь | `frontend/src/App.jsx`; таблиц/API нет | Полный обязательный разрыв | P0 / 4 | Guest demo без хранения; USER registration email/password + optional name; project isolation, три сценария, reopen immutable run |
| TZ-036–051, ADD-020/023: catalog, TTX, provenance | Runtime 13 generic JSON; staging 187/223 готов вне runtime | `backend/fleet/*.json`, staging manifests | Нет official catalog repository/evidence gate | P0 / 2–5 | 187/223/223 импортированы; unsafe statuses исключены из matching |
| TZ-041–043, TZ-011/024: admin add/edit/update | Нет | Нет route/UI/table | Минимальная admin-функция ошибочно была P1 | P0 / 9 | Admin правит DRAFT, validates, publishes/activates; published immutable |
| TZ-052–058: fit, reasons, missing data, forced compare | Есть базовые rejects/forced warning | `backend/economics.py`, `backend/models.py`, backend tests | Нет полного PASS/FAIL/UNKNOWN/ASSUMED и field evidence | P0 / 6 | Critical FAIL блокирует; critical UNKNOWN → NEEDS_VALIDATION |
| TZ-059–077, ADD-026–027: quantity, CAPEX/OPEX/effect/payback/ROI/TCO | Сильная deterministic база | `backend/economics.py`, immutable fixtures v1/v2; официальное дополнение, стр. 4 | Cost boundary/procurement/overrides неполны | P0 / 7 | Formula trace, ≥5-year TCO; v4 price в RUB с decision provenance; НДС included-assumption без ставки; доставка/пусконаладка/deep integration отдельно |
| TZ-008, ADD-019: baseline/purchase/RaaS | Нет требуемой коммерческой оси | Текущие `scenarios` в API/economics | Uncertainty ошибочно может выглядеть как коммерческие сценарии | P0 / 7 | Все три сценария в одной таблице на одинаковых метриках |
| TZ-078: sensitivity ≥3 | What-if controls есть, formal output нет | Frontend params/results | Нет зафиксированного sensitivity result | P0 / 7 | Equipment price, volume, labor cost дают delta и сохраняются в run |
| TZ-018, TZ-083–086: обязательная 2D и controls | Нет; есть дополнительный 3D | `frontend/src/components/RobCraftFrame.jsx`, `robcraft/` | 3D не закрывает requirement | P0 / 8 | 2D zones/routes/robots/operations/charging + start/pause/restart/speed/scenario |
| TZ-009, TZ-085: simulation подтверждает KPI | RobCraft считает KPI локально | `robcraft/src/simulation.js` | Нет SimulationReport/reconciliation | P0 / 8 | Required vs observed и verdict с fixed measurement window |
| TZ-019, TZ-088–090: PDF, Excel/CSV, visualization export | Частичный PDF | `frontend/src/utils/generateReport.js`, `generateZonalReport.js` | Нет spreadsheet/visual export; provenance неполна | P0 / 9 | Экспорты воспроизводят snapshot и открываются offline |
| TZ-107: постоянная СУБД | Нет | `compose.yaml`, `backend/requirements.txt` | Полный разрыв | P0 / 1–4 | PostgreSQL migration + persisted project/run |
| TZ-105–109: Docker, reproducibility, OpenAPI | Два контейнера, FastAPI OpenAPI | Dockerfiles, `compose.yaml`, `/docs` framework route | Нет DB/migrate service и versioned business API | P0 / 1, 10 | Clean Compose; migration failure blocks backend; API documented |
| TZ-111: offline resilience | Core/RobCraft работают локально | fallback code, RobCraft zero runtime deps | CDN-шрифт и optional LLM path требуют проверки | P0 / 9–10 | Full demo без внешней сети; local assets |
| TZ-113–116: 50 users, ≤10 s economy, ≤60 s model + status | Не измерено; sync calc быстрый локально | Unit tests не load tests | Нет зафиксированного fixture/load/status | P0 / 10 | Reproducible smoke с отчётом времени и видимым status |
| TZ-117: upload error не теряет project | Нет project/file intake | Отсутствующие routes/tables | Полный разрыв | P0 / 4–5 | Transactional negative upload test |
| TZ-118–123: access, hash, isolation, HTTPS, delete files | Нет auth/persistence | Нет реализации | Полный разрыв | P0 / 4, 10 | Argon2id/cookie+CSRF, cross-user denial, HTTPS, deletion state/outbox, hard delete payload/files; tombstone без PII/content удаляется через 30 дней |
| OWNER-001: admin user CRUD, bootstrap и diagnostic download | Нет | Подтверждённое продуктовое решение | Нужны admin API/UI, one-shot bootstrap и безопасный формат export | P0 / 4, 10 | Первый admin идемпотентно создаётся из `.env`; admin управляет USER, не может удалить последнего admin; скачивает sanitized diagnostic bundle без secrets/PII/password hashes |
| TZ-132, TZ-140–144: demo/docs/sources/limitations | README и внутренние docs сильны | `README.md`, `docs/`, `research/` | Нет user/admin guide и полного official E2E artifact | P0 / 10 | Полный demo на organizer dataset + комплект документации |

## 6. Архитектурный вердикт

Направление PostgreSQL/SQLAlchemy/Alembic оправдано обязательной СУБД,
project persistence и воспроизводимостью. Но прежняя идея одной большой первой
миграции переусложняла старт. Исправленный порядок:

1. `0001_storage_control_plane`: версии, artifacts, imports, activation.
2. `0002_catalog_domain`: source rows, models, applicability, observations,
   evidence, resolved facts, procurement; importer.
3. Repository boundary и dual-run при legacy default.
4. `0003_project_run_persistence`: users/projects/files/scenarios/AnalysisRun.
5. Только затем activation/switch, official profiles и XLSX/CSV intake.
6. Readiness/constraints/capacity.
7. Baseline/purchase/RaaS и sensitivity.
8. 2D + SimulationReport.
9. Exports + minimal admin.
10. Security/performance/deployment acceptance.

Это минимизирует повторную работу: file intake сразу принадлежит проекту,
AnalysisRun с самого переключения знает catalog/rules versions, а evidence gate
существует до нового matching. Полный contract-v1 refactor до БД не нужен.

Первая следующая итерация — только
`infra/postgres-storage-control-plane`. Её точный scope, пять таблиц,
constraints, local/Compose/CI path и Definition of Done находятся в docs/17.

## 7. Противоречия и пробелы документов

### Между официальными источниками

- Дополнение называет `catalog_export_v5` и Excel с ценами; фактически дан v4
  CSV. Организаторы подтвердили актуальность v4, поэтому version question закрыт,
  но расхождение имён сохраняется в provenance.
- Валюта в исходном файле не указана; для проекта принято отдельное продуктовое
  решение трактовать цены v4 в RUB, не приписывая это источнику. Официальное
  дополнение (стр. 4) рекомендует считать цены указанными с учётом НДС, если Q&A
  не уточнит иное; ставка не задана, поэтому это organizer assumption, а не
  проверенный атрибут каждой строки. Доставка, пусконаладка и глубокая IT
  integration из цены исключены.
- Дубли organizer_id названы альтернативными предложениями, но в CSV часть
  дублей явно различается применимостью/отраслью. Фактически 23 identifier
  повторяются в 59 из 223 строк; как минимум три группы содержат разные цены.
  Строки нельзя схлопывать, а расчёт должен ссылаться на конкретные
  applicability и price offer.
- XLSX legend задаёт более широкий CAPEX boundary, чем краткая формулировка
  дополнений; выбранный состав должен быть явным и единым.
- XLSX не содержит required/optional flags. Их нельзя выдумывать.

### Между внутренними документами и кодом

- docs/08 и docs/11 заявляли текущую 2D-визуализацию, но UI её не содержит;
  формулировки исправлены этим аудитом.
- docs/06 описывает целевой `/api/v1`, тогда как код реализует legacy
  `/api/*`.
- docs/07 помечал часть iframe-интеграции как NEXT; статус исправлен.
- docs/13 ставит развитие 3D ближе обязательных конкурсных разрывов; docs/12
  теперь задаёт обратный приоритет.
- docs/15 — исторический integration plan: раздел «ближайшая работа» уже
  выполнен и не должен управлять новым backlog.
- PROJECT_CONTEXT называл embedded flow одно-зональным; контекст исправлен по
  коду и multi-zone tests.
- docs/05 корректно описывает target architecture, но без явной маркировки его
  легко принять за существующую реализацию; current-state evidence выше
  приоритетнее.

## 8. Что отсутствовало или было неверно приоритизировано

- Минимальная admin-актуализация обязательна и не может целиком оставаться P1.
- RaaS обязателен как коммерческий сценарий; airport/RaaS нельзя объединять в
  один опциональный пункт.
- Сохранение визуализации, status длительной операции, удаление project files,
  user/admin guides и нагрузка до 50 пользователей раньше не имели ясной
  итерации.
- Projects/AnalysisRun стояли после economics, из-за чего persisted snapshots
  пришлось бы добавлять задним числом.
- XLSX/CSV intake стоял до project file boundary, что создавало временное
  хранение.
- Big-bang «catalog schema + importer + switch» затруднял rollback и скрывал
  дефекты миграции.
- Новый `/api/v1` и полная раскладка backend по папкам до storage/data contract
  преждевременны. DTO вводятся у фактической repository/domain границы.

## 9. Скрытые миграционные риски

1. 187 models нельзя получить удалением 36 duplicate rows: нужно сохранить 223
   source/applicability/price records.
2. Organizer UUID — natural source ID, а не глобальный PK всех версий.
3. Цена без валюты непригодна для economics; RUB разрешён для organizer v4
   только по зафиксированному продуктовому решению, а не как неявный default для
   любого источника. Ставку и сумму НДС выводить из допущения запрещено.
4. EAV observation без отдельного resolved-fact gate позволит случайно читать
   CONFLICT/NOT_FOUND как значение.
5. Failure audit и domain import в одной транзакции уничтожат diagnostics при
   rollback.
6. Mutable `is_active` без history/partial uniqueness допускает две активные
   версии и ломает reopen.
7. Автоматический import при backend startup сделает deploy неидемпотентным.
8. Alembic downgrade не заменяет backup/restore production data.
9. Файлы в container filesystem исчезнут при redeploy; bytea раздует БД.
10. DB UUID/timestamp внутри revision hash сломает детерминированность и
    двухфазный iframe protocol.
11. ORM objects за repository boundary свяжут domain и lifecycle session.
12. SQLite tests дадут ложную уверенность для JSONB/partial indexes/PostgreSQL
    constraints.

## 10. Где код сильнее и слабее документации

Сильнее:

- RobCraft уже multi-zone и значительно богаче старых планов; 77 тестов
  подтверждают сценарии, physics-like safety, editor и revision binding.
- Двухфазный protocol, strict schemas и stale-request protection реализованы.
- Экономика и запрет ложной рекомендации лучше, чем отражено в части старых
  backlog-статусов.

Слабее:

- target storage/API/component architecture существует только в docs.
- Текущий hard filtering использует немного полей и silent defaults; это не
  официальный constraint engine.
- Текущие generic models/prices и presets слабее organizer data.
- RobCraft KPI ещё не являются доказательством calculation throughput.
- Client state/PDF не обеспечивают project reproducibility и required exports.

## 11. Безопасно отложить

Live scraper и scheduler, все ТТХ 223 моделей, CAD/BIM, unified physical 3D,
полный route optimizer, S3/object storage, collaborative projects,
enterprise IAM, дополнительные регионы и одинаково глубокие airport/clinic
ветки. Нельзя откладывать evidence correctness, storage/persistence, официальный
intake, commercial scenarios, sensitivity, 2D, exports, minimal admin и
security/deployment acceptance.

## 12. Неблокирующие открытые решения

- Точная семантика отдельных duplicate rows сверх обязательного сохранения
  каждой source row и трактовки дублей как альтернативных предложений. Она не
  блокирует schema/import: identity модели и конкретное предложение разделены.

Закрыты решения: v4 актуален; derived text bundle разрешён; цены v4
обрабатываются в RUB по продуктовому решению; НДС включён как допущение
организаторов без известной ставки; P0 использует PostgreSQL + local named
volumes без S3; guest не персистентен, USER регистрируется по email/password с
optional name, ADMIN управляет пользователями; первый ADMIN создаётся
идемпотентным one-shot bootstrap из локального `.env`; retention минимального
deletion tombstone — 30 дней; project sharing отсутствует. Evidence policy
приведена таблицей в docs/17.

Ни одно из этих решений не блокирует migration 0001: она не импортирует данные,
не включает auth и не меняет runtime.

## 13. Итоговый Definition of Done аудита

- официальные материалы и staging проверены по фактам/counts/checksums;
- главные requirements связаны с кодом, gap, priority, iteration и acceptance;
- docs/12, docs/16 и docs/17 задают один порядок;
- первая итерация мала, обратима и не меняет расчёт;
- schema boundaries, lifecycle, evidence gate, import transaction, files,
  backup/reset, local/Compose/CI и security зафиксированы;
- обязательные функции не смешаны с P1/CUT;
- остающиеся вопросы названы вопросами, а не заполнены догадками.
