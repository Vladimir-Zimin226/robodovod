# Visualization 2D SimulationReport

Статус: **IMPLEMENTED**, C24 `visualization/2d-simulation-report`, 2026-09-23.

Живое уточнение 2026-09-24: нынешняя 2D-картинка — синтетический треугольный
20-секундный цикл для всех роботов, не warehouse layout и не timeline событий
C23. Она требует отдельной продуктовой доработки и ясной подписи происхождения
геометрии. См. [план исправления](live-calculation-remediation-2026-09-24.md).

## Результат

Добавлен защищённый lifecycle adapter над единственным расчётным источником —
C23 `run_simulation`. `POST /api/v2/simulations` запускает strict
`SimulationRequest v1`, `GET /api/v2/simulations/{request_id}` возвращает
revision-bound progress/terminal state, а
`POST /api/v2/simulations/{request_id}/cancel` фиксирует typed `CANCELLED`.
Мутации требуют действующую сессию и CSRF, чтение — сессию; `tenant_id` обязан
равняться authenticated owner, а `project_id` проверяется owner predicate.
Process-local lifecycle registry не изменяет БД, AnalysisRun или старые reports.

Новый offline SVG consumer принимает только связку ScenarioSpec v2 +
SimulationReport v1 с совпадающими request/tenant/project/scenario revision.
Он показывает zones, routes, fleet, operations и non-spatial charging badge,
controls start/pause/stop/restart/speed и выбор сценария. Timeline зависит
только от scenario seed и simulation time; speed меняет воспроизведение, но не
порядок, snapshot или KPI. Каждый visual event содержит scenario revision,
report digest, seed и simulation time.

## Честность данных и presentation

Required, expected и observed capacity, queue/wait/turnaround, productive/busy/
nonproductive utilization, resource wait, SLA, limitations и deviation verdict
читаются непосредственно из C23 report. Frontend не содержит capacity,
finance, SLA или queue formulas и не меняет economics snapshot. `PASS`
показывается только при C23 verdict `PASS`; `NOT_EVALUATED` и `CONDITIONAL`
сохраняются явно. Warning определяется server verdict
`DEVIATION/OVERLOADED/INPUT_MISMATCH`, включая утверждённую границу строго
больше 10%.

Synthetic geometry имеет метку `SYNTHETIC` и assumption reference; provided
геометрия — `PROVIDED_REFERENCE` и geometry reference. Coordinates всегда
presentation-only. Analytical `one_way_distance` копируется без изменения и
показывается отдельно. Если physical charge cycle отсутствует, UI сообщает
«в агрегированном простое» и не создаёт battery percentage, charging events или
failure events. Все отчёты сохраняют утверждение
`PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION`.

Capacity-only fixture с `finance: null` полноценно строит четыре робота,
synthetic zone/path, KPI и `NOT_EVALUATED` SLA. Детерминированный golden capture
связан с scenario revision, report ID/digest, seed и simulation time. Это
contract fixture, не export и не изменение persistence; сохранение export
артефактов остаётся C26.

## Артефакты

- `backend/simulation_api.py` — lifecycle state, job registry и auth/CSRF/owner
  router;
- `contracts/simulation-run-state-v1.schema.json` и
  `scripts/build_simulation_2d_contract.py` — strict polling contract и drift
  check;
- `frontend/src/simulationApi.js` — CSRF client, polling, cancel и stale
  generation guard;
- `frontend/src/simulation2dModel.js` — strict bindings, presentation geometry,
  deterministic timeline/frame/capture без business arithmetic;
- `frontend/src/components/Simulation2DReport.jsx` — offline SVG и отчёт C23;
- `frontend/tests/fixtures/simulation-2d.capacity-only.golden.json` — golden
  capture.

## Проверки и совместимость

Targeted backend tests покрывают run/progress/cancel, tenant/project owner,
CSRF dependency, revision/digest binding, request collision и strict unknown
version/extra field rejection. C23/C22 regressions дополнительно покрывают
22/24-hour windows, maximum ≤60-second profile, >10% boundary, SLA
`NOT_EVALUATED/CONDITIONAL`, failure-data absence и capacity-only flow.

Frontend tests покрывают все controls, restart/speed, deterministic frame,
stale response, strict versions/fields/revision, synthetic/provided labels,
immutable analytical distance, no fake charging/failure/SLA and exact golden
capture. Существующие RobCraft same-origin/source, two-phase PREPARED/APPLY,
stale request и ScenarioSpec v1/v2 negotiation tests остаются неизменными.

ScenarioSpec v1, старые runs, C23 DTO/schema/fixtures, immutable registry v1,
catalog/pool membership, economics snapshots, RobCraft и production runtime не
изменены. Rollback аддитивен: удалить C24 router/state schema, 2D client/model,
tests/golden и App bundle branch; C23 service и прежние UI/runtime paths
продолжат работать без migration.

Следующий этап — C25 `robcraft/scenario-v2-reconciliation`: отдельный v2
adapter/report comparison с сохранением существующего same-origin/source и
two-phase protocol. C25 в C24 не начинался.
