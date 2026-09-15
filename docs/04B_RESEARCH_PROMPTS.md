# RobCo — Research prompts after v0.2

Этот файл не повторяет полностью уже завершённые R1–R10. Он содержит **операционные follow-up prompts**, которые ещё могут повлиять на хакатонную версию.

## P0 WATCH — Official LCT case refresh

```text
Проверь только официальные материалы ЛЦТ-2026, опубликованные после последнего аудита по кейсу:
«Платформа подбора роботизированных решений с расчётом экономического эффекта и визуализацией работы роботов на объекте».

Ищи новые:
- FAQ/Q&A;
- уточнения постановщика;
- критерии и веса;
- submission requirements;
- technical restrictions;
- demo/pitch timing;
- dataset/API;
- legal/IP conditions;
- дедлайны.

Сначала перечисли только новые или изменившиеся факты с датой и официальным источником.
Затем дай delta against RobCo v0.2:
1. новое обязательное требование;
2. уже закрыто;
3. gap;
4. что изменить в backlog/contracts/demo;
5. что не требует изменений.

Не заменяй отсутствие опубликованных данных догадками.
```

## P0 — Curated catalog verification

```text
Для заданного списка DEMO_CURATED решений RobCo проведи финальную верификацию перед импортом в seed dataset.

Для каждого решения проверь:
- точное manufacturer/brand/model identity;
- current/active status;
- critical technical fields, реально используемые в hard constraints;
- operating environment;
- integration/API evidence;
- Russia procurement channel;
- service/spares/commissioning in Russia;
- supply risk;
- price status and price boundary;
- observed_at / last_verified_at;
- conflicting values across sources.

Верни только machine-importable facts и warnings.

Правила:
- missing = null/UNKNOWN;
- critical conflict = CONFLICT, не выбирай число сам;
- distributor ≠ manufacturer;
- bare arm ≠ turnkey cell;
- reseller listing ≠ installed CAPEX;
- наличие товара в РФ ≠ manufacturer-backed support;
- не делай санкционных/юридических гарантий.

Выход:
1. import-ready JSON;
2. field_evidence mapping;
3. critical conflicts;
4. DEMO_CURATED / SELECTABLE / DISCOVERY recommendation.
```

## P1 — Wordstat remeasurement

```text
Проведи фактический замер поискового спроса Яндекс Wordstat по B2B-роботизации в России.

Не используй оценочные или придуманные частотности.
Если прямой Wordstat measurement недоступен, прямо скажи, что quantitative part cannot be completed, и не подменяй его аналогиями.

Нужно измерить минимум 25 запросов из кластеров:
- роботизация производства;
- автоматизация производства;
- роботизация склада;
- автоматизация склада;
- промышленные роботы;
- промышленный робот цена;
- робот-манипулятор;
- робот паллетайзер / паллетизация;
- AMR / AGV;
- автономный/беспилотный погрузчик;
- расчет окупаемости роботизации;
- стоимость роботизации;
- подобрать промышленного робота;
- problem-first запросы про сокращение ручного труда/внутреннюю логистику.

Для каждого наблюдения обязательно:
keyword
match_mode/operator
region=Russia
frequency
observed_at
source/evidence
intent
noise notes

Отдельно:
- не использовать broad «робот» как B2B demand;
- не оценивать B2B subset простым вычитанием;
- показать queries, где высокая commercial relevance при низкой frequency.

На выходе:
1. raw observations;
2. cleaned semantic core;
3. priority landing pages;
4. product terminology implications;
5. naming implications only if supported by actual search evidence.
```

## P0/P1 — Regional demo dataset hardening

```text
Подготовь минимальный source-backed regional dataset RobCo только для:
- Московской области;
- Магаданской области;
- Мурманской области.

Цель — не создать «региональные коэффициенты», а заполнить контекст для demo/economics.

Для каждого региона найди только доказуемые данные/флаги:
- federal_subject code/name;
- far_north / arctic legal status where applicable;
- labor benchmark suitable as fallback (prefer official statistics);
- climate context relevant to exposed/outdoor robotics;
- logistics/remoteness qualitative class with evidence;
- service/mobilization assumptions only where sourced;
- evidence date/source/confidence.

Не создавай числовой logistics multiplier без прямой модели/источника.
Не применяй outdoor climate to indoor heated robot matching.
Не удваивай northern allowances, если salary benchmark уже отражает фактическую начисленную зарплату.

Output:
1. JSON-ready regional profiles;
2. source registry;
3. fields safe for auto-fill;
4. fields that remain assumption/user input;
5. warnings for demo narrative.
```

## P1 — Procurement freshness check

```text
Обнови российскую закупочную применимость только для SELECTABLE/DEMO_CURATED каталога RobCo.

Для каждого решения проверь на текущую дату:
- active Russian seller/integrator/distributor;
- authorization status if claimed;
- service/commissioning;
- spare parts evidence;
- current model status;
- price or RFQ status;
- obvious supply/account/cloud restriction updates.

Не исследуй обход ограничений и не предлагай альтернативные нелегальные supply routes.

Верни delta only:
UNCHANGED / IMPROVED / DEGRADED / UNVERIFIED
+ evidence + date + required catalog update.
```

## P1 — Domain reviewer checklist

```text
Ты — независимый инженер по промышленной роботизации. Проведи sanity review заданного golden scenario RobCo.

Не переписывай продукт. Проверь только engineering plausibility:
- выбранный automation architecture;
- hard constraints;
- mission/cycle calculation;
- fleet quantity;
- charging allowance;
- aisle/turning/load assumptions;
- integration assumptions;
- retained supervision;
- installed CAPEX completeness;
- regional/environment assumptions;
- pilot validation plan.

Для каждого пункта:
PASS / QUESTION / WRONG / MISSING
reason
severity
minimum fix before demo

Отдельно перечисли 5 вопросов, которые реальный интегратор задал бы первым.
```

## Archive note

Завершённые research tracks R1–R10 остаются исходной доказательной базой. В v0.2 новые исследования запускать только когда они закрывают конкретный gap, а не ради расширения объёма отчётов.
