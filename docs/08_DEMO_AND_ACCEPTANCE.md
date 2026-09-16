# RobCo — Demo, datasets & acceptance v0.2

## 1. Demo objective

За 3–5 минут жюри должно понять:

- пользователь не обязан знать робототехнику;
- RobCo умеет сказать «не подходит»;
- расчёты детерминированы;
- каталог доказательный;
- Россия/Китай/global reference различаются технической и закупочной логикой;
- экономика считает проект, а не цену робота;
- visualization объясняет scenario;
- финал — usable preliminary ТЭО.

## 2. Golden demo — warehouse

### Step 1 — input

Пользователь вводит свободный текст, например:

> Склад 12 000 м², 800 перемещений паллет в сутки, средний маршрут 180 м, паллета до 650 кг, 2 смены, хотим сократить ручные перевозки.

Регион может быть указан естественно или уточнён позже.

### Step 2 — extraction

Показываем chips/facts:

- object;
- process;
- volume;
- route;
- load;
- shifts;
- unknown critical values.

### Step 3 — clarification

5–7 вопросов максимум, только material parameters:

- проходы;
- pickup/drop;
- floor/slope;
- people traffic;
- WMS;
- charging;
- region if needed for economics/procurement.

### Step 4 — readiness

Show:

- readiness band;
- dimensions;
- blockers;
- confidence;
- prerequisites.

### Step 5 — architecture

RobCo recommends e.g. `PALLET_TRANSPORT_AMR`, with alternatives `AUTONOMOUS_FORKLIFT` and partial automation if relevant.

### Step 6 — candidates

For recommended architecture show 2–4 options:

- Russian procurement-ready option;
- Chinese option with Russian channel;
- global technical reference;
- only if each is actually comparable for the task.

Each card:

- technical fit;
- procurement fit RU;
- price status;
- service/supply risk;
- confidence;
- 2–3 reasons;
- caveat.

### Step 7 — hard rejects

At least one candidate should be visibly rejected for a real reason, proving the system is not a catalog ranking toy.

### Step 8 — capacity

Show mission-cycle trace and fleet result.

### Step 9 — economics

Show:

- hardware/solution price boundary;
- installed CAPEX;
- annual OPEX;
- labor cash benefit;
- TCO 5y;
- payback;
- NPV;
- uncertainty range.

### Step 10 — what-if

Change 2 → 3 shifts or labor cost. Chain recomputes:

`capacity/economics/recommendation`.

Optional wow-case: switch object profile from standard Moscow-region assumptions to Magadan regional context, but only if regional seed data is defensible.

### Step 11 — visualization

Текущее состояние: обязательного 2D top-down в основном интерфейсе нет.
Встроенный same-origin RobCraft показывает поддержанные representative-сценарии
в 3D от первого лица и со свободной камерой:

- racks/zones;
- pickup/drop;
- routes;
- chargers;
- разные модели движущихся роботов и людей;
- безопасные остановки, объезды и резервирование конфликтных зон;
- погрузка, выгрузка, зарядка, отказы и накопление доставленного груза;
- before/after;
- KPI/report overlay.

Label it `Интерактивный сценарий работы` или `сценарная симуляция`, not `инженерный цифровой двойник`.

К конкурсной приёмке отдельный 2D-viewer должен читать тот же ScenarioSpec,
показывать зоны/маршруты/роботов/операции/зарядку и иметь
start/pause/restart/speed/scenario controls. RobCraft 3D не заменяет этот пункт.

### Step 12 — report

Generate preliminary ТЭО with sources/assumptions.

## 3. Demo 2 — Airport / large logistics

Purpose: show different process + commercial mode.

Recommended story:

- outdoor/yard cargo movement;
- environmental exposure;
- Russian autonomous transport/RaaS reference;
- recurring service economics instead of pure CAPEX;
- optional inspection/cleaning subscenario.

This demo proves economics engine is not hardcoded to AMR purchase.

## 4. Demo 3 — Clinic/service

Purpose: prove service robotics branch.

Possible scenario:

- cleaning large floors;
- delivery as secondary comparison.

Important honesty:

- do not label front-of-house service robot as secure medical delivery robot;
- if no strong Russian hardware SKU exists, show Chinese procurement option or managed service and say evidence gap explicitly.

## 5. Negative demo

Input intentionally unsuitable for full automation:

- highly variable task;
- insufficient volume;
- unresolved safety blocker;
- impossible geometry.

Output:

`NOT_RECOMMENDED_YET` + process redesign/preconditions.

This is a critical trust signal.

## 6. Definition of Done — Product

- starts from process/problem;
- architecture is explicit;
- technical/procurement/economic dimensions are separate;
- Russia is fixed market;
- no country question;
- region asked only when material;
- user can see assumptions/confidence;
- at least two real procurement alternatives in golden path;
- negative recommendation works.

## 7. Definition of Done — Technical

- analysis numeric core works without LLM;
- same normalized input + versions → same output;
- hard constraint UNKNOWN is not PASS;
- price boundary preserved;
- procurement status versioned/date-stamped;
- regional benchmark fallback traceable;
- golden tests pass;
- demo reset works.

## 8. Definition of Done — Research/data

For every DEMO_CURATED record:

- model identity verified;
- critical specs sourced;
- contradictions resolved or flagged;
- procurement status RU supported;
- service/supply caveat known;
- price status/boundary known;
- no unsupported «X% cheaper» claim.

## 9. Definition of Done — UX

- user sees result before drowning in details;
- maximum 2–4 recommended candidates;
- separate badges for technical/procurement/confidence;
- unknown values visually distinct;
- evidence click does not disrupt main flow;
- regional context explained in plain Russian.

## 10. Demo reliability checklist

- public VPS + HTTPS;
- seeded DB;
- presets;
- deterministic local calculations;
- LLM fallback;
- one-click/reset command;
- backup screenshots;
- backup screen recording;
- report HTML fallback;
- no dependency on live vendor sites;
- no dependency on live Wordstat;
- no dependency on live weather/logistics APIs.

## 11. Likely jury questions

### «Почему просто не ChatGPT?»

Because LLM only extracts/explains. Engineering constraints, capacity, procurement policy and economics are versioned deterministic engines.

### «Насколько точен ROI?»

Preliminary estimate with source/assumption/confidence ranges. Site survey/quote/pilot reduce uncertainty.

### «Откуда цены?»

Each price has boundary, source/date/confidence. Quote-only is shown as quote-only.

### «Почему китайский вариант лучше?»

RobCo does not assume it is better. Technical fit and Russia procurement evidence are separate. Sometimes Russian, Chinese or global reference can win on different axes.

### «Что означает российский робот?»

We distinguish legal manufacturer, development, assembly, OEM/rebrand, localization and service instead of one country badge.

### «Регион меняет подбор?»

Only when actual operation environment does. Region mostly changes labor/logistics/service/confidence; indoor heated process remains indoor heated even in Magadan.

### «Это simulation?»

RobCraft — это детерминированная сценарная симуляция с упрощённой физикой, заданиями и collision avoidance. Это не инженерный digital twin: модель не откалибрована по CAD, паспортной кинематике, WMS/FMS или реальной телеметрии, поэтому её KPI нельзя выдавать за подтверждённую производительность объекта.

## 12. Pitch skeleton

1. Problem: early robotization decision is fragmented.
2. User describes process, not robot.
3. AI structures data.
4. Readiness + architecture.
5. Hard constraints.
6. **Procurement reality for Russia.**
7. Capacity + economics.
8. Region/context effect.
9. What-if.
10. Visualization + preliminary ТЭО.
11. Why different: causal, evidence-first, procurement-aware.
