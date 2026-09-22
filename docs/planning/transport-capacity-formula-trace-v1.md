# Transport capacity formula trace v1

Статус: **IMPLEMENTED**, C07, 2026-09-23.

## Результат

Добавлен изолированный pure engine F01–F04/F07 для `TRANSPORT_CYCLE` и
`DELIVERY_CYCLE`. Расчёт использует C03 `NormalizedProcess`, только
`EXECUTABLE` dependency closure C06 и `ELIGIBLE` report C05. Production API,
frontend, каталог, pool membership и старые runs не менялись.

Формулы исполняются с Decimal context 28 / HALF_EVEN без промежуточного
display rounding:

- F01: `H = shifts × hours`, строго `0 < H ≤ 24`, без clamp;
- F02: `cycle = 2L/v + exchange`, где total учитывается один раз, а split —
  как `load + unload`;
- F03: `trips/h = 3600/cycle`, nominal capacity — trips × typed batch;
- F04: `required = daily/H × intraday_peak × (1 + reserve)`, effective
  capacity — nominal × availability, recommendation — exact `ceil`;
- F07: fleet capacity строится от выбранного N, coverage и display utilization
  ограничиваются единицей, raw load ratio и overload сохраняются отдельно.

K02 разрешает USER operating speed только в `(0, safe max]`; при отсутствии
USER-ввода safe max используется как явно трассируемый optimistic proxy. K03
для BOX применяет exact `floor(payload/item_mass)` и минимум известных
handling/passport/geometry limits. USER handling override выше mass limit
блокируется; отсутствующий geometry limit отмечается warning и не выдумывается.
Для остальных quantity kinds batch равен явному физическому значению либо 1.
K04 не содержит legacy target utilization `.90`.

## Trace и воспроизводимость

`CalculationTrace` содержит version bindings, typed numerical inputs с unit и
provenance, F01/F02/F03/F04/F07 DAG, cycle/trips/nominal/effective/required/fleet
intermediates, assumption use, C05 evaluations и отдельные FLOOR/CEIL events.
Registry и constraint v2 bindings добавлены в C01 аддитивно; прежние literal
версии сохранены для чтения старых fixtures/runs. Canonical input и trace
digests детерминированы, повторный расчёт byte-stable.

C06 scenario snapshot повторно сверяется с нормализованными demand, exchange,
distance, schedule, batch и selected fleet. Unsafe/ambiguous/missing facts не
попадают в формулу. Нулевой selected fleet возвращает capacity/coverage 0,
null utilization и overload; inactive block — `NOT_APPLICABLE`.

## Проверки и fixtures

Golden synthetic transport закрепляет `L=120 m`, `v=1 m/s`, exchange `90 s`,
`H=22 h`, demand `2000/day`, availability `.70`, peak `1.25`, reserve `.20`:
cycle `330 s`, nominal `120/11`, required `1500/11`, recommendation `18`.
Проверены manual N=17/18/19, total 90 против split 45+45, delivery profile,
BOX floor и excessive override, exact ceil boundary, H=0/H>24, v=0/v>safe,
demand monotonicity, unsafe C06 facts и отсутствие скрытой `.90`.

Golden: `contracts/fixtures/transport-capacity-v1.golden.json`.
Rollback аддитивен: удалить C07 package/tests/fixture и новые trace enum values;
production route при этом не меняется.

Следующий обязательный этап C08 переиспользует quantities/trace подход для
cleaning F05/F07; transport engine в C08 не расширяется.
