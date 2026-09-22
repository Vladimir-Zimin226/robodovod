# Delta-register поставки Жени `reference v2`

Статус: **REVIEWED / DEFERRED OVERLAY**, 2026-09-22.

Этот документ сохраняет решения из новой поставки Жени, но не заменяет
[calculation policy v1](calculation-policy-decisions-v1.md). K01–K29 и Q01–Q12
остаются исполнимой основой текущего плана. Новая поставка используется как
review backlog: совместимые уточнения можно принять отдельным versioned
решением, конфликтующие — только через будущую policy v2. Она не блокирует C03.

## 1. Идентичность и масштаб поставки

Корень: `Разобрать/Версии проекта от Жени/Референсы/reference v2/`.
Все 14 файлов механически сопоставлены с прежним `reference/`; содержательные
дельты и изменённые разделы проверены. Суммарный net рост — 4416 строк.
Наибольшие изменения: R02 +71%, R03 +83%, R04 примерно ×2,
R07 примерно ×2, R10 +34%, R11 +57%, R13 примерно ×2.5. R00 идентичен прежней
версии; R05, R09 и R12 почти не изменились.

| ID | SHA-256 `reference v2` |
|---|---|
| R00 | `bbf66a169149e39235a1cd38c4534fc2461c1accdd3ad1d31fddd02717556cb0` |
| R01 | `240f0b71811a48625268f7fb29a469f87c7fc95d4918832ace8cf48370c35c84` |
| R02 | `64eeb1214557190177b7d6cb44833eb86e10acd8b81a2bcc0ec31ff9d37109c8` |
| R03 | `7f506fa35336bb642a3959273eb6f5b1d7e85a6d4dc7b9c161683b53720b4f58` |
| R04 | `5f793bc792683e2b8116acb918906406362366b8f2526e77e8eb0bc1af1b2226` |
| R05 | `5e3c4a843007dabba72b4a2460bc10d971c5dd2e4fbff58b994b9bebeaae8110` |
| R06 | `1f851d8712cb500b1c5f35fdedddb74e11d116257451a2ed5ea67f1e9670cc8a` |
| R07 | `f3d75c5271c715849516dc4f1bcd3ea52ef012aa057ddc97a763b9ced4aff5c5` |
| R08 | `26abdcf35ef1ddd2c6826a60f8a8a85678ef6bf53f4cc980c4f476dc59992f54` |
| R09 | `a476dc7d27ff7d94c1c2bef28465008d1baf18ef8a1986ce7e03a0fecaa7b8e4` |
| R10 | `5375f22b38e3aa9b9561c6bd9ca08941fcc31032ad0a161f5926be2f193784af` |
| R11 | `01edcf2aaca9ab060db91b123378204fdfffc2b524866371969f9d9de5a8aff8a` |
| R12 | `fc011fc187207c08f6d087e8384486b540e2b3b76cc100ccf815855e7b104095` |
| R13 | `4a6102ffc1b88ac527fbb80a64954ce1976527ab872511c0955d36c8f24d3944` |

Файлы по-прежнему называют себя версией 3.2 от 2026-09-18, хотя содержимое
существенно новее. Поэтому путь и hash обязательны; одного version label
недостаточно для provenance.

## 2. Правило применения

Приоритет не меняется: официальное ТЗ и дополнения → policy v1 → совместимые
уточнения `reference v2` → прежний reference → legacy code. Нельзя:

- пересчитывать старые runs новым текстом;
- менять immutable registry v1 или его source hashes;
- превращать неподтверждённые нормы и vendor facts в hard fail/default;
- молча заменять K-решение новым правилом Жени;
- расширять runtime scope только потому, что в документах появилась формула.

Если решение принято позднее, оно получает новый ID/version, migration note и
fixture. Registry v1 остаётся доступен для replay; новые значения выпускаются
как registry v2 или additive policy overlay.

## 3. Сохранённые решения Жени

| ID | Уточнение `reference v2` | Отношение к policy v1 | Точка возврата |
|---|---|---|---|
| ZV2-01 | При роли в N процессах default allocation = 1/N | Конфликт с K17, где fallback основан на person-shifts | Перед C14/C18 |
| ZV2-02 | Стоимость закрытия дефицита без default, условно обязательна; 0 отключает монетизацию | Конфликт с K07 `annual_direct` default | Перед C14 |
| ZV2-03 | Годовое высвобождение округлять `floor(final × ramp)` | Конфликт с K09 `ceil` | Перед C14 |
| ZV2-04 | Флаг «разрешить замену избыточных», default false | Новая policy, отсутствует в K01–K29 | Перед C14 |
| ZV2-05 | Дефицит/избыток считать по ролям; object totals только report | Совместимо с запретом взаимозачёта ролей, уточняет K17 | Перед C14/C18 |
| ZV2-06 | Process catalog хранит required fields/integrations/allocation; activation: role → checkbox → automatic | В основном совместимо с C03/C05; не менять текущие mappings молча | После C11, до C14 |
| ZV2-07 | 29 role codes; `catering_worker` используется и для airport catering | Требует сверки с K19 mapping `trolley_operator` | После C11, до C14 |
| ZV2-08 | Батарея включена в цену робота; отдельная цена только для replacements | Новая commercial policy, влияет на C13/C15 | Перед C13/C15 |
| ZV2-09 | Повторная замена основного оборудования по сроку службы, без амортизации replacement CAPEX | Новая упрощённая lifecycle policy | Перед C15/C16 |
| ZV2-10 | Явные `CAPEX_gross`, `CAPEX_amortizable`, `CAPEX_cashflow` | Совместимо с K11/K13, требует контрактного уточнения | Перед C15/C16 |
| ZV2-11 | RaaS infrastructure ownership: client/vendor | Расширяет K21 | Перед C13/C17 |
| ZV2-12 | Goods/services gross VAT, labour без VAT; default 20%, отдельная card rate | K20 сохраняет raw gross и запрещает угадывать rate; ставки deferred до evidence | Перед C13/C16 |
| ZV2-13 | Интеграции относятся к applicability score, не hard fail; итог 23 проверки | Направление совместимо с K14/K15, но поставка внутренне противоречива | Перед C05/C19 |
| ZV2-14 | Fleet density <30 m²/robot — warning object-level | Совместимое уточнение C05, не hard fail и не score penalty | Перед C05 |
| ZV2-15 | Deployment и utilization — разные кривые | Полезное расширение, но в поставке два разных hackathon defaults | Перед C15 |
| ZV2-16 | Дополнительный доход / предотвращённые потери, default 0 | Соответствует категории ТЗ, но требует отдельного provenance/input | Перед C03/C16 review |
| ZV2-17 | Пульт/tech и shared OPEX считаются один раз на объект; minimum pult не масштабируется | В основном совместимо с K06/K17, формулы требуют reconciliation | Перед C14/C18 |
| ZV2-18 | TCO использует cashflow CAPEX, replacements и вычитает residual; отдельный gross TCO | Расширяет определения K11/K13 | Перед C16/C17 |

## 4. Внутренние неоднозначности поставки

До принятия policy v2 необходимо разрешить:

- 23 проверки в основном тексте против 31 в поздней сводке R02;
- integrations как score component против упоминаний hard fail в process catalog;
- `deployment_curve = utilization_curve = ramp` против deployment `1.0` для
  купленного сразу hackathon-парка;
- новые VAT/airside/medical assertions без достаточной первичной evidence;
- дубли заголовков, повторные summary-блоки и несовпадающие счётчики замен;
- простую замену оборудования без cohorts и налогового эффекта как явно
  временное упрощение, а не универсальный финансовый факт.

## 5. Review checkpoints без блокировки C03

| Gate | Когда | Что решаем |
|---|---|---|
| V2-A | После C11, до C14 | role mapping/allocation, deficit/surplus, activation |
| V2-B | Перед C13/C15 | VAT basis, battery inclusion, CAPEX bases, RaaS ownership |
| V2-C | Перед C16/C17 | replacements, TCO/ROI/payback, additional income, tax supplement |
| V2-D | Перед C19 | окончательный набор checks и integration scoring |

### V2-B — решение C13

Gate закрыт 2026-09-23 без изменения policy v1:

- **ZV2-08 — REJECTED_WITH_REASON как универсальный default.** Батарея считается
  включённой только при явном included-cost/source scope; отдельная replacement
  line остаётся возможной для C15. Наличие батареи в любой цене не выводится
  автоматически.
- **ZV2-11 — ADOPTED_IN_POLICY_V2 как contract field.** Ownership каждой RaaS
  responsibility задаётся `CUSTOMER/VENDOR/INTEGRATOR/SHARED/UNKNOWN`; отсутствие
  evidence остаётся `UNKNOWN`, без fallback allocation.
- **ZV2-12 — REJECTED_WITH_REASON в части default VAT 20%.** Сохраняется K20:
  organizer gross не делится, `NET_RUB` требует explicit rate, labour VAT здесь
  не рассматривается. Gross basis и отдельная card rate поддержаны контрактом.
- CAPEX cost bases приняты по K25 как discriminated
  `FIXED_TOTAL/PER_ROBOT/PERCENT_BASE`; численная агрегация остаётся C15.

Каждый gate должен завершаться одним из результатов: `ADOPTED_IN_POLICY_V2`,
`DEFERRED_POST_MVP` или `REJECTED_WITH_REASON`. Отсутствие решения не меняет
policy v1 и не останавливает более ранние независимые этапы.

## 6. Полнота плана и контроль новых добавлений

Все C01–C29, включая полную экономику, allocation, sensitivity, simulation,
exports и rollout, обязательны. Этот delta-register не сокращает существующий
scope, не переводит этапы в optional и не разрешает заменять расчёт постоянным
`PARTIAL`/`NOT_CALCULATED` там, где карточка требует завершённый результат.

Контроль сложности применяется только к требованиям сверх принятого плана.
Каждое ZV2-решение сохраняется до своего gate, получает явный итог
`ADOPTED_IN_POLICY_V2`, `DEFERRED_POST_MVP` или `REJECTED_WITH_REASON`, а
принятое решение добавляется versioned с тестами и migration/replay policy.
Таким образом проект последовательно выполняет весь план, но новая логика не
появляется стихийно и не создаёт очередной скрытый канон.
