# API

Backend — FastAPI. Точная версия контрактов доступна в интерактивной документации `/docs` и машинной спецификации `/openapi.json` работающего экземпляра: локально <http://localhost:8000/docs> и <http://localhost:8000/openapi.json>. Этот файл служит картой API, а не заменой схем запросов и ответов.

| Область | Примеры маршрутов | Назначение |
| --- | --- | --- |
| Состояние сервиса | `GET /`, `GET /ready` | Liveness и готовность БД |
| Сессия | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` | Регистрация, вход и текущий пользователь |
| Проекты | `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{project_id}` | Владеемые проекты и их параметры |
| Каталог | `GET /api/catalog/models`, `GET /api/catalog/positions/{position_id}` | Модели, позиции и источники |
| Расчёт парка | `POST /api/v2/capacity-analyses`, `GET /api/v2/capacity-analyses/{run_id}` | Физический анализ по подтверждённому процессу |
| Экономика | `POST /api/v2/projects/{project_id}/economics-runs`, `POST /api/v2/projects/{project_id}/economics-runs/preview` | Сохранённый расчёт и предварительное денежное сравнение |
| Комплектация | `POST /api/v2/projects/{project_id}/picking-study/preview` | Отдельное предварительное исследование отбора |
| История | `GET /api/projects/{project_id}/analysis-runs`, `GET /api/projects/{project_id}/analysis-runs/{run_id}` | Сохранённые версии результата |

Изменяющие запросы к проектам и расчётам требуют действующей сессии и CSRF; доступ к сохранённым данным проверяется по владельцу. Авторизация администратора нужна для управления пользователями и каталогом. Снимки входов и результатов версионируются; старые расчёты не заменяются новыми числами при чтении.

Исходники маршрутов: [`backend/main.py`](../backend/main.py) и [`backend/persistence_api.py`](../backend/persistence_api.py). [Архитектура](ARCHITECTURE.md) объясняет связь маршрутов с расчётными и визуальными модулями; [расчётные границы](CALCULATIONS.md) описывают, какие входы нужны для денежного вывода.
