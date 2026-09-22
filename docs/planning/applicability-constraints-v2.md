# Applicability constraints v2

Статус: **IMPLEMENTED**, C05, 2026-09-22.

## Результат

Добавлен отдельный детерминированный constraint service, который формирует
один `constraint-report-v2` для readiness и будущего execution path. Каждый
check содержит стабильный ID и версию правила, applicability, severity,
`PASS/FAIL/UNKNOWN/ASSUMED/N_A`, reason/localization codes, scope процесса,
обе стороны сравнения, единицы и source/decision refs. Только применимый
`CRITICAL FAIL` блокирует кандидата; `UNKNOWN` и `ASSUMED` требуют валидации.

Правила находятся в `data/calculation/constraint-rules-v2.json`. Их текущий
состав является версионированными данными, а не нормативным требованием иметь
фиксированное количество проверок. В migration notes явно исключён legacy
hard reject `autonomy × 0.8`: до C23 маршрут и зарядка не получают скрытой
формулы. Legacy `economics.check_constraints`, production API и старые runs
не изменены; `readiness.py` лишь предоставляет аддитивный delegate v2.

## Scope и evidence gates

Реализованы именованные R03/R08/K15 проверки process/object/cargo scope,
payload, aisle, lift height и `ceiling ≥ lift + 1 m`, фактически пересекаемых
этажей, temperature, noise с zone/time scope, operational airside/apron
permission, restricted-zone/access protocols, clinic sanitization, Class B
containment, cleanable/disinfectable material, floor covering/flatness/slope,
outdoor, availability и technical passport. Значение candidate fact участвует
в результате только при `MATCHING_SAFE`; конфликт, неоднозначная модель,
отсутствие evidence или самого факта дают `UNKNOWN`, а не PASS.

Требование с provenance `ASSUMPTION` не превращается в окончательный PASS:
даже при достаточной характеристике check получает `ASSUMED`, а report —
`NEEDS_VALIDATION`. Clinic checks применяются только к реально требующим их
процессам; Class B означает containment/cleaning, не универсальную
взрывозащиту. Floor/lift проверяется только для этажей маршрута. Airside —
операционное разрешение, без выдуманного EASA/ICAO сертификата.

Life versus horizon, budget versus CAPEX, charging power и сохранённый
reference-v2 density threshold `30 m²/robot` являются warnings без влияния на
eligibility. Integration compatibility остаётся advisory до V2-D и не стала
скрытым hard fail. Ranking, score, deployment certification, formula execution,
catalog membership и frontend находятся вне C05.

## Контракты и воспроизводимость

- `backend/calculation/constraints.py` — strict DTO, loader и pure evaluator;
- `data/calculation/constraint-rules-v2.json` — versioned rules и migration notes;
- `contracts/constraint-*-v2.schema.json` — request, report и rules schemas;
- `contracts/fixtures/constraint-report-v2.*.json` — warehouse, airport и
  clinic golden request/report snapshots;
- `scripts/build_calculation_constraint_contracts.py` — детерминированная
  генерация и `--check` против drift.

Golden fixtures имеют безопасные положительные evidence bindings. Отрицательные
и boundary cases покрыты unit truth tables: unknown evidence, airside/apron,
clinic waste, route floors/lift, ceiling clearance, temperature/noise scope,
floor constraints, passport, assumption provenance и warning isolation.

## Проверка и rollback

Целевые C05, legacy readiness и затронутые C01/C03 contract/intake tests
проверяют отсутствие расхождения readiness/execution нового path и отсутствие
регрессии v1. Rollback аддитивен: удалить C05 delegate/artifacts, не меняя
legacy runtime, immutable registry v1, старые runs, pool membership или API.

Следующий этап C06 использует report/rule identities и evidence semantics для
`catalog/formula-executability-audit-v3`; он отдельно проверит dependency
closure формул по каждому profile и не должен смешивать catalog readiness с
исполняемостью конкретного run.
