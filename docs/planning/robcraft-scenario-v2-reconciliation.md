# RobCraft ScenarioSpec v2 reconciliation

Статус: **IMPLEMENTED**, C25 `robcraft/scenario-v2-reconciliation`, 2026-09-23.

## Результат

RobCraft теперь принимает strict ScenarioSpec v1 и v2 без implicit downgrade.
V2 adapter использует process/task/fleet/operating-window bindings C22,
сохраняет immutable finance snapshot и analytical route, а частоту visual tasks
вычисляет по явно указанным operating windows. Прежний безусловный делитель
24 часа для v2 удалён; v1 продолжает работать как исторический контракт.

Процедурные coordinates, speed и payload в v2 имеют только conceptual renderer
смысл. `PROVIDED`, `SYNTHETIC` и `UNKNOWN` geometry сохраняются как source
labels; opaque geometry reference не подменяет реальные coordinates, а
synthetic scene/ScenePatch не меняет `one_way_distance` или finance snapshot.

## Отчёт и сравнение

RobCraft возвращает отдельный `robcraft-renderer-report-v1` со статусом
`LOCAL_VISUAL_OBSERVATION_ONLY`. Он связан с scenario revision/spec seed,
опциональными C23 report ID/digest/scheduler seed, renderer/event-profile
versions и simulation time. Moving utilization отделён от productive
utilization; последний имеет `NOT_EVALUATED_LOCAL_TIME_STEP`. Local energy
остаётся `ARBITRARY_RENDERER_UNIT` и явно не сопоставима с RUB или kWh.
Visual faults и charging не считаются аналитической моделью; SLA берётся только
из C23 и не получает локальный fake PASS. Engineering claim ограничен
`CONCEPTUAL_VISUALIZATION_NOT_CERTIFICATION`.

Backend `compare_robcraft_report` — чистый report adapter без новых capacity,
finance или SLA formulas. Он сравнивает renderer throughput с C23 observed
capacity только при совпадении revision/report digest/seed, unit, operating
windows, warm-up и measurement days. Live window возвращает `NOT_COMPARABLE`.
При сопоставимой basis warning возникает строго при отклонении больше 10%; 10%
остаётся `CONSISTENT`, 10.01% — `DEVIATION`. Изменённая geometry архивируется
со статусом `MODIFIED`, но `economics_status` остаётся `UNCHANGED`.

## Secure embedding protocol

Сохранены same-origin и exact `event.source` checks, двухфазный
`LOAD_SCENARIO` → `PREPARED` → `APPLY_REVISION`, request/revision binding и
strict envelope. Capabilities теперь явно объявляют ScenarioSpec v2,
SimulationReport v1 binding и renderer report v1. Generation guard не даёт
медленному старому LOAD заменить более новый PREPARED; stale APPLY отклоняется.
Frontend дополнительно проверяет schema, revision и authoritative report digest
перед показом локальной телеметрии.

C24 2D consumer по-прежнему показывает только authoritative C23 KPI. В его
capacity-only flow добавлена связанная RobCraft-сцена; браузер не выполняет
финансовую арифметику и не меняет economics snapshot. Tenant/CSRF lifecycle API
C24, C23 contracts, registry/catalog membership, old runs и production runtime
не изменены.

## Артефакты и проверки

- `backend/calculation/robcraft_reconciliation.py` — strict renderer report и
  same-basis comparison;
- `contracts/robcraft-renderer-report-v1.schema.json` и
  `contracts/robcraft-kpi-comparison-v1.schema.json` — versioned contracts;
- geometry-modified renderer/comparison golden fixtures и reproducible builder;
- RobCraft v2 adapter, renderer report builder и protected embedding bridge;
- frontend report parser/binding и честная visual-only presentation.

Targeted Python tests покрывают 10%/10.01%, live-window incompatibility, stale
digest, extra fields, geometry/economics status и schema drift. JS tests
покрывают v1/v2 parsing, short shift, capacity-only flow, analytical route
immutability, report binding, malicious origin/source, stale LOAD/PREPARED/
APPLY и ScenePatch regressions. Frontend contract tests запрещают fake SLA и
finance fields. Frontend lint и production build проходят.

Rollback аддитивен: удалить C25 contracts/fixtures/builder, comparison adapter,
v2 branch адаптера и новый report message. ScenarioSpec v1, C23/C24 и старые
runs продолжат работать без migration.

Следующий этап — C26 `report/calculation-evidence-exports`. Exports, catalog
rollout, economics migration и production deployment в C25 не выполнялись.
