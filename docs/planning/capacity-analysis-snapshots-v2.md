# Capacity analysis snapshots v2

Статус: **IMPLEMENTED**, C11, 2026-09-23.

## Результат

Активирован отдельный контракт C01 `POST /api/v2/capacity-analyses` без
обязательной экономики. Endpoint защищён существующими session, CSRF и owner
predicates; `GET /api/v2/capacity-analyses/{run_id}` открывает только snapshot
владельца. `/api/calculate` и старые full-analysis routes не менялись.

Новый `calculation/service.py` принимает один immutable PUBLISHED catalog
snapshot, выбирает `CapacityRuntimeDTO` по точной паре model/position и не читает
legacy `Robot`, цену или economics. C10 router определяет C07/C08/C09 handler;
C05 constraint report и C06 executability относятся к той же input revision и
сохраняются в diagnostics. Недостающий passport/environment evidence остаётся
`NEEDS_VALIDATION` и даёт воспроизводимый blocked result без fallback.

## Persistence и replay

Миграция `0008_capacity_snapshots` добавляет `run_kind` и отдельные trace/version
snapshots с SHA-256. Per-kind constraints сохраняют прежние требования:

- `FULL_ANALYSIS` по-прежнему требует economics version и ScenarioSpec;
- `CAPACITY_ANALYSIS` требует input/result/trace/version bindings и hashes,
  запрещает economics version и ScenarioSpec;
- terminal runs и их input/version snapshot остаются неизменяемыми DB trigger;
- старые строки мигрируются как `FULL_ANALYSIS`, без переписывания payload.

Reopen проверяет result, trace и version checksums, совпадение вложенного trace и
его version bindings. Catalog/registry/process/formula/constraint/policy versions
закреплены в trace; обновление источника требует нового run.

## Проверки и границы

Synthetic golden проверяет C05→C06→C07→trace→snapshot на безопасном transport
DTO без цены. Покрыты deterministic replay, conservative blocked path,
REFERENCE_ONLY, model/position mismatch, OpenAPI schemas, legacy route,
per-kind DB constraints, CSRF, cross-user denial, reopen и terminal immutability.
PostgreSQL integration tests используют только `TEST_DATABASE_URL` disposable DB.

Production catalog activation, slot switch, frontend, economics, labour и
ScenarioSpec v2 не входят в C11. Rollback удаляет additive endpoint/service и
миграцию после удаления capacity-kind runs; legacy full runs сохраняются.

Следующий обязательный этап — C12 `frontend/capacity-results-trace`: он читает
серверные status/units/revision/trace, показывает blockers и selected/recommended
fleet и не выполняет локальную арифметику. C12 в C11 не реализовывался.
