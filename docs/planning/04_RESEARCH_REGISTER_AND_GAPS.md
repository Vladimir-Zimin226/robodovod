# RobCo — Research register & gaps v0.2

## 1. Status legend

- `DONE` — достаточно для product decisions MVP;
- `DONE_WITH_CAVEATS` — полезно, но отдельные числа/claims нельзя зашивать как truth;
- `NEEDS_REMEASUREMENT` — структура полезна, quantitative evidence недостаточна;
- `WATCH` — обновить при появлении новых официальных данных.

## 2. Register R1–R10

| ID | Тема | Статус | Что переносим в продукт |
|---|---|---|---|
| R1 | Global robot catalog/specs/prices | DONE | evidence-first catalog, hard constraints, reference models |
| R2 | Economics/TCO/ROI/NPV | DONE | full installed CAPEX, OPEX, cash-flow, conservative assumptions |
| R3 | Competitors | DONE | positioning, table-stakes, gap: early feasibility + causal economics |
| R4 | Visualization / similar services | DONE | 2D scenario visualization + standalone WebGL RobCraft; no engineering digital-twin claims |
| R5 | Official LCT case | WATCH | compliance checklist; revisit after official Q&A/material updates |
| R6 | Process-level readiness | DONE | dimensions, gates, evidence vs heuristics separation |
| R7 | Russian robotics procurement | DONE | localization/OEM/procurement/service/supply fields, RU shortlist |
| R8 | Chinese robotics for RU | DONE | CN shortlist, Russia channel, technical vs commercial scores |
| R9 | Wordstat/search demand/naming | NEEDS_REMEASUREMENT | terminology/intent/SEO hypotheses only; frequencies not trusted |
| R10 | Regional factors inside Russia | DONE_WITH_CAVEATS | region UX + labor/logistics/service/environment model; no hardcoded unsourced coefficients |

## 3. Research decisions already accepted

### Robot catalog

- catalog must be evidence-first;
- missing public value = `UNKNOWN`, not zero/false;
- vendor throughput is sanity check, not capacity formula;
- arm price != cell price;
- global references are useful even when procurement in Russia is weak.

### Russian procurement

Need separate:

- origin/localization;
- OEM/rebrand;
- sales channel;
- service;
- spares;
- commissioning;
- cloud/update dependence;
- supply risk.

### Chinese layer

Do not define as «cheap substitutes». Use:

`technical_fit + commercial_observation + russia_procurement_evidence`.

### Regional context

Strongest useful factors for MVP:

- federal subject;
- remote/far north/arctic flags;
- labor fallback;
- logistics/mobilization class;
- service coverage;
- actual operation environment.

But exact multipliers in R10 are illustrative unless separately sourced.

### SEO/search

Accepted qualitatively:

- user language spans both `автоматизация` and `роботизация`;
- process/problem-first language is important;
- CTA `рассчитать окупаемость` is clearer than `сформировать ТЭО` for broad audience;
- professional terminology can appear progressively.

Rejected as evidence:

- approximate Wordstat counts;
- inferred B2B percentages;
- unsourced SEO competition/naming scores.

## 4. Remaining research/gaps before freeze

### G1 — Wordstat real measurement

Need real observed data or remove quantitative claims from pitch/site plan.

Minimum:

- 20–30 high-value queries;
- Russia region;
- consistent match mode;
- observed date;
- screenshots/export where possible.

**Priority: P1 for hackathon, P0 only if naming/SEO is presented to jury.**

### G2 — Curated procurement validation

For each DEMO_CURATED option confirm:

- official/current model;
- key hard constraints;
- source dates;
- Russian channel/service status;
- price boundary/status;
- no contradictory field used in calculation.

**Priority: P0.**

### G3 — Regional defaults dataset

Do not research all 89 subjects deeply before hackathon. Need a small deterministic table sufficient for demo:

- Moscow Oblast;
- Magadan Oblast;
- Murmansk Oblast;
- optionally Sakhalin/Primorye.

Store only sourced/explicit fields; everything else `UNKNOWN`.

**Priority: P0/P1 depending demo.**

### G4 — Official LCT updates

Re-check after Q&A/new materials. Do not let new criteria surprise the team.

**Priority: P0 watch.**

## 5. Research artifact rules going forward

Every numeric observation intended for computation:

```yaml
value:
unit:
source_url:
source_type:
observed_at:
applies_to:
confidence:
notes:
```

Product heuristics additionally:

```yaml
policy_owner: RobCo
policy_version:
reason:
not_market_fact: true
```

## 6. Research freeze criterion

Research is sufficient for MVP when:

- warehouse golden path can run with no invented critical values;
- at least 3 technical candidates can be compared;
- at least 2 procurement alternatives have credible Russian evidence;
- economics exposes uncertainty rather than filling gaps silently;
- regional adjustment has a defensible fallback policy;
- every demo-visible claim can be traced to evidence or labeled assumption.
