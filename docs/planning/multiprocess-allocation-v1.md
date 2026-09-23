# Multiprocess allocation v1

Статус: **IMPLEMENTED**, C18 `economics/multiprocess-allocation-v1`,
2026-09-23.

## Результат

Добавлен pure C18 engine, который связывает выбранную конфигурацию каждого
процесса с immutable digest результата C16/C17 и объединяет их в один
object-level ledger. Контракт фиксирует cohort, model/position identity,
acquisition mode, прямой capital basis и process-direct cashflows. Проекции
обязаны явно исключать object-scoped роли, пульт, technical staff и shared site
costs; эти статьи вводятся ровно один раз на уровне проекта.

Shared site CAPEX распределяется по K17 пропорционально прямому capital без
shared/reserve. При нулевом знаменателе используется равное распределение.
Денежное распределение выполняется в копейках методом largest remainder с
tie-break по stable process ID, поэтому сумма process allocations точно равна
project amount и не зависит от порядка входа.

## Role pools, FOT и combined cashflow

C18 принимает полный C14 labour snapshot с tenant/project/revision/object
bindings и проверяет его semantic digest. Перед расчётом повторно проверяются
conservation equations: allocated + unallocated = role headcount,
released ≤ allocated, released + remaining = headcount, а process totals
совпадают с role и site totals.

Object FOT строится один раз из C14 role ledgers. Fixed overhead остаётся от
полной численности, released staffing следует сохранённой annual ramp, а
additional control operators и technicians учитываются только через единый
site ledger. Для process presentation FOT распределяется отдельно и
консервативно; capacity snapshots и их fleet sizing не пересчитываются и не
зависят от зарплат.

Combined baseline/scenario cashflows состоят из process-direct flows,
единственного object FOT и явно введённых shared non-labour costs. Project NPV
и simple/discounted payback считаются из итогового differential CF, а не из
суммы округлённых process metrics. Trace сохраняет direct→allocation→combined
узлы, provenance, policy/registry/precision versions и replay digests.

## Контракты, проверки и границы

Сгенерированы strict schemas
`multiprocess-allocation-request-v1`/`multiprocess-allocation-result-v1`,
golden fixture с двумя процессами одной роли и отдельный negative fixture.
Targeted tests покрывают exact conservation, shared CAPEX до копейки, нулевой
capital denominator, reorder invariance включая replay digest, single-process
identity, одинаковую site cost для разных моделей, project payback, tenant и
digest isolation, tampered role pools и запрет process projections со shared
статьями. Targeted regressions C14–C17 сохранены.

C18 не добавляет API/DB migration, не меняет frontend, catalog/pool membership,
immutable registry v1, старые runs или production runtime. Rollback аддитивен:
удалить allocation module, service boundary, schemas, fixtures, generator,
tests и этот отчёт. Следующий этап — C19 `engine/ranking-v2`.
