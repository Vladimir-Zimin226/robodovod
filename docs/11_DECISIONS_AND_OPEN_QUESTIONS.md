# РОБОДОВОД — Decisions & Open Questions

## 1. Frozen decisions

### Product

- Product and repository name: `РОБОДОВОД` / `robodovod`.
- `RobCo`, «РобоМера» and `Prism` are former working names retained only in historical materials.
- Market MVP = Russia only.
- User starts from process/problem.
- Preliminary ТЭО is final artifact, not first CTA.

### Architecture

- monolith FastAPI + React + PostgreSQL;
- LLM outside numeric truth path;
- versioned deterministic engines;
- technical catalog / evidence / procurement separated;
- AutomationArchitecture introduced;
- EquipmentModel != SolutionConfiguration != ProcurementOption;
- ServiceOffering supported.

### Procurement

- no phrase «санкционно безопасный» as system guarantee;
- use procurement status/confidence/supply risk;
- RU/CN/global references may coexist;
- global benchmark can remain reference-only;
- localization and supply risk are orthogonal.

### Region

- no country question;
- region optional until material;
- subject/city enough for MVP;
- actual environment drives technical constraints;
- no unsourced region multiplier.

### Visualization

- основной интерфейс пока сохраняет 2D scenario visualization;
- автономный 3D-движок называется «РобКрафт» и живёт в `robcraft/`;
- RobCraft запускается независимо и встраивается только через будущий версионированный контракт;
- допустим термин «сценарная симуляция», но не claims инженерного цифрового двойника или подтверждённой производительности.

## 2. Decisions to freeze before coding contracts

### Q1. Final readiness dimensions/weights

Owner: Z.  
Deadline: before readiness implementation.

### Q2. Architecture taxonomy for golden path

Need exact 6–10 enum values, not endless hierarchy.

Owner: Z.

### Q3. Demo curated equipment set

Need exact 8–10 records, with role:

- RU candidate;
- CN candidate;
- global technical reference;
- service/RaaS example.

Owner: Z, reviewer EXT.

### Q4. Procurement scoring policy

What makes `procurement_fit_ru` 90 vs 70? Need transparent rubric or qualitative band.

Recommendation for MVP: use bands (`HIGH/MEDIUM/LOW`) internally derived from a few explicit subfactors rather than pretend precise 0–100 science.

Owner: Z.

### Q5. Regional logistics policy

Need decide whether v0.2 economics uses:

A. only user-entered logistics + warnings, or
B. a small sourced planning allowance table for 3 demo regions.

Recommendation: B for presets, A for general user flow.

Owner: V+Z.

### Q6. Labor benchmark source implementation

Need determine actual accessible dataset/export for regional/industry fallback. If ingestion is time-expensive, keep demo-seeded values and ask user labor cost in generic flow.

Owner: V.

### Q7. Recurring commercial model

Choose one:

- Evocargo-style RaaS;
- managed service;
- generic RaaS schema.

Recommendation: generic engine + one real demo seed.

Owner: V+Z.

### Q8. Fixed manipulation scope

Does golden path require palletizing/cobot calculations or only catalog comparison?

Recommendation: P1 depth unless official criteria make it essential.

## 3. Research/watch questions

- official LCT Q&A/criteria updates;
- real Wordstat remeasurement;
- source-backed regional labor/logistics seeds;
- current procurement freshness for DEMO_CURATED records;
- domain reviewer sanity check.

## 4. Naming

`RobCo`:

- okay for internal/hackathon use;
- do not build commercial SEO strategy around it yet;
- avoid copying Fallout visual identity/trade dress;
- commercial naming decision after real search/trademark/domain check.

## 5. Product language

Preferred broad-user copy:

- «Что хотите автоматизировать?»
- «Оценить роботизацию»
- «Рассчитать окупаемость»
- «Подходящие варианты»
- «Доступность в России»
- «Что нужно проверить перед внедрением»

Technical progressive disclosure:

- AMR/AGV;
- hard constraints;
- TCO/NPV;
- procurement confidence;
- evidence provenance;
- ТЭО.

Avoid as primary marketing language without evidence:

- «автоматизация под ключ»;
- «цифровой двойник»;
- «оптимизированный fleet»;
- «точный ROI»;
- «санкционно безопасный».
