# Full cashflows and reconciliation v1

Статус: **IMPLEMENTED**, C16 `economics/full-cashflows-reconciliation-v1`,
2026-09-23.

## Результат и V2-C

Добавлены strict `FinancialAnalysisRequestV1`/`FinancialResultV1` и pure engine
F23–F31. Вход связывает immutable C14/C15 snapshots по tenant/project/revision,
content digests, labour trace и capacity digest. Старые runs и registry v1 не
изменяются; DB/API route, frontend и production activation отсутствуют.

V2-C закрыт overlay `hackathon-calculation-policy-v1+v2c-c16`:

- ZV2-09 остаётся `REJECTED_WITH_REASON`: replacement основного оборудования
  без cohorts, commissioning, depreciation и tax policy не добавляется;
- ZV2-10 `ADOPTED_IN_POLICY_V2`: C16 использует C15 `CAPEX_cashflow` для t0 и
  `CAPEX_amortizable` для depreciation, reserve второй раз не выводится;
- ZV2-12 остаётся `REJECTED_WITH_REASON` для default VAT 20%: primary идёт по
  gross cash basis, tax supplement помечен simplified non-tax-accounting;
- ZV2-16 `ADOPTED_IN_POLICY_V2`: additional income/prevented loss допускается
  только через explicit `INCLUDED` sourced amount либо traceable `EXCLUDED`;
- ZV2-18 `ADOPTED_IN_POLICY_V2`: публикуются `TCO_purchase_gross` и
  `TCO_purchase_net_of_residual`, а ROI однозначно назван
  `roi_on_capex_cashflow`; неоднозначный profitability-TCO не возвращён.

## Ledger и метрики

- F23 формирует по ролям ежегодные base/remaining direct labour, одинаковый
  fixed overhead, deficit и equipment ledgers с K09 ramp/indexation.
- F24 считает severance во все годы только по положительному приросту released.
- F25 строит полные EBITDA base/scenario; C15 OPEX включается один раз,
  battery replacement остаётся отдельным cash item, savings повторно не
  прибавляется.
- F26 использует `CAPEX_amortizable/5` первые пять лет. Primary tax равен нулю;
  supplement поддерживает `ILLUSTRATIVE_OTHER_INCOME` и FIFO losses на 10 лет с
  50% deduction cap для `ILLUSTRATIVE_NO_OTHER_INCOME`.
- F27 хранит t0, primary и supplement cash flows; depreciation не становится
  вторым cash out, residual появляется только в terminal year.
- F28 считает `NPV_scenario - NPV_base`; F29 — первое simple/discounted crossing
  с интерполяцией и nullable `NOT_REACHED`; CAPEX=0 следует K13.
- F30 публикует cumulative effect и два TCO; F31 — ROI на CAPEX cashflow и net
  benefit after investment.

Каждый annual total имеет formula trace, units и upstream refs. Replay содержит
canonical input, C14/C15 и capacity digests. Money сериализуется с двумя знаками
HALF_EVEN; внутренний Decimal не использует float.

## Reconciliation и проверки

Результат содержит ровно `R13-01..R13-49`: применимые правила получают PASS,
K09/K12/K13/V2-C отклонения — POLICY_EXCEPTION, а ranking/RaaS/UI/data rules вне
C16 — NOT_APPLICABLE с scope ref. `INCOMPLETE` upstream cost не превращается в
ноль и блокирует метрики.

Golden warehouse покрывает full C14/C15 bindings, equipment withdrawal,
deficit, ramp, severance, depreciation, residual и 49 findings. Unit/negative
tests покрывают знак −80−(−100)=+20, identical flows, reserve, overhead,
tax modes/loss carry, late/non-monotonic/no payback, CAPEX=0, missing finance,
additional income, gross/net TCO, tenant/digest isolation и strict schemas.

C16 не реализует RaaS, allocation, ranking, sensitivity или UI. Следующий этап —
C17 `economics/raas-cashflows-v1`.
