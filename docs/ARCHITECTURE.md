# Архитектура

Порядок запуска — в [быстром старте](GETTING_STARTED.md), карта маршрутов — в
[API](API.md). Ниже кратко описаны слои и основные контракты.

Актуальный код: `backend/main.py`, `backend/persistence_api.py`,
`backend/calculation/`, `frontend/src/`, `robcraft/`, `compose.yaml`.

**Локально:** Docker Desktop, копия `.env.example` в `.env` с собственными
секретами и URL-encoded паролем приложения. В Windows CMD из корня:

```cmd
copy .env.example .env
docker compose up --build -d
curl.exe -f http://localhost:8000/ready
```

Заполните placeholders в `.env` до запуска. UI — `http://localhost:5173`,
API и OpenAPI — `http://localhost:8000/docs`. Compose поднимает PostgreSQL,
применяет Alembic `head`, затем backend/frontend. Секреты, реальные .env,
backup и персональные данные в комплект не включаются.

**Слои:** React/Vite управляет вводом и показом; FastAPI/Pydantic проверяет
контракты и владельца; SQLAlchemy/PostgreSQL хранят project, scenario и
immutable AnalysisRun. C03 нормализует процесс, C05 проверяет ограничения,
C11 считает парк, C14 — труд и новый штат, C15–C18 — денежные потоки,
C19 — предварительное ранжирование, C23 — модельный прогон.
ScenarioSpec связан с конкретным C11/economics run. PDF/ZIP читают
снимки, checksum и версии, не считают новую экономику.

**Основные маршруты:** `POST /api/v2/capacity-analyses`,
`POST /api/v2/projects/{project_id}/economics-runs`, новый
`POST /api/v2/projects/{project_id}/economics-runs/preview` и
`POST /api/v2/projects/{project_id}/picking-study/preview`.
Точные схемы публикует `/openapi.json`. Изменяющие запросы требуют CSRF,
сохранённые расчёты и предпросмотр проверяют владельца. Новый экономический
ввод — `economics-explicit-inputs-v6`; старые версии не мигрируются в новые
числа автоматически.

**Деплой:** инструкция для исходного окружения —
[production runbook](PRODUCTION_DEPLOYMENT.md). Команды и состав обновляемых
сервисов выбирают под конкретный commit. Этот документ описывает устройство
проекта, а не состояние текущего сервера.
