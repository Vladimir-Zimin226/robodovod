# RobCo — Regional Context RU v0.2

## 1. Product rule

RobCo v0.2 works **only in Russia**.

Therefore:

- `country = RU` is constant;
- no country selector;
- no onboarding question about country;
- region is requested only when it materially improves procurement/economics/environment assessment.

## 2. Why region matters

Regional research supports a strong qualitative conclusion:

- high impact: labor economics, domestic logistics, engineer mobilization, service/spares access;
- conditional impact: environment for outdoor/semi-outdoor robotics;
- lower impact for most MVP cases: electricity tariff, generic internet availability;
- little direct impact on fleet quantity for the same indoor process.

Exact regional money multipliers in research are not treated as validated market constants.

## 3. Region is not environment

Separate:

### Site location

- federal subject;
- city optional.

### Operation environment

- indoor heated;
- indoor unheated;
- semi-outdoor/transition;
- outdoor;
- actual min/max temperature if known;
- snow/ice exposure;
- wind exposure;
- corrosion/moisture;
- dust/contamination.

Example:

`warehouse in Magadan + heated indoor route` does not reject standard indoor AMR based on outdoor climate.

## 4. P0 regional fields

```yaml
site_location:
  country: RU
  federal_subject: null
  city: null

regional_context:
  far_north: null
  arctic_zone: null
  remote_location: null
  island_logistics: null
  logistics_class: UNKNOWN
  mobilization_class: UNKNOWN
  service_context: UNKNOWN
  labor_benchmark: null
```

P1:

- extreme cold context;
- coastal corrosion hint;
- lead-time benchmarks;
- labor availability pressure;
- broader service-distance model.

CUT/P2:

- detailed weather maps;
- region-wide connectivity scoring;
- subsidy/tax engine;
- live route freight estimator.

## 5. Location intake policy

### Preferred

User naturally writes: `склад в Магадане` → AI extracts.

### If absent

Continue technical analysis.

Before economics/procurement, if benchmark dependence is material:

> «В каком регионе находится объект? Это нужно только для оценки зарплат, доставки и сервиса.»

Do not ask exact address unless a feature truly uses it.

### If user skips

Use national defaults and show:

`Регион не указан — логистика и стоимость труда рассчитаны с пониженной уверенностью.`

## 6. Regional effect matrix

| Factor | Technical matching | Readiness | Capacity | CAPEX | OPEX | Procurement | Confidence |
|---|---|---|---|---|---|---|---|
| Federal subject alone | No | No | No | Indirect | Indirect | Indirect | Yes |
| Actual cold exposure | Yes | Yes | Sometimes | Yes | Sometimes | No | Yes |
| Snow/ice on route | Yes/infra | Yes | Sometimes | Maybe | Maybe | No | Yes |
| Regional labor benchmark | No | Economic only | No | No | Benefit baseline | No | Yes |
| Remote logistics | No | Project readiness | No | Yes | Maybe | Yes | Yes |
| Fly-in service | No | Operational | No | Commissioning | Maintenance | Yes | Yes |
| Electricity | Rarely | Rarely | No | No | Low materiality normally | No | Low |
| Generic regional internet | No | No | No | No | No | No | Low |

## 7. Labor fallback hierarchy

1. `USER_PROVIDED_FULLY_LOADED_COST` — HIGH.
2. `INDUSTRY_REGION_BENCHMARK` — MEDIUM.
3. `REGIONAL_AVERAGE` — LOW/MEDIUM.
4. `NATIONAL_DEFAULT` — LOW.

Never double-count northern/region coefficients if benchmark already includes actual regional payroll conditions.

Do not automatically multiply user-provided salary by an extra regional factor unless user explicitly gave base salary excluding applicable additions.

## 8. Logistics model

Economics structure:

```text
equipment/system price
+ import/international logistics if relevant and known
+ domestic logistics
+ special handling
+ mobilization/commissioning travel
+ contingency for unknowns
```

`logistics_class` is a planning category, not a magic multiplier.

Possible enum:

- `STANDARD`;
- `EXTENDED`;
- `COMPLEX_REMOTE`;
- `EXTREME_REMOTE`;
- `UNKNOWN`.

Each class only controls which assumptions/questions/warnings are activated. Money must come from user quote, sourced benchmark or explicit allowance.

## 9. Mobilization model

Separate `integration_base_cost` from mobilization:

```text
mobilization = travel + accommodation + local transport + freight/special handling
```

If unknown, use range/allowance with low confidence rather than one number.

## 10. Service coverage

Do not use `service_in_russia = true` as sufficient.

Recommended:

- `LOCAL`;
- `REGIONAL`;
- `NATIONWIDE_FLY_IN`;
- `REMOTE_ONLY`;
- `UNVERIFIED`.

Optional response class only if source/evidence supports it. No invented SLA.

## 11. Environment policy

Regional hints can trigger a question:

> «Робот будет работать только внутри отапливаемого здания или выходить на улицу?»

Then actual environment is used for hard constraints.

Examples:

- indoor heated AMR in Murmansk → regional cold usually irrelevant technically;
- tug crossing open yard in Murmansk → temperature/snow become technical/infrastructure constraints;
- UAV in exposed coastal area → wind/weather/IP/regulatory window matter.

## 12. Confidence policy

Do not globally set `confidence=LOW` just because region is remote.

Lower only the affected dimensions:

- price/logistics confidence;
- service lead-time confidence;
- environment assumption confidence;
- implementation schedule confidence.

Technical payload/reach evidence remains unchanged.

## 13. Minimal demo regional dataset

Prefer 3 sourced profiles:

### Moscow Oblast

Baseline standard logistics/service context; heated warehouse demo.

### Magadan Oblast

Remote logistics + service mobilization + cold-context warning; actual indoor environment still explicit.

### Murmansk Oblast

Northern/outdoor airport/logistics showcase.

Optional Sakhalin/Primorye only if data ready.

## 14. What not to copy from research as fact

Do not hardcode illustrative values such as:

- `Far East = 1.5`;
- `Arctic = 2.0`;
- arbitrary delivery percentage uplifts;
- generic salary multipliers for all occupations;
- generic response days for vendors without SLA evidence.

These can be research hypotheses, not production constants.

## 15. Regional P0 acceptance

Feature is done when:

- no country question exists;
- location can be extracted from text;
- missing region does not block technical analysis;
- region changes only relevant economic/procurement assumptions;
- actual environment overrides climate hint;
- every regional numeric adjustment has source/assumption/confidence;
- no pseudo-precise coefficient appears without evidence.
