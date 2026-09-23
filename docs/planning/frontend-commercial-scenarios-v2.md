# Frontend commercial scenarios v2

Статус: **IMPLEMENTED**, C21 `frontend/commercial-scenarios-v2`, 2026-09-23.

## Результат

Добавлен отдельный frontend flow для шести комбинаций
`PURCHASE/RAAS × PESSIMISTIC/BASE/OPTIMISTIC`. Он активируется только для
versioned `commercial-scenarios-bundle-v2`; C12 capacity viewer и legacy saved
run viewer сохранены отдельными ветками.

Bundle содержит строгие presentation projections существующих C13–C20
snapshots с source schema version/digest, tenant/project/revision bindings и
независимыми procurement, financial, allocation, ranking и sensitivity
statuses. Смешанные identities, stale revision, неполная матрица из шести
сценариев и ложный `RECOMMENDED` при incomplete finance или unready procurement
отклоняются до отображения.

## UI и отсутствие клиентской арифметики

Экран показывает commercial inputs и monthly gross по ролям, raw price/tax
basis, procurement blockers, baseline/scenario/delta cashflows, expenses,
object roles, control-post, technical staff, NPV project, nullable payback,
assumptions, provenance и version bindings. Sensitivity отображает шесть
готовых server deltas и причины дискретных fleet/headcount steps.

Frontend не вычисляет CAPEX, OPEX, NPV, payback, ranking, VAT или sensitivity.
Decimal strings форматируются только для presentation. Неизвестная ставка VAT
остаётся «не задана», missing salary видна как blocker, `NOT_REACHED` payback
показывается текстом, а procurement `UNVERIFIED` не выглядит готовым.

Первое изменение USER price/RaaS/salary input удаляет result из локальной
session, скрывает все старые метрики и предлагает новый server run. Старый
result не переиспользуется и не корректируется браузером.

## Контракты, проверки и границы

Добавлены strict JSON Schema и воспроизводимый golden fixture, runtime adapter,
responsive React component и App routing. Tests покрывают все шесть комбинаций,
partial finance, false-best guard, no VAT guess, server-only metrics, exact
displayed money, missing salary, sensitivity, identity/revision isolation,
input invalidation и сохранение старых viewers. Полный frontend suite, ESLint и
production build проходят.

C21 не меняет backend formulas/API persistence, catalog/pool membership,
immutable registry, старые runs или production runtime. Simulation, exports и
реальные procurement/payment actions вне scope. Rollback аддитивен: удалить
presentation contract, adapter/component, route, styles, fixture/generator,
tests и этот отчёт. Следующий этап — C22 `contracts/scenario-spec-v2`.
