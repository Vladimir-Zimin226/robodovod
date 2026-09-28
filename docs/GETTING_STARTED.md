# Локальный запуск и подготовка каталога

Команды ниже выполняются из корня репозитория. Они проверены по `compose.yaml`, CLI в `backend/catalog_importer.py` и `backend/catalog_activation.py`. Полный запуск контейнеров в этой среде проверить не удалось: Docker Engine недоступен. Поэтому после старта обязательно проверьте фактический статус у себя.

## Docker Compose

1. Установите Docker с Compose и запустите Engine. Скопируйте [шаблон](../.env.example) в `.env`. Замените все `<...>`: имя БД, разные роли/пароли PostgreSQL, `DATABASE_URL` с host `db`, email администратора. URL-кодируйте пароль в DSN. Для работы без внешнего LLM задайте `YC_FOLDER_ID=` и `YC_API_KEY=`.
2. В PowerShell:

   ```powershell
   if (!(Test-Path .env)) { Copy-Item .env.example .env }
   # После заполнения .env:
   docker compose config --quiet
   docker compose up --build -d
   docker compose ps
   curl.exe -f http://localhost:8000/ready
   ```

   `db` → `migrate` → `backend` → `frontend` связаны через health/dependency в Compose. `/ready` подтверждает подключение backend к БД, но **не** наличие расчётного каталога. UI: <http://localhost:5173>; API: <http://localhost:8000/docs>.

## Первый импорт на пустой БД

Bundle находится в [data/import/organizer-catalog-v4](../data/import/organizer-catalog-v4/README.md). Команды ниже меняют локальную БД только на шагах `COMMIT`, `publish` и `activate`. Сервис `tools` не стартует при обычном `up`. Соберите tools-образ после изменения checkout.

```powershell
docker compose --profile tools run --rm --build catalog-import --phase BASE --mode VALIDATE_ONLY
docker compose --profile tools run --rm catalog-import --phase BASE --mode COMMIT
docker compose --profile tools run --rm catalog-import --phase ENRICHMENT --mode VALIDATE_ONLY
docker compose --profile tools run --rm catalog-import --phase ENRICHMENT --mode COMMIT
docker compose --profile tools run --rm --build catalog-activation validate --catalog-code organizer-catalog-v4
docker compose --profile tools run --rm catalog-activation publish --catalog-code organizer-catalog-v4
docker compose --profile tools run --rm catalog-activation activate --slot discovery --catalog-code organizer-catalog-v4
docker compose --profile tools run --rm catalog-activation activate --slot capacity --catalog-code organizer-catalog-v4 --approval-report /contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json
docker compose --profile tools run --rm catalog-activation status
docker compose --profile tools run --rm --build economics-activation activate --approval-report /contracts/fixtures/economics-dual-run-report-v1.golden.json
docker compose --profile tools run --rm economics-activation status
curl.exe -f http://localhost:8000/api/catalog/status
```

Проверяйте код завершения каждой команды до следующей. `discovery` открывает библиотеку; `capacity` нужен для нового физического расчёта и принимает только отчёт, соответствующий политике, digest и содержимому каталога. Включённый golden report относится к неизменённому organizer bundle. При отказе активации разберите причину, не обходите проверку. `runtime` не активируется для этого bundle: legacy API, который его требует, возвращает 503. `/api/catalog/status` требует активного `discovery`.

Для первой учётной записи администратора после миграции и заполнения `BOOTSTRAP_ADMIN_*`:

```powershell
docker compose --profile tools run --rm --build admin-bootstrap
```

Повторный запуск на существующей БД: сначала `catalog-activation status`, затем запускайте только недостающие шаги. `docker compose down` сохраняет named volumes; удаление с `-v` удаляет данные. Папки `backup/`, `Разобрать/` и локальный `.env` не являются частью запускаемой копии Git.

## Без Docker

Нужны Python 3.12+, Node.js версии, совместимой с Vite 8 (в проекте использовалась 22.12+), и PostgreSQL 16. Настройте отдельную БД, application role и `DATABASE_URL` с host `localhost`. В PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd ci --prefix frontend
$env:DATABASE_URL = 'postgresql+psycopg://<application-role>:<url-encoded-password>@localhost:5432/<database-name>'
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload --port 8000
```

Во втором терминале: `npm.cmd run dev --prefix frontend`. Для импорта и активации через Python установите `PYTHONPATH=backend` и передавайте те же аргументы модулям `catalog_importer` и `catalog_activation`, но отчёт для `capacity` задавайте путём `contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json`. Этот путь зависит от текущего каталога; выполняйте из корня репозитория.
