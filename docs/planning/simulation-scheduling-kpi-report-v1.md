# Simulation scheduling KPI report v1

Статус: **IMPLEMENTED**, C23 `simulation/scheduling-kpi-report-v1`, 2026-09-23.

## Результат

Добавлен отдельный pure backend service `deterministic-queue-v1`, который
принимает только strict `SimulationRequest v1` с вложенным ScenarioSpec v2 и
возвращает immutable-derived `SimulationReport v1` либо typed terminal error.
Production API, persistence, frontend и RobCraft не подключались: endpoint,
progress consumer и обязательная 2D-визуализация остаются C24.

Календарь использует целые микросекунды, фиксированный seed 42, один warm-up
день, один measurement день и один completion-grace день. Arrivals равномерны
в явных operating windows, FIFO/tie-break policy и версии event/arrival model
записаны в отчёте. DAILY и PEAK_STRESS разделены; peak factor обязателен только
для PEAK_STRESS. Лимиты 10 000 jobs/day, 100 robots, 60 секунд и progress batch
1000 являются обязательными полями request, а не скрытыми defaults.

## Семантика KPI и ограничений

Сервис не заменяет C11 capacity formula: nominal/effective fleet capacities,
batch, demand, selected fleet и operating windows читаются из связанного C22
snapshot. Nominal operation time и aggregate nonproductive allowance показаны
раздельно; resource wait не умножается на availability повторно. Отдельного
failure/charging distribution нет: version binding фиксирует
`failure_model_version=not-provided`, failure downtime имеет
`NOT_EVALUATED_NO_INPUT`, а charging остаётся только частью уже рассчитанного
aggregate allowance.

Report содержит scenario revision/digests, time basis, workload, completed
jobs/units на measurement и grace boundaries, queue/wait/turnaround,
busy/productive/nonproductive utilization, explicit resource metrics, SLA,
limitations и calculation trace. Capacity deviation использует явно названный
denominator `EXPECTED_EFFECTIVE_FLEET_CAPACITY`; ровно 10% допустимо, warning
возникает только при превышении. Нулевой expected/observed даёт `N_A`, а
ненулевой observed при нулевом expected — `INPUT_MISMATCH`.

SLA minutes, target и provenance всегда задаются явно. Без SLA результат
`NOT_EVALUATED`; без достаточной resource/geometry модели он `CONDITIONAL`.
Сервис не выводит SLA из capacity и не заявляет инженерную сертификацию:
каждый отчёт маркирован
`PRELIMINARY_SCENARIO_SIMULATION_NOT_CERTIFICATION`.

## Контракты и воспроизводимость

- `backend/calculation/scheduling.py` — strict DTO, deterministic calendar,
  queue/resource dispatcher, KPI/report/error/progress service;
- `contracts/simulation-{request,report,progress,error}-v1.schema.json` —
  generated JSON Schemas с `additionalProperties: false`;
- `contracts/fixtures/simulation-request-v1.capacity-only.golden.json` и
  `simulation-report-v1.capacity-only.golden.json` — capacity-only replay без
  finance payload;
- invalid fixtures фиксируют unknown request version и extra-field rejection;
- `scripts/build_simulation_report_v1_contract.py` — deterministic generation
  и drift check.

Tenant/project обязаны совпадать с ScenarioSpec v2. Report ID, request/spec
digests и self-checking content digest детерминированы; timestamps и UUID не
используются. Значимые C22 calculation/catalog/registry bindings входят через
полный scenario digest, поэтому смена revision меняет report/replay identity.
ScenarioSpec v1, старые runs, immutable registry v1 и catalog/pool membership
не изменены.

## Проверки и границы

Targeted tests покрывают deterministic replay/event policy, аналитический
capacity-only fixture, 22/24 часа, zero expected, overload/censoring, ровно
10% и >10%, SLA 20/30 минут, explicit shared-resource queue, отсутствие
двойного availability factor, missing failure data, progress/cancel/timeout и
предельный профиль 10 000 jobs/day × 100 robots. Также проверены strict
unknown-version/extra-field rejection, tenant isolation, v1 compatibility,
generated schema/fixture drift и C11/C22 regressions.

Acceptance-прогон: 23 targeted Python tests прошли за 3.63 s; maximum-profile
test уложился в policy limit 60 s. Generator `--check` и 7 существующих Node
protocol tests прошли. DB, Docker, полные suites, frontend build и production
runtime не запускались, поскольку C23 не меняет эти слои.

Rollback аддитивен: удалить C23 module, schemas/fixtures, generator и tests;
C22 ScenarioSpec и все прежние runtime paths продолжат работать без migration.

Следующий этап — C24 `visualization/2d-simulation-report`: API/progress/cancel
consumer и обязательная offline 2D-визуализация поверх этого сервиса. C24 в
рамках C23 не начинался.
