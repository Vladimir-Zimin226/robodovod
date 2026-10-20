# Команды следующего обновления (самостоятельный деплой)

> Обновление 21.10.2026: приведённые ниже команды с bundle описывают уже выполненный перенос версии `86311b5`. GitHub теперь содержит только ветку `main`; она включает весь код, презентации и документацию. Для следующего обновления после проверки чистого рабочего дерева на сервере используйте `git fetch origin main`, `git switch main`, `git merge --ff-only origin/main`, затем команды `sudo docker compose` и smoke из раздела ниже. Не выполняйте заново перенос старого bundle.

Перед `npm ci` закройте локальный Vite (`localhost:4177`): на Windows его процесс удерживает `rolldown-binding.win32-x64-msvc.node` и мешает npm удалить старые зависимости. После остановки Vite `npm ci` дважды прошёл, включая обновлённый lock-файл; `npm test` 219/219, сборка и targeted ESLint PASS, `npm audit` — 0 уязвимостей. Исходники и новая презентация уже в коммитах `97e62a1`, `c056f79`, `5b35165`; старый bundle от 20.10.2026 не содержит FINAL FIX V2. Команд backup здесь нет по запросу заказчика; существующий runbook с проверками состояния: [SELF_DEPLOY_RC.md](../../recovery-v2/SELF_DEPLOY_RC.md).

## Локально, Windows CMD, из корня репозитория

```bat
cd /d "C:\Users\Владимир Королев\PycharmProjects\Конкурсы\robodovod"
cd frontend
npm ci
npm test
npm run build
cd ..
python -m pytest backend/test_showcase_presets.py backend/test_warehouse_roles.py backend/test_role_report_view.py backend/test_readable_report.py -q
git status --short
git log -1 --format="%H %s"
git bundle create "Разобрать/robodovod-final-fix-v2.bundle" f102d88..HEAD
git bundle verify "Разобрать/robodovod-final-fix-v2.bundle"
scp "Разобрать/robodovod-final-fix-v2.bundle" robodovod:/tmp/robodovod-final-fix-v2.bundle
ssh robodovod
```

Перед созданием bundle `git status --short` должен быть пустым. База `f102d88` должна существовать на сервере, иначе bundle не применится. Команда `scp` использует подтверждённый пользователем SSH alias `robodovod`.

## На сервере, внутри SSH

```sh
cd /opt/robodovod
git status --short
git rev-parse HEAD
git bundle verify /tmp/robodovod-final-fix-v2.bundle
git fetch /tmp/robodovod-final-fix-v2.bundle HEAD:refs/heads/rc/final-fix-v2
git log -1 --format='%H %s' rc/final-fix-v2
git switch rc/final-fix-v2
sudo -v
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml config --quiet
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml build backend frontend migrate
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d backend frontend caddy
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml ps
curl -fsS https://robodovod.ru/health
curl -fsS https://robodovod.ru/ready
curl -fI https://robodovod.ru/demo/trailer/robodovod-trailer-web-720p.mp4
```

Перед `git switch` рабочее дерево сервера должно быть чистым и SHA целевой ветки — проверенным. На текущем сервере пользователь `deploy` не имеет прямого доступа к `/var/run/docker.sock`: все команды Docker Compose выполняйте через `sudo`. `sudo -v` может запросить пароль. Compose фактически публикует через **Caddy** (не Nginx). Не запускать `down -v`, import/activation каталога или непроверенные миграции. Если Compose/каталог/миграции на сервере отличаются от [runbook](../../recovery-v2/SELF_DEPLOY_RC.md), остановитесь и разберите расхождение.

После обновления в настоящем браузере проверьте главную, три DEMO без ввода, один editable расчёт, 2D/3D движение и паузу, ×1/×2/×4/×8, деньги/«Что если?», PDF, RobCraft/save, регистрацию/вход/выход, мобильный 390 px и консоль/серверные журналы. `/ready` не подтверждает эти сценарии.
