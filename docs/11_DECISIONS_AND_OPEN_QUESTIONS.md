# РОБОДОВОД — Decisions & Open Questions

Уточнение 2026-09-19: исторические решения ниже сохранены; их расчётная часть
пересмотрена по reference Жени 3.2. Текущий канон, конфликтующие пары источников
и владельцы решений: [план 19](19_ZHENYA_CALCULATION_IMPLEMENTATION_PLAN.md).
В частности, Q6 о salary benchmarks больше не разрешает salary fallback:
целевая зарплата вводится пользователем по роли, без default из preset/региона.

Непосредственная следующая ветка — `contracts/calculation-semantics-v1`.
Capacity formulas следуют после units/registry/intake/constraints/audit.
В этой документационной сессии новые формулы и runtime activation не выполнялись.

### Расчётные вопросы после аудита reference

- Женя: полный process_catalog и role codes; exchange total/split, рабочая
  скорость и batch conversions; precision и zero-domain policy.
- Женя: распределение pult/released/additional, дефицит и ричтраки;
  годовой ramp/service/severance и повторные замены батарей.
- Женя и профильный reviewer: tax modes/losses и применимость нормативных
  требований; источники цены без НДС, RaaS responsibilities и warranty.
- Женя: curves/weights scoring, denominator 75/77, completeness без зарплаты,
  shared infrastructure/roles allocation и ranking cohort.
- Женя и simulation owner: scheduling/SLA, окно/знаменатель отклонения >10%,
  разделение availability и моделируемых потерь, типовой проект для ≤60s.
- Владелец продукта: какие из 28 blocks обещают самостоятельный capacity;
  отсутствующие формулы нельзя заменить generic transport. Упоминание БАС
  не разрешает включать их в текущий pool без отдельного решения и evidence.

Полный регистр Q01–Q12 и K01–K29 находится в плане 19; принятие предложенного
решения фиксируется отдельным decision record, не подразумевается этим списком.
Catalog baseline 187/223, capacity 21/24 (6/6 ready и 15/18 с assumptions),
deployment-ready 0 сохраняется. Изменение pool требует доказанного diff и
согласования; calculation readiness и formula executability разделены.

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
- PostgreSQL foundation and storage ADR precede organizer catalog integration;
- organizer data and external enrichment are separate immutable layers;
- only approved verified evidence may become an automatic matching input;
- catalog import is versioned, transactional and idempotent;
- embedded legacy fleet is removed; runtime/discovery require activated catalog slots;
- `organizer-catalog-v4` is the confirmed current organizer version;
- deterministic derived organizer JSON/CSV bundle may be committed to Git;
  source binaries and working staging remain outside Git;
- P0 uses PostgreSQL plus local named volumes for uploads/backups; S3 is deferred;
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

- обязательной 2D scenario visualization в основном интерфейсе пока нет;
- автономный 3D-движок называется «РобКрафт» и живёт в `robcraft/`;
- RobCraft запускается независимо и уже встроен same-origin iframe через
  `ScenarioSpec v1` и двухфазный revision protocol;
- 2D реализуется отдельным consumer того же ScenarioSpec и остаётся P0;
- допустим термин «сценарная симуляция», но не claims инженерного цифрового двойника или подтверждённой производительности.

### Authentication and administration

- guest is an unauthenticated, non-persistent demo flow;
- self-registration requires email/password and optional name, always creates
  role USER;
- roles stored for accounts are USER and ADMIN; project sharing is not planned;
- ADMIN creates, edits, disables/deletes users and performs password reset;
- the last active ADMIN cannot be deleted or demoted;
- ADMIN may download a sanitized diagnostic bundle, not a raw database dump;
- operational `pg_dump` and uploads backup remain server/CLI operations;
- the first ADMIN is created by an idempotent one-shot bootstrap from
  `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` and optional
  `BOOTSTRAP_ADMIN_NAME`; the local `.env` is ignored by Git, while
  `.env.example` contains placeholders only, and bootstrap never overwrites an
  existing administrator;
- passwords use Argon2id; browser auth uses secure HttpOnly/SameSite cookie and
  CSRF protection.

### Deletion and diagnostics

- project deletion hard-deletes project payload, runs, metadata and local files;
- only a minimal deletion tombstone remains without filenames, content, email or
  name; retention is 30 days, then the tombstone is purged;
- diagnostic bundle contains versions, manifests, import/integrity results,
  redacted errors and aggregate counts, but no secrets, password hashes, PII,
  uploaded binaries or full user snapshots.

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

## 3.1. Storage decisions before the first migration

Closed decisions are recorded above and in docs/17. Remaining product/research
questions do not block 0001–0003 because the import contract preserves every
source row:

- exact duplicate-row semantics beyond preserving every source row;
- exact readiness weights and demo-curated equipment set.

The working direction is recorded in
`17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md`.

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
