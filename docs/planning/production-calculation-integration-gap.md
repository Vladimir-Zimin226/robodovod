# Production calculation integration gap — 2026-09-24

Статус: **BLOCKED FOR FULL PUBLIC RELEASE**. Владелец выбрал полноценный сервис
с работающим расчётом после исправлений, а не каталог без расчёта. Эта проверка
не изменяет принятые формулы, registry v1, catalog membership или исторические
runs.

## Исполняемый путь сейчас

1. Основной экран `frontend/src/App.jsx:recalc` вызывает legacy
   `POST /api/calculate`; `saveAnalysis` выбирает legacy `/analysis-runs` для
   результата этого пути. Пустой fresh DB не имеет `runtime` slot, а
   `organizer-catalog-v4` не содержит `runtime_robots`. Активация этого каталога
   в `runtime` правильно отвергается.
2. Экран «Процессы и роли v2» делает только
   `POST /api/v2/calculation-intake/normalize`. Он не выбирает capacity position
   и не создаёт capacity/economics run.
3. Persistence v2 API требует `resolve_economics_version` и
   `calculate_economics_v2`; `main.app` их не передаёт. Тест API подставляет
   fixture executor, который возвращает готовый commercial bundle; такого
   production orchestrator в репозитории нет.
4. Даже прямой вызов production C11 с готовым capacity-кандидатом использует
   `conservative_constraints`. Он знает только object/process scope и даёт
   `NEEDS_VALIDATION`, в частности для обязательных проверок technical passport
   и availability. `analyze_capacity` в этом состоянии возвращает `BLOCKED`.
   Положительный C11 golden явно подменяет provider на тестовый `ELIGIBLE`.
   Это допустимый unit test формул, но не доказательство исполнимости на VDS.

Дополнительно исходный backend image не содержал committed snapshots
`data/calculation` и `data/review/process-profile-coverage-v1.json`. Dockerfile
исправлен; локально собранный image успешно загрузил registry, executability,
constraints, process catalog и C11 version bindings.

## Что требуется для полноценного выпуска

- Для конкретного поддержанного процесса и позиции: проверить официальные
  model facts и источник технического паспорта/availability, собрать явные
  требования объекта с provenance, провести C05 до `ELIGIBLE` без test provider.
  Текущий `catalog_capacity_runtime.json` намеренно фиксирует
  `deployment_ready_models=0`; выдавать его за deployment-ready нельзя.
- Подключить UI к нормализованным процессам, отдельному capacity slot и
  server-owned C11 endpoint. Для неизвестных фактов показывать `BLOCKED` или
  `PARTIAL` с причиной, не подставлять скрытые значения.
- Реализовать production orchestrator C13–C21 поверх неизменных validated
  snapshots и явных user inputs. Создавать commercial bundle и ScenarioSpec v2
  на сервере, затем подключить versioned economics route. Fixture bundle не
  может быть runtime executor.
- Пройти новый сквозной тест браузер → API → official catalog → C05/C11 →
  C13–C21 → immutable run → reopen/export, включая tenant/CSRF, goldens,
  deterministic replay и повторный C29 gate. Только после этого C30 может
  продолжить migration/bootstrap/traffic switch.

Следующее внешнее входное условие: evidence-backed факты и требования хотя бы
для одного реально поддержанного сценария. Без них C05 не может честно
подтвердить `ELIGIBLE`; изменение gate на `PASS` по умолчанию запрещено.
