# Formula executability audit v3

Статус: **IMPLEMENTED**, C06, 2026-09-22.

## Результат

Добавлен отдельный versioned resolver dependency closure для профилей
`TRANSPORT_CYCLE_V1`, `DELIVERY_CYCLE_V1`, `CLEANING_AREA_V1` и
`PALLETIZING_THROUGHPUT_V1`. Он описывает входы F01–F07 как один из трёх
разрешённых origins: evidence-gated catalog fact, normalized scenario input
или immutable policy parameter C02. Dependency graph проверяется в обе стороны:
каждая формула ссылается только на уже известные inputs/outputs, а каждый
объявленный input действительно потребляется указанной формулой.

Catalog label и run executability разделены. `CATALOG_EXECUTABLE` означает,
что model-specific facts и policy bindings безопасно разрешены, но не означает
готовность конкретного расчёта. Run получает `EXECUTABLE` только при полном
C03-compatible scenario input, допустимом C05 report и корректных units/domains.
Missing input, unknown/ambiguous identity, unsafe evidence, wrong unit/domain и
unsupported profile имеют локальные blocker codes; значение не подменяется
нулём или vendor default.

Legacy v2 assumptions `45 s` и `1 unit/trip` не стали скрытыми входами v3:
exchange total и units per trip явно требуются от run. Registry values имеют
отдельную provenance и не называются vendor facts. Resolver не исполняет
формулы, не требует `Robot`, prices или economics и не переключает runtime.

## Full-catalog audit и pool diff

Golden audit детерминированно покрывает 187 models / 223 positions:

| Статус | Models | Positions |
|---|---:|---:|
| `CATALOG_EXECUTABLE` | 21 | 24 |
| `MISSING_SAFE_FACT` | 19 | 19 |
| `INVALID_FACT` | 0 | 0 |
| `UNKNOWN_IDENTITY` | 0 | 0 |
| `UNSUPPORTED_PROFILE` | 143 | 176 |
| `NOT_EQUIPMENT` | 4 | 4 |

Exact identity diff относительно readiness v2 содержит 21/24 в baseline и
candidate sets, additions/removals пусты. Membership не менялся. Все candidate
models относятся к BRS; БАС отсутствуют.

В ходе unit/domain проверки пять v2-ready карточек потребовали явной безопасной
нормализации. V3 фиксирует только точные C01 conversions `km/h → m/s`, `t → kg`,
эквивалент записи `m²/h → m2/h` и консервативный минимум подтверждённого
диапазона производительности. Неподдерживаемые единицы или нечисловые диапазоны
остаются `INVALID_FACT`; усреднение и угадывание запрещены.

## Артефакты

- `backend/calculation/executability.py` — strict profiles, catalog/run DTO и resolver;
- `backend/catalog_repository.py` — cost-free evidence projection без legacy `Robot`;
- `data/calculation/formula-executability-profiles-v3.json` — dependency graph;
- `contracts/*formula-executability*v3.schema.json` — profiles, audit, diff и run schemas;
- `data/review/catalog-formula-executability-audit-v3.json` — golden full-audit;
- `data/review/catalog-formula-executability-pool-diff-v3.json` — exact identity diff;
- `scripts/build_catalog_formula_executability_v3.py` — deterministic build/`--check`.

## Проверка и границы

Tests покрывают unsafe evidence statuses, wrong unit/domain, exact conversions,
unknown identity/profile, missing policy/scenario input, duplicate/unknown input,
`H = shifts × hours ≤ 24` без clamp, C05 eligibility, deterministic exact sets,
no BAS и repository DTO без cost fields. Existing readiness v2, capacity runtime,
repository, C02 registry, C03 intake и C05 constraints остаются совместимы.

Production API, frontend, database activation, external research, новые formula
implementations, catalog membership и старые audits/runs не изменены. Rollback
аддитивен: удалить v3 artifacts/projection, сохранив immutable v1/v2 contracts.

Следующий этап C07 реализует pure F01–F04/F07 transport/delivery capacity и
CalculationTrace, используя C06 resolver result как prerequisite. Cleaning и
palletizing formulas остаются отдельными обязательными C08/C09.
