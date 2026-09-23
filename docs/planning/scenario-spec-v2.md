# ScenarioSpec v2

Статус: **IMPLEMENTED**, C22 `contracts/scenario-spec-v2`, 2026-09-23.

## Результат

Добавлен аддитивный strict `scenario-spec-v2`, который строится только из
immutable C11 capacity request/result/trace. Контракт связывает tenant/project,
run и input revision, отдельные model/position IDs, typed demand, явный process
profile, operating windows, batch/exchange semantics, analytical route,
recommended/selected fleet, nominal/effective capacity и trace nodes.

Экономика не обязательна. Capacity-only spec содержит явное `finance: null`;
при наличии C18 builder принимает только `COMPLETE` allocation snapshot с теми
же tenant/project/input revision, process, model, position и acquisition. В
binding входят C18 digest, cohort, metrics и finance version bindings. Никаких
цен, зарплат или финансовой арифметики builder не выводит самостоятельно.

## Воспроизводимость и версии

`revision_id` вычисляется из канонического полного semantic body, включая C11
request/result/trace digests, catalog/projection/registry/process/formula/
constraint/commercial/precision/calculation versions и optional C18 binding.
Модель при чтении повторно проверяет revision: изменение значимой версии или
payload с прежним revision отклоняется. Seed также детерминирован и не зависит
от timestamp/UUID runtime metadata.

Синтетическая геометрия и route имеют обязательный assumption reference и не
могут заменить аналитическую длину C11. Operating windows обязаны сохранить
расчётные operating hours, а transport batch — C11 batch semantics. Cleaner
fixture не содержит payload или transport exchange.

## Совместимость и protocol boundary

ScenarioSpec v1 schema, fixtures, Pydantic model, builder и старые runs не
изменены. Frontend protocol adapter получил явное version negotiation без
implicit downgrade; действующий RobCraft объявляет только `scenario-spec-v1`,
поэтому v2 renderer adapter намеренно остаётся C25. Same-origin проверки,
source-window predicate, двухфазные PREPARED/APPLY и stale request binding не
ослаблены.

## Артефакты и проверки

- `backend/scenario_spec_v2.py` — DTO, invariants и pure builder;
- `contracts/scenario-spec-v2.schema.json` — generated strict JSON Schema;
- `contracts/fixtures/scenario-spec-v2.capacity-only-cleaner.golden.json` —
  golden без finance/payload;
- `scripts/build_scenario_spec_v2_contract.py` — deterministic schema/fixture
  generation и drift check;
- Python unit/negative/version/tenant/v1 compatibility tests;
- JavaScript schema parity и frontend/RobCraft protocol regressions.

Acceptance-прогон: 38 targeted Python tests C22/C11/v1 contracts прошли;
19 Node tests ScenarioSpec v1/v2 и iframe protocol прошли; полный frontend
contract suite — 50 tests, ESLint — без ошибок. Generator `--check` и
`git diff --check` прошли. DB/Docker/full suites не запускались: C22 не меняет
persistence schema, endpoint или runtime activation.

C22 не меняет API/DB persistence, frontend UI, scheduler, simulation,
2D/RobCraft renderer, catalog membership, immutable registry v1 или production
runtime. Rollback аддитивен: удалить v2 module/schema/fixture/tests/generator и
version-negotiation helper; v1 path продолжит работать без data migration.

Следующий этап — C23 `simulation/scheduling-kpi-report-v1`: deterministic
event model, operating calendar, queues/SLA и immutable SimulationReport v1.
Обязательная 2D-визуализация начинается только в C24.
