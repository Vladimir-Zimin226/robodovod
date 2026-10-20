# Самостоятельное развёртывание RC на существующем сервере

Этот порядок предназначен для оператора действующего `robodovod.ru`. Локальная команда не имеет доступа к серверу и не выполняла production backup или smoke. Исходный runbook: [PRODUCTION_DEPLOYMENT.md](../PRODUCTION_DEPLOYMENT.md). Release commit берите из итогового сообщения и проверяйте через `git rev-parse HEAD`.

## 1. Остановиться до изменений, если состояние отличается

На сервере проверьте, что checkout находится в ожидаемом каталоге (в runbook — `/opt/robodovod`), рабочее дерево чистое, `.env.production` существует и имеет права `600`. Не выводите файл или его переменные в логи/чат. Пользователь `deploy` на действующем сервере не имеет прямого доступа к Docker socket, поэтому Docker Compose запускается через `sudo`; пароль может запрашиваться. Сохраните текущий commit, идентификаторы работающих образов и результат `sudo docker compose ps` в приватном операционном журнале. Сравните текущую Alembic revision, активные `capacity`/`discovery`/`runtime` и economics route с ожидаемой конфигурацией. Никаких команд import/activate каталога ради этого релиза автоматически не требуется.

```sh
cd /opt/robodovod
git status --short
git rev-parse HEAD
test -f .env.production && test "$(stat -c %a .env.production)" = 600
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml config --quiet
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml ps
```

Если дерево грязное, commit неизвестен, Compose не совпадает с текущей инфраструктурой или схема БД неясна — не переключайте трафик. В текущем Compose нет независимого preview slot.

## 2. Резервная копия и проверка восстановления

До обновления кода и миграций запустите `scripts/production/backup.sh` на сервере. Он сохраняет PostgreSQL dump и uploads, создаёт SHA-256. Проверьте наличие всех трёх файлов и храните копию вне сервера. Затем запустите `scripts/production/restore-drill.sh /путь/к/созданному/postgres-....dump`; скрипт восстанавливает дамп в **отдельную** БД и проверяет Alembic revision/число таблиц. Не используйте старый дамп для этой проверки. Если backup или drill не прошёл, не продолжайте.

## 3. Код и приложение

Заказчик выбрал самостоятельный перенос локального Git bundle, без push в GitHub. Скопируйте `docs/recovery-v2/robodovod-rc-2026-10-20.bundle` с рабочей машины на сервер безопасным способом. Bundle содержит изменения после базового `f102d88`; на сервере этот commit должен существовать. Сначала выполните `git bundle verify /путь/к/robodovod-rc-2026-10-20.bundle`. Если prerequisite отсутствует, остановитесь и запросите полный пакет, не подменяйте историю. Затем создайте отдельную локальную RC-ветку командой `git fetch /путь/к/robodovod-rc-2026-10-20.bundle HEAD:refs/heads/rc/recovery-v2-2026-10-20`. Проверьте SHA и содержимое; только при чистом checkout переключитесь на эту ветку. Не используйте `git reset --hard` для сохранения неизвестных файлов сервера. Сохраните предыдущий commit для отката. Bundle не содержит незакоммиченных пользовательских файлов, `.env.production` и исходный WAV; веб-MP4 с AAC включён в Git-коммит.

Проверьте, что `frontend/public/privacy-policy.html` содержит РОБОДОВОД и данные оператора, а frontend и backend используют `robodovod-privacy-v1-2026-10-20`. Предыдущее значение согласия отвергается API; при обновлении может быть короткое окно несовместимости старой вкладки с новым backend. Попросите тестовых пользователей перезагрузить страницу.

После backup/drill и проверки совместимости снимка БД соберите `backend`, `frontend`, `migrate`. Применяйте только просмотренные Alembic миграции. Существующий Compose запускает `migrate` перед backend; не запускайте вторую миграцию параллельно. Затем обновите сервисы и дождитесь `healthy`.

```sh
sudo -v
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml build backend frontend migrate
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d backend frontend caddy
sudo docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml ps
```

Если фактическая инфраструктура не использует именно эти Compose-файлы, выполните её существующий workflow с теми же воротами backup, проверки миграции и smoke. Не удаляйте volume БД/файлов и не повторяйте bootstrap/import/activation на существующей БД.

## 4. Production smoke перед объявлением выпуска

1. `scripts/production/smoke.sh`: `/health`, `/ready`, главная и редирект `www`.
2. Проверьте HTTP Range для видео: `curl -fI https://robodovod.ru/demo/trailer/robodovod-trailer-web-720p.mp4`; затем `curl -fsS -H 'Range: bytes=0-1023' -o /dev/null -w '%{http_code}\n' https://robodovod.ru/demo/trailer/robodovod-trailer-web-720p.mp4` должен вернуть `206`. В браузере Play по нажатию, звук, Mute/Unmute и перемотка; silent preview не включает звук автоматически.
3. Откройте `https://robodovod.ru/privacy-policy.html`; проверьте данные оператора и версию. Создайте тестовый аккаунт с явным согласием, войдите/выйдите, проверьте недоступность чужого проекта. Удалите тестовые данные штатным способом после проверки.
4. Склад, аэропорт, клиника: пять шагов, 2D/3D движение и пауза, деньги/«Что если?», результат и PDF. Для неподтверждённой модели финансы должны быть явно сценарными либо недоступными.
5. RobCraft: каталог `i`, размещение/удаление, зоны, движение, экономика, save/reopen. Повторите ключевые экраны на 360/390/768 px. Просмотрите browser console и журналы backend/Caddy без публикации секретов.

Не объявляйте production PASS только по `/ready`: он не подтверждает каталог, браузер и PDF.

## 5. Если smoke не прошёл

Остановите выпуск и верните трафик на **предыдущие проверенные совместимые** образы/commit. Если новая схема уже несовместима со старым backend, предпочтителен исправляющий roll-forward или восстановление из только что проверенного dump по отдельному плану с остановкой записи. Не выполняйте `docker compose down -v` и слепой Alembic downgrade. Запишите фактический commit, ошибку и результаты smoke в `RELEASE_CANDIDATE_REPORT.md`.

Номер уведомления Роскомнадзора `100293352` и дата `22.05.2026` предоставлены оператором из политики другого сервиса. Перед публичным запуском оператору следует проверить актуальность сведений уведомления для обработки в РОБОДОВОДЕ и фактическое размещение данных в production; новый документ не выдаёт эти сведения за проверенные автоматически.
