# Palletizing capacity trace v1

Статус: **IMPLEMENTED**, C09, 2026-09-23.

## Результат

Добавлен изолированный pure engine F01/F06/F07 для C03 процесса
`warehouse_palletizing` с scope `FIXED_CELL` и demand строго `pallet/day`.
Engine требует C05 `ELIGIBLE`, C06 `PALLETIZING_THROUGHPUT_V1`, pinned
registry/version bindings и explicit `pick/min` rate. Production API,
frontend, catalog membership, immutable registry v1 и старые runs не менялись.

F06 сохраняет размерности на каждом шаге:

- `H = shifts × hours`, строго `0 < H ≤ 24`;
- exact conversion `pick/min × 60 min/h = pick/h`;
- `boxes/day = picks/h × H × cell_efficiency`;
- `nominal pallets/day = boxes/day / boxes_per_pallet`;
- `effective pallets/day = nominal × availability`;
- `recommended cells = ceil(demand/effective)` без epsilon;
- F07 считает actual fleet capacity, raw load, coverage, display utilization и
  overload от выбранного количества ячеек.

Policy binding использует именно `default.palletizing.boxes-per-pallet = 20`
для выходной паллетизации. Значение 33 относится к receiving и не подменяет
F06 denominator. Cell efficiency `.65` применяется ровно один раз, отдельно
от availability.

## Evidence и отсутствие pool expansion

В текущем C06 audit нет ни одной catalog-executable palletizing model/position.
Golden использует identity `synthetic.palletizing.cell` вне каталога и explicit
assumption provenance для rate 10 pick/min. Такой rate возвращает
`WITH_ASSUMPTIONS`, не объявляется vendor fact и не меняет membership 21/24.
Unknown/unsafe rate и unsupported profile дают `BLOCKED`; K29 default rate не
подставляется автоматически.

## Контракты и trace

В C01 аддитивно добавлены typed units `min/h`, `pick/h`, `box/pallet` и
семантики intermediate quantities. `CELL_RATE` теперь канонически требует
`pick/min`; другой throughput kind не конвертируется автоматически. Отдельная
strict JSON Schema `palletizing-capacity-request-v1` генерируется общим builder.

Trace содержит demand, H, pick rate origin, exact unit conversion, output
boxes/pallet, efficiency, availability, picks/hour, boxes/day,
nominal/effective/fleet pallets/day, exact CEIL и manual selected fleet.
Каждый numerical input имеет unit/provenance, replay byte-stable.

## Golden и проверки

Synthetic golden: demand 2000 pallet/day, 2×11h, 10 pick/min, efficiency .65,
20 box/pallet, availability .70. Получено 600 pick/h, 8580 box/day,
429 nominal pallet/day, 300.3 effective pallet/day и recommendation 7.

Проверены 20 против receiving 33, denominator 0, wrong throughput unit/kind,
unknown/missing rate, manual cells 6/7/8, unsupported profile, resolver
integration, inactive/selected zero, monotonicity, отсутствие transport peak и
finance, отсутствие palletizing members в действующем pool.

Golden: `contracts/fixtures/palletizing-capacity-v1.synthetic.golden.json`.
Rollback аддитивен: удалить C09 engine/schema/tests/fixture; C07/C08 и
production runtime останутся без изменений.

Следующий обязательный этап C10 фиксирует coverage всех 28 process scopes и
маршрутизацию к C07–C09; C10 в рамках C09 не начинался.
