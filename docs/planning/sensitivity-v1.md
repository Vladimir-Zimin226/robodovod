# Economics sensitivity v1

Статус: **IMPLEMENTED**, C20 `economics/sensitivity-v1`, 2026-09-23.

## Результат

Добавлен deterministic sensitivity orchestrator для шести обязательных
tornado-вариантов: equipment price, operation volume и role salary, каждый
ровно −10%/+10%. Override всегда явный USER input с base/variant value, unit,
scope и provenance. Baseline связан с immutable C18 result/digest, parent run,
tenant/project/object и выбранными C19 candidate/configuration/digest.

Sensitivity не содержит второй реализации финансовых формул. Baseline и каждый
исполняемый variant повторно проходят canonical
`calculate_multiprocess_allocation`; upstream-derived C18 request хранится в
strict bundle. Результат публикует delta project CAPEX, project NPV,
simple/discounted payback и digest нового allocation result/trace. Если
upstream variant заблокирован, C20 не создаёт числовой financial result.

## Capacity, labour и дискретные шаги

Для каждого процесса сохраняются version/digest capacity snapshot, demand и
selected fleet. Price и salary overrides обязаны иметь byte-equivalent capacity
bindings, поэтому экономика и зарплата не могут менять sizing. Volume override
может получить новый capacity digest и fleet count только для своего process;
остальные snapshots остаются неизменными.

Trace связывает baseline → override → список повторно вызванных engines → C18
result → delta. Для каждого варианта явно записываются
`discrete-fleet-step`/`no-discrete-fleet-step` и
`headcount-step`/`no-headcount-step`. Salary остаётся USER provenance и
сверяется с monthly gross целевой C14 role. Shared costs, discount,
uncertainty, selected configuration identities и frozen cohort нельзя менять
через sensitivity override.

## Контракты, проверки и границы

Сгенерированы strict schemas `sensitivity-request-v1`/`sensitivity-result-v1`,
golden bundle со всеми шестью вариантами и negative fixture для неверного
процента, изменения capacity через price и tampered baseline digest. Tests
покрывают exact ±10%, canonical engine reuse, deterministic reorder, immutable
baseline replay, tenant/cohort isolation, blocked variant, price/salary
capacity independence, volume fleet threshold, explainable deltas и запрет
клиентского NPV.

C20 не меняет frontend, DB/API persistence, catalog/pool membership, immutable
registry v1, старые runs или production runtime. Monte Carlo и вероятностные
распределения вне scope. Rollback аддитивен: удалить sensitivity module,
service boundary, schemas, fixtures, generator, tests и этот отчёт. Следующий
этап — C21 `frontend/commercial-scenarios-v2`.
