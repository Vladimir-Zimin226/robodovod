# Commercial inputs and procurement report v1

Статус: **IMPLEMENTED**, C13, 2026-09-23.

## Контракты и resolver

Добавлены strict versioned contracts `CommercialMoneyV1`, PURCHASE/RAAS terms,
`CostBasisV1`, service responsibilities и procurement request/report. Денежный
ввод хранит raw amount, currency, tax basis, explicit VAT rate, source, dates,
evidence и точный model/position/option scope. Ноль допустим только с явной
семантикой `EXCLUDED_BY_SCENARIO` или `ZERO_PRICE_CONFIRMED`.

Pure resolver работает с одним immutable PUBLISHED catalog snapshot. Organizer
`CASH_GROSS_RUB` сохраняется identity-преобразованием и не делится на
предполагаемую ставку. `NET_RUB` становится gross только с explicit rate;
не-RUB без отдельного будущего FX contract блокируется. Currency `UNKNOWN`
разрешается только явной revisioned USER/POLICY assumption, raw currency при
этом не переписывается.

`POST /api/v2/procurement-reports` возвращает отчёт независимо от capacity и
economics. Статусы применяются в порядке policy §5: `DISCONTINUED`,
`SUPPLY_RISK`, `CONFIRMED_AVAILABLE`, `QUOTE_REQUIRED`, `LIKELY_AVAILABLE`,
`UNVERIFIED`. Score не вычисляется. Только `CONFIRMED_AVAILABLE` означает
procurement-ready.

## Evidence gates и V2-B

USER/FILE budget допустим как scenario input, но не становится vendor quote.
Organizer price, vendor quote и procurement assertions сравниваются с полным
server-owned snapshot payload: совпадения одного ID недостаточно. Stale quote,
scope/model/position mismatch, unknown validity, ambiguous source и отсутствие
service responsibilities сохраняются отдельными machine codes.

V2-B закрыт в delta-register: blanket battery-in-price и default VAT 20%
отклонены как неподтверждённые defaults; RaaS ownership принят как explicit
responsibility с `UNKNOWN`; K25 bases сохранены без выполнения C15 arithmetic.

## Данные, проверки и границы

`synthetic-commercial-budget-v1` закрепляет MULE row 20, raw organizer
3,000,000 с unknown currency, explicit demo RUB assumption, PURCHASE/RAAS terms,
отдельные budget lines и явные zero exclusions. Golden report остаётся
`UNVERIFIED`: техническая/capacity готовность не доказывает закупочную.

Проверки покрывают gross/net VAT, unknown/foreign currency, stale/forged quote,
identity/scope mismatch, zero semantics, ambiguous sources, K25 service basis,
status priority, synthetic golden, schemas и API/OpenAPI. C13 не считает CAPEX,
OPEX, NPV или procurement score, не отправляет запросы поставщикам, не меняет
frontend, каталог membership, activation или старые runs.

Rollback удаляет additive contracts/resolver/API/fixtures; исходные organizer
price rows и catalog schema остаются неизменными. Следующий обязательный этап —
C14 `engine/role-labor-baseline-v1`.
