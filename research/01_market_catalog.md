# RobCo: доказательное исследование рынка роботизированных решений для предварительного аудита и ТЭО

## Executive summary

Для хакатонного MVP RobCo я рекомендую строить каталог не как «список роботов с ценами», а как **evidence-first decision dataset**: сначала несовместимость по hard constraints, затем расчет требуемого количества единиц, и только после этого — экономика. Это особенно важно потому, что производители часто публикуют payload, скорость и габариты, но не публикуют одновременно минимальный рабочий проход, turning envelope, стоимость интеграции, стоимость сервиса и фактическую производительность в смешанном трафике. Например, MiR250 имеет хорошо документированные проходы, дверные проемы, уклон, runtime и safety-функции, тогда как Kivnon K05/K55 дают хорошие сведения по грузоподъемности, навигации и интерфейсам, но не публикуют числовой minimum aisle для конкретного проекта. citeturn15search0turn13search2turn13search3

Критически важно **не подменять максимальную скорость расчетной скоростью процесса**. MiR250 способен двигаться до 2,0 м/с, K05 — до 0,7 м/с, K55 — до 1,0 м/с, FlashBot Max — 0,5–1,2 м/с, но из этих значений нельзя напрямую получить moves/hour: ожидание у станций, торможения, пешеходы, перекрестки, автоматические двери, лифты, операции pickup/drop и charging должны моделироваться отдельно. citeturn15search0turn13search2turn13search3turn22view0

Ценовые данные на рынке асимметричны. В текущих публичных источниках хорошо подтверждаются: **FlashBot Max — от $20 000**, **PUDU CC1 Pro — $24 000**, **UR10e — $44 636–49 000 за робот-манипулятор в двух текущих листингах**, а Robotiq прямо указывает, что Lean Palletizing в Americas **starts at $85 000**. Для MiR250 найден только явно обозначенный интегратором **market estimate $50 000–70 000 для ASEAN в 2026 году**; его нельзя выдавать за официальный прайс или quotation. Для Kivnon K05/K55 и Corvus One в исследованных официальных материалах числовой публичной цены не обнаружено. citeturn22view0turn19search15turn21view6turn22view3turn22view7turn14view1turn13search2turn13search3turn21view0

В результате RobCo должен поддерживать минимум три режима цены: `exact_public`, `sourced_estimate` и `quote_required`. **`quote_required` не следует автоматически заменять «среднерыночной» цифрой**: корректнее показать sensitivity model без базового NPV либо запросить quotation. Это принципиально уменьшает риск создания убедительной, но вымышленной экономики.

Для MVP я бы загрузил **девять selectable reference records — по одному на каждый требуемый класс**. Это не census всех производителей мира, а специально ограниченная evidence-first выборка: модели выбраны так, чтобы покрыть все три типа объектов, дать разные типы навигации и интеграции и одновременно сформировать достаточное количество hard constraints для rules engine.

| Приоритет | Класс | MVP reference solution | Зачем включать в RobCo | Основные объекты |
|---|---|---|---|---|
| A | AMR | **Mobile Industrial Robots MiR250** | Очень сильная открытая техническая документация: payload, aisle, doorway, slope, runtime, charging ratio, safety, Fleet REST API. citeturn15search0turn15search2 | склад, аэропорт/логистика, клиника |
| A | AGV | **Kivnon K05 Twister** | Хороший пример инфраструктурно-зависимого AGV: magnetic guidance + RFID, 450 кг carrying / 1000 кг towing, VDA 5050/OPC-UA. citeturn13search2 | склад, производство, логистика |
| A | Autonomous tug | **MiR250 Hook** | Отдельный decision branch для существующих тележек: до 500 кг, AprilTag identification, автономный pickup. citeturn15search4turn15search1 | аэропорт/логистика, склад, сервис |
| A | Robotic forklift/stacker | **Kivnon K55** | Вводит pallet geometry, lift height и aisle/turning-envelope как обязательные constraints; 1200 кг, подъем до 1500 мм, SLAM. citeturn13search3 | склад, крупная логистика |
| A | Indoor delivery robot | **PUDU FlashBot Max** | Отлично моделирует многоэтажные сервисные объекты: 60 см path clearance, elevator/e-gate integration, secure compartments. citeturn17search14turn22view0 | клиника, гостиница/сервис, терминал |
| A | Autonomous cleaning | **PUDU CC1 Pro** | Есть usable throughput 700–1000 м²/ч, runtime, path width, tank data и optional docking station — удобно для sizing engine. citeturn18search0turn18search2 | аэропорт, клиника, склад |
| A | Inventory drone | **Corvus One** | Хороший пример системы, где часть важных характеристик intentionally quote/pilot-driven: WMS API, autonomous counting и клиентские KPI доступны, но speed/dimensions/battery публично не нормализованы. citeturn21view0 | крупный склад |
| A | Palletizing cell | **Robotiq Production-Ready / Lean Palletizing** | В текущем datasheet есть 21 кг, 13 picks/min, 2200 мм и footprint полноценной ячейки; есть manufacturer starting price. citeturn19search9turn20view0turn22view7 | склад/производственная логистика |
| B | Cobot / pick-and-place | **Universal Robots UR10e, с lifecycle-флагом UR12e successor** | Очень полезный price/spec anchor, но нельзя скрывать, что поставщики уже обозначают UR12e как successor. citeturn21view4turn21view6turn22view3 | склад, сервисная/производственная ячейка |

Для net-new procurement последнюю запись стоит архитектурно хранить как `UR10e` + `successor_model=UR12e`: один текущий дистрибьютор прямо пишет «The UR10e is now the UR12e», а другой на странице UR10e называет UR12e следующей эволюцией модели. citeturn22view3turn21view6


## Нормализованный каталог, price evidence и fallback-цены

**Правило нормализации.** `confidence` ниже — не рейтинг качества самого робота. Это оценка пригодности публичных evidence для автоматизированного RobCo-аудита: `0.90–1.00` означает сильную актуальную manufacturer documentation; `0.80–0.89` — хорошую документацию с существенным неизвестным полем или lifecycle-вопросом; price confidence хранится отдельно.

**Normalized Markdown table**

| ID | Класс / manufacturer/model | Назначение и use cases | Payload / рабочая нагрузка | Dimensions | Speed | Autonomy / battery / charging | Minimum aisle / turning | Environment | Navigation / localization | Safety | Integrations | Throughput / reference performance | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|
| R01 | **AMR — MiR MiR250** | Транспорт bins, racks, modules и внутренних грузов | 250 кг | 800×580×300 мм; масса 94 кг | max 2,0 м/с | Li-ion; до 13 ч при max payload, 17,5 ч без груза; charging ratio до 1:16: 10 мин заряда → до 2 ч 40 мин работы при max payload | corridor 1450 мм default; 850 мм при minimized footprint/muted protective fields; doorway 1500/800 мм соответственно; gap ≤20 мм; уклон ±5% при 0,5 м/с | Indoor; IP21; 5–40 °C; поверхность без воды/масла/грязи | Autonomous map-based platform; два SICK nanoScan3, 3D cameras и proximity sensing в платформе | 12 safety functions; design references ISO 3691-4 с перечисленными производителем исключениями, ISO 13849-1, ISO 13850, ISO 12100, RIA R15.08-1 | MiR Fleet; REST API; ERP/WMS/MES; Wi‑Fi 2.4/5 GHz | Vendor не публикует универсальный moves/hour; использовать route model, не 2 м/с напрямую | **0.96** citeturn15search0turn15search2turn15search19 |
| R02 | **AGV — Kivnon K05 Twister** | Подхват/перемещение грузов, carts, medium-weight intralogistics | 450 кг onboard; towing до 1000 кг; integrated lift stroke 60 мм | 800×800×280 мм | max 0,7 м/с | LiFePO₄; automatic charging brushes/floor pads; runtime hours публично не указаны | Числовой operational aisle не опубликован; машина bidirectional и вращается 360°, но физические 800 мм **не равны** безопасному aisle constraint | Industrial indoor intralogistics | Magnetic guidance + RFID reading | Front laser scanner, safety PLC, E-stop | VDA 5050, Wi‑Fi, OPC-UA, UDP, TCP, Kivnon Fleet Manager | stopping accuracy ±10 мм; moves/hour не опубликован | **0.92** citeturn13search2 |
| R03 | **Autonomous tug — MiR250 Hook** | Автономный pickup и towing существующих carts | до 500 кг буксируемой нагрузки | Габарит полного `robot+hook+cart` публично не дан; base MiR250 — 800×580 мм, но использовать его как train envelope нельзя | max 2,0 м/с | до 10 ч operating time | Minimum aisle/turning с тележкой не опубликован; требуется swept-path validation по cart geometry | Indoor, на базе MiR250 | MiR navigation + AprilTag recognition для идентификации и pickup carts | Manufacturer указывает безопасное движение вокруг людей/препятствий; базовая платформа имеет safety architecture MiR250 | MiR Fleet / REST API / ERP-WMS-MES ecosystem | trips/hour не опубликован | **0.91** citeturn15search1turn15search4turn15search0turn15search2 |
| R04 | **Robotic forklift/stacker — Kivnon K55** | Autonomous pallet transport and stacking | 1200 кг | 1920×920×2340 мм | max 1,0 м/с | 2 lithium batteries; in-line/trickle charging; built-in charging connector; runtime hours не опубликованы | Manufacturer позиционирует для narrow aisles, но числовой minimum aisle не публикует — обязательна проверка turning/safety envelope | Industrial warehouse/intralogistics | SLAM | 360° laser coverage + right/left safety scanners | VDA 5050 / compatible fleet systems | lift до 1500 мм; current configuration — standard forks/open pallets; pallets/hour не опубликован | **0.92** citeturn13search3 |
| R05 | **Indoor delivery — PUDU FlashBot Max** | Room/package/amenities delivery, multi-floor service logistics | 10 кг на compartment; reseller указывает до 20 кг total; 2–4 adjustable compartments | 538×534×1052 мм; 60 кг | 0,5–1,2 м/с | до 9 ч; charge ≈4 ч; auto-docking/charging | path clearance 600 мм | Indoor и semi-open building environments: corridors, garden corridors, fitness/poolside; это **не доказательство weatherproof outdoor rating** | PUDU VSLAM+ + LiDAR/3D sensing | Multi-sensor 3D obstacle avoidance, включая low/overhanging obstacles | KONE/OTIS elevator options, e-gates/turnstiles, PUDU Link; PUDU Open Platform/Open API | 2–4 заказов за trip потенциально по числу compartments; deliveries/hour зависит от elevators/routes | **0.93** citeturn17search14turn22view0turn17search2turn17search8 |
| R06 | **Autonomous cleaning — PUDU CC1 Pro** | Sweep, scrub, vacuum, carpet vacuum, dust mop | N/A как транспортный payload | 629×552×695 мм; 75 кг | 0,2–1,2 м/с | 50 Ah; ≈3 ч charge; scrub 5 ч, sweep/vac 5 ч, carpet vacuum 4 ч, silent mop 9 ч; automatic charge/refill/drain требует optional docking station | min path 700 мм; threshold 8 мм в cleaning mode / 20 мм non-cleaning; slope 3° cleaning / 8° non-cleaning | Commercial/industrial indoor cleaning; IPX4 | LiDAR + visual-fusion / VSLAM+ | AI-driven perception continuously detects static/moving obstacles; IEC 63327 compliance/certification заявляется производителем | PUDU Link; optional e-gate/elevator integration | all-covered cleaning 700–1000 м²/ч; AI spot cleaning 1500–3000 м²/ч; cleaning width 500 мм | **0.96** citeturn18search0turn18search2 |
| R07 | **Inventory drone — Corvus Robotics Corvus One** | Autonomous inventory cycle counting: pallet-level reserves, selected bulk locations, single-deep case counting | Полезная нагрузка как отдельный параметр производителем публично не раскрыта | Не опубликованы | Не опубликована | Полностью autonomous operation/landing заявлена, но public flight runtime и charging time не опубликованы | Numerical aisle/rotor-clearance constraint не опубликован → mandatory vendor/site validation | Indoor warehouse; Cold Chain variant — до −20 °F | autonomous 3D flight; без beacon/reflector/sticker navigation; 14 onboard cameras | 14-camera omnidirectional collision prevention; может работать active shift при соблюдении vendor operating procedure | Any WMS via API/data upload или standalone; examples include SAP, Manhattan, Blue Yonder, Oracle и др.; on-prem data | Customer references: 10–12 full-facility counts/year vs 2–4; Southern Glazer’s 6× count frequency; MSI reports 20× faster counting — **case-study KPI, не universal rate** | **0.86** citeturn21view0 |
| R08 | **Palletizing cell — Robotiq Production-Ready / Lean Palletizing** | Automated case palletizing | cell payload 21 кг в current production-ready datasheet | complete cell footprint >3700×3600 мм EU; >163×142 in US | N/A для стационарной ячейки | Grid-powered; battery/charging N/A | Требуется footprint ячейки и зона conveyor/pallet access, а не aisle мобильного робота | Indoor industrial cell | Fixed robot cell; navigation N/A | Integrated safeguarding в current production-ready configuration | Upstream conveyor/cell automation и Robotiq software; публичное подтверждение generic WMS/MES API в исследованном datasheet отсутствует | до 13 picks/min; max pallet height 2200 мм; unlimited SKU/box patterns заявлено в datasheet | **0.95** citeturn19search9turn20view0 |
| R09 | **Cobot/pick-and-place — Universal Robots UR10e** | Pick-and-place, machine tending, packaging, assembly | 12,5 кг | reach 1300 мм; mounting footprint Ø190 мм; arm ≈33,3 кг | В official SW5_22 manual: tool ≈1 м/с; current distributor page указывает max TCP 4 м/с — **необходимо version resolution** | Grid-powered; typical program ≈350 W, manual lists average 615 W; battery N/A | Reach/workspace check вместо aisle; collision-free robot cell envelope обязателен | 0–50 °C, с возможным derating >35 °C; IP54 | 6-axis fixed cobot | 17 safety functions; PLd Category 3 по EN ISO 13849-1 | MODBUS TCP, EtherNet/IP, PROFINET, I/O; UR platform также предоставляет PolyScope ecosystem | cycle rate application-specific, не публикуется как универсальный picks/min | **0.88**, lifecycle transition to UR12e citeturn21view4turn21view5turn21view6turn22view3 |

У K55 есть исторические/вариантные страницы с отличающимися параметрами; для RobCo нельзя объединять старые 1000 кг / magnetic-navigation варианты с текущим K55 на 1200 кг и SLAM. Аналогично у Robotiq старый PE20 на 18 кг/2150 мм нельзя незаметно смешивать с более свежим Production-Ready Palletizer на 21 кг/2200 мм. Версия продукта должна быть полноценным ключом каталога. citeturn13search3turn19search1turn19search9

**Price evidence table**

| Model / evidence | Public price | Тип цены | Что доказуемо входит | Что нельзя считать включенным без quotation | Integration / commissioning evidence | Price confidence |
|---|---:|---|---|---|---|---:|
| **FlashBot Max — RobotLAB** | **starting at $20,000** | Public reseller purchase starting price, US | Exact model; RobotLAB отдельно заявляет US sales/setup/service и что занимается deployment/training | Нельзя из формулировки сделать вывод, что elevator hardware, door integration, onsite labor, freight, taxes и ongoing service уже входят в $20k | RobotLAB говорит, что handles delivery, onsite setup, training, ongoing service, но отдельная числовая integration price отсутствует | **0.86** citeturn22view0 |
| **PUDU CC1 Pro — RobotLAB** | **$24,000** | Public reseller purchase price | Exact CC1 Pro hardware listing | Optional docking/work station, utilities, installation и service contract не доказаны как включенные в $24k | RaaS/lease доступны по quotation; onsite scope необходимо подтверждать | **0.87** citeturn19search15turn18search0 |
| **Robotiq Lean Palletizing — manufacturer** | **starts at $85,000 in Americas** | Manufacturer starting price for workcell | Сам производитель формулирует цену как starting price Lean Palletizing workcell | Exact robot arm, gripper, guarding, conveyor, freight, installation и specific BOM должны быть подтверждены в quote для выбранной конфигурации | Числовая commissioning charge не опубликована; manufacturer позиционирует систему как rapid-install cell | **0.96** citeturn22view7turn19search9 |
| **Robotiq PE20 package for UR20 — Automation Distribution** | **$49,429.69** | Component/package listing — **не total implementation** | Pedestal base, PLC/control box, 2 pallet sensors, status lights, holder/buttons, cable management, box sensor, Material Handling Copilot dongle | Страница прямо говорит **“No Gripper Included”**; UR20 arm также не перечислен в BOM, поэтому RobCo не должен считать эту цифру полной ячейкой | Вариант with vacuum gripper listed at $57,712.50; PowerPick variant $59,493.75; все это нужно хранить как component evidence | **0.93 для component price; 0 для total-cell assumption** citeturn22view2 |
| **UR10e — Robotics Center, authorized distributor** | **$49,000** | Current distributor hardware price | Robot listing; warranty coverage, engineer support и onboarding/setup integration support заявлены продавцом | EOAT, vision, fixtures, safety equipment, cell engineering, commissioning labor, freight/tax не следует автоматически включать | Standard 4–6-week delivery option без priority surcharge; shipping рассчитывается отдельно; listing имеет Backorder status | **0.92** citeturn21view6 |
| **UR10e — Electromate** | **$44,636** | Current distributor hardware listing | Exact UR10e arm listing | Gripper/vision/base/cell/integration не входят из самого факта этой цены | Numeric commissioning cost отсутствует | **0.89**; продавец также пишет, что UR10e теперь UR12e citeturn22view3 |
| **MiR250 — DNC Automation 2026** | **$50,000–70,000** | **Estimate, не official price**, ASEAN market estimate | Только рыночная hardware estimate | Не quotation; не применять как подтвержденную закупочную цену в другом регионе | Источник отдельно оценивает total project примерно 1,5–2× hardware и приводит пример WMS/commissioning, но это **integrator estimate**, не MiR price book | **0.40** citeturn14view1 |
| **Kivnon K05** | **не опубликована** | `quote_required` | — | Hardware, charger, guidance installation, Fleet, commissioning — только quotation | Numeric public evidence не обнаружено в current official product material | **0.98 confidence, что numeric price отсутствует в исследованном official page; 0 по сумме** citeturn13search2 |
| **MiR250 Hook** | **не опубликована** | `quote_required` | — | Нельзя складывать generic MiR250 estimate и generic top-module estimate и называть результат ценой Hook | Проектная цена зависит от carts/hitch/deployment | **0 по сумме** citeturn15search1turn15search4 |
| **Kivnon K55** | **не опубликована** | `quote_required` | — | Нельзя подставлять цену ручного stacker/forklift или другого AGV | Rack/pallet/site integration потенциально существенна и требует quotation | **0 по сумме** citeturn13search3 |
| **Corvus One** | **не опубликована** | `quote_required` / commercial system | Manufacturer подтверждает onsite implementation 1–2 недели и training обычно 1–2 часа | Стоимость hardware/service/software/hosting публично не дана | Vendor заявляет go-live process и ROI <6 months, но это vendor claim, не price evidence | **0 по сумме** citeturn21view0 |

У PUDU сама manufacturer support policy подтверждает наличие lifecycle service; отдельная страница PUDU Care описывает site survey, map creation, performance verification и user training как элементы deployment service package. Однако это **не означает**, что такой пакет уже включен в reseller hardware price. В исследованных публичных материалах годовая стоимость PUDU Care не указана. citeturn17search7turn17search9turn17search11

**Fallback price ranges для calculation engine**

Рекомендую хранить fallback не как единую таблицу «средняя цена класса», а как evidence object со scope и регионом:

| Класс | Разрешенный fallback для MVP | Scope | Default RobCo behavior |
|---|---|---|---|
| AMR | **MiR250 $50k–70k — sourced estimate, ASEAN 2026** | Hardware estimate конкретной модели, не market-wide | Разрешить только с большим warning и `price_confidence≈0.4`; supplier quote всегда выше по приоритету. Источник также дает low-confidence project multiplier 1.5–2× hardware. citeturn14view1 |
| AGV | **null** | K05 | `quote_required`; не рассчитывать headline NPV из выдуманной цены. citeturn13search2 |
| Autonomous tug | **null** | MiR250 Hook | `quote_required`; не выводить цену Hook из цены base AMR. citeturn15search4 |
| Robotic forklift/stacker | **null** | K55 | `quote_required`. citeturn13search3 |
| Indoor delivery | **$20k starting anchor** | FlashBot Max, US reseller | Exact-model anchor; implementation/elevator integration separate unless quote proves otherwise. citeturn22view0 |
| Cleaning | **$24k anchor** | CC1 Pro, US reseller | Hardware purchase anchor; optional workstation and annual service separate. citeturn19search15turn18search0 |
| Inventory drone | **null** | Corvus One | `quote_required`; business case can initially use labor/inventory benefit threshold without pretending to know CAPEX. citeturn21view0 |
| Palletizing cell | **≥$85k** | Lean Palletizing workcell, Americas | Manufacturer starting price; upper bound remains `null`, not invented. citeturn22view7 |
| Cobot/pick-and-place | **$44,636–49,000** | UR10e arm only | Strong hardware anchor, **not complete pick-and-place cell**. citeturn22view3turn21view6 |

Это дает полезный продуктовый принцип: **`null` является корректным значением цены**. Для RobCo `null + quote_required` лучше, чем ложная точность. Даже при хакатонном UX можно построить экономический диапазон с пользовательским assumption, но UI должен явно писать: `User assumption — not market evidence`.


## Hard constraints по классам

Ниже — рекомендуемый pre-filter. Это именно **RobCo decision logic**, выведенный из структуры manufacturer specifications; он не заменяет formal risk assessment или layout simulation.

| Класс | Обязательные inputs | Hard fail / compatibility gates | Что нельзя проверять «по размеру корпуса» |
|---|---|---|---|
| **AMR** | payload, load dimensions/CG, aisle, doorway, route length, slopes, gaps/thresholds, floor state, indoor/outdoor, temperature, human traffic, charging location | Для MiR250: payload >250 кг; рабочий corridor уже допустимого режима; doorway меньше допустимого; slope >5%; требование работы во внешней/мокрой среде против indoor/IP21 условий | 580 мм physical width ≠ 580 мм required aisle. Manufacturer дает 1450 мм default и 850 мм только при специальной minimized/muted configuration. citeturn15search0 |
| **AGV** | carrying payload, towing payload, route topology, guidance technology, station accuracy, charger, traffic crossings | Для K05: carrying >450 кг; towing >1000 кг; отсутствие допустимой magnetic/RFID infrastructure для выбранной current configuration | Корпус 800×800 мм и возможность 360° rotation не доказывают 800-мм безопасный проход: safety field/minimum operational aisle публично не указан. citeturn13search2 |
| **Autonomous tug** | tow mass, cart footprint, wheel resistance, hitch geometry/height, train length, cart brakes/stability, slopes, pickup point, turnaround space | Для MiR250 Hook: cart/train load >500 кг; несовместимый cart pickup; невозможность надежно разместить/распознавать AprilTag; недостаточный swept path | Нельзя использовать aisle constraint base MiR250 как aisle для `Hook + cart`: хвост тележки меняет swept envelope. citeturn15search4turn15search0 |
| **Robotic forklift/stacker** | pallet type, opening orientation, load mass, load dimensions/CG, fork geometry, lift height, rack clearance, aisle, turn radius, floor levelness, overhead clearance | Для current K55: >1200 кг; требуемый lift >1500 мм; pallet incompatible с current standard-fork/open-pallet configuration | 920-мм width не является required aisle. Производитель лишь говорит narrow aisle, без numerical aisle; RobCo должен поставить `layout_validation_required=true`. citeturn13search3 |
| **Indoor delivery robot** | item weight and dimensions, compartment requirement, corridor/door width, threshold, lift cabin/door size, elevator brand/control access, gates, floors, semi-outdoor exposure | Для FlashBot Max: compartment load >10 кг; если использовать reseller total rating — total >20 кг; path <600 мм; multi-floor mission без технически реализуемой elevator integration | “Semi-outdoor” у PUDU относится к semi-open building environments; RobCo не должен автоматически считать модель rain/outdoor-rated без IP/weather evidence. citeturn17search14turn22view0 |
| **Autonomous cleaning** | floor types, total cleanable area, obstacles, min path, thresholds, slopes, cleaning mode, water/refill/drain infrastructure, carpet areas, required unattended hours | Для CC1 Pro: path <700 мм; в cleaning mode threshold >8 мм или slope >3°; требование fully autonomous refill/drain без optional workstation/utilities | Нельзя использовать spot-cleaning 1500–3000 м²/ч как throughput полного покрытия; для full-coverage базовый rated range — 700–1000 м²/ч. citeturn18search0turn18search2 |
| **Inspection/inventory drone** | rack geometry, aisle geometry, ceiling height, labels/barcodes, shrink wrap/visibility, required counting type, shift rules, landing-pad location, power, Ethernet/WMS | Corvus One не должен автоматически пройти outdoor inspection use case; неподдерживаемый inventory pattern или невозможность безопасного flight deployment требует vendor validation; cold environment ниже documented Cold Chain capability также fail | Public minimum aisle, drone dimensions, speed и flight time не опубликованы — **RobCo обязан вернуть unknown, а не вычислить clearance из изображения**. Corvus требует при deployment проверить power drop и Ethernet access. citeturn21view0 |
| **Palletizing cell** | case weight/dimensions/material, pallet size, max stack height, patterns/SKUs, conveyor location/height, required picks/min, footprint, product grippability, safety zoning | Для current Robotiq production-ready cell: payload >21 кг; pallet height >2200 мм; required nominal throughput >13 picks/min; доступное место меньше documented cell footprint | Rated 13 picks/min — ceiling/reference, не обещание для любой SKU mix. Vacuum pickup, slipsheets, double-pick и conveyor timing могут понизить effective throughput. citeturn19search9turn20view0 |
| **Cobot / pick-and-place** | part mass + EOAT/cables, reach, pose set, cycle time, accuracy/repeatability, mounting, IP/temp, vision, guarding/risk level, PLC/protocol | Для UR10e: flange payload requirement >12,5 кг; reach >1300 мм; environmental requirements beyond IP54/0–50 °C; cell cannot be made safe under required speed/force | `payload = part only` — опасная модель данных; для проверки нужно учитывать весь moving payload at flange. Также speed variant сейчас требует resolution: official SW5_22 manual и distributor listing расходятся. citeturn21view4turn21view6 |

Два важных правила должны быть глобальными. Во-первых, любой hard parameter со значением `unknown` должен давать не `PASS`, а `CONDITIONAL_PASS / VALIDATION_REQUIRED`. Во-вторых, manufacturer-rated maximum throughput нельзя превращать в operating throughput без derating. Это особенно видно на cleaning и palletizing: PUDU отдельно различает full-coverage и spot rates, а Robotiq пишет «up to 13 picks/min». citeturn18search0turn19search9


## Inputs для calculation engines и рекомендуемые формулы

RobCo фактически нужны четыре взаимосвязанных движка: **compatibility engine → sizing engine → economics engine → explanation/confidence engine**.

**Site/process inputs.** Минимальная входная модель должна включать `object_type`, `process_type`, `country`, `currency`, `operating_days_per_year`, `shifts_per_day`, `shift_hours`, `peak_factor`, `required_moves_per_hour` или другой process-specific demand. Для мобильных роботов нужны loaded/empty route distances, pickup/drop times, waits, pedestrian/forklift traffic, aisle widths, door widths, slopes, thresholds, floor condition, elevator/gate interfaces и charging locations. Наличие таких constraints напрямую следует из manufacturer data: MiR, например, отдельно нормирует corridor, doorway, incline и floor environment, а FlashBot Max отдельно — path clearance и elevator integration. citeturn15search0turn17search14

Для forklift/stacker branch обязательны `pallet_type`, `pallet_dimensions`, `pallet_entry_direction`, `load_weight`, `load_center_or_CG`, `required_lift_height`, rack geometry и overhead clearance. K55 показывает, почему `payload_kg` одного недостаточно: current configuration одновременно задает 1200 кг, 1500 мм lift и standard forks/open pallet geometry. citeturn13search3

Для cleaning branch нужны `cleanable_area_m2`, `floor_mix`, `required_frequency`, `obstacle_density`, `traffic_hours`, `water_points`, `drain_points`, `cleaning_mode`, `unattended_requirement`. CC1 Pro дает хорошую основу для такого engine: full-coverage 700–1000 м²/ч, разные runtimes по mode, 15-L clean/dirty tanks и optional automated refill/drain station. citeturn18search0

Для palletizing/cobot branch нужны `case_weight`, `case_dimensions`, `cases_per_minute`, `SKU_count`, `pallet_dimensions`, `stack_height`, `pattern`, conveyor parameters, `EOAT_weight`, required reach и safety-zone assumptions. Robotiq current cell дает 21 кг, 13 picks/min и 2200 мм как верхние feasibility gates; UR10e дает 12,5 кг payload и 1300 мм reach для generic manipulation branch. citeturn19search9turn21view4

**Sizing mobile robots.** Для первого MVP достаточно аналитической cycle-time модели:

```text
cycle_time_sec =
    loaded_distance_m / effective_loaded_speed_mps
  + empty_distance_m / effective_empty_speed_mps
  + pickup_time_sec
  + dropoff_time_sec
  + expected_wait_sec
  + intersection_and_door_delay_sec
```

```text
effective_cycles_per_hour =
    3600 / cycle_time_sec
    × availability
    × utilization
```

```text
capacity_per_robot_per_hour =
    effective_cycles_per_hour
    × units_per_cycle
```

```text
robot_count =
    ceil(
      peak_required_units_per_hour
      / capacity_per_robot_per_hour
    )
```

`effective_*_speed` не должна по умолчанию равняться datasheet max speed. Datasheet speed следует хранить как hard upper bound. Например, MiR250 max = 2 м/с, а K05 max = 0,7 м/с; фактическое значение должно приходить из pilot, simulation или configurable derating profile. citeturn15search0turn13search2

После throughput-sizing нужен отдельный battery/charging feasibility pass. Для MiR250 можно использовать официальные runtime и charging-ratio данные; для K05/K55 runtime hours публично не даны, поэтому RobCo не должен моделировать full-shift autonomy из одного факта наличия автоматической зарядки. citeturn15search0turn13search2turn13search3

**Sizing cleaning**

```text
effective_cleaning_rate_m2h =
    vendor_full_coverage_rate_m2h
    × traffic_factor
    × coverage_factor
    × availability
```

```text
cleaners_required =
    ceil(
      required_cleaning_area_m2_per_shift
      / (effective_cleaning_rate_m2h × productive_hours_per_shift)
    )
```

Для CC1 Pro engine default input должен быть full-coverage **700–1000 м²/ч**, а 1500–3000 м²/ч разрешать только для `spot_cleaning` scenario. citeturn18search0

**Sizing palletizing**

```text
effective_picks_per_min =
    vendor_max_picks_per_min
    × OEE
    × product_mix_factor
    × feed_availability
```

```text
cells_required =
    ceil(required_picks_per_min / effective_picks_per_min)
```

Для Robotiq `vendor_max_picks_per_min=13`; это верхнее published reference, а не гарантированное значение `effective_picks_per_min`. citeturn19search9

Для Corvus One я бы **не создавал synthetic locations/hour**. Поскольку производитель публично не дает стандартную flight speed/battery/scan-rate спецификацию, sizing should accept `pilot_verified_locations_per_hour` либо vendor simulation. Customer references вроде «20× faster» полезны для prior/business-case narrative, но не являются универсальной capacity constant. citeturn21view0

**CAPEX engine**

```text
CAPEX_initial =
    robot_hardware
  + required_top_modules_or_EOAT
  + chargers_docks_workstations
  + fleet_or_control_software_setup
  + integration
  + site_modifications
  + safety_equipment
  + commissioning
  + training
  + freight_duties_taxes
```

Каждый term должен иметь `price_basis`, например:

```text
exact_public
official_quote
authorized_distributor_quote
sourced_estimate
user_assumption
unknown
```

Это предотвращает две самые частые ошибки ТЭО: стоимость arm выдавать за стоимость robotic cell и hardware price — за total implementation. Public evidence Robotiq хорошо демонстрирует проблему: $49,429.69 PE20 package explicitly excludes the gripper, тогда как manufacturer-level Lean Palletizing workcell starts at $85k. citeturn22view2turn22view7

**OPEX engine**

```text
OPEX_annual =
    maintenance_contract
  + SaaS_or_fleet_subscription
  + electricity
  + consumables
  + scheduled_spares
  + battery_replacement_amortization
  + network_connectivity
  + residual_operator_labor
```

Не стоит заполнять отсутствующие maintenance-contract цифры процентом от CAPEX без отдельного evidence или пользовательского assumption. В исследованных public sources PUDU подтверждает lifecycle service и warranty/support mechanisms, MiR — fleet/service ecosystem, но точные annual service fees для выбранных конфигураций не опубликованы в изученных материалах. citeturn17search3turn17search11turn15search5

Для cleaning отдельно нужны water, detergent, brushes/pads/squeegee, waste bags и manual intervention. Для cobot — EOAT wear, vision maintenance и safety inspection. Для drone — software/service/hosting arrangement. Если суммы неизвестны, они должны оставаться `null`, а не «5% от CAPEX» без provenance.

**Savings, payback и NPV**

```text
annual_gross_benefit =
    avoided_labor_cost
  + avoided_overtime
  + avoided_equipment_cost
  + documented_error_or_inventory_loss_reduction
  + incremental_contribution_margin
```

```text
annual_net_cash_benefit =
    annual_gross_benefit
  - annual_robot_OPEX
```

```text
simple_payback_years =
    CAPEX_initial / annual_net_cash_benefit
```

```text
NPV =
    -CAPEX_initial
    + Σ[t=1..T] (
        net_cash_flow_t / (1 + discount_rate)^t
      )
    + residual_value_T / (1 + discount_rate)^T
```

RobCo должен защищаться от double counting: нельзя одновременно считать ту же экономию как `FTE avoided`, `labor hours saved` и `throughput benefit`, если дополнительный throughput не создает отдельную contribution margin.

Особенно полезно возвращать минимум три сценария: `evidence_low`, `base`, `evidence_high`. Если верхней границы нет — как у Robotiq starting-at price — нельзя изобретать ее ради симметрии. Если вся цена `quote_required`, economic engine должен честно возвращать `CAPEX evidence incomplete`.

**Минимальный calculation input schema**

| Group | Ключевые поля |
|---|---|
| Site | `country`, `currency`, `indoor_outdoor`, `temperature_min/max`, `humidity`, `floor_condition`, `aisle_min_mm`, `door_min_mm`, `slope_max_pct`, `threshold_max_mm`, `pedestrian_density`, `forklift_traffic`, `elevators`, `gates`, `network`, `utilities` |
| Process | `process_type`, `load_type`, `payload_kg`, `load_dimensions`, `pallet_type`, `moves_per_hour`, `peak_moves_per_hour`, `distance_loaded_m`, `distance_empty_m`, `pickup_sec`, `dropoff_sec`, `operating_hours` |
| Cleaning | `area_m2`, `frequency`, `floor_types`, `cleaning_mode`, `traffic_factor`, `water_access`, `drain_access` |
| Palletizing | `case_weight_kg`, `case_dimensions`, `required_picks_min`, `pallet_size`, `max_stack_mm`, `SKU_count`, `conveyor_geometry`, `EOAT` |
| Inventory drone | `locations`, `rack_height`, `aisle_geometry`, `barcode_types`, `shrink_wrap`, `count_frequency`, `pilot_locations_h` |
| Economics | `hardware_price`, `price_basis`, `integration`, `site_modification`, `software`, `commissioning`, `maintenance`, `energy_price`, `consumables`, `labor_cost_loaded`, `discount_rate`, `project_horizon`, `tax`, `freight` |
| Evidence | `source_type`, `source_url`, `publication_date`, `accessed_at`, `region`, `currency`, `is_estimate`, `confidence`, `model_version`, `evidence_notes` |


## JSON-compatible records

Ниже — seed dataset для MVP. `null` означает именно «не подтверждено публичным evidence», а не ноль. `Sxx` ссылаются на Source Appendix далее.

```json
{
  "catalog_version": "robco-mvp-2026-09-08",
  "price_policy": {
    "allowed_basis": [
      "official_public",
      "authorized_distributor_public",
      "reseller_public",
      "sourced_estimate",
      "quote_required",
      "user_assumption"
    ],
    "rule": "Do not convert quote_required or null into a numeric price without explicit evidence or user assumption."
  },
  "records": [
    {
      "id": "R01",
      "solution_class": "AMR",
      "manufacturer": "Mobile Industrial Robots",
      "model": "MiR250",
      "use_cases": [
        "intralogistics",
        "material_transport",
        "warehouse_transport",
        "service_internal_transport"
      ],
      "payload": {
        "max_kg": 250
      },
      "dimensions_mm": {
        "length": 800,
        "width": 580,
        "height": 300
      },
      "speed_mps": {
        "max": 2.0
      },
      "autonomy": {
        "runtime_h_max_payload": 13.0,
        "runtime_h_no_load": 17.5,
        "battery_type": "lithium-ion",
        "charge_ratio_runtime_to_charge": 16,
        "charge_example": "10 min charge -> up to 2 h 40 min runtime at maximum payload"
      },
      "mobility_constraints": {
        "corridor_default_mm": 1450,
        "corridor_minimized_mm": 850,
        "doorway_default_mm": 1500,
        "doorway_minimized_mm": 800,
        "gap_max_mm": 20,
        "incline_max_pct": 5
      },
      "environment": {
        "indoor": true,
        "outdoor": false,
        "ip_rating": "IP21",
        "temperature_c_min": 5,
        "temperature_c_max": 40
      },
      "navigation": "autonomous MiR platform with safety laser scanners and 3D sensing",
      "safety": {
        "safety_functions": 12,
        "standards": [
          "ISO 3691-4 with manufacturer-listed exceptions",
          "ISO 13849-1",
          "ISO 13850",
          "ISO 12100",
          "RIA R15.08-1"
        ]
      },
      "integrations": [
        "MiR Fleet",
        "REST API",
        "ERP",
        "WMS",
        "MES"
      ],
      "throughput": {
        "vendor_moves_per_hour": null,
        "sizing_method": "route cycle-time model"
      },
      "price": {
        "public_official": null,
        "fallback_usd_min": 50000,
        "fallback_usd_max": 70000,
        "basis": "sourced_estimate",
        "region": "ASEAN",
        "year": 2026,
        "note": "Not an official MiR quote"
      },
      "integration_commissioning_cost": {
        "amount": null,
        "secondary_estimate_project_multiplier": "1.5-2.0x hardware",
        "use_by_default": false
      },
      "service_opex_public_amount": null,
      "geography": "global distributor ecosystem; local availability requires confirmation",
      "confidence": 0.96,
      "sources": ["S01", "S02", "S21"]
    },
    {
      "id": "R02",
      "solution_class": "AGV",
      "manufacturer": "Kivnon",
      "model": "K05 Twister",
      "use_cases": [
        "intralogistics",
        "cart_transport",
        "load_transport",
        "towing"
      ],
      "payload": {
        "onboard_max_kg": 450,
        "towing_max_kg": 1000
      },
      "dimensions_mm": {
        "length": 800,
        "width": 800,
        "height": 280
      },
      "speed_mps": {
        "max": 0.7
      },
      "autonomy": {
        "battery_type": "LiFePO4",
        "runtime_h": null,
        "automatic_charging": true,
        "charging_method": "brushes and floor pads"
      },
      "mobility_constraints": {
        "minimum_operational_aisle_mm": null,
        "bidirectional": true,
        "rotation_360_deg": true,
        "lift_stroke_mm": 60
      },
      "environment": {
        "indoor_industrial": true
      },
      "navigation": "magnetic guidance with RFID reading",
      "safety": [
        "front laser scanner",
        "safety PLC",
        "emergency stop"
      ],
      "integrations": [
        "VDA 5050",
        "Wi-Fi",
        "OPC-UA",
        "UDP",
        "TCP",
        "Kivnon Fleet Manager"
      ],
      "throughput": {
        "vendor_moves_per_hour": null,
        "stopping_accuracy_mm": 10
      },
      "price": {
        "amount": null,
        "basis": "quote_required"
      },
      "integration_commissioning_cost": null,
      "service_opex_public_amount": null,
      "confidence": 0.92,
      "sources": ["S03"]
    },
    {
      "id": "R03",
      "solution_class": "autonomous_tug",
      "manufacturer": "Mobile Industrial Robots",
      "model": "MiR250 Hook",
      "use_cases": [
        "autonomous_cart_pickup",
        "cart_towing",
        "internal_logistics"
      ],
      "payload": {
        "towing_max_kg": 500
      },
      "dimensions_mm": null,
      "speed_mps": {
        "max": 2.0
      },
      "autonomy": {
        "runtime_h": 10
      },
      "mobility_constraints": {
        "minimum_operational_aisle_mm": null,
        "requires_cart_swept_path_validation": true
      },
      "environment": {
        "indoor": true
      },
      "navigation": "MiR base navigation plus AprilTag cart identification",
      "cart_interface": {
        "april_tag_required": true,
        "existing_carts_potentially_reusable": true
      },
      "safety": "MiR base safety architecture plus towing application risk assessment",
      "integrations": [
        "MiR Fleet",
        "REST API",
        "ERP",
        "WMS",
        "MES"
      ],
      "throughput": {
        "vendor_trips_per_hour": null
      },
      "price": {
        "amount": null,
        "basis": "quote_required"
      },
      "integration_commissioning_cost": null,
      "service_opex_public_amount": null,
      "confidence": 0.91,
      "sources": ["S01", "S02"]
    },
    {
      "id": "R04",
      "solution_class": "robotic_forklift_stacker",
      "manufacturer": "Kivnon",
      "model": "K55",
      "use_cases": [
        "autonomous_pallet_transport",
        "pallet_stacking"
      ],
      "payload": {
        "max_kg": 1200
      },
      "dimensions_mm": {
        "length": 1920,
        "width": 920,
        "height": 2340
      },
      "speed_mps": {
        "max": 1.0
      },
      "lift": {
        "max_height_mm": 1500,
        "fork_type": "standard forks",
        "pallet_type_evidence": "open pallets",
        "entry": "front"
      },
      "autonomy": {
        "battery_count": 2,
        "battery_type": "lithium",
        "runtime_h": null,
        "charging": "in-line/trickle charging and built-in connector"
      },
      "mobility_constraints": {
        "minimum_operational_aisle_mm": null,
        "requires_turning_envelope_validation": true
      },
      "navigation": "SLAM",
      "safety": [
        "360-degree laser coverage",
        "left and right safety scanners"
      ],
      "integrations": [
        "VDA 5050",
        "fleet management systems"
      ],
      "throughput": {
        "vendor_pallets_per_hour": null
      },
      "price": {
        "amount": null,
        "basis": "quote_required"
      },
      "integration_commissioning_cost": null,
      "service_opex_public_amount": null,
      "confidence": 0.92,
      "sources": ["S04"]
    },
    {
      "id": "R05",
      "solution_class": "indoor_delivery_robot",
      "manufacturer": "PUDU Robotics",
      "model": "FlashBot Max",
      "use_cases": [
        "room_delivery",
        "package_delivery",
        "multi-floor_delivery",
        "clinic_service_delivery"
      ],
      "payload": {
        "per_compartment_max_kg": 10,
        "total_max_kg_reseller_evidence": 20
      },
      "compartments": {
        "min": 2,
        "max": 4,
        "secure_access": [
          "password",
          "phone",
          "NFC"
        ]
      },
      "dimensions_mm": {
        "length": 538,
        "width": 534,
        "height": 1052
      },
      "weight_kg": 60,
      "speed_mps": {
        "min": 0.5,
        "max": 1.2
      },
      "autonomy": {
        "runtime_h": 9,
        "charge_h": 4,
        "automatic_charging": true
      },
      "mobility_constraints": {
        "minimum_path_clearance_mm": 600
      },
      "environment": {
        "indoor": true,
        "semi_open_building": true,
        "weatherproof_outdoor_confirmed": false
      },
      "navigation": "PUDU VSLAM+ with LiDAR/3D sensing",
      "safety": "3D multi-sensor obstacle avoidance",
      "integrations": [
        "PUDU Link",
        "PUDU Open Platform",
        "e-gate",
        "turnstile",
        "KONE elevator",
        "OTIS elevator"
      ],
      "throughput": {
        "orders_per_trip_max_by_compartments": 4,
        "deliveries_per_hour": null
      },
      "price": {
        "usd": 20000,
        "basis": "reseller_public_starting_price",
        "region": "US"
      },
      "integration_commissioning_cost": null,
      "service_opex_public_amount": null,
      "confidence": 0.93,
      "sources": ["S05", "S06", "S16"]
    },
    {
      "id": "R06",
      "solution_class": "autonomous_cleaning_robot",
      "manufacturer": "PUDU Robotics",
      "model": "CC1 Pro",
      "use_cases": [
        "sweeping",
        "scrubbing",
        "vacuuming",
        "carpet_vacuuming",
        "dust_mopping"
      ],
      "dimensions_mm": {
        "length": 629,
        "width": 552,
        "height": 695
      },
      "weight_kg": 75,
      "speed_mps": {
        "min": 0.2,
        "max": 1.2
      },
      "autonomy": {
        "battery_capacity_ah": 50,
        "charge_h": 3,
        "runtime_scrubbing_h": 5,
        "runtime_sweep_vacuum_h": 5,
        "runtime_carpet_vacuum_h": 4,
        "runtime_silent_mop_h": 9
      },
      "mobility_constraints": {
        "minimum_path_clearance_mm": 700,
        "threshold_cleaning_mode_mm": 8,
        "threshold_non_cleaning_mode_mm": 20,
        "slope_cleaning_deg": 3,
        "slope_non_cleaning_deg": 8
      },
      "environment": {
        "ip_rating": "IPX4"
      },
      "navigation": "LiDAR plus visual fusion positioning",
      "safety": "AI-driven static and moving obstacle perception",
      "integrations": [
        "PUDU Link",
        "optional e-gate",
        "optional elevator control"
      ],
      "cleaning": {
        "full_coverage_m2h_min": 700,
        "full_coverage_m2h_max": 1000,
        "spot_m2h_min": 1500,
        "spot_m2h_max": 3000,
        "cleaning_width_mm": 500,
        "clean_water_l": 15,
        "dirty_water_l": 15
      },
      "docking": {
        "auto_charge": true,
        "auto_water_refill_drain": true,
        "optional_workstation_required": true
      },
      "price": {
        "usd": 24000,
        "basis": "reseller_public_purchase_price",
        "region": "US"
      },
      "integration_commissioning_cost": null,
      "service_opex_public_amount": null,
      "confidence": 0.96,
      "sources": ["S07", "S08", "S17"]
    },
    {
      "id": "R07",
      "solution_class": "inspection_inventory_drone",
      "manufacturer": "Corvus Robotics",
      "model": "Corvus One",
      "use_cases": [
        "pallet_reserve_cycle_counting",
        "bulk_inventory_counting",
        "single_deep_case_counting"
      ],
      "payload": null,
      "dimensions_mm": null,
      "speed_mps": null,
      "autonomy": {
        "flight_runtime_min": null,
        "charge_time_min": null,
        "autonomous_flight": true
      },
      "mobility_constraints": {
        "minimum_aisle_mm": null,
        "vendor_site_validation_required": true
      },
      "environment": {
        "indoor_warehouse": true,
        "cold_chain_variant_min_f": -20
      },
      "navigation": {
        "type": "autonomous 3D flight",
        "beacons_required": false,
        "reflectors_required": false,
        "navigation_stickers_required": false,
        "onboard_cameras": 14
      },
      "safety": "omnidirectional camera-based collision prevention",
      "integrations": [
        "WMS API",
        "data upload",
        "standalone",
        "SAP",
        "Manhattan",
        "Blue Yonder",
        "Oracle"
      ],
      "data_storage": "on-premise inventory data supported",
      "throughput": {
        "universal_locations_per_hour": null,
        "customer_reference_annual_full_counts": "10-12 vs 2-4",
        "customer_reference_speedup": "up to 20x in MSI case"
      },
      "deployment": {
        "onsite_weeks_min": 1,
        "onsite_weeks_max": 2,
        "training_hours_typical": "1-2"
      },
      "price": {
        "amount": null,
        "basis": "quote_required"
      },
      "service_opex_public_amount": null,
      "geography_evidence": "customers across North America; designed/manufactured/tested in Mountain View, California",
      "confidence": 0.86,
      "sources": ["S09"]
    },
    {
      "id": "R08",
      "solution_class": "palletizing_robot_cell",
      "manufacturer": "Robotiq",
      "model": "Production-Ready Palletizer / Lean Palletizing",
      "use_cases": [
        "case_palletizing"
      ],
      "payload": {
        "max_kg": 21
      },
      "cell_footprint": {
        "eu_gt_mm": {
          "length": 3700,
          "width": 3600
        },
        "us_gt_in": {
          "length": 163,
          "width": 142
        }
      },
      "power": {
        "battery": false
      },
      "palletizing": {
        "throughput_picks_min_max": 13,
        "pallet_height_mm_max": 2200,
        "sku_and_patterns": "unlimited per manufacturer datasheet"
      },
      "safety": "integrated safeguarding in production-ready cell",
      "integrations": {
        "cell_software": true,
        "upstream_conveyor_support": true,
        "public_generic_wms_mes_api_evidence": null
      },
      "price": {
        "usd_min": 85000,
        "usd_max": null,
        "basis": "manufacturer_public_starting_workcell_price",
        "region": "Americas"
      },
      "integration_commissioning_cost": null,
      "service_opex_public_amount": null,
      "confidence": 0.95,
      "sources": ["S10", "S11"]
    },
    {
      "id": "R09",
      "solution_class": "cobot_pick_and_place",
      "manufacturer": "Universal Robots",
      "model": "UR10e",
      "lifecycle": {
        "status": "transition",
        "successor": "UR12e",
        "new_procurement_requires_confirmation": true
      },
      "use_cases": [
        "pick_and_place",
        "machine_tending",
        "packaging",
        "assembly"
      ],
      "payload": {
        "max_kg": 12.5
      },
      "reach_mm": 1300,
      "footprint_mm": {
        "diameter": 190
      },
      "arm_weight_kg": 33.3,
      "speed_mps": {
        "official_sw5_22_tool_approx": 1.0,
        "current_distributor_max_tcp": 4.0,
        "evidence_status": "conflict_requires_variant_resolution"
      },
      "power": {
        "typical_program_w": 350,
        "manual_average_w": 615
      },
      "environment": {
        "temperature_c_min": 0,
        "temperature_c_max": 50,
        "performance_derating_above_c": 35,
        "ip_rating": "IP54"
      },
      "safety": {
        "functions": 17,
        "performance_level": "PLd Category 3",
        "standard": "EN ISO 13849-1"
      },
      "integrations": [
        "MODBUS TCP",
        "EtherNet/IP",
        "PROFINET",
        "digital I/O",
        "analog I/O"
      ],
      "throughput": {
        "universal_picks_per_min": null
      },
      "price": {
        "usd_public_min": 44636,
        "usd_public_max": 49000,
        "basis": "current_distributor_hardware_listings"
      },
      "integration_commissioning_cost": null,
      "service_opex_public_amount": null,
      "confidence": 0.88,
      "sources": ["S12", "S13", "S18", "S19"]
    }
  ]
}
```

На уровне production schema я дополнительно разделил бы `record_confidence` на `spec_confidence`, `price_confidence`, `availability_confidence` и `integration_confidence`. У Corvus, например, confidence технической концепции высокий, но confidence для числового fleet sizing ниже из-за отсутствующих публичных speed/runtime данных; у UR10e обратная ситуация — много технических и ценовых данных, но есть lifecycle ambiguity. citeturn21view0turn22view3


## Unresolved questions и Sources appendix

**Unresolved questions**

| Вопрос | Почему блокирует точное ТЭО | Что должен сделать RobCo |
|---|---|---|
| **В какой стране будет закупка?** | Все подтвержденные public prices привязаны к определенному продавцу/региону: Robotiq прямо ограничивает starting price Americas, MiR estimate относится к ASEAN, PUDU/UR listings — преимущественно US/Canada. citeturn22view7turn14view1turn22view0turn21view6 | `country` и `currency` — mandatory economics inputs; FX/tax/import нельзя silently переносить между регионами. |
| **Какова точная цена MiR250, MiR250 Hook, K05, K55 и Corvus?** | По исследованным official sources нет public numeric quotation. citeturn15search0turn15search4turn13search2turn13search3turn21view0 | Запрос quotation; до него выводить sensitivity или `NPV unavailable with evidence-grade pricing`. |
| **Каковы aisle/turning envelopes K05, K55 и Hook с реальным грузом?** | Vendor body dimensions недостаточны для safety feasibility. citeturn13search2turn13search3turn15search4 | CAD/layout validation, vendor simulator или site pilot; field `minimum_operational_aisle=null` до подтверждения. |
| **Что точно входит в $20k FlashBot и $24k CC1 Pro?** | Reseller говорит, что занимается setup/training/service, но не связывает весь этот scope однозначно с базовой hardware price. citeturn22view0turn19search15 | Separate BOM: robot, charger/dock, elevator kit, onsite integration, training, annual service. |
| **Сколько стоят elevator/door integrations?** | Они могут быть существенной частью service-object CAPEX; PUDU подтверждает cloud/hardware elevator options, но не их public price. citeturn17search14 | Quote per lift/gate; хранить как `site_integration_capex`, а не robot hardware. |
| **Каков annual service/OPEX?** | Manufacturer service programs существуют, но числовые annual fees по выбранным моделям не опубликованы в изученных материалах. citeturn17search5turn17search11 | Не использовать arbitrary %CAPEX без маркировки `user_assumption`. |
| **Каков реальный throughput Corvus?** | Customer case-study ratios не дают универсального locations/hour. citeturn21view0 | Vendor simulation/pilot → `verified_locations_per_hour`. |
| **Какой exact Robotiq BOM соответствует starting $85k?** | Manufacturer public price является starting workcell price, а component listings показывают, насколько сильно package composition меняет стоимость. citeturn22view7turn22view2 | Exact configuration quotation с arm, gripper, guarding, conveyor interface, installation. |
| **UR10e или UR12e?** | Текущие продавцы прямо обозначают UR12e как successor; есть также конфликт по max TCP speed между official UR10e SW5_22 manual и distributor listing. citeturn21view4turn21view6turn22view3 | Для нового проекта запросить UR12e quote; UR10e сохранить как historical/public-price anchor, но не silently substitute. |
| **Какой utilization/OEE брать?** | Ни datasheet max speed, ни rated picks/min не являются фактической производительностью площадки. citeturn15search0turn19search9 | Pilot/simulation; до этого показывать sensitivity по utilization/traffic/OEE. |

**Sources appendix.** Для product pages без указанной даты публикации ниже дана дата проверки — **2026-09-08**.

| ID | Source / type | Date | URL |
|---|---|---|---|
| **S01** | Mobile Industrial Robots — MiR250 Specifications; **официальная product specification** | publication date не указана; checked 2026-09-08 | https://mobile-industrial-robots.com/products/robots/mir250/specifications citeturn15search0 |
| **S02** | Mobile Industrial Robots — MiR250 Hook; **официальная product page** | checked 2026-09-08 | https://mobile-industrial-robots.com/da/produkter/applikationer/mir250-hook citeturn15search4 |
| **S03** | Kivnon — K05 Twister; **официальная product page/specs** | checked 2026-09-08 | https://www.kivnon.com/en-uk/k05-model/ citeturn13search2 |
| **S04** | Kivnon — K55; **официальная product page/specs** | checked 2026-09-08 | https://www.kivnon.com/en-uk/k55/ citeturn13search3 |
| **S05** | PUDU Robotics — FlashBot Max; **официальная product page** | checked 2026-09-08 | https://www.pudurobotics.com/en/products/flashbot-new citeturn17search14 |
| **S06** | PUDU Open Platform; **официальная developer/integration platform** | checked 2026-09-08 | https://www.pudurobotics.com/en/open-platform citeturn17search2 |
| **S07** | PUDU Robotics — CC1 Pro; **официальная product specification** | checked 2026-09-08 | https://www.pudurobotics.com/en/products/cc1-pro citeturn18search0 |
| **S08** | PUDU CC1 Pro Korean product page; **официальная specification с threshold/slope/IP details** | checked 2026-09-08 | https://www.pudurobotics.com/kr/products/cc1-pro citeturn18search2 |
| **S09** | Corvus Robotics — Corvus One; **официальная product/deployment/case-study page** | checked 2026-09-08 | https://www.corvus-robotics.com/corvus-one citeturn21view0 |
| **S10** | Robotiq Production-Ready Palletizer datasheet; **официальный PDF datasheet** | current PDF; checked 2026-09-08 | https://robotiq.com/hubfs/PAL_Product_Sheet_EN_Recto_Verso_WEB.pdf citeturn19search9turn20view0 |
| **S11** | Robotiq Lean Palletizing; **официальная solution/pricing page** | checked 2026-09-08 | https://robotiq.com/solutions/palletizing citeturn22view7turn22view8 |
| **S12** | Universal Robots — UR10e Technical Specifications, SW5_22; **официальный manual/specification** | checked 2026-09-08 | https://www.universal-robots.com/manuals/EN/HTML/SW5_22/Content/prod-usr-man/complianceUR10e/H_g5_sections/appendix_g5/tech_spec_sheet.htm citeturn21view4 |
| **S13** | Universal Robots product platform; **официальная integration/safety page** | checked 2026-09-08 | https://www.universal-robots.com/products/ citeturn21view5 |
| **S14** | MiR Fleet; **официальная software/integration page** | checked 2026-09-08 | https://mobile-industrial-robots.com/products/software/mir-fleet citeturn15search5turn15search2 |
| **S15** | PUDU Support / lifecycle service; **официальная service page** | checked 2026-09-08 | https://www.pudurobotics.com/en/support citeturn17search11 |
| **S16** | RobotLAB — FlashBot Max; **commercial reseller/integrator price listing** | checked 2026-09-08 | https://www.robotlab.com/store/pudu-flashbot-max/ citeturn22view0 |
| **S17** | RobotLAB — PUDU CC1 Pro; **commercial reseller/integrator price listing** | checked 2026-09-08 | https://www.robotlab.com/store/pudu-cc1-pro-robot/ citeturn19search15 |
| **S18** | Robotics Center — UR10e; **authorized distributor public price listing** | checked 2026-09-08 | https://www.roboticscenter.ai/store/product/universal-robots-ur10e citeturn21view6 |
| **S19** | Electromate — UR10e; **industrial distributor public price listing** | checked 2026-09-08 | https://www.electromate.com/ur10e-robot/ citeturn22view3 |
| **S20** | Automation Distribution — Robotiq PE20 for UR20; **industrial distributor component-price evidence** | checked 2026-09-08 | https://automationdistribution.com/robotiq-palletizing-solution-pe-series-for-ur20-sol-pal-ur-pe20/ citeturn22view2 |
| **S21** | DNC Automation — MiR Product Guide; **integrator market estimate, secondary source** | 2026-03-28 | https://www.dnc-automation.com/mir-mobile-robot/ citeturn14view1 |
| **S22** | Robotiq PE20 launch page; **manufacturer product page for older/parallel PE20 configuration** | 2023-08-29 | https://palletizing.robotiq.com/pe20-launch-landing-page citeturn19search1 |
| **S23** | PUDU Care service agreement; **официальные deployment/service terms** | checked 2026-09-08 | https://www.pudurobotics.com/en/pudu-care/package-basic-terms citeturn17search7 |

Итоговая архитектурная рекомендация для RobCo: **не хранить одну `price` и одну `payload` на модель**. Для надежного ТЭО catalog entity должна содержать versioned technical constraints, отдельные price evidences с `scope/region/date`, отдельный integration BOM, lifecycle status и per-field confidence. Именно это позволяет системе объяснить не только «почему выбран MiR250 / K55 / FlashBot / CC1 Pro», но и более важное — **какие факты доказаны, какие являются estimate, какие еще требуют quotation или site validation, и насколько это влияет на CAPEX, количество оборудования, payback и NPV**. Публичные материалы рассмотренных производителей показывают, что без такого provenance layer технически правдоподобный каталог очень легко превращается в экономически недостоверный. citeturn15search0turn13search3turn22view0turn18search0turn21view0turn22view7