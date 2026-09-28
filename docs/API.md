# Карта API

Backend — FastAPI. Точные типы запросов и ответов берите из `/openapi.json` работающего экземпляра ([локальный Swagger UI](http://localhost:8000/docs)). Код маршрутов: [main.py](../backend/main.py), [persistence_api.py](../backend/persistence_api.py), [admin_catalog_api.py](../backend/admin_catalog_api.py), [evidence_export_api.py](../backend/evidence_export_api.py).

| Область | Основные маршруты |
| --- | --- |
| Состояние | `GET /health` — liveness; `GET /ready` — соединение с БД; `GET /api/catalog/status` — активные источники после `discovery`. |
| Сессия | `POST /api/auth/register`, `/login`, `/logout`; `GET /api/auth/me`. |
| Проекты | `GET/POST /api/projects`; `GET/PATCH/DELETE /api/projects/{project_id}`; файлы через `/files/preview` и `/files`. |
| Ввод и каталог | `POST /api/v2/calculation-intake/normalize`; `GET /api/catalog/models` и `/positions/{position_id}`. |
| Физический расчёт | `POST /api/v2/capacity-analyses`; `GET /api/v2/capacity-analyses/{run_id}`. |
| Денежный расчёт | `POST /api/v2/projects/{project_id}/economics-runs`; `POST .../economics-runs/preview`; `POST .../economics-runs/{run_id}/replay`. |
| История и экспорт | `GET /api/projects/{project_id}/analysis-runs` и `/{run_id}`; `GET .../{run_id}/exports/investor-report.pdf`, `/investor-report-preview.pdf`, `/evidence.zip`. |
| Администратор каталога | `/api/admin/catalog`: версии, разделы, импорт JSON, validate, publish, activate и audit. |

`/ready` может вернуть 200 при ещё не импортированном каталоге. `discovery` нужен для просмотра каталога, `capacity` — для нового расчёта парка, отдельный economics route — для нового денежного расчёта. Legacy `runtime` маршруты на organizer bundle остаются недоступны. Статусы активации проверяются tools CLI из [инструкции запуска](GETTING_STARTED.md).

Изменяющие запросы к проектам и расчётам требуют действующую сессию и CSRF; данные проекта читаются только владельцем. Административные методы требуют роль ADMIN. Снимки расчётов и экспорта сохраняют свою версию и контрольные суммы. Для точного списка полей используйте OpenAPI текущего запущенного commit, а не примеры исторических спецификаций.
