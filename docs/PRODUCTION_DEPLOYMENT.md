# Развёртывание в production

Этот runbook описывает текущие `compose.yaml` и `compose.production.yaml`. Он **не подтверждает состояние robodovod.ru**: live revision, данные, образ, DNS и пользовательский путь должны быть проверены оператором на сервере. В ходе подготовки документации production не обновлялся. Шаги с миграцией, каталогом и переключением трафика нельзя выполнять как один слепой сценарий.

## Что делает Compose

`db` — PostgreSQL 16 с named volume; `migrate` выполняет `alembic upgrade head`; `backend` запускается после успешной миграции; `frontend` — после готового backend; `caddy` проксирует сайт и `/api/*`, `/health`, `/ready`. Production overlay убирает опубликованные порты БД, backend и frontend, оставляя 80/443 у Caddy. Сети `data` и `edge` разделены. Проверено синтаксически: `docker compose --env-file .env.production.example -f compose.yaml -f compose.production.yaml config --quiet`. Сборка образов и запуск stack в этой среде не проверены, поскольку Docker Engine недоступен.

## Перед любым изменением сервера

1. Зафиксируйте текущий commit, теги образов, `docker compose ps`, Alembic revision и активные `discovery`/`capacity`/`runtime` и economics route. Сопоставьте их с планом выпуска. Если фактическое состояние неизвестно, остановитесь.
2. Сверьте чистоту server checkout и подготовьте отдельный **проверенный** commit/tag. Не считайте локальную ветку автоматически развернутой. Проверьте, что новая миграция совместима с данными и приложением. В репозитории Alembic head на 29.09.2026 — `0013_operation_batches`; это **не** утверждение о живой БД.
3. Для существующей БД сделайте операционный backup PostgreSQL и uploads, проверьте SHA-256 и восстановление в отдельной БД. Скрипты: `scripts/production/backup.sh` и `restore-drill.sh`; они работают с server-local `.env.production`, БД и volumes. Храните копию вне сервера. Убедитесь, что restore drill относится к **новому** dump.
4. Подготовьте изолированную проверку новой версии с TLS и тестовым проектом. Текущий Compose **не содержит отдельного preview slot**. Способ проверки до переключения публичного Caddy следует спроектировать и проверить для конкретного сервера. Пока его нет, безопасную универсальную команду traffic switch подтвердить нельзя.

## Конфигурация и проверка до запуска

На сервере создайте `.env.production` из [шаблона](../.env.production.example); храните его вне Git с правами `600`. Замените все placeholders. `DATABASE_URL` указывает на `db` и application role; административная роль PostgreSQL должна быть другой. `COMPOSE_PROJECT_NAME` фиксирует имена volumes; менять его при обновлении нельзя. Секреты и DSN не выводите в логи проверки.

```bash
cd /opt/robodovod
test -f .env.production
test "$(stat -c %a .env.production)" = 600
! grep -Eq '<[^>]+>' .env.production
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C config --quiet
$C ps
```

Команда `config --quiet` проверяет структуру Compose и подстановку переменных. Она не проверяет доступность БД, корректность секретов и готовность миграции. Нужные образы можно собрать командой `$C build backend frontend migrate catalog-import catalog-activation admin-bootstrap`, но факт успешной сборки на целевом сервере проверяется отдельно.

## Новая установка в пустую БД

После проверки, что это действительно **новая установка**, подготовьте данные в следующем порядке:

```bash
cd /opt/robodovod
C='sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml'
$C build backend frontend migrate catalog-import catalog-activation economics-activation admin-bootstrap
$C up -d db
$C run --rm migrate
$C run --rm catalog-import --phase BASE --mode VALIDATE_ONLY
$C run --rm catalog-import --phase BASE --mode COMMIT
$C run --rm catalog-import --phase ENRICHMENT --mode VALIDATE_ONLY
$C run --rm catalog-import --phase ENRICHMENT --mode COMMIT
$C run --rm catalog-activation validate --catalog-code organizer-catalog-v4
$C run --rm catalog-activation publish --catalog-code organizer-catalog-v4
$C run --rm catalog-activation activate --slot discovery --catalog-code organizer-catalog-v4 --actor production-operator
$C run --rm catalog-activation activate --slot capacity --catalog-code organizer-catalog-v4 --actor production-operator --approval-report /contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json
$C run --rm catalog-activation status
$C run --rm economics-activation activate --actor production-operator --approval-report /contracts/fixtures/economics-dual-run-report-v1.golden.json
$C run --rm economics-activation status
$C run --rm admin-bootstrap
```

Это CLI-команды действующего кода и Compose, **не протокол выполненной production-установки**. `capacity` принимает только соответствующий catalog digest и утверждённый report. Golden reports из репозитория пригодны только для неизменённых bundle и политик. `runtime` для этого каталога не активируется: legacy-роботов там нет. Economics route переключается **отдельно** и требует собственного принятого отчёта. Не включайте маршрут ради прохождения проверки без соответствия политике.

Для существующей БД **не повторяйте** bootstrap, import и activation автоматически. Сначала сравните текущие версии, источники и историю. При несовпадении bundle или схемы нужен отдельный план миграции данных.

## Приёмка и откат

Перед публичным переключением в изолированном окружении проверьте `/health` и `/ready`, вход, права владельца и CSRF, нормализацию процесса, каталог, новый расчёт парка, денежный расчёт, сохранение и повторное открытие, PDF/ZIP и 2D/3D. Проверьте текущие `/api/catalog/status` и `catalog-activation status`. После переключения повторите HTTP smoke через `scripts/production/smoke.sh` и пользовательский сценарий с клиентской машины. `/ready` подтверждает БД, но не полноту пользовательского пути.

Откат приложения возможен только на **проверенный совместимый** commit и образы. Не используйте `docker compose down -v` и production Alembic downgrade как обычный откат: сохранённые расчёты и новые таблицы могут сделать его разрушающим. Если старая версия несовместима со схемой, нужен roll-forward или отдельное восстановление по согласованному плану. Точные команды переключения и отката зависят от фактического состояния сервера и preview-схемы, которых репозиторий не задаёт.
