# Cleaning capacity trace v1

Статус: **IMPLEMENTED**, C08, 2026-09-23.

## Результат

Добавлен изолированный pure engine F01/F05/F07 для C03 процессов
`CLEANING_AREA`. Вход строго привязан к `NormalizedProcess`, C05
`ELIGIBLE`, C06 `CLEANING_AREA_V1`, immutable registry/version bindings и
evidence-gated cleaning rate. Production API, frontend, catalog membership,
старые runs и immutable registry v1 не менялись.

F05 вычисляется без транспортных peak/payload/batch понятий:

- `H = shifts × hours`, строго `0 < H ≤ 24`, без clamp;
- `required m2/day = area m2 × frequency 1/day`;
- `nominal m2/day = safe rate m2/h × H`;
- `effective m2/day = nominal × availability`;
- `recommended N = ceil(required/effective)` без epsilon;
- F07 считает fleet capacity, raw load, clamped display utilization,
  coverage и overload от фактически выбранного N.

Area source versioned и взаимоисключающий: `DIRECT` либо
`SHARE_OF_TOTAL`. Второй режим сохраняет total area и share отдельными typed
inputs и трассирует derived area. Он не является скрытым default. Frequency
обязательна для active run; missing/zero/negative area/frequency блокируют
формулу. Inactive block возвращает `NOT_APPLICABLE`; selected fleet 0 следует
zero policy C01.

## Контракты и trace

В C01 аддитивно добавлены единица `1/day` и семантики cleaning/total area и
area share. Старые unit/version literals сохранены. Отдельная strict JSON
Schema `cleaning-capacity-request-v1` генерируется общим contract builder.

Trace использует общий runtime C07 и содержит area source, frequency, safe
rate, H, availability, daily required/nominal/effective/fleet capacity,
exact CEIL event, C05 evaluations и provenance каждого numerical input.
C06 snapshot повторно сверяется по area, frequency, schedule и selected fleet;
C03 demand обязан точно равняться `area × frequency` в `m2/day`.

## Golden и проверки

Airport golden фиксирует R05 derivation `85000 × 0.6 = 51000 m2`. При
frequency 1/day, H=24, safe rate 1000 m2/h и availability .70 получаются
nominal 24000 m2/day, effective 16800 m2/day и recommendation 4.

Проверены manual fleet 3/4/5, area 0/negative, frequency 0/missing, H=24,
exact ceil, inactive и selected zero, area/rate/availability monotonicity,
unsafe fact, отсутствие peak/transport/pallet/finance/salary semantics и
byte-stable replay. Integration исполняет все шесть C06-ready cleaning
position DTO: РУБИ-С-03, MARK 2 SE, АК-SC80, Клинботикс 400 PRO,
Клинботикс 600 и БРО 3.0 — без cost/autonomy полей.

Golden: `contracts/fixtures/cleaning-capacity-v1.airport.golden.json`.
Rollback аддитивен: удалить C08 engine/schema/tests/fixture; C07 transport и
production runtime останутся без изменений.

Следующий обязательный этап C09 реализует F06/F07 palletizing с явными
picks/min, boxes/pallet и efficiency; C09 в рамках C08 не начинался.
