# Полная экономика проектов роботизации RobCo: консервативная TCO/ROI/payback/NPV-модель

## Принцип модели и ключевой вывод

Главная рекомендация для RobCo: **никогда не считать экономику от цены робота**. Для стационарной промышленной автоматизации Association for Advancing Automation приводит показательный ориентир: сам робот в turnkey-системе может составлять лишь около **трети полной установленной стоимости**; остальное — проектирование, tooling/end-of-arm equipment, ограждения и safety, conveyors, интеграция, программирование и монтаж. OSHA аналогично рассматривает законченное robotic application как систему, включающую end-effector, датчики, safeguarding, controls и fixtures, а не только манипулятор. citeturn15search0turn15search3

Поэтому RobCo стоит строить модель как **cash-flow engine из отдельных статей**, где каждая статья имеет:

`min / base / max + fixed/site / per-robot / %hardware + confidence + source + included_in_vendor_quote`.

Не следует скрывать неопределенность одним «точным» числом. Для hardware публичные цены доступны относительно часто; для facility modifications, networking, WMS/MES/ERP, commissioning и supervision они значительно более site-specific. В этих строках разумнее иметь широкий planning allowance с низкой confidence и обязательное требование заменить его коммерческим предложением до investment approval.

**Рекомендуемая семантика confidence:**

| Confidence | Что означает для RobCo |
|---|---|
| **High** | OEM, регулятор/стандарт, официальный прайс или несколько надежных прямых источников |
| **Medium** | публичный reseller/integrator price, несколько согласующихся отраслевых источников |
| **Low** | слабая публичная прозрачность; диапазон — budgeting assumption RobCo, который нельзя выдавать за рыночный benchmark |

Для safety особенно опасно закладывать ноль только потому, что устройство называется AMR или cobot. ISO 3691-4:2023 охватывает safety driverless industrial trucks, включая AGV и AMR, а актуальные ISO 10218-1/-2 опубликованы в редакции 2025 года для industrial robots и robot applications/cells; ISO 10218-2 прямо охватывает safeguarding при integration, commissioning, operation, maintenance и repair. citeturn14search6turn14search4turn14search10

## Стоимость hardware по классам

Ниже — **не закупочный прайс-лист**, а первый диапазон для pre-quote оценки. В большинстве случаев это стоимость базового оборудования или публично наблюдаемого package, **до полной site integration**, если явно не сказано обратное.

| Класс | Консервативный planning range hardware, USD | Что двигает цену | Confidence / основания |
|---|---:|---|---|
| **AMR** | **$40k–150k**, heavy/custom **$200k+** | payload, lift/top module, IP/environment, precision docking, fleet features | **Medium.** Публичный MiR250 сейчас встречается около $51.8k; конфигурация с дополнительным carrier заметно дороже. citeturn18search0turn18search4 |
| **AGV** | **$40k–200k+** | payload, type, navigation infrastructure, lift, customization | **Low–Medium.** Текущие отраслевые budgeting guides дают примерно $40k–70k для unit-load, $75k–200k+ для forklift AGV и $200k+ для custom systems. citeturn20search4turn20search12 |
| **Autonomous tug / tugger** | **$20k–120k** | towing capacity, train configuration, navigation, indoor/outdoor | **Medium.** Публичный отраслевой диапазон $20k–120k с payload/navigation/environment как основными драйверами. citeturn20search1 |
| **Robotic forklift** | **$45k–250k+** | pallet mover vs stacker/reach/VNA, lift height, payload, precision, hybrid/manual mode | **Medium.** Публичные ориентиры: ~$45–60k pallet mover, ~$60–80k stacker, ~$85–120k counterbalance, ~$95–130k reach, ~$150–200k VNA; более сложные autonomous systems могут идти выше. citeturn20search13turn20search22 |
| **Service delivery robot** | **$10k–25k** | payload/trays, displays, elevator/door integration, environment, fleet | **Medium–High.** BellaBot публично начинается около $14.5k; Keenon T10 предлагается примерно за $19.6k у одного reseller и $23k у другого. citeturn21search32turn21search13turn21search9 |
| **Cleaning robot** | **$10k–50k** типично; тяжелые industrial units могут быть выше | width, scrub/vacuum/sweep, water tanks, autonomous refill/drain, duty cycle | **Medium–High.** RobotLAB дает общий диапазон около $10k–50k; PUDU CC1 Pro — $24k, MT1 — ~$19k–20k. citeturn18search6turn18search2turn18search34 |
| **Inspection drone / drone-in-a-box** | **~$20k–25k** для базового DJI Dock 3-class system; specialized payloads выше | thermal/sensor payload, dock, RTK/relay, weather hardening, regulatory package | **Medium–High.** DJI официально позиционирует Dock 3 + Matrice 4D/4TD для удаленных 24/7 operations; публичные bundle prices находятся примерно в районе $20.8k–24.3k до installation/options. citeturn21search2turn21news38turn21search34 |
| **Palletizing cell** | **$50k–300k+** | payload/reach, pallets/SKUs, EOAT, conveyors, vision, guarding, cycle rate | **Medium–High.** Robotiq дает широкий диапазон $50k–300k+ именно для robotic palletizer в зависимости от complexity/capability. citeturn19search1 |
| **Cobot** | **$35k–70k** arm/base package; deployed application часто существенно выше | payload/reach, EOAT, machine interface, vision, fixtures, safety | **High** для публичных anchors: UR10e около $44.6k у Vention; Haas 5/10/15 kg integrated packages ~$42k/$48k/$63k и включают часть grippers, barriers и fixtures. citeturn19search21turn19search11turn19search2turn19search8 |

Особенно важно различать **bare arm**, **robot package**, **cell** и **fully commissioned system**. Например, Haas 10 kg package за ~$48k уже включает cobot, два pneumatic grippers, protective barriers, temporary mounting base, parts table, flip station и cabling; сравнивать его напрямую с bare-arm quote некорректно. citeturn19search2

То же относится к palletizing: $50–300k у Robotiq — уже уровень solution/cell, поэтому RobCo не должен сверху автоматически добавлять еще «100% integration», не проверив bill of materials. citeturn19search1

## Полный cost stack TCO

В этой таблице `M` означает: строка **обязана существовать в финансовой модели**, хотя она может быть равна нулю, если vendor contract явно включает ее. `C` — conditional по application/site.

| Статья | Обязательность | Главный cost driver | Planning range для MVP | Тип стоимости | Confidence / источник |
|---|---|---|---|---|---|
| **Hardware** | **M** для всех | класс, payload/reach, environment, lift, sensors, redundancy | см. таблицу выше | **per robot / per cell** | **Med–High.** Публичные OEM/reseller anchors приведены выше. |
| **Chargers / docks / initial batteries** | **M** для battery robots; C если входит в bundle | fleet size, robots/charger, charge rate, automatic vs cable charging, water dock у cleaners | **RobCo placeholder:** 5% / 10% / 20% от mobile hardware для min/base/max, **но всегда заменять quote**; для drone dock считать частью core hardware | **per robot + shared fixed/site** | **Low** на %, **High** на необходимость. MiR имеет отдельную autonomous Charge 48V; у CC1 docking station обеспечивает charging + water supply/drain, а Dock 3 является основой autonomous drone operation. citeturn22search1turn22search2turn21search2 |
| **End effectors / top modules / attachments** | **C**, но обычно **M** для palletizing/cobot | gripping technology, custom fingers, vacuum, force sensing, tool changing, AMR top module | простое EOAT **$3k–15k** planning; custom/vision/process tooling quote separately | **per robot** | **Medium.** Один актуальный Robotiq 2F-85 reseller anchor — ~€5.6k ex VAT; completed application по OSHA включает end-effector. citeturn23search6turn15search3 |
| **Safety equipment** | **M** как risk/safety work; hardware C по результатам assessment | speed/mass, human interaction, load, pinch/crush/drop risk, cell access | **$5k–30k** для простой system allowance; сложная fenced cell может быть существенно выше. Не использовать blanket `%` после quote | **fixed/cell + per robot** | **Medium**. Один current safety laser scanner стоит порядка $3.0k–3.4k сам по себе, до fencing/interlocks/controllers; ISO/OSHA требуют учитывать safeguarding всей application. citeturn23search15turn23search19turn14search10turn15search3 |
| **Facility modifications** | **C**, часто существенны у AGV/forklift/drone/fixed cell/cleaner | floor, doors, elevators, racks, charging power, foundations, water/drain, barriers | **RobCo allowance:** 0–10% HW simple; 10–30% при utilities/doors/layout; >30% — отдельный engineered estimate | **fixed/site** | **Low.** Универсальный рынок здесь бессмыслен. Для cleaning даже автоматизация refill/drain зависит от выбранной workstation architecture; PUDU предлагает варианты с water/drain и варианты без plumbing modifications. citeturn22search2turn22search6 |
| **Networking / IT infrastructure** | **C→M** для fleet/cloud/drone | Wi-Fi coverage, VLANs, industrial switches, redundancy, cybersecurity, LTE/5G, server/cloud | **RobCo allowance:** $0–5k small site; $5–25k standard fleet; $25–100k+ major redesign | **fixed/site**, иногда per device | **Low.** Это budgeting envelope, не рыночный benchmark. Отдельно quote после wireless/network survey. |
| **WMS / MES / ERP / API integration** | **C**, но может быть критическим M для intralogistics | number/type of APIs, event semantics, exception handling, master data, testing, legacy systems | **RobCo allowance:** $5–25k light interface; $25–100k standard bidirectional; $100–300k+ complex/custom | **fixed/site/interface** | **Low.** Не использовать как final estimate: public pricing крайне project-specific. IT integration, mapping и training часто bundling-ятся в commercial robotics offering, из-за чего hardware quote нельзя сравнивать с managed/RaaS quote напрямую. |
| **Installation / commissioning / mapping / training** | **M** | cell complexity, routes/maps, traffic testing, programming, SAT/FAT, site travel, training | **$5–20k** simple; **$20–80k** engineered; custom fixed cell может идти намного выше | **fixed/site + per cell** | **Medium.** Один 2026 integrator benchmark дает $125–200/h × ~150–400 h, то есть ~$19k–80k engineering/integration до дополнительных hardware/site costs; A3 подтверждает, что integration может быть большой долей turnkey cost. citeturn23search1turn15search0 |
| **Software licenses / fleet / cloud** | **M в модели**, фактическая плата может быть 0, если perpetual/bundled | fleet size, missions, users, cloud storage/video, enterprise connectors | от **$0** bundled до recurring enterprise quote; для planning можно держать **2–8% HW/year** до quote. Low-end public drone example — ~$999/year | **fixed/site / per fleet / per robot / subscription** | **Low–Medium.** FlytBase Pro публично запускался по $999/year и поддерживал DJI docks; enterprise functionality и storage/services могут тарифицироваться отдельно. citeturn22search7turn22search19 |
| **Annual support / maintenance / repairs / spares** | **M** | duty cycle, environment, response SLA, parts logistics, warranty, fleet scale | **3–8% initial system cost/year** как основной reserve; **5–15% robot price** встречается для industrial robot maintenance в зависимости от среды | **% hardware/system per year + fixed SLA** | **Medium.** Один industry benchmark приводит 3–8% system cost; специализированный robot-maintenance provider — 5–15% purchase price. citeturn23search4turn23search0 |
| **Energy** | **M**, но не задавать универсальный $ | battery kWh/cycle, average kW, scheduled hours, charging losses, local tariff | **рассчитывать, не угадывать**: `kWh × tariff`; min/base/max через energy measurement/spec + tariff scenario | **per operating hour / per cycle** | **High** для формулы, **Low** для универсального диапазона. Например, MiR250 имеет battery capacity 1.63 kWh; для UR10e один distributor указывает ~350 W average consumption — различия между классами слишком велики для единой ставки. citeturn22search0turn19search9 |
| **Battery replacement** | **M reserve** для battery classes | equivalent full cycles, calendar aging, temperature, depth of discharge, replacement battery quote | считать по lifecycle; до quote **5–20% HW per replacement event** только как low-confidence placeholder | **per robot / replacement event** | **Medium** для lifecycle method, **Low** на generic %. MiR250 специфицирует минимум 3,000 full cycles до снижения capacity ниже указанного threshold. citeturn22search8 |
| **Operator / supervision** | **M** практически во всех случаях | exceptions, loading/unloading, replenishment, QA, traffic incidents, cleaning consumables, remote drone oversight | не задавать рыночный `$`; до pilot считать **10–30% исходного task labor retained** + site-level supervision allowance | **fixed/site + variable/FTE** | **Low** на staffing ratio; необходимость operational oversight зависит от application. Для drones regulatory operating concept также может ограничивать фактически автономный режим; в США BVLOS по Part 107 по состоянию на 2026 остается предметом waiver/authorization framework. citeturn14search0turn14search5 |

### Что обязательно добавить сверх исходного списка

Для RobCo я бы ввел еще четыре строки, даже если в UI MVP они первоначально находятся под `Other OPEX/CAPEX`:

`consumables`, `insurance/compliance`, `decommissioning`, `contingency`.

Для cleaning consumables — brushes, squeegees, detergent, filters и вода — могут быть реальными recurring costs; сама PUDU workstation, например, автоматизирует detergent addition и water handling, что подтверждает наличие этих физических consumables. citeturn22search2

Для inspection drone стоит отдельно учитывать cloud storage/data processing, communication, remote operations и regulatory/compliance workload. DJI Dock 3 предназначен для удаленных operations, а сторонние autonomy platforms добавляют fleet, data-security и workflow functionality; это отдельная экономическая система поверх самого aircraft/dock. citeturn21search2turn22search19

**Contingency для MVP:** пока статья не покрыта binding quote, разумно использовать RobCo allowance примерно **10–20% на неопределенные non-hardware CAPEX**, а не добавлять contingency ко всему hardware, по которому уже есть фиксированное предложение. Это не «отраслевой факт», а преднамеренная защита модели от optimism bias.

## Availability, utilization и корректный расчет эффекта

Самая распространенная концептуальная ошибка — заменить фактически продуктивные часы фразой «робот работает 24/7». Техническая способность автоматически заряжаться не означает 100% utilization. MiR, например, действительно поддерживает autonomous charging и fleet-aware charging, а текущий MiR250 имеет до 13–17.5 часов runtime в зависимости от нагрузки; это устраняет часть charging friction, но не спрос, congestion, blocked destinations, process starvation или failures. citeturn22search1turn18search24

Для RobCo лучше использовать loss waterfall:

\[
H_{scheduled}
\rightarrow
H_{technical-ready}
\rightarrow
H_{operational-ready}
\rightarrow
H_{demanded}
\rightarrow
H_{productive}
\]

где:

\[
A_{tech} =
1-\frac{H_{unplanned\ downtime}}{H_{scheduled}}
\]

\[
U_{effective}=
\frac{H_{productive}}{H_{scheduled}}
\]

Именно **effective productive utilization** должен попадать в labor/throughput model. Не нужно одновременно брать фактический measured productive utilization и еще раз умножать его на charging downtime, congestion и availability, если эти потери уже находятся внутри измерения.

### Planning assumptions RobCo до появления pilot data

Это **не отраслевые benchmarks**, а специально консервативные starting priors:

| Класс | Conservative | Base | Optimistic | Как измерять в pilot |
|---|---:|---:|---:|---|
| AMR / AGV / tug / robotic forklift | **45–55%** effective productive utilization | **60–70%** | **75–85%** | productive mission minutes / scheduled minutes |
| Service delivery | **35–45%** | **50–60%** | **65–75%** | successful loaded delivery minutes + completed missions |
| Cleaning | **55–65%** | **70–80%** | **80–90%** | completed required m² / planned m² лучше, чем runtime |
| Palletizing cell / cobot | **55–65%** | **70–80%** | **80–90%** | good-cycle time / scheduled process time |
| Inspection drone | **не задавать generic %** | site-specific | site-specific | permitted weather-window × technical readiness × successful missions |

Для drone особенно опасно ставить generic utilization. В США, например, Part 107 waivers используются для операций за пределами стандартных ограничений, включая BVLOS; FAA также ведет отдельную нормотворческую работу по более широкому BVLOS framework. Поэтому юридически допустимые operating windows должны быть параметром модели по конкретной юрисдикции, а не свойством hardware. citeturn14search0turn14search14

Для first-year benefits дополнительно нужен **ramp factor**, потому что steady-state нельзя применять к дню запуска:

| Scenario | Year-one realization of steady-state |
|---|---:|
| Conservative | **75–80%** |
| Base | **~90%** |
| Optimistic | **~95%** |

Это RobCo modeling margin, не market statistic.

### Как правильно считать labor savings

Робот не экономит деньги в размере:

\[
Robot\ hours \times Labor\ rate
\]

если компания продолжает платить тем же людям.

Правильная последовательность:

\[
AddressableHours =
BaselinePaidHours
\times TaskShareInScope
\]

\[
AutomatableHours =
AddressableHours
\times AutomationCoverage
\times Reliability
\]

Но финансовый эффект должен быть ограничен фактически cashable labor:

\[
CashableHours =
\min(
AutomatableHours,\;
PayrollHoursActuallyRemoved
+
OvertimeAvoided
+
AgencyHoursAvoided
+
PlannedHiresAvoided
)
\]

\[
LaborSavings_t =
CashableHours_t
\times LoadedCashLaborRate_t
\]

`LoadedCashLaborRate` должен включать только реально изменяемые cash costs: wage, payroll taxes, employer-paid benefits, shift/overtime premiums и variable agency costs. Не следует включать allocated corporate overhead, если он останется после автоматизации.

В качестве иллюстрации, а **не универсального RobCo default**, BLS сообщает, что в марте 2026 года средняя стоимость compensation для private-industry employer в США составляла $46.60 за hour worked: $32.60 wages и $14.01 benefits, то есть benefits — около 30.1% total compensation. Для Японии, Европы или конкретного клиента эти данные нельзя переносить; нужен customer-specific loaded rate. citeturn15search2turn15search12

Если сотрудник не увольняется и не заменяет open requisition/overtime/contractor, released hours должны идти в модели как **capacity benefit / soft benefit**, а не как hard labor savings.

Это особенно важно для cobot и palletizing: автоматизация части цикла часто оставляет loading, replenishment, QA, exception handling или material presentation человеку. Поэтому assumption `1 robot = 1 FTE saved` без task-level time study использовать нельзя. Общие safety requirements также предполагают operational, maintenance и commissioning interactions с людьми, а не полностью «безлюдную» систему. citeturn14search10turn15search3

### Когда throughput разрешено монетизировать

Throughput имеет hard-dollar value только тогда, когда дополнительная производительность способна превратиться в дополнительный contribution margin или избежать другой реальной cash expense.

Для RobCo рекомендую:

\[
MonetizableUnits_t =
\min(
\Delta Capacity_t,\;
ProfitableUnmetDemand_t,\;
UpstreamAvailable_t,\;
DownstreamAvailable_t
)
\]

\[
ThroughputBenefit_t =
MonetizableUnits_t
\times ContributionMarginPerUnit_t
\times RealizationFactor_t
\]

Не использовать `revenue per unit`: нужен **contribution margin после incremental variable cost**.

Throughput можно поставить >0 в base-case только если выполнены одновременно четыре проверки: robotized operation действительно bottleneck; есть спрос/backlog либо robot avoids real outsourcing/overtime/capex; upstream и downstream способны пропустить дополнительный volume; коммерческий margin известен.

Если этих доказательств нет, **Conservative throughput benefit = $0** и, как правило, **Base = $0**. Capacity improvement показывается отдельно как operational KPI.

Главное правило против double counting: если высвободившийся сотрудник нужен, чтобы обеспечить более высокий volume, нельзя одновременно считать его зарплату полностью «сэкономленной» и присваивать полный throughput benefit.

## Финансовые формулы и сценарии

### Стандартный RobCo cash-flow model

Пусть:

`HW` — hardware;  
`CH` — chargers/docks;  
`EOAT` — end effectors;  
`SAFE` — safety;  
`FAC` — facility modifications;  
`NET` — networking;  
`INT` — WMS/MES/ERP integration;  
`COMM` — installation/commissioning/mapping/training;  
`SW0` — initial software;  
`SP0` — initial spares;  
`CONT` — contingency.

Тогда:

\[
CAPEX_0 =
HW+CH+EOAT+SAFE+FAC+NET+INT+COMM+SW_0+SP_0+CONT
\]

Годовой OPEX:

\[
OPEX_t =
Software_t+
Support_t+
Maintenance_t+
Repairs_t+
Spares_t+
Energy_t+
Supervision_t+
Consumables_t+
Connectivity_t+
Compliance_t
\]

Battery или other major replacement лучше **не амортизировать искусственно ровной строкой**, если строится cash-flow NPV:

\[
Replacement_t =
\begin{cases}
BatteryCost_t,&\text{replacement year}\\
0,&\text{otherwise}
\end{cases}
\]

Для battery robots:

\[
ExpectedBatteryReplacementYear
\approx
\min
\left(
CalendarLife,\;
\frac{RatedFullCycles}{EquivalentFullCyclesPerYear}
\right)
\]

Например, MiR250 заявляет минимум 3,000 full charging cycles до указанного degradation threshold; это аргумент за cycle-driven model вместо правила «менять батарею каждые N лет» для всех платформ. citeturn22search8

Energy:

\[
EnergyCost_t=
kWh_t\times Tariff_t
\]

Для battery robot:

\[
kWh_t
=
\frac{
BatteryCapacity
\times EquivalentFullCycles_t
}{
ChargingEfficiency
}
\]

Для стационарного робота:

\[
kWh_t =
AveragePower_{kW}\times RunHours_t
\]

**Не рекомендую RobCo иметь global `$ energy / robot / year` default.** Слишком различаются 350 W-class cobot и industrial forklift battery system. Публичные данные UR10e и MiR250 хорошо показывают порядок этой неоднородности. citeturn19search9turn22search0

### TCO

Nominal TCO на горизонте \(N\):

\[
TCO_N =
CAPEX_0+
\sum_{t=1}^{N}
(OPEX_t+Replacement_t)
+
Decommissioning_N
-
Residual_N
\]

Для финансового сравнения лучше также показывать PV-TCO:

\[
PV(TCO)=
CAPEX_0+
\sum_{t=1}^{N}
\frac{
OPEX_t+Replacement_t
}{
(1+r)^t
}
+
\frac{Decommissioning_N-Residual_N}{(1+r)^N}
\]

### Benefits и net cash flow

\[
Benefit_t =
LaborSavings_t+
ThroughputBenefit_t+
HardQualitySavings_t+
AvoidedEquipmentCost_t+
OtherCashSavings_t
\]

Safety/ergonomics/quality можно показывать как KPI, но не следует автоматически переводить в cash. Денежное значение safety имеет смысл, например, если есть собственная history of incidents, claims, insurance/downtime cost и понятная вероятность их снижения.

\[
FCF_t =
Benefit_t-OPEX_t-Replacement_t-\Delta WorkingCapital_t
\]

### NPV

\[
NPV =
-CAPEX_0+
\sum_{t=1}^{N}
\frac{FCF_t}{(1+r)^t}
+
\frac{Residual_N-Decommissioning_N}{(1+r)^N}
\]

`r` должен быть finance-approved hurdle rate / WACC-like discount rate клиента. **RobCo не должен выдавать единый market discount rate за факт.** Если finance rate временно неизвестен, для прототипа модели допустима только sensitivity, например **8% / 10% / 12%**, явно помеченная `temporary modeling assumption`.

### Payback

\[
Payback =
\min
\left\{
t:
-CAPEX_0+
\sum_{k=1}^{t}FCF_k
\ge0
\right\}
\]

Не показывать «2.37 years», если исходная модель годовая и labor/utilization являются грубыми assumptions. Корректнее показать **2–3 года** или перейти к monthly cash flow, если нужна месячная точность.

Дополнительно полезен discounted payback:

\[
DiscountedPayback =
\min
\left\{
t:
-CAPEX_0+
\sum_{k=1}^{t}
\frac{FCF_k}{(1+r)^k}
\ge0
\right\}
\]

### ROI

Поскольку «ROI» используется компаниями по-разному, RobCo должен **зафиксировать одно определение в продукте**. Я рекомендую TCO-based ROI:

\[
ROI_{TCO,N}=
\frac{
TotalBenefits_N-TCO_N
}{
TCO_N
}
\]

и рядом всегда показывать NPV. NPV — менее двусмысленный decision metric; простым ROI легко манипулировать горизонтом и исключением recurring costs.

### Cost per productive unit

Для operational comparison между robot classes полезно дополнительно считать:

\[
CostPerProductiveHour=
\frac{AnnualizedTCO}{ProductiveHours}
\]

и классовые KPI:

`$/mission`, `$/pallet move`, `$/delivery`, `$/m² cleaned`, `$/inspection`, `$/good pallet`, `$/good part`.

Это часто более информативно, чем «стоимость робота».

### Сценарии RobCo

Горизонт следует держать одинаковым между Conservative/Base/Optimistic — иначе optimistic case искусственно улучшается просто за счет большего числа лет.

| Assumption | Conservative | Base | Optimistic |
|---|---:|---:|---:|
| Непокрытый quote CAPEX | upper-end estimates | current expected quote | lower-end validated quote |
| Contingency на неопределенный non-HW CAPEX | **20%** | **10–15%** | **5–10%** |
| Mobile effective utilization | **45–55%** | **60–70%** | **75–85%** |
| Fixed-cell effective utilization | **55–65%** | **70–80%** | **80–90%** |
| Year-one ramp | **75–80%** | **~90%** | **~95%** |
| Cashable labor realization от validated automatable hours | **50%** | **70–80%** | **90%** только при staffing plan |
| Residual supervision | **~30%** addressable task labor | **~20%** | **~10%** |
| Maintenance reserve | **~8% system cost/y** | **~5%** | **~3%** |
| Throughput | **$0**, если нет binding evidence | только validated; haircut ~50% | validated high realization |
| Residual value | **$0** | **$0** | только при documented resale/buyback |
| Discount rate, если finance rate отсутствует | sensitivity **12%** | **10%** | **8%** |

Maintenance scenarios 3–8% опираются на опубликованный system-cost benchmark; в тяжелой/грязной среде отдельные maintenance providers приводят диапазоны до 15% robot purchase price, поэтому 8% не следует считать hard ceiling. citeturn23search4turn23search0

Optimistic case **не должен быть approval case**. Его назначение — upside sensitivity. Основной investment decision должен выдерживать Base и иметь понятный downside в Conservative.

### Разумный NPV horizon

IFR в статистике operational stock использует средний assumed industrial-robot service life **12 лет**, причем историческое исследование указывало, что физическая жизнь могла быть ближе к 15 годам. В том же источнике IFR отмечает, что tax depreciation periods могут быть гораздо короче — порядка 5–6 лет в приведенных примерах, а low-cost robots способны иметь service life менее пяти лет. citeturn16view0turn17view0

Из этого **не следует** считать 12–15-летний NPV для каждого RobCo проекта. Physical hardware life ≠ economically useful application life: software, vendor platform, process, product mix и integration могут устареть раньше.

Я рекомендую:

| Тип | Primary RobCo horizon | Sensitivity |
|---|---:|---:|
| AMR / AGV / tug / robotic forklift | **5 лет** | 3 / 7 лет |
| Service delivery / cleaning | **5 лет** | 3 / 7 лет |
| Inspection drone | **5 лет максимум до validated regulatory/tech case** | 3 / 5 |
| Cobot / palletizing cell | **5 лет для общего comparison**, плюс **7-летний supplemental view** | 5 / 7 / 10 |

Так RobCo сохраняет сопоставимость классов и не «покупает ROI» длинным горизонтом. Более долгий 7–10-летний view для fixed industrial cell допустим как sensitivity, поскольку физическая жизнь industrial robot действительно может быть существенно длиннее пяти лет. citeturn17view0

## Почему ROI роботизации обычно завышается

Наиболее опасная ошибка — **hardware-only CAPEX**. При стационарной автоматизации публичный ориентир A3, где робот может быть примерно третью turnkey system, показывает, насколько сильно arm/list price способен занизить investment requirement. citeturn15search0

Вторая ошибка — считать rated availability как paid utilization. Automatic charging, long runtime и возможность remote operation расширяют operating window, но не гарантируют наличие заданий, свободный маршрут, готовый load/unload point, upstream material, downstream capacity или weather/legal window. MiR и DJI действительно дают технологии для near-continuous/remote operations; экономический utilization все равно определяется процессом. citeturn22search1turn21search2

Третья — `robot hours × worker wage = savings`. Реальная экономия возникает только при удалении payroll, overtime, agency labor или предотвращении будущего найма. Freed capacity без staffing action — не cash saving. Для fully-loaded labor rate также нельзя брать только wage: американский BLS example показывает существенную benefit component, но этот ratio необходимо локализовать по клиенту. citeturn15search2

Четвертая — считать, что supervision станет нулевой. Для fixed robots сохраняются loading, exceptions, QA и maintenance; для cleaning — consumables/refill/edge cases; для service robots — guest/customer exceptions; для autonomous forklifts — pallet/rack anomalies; для drones — remote operating and regulatory obligations. Современные safety standards прямо охватывают commissioning, operation, maintenance и repair вокруг robot application. citeturn14search10turn14search6

Пятая — монетизировать **всю дополнительную production capacity по revenue**. Нужны bottleneck confirmation, profitable unmet demand, contribution margin и capacity всех соседних процессов. Иначе throughput — operational KPI, не financial benefit.

Шестая — двойной счет: одновременно full FTE reduction и full throughput uplift от тех же freed hours; maintenance contract плюс отдельный maintenance reserve; RaaS fee плюс hardware depreciation/support/software, уже входящие в subscription; battery reserve плюс battery replacement cash flow; integrated palletizing-cell price плюс повторное добавление included EOAT/safety/integration.

Седьмая — отсутствие ramp. Initial mapping, process tuning, training, exceptions и WMS/MES integration почти неизбежно означают, что Year 1 не является steady-state year. Поэтому RobCo scenario model должен иметь отдельный ramp factor.

Восьмая — zero-cost infrastructure. Особенно это опасно для cleaning docks, autonomous forklifts и drones: water/drain/power, rack/floor tolerances, charging placement, wireless coverage, foundation/RTK/communications или doors/elevators способны превратить «простую установку» в отдельный facility project. PUDU прямо показывает, что cleaning workstation architecture меняет требования к water/drain, а DJI Dock 3 продается как system, установка которого идет сверх базовой bundle price. citeturn22search2turn21news38

Девятая — считать cobot автоматически «без safety cost». Актуальная ISO 10218 framework относится к industrial robots и applications/cells; required risk reduction определяется application, а не маркетинговым словом collaborative. Даже Haas в своем cobot package включает protective barriers. citeturn14search4turn19search2

Десятая — слишком длинный horizon и необоснованный residual value. IFR показывает физическую жизнь industrial robots существенно длиннее пяти лет, но одновременно отмечает намного более короткие depreciation periods и возможную короткую жизнь low-cost robots. Для investment model безопаснее сначала использовать 5-летний view и нулевой residual, а не предполагать, что технологически устаревшая система обязательно сохранит значительную resale value. citeturn17view0

## High-impact assumptions и рекомендации для MVP RobCo

Для sensitivity analysis не нужно варьировать одинаково все пятьдесят inputs. Основная часть неопределенности обычно сосредоточена в нескольких переменных. Для RobCo я бы ставил сверху tornado chart именно: **cashable labor hours, robot count/sizing, effective utilization, integration/facility CAPEX, Year-one ramp, maintenance/software OPEX, residual supervision и monetized throughput**. Hardware list price часто заметен визуально, но не обязательно является самым опасным assumption: A3 как раз показывает, насколько крупными могут быть surrounding system costs. citeturn15search0

### Минимальная структура data model

Каждая cost line должна храниться не просто как число, а как объект примерно такого смысла:

```text
cost_item
class
site_id
vendor
amount_min
amount_base
amount_max
currency
price_basis        # fixed_site | per_robot | per_cell | pct_hardware | annual | usage
quantity_driver
included_in_bundle
recurring
start_year
replacement_year
source_type
source_date
confidence
notes
```

Особенно важен `included_in_bundle`: Haas cobot package демонстрирует, почему без него легко дважды добавить grippers/barriers/fixtures, а drone-in-a-box bundle уже содержит dock и aircraft. citeturn19search2turn21news38

### Defaults, которые стоит зашить в MVP

Для неизвестного проекта разумный initial model может стартовать с **5-летнего horizon, zero residual value, no throughput benefit, 10–15% contingency на незафиксированные non-hardware CAPEX, 5% annual maintenance reserve и 20% residual supervision of addressable labor**. Maintenance default находится внутри опубликованного 3–8% system-cost диапазона; остальные значения являются именно консервативными RobCo modeling defaults, а не статистикой рынка. citeturn23search4

Discount rate лучше вообще сделать mandatory input. В отсутствие finance input интерфейс может показывать sensitivity 8/10/12%, но с warning `temporary assumption — replace with corporate hurdle rate`.

Energy должен рассчитываться из equipment specification или pilot telemetry, а не из `% hardware`. Battery replacement — из EFC/cycle model. Software, integration, networking и facility modifications до получения quote должны иметь **Low confidence badge**, даже если в spreadsheet они получили числовой midpoint.

### Как сократить MVP без потери полноты

Вместо девяти независимых экономических движков достаточно четырех archetypes:

| Archetype | Покрываемые классы | Специальные economics |
|---|---|---|
| **Mobile intralogistics** | AMR, AGV, tug, robotic forklift | fleet sizing, charging, WMS, traffic, pallet/load exceptions |
| **Mobile service** | service delivery, cleaning | demand/route coverage, replenishment, consumables, elevators/doors |
| **Autonomous inspection** | inspection drone | dock, weather/legal window, cloud/data, remote supervision |
| **Fixed manipulation** | palletizing cell, cobot | EOAT, guarding, fixtures, machine/PLC/MES integration, cycle/yield |

Hardware ranges остаются class-specific, но cost engine, cash-flow formulas и scenario mechanics могут быть общими.

### Что MVP обязан показывать пользователю

Основной экран investment case должен одновременно показывать:

**Year-0 installed CAPEX**, а не robot price; **annual recurring OPEX**; **five-year TCO и PV-TCO**; **NPV**; **simple и discounted payback**; **TCO-based ROI**; **cost per productive unit**; Conservative/Base/Optimistic; и tornado sensitivity.

Самый полезный visual warning — разница:

\[
Robot\ price
\rightarrow
Installed\ project\ CAPEX
\rightarrow
5y\ TCO
\]

Именно здесь скрывается большая часть ошибок procurement-stage ROI.

### Approval logic

Для RobCo я бы не делал rule вида «робот хорош, если payback < 2 years»: требуемый payback зависит от cost of capital, риска и политики клиента.

Вместо этого approval case должен отвечать трем условиям: **Base NPV положительный при finance-approved hurdle rate; проект не зависит от unvalidated throughput; Conservative case показывает приемлемый downside и явно объясняет, какие assumptions ломают economics.**

Optimistic case должен использоваться исключительно для upside, а не как аргумент закупки.

### Практический gate перед переводом opportunity в «validated ROI»

До этого gate диапазоны остаются estimates. После него у RobCo должны быть: vendor quote с included/excluded BOM; site survey; process time study; baseline task labor и customer-loaded rates; planned staffing action; simulation или pilot productive utilization; WMS/MES/ERP interface scope; safety assessment scope; charging strategy; maintenance/software SLA; battery pricing/lifecycle; и documented demand/contribution margin, если monetizes throughput.

**Итоговая консервативная позиция RobCo:** hardware prices можно использовать для lead qualification, но инвестиционное решение должно строиться только на installed-cost stack и cashable benefits. Для неизвестных строк лучше показывать широкую Low-confidence вилку, чем midpoint с двумя знаками после запятой. Для labor — считать только реализуемые payroll/overtime/hiring savings. Для throughput — ноль без доказанного bottleneck и profitable demand. Для NPV — базовый горизонт пять лет, zero residual и единый horizon между сценариями; семь лет — дополнительная sensitivity для более долговечных fixed cells. Такой подход сознательно занижает красивый headline ROI, но существенно снижает вероятность того, что RobCo продаст клиенту экономику, которая исчезнет после commissioning. citeturn15search0turn17view0