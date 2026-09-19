# РОБОДОВОД — Decisions & Open Questions

Уточнение 2026-09-20: по поручению пользователя все K01–K29 и Q01–Q12
расчётного плана разрешены агентом. Приоритет имеют ТЗ и дополнения,
затем [принятая policy v1](planning/calculation-policy-decisions-v1.md).
Ожидание Жени, внешнего исследования или коммерческого ответа не является
условием начала/завершения C01–C29. Scope каждого из28process blocks принят.

Непосредственная следующая ветка — `contracts/calculation-semantics-v1`.
Ключевые решения: gross денежная база по дополнениям§6; primary pretax CF;
налоговый supplement как model assumption; консервативный unknown residual;
целочисленный pult conservation; repeated battery wear; точные score curves;
детерминированная simulation/SLA policy. Подробности и тесты в
[плане19](19_ZHENYA_CALCULATION_IMPLEMENTATION_PLAN.md).

Исторические вопросы ниже не являются approval gates текущего расчётного
плана. Salary benchmark остаётся запрещённым fallback custom проекта;
для demo разрешён отдельно подписанный scenario input из dataset.
Discovery187/223, pool21/24 и отсутствие БАС сохраняются; изменение membership
исключено из этой цепочки. Readiness/evidence/runtime missing input различаются.

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

## 2. Исторические вопросы и принятые решения 2026-09-20

Следующая таблица закрывает прежние Q1–Q8 этого документа; это отдельная
нумерация от Q01–Q12 плана 19. Формулировки и прежние владельцы ниже сохранены
как история, а не как действующие зависимости.

| Вопрос | Решение для исполнения |
|---|---|
| Q1 readiness | K16 и независимые статусы capacity/labour/finance; completeness не заменяет executability. |
| Q2 taxonomy | Текущие architecture IDs сохраняются для совместимости; новые process scopes и их отображение определены K19/таблицей 28 процессов. Количество enum не является gate. |
| Q3 demo set | Текущий pool 21/24; полный warehouse fixture закреплён за MULE в policy §6. Подбор 8–10 новых записей и реального RaaS offer не требуется. |
| Q4 procurement | Численный procurement score не вводится. Сохраняются шесть статусов docs/09; детерминированный resolver и отдельный supply risk закреплены в policy §5. Отсутствие подтверждения не означает доступность. |
| Q5 logistics | Ввод пользователя или явный синтетический demo budget; региональные коэффициенты и таблицы без источника не создаются. |
| Q6 wages | USER/FILE для custom; отдельно выбранный demo assumption из dataset по K05. Региональный fallback не входит в обязательный путь. |
| Q7 recurring | Generic RaaS по K21 с раскрытым scenario tariff, без зависимости от живого коммерческого предложения. |
| Q8 fixed cell | C09 реализует формулу на synthetic fixtures; admission реального SKU требует safe facts, расширение pool не входит в этап. |

### Исторические формулировки до редакции 2026-09-20

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
