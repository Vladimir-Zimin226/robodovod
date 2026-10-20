# Команды следующего обновления (самостоятельный деплой)

Перед `npm ci` закройте локальный Vite (`localhost:4177`): на Windows его процесс удерживает `rolldown-binding.win32-x64-msvc.node` и мешает npm удалить старые зависимости. После остановки Vite `npm ci` дважды прошёл, включая обновлённый lock-файл; `npm test` 219/219, сборка и targeted ESLint PASS, `npm audit` — 0 уязвимостей. Старый bundle от 20.10.2026 не содержит FINAL FIX V2. Команд backup здесь нет по запросу заказчика; существующий runbook с проверками состояния: [SELF_DEPLOY_RC.md](../../recovery-v2/SELF_DEPLOY_RC.md).

## Локально, Windows CMD, из корня репозитория

```bat
cd /d "C:\Users\Владимир Королев\PycharmProjects\Конкурсы\robodovod"
cd frontend
npm ci
npm test
npm run build
cd ..
python -m pytest backend/test_showcase_presets.py backend/test_warehouse_roles.py backend/test_role_report_view.py backend/test_readable_report.py -q
git add -- README.md backend/Dockerfile backend/calculation/object_roles.py backend/calculation/readable_report.py backend/calculation/role_report.py backend/calculation/role_report_view.py backend/object_roles_api.py backend/warehouse_roles_api.py backend/test_role_report_view.py backend/test_warehouse_roles.py backend/test_showcase_presets.py
git add -- frontend/package-lock.json frontend/src/App.jsx frontend/src/OnboardingScreen.jsx frontend/src/index.css frontend/src/presentation.js frontend/src/simulationPlayback.js frontend/src/showcasePresets.js frontend/src/showcasePresets.json frontend/src/sceneCapture.js frontend/tests/simulationPlaybackSpeed.test.mjs
git add -- frontend/src/components/DemoRoleWorkspace.jsx frontend/src/components/IntakeScreen.jsx frontend/src/components/InvestmentReport.jsx frontend/src/components/ObjectRoleWorkspace.jsx frontend/src/components/SceneSimulationControls.jsx frontend/src/components/TrailerPlayer.jsx frontend/src/components/WhatIfPanel.jsx frontend/public/images/hero_banner.webp frontend/public/images/object_warehouse.webp frontend/public/images/object_airport.webp frontend/public/images/object_clinic.webp
git add -- docs/api docs/audit docs/architecture/OVERVIEW.md docs/CHANGELOG.md docs/qa/final-home-demo-fix/FINAL_REPORT.md docs/qa/final-home-demo-fix/DEPLOY_COMMANDS.md docs/qa/final-home-demo-fix/smoke_demo_browser.py docs/qa/final-home-demo-fix/capture_demo_pdfs.py docs/qa/final-home-demo-fix/demo-browser-evidence.json docs/qa/final-home-demo-fix/editable-browser-evidence.json docs/qa/final-home-demo-fix/demo-pdf-evidence.json docs/recovery-v2/PROGRESS.md docs/recovery-v2/NEXT_SESSION.md
git add -- docs/qa/final-home-demo-fix/evidence/home-1440.png docs/qa/final-home-demo-fix/evidence/home-390.png docs/qa/final-home-demo-fix/evidence/what-if-1440-fixed.png docs/qa/final-home-demo-fix/evidence/retail-1440-simulation.png docs/qa/final-home-demo-fix/evidence/airport-1440-simulation.png docs/qa/final-home-demo-fix/evidence/clinic-1440-simulation.png docs/qa/final-home-demo-fix/evidence/demo-retail.pdf docs/qa/final-home-demo-fix/evidence/demo-airport.pdf docs/qa/final-home-demo-fix/evidence/demo-clinic.pdf docs/qa/final-home-demo-fix/evidence/demo-retail-contact.png docs/qa/final-home-demo-fix/evidence/demo-airport-contact.png docs/qa/final-home-demo-fix/evidence/demo-clinic-contact.png
git diff --cached --check
git diff --cached --stat
git commit -m "fix: complete locked demos and simulation release patch"
git status --short
git log -1 --format="%H %s"
git bundle create robodovod-final-fix-v2.bundle f102d88..HEAD
git bundle verify robodovod-final-fix-v2.bundle
scp robodovod-final-fix-v2.bundle robodovod:/tmp/robodovod-final-fix-v2.bundle
ssh robodovod
```

Перед `git commit` просмотрите `git diff --cached --stat`; в индекс добавлены только выбранные исходники, документы и ключевые доказательства, а не пользовательские временные/архивные файлы. База `f102d88` должна существовать на сервере, иначе bundle не применится. Команда `scp` использует подтверждённый пользователем SSH alias `robodovod`.

## На сервере, внутри SSH

```sh
cd /opt/robodovod
git status --short
git rev-parse HEAD
git bundle verify /tmp/robodovod-final-fix-v2.bundle
git fetch /tmp/robodovod-final-fix-v2.bundle HEAD:refs/heads/rc/final-fix-v2
git log -1 --format='%H %s' rc/final-fix-v2
git switch rc/final-fix-v2
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml build backend frontend migrate
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d backend frontend caddy
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml ps
curl -fsS https://robodovod.ru/health
curl -fsS https://robodovod.ru/ready
curl -fI https://robodovod.ru/demo/trailer/robodovod-trailer-web-720p.mp4
```

Перед `git switch` рабочее дерево сервера должно быть чистым и SHA целевой ветки — проверенным. Compose фактически публикует через **Caddy** (не Nginx). Не запускать `down -v`, import/activation каталога или непроверенные миграции. Если Compose/каталог/миграции на сервере отличаются от [runbook](../../recovery-v2/SELF_DEPLOY_RC.md), остановитесь и разберите расхождение.

После обновления в настоящем браузере проверьте главную, три DEMO без ввода, один editable расчёт, 2D/3D движение и паузу, ×1/×2/×4/×8, деньги/«Что если?», PDF, RobCraft/save, регистрацию/вход/выход, мобильный 390 px и консоль/серверные журналы. `/ready` не подтверждает эти сценарии.
