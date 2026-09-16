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

Текущие расчётные endpoint по-прежнему читают 13 JSON-записей из
`backend/fleet`; пустая мигрированная БД не меняет каталог, экономику или
ScenarioSpec. Автоматического импорта при startup нет.

## Catalog domain schema 0002

Миграция `0002_catalog_domain` добавляет версионированную схему каталога:
производителей, исходные строки, модели оборудования, применимость, наблюдения
ТТХ, evidence, resolved facts и procurement options. Значения ТТХ типизированы,
unsafe evidence не допускается в `matching_spec_facts`, а данные версии после
перехода из `DRAFT` неизменяемы. Цена и её provenance хранятся отдельно от
модели оборудования.

Runtime-каталог и расчётные endpoint продолжают использовать `backend/fleet`.

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

Описание интегрированной экономической и зональной логики, включая её текущие
ограничения, находится в [отдельной технической записке](docs/14_ECONOMICS_AND_ZONES.md).

Нормализованный organizer v4 bundle и внешний P0 enrichment проходят строгий
validate/import в PostgreSQL, но runtime всё ещё использует legacy
`backend/fleet`. Следующий этап — repository boundary и контролируемый dual-run;
его границы описаны в
[решении о хранении данных](docs/17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md).

Прототип является предварительной оценкой, а RobCraft — демонстрационной сценарной симуляцией. Они не являются инженерным проектом, офертой поставщика или откалиброванным цифровым двойником.
