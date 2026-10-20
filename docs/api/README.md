# API РОБОДОВОДА

[Точная схема OpenAPI](openapi.json) и [все зарегистрированные маршруты](routes.md) создаются из текущего `backend/main.py` командой `python docs/api/generate_reference.py` из корня репозитория. `GET /openapi.json` и `GET /docs` доступны там, где их не закрывает внешний reverse proxy. Перед выпуском проверяйте, что сгенерированный файл не изменился. Схема включает и внутренние/admin маршруты; не считайте все пути публичными.

## Основной гостевой поток

| Назначение | Маршрут | Доступ |
| --- | --- | --- |
| Состояние процесса и БД | `GET /health`, `GET /ready` | без сессии; `ready` не доказывает активацию каталога |
| Шаблон склада | `GET /api/v2/warehouse-roles/template` | гость |
| Предпросмотр склада | `POST /api/v2/warehouse-roles/preview` | гость |
| Маршрут склада | `POST /api/v2/warehouse-roles/route-preview` | гость |
| PDF склада | `POST /api/v2/warehouse-roles/report.pdf` | гость |
| Шаблон объектного расчёта | `GET /api/v2/object-roles/{kind}/template` | гость; `kind` — `WAREHOUSE`, `AIRPORT` или `CLINIC` |
| Предпросмотр объекта | `POST /api/v2/object-roles/{kind}/preview` | гость |
| Маршрут объекта | `POST /api/v2/object-roles/{kind}/route-preview` | гость |
| PDF объекта | `POST /api/v2/object-roles/{kind}/report.pdf` | гость |
| Вход и согласие | `/api/auth/register`, `/login`, `/logout`, `/me`, `/privacy-consent` | правила в OpenAPI и auth router |
| Сохранение проектов и RobCraft | `/api/projects/...`, `/api/projects/{project_id}/robcraft-scene` | сессия, владелец проекта; для записи CSRF |

Публичные preview принимают JSON по Pydantic-схемам в OpenAPI. Три полных воспроизводимых payload находятся в [`frontend/src/showcasePresets.json`](../../frontend/src/showcasePresets.json). Пример локального вызова склада в PowerShell:

```powershell
$demo = Get-Content frontend/src/showcasePresets.json -Raw | ConvertFrom-Json
$body = $demo.retail.input | ConvertTo-Json -Depth 100
Invoke-RestMethod http://127.0.0.1:8000/api/v2/object-roles/WAREHOUSE/preview -Method Post -ContentType 'application/json' -Body $body
```

Для аэропорта/клиники замените ключ и путь на `airport`/`AIRPORT` либо `clinic`/`CLINIC`. Route-preview принимает тот же вход с рассчитанным процессом; точный contract приведён в OpenAPI и проверяется тестом `backend/test_showcase_presets.py`. Для PDF используйте тот же payload и соответствующий `report.pdf`; ответ имеет MIME `application/pdf`. Поля нагрузки и техники используют единицы в именах (`kg`, `m`, `hours`, `rub`); значения денег не превращайте из `null` в ноль.

`SCENARIO_TYPE` означает учебный тип без подтверждённого паспорта. `UNKNOWN` означает недостаток данных. `CAPACITY_SHORTFALL` указывает, что мощности сценария недостаточно; `NO_ROUTE` — что маршрут не найден. Такие статусы сами по себе не подтверждают подбор модели или закупочную рекомендацию. Коэффициенты воспроизведения 1×/2×/4×/8× отсутствуют в API: они ускоряют только клиентский курсор, а не робота и не NPV.

Обычные ошибки: `400` неверный сценарий, `401` нет сессии, `403` нет прав/CSRF, `404` ресурс не найден, `409` конфликт ревизии, `422` неверное тело, `503` каталог или файлы сцены недоступны. Точные детали и тела ошибок зависят от маршрута и приведены в OpenAPI/коде. Admin endpoints требуют отдельной роли; не используйте их для гостевой демонстрации.
