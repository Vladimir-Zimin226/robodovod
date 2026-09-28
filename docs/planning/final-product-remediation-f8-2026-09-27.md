# F8 — локальный кандидат финальной сдачи, 27.09.2026

**Статус: частично выполнено; финальная приёмка не пройдена.** F1–F7 приняты
локально. Этот этап подготовил проверяемый комплект и выполнил числовые,
PostgreSQL, frontend и нагрузочные проверки. Полный browser путь, сторонний clean checkout, demo-доступы и
production HTTPS остаются открытыми gates. Поэтому выпуск нельзя обозначать
как принятый по всему ТЗ или готовый к передаче по пункту 8.2.

## Что подготовлено

- [Руководство пользователя, администратора, архитектура, формулы, ограничения
  и сценарий показа](FINAL_DELIVERY_2026-09-27.md), его DOCX и презентация
  PPTX в [`docs/delivery/f8`](../delivery/f8). Там же OpenAPI и инвентаризация
  библиотек/лицензий. Это локальные артефакты; лицензии внешних данных требуют
  отдельного подтверждения правообладателя.
- Обезличенный guest package v2 для типового склада, отдельный sample ZIP
  220 паллет/сутки и 120 м. Старый guest v1 и golden v2 оставлены побайтно
  прежними; новый golden фиксирует текущую проекцию экономики.
- Кэш опубликованных immutable catalog snapshots с инвалидированием по
  активному slot identity; ограничение выдачи каталога `limit/offset`. Для
  локального профиля нагрузки production backend настроен на четыре worker.
  Размер ресурсов production не подтверждён локальным замером.

## Свидетельства и границы

| Проверка | Результат | Граница |
|---|---|---|
| Backend + disposable PostgreSQL 17 | 864 passed | Не production БД |
| RobCraft | 83 passed | Последний доступный локальный запуск |
| Frontend test/lint/build | F8: 135 passed, lint/build passed | Запуск вне файловой песочницы разрешён; Vite предупредил о JS chunk >500 kB, сборка успешна |
| Генерация guest package и glossary | `--check` прошёл | Проверяет воспроизводимость файлов, не UI |
| 50 пользователей, 450 HTTP read requests | p95: defaults 323 мс, catalog 748 мс, projects 351 мс | Локальный Windows PostgreSQL 17, Uvicorn 4 workers, YC отключён; регистрация/создание проекта вне окна; [JSON](../delivery/f8/load-probe.json) |
| 220/120 экономика + симуляция | 3 прогона: экономика 928–1058 мс, симуляция 12–14 мс | In-process synthetic; HTTP, запись в БД и очередь исключены; [JSON](../delivery/f8/timing-probe.json) |
| Сохранённые локальные данные | 141 analysis runs, 44 artifacts; SHA sample ZIP `4e7c1ef6852d08522c1c0a88c3557d68e7b69c4181187205368ee8e977a1e169` | Снимок disposable БД после тестов, не сравнение живой БД до/после; [JSON](../delivery/f8/integrity-probe.json) |
| Browser 1366×768 и 390 px | F8 production build: Chrome/Edge navigation, direct link, Back/reload, project restore, ADMIN denial прошли | Синтетические read-only API replies; полный F8 product journey не повторён; [JSON](../delivery/f8/browser-navigation.json), скриншоты `.tmp/f8-browser-navigation` |
| YC failure / malformed upload | Покрыто тестами F2/F6 и backend F8 | Свежий ручной browser walkthrough и live YC latency не подтверждены |

## Матрица обязательного объёма

| ТЗ | Состояние в текущем кандидате | Основание / открытый gate |
|---|---|---|
| 3.2, 3.3.5, 3.4 | Реализовано локально | F2 workbook/preview, F3 ручной ADMIN catalog, F4 explainable selection; повторный F8 browser обязателен |
| 3.5, 3.6, 3.7 | Реализовано локально | F5 bundle, F1 выбранный ScenarioSpec/C23/2D/3D/SVG, PDF/XLSX/CSV/ZIP; 220/120 и типовой склад в F1–F5; F8 browser обязателен |
| Три типа объектов | Подтверждены паспорта и каталог; полный числовой путь — склад | Аэропорт/клиника не выданы за поддержанные складские формулы |
| 3.8, 4.1–4.2 | Документировано | Актуальный OpenAPI и границы интеграций в комплекте; production конфигурацию проверить на сервере |
| 4.3.1–4.3.3 | Локальные цели измерены | 50-user read p95 пройден; economics/simulation только in-process; HTTP job/progress и живой YC открыты |
| 4.4–4.5 | Код и прежние gates есть | Owner/CSRF/roles входят в backend suite; новый независимый проход, desktop/mobile и удаление после импорта открыты |
| 5.1–5.7, 6.1–6.10 | Документы/презентация/sample готовы | Демонстрация на финальном build и сторонний запуск открыты |
| 8.2.1–8.2.8 | Не закрыто | Нет pinned release tag, двух проверенных USER/ADMIN доступов, чистой сборки и HTTPS smoke |

Исходная [матрица аудита](final-tz-compliance-audit-2026-09-26.md) остаётся
историческим baseline от 26 сентября. Для новых свидетельств использовать
этот отчёт, а не переписывать оценки задним числом.

## Оставшиеся шаги приёмки

1. Выполнить полный browser walkthrough 1366×768 и
   390 px: guest/offline, USER без подсказок, manual/Brain/XLSX 220/120,
   типовой склад, три сценария и sensitivity, C23/2D/3D, все экспорты,
   history/reopen/recalculate, ADMIN edit/publish и отказ без роли.
2. Повторить timed HTTP economics и simulation job с progress на целевой
   конфигурации; измерить YC отдельно. Проверить malformed upload и отказ YC в
   браузере, не теряя проект.
3. Проверить clean checkout/build, выдать проверенные USER/ADMIN доступы
   отдельным защищённым каналом, закрепить commit/tag и сверить manifest.
4. После согласованного обновления сервера пройти HTTPS smoke и сравнить
   counts/digests исторических записей до и после. Живые immutable runs,
   snapshots и simulation artifacts не переписывать.

## Windows CMD для оператора сервера после готовности локальных gates

Рабочий каталог и существующий `.env.production` должны быть заданы оператором.
Эти команды пока **не выполнены** и не являются свидетельством deploy:

```cmd
cd C:\path\to\robodovod
git status --short
git fetch --tags origin
git checkout <approved-release-tag>
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml build backend frontend
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d --wait db
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml run --rm migrate
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d --wait backend frontend caddy
curl.exe -f https://robodovod.ru/ready
curl.exe -f https://robodovod.ru/openapi.json -o NUL
```

Перед применением сверить текущую Alembic revision и фактический tag; после
обновления выполнить авторизованный USER/ADMIN smoke и сверку digests. Серверный
backup в рамках этого задания не требуется. Не выполнять `down -v`, downgrade,
повторный bootstrap/import или изменение сохранённых run/artifact строк.
