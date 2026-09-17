# РОБОДОВОД

Платформа предварительной оценки роботизации для ЛЦТ‑2026. Пользователь описывает объект и процесс обычным языком, а прототип подбирает роботизированные решения, проверяет ограничения, рассчитывает экономику и показывает сценарий работы. Отдельный модуль RobCraft добавляет автономную интерактивную 3D-сцену.

> RobCo / «РобоМера» — прежние рабочие названия. Актуальный интерфейс демонстрационной версии — «РОБОДОВОД».

Имя репозитория и корневого каталога: `robodovod`.

## Быстрый запуск через Docker

Требование: запущенный Docker Desktop.

Один раз создайте локальный файл окружения из безопасного шаблона и замените
каждый `<...>` placeholder. Для полного Compose `DATABASE_URL` должен содержать
host `db`; пароль внутри URL должен быть URL-encoded. Роли
`POSTGRES_ADMIN_USER` и `APP_DB_USER` обязаны различаться: backend и миграции
используют только вторую, не-superuser роль.

```powershell
Copy-Item .env.example .env
```

Реальный `.env` игнорируется Git. После его заполнения из корня репозитория:

```bash
docker compose up --build
```

После запуска откройте <http://localhost:5173>. API доступен на <http://localhost:8000>, документация API — на <http://localhost:8000/docs>.
Лёгкая liveness-проверка — <http://localhost:8000/>, readiness PostgreSQL —
<http://localhost:8000/ready>. Compose ждёт `db healthy`, затем успешного
`alembic upgrade head` в одноразовом сервисе `migrate` и только после этого
запускает backend. Неуспешная миграция блокирует его старт.

Остановка и последующий запуск без пересборки сохраняют named volume PostgreSQL:

```bash
docker compose down
docker compose up
```

Не используйте `docker compose down -v`, если данные должны сохраниться.

## Локальный запуск без Docker

Требования: Python 3.12+ и Node.js 22.12+.

### Git Bash

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm.cmd install --prefix frontend
```

Для локального backend нужен внешний PostgreSQL 16. Можно запустить только БД
из Compose (сначала заполните `.env`, как выше):

```powershell
docker compose up -d db
```

В локальном терминале задайте тот же application DSN, но с host `localhost`,
выполните миграцию и запустите backend:

```bash
export DATABASE_URL='postgresql+psycopg://<application-role>:<url-encoded-password>@localhost:5432/<database-name>'
./.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
./.venv/Scripts/python.exe -m uvicorn main:app --app-dir backend --reload --port 8000
```

Frontend во втором терминале:

```bash
npm.cmd run dev --prefix frontend
```

### PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd install --prefix frontend
```

Миграция и backend в первом терминале:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://<application-role>:<url-encoded-password>@localhost:5432/<database-name>'
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload --port 8000
```

Frontend во втором терминале:

```powershell
npm.cmd run dev --prefix frontend
```

Vite проксирует `/api` на локальный backend. PowerShell иногда блокирует `npm.ps1`, поэтому используется `npm.cmd`.

Проверка обоих health-маршрутов:

```powershell
Invoke-RestMethod http://localhost:8000/
Invoke-RestMethod http://localhost:8000/ready
```

PostgreSQL migration/constraint tests требуют отдельную одноразовую БД; команда
сознательно выполняет downgrade и не должна указывать на рабочую БД:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://<application-role>:<url-encoded-password>@localhost:5432/<disposable-database-name>'
.\.venv\Scripts\python.exe -m pytest backend\test_storage_integration.py backend\test_catalog_schema_integration.py -q
```

Downgrade нужен только для одноразовой development/test БД, не вместо backup:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini downgrade base
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

## Storage control-plane 0001

Миграция `0001_storage_control_plane` создаёт только `catalog_versions`,
`source_artifacts`, `catalog_version_sources`, `import_runs` и
`catalog_activations`. UUID создаёт приложение, бинарные source-файлы в БД не
хранятся. PostgreSQL CHECK/FK/partial indexes и constraint triggers защищают
lifecycle, идемпотентность успешного импорта, единственную активную версию в
slot и неизменяемую историю активаций.

По умолчанию расчётные endpoint читают 13 JSON-записей из `backend/fleet`;
пустая мигрированная БД не меняет каталог, экономику или ScenarioSpec.
Автоматического импорта, публикации или активации при startup нет.

## Catalog domain schema 0002

Миграция `0002_catalog_domain` добавляет версионированную схему каталога:
производителей, исходные строки, модели оборудования, применимость, наблюдения
ТТХ, evidence, resolved facts и procurement options. Значения ТТХ типизированы,
unsafe evidence не допускается в `matching_spec_facts`, а данные версии после
перехода из `DRAFT` неизменяемы. Цена и её provenance хранятся отдельно от
модели оборудования.

Runtime-каталог по безопасному default продолжает использовать `backend/fleet`.

## Catalog validator/importer

Коммитнутый текстовый bundle находится в
`data/import/organizer-catalog-v4/`. Исходные PDF/XLSX/DOCX/CSV в него не
входят: `manifest.json` хранит их metadata, SHA-256 и размеры. Импортёр всегда
проверяет schema, hashes, sizes, counts, natural keys, ссылки и evidence policy
до записи domain rows.

Импорт выполняется явно и только в `DRAFT`. Обычный `docker compose up` его не
запускает. Сначала выполните validate-only, затем BASE и ENRICHMENT:

```bash
docker compose --profile tools run --rm catalog-import --phase BASE --mode VALIDATE_ONLY
docker compose --profile tools run --rm catalog-import --phase BASE --mode COMMIT
docker compose --profile tools run --rm catalog-import --phase ENRICHMENT --mode VALIDATE_ONLY
docker compose --profile tools run --rm catalog-import --phase ENRICHMENT --mode COMMIT
```

Повтор успешного `COMMIT` идемпотентен и возвращает существующий `ImportRun`.
Ошибка откатывает всю фазу, а отдельная запись `ImportRun` остаётся со
санитизированной диагностикой. Импорт не публикует и не активирует версию.

Для локального Python с внешним PostgreSQL:

```bash
export DATABASE_URL='postgresql+psycopg://<application-role>:<url-encoded-password>@localhost:5432/<database-name>'
PYTHONPATH=backend ./.venv/Scripts/python.exe -m catalog_importer --bundle data/import/organizer-catalog-v4 --phase BASE --mode VALIDATE_ONLY
PYTHONPATH=backend ./.venv/Scripts/python.exe -m catalog_importer --bundle data/import/organizer-catalog-v4 --phase BASE --mode COMMIT
PYTHONPATH=backend ./.venv/Scripts/python.exe -m catalog_importer --bundle data/import/organizer-catalog-v4 --phase ENRICHMENT --mode VALIDATE_ONLY
PYTHONPATH=backend ./.venv/Scripts/python.exe -m catalog_importer --bundle data/import/organizer-catalog-v4 --phase ENRICHMENT --mode COMMIT
```

Maintainer может детерминированно пересобрать bundle только из локального
ignored staging и проверить отсутствие расхождений:

```bash
python scripts/build_catalog_bundle.py
python scripts/build_catalog_bundle.py --check
```

## Catalog repository и dual-run

PostgreSQL adapter требует явный `catalog_version.code`, возвращает DTO без
ORM-объектов и читает ТТХ только из evidence-gated view
`matching_spec_facts`. Расчётные endpoint используют reference adapter над
`backend/fleet`, пока явно не заданы одновременно активный `runtime` slot и
`CATALOG_RUNTIME_SOURCE=activated`.

После явного BASE/ENRICHMENT import служебное сравнение запускается отдельным
Compose tools-service:

```bash
docker compose --profile tools run --rm catalog-dual-run
```

Локальный эквивалент:

```powershell
$env:CATALOG_DUAL_RUN_ENABLED = 'true'
$env:DATABASE_URL = 'postgresql+psycopg://<application-role>:<url-encoded-password>@localhost:5432/<database-name>'
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m catalog_dual_run --catalog-code organizer-catalog-v4 --fixture backend\fixtures\catalog-dual-run-warehouse-v1.json
```

JSON-отчёт сравнивает только явно сопоставленные модели по identity, hard
rejection, fleet, economics и canonical ScenarioSpec. Каждое несовпадение
получает `EXPECTED_DIFFERENCE`, `DEFECT` или `BLOCKED_BY_EVIDENCE`; имена моделей
автоматически не склеиваются. Текущий официальный каталог ожидаемо блокируется
до evidence-backed runtime projection: dual-run не подставляет отсутствующие
операционные и экономические поля из legacy. Код завершения `2` означает
необъяснённый `DEFECT`, `3` — ошибку конфигурации; expected/blocked без дефектов
завершаются кодом `0`.

## Catalog activation и официальные profiles

Lifecycle выполняется только явной tools-командой. `publish` повторно проверяет
checksums, успешные BASE/ENRICHMENT, фактические counts в БД и официальный
profile bundle, затем проводит разрешённые переходы `DRAFT → VALIDATED →
PUBLISHED`. Активация slot сериализована advisory lock, в одной транзакции
закрывает старую history row и создаёт новую:

```bash
docker compose --profile tools run --rm catalog-activation publish --catalog-code organizer-catalog-v4
docker compose --profile tools run --rm catalog-activation activate --catalog-code organizer-catalog-v4 --slot discovery
docker compose --profile tools run --rm catalog-activation status
```

`/api/catalog/models` использует активный `discovery` slot и возвращает
иерархию, поиск/фильтры/сортировку, provenance facts и `selectable`. Публичной
единицей являются все 223 исходные catalog positions; они ссылаются на 187
канонических моделей, но не схлопывают различающиеся цену, отрасль, сценарий,
регион и кейс. После активации discovery-слота позиции доступны для просмотра,
но не для расчётного выбора: bundle
пока не содержит evidence-backed `runtime_projection`. Поэтому команда
`activate --slot runtime` завершается безопасной ошибкой, а не дополняет ТТХ из
legacy. Мгновенный rollback расчётов — `CATALOG_RUNTIME_SOURCE=legacy`
(значение по умолчанию); отсутствие/ошибка активированного runtime в режиме
`activated` даёт 503 без скрытого fallback.

Официальные профили доступны через `/api/object-profiles`,
`/api/object-profiles/{type}` и `/api/object-profiles/{type}/preset`. Они
сохраняют 42/39/57 параметров склада/аэропорта/медучреждения с
default/min/max/unit/source. Проекция в текущий `UserInput` возвращает
field-level `PRESET/CALCULATED/ASSUMED` provenance; совместимый
`/api/presets/{type}` возвращает только `normalized_input`.

## Изображения официального каталога

Migration `0004_catalog_position_media` добавляет append-only metadata assets и
связи с catalog positions. Сам restricted PDF и извлечённые бинарные файлы в Git
не входят. Tools-команда сверяет PDF с зарегистрированным SHA-256, извлекает 223
карточки, дедуплицирует одинаковые изображения по содержимому и сохраняет их в
именованный `catalog_media` volume:

```bash
docker compose --profile tools run --rm catalog-media
```

По умолчанию PDF читается из локальной игнорируемой папки
`Разобрать/Материалы от организаторов/Датасет`. Другой каталог задаётся через
`OFFICIAL_CATALOG_SOURCE_DIR`. Повторный запуск проверяет metadata и
восстанавливает отсутствующие файлы volume, не изменяя append-only связи. API
возвращает media provenance до страницы/слота PDF и отдаёт content-addressed
изображения через `/api/catalog/media/{catalog_code}/{sha256}`.

## Описания позиций официального каталога

Migration `0005_catalog_description` добавляет append-only overlay
для 223 позиций. Два строгих адаптера читают локальные page-oriented и
field-oriented транскрипции, проверяют SHA-256 PDF/Markdown, порядок,
`source_page/source_slot`, название, организацию и checksum изображения.
Существующие описания не заменяются: расхождения публикуются как
`REVIEW_REQUIRED`; УГТ, стадия, market potential, кейсы и служебные метки не
попадают в runtime/matching facts.

```bash
docker compose --profile tools run --rm catalog-description --mode VALIDATE_ONLY
docker compose --profile tools run --rm catalog-description --mode COMMIT
```

Повторный `COMMIT` идемпотентен. API каталога возвращает выбранное описание,
полный overlay и provenance; расчётный runtime остаётся на `backend/fleet`.

## XLSX/CSV-файлы проекта

Авторизованный пользователь может открыть сохранённый проект, выбрать профиль
объекта и загрузить `.xlsx` или `.csv`. Preview проверяет формат, полный набор
параметров, типы, единицы и диапазоны, не изменяя проект. Apply повторно
проверяет те же bytes, сохраняет файл в `project_uploads`, фиксирует SHA-256 и
field-level `FILE/CALCULATED/ASSUMED` provenance и обновляет выбранный сценарий
одной транзакцией. Невалидный файл не создаёт `project_files` и не меняет
scenario inputs.

CSV-шаблон для каждого официального профиля доступен по
`/api/project-file-templates/{warehouse|airport|medical_facility}.csv`.
Официальный `Датасеты_хакатон.xlsx` остаётся локальным и не добавляется в Git;
его warehouse-лист детерминированно даёт тот же нормализованный `UserInput`,
что и официальный preset.

## Пользователи, проекты и AnalysisRun (migration 0003)

Гостевой `/api/calculate` по-прежнему работает без регистрации и ничего не
сохраняет. После регистрации пользователь получает изолированные проекты,
три сценарных слота (`BASE`, `OPTIMISTIC`, `PESSIMISTIC`) и immutable snapshots
расчётов. Повторное открытие читает сохранённый snapshot, а rerun создаёт новую
запись. Default runtime использует `backend/fleet`; каждый новый AnalysisRun
фиксирует code и, для PostgreSQL-каталога, UUID реально разрешённого request
snapshot. Переключение версии после расчёта не меняет сохранённый результат.

Первый ADMIN создаётся только явной one-shot командой после миграции. Реальные
значения должны находиться в игнорируемом `.env`, а не в Git:

```bash
docker compose --profile tools run --rm admin-bootstrap
```

Команда идемпотентна, не меняет существующий пароль и не повышает USER при
совпадении email. В интерфейсе аватар открывает вход/регистрацию; после входа
доступны «Мои проекты», а для ADMIN — экран «Пользователи» с созданием,
изменением роли/статуса, сбросом пароля и удалением. Последнего активного ADMIN
нельзя удалить, отключить или понизить.

Удаление проекта закрывает доступ, удаляет локальные файлы из named volume и
hard-deletes payload/scenarios/runs. Минимальный tombstone без PII и имён/ключей
файлов хранится 30 дней. Плановая очистка запускается явно:

```bash
docker compose --profile tools run --rm persistence-maintenance purge-deletion-tombstones
```

Для локального HTTP `SESSION_COOKIE_SECURE=false`; за HTTPS-прокси значение
обязательно переключается на `true`. Изменяющие запросы защищены CSRF-токеном,
пароли хешируются Argon2id, а owner predicate применяется в каждом project/run
query.

## Автономный запуск RobCraft

RobCraft не требует запуска backend, frontend, Docker или загрузки зависимостей:

```powershell
node .\robcraft\server.mjs
```

Откройте <http://127.0.0.1:4174>. Подробности находятся в [документе движка](docs/13_ROBCRAFT_ENGINE.md) и [локальном README](robcraft/README.md).

## Проверка перед выступлением

```powershell
# frontend
npm.cmd run lint --prefix frontend
npm.cmd run build --prefix frontend

# backend
.\.venv\Scripts\python.exe -m compileall backend
```

Для работы демо интернет и LLM-ключи не обязательны: интервью имеет локальный fallback, а расчёты выполняются детерминированно. Для YandexGPT можно перед стартом backend задать `YC_FOLDER_ID` и `YC_API_KEY` в окружении.

## Структура

```text
backend/       FastAPI API, расчётный движок, тесты и категорийный каталог fleet/
frontend/      React/Vite интерфейс и визуализация
robcraft/      автономный браузерный 3D-движок сценарной симуляции
compose.yaml   запуск всего демо через Docker Compose
docs/          продуктовые и технические спецификации
research/      исходные исследовательские отчёты и их индекс
examples/      примеры входных данных и записей каталога
project.json   машиночитаемый манифест концепции
```

## Документы

- [Контекст проекта](docs/PROJECT_CONTEXT.md) — единая точка входа: задача, ценность, состояние прототипа, ограничения и ближайшие решения.
- [Обзор продукта](docs/01_PROJECT_OVERVIEW.md) — vision, пользователи, JTBD и scope.
- [Спецификация](docs/02_PRODUCT_SPEC.md) — целевая предметная модель и логика.
- [Архитектура](docs/05_TECHNICAL_ARCHITECTURE.md) — целевая, а не полностью реализованная архитектура.
- [Сценарий демо](docs/08_DEMO_AND_ACCEPTANCE.md) — golden path и критерии готовности.
- [План доработки](docs/12_IMPLEMENTATION_PLAN.md) — этапы реализации, приоритеты и Definition of Done.
- [Хранение данных и интеграция каталога](docs/17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md) — порядок PostgreSQL → схема/импортёр → проверенное подключение официальных данных.
- [Контекст RobCraft](docs/13_ROBCRAFT_ENGINE.md) — состояние 3D-движка, контракт, ограничения и путь интеграции.
- [План интеграции RobCraft](docs/15_ROBCRAFT_INTEGRATION_PLAN.md) — непрерывный автопоказ, необязательное ручное управление, экономический HUD, ScenarioSpec и этапы замены 2D-визуализации.
- [Changelog v0.3](docs/00_CHANGELOG_V0.3.md) — появление standalone RobCraft и изменение границы simulation claims.
- [Индекс исследований](research/README.md) — навигация по материалам и статус доказательности.

## Что уже работает

- выбор сценария: склад, аэропорт или клиника;
- AI-интервью с локальным fallback без внешнего API;
- подбор из локального каталога и объяснимые отказы по ограничениям;
- расчёт всего объекта или нескольких независимых функциональных зон;
- строгий версионированный `ScenarioSpec v1` с общей ревизией расчёта и сцены;
- fleet sizing, CAPEX/OPEX, TCO, payback, NPV и what-if на горизонте 5–10 лет;
- отдельный учёт заменяемого, высвобождаемого и остающегося на пульте персонала;
- типизированный каталог из 13 решений в пяти категориях;
- встроенная same-origin 3D-визуализация RobCraft с отдельными концептуальными сценами зон транспорта, клинической доставки, уборки и паллетизации, синхронизацией по `revision_id`, зональным редактором, динамичным автопоказом и скоростью ×1/×2/×4;
- визуализация технически допустимого `NO_ACCEPTABLE_ECONOMICS` без назначения `is_best`: отрицательный статус и пометка «не рекомендация» сохраняются;
- автономный RobCraft: процедурные 3D-сцены склада, аэропорта и больницы, режиссёрская камера, вид от первого лица, физические корпуса и сценарные KPI;
- формирование PDF-отчёта в браузере.
- visualization-first dashboard в тёмной industrial-tech системе: рабочий sidebar,
  command input, readiness, реальные KPI, экономические сценарии, baseline/target,
  ресурсы и адаптивные desktop/mobile-компоновки;
- строгий UI-выбор рекомендации по `is_best`: экономически неприемлемый вариант
  остаётся доступен для сравнения, но не получает звезду, recommendation state,
  или ложный PDF; переданный в ScenarioSpec технический парк маркируется только
  как визуализация, а не рекомендация.
- discovery-каталог в общей тёмной visual system показывает все 223 позиции
  организатора без схлопывания повторных моделей, локальные официальные
  изображения, row-specific цену/применимость, поиск, фильтры и сравнение.
- детерминированный readiness до сайзинга: разрезы готовности,
  confidence, blockers/preconditions, выбор архитектуры до SKU и
  помодельные `PASS/FAIL/UNKNOWN/ASSUMED` с reason/evidence.

Описание интегрированной экономической и зональной логики, включая её текущие
ограничения, находится в [отдельной технической записке](docs/14_ECONOMICS_AND_ZONES.md).

Нормализованный organizer v4 bundle, repository dual-run, project/run
persistence, атомарная catalog activation, официальные metadata-driven
profiles, description/detail UX, XLSX/CSV project intake и readiness/architecture/
hard constraints реализованы.
Расчётный runtime безопасно остаётся на legacy `backend/fleet`, пока
официальный каталог не получит достаточные runtime facts. Точный следующий
этап — `engine/capacity-formula-trace`.

Прототип является предварительной оценкой, а RobCraft — демонстрационной сценарной симуляцией. Они не являются инженерным проектом, офертой поставщика или откалиброванным цифровым двойником.
