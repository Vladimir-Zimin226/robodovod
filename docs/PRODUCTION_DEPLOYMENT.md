# Production deployment — robodovod.ru

Статус: **C30 IN PROGRESS / TRAFFIC SWITCH HOLD**, 2026-09-23.

Production activation запрещена до закрытия двух runtime blockers из раздела
1. Все команды ниже разделены на безопасную подготовку и намеренно закрытый
traffic switch. Project name: `robodovod-prod`; installation root:
`/opt/robodovod`; environment: `.env.production` с mode `600`.

## 1. Обязательный HOLD

Текущий release нельзя считать готовым к публичному расчёту:

1. `main.app` не передаёт `resolve_economics_version` и
   `calculate_economics_v2` в persistence router. Approved economics v2 route
   поэтому отвечает `503`, а production orchestrator C13–C21 отсутствует.
2. `organizer-catalog-v4` содержит capacity pool 21/24, но zero legacy
   `runtime_robots`. Его корректно можно активировать для `discovery` и
   `capacity`, но нельзя для legacy `runtime`; старые `/api/calculate` и
   `/analysis-runs` на fresh DB fail closed.

До отдельного исправления и повторного C29 gate запрещены команды `caddy up`,
catalog `runtime` activation и economics route activation. Нельзя подменять
их synthetic catalog, test fixture или скрытым fallback.

## 2. Локальная публикация release — после снятия HOLD

```powershell
git status --short
git switch main
git pull --ff-only origin main
git merge --ff-only ops/production-domain-deployment-v1
git tag -a v0.4.0 -m "Robodovod production release v0.4.0"
git push origin main
git push origin v0.4.0
git rev-parse v0.4.0^{}
```

Если `--ff-only` невозможен, не создавать merge вручную: опубликовать branch,
сделать reviewed PR и тегировать получившийся commit `main`.

## 3. Read-only preflight VDS — можно выполнить сейчас

С клиентского ПК:

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=10 robodovod "hostname; nproc; free -h; df -h / /opt; docker version; docker compose version"
ssh robodovod "sudo ufw status verbose; sudo ss -lntup"
ssh robodovod "cd /opt/robodovod && git status --short && git rev-parse HEAD && stat -c '%a %n' .env"
```

Ожидается clean server tree, `.env` mode `600`, открыты только 22/80/443,
5432/8000/5173 не слушают public interface. Из текущей Codex-среды SSH
23.09.2026 завершился timeout; это не доказательство недоступности с ПК
владельца, но server preflight ещё не принят.

## 4. Подготовка server checkout — можно выполнить без запуска

После публикации тега:

```bash
ssh robodovod
cd /opt/robodovod
git status --short
git fetch --prune --tags origin
git verify-tag v0.4.0
git show --no-patch --decorate v0.4.0
git checkout --detach v0.4.0
git rev-parse HEAD
```

Полученный hash должен совпасть с локальным `git rev-parse v0.4.0^{}`.

## 5. Production secrets

На VDS, не на рабочем ПК:

```bash
cd /opt/robodovod
umask 077
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
openssl rand -hex 32
openssl rand -base64 24
nano .env.production
```

Первые два значения используются как разные PostgreSQL passwords, третье —
как initial admin password. Special characters application password должны
быть URL-encoded в `DATABASE_URL`. Проверка без вывода значений:

```bash
test "$(stat -c %a .env.production)" = 600
grep -Eq '^SESSION_COOKIE_SECURE=true$' .env.production
grep -Eq '^APP_ALLOWED_ORIGINS=https://robodovod.ru,https://www.robodovod.ru$' .env.production
grep -Eq '^COMPOSE_PROJECT_NAME=robodovod-prod$' .env.production
! grep -Eq '<[^>]+>' .env.production
```

## 6. Safe config/build preflight — можно выполнить сейчас

```bash
cd /opt/robodovod
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C config --quiet
$C build --pull backend frontend migrate
$C images
```

`compose.production.yaml` удаляет published ports DB/backend/frontend. Только
Caddy публикует TCP 80/443 и UDP 443. Network `data` internal-only.

## 7. Backup и restore drill

Перед любой migration существующей БД:

```bash
cd /opt/robodovod
sudo install -d -m 700 -o deploy -g deploy /var/backups/robodovod
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d db
DOCKER='sudo docker' BACKUP_DIR=/var/backups/robodovod ./scripts/production/backup.sh
DOCKER='sudo docker' ./scripts/production/restore-drill.sh /var/backups/robodovod/postgres-YYYYMMDDTHHMMSSZ.dump
```

Скопировать dump, uploads archive и checksum manifest в зашифрованное off-host
хранилище. Наличие локального файла без restore drill не считается backup.

## 8. Migration и first bootstrap — выполнять только после снятия HOLD

```bash
cd /opt/robodovod
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C up -d db
$C run --rm migrate
$C run --rm catalog-import --phase BASE --mode VALIDATE_ONLY
$C run --rm catalog-import --phase BASE --mode COMMIT
$C run --rm catalog-import --phase ENRICHMENT --mode VALIDATE_ONLY
$C run --rm catalog-import --phase ENRICHMENT --mode COMMIT
$C run --rm catalog-activation validate --catalog-code organizer-catalog-v4
$C run --rm catalog-activation publish --catalog-code organizer-catalog-v4
$C run --rm catalog-activation activate --slot discovery --catalog-code organizer-catalog-v4 --actor production-c30
$C run --rm catalog-activation activate --slot capacity --catalog-code organizer-catalog-v4 --actor production-c30 --approval-report /contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json
$C run --rm admin-bootstrap
$C run --rm catalog-activation status
$C run --rm economics-activation status
```

Не активировать `runtime` для organizer catalog. Economics activation допустима
только после появления production executor и повторной acceptance:

```bash
$C run --rm economics-activation activate --actor production-c30 --approval-report /contracts/fixtures/economics-dual-run-report-v1.golden.json
```

Rollback economics меняет только route configuration:

```bash
$C run --rm economics-activation rollback --actor production-rollback
```

## 9. Traffic switch — CLOSED до снятия HOLD

После устранения blockers, зелёного повторного C29 и предыдущих шагов:

```bash
cd /opt/robodovod
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C up -d backend frontend caddy
$C ps
$C logs --tail=200 backend frontend caddy
curl -fsS https://robodovod.ru/health
curl -fsS https://robodovod.ru/ready
curl -fsSI http://robodovod.ru/
curl -fsSI https://www.robodovod.ru/
./scripts/production/smoke.sh
```

С клиентского ПК проверить закрытые порты:

```powershell
Test-NetConnection robodovod.ru -Port 443
Test-NetConnection robodovod.ru -Port 5432
Test-NetConnection robodovod.ru -Port 8000
Test-NetConnection robodovod.ru -Port 5173
```

Для последних трёх ожидается `TcpTestSucceeded: False`.

## 10. Application rollback

Rollback не делает downgrade БД и не удаляет volumes:

```bash
cd /opt/robodovod
PREVIOUS_COMMIT=<recorded-compatible-commit>
git show --no-patch "$PREVIOUS_COMMIT"
git checkout --detach "$PREVIOUS_COMMIT"
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C config --quiet
$C build backend frontend
$C up -d backend frontend caddy
$C ps
```

Если предыдущий application commit несовместим с уже применённой schema,
traffic остаётся закрытым до roll-forward. `down -v`, ручной SQL rewrite и
Alembic downgrade на production запрещены.

## 11. Проверено локально перед передачей

- production Compose проходит `config --quiet`, backend/frontend images
  собираются, Caddyfile проходит `caddy validate`;
- disposable production-like stack применяет Alembic migrations, сообщает
  healthy для PostgreSQL/backend/frontend и не публикует 5432/8000/5173;
- `/health`, `/ready`, frontend и economics route `status` отвечают ожидаемо;
- backup/restore/smoke scripts проходят `sh -n`;
- targeted backend regression: 16 tests passed;
- C29 acceptance остаётся базой release: 616 backend tests с PostgreSQL,
  66 frontend tests, lint/build и restore drill прошли до начала C30.

Это подтверждает готовность deployment infrastructure, но не снимает runtime
HOLD из раздела 1.
