# РОБОДОВОД

РОБОДОВОД помогает предварительно оценить роботизацию конкретной операции: описать объект и нагрузку, посмотреть решения каталога, рассчитать потребный парк, сравнить покупку с арендой и сохранить результат с допущениями, 2D/3D-сценой и экспортом. Основной демонстрационный процесс — перевозка **подготовленных** паллет; отбор и упаковка считаются отдельно. Проект команды **ZMNCRAFT** для ЛЦТ‑2026.

## Состояние и границы

В репозитории есть код интерфейса, API, версионированных расчётов, каталога и экспорта. Примеры используют учебные и введённые пользователем условия. Итог — **предварительная оценка**, а не инженерный проект, подтверждение поставки или оферта. Для решения о внедрении нужны замеры на объекте, проверка безопасности и интеграций, паспорт техники и письменные коммерческие условия. Неизвестная цена не равна нулю; при нехватке входов финансовый результат остаётся частичным. Исторические сохранённые расчёты не пересчитываются автоматически.

Локальный Compose запускает сервисы и миграции, но **не импортирует и не активирует каталог**. Просмотр каталога требует активного `discovery`, расчёт парка в новом проектном маршруте — одобренного `capacity`. Старые маршруты с `runtime` на каталоге организаторов недоступны: в нём нет пригодной legacy-проекции. Код и Compose проверены; живой production в рамках подготовки документации не проверялся и не обновлялся.

## Как устроено

`frontend/` — React/Vite: ввод, результаты и экспорт. `backend/` — FastAPI: права доступа, каталог, проверка ограничений, расчёт мощности и экономики, сохранение версий и симуляция. `robcraft/` показывает условную 3D-сцену. PostgreSQL хранит проекты, версии каталога и расчёты; Alembic применяет схему. Compose соединяет сервисы, а в production Caddy принимает HTTP(S). Подробнее: [архитектура](docs/ARCHITECTURE.md).

## Локальный запуск и каталог

Нужен запущенный Docker Engine с Compose. Команды выполняются из корня репозитория в PowerShell. Скопируйте [шаблон](.env.example) в `.env`, замените **все** `<...>` собственными значениями; `DATABASE_URL` должен указывать на `db`, пароль в URL кодируется. Роли администратора PostgreSQL и приложения должны различаться.

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Заполните .env до следующей команды.
docker compose up --build -d
docker compose ps
curl.exe -f http://localhost:8000/ready
```

Интерфейс: <http://localhost:5173>; OpenAPI: <http://localhost:8000/docs>. Для **пустой локальной БД** последовательно импортируйте bundle, опубликуйте его и активируйте слоты:

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
```

Фиксированный отчёт для `capacity` привязан к включённому bundle и политике: при изменении данных команда должна отказать. `runtime` здесь не активируйте. Для повторного запуска с уже заполненной БД сначала проверьте статус, затем выполняйте только нужные операции. Подробности, проверка состояния и запуск без Docker: [локальный старт](docs/GETTING_STARTED.md). Остановка без удаления данных: `docker compose down`.

## Документы и материалы

- [Путь пользователя](docs/USER_GUIDE.md), [карта API](docs/API.md), [расчёты и ограничения](docs/CALCULATIONS.md).
- [Управление каталогом](docs/ADMIN_CATALOG.md), [production runbook](docs/PRODUCTION_DEPLOYMENT.md).
- [Пример инвестиционной оценки, PDF](docs/examples/investment-assessment-2026-09-28.pdf) — сохранённый учебный расчёт от 28.09.2026; цена, зарплаты и условия в нём являются сценарными допущениями.
- [Презентация, PDF](docs/presentation/Robodovod-ZMNCRAFT-2026.pdf) ([PPTX](docs/presentation/Robodovod-ZMNCRAFT-2026.pptx)). [Индекс документов](docs/README.md) отделяет действующие инструкции от [планов и истории](docs/planning/README.md).

## Команда и контакты

**ZMNCRAFT:** Владимир Зимин, капитан команды, Томари — Telegram **@vovzmncraft**; Евгений Юрченко, Хабаровск — Telegram **@pawuk_ptr**.
