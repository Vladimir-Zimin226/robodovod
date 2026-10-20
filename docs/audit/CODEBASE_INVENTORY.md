# Инвентаризация кодовой базы, 21.10.2026

`git ls-files` на HEAD `59b36d3` показывает 1618 отслеживаемых путей: `docs` 649, `frontend` 293, `backend` 241, `contracts` 148, `scripts` 107, `data` 85, `robcraft` 70. Проверены entrypoints, маршруты OpenAPI, вызовы изменённых компонентов и candidate для удаления; это обзор структуры и затронутых потоков, а не доказательство отсутствия всех динамических интеграций.

| Область | Entrypoint и источник истины | Риск |
| --- | --- | --- |
| React/Vite | `frontend/src/main.jsx`, `App.jsx`; immutable DEMO `showcasePresets.json` | устаревший асинхронный ответ, локальный state |
| FastAPI | `backend/main.py`; 129 путей в `docs/api/openapi.json` | гостевые preview, auth/CSRF, владелец проекта |
| Расчёт | `backend/calculation/` и role API | пригодность, парк, ФОТ, CAPEX/OPEX, NPV |
| Сцены/симуляция | `data/scenes`, `backend/calculation/scene_simulation.py`; WebGL/2D frontend | файлы обязательны в Docker image |
| PDF | `role_report_view.py` → `role_report.py` → `readable_report.py` | коллизии при переносе и сравнение с UI |
| Каталог | `data/import/organizer-catalog-v4`, `backend/catalog_*` | `discovery` и `capacity` активируются отдельно |
| Persistence | PostgreSQL, Alembic в `backend/`, project/RobCraft APIs | миграции и пользовательские данные не удалять |
| Деплой/тесты | `compose*.yaml`, `backend/Dockerfile`, `scripts/`, `frontend/tests`, `backend/test_*` | production схема и конфигурация должны совпадать |

Основной pipeline: inputs → roles/fit → SceneModel/route → capacity/economics → report view → UI/PDF. Подробнее: [архитектура](../architecture/OVERVIEW.md). RobCraft живёт в `robcraft/` и сохраняется через project API. Архивы `docs/handoff` и `docs/planning` сохранены как история; их код не является текущим entrypoint.
