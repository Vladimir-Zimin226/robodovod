# Process profile coverage v1

Статус: **IMPLEMENTED**, C10, 2026-09-23.

## Результат

Добавлен immutable process-profile catalog v1 с ровно 28 строками K19 и
микроэтапами C10.01–C10.28. Каждая строка фиксирует object/process identity,
scope, roles, допустимые quantity kinds, `has_fot_savings`, requirements,
checks, стабильные error codes, UI metadata и ссылки на policy/source.
Каталог проверяется против полного `ProcessCode` enum и C03 projection.

Router направляет только принятые формульные scopes в C07 transport/delivery,
C08 cleaning или C09 palletizing. REFERENCE_ONLY возвращает discovery inputs и
объяснимую причину отсутствия физического профиля; CONSTRAINT_ONLY выполняет
только применимые checks и не создаёт fleet. Digital `clinic_results` и
inactive процессы получают явный NOT_APPLICABLE. Весь warehouse flow из шести
блоков покрыт и не подменяет storage/picking/inventory транспортной формулой.

## USER_CYCLE и размерности

Для REFERENCE_ONLY предусмотрен отдельный opt-in USER_CYCLE. Он требует
явные `cycle_time` и `units_per_cycle` только с USER/FILE provenance, поэтому
generic cycle не становится vendor/SKU fact. Расчёт сохраняет exact Decimal:

- `H = shifts × hours`, с общей проверкой `(0, 24]` без clamp;
- `q = 3600 × units_per_cycle / cycle_seconds`;
- `effective = q × availability`;
- `N = ceil((demand/H) / effective)`;
- actual selected fleet определяет coverage, utilization и overload.

Batch helper считает jobs через exact CEIL. Разные quantity kinds нельзя
смешивать без явного положительного conversion factor; нулевой denominator
отклоняется. Portions, deliveries, kg, samples, sets, bins, carts, pallets и
другие demand kinds остаются отдельными типами C03.

## Контракты, данные и границы

Сгенерированы strict schemas process catalog, route decision, USER_CYCLE input
и result. Coverage manifest закрепляет 28 строк и неизменный pool 21 models / 24
positions. Новых equipment facts, BAS, catalog membership, commercial данных,
finance/labour formulas, frontend arithmetic и production activation нет.
Registry v1 и старые runs не изменены; reference v2 остаётся deferred overlay.

Проверены exact rows/enums/scopes/roles/quantity kinds, все dispositions,
no-role safety profile, applicable clinic constraints, physical/digital split,
inactive semantics, unsupported reasons, warehouse full flow, UI metadata,
batch conversion, negative provenance/profile cases и byte-stable USER_CYCLE
golden. Synthetic golden: demand 1000/day, H=20h, cycle 120s, 2 units/cycle,
availability .8 → 60 nominal units/h, 48 effective units/h, N=2.

Rollback аддитивен: удалить C10 catalog/router/USER_CYCLE schemas, generated
catalog/coverage data, tests и этот отчёт. C03 и C07–C09 останутся рабочими.

Следующий обязательный этап — C11 `api/capacity-analysis-snapshots-v2`:
независимый versioned endpoint, immutable input/output snapshots и trace replay
для C05–C10. C11 в рамках C10 не реализовывался.
