# Production deployment — robodovod.ru

Статус: **C30 LIVE TEST / C11 TRACE HOLD**, 2026-09-24.

### Текущее обновление `v0.5.5` → `v0.5.6`

Живой браузерный ввод уже дошёл до выбора MULE, но `POST
/api/v2/capacity-analyses` вернул 422: C01 присвоил исходному
`explicit_batch` ссылку `conversion.0006`, а C11 построил trace с этой
ссылкой без соответствующей записи provenance. В диагностическом архиве
зафиксирован один `FAILED` C11 run; он остаётся историческим и не
переписывается. Исправление связывает C01 conversion refs с уже существующим
источником нормализованного процесса внутри C11 trace, сохраняя исходный ref
в immutable input snapshot. Формулы, цены, каталог и C05 gates не меняются.
Карточка демо-профиля получает тёмный фон и контрастный текст.

Это code-only hotfix: **новый backup, миграция, импорт каталога, activation и
bootstrap не нужны**. На сервере с чистым `main` на `v0.5.5`:

```bash
set -euo pipefail
cd /opt/robodovod
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 v0.5.5)"
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C config --quiet
OLD_BACKEND="$($C images -q backend)"
OLD_FRONTEND="$($C images -q frontend)"
test -n "$OLD_BACKEND"
test -n "$OLD_FRONTEND"
sudo docker image tag "$OLD_BACKEND" robodovod-backend:rollback-v055
sudo docker image tag "$OLD_FRONTEND" robodovod-frontend:rollback-v055
git fetch --prune --tags origin
git pull --ff-only origin main
test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 v0.5.6)"
$C config --quiet
$C build backend frontend
$C stop caddy
$C up -d --wait --no-deps backend frontend
$C exec -T backend python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/ready").read().decode())'
$C up -d --wait --no-deps caddy
$C ps
```

При любой ошибке остановиться; если Caddy уже остановлен, не открывать
публичный трафик до исправления. После успешного обновления сделать hard
refresh браузера и новый C11 run, затем C13–C21 → reopen/export. Отдельно
проверить HTTPS `/ready` с клиентского ПК. До успешного живого расчёта C30
остаётся на HOLD.

После `v0.5.4` серверная нормализация C01 и активный capacity-каталог
подтверждены. Живой браузерный тест выявил вторую ошибку: выпадающий список
демо-моделей сравнивал внутренний `model_id` API с опубликованным
`organizer_id` авторских профилей. Это разные UUID; поэтому список был пуст,
хотя MULE присутствует в активном каталоге и расчётно доступен. `v0.5.5`
использует `organizer_id` только для сопоставления авторского профиля, а
неизменённый внутренний `model_id` передаёт в C11. Архив администратора
подтвердил: C01 ответил 200, `/api/catalog/models` ответил 200, C11 runs ещё
не создавались. Папка `backup/` локально исключена из Git.

Для обновления именно с `v0.5.4` на `v0.5.5` не повторять backup, migration,
import, activation или bootstrap. После сверки чистого `main` на сервере:

```bash
cd /opt/robodovod
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 v0.5.4)"
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
git fetch --prune --tags origin
git pull --ff-only origin main
test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 v0.5.5)"
$C config --quiet
$C build frontend
$C up -d --wait --no-deps frontend
$C ps
```

`v0.5.5` меняет только браузерную сборку, тесты и документацию: backend,
PostgreSQL и Caddy не пересоздаются. После обновления сделать hard refresh
страницы, заново проверить ввод, выбрать MULE, подтвердить демо-допущения,
затем пройти C11 → C13–C21 → reopen/export. При пустом списке или сетевой
ошибке остановить приёмку, сохранить диагностический ZIP и HTTP-статусы.

`www.robodovod.ru` по Caddyfile всегда отдаёт 301 на apex. HTTP 301 для
`www` не подтверждает доступность apex: отдельные тайм-ауты подключения к
`robodovod.ru:443` требуют проверки с клиентской сети и не исправляются
этим frontend hotfix.

Первый публичный запуск `v0.5.3` состоялся: HTTPS для обоих доменов, backend,
frontend, catalog discovery/capacity и economics v2 route работают. Сквозной
браузерный расчёт пока **не принят**: `POST /api/v2/calculation-intake/normalize`
возвращал 404, поскольку обработчик C01 не был подключён в `main.app`. До
проверки hotfix не утверждать, что публичный C11 → C13–C21 путь работает.

Hotfix `v0.5.4` подключает C01 endpoint, добавляет HTTP regression test и
админский диагностический ZIP. ZIP доступен только ADMIN по POST с CSRF,
содержит снимки расчётных/каталожных таблиц всех tenants, audit и ограниченный
журнал запросов backend. Он не содержит известных password/session/token fields,
`.env` или Docker/Caddy logs и **не заменяет restore backup**. Файл считать
конфиденциальным. Для этого stateless code hotfix дополнительный backup не
является deployment gate: уже проверенный backup `20260924T034525Z` сохранён;
оператор осознанно отказался от повторных backup на первом развёртывании.

Публичный Caddy уже запущен оператором. Команды первого развёртывания ниже
сохранены для истории; при обновлении с `v0.5.3` не повторять миграцию, импорт,
активацию каталога или bootstrap. Project name: `robodovod-prod`; installation root:
`/opt/robodovod`; environment: `.env.production` с mode `600`.

Команды выполнять по одной в указанном порядке. При любом ненулевом exit code,
неожиданном hash/status или failed/unhealthy контейнере остановиться и закрыть
публичный Caddy до расследования.

## 0. Текущее обновление с `v0.5.3` на `v0.5.4`

После публикации проверенного `main`/tag, на сервере:

```bash
cd /opt/robodovod
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C stop caddy
test -z "$(git status --porcelain)"
git fetch --prune --tags origin
git pull --ff-only origin main
test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 v0.5.4)"
$C config --quiet
$C build backend frontend
$C up -d --wait --no-deps backend frontend
$C run --rm --no-deps economics-activation status
$C ps
```

Не запускать `migrate`, `catalog-import`, `catalog-activation` или
`admin-bootstrap` повторно. До открытия трафика проверить новый C01 HTTP
endpoint и каталог, затем вернуть Caddy:

```bash
$C exec -T backend python - <<'PY'
import urllib.error
import urllib.request

base = "http://127.0.0.1:8000"
for path in ("/ready", "/api/catalog/status"):
    print(path, urllib.request.urlopen(base + path).read().decode())
request = urllib.request.Request(
    base + "/api/v2/calculation-intake/normalize",
    data=b"{}",
    headers={"Content-Type": "application/json"},
)
try:
    urllib.request.urlopen(request)
except urllib.error.HTTPError as error:
    assert error.code == 422, f"unexpected C01 status {error.code}"
    print("C01 route registered: empty input returned 422")
else:
    raise AssertionError("empty intake unexpectedly accepted")
PY
$C up -d --wait caddy
$C ps
```

Публичный smoke без секретов: HTTPS `/health`, `/ready`, `/api/catalog/status`,
TLS обоих доменов, закрытые 5432/8000/5173. Затем авторизованный UI flow с
открытым проектом; проверить новый C01 route, C11, C13–C21, reopen/export и
админский диагностический ZIP. При ошибке `$C stop caddy`, не удалять volumes.

## 1. Обязательный HOLD

Технический UI → C11 → C13–C21 gap закрыт и повторный C29 прошёл: production
executor подключён, actual organizer catalog path, immutable persistence,
reopen/export/replay, tenant isolation и CSRF проверены. HOLD теперь означает:

1. deploy выполняется только из проверенного `main`; до публикации/сверки hash
   серверный checkout и public traffic не менять;
2. до запуска backend обязательны production `.env`, backup/restore drill,
   migration/import/activation и internal smoke;
3. `organizer-catalog-v4` нельзя активировать в legacy `runtime`: у него zero
   `runtime_robots`. Для новых поддержанных расчётов активируются только
   `discovery`, `capacity` и economics v2 route;
4. demo `WITH_ASSUMPTIONS` — предварительное ТЭО. Без паспорта/комплектации,
   availability и фактических условий объекта C05 остаётся
   `NEEDS_VALIDATION`; UI не вправе показывать PASS/deployment-ready или
   закупочную рекомендацию.

Технический разбор: [production calculation integration gap](planning/production-calculation-integration-gap.md).

Synthetic catalog, fixture executor и скрытый fallback в production запрещены.

### Инцидент первого импорта 2026-09-24

На `v0.5.0` первый `BASE VALIDATE_ONLY` остановился с `size mismatch:
catalog_applicability.csv`. Manifest закрепляет исходные байты двух CSV, но
Git нормализовал встроенные CRLF при Linux checkout: `catalog_applicability.csv`
стал 119210 вместо 119228 байт, `catalog_field_evidence.csv` — 826195 вместо
826253. Исправление `v0.5.1` закрепляет исходные Git blobs и отключает
нормализацию в `data/import/organizer-catalog-v4/`. Содержимое manifest, каталог
и закупочные данные не менялись. `v0.5.2` исправляет выбор PostgreSQL admin
role в backup/restore scripts. На первом backup с `v0.5.2` архив uploads был
создан контейнером от root, поэтому последующий `chmod` от deploy завершился
ошибкой. `v0.5.3` создаёт архив с mode 600 и передаёт владение вызывающему
пользователю до выхода контейнера. Старые теги не переписывать; продолжать
deployment только с `v0.5.3`.

До нового импорта на сервере после обновления `main` проверить:

```bash
cd /opt/robodovod
test "$(wc -c < data/import/organizer-catalog-v4/catalog_applicability.csv)" -eq 119228
test "$(wc -c < data/import/organizer-catalog-v4/catalog_field_evidence.csv)" -eq 826253
printf '%s\n' \
  '85501030ce65c20c449eb050baa2c73e0fdf44bd507bbe1272dc2c17114efa6f  data/import/organizer-catalog-v4/catalog_applicability.csv' \
  '43cd81bfd9222c29122a2972f5709e394a0664f610fabadf7790b55858040262  data/import/organizer-catalog-v4/catalog_field_evidence.csv' | sha256sum -c -
```

Уже выполненную миграцию повторять не нужно. Не удалять volume БД и не
исправлять CSV вручную на VDS. Неудачный `VALIDATE_ONLY` оставил audit run со
статусом `FAILED`; повторная команда без `--request-key` создаёт новую попытку.

## 2. Локальная публикация проверенного release

```cmd
git status --short
git switch main
git pull --ff-only origin main
git merge --ff-only fix/normalization-admin-diagnostics
git tag -a v0.5.4 -m "Robodovod intake and diagnostic hotfix v0.5.4"
git push --atomic origin main refs/tags/v0.5.4
git rev-list -n 1 v0.5.4
```

Если `--ff-only` невозможен, не создавать merge вручную: опубликовать branch,
сделать reviewed PR и тегировать получившийся commit `main`.

## 3. Read-only preflight VDS — можно выполнить сейчас

С клиентского ПК в `cmd.exe`:

```cmd
ssh -o BatchMode=yes -o ConnectTimeout=10 robodovod "hostname; nproc; free -h; df -h / /opt; docker version; docker compose version"
ssh -tt robodovod "sudo ufw status verbose && sudo ss -lntup && sudo docker info --format '{{.ServerVersion}}'"
ssh robodovod "cd /opt/robodovod && git status --short && git rev-parse HEAD && stat -c '%a %n' .env"
```

Ожидается clean server tree, `.env` mode `600`, открыты только 22/80/443,
5432/8000/5173 не слушают public interface. `-tt` даёт `sudo` терминал для
интерактивного ввода пароля; пароль не нужно присылать и нельзя помещать в
команду. 24.09.2026 с клиентского ПК подтверждены 4 vCPU, 7.8 GiB RAM,
74 GiB свободного места, Compose v5.5.1, clean checkout на
`19cbcbca8325aed6a0182a8d359522795d5a910f` и `.env` mode `600`.
Повторный интерактивный preflight подтвердил UFW active/default deny incoming,
allow только 22/80/443 для IPv4/IPv6, лишь SSH на public listening sockets,
Docker daemon 29.8.1. `docker volume ls` и `docker ps -a` не вывели записей;
этот VDS не содержит прежнего Docker stack или volume. Security group Selectel
и текущие публичные DNS ответы остаются отдельными внешними проверками.

## 4. Подготовка server checkout — можно выполнить без запуска

После публикации `v0.5.4`:

```bash
ssh robodovod
cd /opt/robodovod
git status --short
git fetch --prune --tags origin
test "$(git cat-file -t v0.5.4)" = tag
git show --no-patch --decorate v0.5.4
git switch main
git pull --ff-only origin main
test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 v0.5.4)"
git branch --show-current
```

Последняя команда должна вывести `main`, а проверяемый hash должен совпасть с
локальным `git rev-list -n 1 v0.5.4`.
`git verify-tag` подходит только для подписанного тега; приведённая выше
команда создаёт обычный annotated tag.

## 5. Production secrets

Локальный пароль БД, ранее попавший в диагностический вывод, не использовать
на VDS. Владелец подтвердил, что production credentials сгенерированы
независимо, и отложил локальную ротацию; она не блокирует этот deployment.
Локальный `.env` не печатать и не добавлять в Git.

На VDS, не на рабочем ПК:

```bash
cd /opt/robodovod
umask 077
test -e .env.production || cp .env.production.example .env.production
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
grep -Eq '^POSTGRES_ADMIN_USER=[A-Za-z0-9_]+$' .env.production
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

Перед migration существующей и уже инициализированной БД:

```bash
cd /opt/robodovod
sudo install -d -m 700 -o "$(id -un)" -g "$(id -gn)" /var/backups/robodovod
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d db
DOCKER='sudo docker' BACKUP_DIR=/var/backups/robodovod ./scripts/production/backup.sh
DOCKER='sudo docker' ./scripts/production/restore-drill.sh /var/backups/robodovod/postgres-YYYYMMDDTHHMMSSZ.dump
```

Для частичного backup `20260924T024748Z` оба файла уже прошли `sha256sum -c`;
архив uploads содержит пустой каталог, но остался root-owned. После обновления
кода сначала исправить права именно этого архива, затем проверить его manifest:

```bash
sudo chown "$(id -u):$(id -g)" /var/backups/robodovod/uploads-20260924T024748Z.tar.gz
chmod 600 /var/backups/robodovod/uploads-20260924T024748Z.tar.gz
sha256sum -c /var/backups/robodovod/sha256-20260924T024748Z.txt
```

Затем повторить `backup.sh` из `v0.5.3`, проверить новые checksum и выполнить
restore drill на новом dump. Не удалять старый backup до успешного drill.

На подтверждённой пустой установке restore drill до migration не пройдёт:
в dump ещё нет Alembic revision и 31 таблицы. Сначала выполните migration из
раздела 8, затем backup и restore drill по тем же командам. Наличие или
отсутствие прежней БД подтвердить до запуска по Docker volumes и server state;
существующий volume нельзя считать пустым по одному лишь отсутствию приложения.
Скрипты подключаются к PostgreSQL под ролью `POSTGRES_ADMIN_USER` из
`.env.production`; системный пользователь контейнера остаётся `postgres`.

Скопировать dump, uploads archive и checksum manifest в зашифрованное off-host
хранилище. Наличие локального файла без restore drill не считается backup.

## 8. Migration и first bootstrap — после публикации проверенного main/tag

```bash
cd /opt/robodovod
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C up -d db
$C run --rm migrate
$C build catalog-import catalog-activation economics-activation admin-bootstrap
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

Если остановка произошла на первом `BASE VALIDATE_ONLY` из-за инцидента выше,
`db` и migration уже выполнены. После pull `v0.5.3` и проверки двух SHA-256
возобновить раздел с `$C build catalog-import ...`, затем повторить
`BASE VALIDATE_ONLY`; не создавать новую БД и не повторять bootstrap.

Не активировать `runtime` для organizer catalog. После зелёного повторного C29
активировать versioned economics route отдельной командой:

```bash
$C run --rm economics-activation activate --actor production-c30 --approval-report /contracts/fixtures/economics-dual-run-report-v1.golden.json
```

Rollback economics меняет только route configuration:

```bash
$C run --rm economics-activation rollback --actor production-rollback
```

## 9. Traffic switch — отдельное ручное действие после всех gates

После публикации main/tag, backup/restore, миграций, activation и internal
проверок:

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

С клиентского ПК в `cmd.exe` проверить закрытые порты:

```cmd
powershell -NoProfile -Command "Test-NetConnection robodovod.ru -Port 443 -InformationLevel Quiet"
powershell -NoProfile -Command "Test-NetConnection robodovod.ru -Port 5432 -InformationLevel Quiet"
powershell -NoProfile -Command "Test-NetConnection robodovod.ru -Port 8000 -InformationLevel Quiet"
powershell -NoProfile -Command "Test-NetConnection robodovod.ru -Port 5173 -InformationLevel Quiet"
```

Ожидается `True` для 443 и `False` для последних трёх.

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
- production orchestrator golden связан с economics activation report;
- C29 повторён: 625 backend tests с PostgreSQL, 73 frontend tests,
  Draft 2020-12 commercial schema, lint и production build прошли;
- actual organizer catalog acceptance прошёл C11 → C13–C21 → reopen → replay →
  export без C05 PASS и без procurement-ready утверждения.

Эта прежняя локальная приёмка не обнаружила отсутствующий production C01 HTTP
route. Текущий C30 остаётся на HOLD до публичной проверки полного v2 flow после
hotfix: normalize → C11 → C13–C21 → reopen/replay/export.
