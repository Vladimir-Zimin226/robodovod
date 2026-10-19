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
| РД-помощник | `POST /api/assistant/service` — свободный диалог через Yandex Cloud с поиском по справке, методике и активному каталогу. |
| История и экспорт | `GET /api/projects/{project_id}/analysis-runs` и `/{run_id}`; `GET .../{run_id}/exports/investor-report.pdf`, `/investor-report-preview.pdf`, `/evidence.zip`. |
| Администратор каталога | `/api/admin/catalog`: версии, разделы, импорт JSON, validate, publish, activate и audit. |

Для `POST /api/assistant/service` передайте `message` (2–2000 символов) и, при продолжении диалога, до восьми предыдущих сообщений `history: [{"role":"user|assistant","content":"..."}]`. Ответ `service-assistant-chat-v2` содержит `reply` и список найденных `sources` с заголовками и ссылками на карточки, когда они есть. История не сохраняется сервером и не меняет проект. Ключ `YC_API_KEY` и папка `YC_FOLDER_ID` обязательны; модель задаётся `RD_ASSISTANT_MODEL` (по умолчанию `yandexgpt/latest`). При отсутствии конфигурации сервер возвращает 503, при недоступности модели 502/504.

`/ready` может вернуть 200 при ещё не импортированном каталоге. `discovery` нужен для просмотра каталога, `capacity` — для нового расчёта парка, отдельный economics route — для нового денежного расчёта. Legacy `runtime` маршруты на organizer bundle остаются недоступны. Статусы активации проверяются tools CLI из [инструкции запуска](GETTING_STARTED.md).

Изменяющие запросы к проектам и расчётам требуют действующую сессию и CSRF; данные проекта читаются только владельцем. Административные методы требуют роль ADMIN. Снимки расчётов и экспорта сохраняют свою версию и контрольные суммы. Для точного списка полей используйте OpenAPI текущего запущенного commit, а не примеры исторических спецификаций.

Новые денежные запуски формы используют `economics-explicit-inputs-v7` и оболочку `economics-run-input-v8`. Поле `implementation_lines` содержит `DELIVERY`, `COMMISSIONING`, `INTEGRATION` со статусом, суммой, источником и объяснением. Отсутствующая статья остаётся `UNKNOWN`; сервер сохраняет частичный результат и не выдаёт NPV/окупаемость покупки. Старые версии читаются без пересчёта. AI-маршруты Brain turn/retry, Roboexpert summary/web и assistant web оставлены как legacy и возвращают HTTP 410; детерминированные каталожные маршруты действуют.

Для нового расчёта по нескольким ролям в том же v7 вводе передайте `role_work_profiles`: по одной записи на каждый `process.role_refs` с `role_id`, `robotizable_fraction` (строка 0–1), `manual_units_per_shift` (положительная строка при доле больше нуля, иначе `null`), `residual_operations`, `source` (`USER` или `ASSUMPTION`), `basis`, `confirmed: true`. Доля основной роли должна совпадать с `work_share.fraction`. При ошибке или неполном наборе ролей денежная ветка останется частичной. Результат сохраняет допущения в `role_work_profiles`, а трудовые показатели каждой роли — в `role_labour` и в `scenarios[].role_labour` для рассчитанных веток. Парк роботов на процесс учитывается один раз.
