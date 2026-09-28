# RobCo — Product Specification v0.2

## 1. Product boundary

RobCo — preliminary decision-support system. Все численные engineering/business outputs должны иметь источник данных, формулу или явно маркированное product assumption.

## 2. Domain model

### 2.1 Project

Хранит:

- `id`, `name`;
- `object_profile`;
- `process_profile`;
- `site_location`;
- `regional_context`;
- `analysis_runs[]`;
- versions.

`country` пользователь не вводит: текущий application market всегда `RU`.

### 2.2 ObjectProfile

Минимум:

- `object_type`;
- `area_m2` optional;
- `operating_hours_day`;
- `shifts_per_day`;
- `days_per_year`;
- `environment`;
- `floor/surface`;
- `network/integration context`;
- `human_traffic`;
- `zones/routes` optional.

### 2.3 SiteLocation

```yaml
country: RU                  # server constant
federal_subject: null        # P0 when economics/procurement requires
city: null                   # optional
address: null                # not requested in normal MVP flow
```

### 2.4 RegionalContext

Derived/confirmed context:

```yaml
far_north: null
arctic_zone: null
remote_location: null
island_logistics: null
extreme_cold_context: null
coastal_corrosion_context: null
logistics_class: UNKNOWN
mobilization_class: UNKNOWN
labor_benchmark: null
```

Important: environmental hard constraints use `ObjectProfile.environment`, not these flags directly.

### 2.5 ProcessProfile

Common fields:

- `process_family`;
- `current_method`;
- `goal`;
- `volume_per_day` / `required_throughput`;
- `peak_factor`;
- `route_distance_m`;
- `load_geometry`;
- `load_mass_kg`;
- `pickup/drop_time_s`;
- `takt/cycle` where applicable;
- `labor_fte_addressable`;
- `labor_cost_user_input`;
- `integration_requirements`;
- `safety/human interaction`;
- `constraints`.

### 2.6 ParameterValue

```json
{
  "value": 180,
  "unit": "m",
  "source": "USER|AI_EXTRACTED|BENCHMARK|DEFAULT|DERIVED",
  "confidence": 0.95,
  "evidence_id": null,
  "assumption_id": null
}
```

### 2.7 Assumption

- `id`;
- `parameter_path`;
- `value/range`;
- `reason`;
- `source`;
- `confidence`;
- `materiality`;
- `how_to_verify`.

### 2.8 AutomationArchitecture

Абстракция «как автоматизировать процесс», не привязанная к OEM.

Examples:

- `PALLET_TRANSPORT_AMR`;
- `AUTONOMOUS_FORKLIFT`;
- `GOODS_TO_PERSON`;
- `AUTONOMOUS_CLEANING`;
- `INDOOR_DELIVERY`;
- `PALLETIZING_CELL`;
- `COBOT_MACHINE_TENDING`;
- `OUTDOOR_AUTONOMOUS_TRANSPORT`;
- `AERIAL_INSPECTION`.

Fields:

- `id`;
- `calculation_profile`;
- `required_capabilities`;
- `preconditions`;
- `architecture_fit_score`;
- `reason_codes`.

### 2.9 EquipmentModel

Физический SKU/family.

Core fields:

- manufacturer/brand/model;
- `equipment_class`;
- class-specific technical specs;
- operating environment;
- interfaces/safety;
- technical evidence references;
- catalog tier.

Не использовать один generic `payload`. Примеры:

- `transport_payload_kg` для AMR;
- `rated_payload_kg` для arm;
- `useful_payload_kg` для UAV;
- cleaning productivity для cleaner.

### 2.10 SolutionConfiguration

Turnkey/system-level configuration:

- `architecture_id`;
- `equipment_model_ids[]`;
- `quantity`;
- chargers/docks;
- EOAT;
- safety;
- conveyors/fixtures;
- software;
- integration scope;
- infrastructure scope.

Для fixed robotics `arm_model != cell_configuration`.

### 2.11 ServiceOffering

Используется, когда результат приобретается как услуга, а не hardware SKU.

Examples:

- robotic delivery service;
- autonomous transport RaaS;
- managed cleaning robotics.

Fields:

- provider;
- service scope;
- equipment references optional;
- setup/integration fee;
- recurring fee;
- SLA fields only if sourced;
- geography/service evidence.

### 2.12 ProcurementOption

Коммерческий способ получить `SolutionConfiguration`/`ServiceOffering` в России.

Fields:

- supplier/integrator/provider;
- market fixed RU;
- procurement status/confidence;
- mode;
- service/spares/commissioning;
- supply risk;
- price evidence;
- lead-time evidence;
- evidence date.

### 2.13 PriceEvidence

```yaml
amount: null
currency: RUB
range_min: null
range_max: null
price_boundary: BARE_ROBOT|ROBOT_PACKAGE|CELL|TURNKEY_SYSTEM|RAAS_MONTHLY|OTHER
price_status: PUBLIC|PUBLIC_RANGE|QUOTE_REQUIRED|RAAS_QUOTE|UNVERIFIED
tax_status: INCLUDED|EXCLUDED|NOT_STATED
incoterm: null
includes: []
excludes: []
market: RU
observed_at: null
confidence: 0.0
source_id: null
```

### 2.14 Scenario

Scenario = architecture + configuration + procurement option + economic assumptions.

Fields:

- `architecture`;
- `solution_configuration`;
- `procurement_option`;
- `capacity_result`;
- `economics`;
- `technical_fit`;
- `procurement_fit_ru`;
- `economic_fit`;
- `evidence_confidence`;
- `regional_adjustments`;
- `risks`.

## 3. Intake modes

1. Template/preset.
2. Guided wizard.
3. AI chat/free text.

Все ведут в один domain model.

### Location UX

Не спрашивать страну. Location policy:

1. если пользователь сам написал город/регион → extract;
2. если регион не влияет на текущий stage → не спрашивать;
3. перед procurement/economics при отсутствии субъекта РФ → один короткий вопрос;
4. при отказе → national assumptions + lower confidence.

## 4. Completeness policy

### Critical for technical feasibility

- task/process;
- required volume/takt;
- load/process capability;
- environment/exposure;
- mandatory geometry where applicable;
- human/safety interaction.

### Critical for economics

- operating schedule;
- addressable labor/current process cost;
- or permission to use benchmark;
- regional subject preferred for fallback labor/mobilization.

### Important

- integrations;
- peak factors;
- exception rate;
- charging opportunity;
- rack/pallet geometry;
- service expectations.

## 5. Readiness Engine

Readiness remains process-level, not enterprise maturity.

Recommended dimensions:

- Process standardization/repeatability;
- Physical/technical environment;
- Infrastructure;
- Data/integration;
- Safety/operability;
- Economic potential;
- Evidence/data confidence.

Hard stops remain separate:

- safety;
- technical;
- operational;
- commercial policy (optional client-specific).

Regional context may create **preconditions** or reduce confidence, but `remote_location` itself should not arbitrarily subtract readiness points.

## 6. Matching

### Stage A — Architecture fit

Select 1–3 feasible automation architectures from process/task.

### Stage B — Technical hard constraints

Examples:

- payload/reach/force;
- aisle/turning/doorway;
- lift height;
- cycle/takt;
- environment/temperature/IP;
- floor/slope;
- load geometry;
- required integration;
- safety/function requirement.

Output: `PASS / FAIL / UNKNOWN` per constraint.

Unknown critical constraint must not silently become PASS.

### Stage C — Procurement fit RU

Evaluate:

- confirmed Russian sales path;
- service/spares;
- commissioning/training;
- supply risk;
- cloud/account/update dependence;
- price/quote evidence freshness;
- regional service/logistics context.

### Stage D — Soft ranking

Do not collapse all truth into one score. UI exposes separate dimensions.

## 7. Capacity engines

### MOBILE_TRANSPORT

Conceptual cycle:

`travel_loaded + travel_empty + pickup + drop + waits + congestion allowance + charging allowance`

`missions_per_robot = productive_operating_time / mission_cycle`

`fleet = ceil(required_missions / missions_per_robot)`

Vendor brochure throughput = sanity check only.

### MOBILE_SERVICE

Delivery/cleaning sizing based on demand/routes/area/productivity and replenishment/charging.

### FIXED_MANIPULATION

Use application cycle, takt, availability, changeover/handling allowances. Arm nominal speed is not cell throughput.

### AERIAL_INSPECTION

Mission duration + regulatory/weather operating window + battery/charging + coverage.

## 8. Economics Engine

### CAPEX

`hardware + chargers/docks + EOAT + safety + infrastructure + integration + installation + commissioning + training + logistics + mobilization + contingency`

### OPEX

`service + maintenance + repairs/spares + software + energy + consumables + supervision + recurring provider fees + periodic mobilization`

### Labor benefit hierarchy

`user-provided fully loaded cost → region+industry benchmark → regional average → national fallback`.

Every fallback carries confidence/warning.

### Procurement modes

#### CAPEX_PURCHASE

Traditional asset purchase + recurring OPEX.

#### RAAS / MANAGED_SERVICE

`initial_setup + recurring_fee + variable_fee + retained_internal_costs`.

MVP needs at least one recurring model to demo airport/service scenario.

### Metrics

- Year-0 installed CAPEX;
- annual OPEX;
- annual cash benefit;
- simple payback;
- discounted payback optional;
- 5y TCO;
- NPV;
- TCO-based ROI;
- cost per productive unit where meaningful.

Do not monetize throughput unless user supplies credible marginal value.

## 9. Scenario Engine

Two orthogonal axes:

### Architecture scenarios

Different ways to automate:

- AMR;
- autonomous forklift;
- partial automation;
- fixed cell vs cobot etc.

### Procurement alternatives

Inside an architecture:

- Russian/local option;
- Chinese option with RF channel;
- global technical reference;
- service/RaaS option.

Do not force one option from each origin if evidence/technical fit is poor.

## 10. Regional adjustments

Regional context can affect:

- labor fallback;
- logistics allowance;
- mobilization;
- service access;
- lead-time confidence;
- outdoor/environment preconditions;
- contingency.

It normally does **not** directly affect fleet quantity for an indoor stable process.

No unsourced region multiplier.

## 11. Confidence

Compute separately:

- `input_confidence`;
- `technical_evidence_confidence`;
- `procurement_confidence`;
- `price_confidence`;
- `regional_assumption_confidence`;
- `overall_decision_confidence`.

Overall confidence should be bottleneck-sensitive rather than simple average.

## 12. What-if

P0 editable parameters:

- shifts;
- volume/throughput;
- route distance;
- labor cost;
- robot/system price;
- integration cost;
- utilization/availability;
- procurement mode;
- region (optional showcase, not primary slider).

What-if reruns the deterministic chain and records deltas.

## 13. Results UX

Above the fold:

- process/object;
- readiness;
- recommended architecture;
- installed CAPEX / recurring cost;
- payback/NPV;
- confidence;
- primary procurement status.

Then:

1. why this architecture;
2. technical candidates;
3. procurement alternatives;
4. hard rejects;
5. capacity calculation;
6. economics;
7. regional effects;
8. what-if;
9. visualization;
10. risks/preconditions;
11. evidence;
12. preliminary ТЭО.

## 14. Preliminary ТЭО structure

`Objective → current process → assumptions → readiness → architecture alternatives → constraint checks → equipment/configuration → procurement alternatives RU → capacity → economics → regional adjustments → scenario comparison → risks/open questions → pilot/quote/validation roadmap → sources`.
