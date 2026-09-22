# Purchase cost ledger v1

Статус: **IMPLEMENTED**, C15 `economics/purchase-cost-ledger-v1`, 2026-09-23.

## Результат и V2-B

Добавлен pure purchase engine F16–F22 и versioned service boundary. Он читает
строгий C13 `ProcurementReportV1`, immutable capacity/labour digests и explicit
technical inputs; C07–C14 не пересчитываются. Результат разделяет
`CAPEX_gross`, `CAPEX_amortizable` и `CAPEX_cashflow`, хранит equipment/reserve
bases, годовые operating lines, battery events и terminal residual.

V2-B завершён overlay `hackathon-calculation-policy-v1+v2b-c15`. Blanket
battery-in-price по-прежнему запрещён: initial battery требует explicit
`INCLUDED_IN_ROBOT_PRICE` provenance либо отдельную цену. Упрощённая замена
основного оборудования без cohorts отклонена; C15 исполняет только K10 battery
schedule. ZV2-10 и разделение purchased deployment=1 от utilization ramp
приняты. Registry v1, commercial policy v1 и старые runs не изменены.

## Ledger и формулы

- F16: robots, exact charger `ceil`, per-robot integration, fixed
  infrastructure и explicit initial battery; hardware multiplier применяется
  только к заданным policy lines.
- F17: FIXED_TOTAL/PER_ROBOT/PERCENT_BASE optionals, included/excluded lines и
  reserve по resolved capital subtotal без двойного счёта.
- F18: insurance/consumables/repair от equipment CAPEX, не от infrastructure,
  reserve или повторно от fleet.
- F19: warranty-gated service, software, communication и C14 control/technical
  labour; каждая строка получает utilization ramp/index ровно один раз.
- F20: взаимоисключающие power W→kW и battery/autonomy energy paths, затем
  tariff, charging efficiency, ramp и energy index.
- F21: cumulative battery cycles с ramp в wear, повторные strict crossing
  events и replacement cost без второго ramp.
- F22: AMR/forklift/shuttle 10/.6, fixed-cell/manipulator 8/.4 либо explicit
  override; unknown class получает conservative residual 0.

Unknown price, charger ratio, warranty, energy path, battery lifecycle или C14
salary не трактуются как ноль: соответствующие строки и totals становятся
`INCOMPLETE`. Zero/excluded и included-in-service имеют отдельные semantics.
Fleet=0 остаётся исполнимым контрсценарием.

## Контракты, trace и проверки

Strict request/result schemas связывают tenant/project/revision, C13 report,
C14 labour digest, capacity digest, sources, ownership, units и policy/registry
versions. Trace содержит F16–F22 nodes, CEIL, line bases и source refs; replay
проверяет canonical input и неизменные upstream digests. Engine не пишет БД,
не меняет owner predicates, frontend, catalog membership или production HTTP
activation.

Golden generator `scripts/build_purchase_cost_contracts.py` фиксирует synthetic
21-robot purchase ledger. Tests покрывают charger ceil, reserve/optionals,
included-line deduplication, repair base, warranty 0/3, technicians 20/21,
W→kW, missing inputs, battery horizon/events, residual 30/18/15%, fleet=0,
separate initial battery, exact sums, schemas и byte-stable replay.

C15 не считает cashflow, tax, depreciation, NPV, ROI, payback, TCO или RaaS.
Следующий этап — C16 `economics/full-cashflows-reconciliation-v1`.
