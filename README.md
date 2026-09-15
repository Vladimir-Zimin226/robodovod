# РОБОДОВОД

Платформа предварительной оценки роботизации для ЛЦТ‑2026. Пользователь описывает объект и процесс обычным языком, а прототип подбирает роботизированные решения, проверяет ограничения, рассчитывает экономику и показывает сценарий работы. Отдельный модуль RobCraft добавляет автономную интерактивную 3D-сцену.

> RobCo / «РобоМера» — прежние рабочие названия. Актуальный интерфейс демонстрационной версии — «РОБОДОВОД».

Имя репозитория и корневого каталога: `robodovod`.

## Быстрый запуск через Docker

Требование: запущенный Docker Desktop.

Из корня репозитория выполните в Git Bash, PowerShell или обычном терминале:

```bash
docker compose up --build
```

После запуска откройте <http://localhost:5173>. API доступен на <http://localhost:8000>, документация API — на <http://localhost:8000/docs>.

Остановка и последующий запуск без пересборки:

```bash
docker compose down
docker compose up
```

## Локальный запуск без Docker

Требования: Python 3.12+ и Node.js 22.12+.

### Git Bash

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm.cmd install --prefix frontend
```

Backend в первом терминале:

```bash
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

Backend в первом терминале:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload --port 8000
```

Frontend во втором терминале:

```powershell
npm.cmd run dev --prefix frontend
```

Vite проксирует `/api` на локальный backend. PowerShell иногда блокирует `npm.ps1`, поэтому используется `npm.cmd`.

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

Прототип является предварительной оценкой, а RobCraft — демонстрационной сценарной симуляцией. Они не являются инженерным проектом, офертой поставщика или откалиброванным цифровым двойником.
