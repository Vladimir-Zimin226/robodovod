# FINAL FIX V2 — локальная приёмка, 21.10.2026

Baseline: `59b36d3`, ветка `integration/evgeny-transfer-2026-10-19`. Изменения приложения зафиксированы коммитом `97e62a1`; обновлённая заказчиком презентация — `c056f79` (PDF/PPTX по 9 слайдов); старые обновлённые QA-снимки — `5b35165`. Этот проход **не развёрнут** на production; заказчик выполняет обновление отдельно. Прочие локальные материалы сохранены согласно [архиву](../../audit/LOCAL_ARTIFACT_ARCHIVE.md).

| ID | Результат | Доказательство / ограничение |
| --- | --- | --- |
| S — симуляция | Локально PASS | Docker image теперь включает `data/scenes`; при отсутствии файла API отвечает 503, не 500. 3 editable browser сценария и 12 DEMO browser сценариев на реальном локальном FastAPI/изолированной PostgreSQL. Production traceback исходного 500 не доступен, production повторить после обновления. |
| D — готовые примеры | Локально PASS | 3 versioned immutable presets в `showcasePresets.json`, одна работа на объект, никаких полей ввода; [browser JSON](demo-browser-evidence.json). Учебные цены/роботы маркированы. |
| E — экономика | Локально PASS в рамках предположений | 43 профильных backend/PDF теста; [финансовая сверка](../../audit/FINANCE_FINDINGS.md). Проверены `t=0`/первый год аренды, неизвестный тариф, NPV и PDF. Паспорта каталога не выдуманы. |
| H — главная | Локально PASS | WebP заказчика в `frontend/public/images`; [desktop](evidence/home-1440.png), [mobile](evidence/home-390.png). |
| C — playback/What-if | Локально PASS | 1×/2×/4×/8× двигают общий курсор; PDF/NPV не зависят от rate. [What-if desktop](evidence/what-if-1440-fixed.png), browser проверка CTA/пересчёта. |
| P — PDF | Локально PASS | [склад](evidence/demo-retail.pdf), [аэропорт](evidence/demo-airport.pdf), [клиника](evidence/demo-clinic.pdf), каждый по 4 страницы; [контактные листы](evidence/demo-retail-contact.png), [аэропорт](evidence/demo-airport-contact.png), [клиника](evidence/demo-clinic-contact.png). Снимки сцены больше не занимают отдельные листы. Наложение строки аренды устранено; `C11` и сырые enum отсутствуют во всех 12 страницах. |
| M — mobile | Локально PASS для DEMO | 12 browser сценариев на 1440/768/390/360 px, без горизонтального overflow, с 2D/3D, Play/Pause и PDF 200; [evidence](demo-browser-evidence.json). Полный legacy RobCraft mobile после этих правок не повторялся. |
| R — clean code/docs | PARTIAL | Удалён доказанно мёртвый `sceneCapture.js`; [инвентаризация](../../audit/CODEBASE_INVENTORY.md), [API](../../api/README.md), [архитектура](../../architecture/OVERVIEW.md). Полный статический анализ всех динамических интеграций не выполнен. |

## Проверенные пользовательские пути

Готовые склад/аэропорт/клиника: пять шагов без ввода, 2D/3D движение, пауза, ×8, экономика, результат, PDF HTTP 200. `smoke_demo_browser.py` повторно прошёл все 12 комбинаций после фиксации JSON-пресетов. Отдельно три обычных editable сценария прошли с локальным активированным каталогом; [evidence](editable-browser-evidence.json). Синтетический API не использовался в этих browser E2E. Локальный FastAPI 8001 использовал изолированную PostgreSQL; это не production-проверка.

Тесты текущего исходного кода: `python -m pytest backend/test_showcase_presets.py backend/test_warehouse_roles.py backend/test_role_report_view.py backend/test_readable_report.py -q` → **43 passed**. После остановки оставленного Vite на 4177 команда `npm ci` повторно прошла, frontend unit tests **219 passed**, production build и targeted ESLint PASS. Три транзитивные зависимости обновлены в `frontend/package-lock.json` до совместимых patch-версий; `npm audit` → **0 уязвимостей**. Предыдущее `EPERM` в `npm ci` было вызвано открытым нативным модулем Rolldown; EPERM при запуске Node внутри ограниченной песочницы решён разрешённым запуском инструментов, локальная сборка подтверждена.

Дополнительно текущий модуль playback импортирован в настоящем browser/Vite: за 0,1 с времени стены курсор из 5,0 с переместился на 5,1/5,2/5,4/5,8 с для 1×/2×/4×/8×. Это проверяет арифметику отображения; физическая модель и backend-входы не менялись.

## Остаточные блокеры

- Перед обновлением сервера создать и проверить **новый** bundle; старый bundle не содержит patch. Новая презентация заказчика уже включена отдельным коммитом `c056f79` и проверена как 9-страничный PDF и 9-слайдовый PPTX.
- Production: настоящий server image, миграции, каталог, авторизация, DEMO, PDF и Nginx пока не проверены после этого patch. Исходный 500 был локализован по отсутствующему `COPY data/scenes` в Dockerfile; исходный серверный traceback недоступен.
- P1: проверить RobCraft и legacy экраны на оставшиеся сырые коды при ручной регрессии. Открытые `P2` — в [backlog](../../audit/TECH_DEBT_BACKLOG.md).

## Развёртывание

Деплой в этой сессии не выполнялся по просьбе заказчика. После успешной сборки и тематического коммита перенесите новый Git bundle по согласованному способу; старый `robodovod-rc-2026-10-20.bundle` **не содержит** этот patch. Команды и preflight приведены в [SELF_DEPLOY_RC.md](../../recovery-v2/SELF_DEPLOY_RC.md); для текущего обновления используйте новый SHA/bundle. Не запускайте import/activation каталога или разрушительные миграции автоматически. После обновления вручную пройдите три DEMO, один editable расчёт, RobCraft/save, согласие/login/logout и мобильный 390 px, проверьте PDF и журналы.

По присланному заказчиком журналу самостоятельного развёртывания 21.10.2026 bundle с HEAD `86311b5` успешно проверен и fetched на сервере, checkout переключён на `rc/final-fix-v2`, Compose config прошёл. `docker compose build` остановился до сборки с `permission denied` на `/var/run/docker.sock`: пользователь `deploy` запускает Docker через `sudo`. Инструкции исправлены на `sudo docker compose`; результат повторной сборки, обновления контейнеров и production smoke пока неизвестен.
