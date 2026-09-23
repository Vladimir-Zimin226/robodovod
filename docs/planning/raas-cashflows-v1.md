# RaaS cashflows v1

Статус: **IMPLEMENTED**, C17 `economics/raas-cashflows-v1`, 2026-09-23.

## Результат и policy bindings

Добавлены strict `RaasAnalysisRequestV1`/`RaasFinancialResultV1` и pure F32
engine. Он принимает C13 RaaS terms и immutable C16 comparator request/result,
проверяет tenant/project/revision, semantic digests, C16 replay и сохраняет
capacity digest. Acquisition mode остаётся независим от uncertainty и
поддерживает `PESSIMISTIC/BASE/OPTIMISTIC × ALL_FLEET/PHASED`.

Применение V2-B/V2-C зафиксировано overlay
`hackathon-calculation-policy-v1+v2bc-c17` без изменения policy/registry v1:

- **ZV2-11 — ADOPTED_IN_POLICY_V2:** infrastructure учитывается у клиента
  только при explicit `CUSTOMER`; `VENDOR` даёт ноль, а `UNKNOWN/SHARED/
  INTEGRATOR` остаётся `INCOMPLETE`, без fallback allocation;
- **ZV2-15 — ADOPTED_IN_POLICY_V2:** `PHASED` масштабирует только RaaS payment
  по utilization ramp, `ALL_FLEET` платит за весь парк; CAPEX не масштабируется;
- **ZV2-18 — ADOPTED_IN_POLICY_V2:** RaaS публикует `tco_raas` и
  `roi_on_raas_tco`; residual и owned robot/battery replacement равны нулю.

Gross cash basis K20 сохраняется, VAT rate не угадывается. Тариф `.02/month`
приходит из explicit C13 scenario terms, base price имеет отдельный provenance.
Это model assumption, не vendor offer. Non-zero buyout и незакрытый contract
horizon не интерпретируются молча и делают finance `INCOMPLETE`.

## F32 ledger

- robot, charger, per-robot integration, maintenance, software и battery lines
  зануляются только при явной ответственности `VENDOR`; иначе line и итог
  `INCOMPLETE`;
- infrastructure остаётся единственным возможным RaaS CAPEX: customer gross
  содержит соответствующую долю reserve, amortizable base — без reserve;
- customer OPEX содержит energy, connectivity и additional control operators;
  service/technicians/battery/residual не переносятся из PURCHASE;
- payment — отдельная annual line, входит ровно один раз в EBITDA, cashflow и
  TCO, не получает inflation или hardware multiplier;
- depreciation применяется только к customer infrastructure без reserve;
- primary pretax и optional illustrative tax supplement следуют K12/C16;
- NPV, simple/discounted payback, cumulative effect, TCO и ROI следуют K13.

Каждая zero/payment line имеет F32 trace с reason/ownership/source refs. Missing
terms, tariff base, responsibility или customer OPEX не превращаются в ноль.
Старые C13–C16 runs не переписываются; DB/API route, frontend и production
activation не меняются.

## Проверки и границы

Golden warehouse фиксирует customer infrastructure, all-fleet payment, full
base/scenario flows и replay. Tests покрывают 3 uncertainties × 2 payment modes,
payment-once/TCO, все zeroing lines, warranty irrelevance, customer/vendor/
unknown infrastructure, unknown maintenance, missing terms/tariff, zero/nonzero
buyout, tenant/revision/digest isolation и strict schemas.

C17 не реализует multiprocess allocation, ranking, sensitivity или UI.
Следующий этап — C18 `economics/multiprocess-allocation-v1`.
