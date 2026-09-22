# Frontend capacity results trace

Статус: **IMPLEMENTED**, C12, 2026-09-23.

## Результат

Добавлен отдельный presentation flow для `capacity-analysis-response-v2`.
`App.jsx` выбирает его только по versioned schema; legacy `/api/calculate`
responses продолжают открываться в прежнем `ResultsPanel`. Сохранённый
`CAPACITY_ANALYSIS` открывается через owner-scoped
`GET /api/v2/capacity-analyses/{run_id}`, а не через live catalog.

View model проверяет совпадение run/process/input revision с trace и отклоняет
устаревший ответ. Decimal strings и units отображаются без преобразования или
frontend-арифметики. Панель раздельно показывает recommended и selected fleet,
nominal/effective capacity, coverage, raw load, utilization и overload;
blocked/NOT_APPLICABLE не получают фиктивных нулей.

## Trace и границы

Drilldown показывает серверные formula nodes, inputs, provenance, outputs,
assumptions, constraint checks и version bindings. Отсутствующая экономика
показана как отсутствующая, без KPI-заглушек. Метка «Участвует в расчёте» имеет
явное предупреждение, что она не означает SLA, готовность к внедрению или
deployment-ready.

Frontend adapter поддерживает POST с CSRF и immutable GET, проверяет revision и
отбрасывает более старый concurrent response. C12 не добавляет формул, ranking,
economics, каталог membership, simulation UI или production activation.

## Проверки и rollback

Unit fixtures покрывают COMPLETE, WITH_ASSUMPTIONS, BLOCKED, ручной парк,
overload, отсутствие economics, mixed identity, stale revision, API create/read
и точное golden-представление decimal values/units. Проверяются весь frontend
test suite, ESLint и production build.

Rollback удаляет capacity adapter/view model/component и возвращает выбор run к
legacy path; backend snapshots C11 и старые runs не изменяются. Следующий
обязательный этап — C13 `procurement/commercial-inputs-v1`.
