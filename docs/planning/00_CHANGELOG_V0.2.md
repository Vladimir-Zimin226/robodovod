# RobCo — changelog v0.2

## Причина новой версии

После v0.1 были добавлены отдельные исследования:

- российские роботизированные решения;
- китайские роботизированные решения с применимостью к РФ;
- поисковая семантика/Wordstat;
- региональные признаки России, влияющие на роботизацию.

Они изменили не только каталог, но и предметную модель.

## Решение 1 — RobotModel больше не центр системы

### Было

`Process → RobotModel → Scenario`

### Стало

`Process → AutomationArchitecture → EquipmentModel → SolutionConfiguration / ServiceOffering → ProcurementOption → Scenario`

Причины:

- голый манипулятор не равен роботизированной ячейке;
- один hardware SKU может продаваться через разные каналы/комплектации;
- RaaS/service невозможно корректно представить как «цену робота»;
- российский поставщик может быть интегратором иностранного OEM;
- один и тот же technical solution может иметь разную доступность, сервис и стоимость внедрения.

## Решение 2 — technical selection и procurement selection разделены

Каждый кандидат имеет минимум четыре независимые оценки:

- `technical_fit`;
- `procurement_fit_ru`;
- `economic_fit`;
- `evidence_confidence`.

Никакого универсального «robot_score = 87» как единственной истины.

## Решение 3 — Россия фиксирована, регион контекстный

- `market = RU` — системная константа;
- страна не спрашивается у пользователя;
- `federal_subject`/`city` запрашиваются только когда это полезно для procurement/economics/environment;
- при отсутствии региона расчёт продолжается с national defaults и пониженной confidence.

## Решение 4 — region ≠ environment

Регион не является hard constraint сам по себе.

`Magadan` не означает, что indoor AMR работает при −40 °C. Для технического matching используются реальные условия:

- `operation_environment = INDOOR_HEATED / INDOOR_UNHEATED / SEMI_OUTDOOR / OUTDOOR`;
- фактический/плановый temperature range;
- snow/ice/wind/corrosion/dust только при exposure.

Регион используется для предложения defaults/warnings, а не для подмены данных объекта.

## Решение 5 — procurement provenance становится core data

Добавлены:

- юридический производитель;
- brand owner;
- страна разработки/сборки;
- localization status;
- OEM/rebrand status;
- critical import dependencies;
- service/spares/commissioning in Russia;
- procurement mode;
- supply risk;
- price boundary;
- field-level evidence.

## Решение 6 — catalog tiers

- `DISCOVERY` — найдено, но недостаточно доказательств для auto-match;
- `SELECTABLE` — достаточно hard-constraint data и procurement evidence;
- `DEMO_CURATED` — проверено golden tests и подготовлено для защиты.

## Решение 7 — commercial model не ограничивается purchase CAPEX

Поддерживаемая taxonomy:

- `CAPEX_PURCHASE`;
- `LEASE`;
- `RENTAL`;
- `RAAS`;
- `MANAGED_SERVICE`.

В MVP обязательно реализовать `CAPEX_PURCHASE` + один recurring mode.

## Решение 8 — Wordstat research не считается закрытым количественно

Текущее исследование полезно для:

- terminology;
- search intent;
- SEO architecture hypotheses;
- CTA/landing directions.

Но приведённые частотности частично демонстративны/расчётны. Поэтому:

- qualitative conclusions → `ACCEPTED_AS_HYPOTHESIS`;
- search volumes/naming scores → `NEEDS_REMEASUREMENT`.

Не использовать эти числа в pitch как доказательство размера рынка.

## Решение 9 — regional coefficients запрещены без evidence

Не хранить hardcoded таблицу вида:

`ЦФО=1.0, Сибирь=1.2, ДВ=1.5, Арктика=2.0`

как рыночный факт.

Использовать hierarchy:

`actual project data → sourced regional benchmark → RobCo planning allowance → national fallback`.

## Решение 10 — procurement-aware differentiation становится P0

Это теперь одна из основных отличительных фич RobCo на защите:

> система может показать мировой technical benchmark, российскую альтернативу и китайскую альтернативу с российским каналом, не выдавая их за полные аналоги и не скрывая supply/service risk.
