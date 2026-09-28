# RobCo — Catalog, Evidence & Procurement Policy v0.2

## 1. Goal

Catalog exists to support decisions, not to maximize number of robot cards.

A record is selectable only when RobCo can answer:

- what it is;
- what process it supports;
- which hard constraints are known;
- where each critical value came from;
- what commercial object the price refers to;
- whether there is credible Russia procurement/service evidence;
- what remains unknown.

## 2. Four entity levels

### Manufacturer / Provider

Legal entity/brand/service provider.

### EquipmentModel

Physical robot/arm/vehicle/device.

### SolutionConfiguration

Equipment + chargers/EOAT/safety/software/integration/infrastructure.

### ProcurementOption / ServiceOffering

How Russian customer can obtain the solution.

Never conflate these levels.

## 3. Catalog tiers

### DISCOVERY

May have incomplete specs or weak Russia channel.

Use for research/browse only.

### SELECTABLE

Requirements:

- identity current;
- enough technical fields for relevant hard constraints;
- no unresolved contradiction in critical fields;
- enough evidence to calculate capacity or mark unknown explicitly;
- procurement status not fabricated.

### DEMO_CURATED

Additional requirements:

- golden test exists;
- result copy manually reviewed;
- source links/date verified;
- procurement caveat reviewed;
- price boundary reviewed;
- visualization asset/icon available.

## 4. Origin/localization model

Required fields:

- `legal_manufacturer_name`;
- `manufacturer_country`;
- `brand_owner_country`;
- `development_country[]`;
- `manufacturing_country`;
- `localization_status`;
- `localization_percent` only from source;
- `russian_industrial_registry_status/number` if applicable;
- `oem_rebrand_status`;
- `underlying_oem`;
- `oem_match_confidence`;
- `critical_import_components[]` if known.

Do not show «🇷🇺 Russian» solely because seller/website is Russian.

## 5. Procurement status RU

Recommended enum:

- `CONFIRMED_AVAILABLE`;
- `LIKELY_AVAILABLE`;
- `QUOTE_REQUIRED`;
- `SUPPLY_RISK`;
- `UNVERIFIED`;
- `DISCONTINUED`.

`QUOTE_REQUIRED` is not bad; it means commercial configuration needs vendor/integrator quote.

`UNVERIFIED` does not mean unavailable.

## 6. Supply risk

Separate from localization.

Dimensions:

- sales channel;
- spare parts;
- service;
- foreign activation;
- cloud dependency;
- firmware/update dependency;
- proprietary controller/software;
- critical imported components;
- regulatory complexity.

Output:

`LOW | MEDIUM | HIGH | UNKNOWN` + reason codes.

Do not make legal/sanctions guarantee claims.

## 7. Procurement modes

- `CAPEX_PURCHASE`;
- `LEASE`;
- `RENTAL`;
- `RAAS`;
- `MANAGED_SERVICE`.

A service can be a valid solution even when no customer-owned hardware SKU exists.

## 8. Price policy

Price must state economic boundary.

Bad:

`AUBO i10 = X → palletizing project costs X`.

Good:

`AUBO i10 bare arm price = X; turnkey cell cost remains separate configuration estimate/quote`.

Required:

- value/range;
- currency;
- tax status;
- incoterm if relevant;
- scope/boundary;
- included/excluded components;
- source;
- observed date;
- confidence.

No generic claim `Chinese solution is 40% cheaper` unless normalized like-for-like evidence exists.

## 9. Technical vs procurement comparison UX

For each candidate:

```text
Technical fit        94/100
Procurement fit RU   88/100
Economics            73/100
Evidence confidence  High
```

Scores are explainability aids, not physical truth. Hard constraints remain gates.

## 10. Recommended MVP portfolio shape

### Discovery

~30–40 records from global/RU/CN research.

### Selectable

~15–20 records with adequate evidence.

### Demo curated

~8–10 records.

Suggested coverage, not final SKU commitment:

- Russian pallet AMR;
- Chinese heavy AMR with Russian integrator;
- global AMR benchmark;
- autonomous forklift;
- Russian outdoor autonomous transport/RaaS;
- Russian or Chinese cleaner;
- Chinese/Russian cobot;
- Russian palletizing cell;
- inspection reference;
- service/delivery option.

## 11. Candidate policy examples

### Global technical reference with weak procurement RU

Status: `REFERENCE_ONLY` in UI / procurement `UNVERIFIED` or `SUPPLY_RISK`.

Purpose: compare technical benchmark, not recommend purchase.

### Chinese OEM with Russian partner

Can be SELECTABLE if:

- model/specs sufficient;
- current Russian channel evidenced;
- support/service status known enough;
- supply caveat shown.

### Russian system on foreign OEM base

Show:

- Russian integration/software/localization evidence;
- underlying OEM status/confidence;
- do not label all hardware domestic unless proven.

## 12. Evidence conflict policy

If two sources conflict on a critical field:

1. prefer newer official datasheet/manual if clearly same model/version;
2. keep both observations;
3. mark field `CONFLICT` if unresolved;
4. critical conflicted field cannot be used as silent hard PASS;
5. DEMO_CURATED requires manual resolution or avoidance of that field.

## 13. Refresh policy

Technical specs: refresh when model/version changes.  
Procurement/service/price: time-sensitive; store `last_verified_at` and treat stale evidence explicitly.

MVP does not need automated refresh; manual seed version is sufficient.
