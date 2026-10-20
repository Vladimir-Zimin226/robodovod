# РОБОДОВОД — передача после функционального прохода 20.10.2026

Этот файл фиксирует **проверенное состояние**, а не объявляет основной пакет полностью готовым. Рабочее дерево содержит накопленные изменения нескольких предыдущих проходов и много untracked файлов; перед новой сессией проверить `git -c safe.directory='<repo>' status --short`, не удалять их автоматически. Сам архив `ROBODOVOD_VISUAL_POLISH_V1_CODEX_2026-10-20.zip` в текущем репозитории не найден: следующая сессия должна получить его от пользователя.

## Фактическая матрица 20 задач

| ID | Статус | Основание и остаток |
|---|---|---|
| 01 | PASS | Карта исходного кода в `codex-phase-a-2026-10-20.md`. |
| 02 | PASS | Ролевые API и guest/member parity: backend unit. |
| 03 | PARTIAL | Guest navigation smoke 3/3 и legacy URL работают; матрица всех ролей/старых входов в production не пройдена. |
| 04 | PASS | Главная, три объекта, примеры и runtime trailer: `phase_a_browser_smoke.py`. |
| 05 | PARTIAL | Три пятишаговые гостевые воронки проходят; production сквозной run с каталогом/БД не проверен. |
| 06 | PASS | 35 пар ролей и safety gates проверены в ролевых тестах. |
| 07 | PARTIAL | Payload/UNKNOWN gates покрыты unit; полная модель ТТХ и production инвалидация ранних шагов не доказаны. |
| 08 | PASS | `SceneModel` общий для 2D/3D, IDs и footprints проверены. |
| 09 | PARTIAL | Существующий серверный scene simulation учитывает путь, препятствие, очередь и зависимый парк/NPV; production e2e и все многороботные конфликты не доказаны. |
| 10 | PARTIAL | 21 GLB установлен и загружается; высокодетальный art pass/FPS оставлены VISUAL POLISH V1. |
| 11 | PASS | Purchase/RaaS, what-if и горизонты проверены существующими frontend/backend тестами. |
| 12 | PARTIAL | Общий `ReportViewModel`, PDF данные и извлекаемый текст проверены; печатная визуальная приёмка/пустые страницы — следующая сессия. |
| 13 | PASS | Runtime trailer и 180-секундный master, playback smoke. |
| 14 | PARTIAL | Общий ScenePatch, каталог, touch, save/reopen, комнаты и проёмы работают; последствия удаления прочих связанных элементов требуют полного UI/QA прохода. |
| 15 | PARTIAL | CHARGE/WORK/DROPOFF, назначение грузового робота, path collision, Play/Pause, ×1/×2/×4, follow, 2D/3D, stop/reroute и сохранение работают. Другие типы заданий/многороботные сценарии не закрыты. |
| 16 | PARTIAL | ASCII DXF LINE/LWPOLYLINE из трёх fixtures → редактируемые 2D/2.5D стены и препятствия, collision, save/reopen. ARC/INSERT/POLYLINE, серверный parser, CAD-проёмы и более сложные чертежи не реализованы. |
| 17 | PARTIAL | Сценарная live economics считает парк, ограниченную спросом выработку, FTE, ФОТ, CAPEX/OPEX, payback, ROI/NPV 5/10. RaaS, варианты, график и одностраничный экспорт отсутствуют; цены только пользовательские. |
| 18 | PARTIAL | Непредвыбранное согласие, серверный version gate, audit timestamp и ссылка в профиле есть. `privacy-policy.html` — **проект** без реквизитов оператора; юридическое согласование обязательно перед публичной регистрацией. |
| 19 | PARTIAL | Текущий touch RobCraft 360/390/768 smoke проходит; полный mobile pass приложения/PDF оставлен VISUAL POLISH V1. |
| 20 | PARTIAL | Локальные тесты/браузерные smoke проходят; PostgreSQL integration и production/staging runtime не подтверждены. |

## Сделано в этой сессии

- Довершены управление движением RobCraft и сохранение текущей позиции при перестройке. При недоступной новой трассе робот стоит на месте; удаление размещённого робота снимает назначение.
- Добавлен локальный ограниченный ASCII DXF импорт с выбранными слоями, единицами, высотой стен, предупреждениями и provenance в ScenePatch. Все три package fixtures импортируются, переключаются в 3D и локально открываются повторно.
- Добавлена отдельная live economics RobCraft. Вводные сохраняются в ScenePatch и проектной сцене; чистая функция тестирует числовой ROI/NPV, спрос и отсутствие фиктивной выгоды.
- Регистрация требует явного согласия с текущей версией; сервер пишет `PRIVACY_CONSENT_GRANTED` в audit. Профиль ведёт к документу, явно помеченному проектом.
- Исправлены и расширены браузерные smoke для Play/Pause, 2D/3D, DXF, экономики и согласия.

## Проверки и ограничения доказательств

- `cd robcraft; npm.cmd test`: финальный полный прогон **149 passed, 0 failed**.
- `cd frontend; npm.cmd test`: **212 passed**. `npm.cmd run build`: PASS. `npx.cmd eslint src/components/PersistenceScreens.jsx`: PASS.
- `python -m pytest backend -q --disable-warnings --maxfail=1 --basetemp=.pytest-run-main`: финальный прогон **1002 passed, 93 skipped**. PostgreSQL-only suites пропущены. Targeted report/physical/simulation/privacy ранее **25 passed**.
- `python scripts/robcraft_editor_smoke.py`: PASS, включая 3 DXF файла и движения 2D/3D. `robcraft_project_browser_smoke.py`: PASS, сохранение/открытие вводных через same-origin API stub. `robcraft_touch_browser_smoke.py`: PASS; третий шаг размещения чувствителен к расстоянию камеры, smoke использует 0,8 с движения.
- `python scripts/phase_a_browser_smoke.py`: PASS для склада, аэропорта и клиники по цепочке «Работы → Роботы → Симуляция → Деньги → Результат», guest access, PDF/trailer и UI согласия. Этот smoke использует in-process backend и пустой тестовый каталог. Он не заменяет production с PostgreSQL и опубликованным каталогом.
- Не выполнены реальная PostgreSQL проверка новых ScenePatch полей, audit согласия в production DB, проверка опубликованного каталога, staging smoke и юридическое согласование политики.

## Актуальные пути

| Область | Файлы |
|---|---|
| Воронка, маршруты UI, доступ | `frontend/src/App.jsx`, `frontend/src/appNavigation.js`, `frontend/src/components/AppShell.jsx`, `frontend/src/components/PersistenceScreens.jsx` |
| Пять экранов и отчёт | `frontend/src/components/ObjectRoleWorkspace.jsx`, `WarehouseRoleWorkspace.jsx`, `SceneSimulationControls.jsx`, `WhatIfPanel.jsx`, `InvestmentReport.jsx` |
| Общая сцена и рендер | `frontend/src/sceneModel.js`, `frontend/src/components/SceneModelPreview.jsx`, `frontend/src/sceneRenderer3D.js`; assets `frontend/public/scene-assets/` |
| Расчёт и PDF | `backend/calculation/scene_simulation.py`, `physical_fit.py`, `role_report.py`, `role_report_view.py`, `readable_report.py` |
| RobCraft | `robcraft/src/main.js`, `simulation.js`, `core/renderer.js`, `editor/{editor,scene-patch,operational,dxf-import,live-economics,map-view}.js`, `robcraft/index.html`, `robcraft/styles.css` |
| RobCraft API и согласие | `backend/robcraft_scene_api.py`, `backend/persistence_api.py`, `backend/persistence_models.py`, `frontend/public/privacy-policy.html` |

## Запуск и повторная проверка

- Полные локальные инструкции: `docs/GETTING_STARTED.md`. Без Docker: PostgreSQL 16 и `DATABASE_URL`, `python -m alembic -c backend/alembic.ini upgrade head`, `python -m uvicorn main:app --app-dir backend --reload --port 8000`, во втором терминале `npm.cmd run dev --prefix frontend`.
- Standalone RobCraft: `cd robcraft; npm.cmd run dev` (порт 4174 по умолчанию).
- Для существующего production окружения **не запускать голый** `docker compose up`: проверить текущие `.env.production`, `compose.yaml`, `compose.production.yaml` и процедуру деплоя. В этой сессии деплой не выполнялся.
- При тестах из sandbox использовать `--basetemp` внутри рабочей папки: стандартный `C:\Temp\pytest-of-...` давал `PermissionError`. Git ownership требует одноразовое `git -c safe.directory='<абсолютный путь repo>' ...`; глобальную конфигурацию не меняли.

## Инварианты для визуальной сессии

1. Расчётные Python контракты и `role_report_view.py` — источник чисел; React и PDF только представляют их. Временный what-if не мутирует базовый run.
2. 2D/3D frontend используют один `SceneModel`; RobCraft 2D/3D используют один ScenePatch. Визуальный декор не должен становиться препятствием/выработкой без явного типа и проверки.
3. Робот без совместимой работы, допустимого payload и доступного маршрута не даёт подтверждённой производительности. Live economics требует пользовательских вводных, цены и пометки сценарности.
4. Не менять `revision_id`, visual fingerprint, source IDs, unit contracts и provenance при CSS/GLB/PDF полировке.
5. Свободно менять внешнюю композицию `AppShell`, `OnboardingScreen`, `InvestmentReport`, CSS, рендер-материалы/свет и ассеты; сохранять данные и API контракт этих компонентов. Любое изменение маршрутов/геометрии требует повторной проверки collision и экономики.

## Рекомендуемый порядок следующего прохода

1. Получить и прочитать `ROBODOVOD_VISUAL_POLISH_V1_CODEX_2026-10-20.zip`; второй концепт — основной эталон. Перед редизайном проверить функциональные blocker-пункты выше.
2. Полировка воронки и RobCraft без изменения расчётного ядра; затем материалы/свет/камеры 2D/3D на общем SceneModel.
3. Визуальная композиция экрана результата и PDF с проверкой переноса, пустых страниц и равенства чисел.
4. Полный mobile pass 360/390/768 и планшет, затем browser smoke, PDF viewer, performance/FPS, лицензии, права, PostgreSQL/staging smoke.
