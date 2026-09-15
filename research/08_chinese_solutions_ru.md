# Китайский procurement-layer для RobCo: доказательный каталог роботизированных решений с фокусом на российский рынок

## Executive summary и методика отбора

Исследование показывает, что отдельный китайский procurement-layer для RobCo имеет практический смысл, но его нельзя строить как каталог «дешёвых аналогов западных роботов». Наиболее зрелые китайские поставщики уже представляют собой полноценные робототехнические платформы с собственными WES/RCS/FMS, промышленными кейсами, международными офисами и тысячами установок. Geek+, Quicktron, HIKROBOT, HAI Robotics, VisionNav, SEER Robotics и Multiway формируют сильный слой mobile robotics; PUDU, KEENON и Gausium — service robotics; ESTUN, JAKA, AUBO и Elite Robots — fixed robotics; DJI Enterprise остаётся технически очень сильным кандидатом для автономной инспекции, но имеет существенно более высокий procurement-риск для РФ. citeturn1search0turn1search2turn12search1turn14search0turn22search0turn22search3

Для российского пользователя ситуация неоднородна. У PUDU есть российский официальный дистрибьютор с заявленными локальным складом запчастей, внедрением и поддержкой; у Gausium — официальный дистрибьютор, сервис, обучение и опубликованное свидетельство EAC; у ESTUN, JAKA и AUBO обнаружены российские официальные дистрибьюторы/представители; Nissa Engineering публично работает в России с Geek+ и является официальным партнёром Quicktron; HIKROBOT предлагается несколькими российскими промышленными поставщиками. citeturn8search1turn8search0turn9search7turn9search12turn9search9turn23search2turn23search14

При этом **публичная стоимость большинства industrial AMR/AGV/forklift практически отсутствует**. Geek+, Quicktron, HAI, VisionNav, HIKROBOT и большинство других производителей продают проекты через RFQ/solution quotation. Поэтому для RobCo опасно подставлять Alibaba-цены как CAPEX. У них обычно неизвестны конфигурация батареи, зарядная станция, FMS/RCS-лицензия, safety package, commissioning, интеграция, доставка и Incoterm. Публичные локальные цены заметно лучше представлены у service robots и cobots: например, российские продавцы публикуют цены PUDU, KEENON, Gausium и AUBO; зарубежный дистрибьютор публикует цену Elite CS612. citeturn15search1turn8search2turn15search7turn15search2turn5search4

Ключевой вывод для архитектуры RobCo: **технический selection и коммерческий selection должны быть разделены**. Робот может получить высокий `technical_evidence_score`, но низкий `commercial_evidence_score` или `russia_availability_score`. Именно так выглядят, например, ForwardX и SEER: техническая документация сильная, но подтверждённый российский procurement-channel существенно слабее, чем у Geek+/Quicktron/PUDU/Gausium/JAKA/AUBO. citeturn10search0turn17search4turn23search2turn8search1turn8search0

Для warehouse automation особенно важно не переносить brochure throughput одного проекта в другой. Quicktron, например, публикует кейс 31 AMR и 50 т/ч и другой объект с более чем 300 роботами, но это показатели целых систем при конкретной топологии, WMS и потоках. Geek+ также публикует system-level throughput и кратные улучшения относительно manual picking. Поэтому fleet sizing RobCo должен считать через **mission-cycle model**, а vendor throughput использовать только как sanity check. citeturn18search1turn18search10turn18search8

Моя итоговая рекомендация — внести в первый production-ready китайский слой **11 CORE-моделей/семейств**:

| CORE candidate | Класс | Почему достаточно доказательств |
|---|---|---|
| Geek+ P800R / P-Series | shelf-to-person AMR | Хорошая документация, REST/Webhook, on-prem, VDA5050, российский интегратор и российский кейс. citeturn18search2turn18search5turn23search2turn7search1 |
| Quicktron M100 | latent/heavy AMR | 1000 кг, опубликованные speed/runtime, сильный RCS/WES/LES, официальный партнёр в РФ. citeturn0search7turn18search4turn23search2 |
| HAI Robotics HaiPick A42T | tote/ACR | 30 кг на load unit, до 12 м, автоматическая зарядка, safety data, российский интеграторский канал. citeturn0search1turn0search4turn23search11 |
| VisionNav VNP15 | autonomous forklift | Очень хорошие hard constraints: 1.5 т, 3 м, aisle и turning geometry, скорость. citeturn0search0turn6search14 |
| PUDU BellaBot | indoor delivery | Хорошие specs + российский официальный дистрибьютор + опубликованная цена. citeturn2search1turn8search1turn15search1 |
| KEENON T10 | indoor delivery | Полные физические specs, российские цены, manufacturer RFQ допускает Russia. citeturn2search2turn8search2turn22search0 |
| Gausium Scrubber 50 | autonomous cleaning | Очень сильная техдокументация, российский официальный канал, сервис, EAC evidence, текущая цена с НДС. citeturn15search3turn8search0turn8search5turn15search7 |
| JAKA Zu12 | UR-class cobot | 12 кг, локальные официальные интеграторы, большая международная база. citeturn9search12turn22search1 |
| AUBO i10 | UR-class cobot | Один из лучших публичных manual/spec sets плюс российская цена и dealer channel. citeturn4search1turn15search2turn9search9 |
| Elite Robots CS612 | UR-class cobot | Очень качественные публичные datasheet/manuals, 12 кг/1304 мм, российский сайт и продажи. citeturn5search0turn9search2turn9search25 |
| ESTUN ER12B-1510 | industrial 6-axis | Традиционный industrial arm, российский официальный distributor, публичный product range. citeturn3search0turn9search7 |

### Как рассчитывались scores

`technical_evidence_score` отражает полноту первичных данных о geometry, payload, speed, accuracy, battery, safety и operating limits. `commercial_evidence_score` — качество цен/RFQ evidence и прозрачность комплектации. `russia_availability_score` — сила российского procurement-channel и локальных внедрений. `serviceability_score` — support, spares, software independence, локальная поддержка и ремонтопригодность. `documentation_score` — качество manuals, API/interface information и consistency данных.

Это **аналитические оценки данного исследования, а не отраслевой рейтинг производителей**. Значения около 90 не означают, что робот «на 90% лучше» другого; они означают, что RobCo может с существенно меньшей неопределённостью использовать его в автоматическом matching.

## Карта китайского рынка и производители-кандидаты

Исследованный рынок не является однородным. В warehouse robotics китайские OEM уже покрывают практически весь диапазон от shelf-to-person и tote-to-person до 2.5-тонных AMR, autonomous pallet movers, reach trucks и vision-guided forklifts. Geek+ сообщает о глобальной support infrastructure и крупных международных клиентах; Quicktron — о более чем 45 тыс. установленных AMR и более 1000 клиентах; HIKROBOT сообщил о достижении 100 тыс. mobile robots ещё в мае 2024 года, а в 2026 году — уже о 180 тыс. cumulative units; SEER работает не только как robot OEM, но и как поставщик controller/software ecosystem для множества сторонних AMR. citeturn1search0turn1search2turn12search1turn12search3turn17search4

В fixed robotics китайский рынок имеет два различных слоя: классические industrial arms, где важны ESTUN/SIASUN/ROKAE, и rapidly maturing cobots — JAKA, AUBO, Elite Robots и Dobot. Для RobCo второй слой особенно удобен: payload/reach/repeatability стандартизированы лучше, чем у многих turnkey warehouse systems, а экономическая модель проще отделяет arm CAPEX от gripper, vision, fixture, safety и integration. JAKA сообщает о десятках тысяч роботов почти в 100 странах; ROKAE — о производственной мощности собственного завода до 50 тыс. роботов в год и работе более чем в 20 странах; SIASUN — о 18 тыс. проектов и экспорте более чем в 40 стран. citeturn22search1turn21search1turn21search6

| Компания / brand | HQ, founded, ownership evidence | Manufacturing footprint / maturity evidence | Основные классы | International evidence | Russia/CIS evidence | RobCo view |
|---|---|---|---|---|---|---|
| **Geekplus Technology / Geek+ / 极智嘉** | Китай; осн. 2015; с 2026 публичная компания, 2590.HK. citeturn6search0turn1search0 | Глобальные offices; 52+ service/partner sites и 12 spare-parts centers заявлены компанией. citeturn1search0 | AMR, shelf/tote/pallet-to-person, sorting | UPS, Walmart, Newegg, ASKUL и др. citeturn1search0 | Nissa внедряет Geek+ в России; опубликован российский Decathlon case. citeturn23search2turn7search1 | **Очень высокая зрелость** |
| **HAI Robotics / 海柔创新** | Shenzhen; осн. 2015; публичный листинг в просмотренных источниках не подтверждён. citeturn6search1 | ACR/high-bay tote automation; текущие глобальные partnerships, включая Dematic. citeturn6search1 | ACR, tote-to-person | Международные партнёры/проекты. citeturn6search1 | AXELOT публично предлагает HAI Robotics в РФ. citeturn23search11 | **Высокая** |
| **Quicktron Intelligent Technology / Quicktron / 快仓智能** | Shanghai; current official site; публичный листинг на дату исследования не подтверждён. | Компания заявляет 45,000+ AMR installations, 1000+ клиентов и 20+ стран. citeturn1search2 | AMR, G2P, material handling | Есть крупные международные cases, включая Cubyn. citeturn18search10 | Nissa — официальный партнёр в России, внедрение и сервис. citeturn23search2 | **Очень высокая** |
| **Hikrobot / HIKROBOT** | Hangzhou Hikrobot Co., Ltd.; юридически выделена в 2016. citeturn12search1 | К 2026 компания сообщала о 180 тыс. cumulative mobile robots; собственные iWMS/RCS. citeturn12search3turn18search0 | AMR, latent, pallet, forklift, CTU | 50+ рынков/overseas branches. citeturn12search1 | Российские distributors/integrators публично предлагают mobile robots; есть русскоязычная документация у поставщиков. citeturn23search0turn23search14 | **Очень высокая** |
| **VisionNav Robotics / 未来机器人** | Shenzhen; точный corporate founding field следует дополнительно закрепить registry evidence перед master-data import. | Autonomous industrial vehicles — основной бизнес. | Forklift, pallet truck, reach truck, tug | >30 стран; внешние партнёры сообщают о >5000 автономных forklifts. citeturn6search3turn6search7 | Есть российские коммерческие страницы решений VisionNav. citeturn6search14 | **Высокая technical maturity** |
| **ForwardX Robotics / 灵动科技** | Осн. 2016; Китай. citeturn12search0 | Завод, открытый в 2022 году: ~115 тыс. ft², заявленная мощность 5000 robots/year; current company figure 4500+ deployed AMRs. citeturn12search0turn12search6 | AMR, latent, heavy-load | 250+ facilities; крупные automotive deployments. citeturn12search4turn12search6 | Надёжный публичный RF channel для РФ не выявлен | **Высокая tech / слабее procurement** |
| **SEER Robotics / 仙工智能** | Shanghai; осн. 2020; 06106.HK. citeturn14search0turn14search4 | Controller + AMR + RDS/M4 ecosystem; 2500+ customers, 70+ стран/регионов. citeturn14search0 | AMR, forklift, controllers, FMS | Germany/Japan/HK subsidiaries; VDA5050 focus. citeturn17search0 | Отдельные российские sellers существуют, но channel конкретно для AMB/FMS недостаточно доказан. citeturn15search9 | **Очень интересен RobCo из-за openness** |
| **Multiway Robotics / 劢微机器人** | Shenzhen; team formed 2019. citeturn14search2turn14search6 | Производство Wuzhen/Zhejiang; WMS/RCS/WCS/Horizons/Simulation. citeturn14search2 | Forklift, reach truck, AMR | Работа в 40+ странах, subsidiaries US/Germany/Japan/Korea. citeturn14search2 | Надёжный российский channel не выявлен | **Высокий technical potential** |
| **SIASUN Robot & Automation / 新松** | Shenyang; осн. 2000; listed enterprise. citeturn21search0 | Industrial parks в Shenyang, Shanghai, Qingdao, Tianjin, Wuxi; 18 тыс.+ projects. citeturn21search6 | Industrial arms, AGV/AMR, special robots | 40+ стран, 4000+ international customers. citeturn21search0 | Убедительный текущий российский procurement-channel в этом проходе не найден | **Зрелый OEM, но не CORE для РФ пока** |
| **PUDU Robotics / 普渡科技** | Shenzhen; осн. 2016. citeturn22search2 | Delivery, cleaning, industrial/service robots | Delivery, cleaning, service | 60+ стран/регионов по официальным данным. citeturn22search2turn22search4 | SPI Robotics заявляет статус официального дистрибьютора РФ, 800 robots, spares/support. citeturn8search1 | **Один из лучших procurement fits** |
| **KEENON Robotics / 擎朗智能** | Shanghai; осн. 2010. citeturn22search0 | Mass-produced service robotics since 2018. citeturn22search0 | Delivery, hotel, hospital, cleaning, heavy delivery | 70+ стран/600+ cities по current site. citeturn22search5 | Российский product site с текущими ценами; Russia присутствует в официальной RFQ geography производителя. citeturn8search2turn22search0 | **Высокая** |
| **Gausium / Gaussian Robotics / 高仙** | Shanghai; осн. 2013. citeturn22search7 | Специализированный autonomous-cleaning OEM; 9400+ customers, 70+ countries/regions. citeturn22search3 | Cleaning/service AMR | Heathrow, Madrid Metro и другие public cases. citeturn15search3 | Официальный distributor в РФ, commissioning, training, service, EAC evidence. citeturn8search0 | **Лучший cleaning candidate** |
| **DEEPRobotics / 云深处科技** | Hangzhou; точный founding year в использованной странице не указан. | 100+ industrial/energy customers in China; overseas Singapore PowerGrid case. citeturn20search6 | Quadruped inspection/patrol | Международный industrial case. citeturn20search6 | Подтверждённый российский service channel не найден | **REFERENCE_ONLY** |
| **ESTUN Automation / 埃斯顿** | Nanjing; industrial automation OEM; с марта 2026 dual A+H listing. citeturn3search0 | Industrial robots, cobots, workstations, automation systems. citeturn3search0 | 6-axis, palletizing, welding, tending | Международная industrial footprint. citeturn3search0 | RobSys публично указывает статус официального дистрибьютора ESTUN в РФ. citeturn9search7 | **Высокая** |
| **JAKA Robotics / 节卡机器人** | Shanghai; осн. 2014. citeturn22search1 | Changzhou production base; 300+ partners. citeturn22search1 | Cobots, general intelligent robots | Tens of thousands robots, nearly 100 countries; Toyota, Schneider и др. citeturn22search1 | Российские официальные distributor/integrator channels. citeturn9search12turn9search16 | **Очень высокая** |
| **AUBO Robotics / 遨博** | Beijing; точную текущую corporate form/founding year перед импортом следует сверить registry-source | Сильная industrial cobot документация. citeturn4search1 | Cobot | CE/NRTL/CR etc. для i-series. citeturn4search1 | Российский официальный dealer + несколько sellers/integrators. citeturn9search9turn9search17 | **Очень высокая** |
| **Elite Robots / 艾利特机器人** | Suzhou-based robotics vendor; corporate founding fields требуют отдельной registry normalization | Очень подробные datasheets/manuals/service manuals. citeturn5search0 | Cobots | International sales and documentation. citeturn5search0 | Есть официальный русскоязычный сайт и российские sellers. citeturn9search2turn9search25 | **Высокая** |
| **ROKAE Robotics / 珞石机器人** | HQ/R&D Beijing, manufacturing Shandong. citeturn21search4 | Собственный завод, заявленная annual capacity 50,000 robots; 600+ R&D patents. citeturn21search1 | Industrial, collaborative robots | Sales/service activity >20 countries. citeturn21search1 | Убедительный RF procurement channel не найден | **OPTIONAL watchlist** |
| **UBTECH Robotics / 优必选** | Shenzhen; осн. 2012; 9880.HK с 29.12.2023. citeturn20search5 | Shenzhen factory, own full-stack robotics tech. citeturn20search5 | Humanoid/service/mobile service | International commercialization. citeturn20search5 | Current RF channel для industrial/service portfolio не доказан | **REFERENCE_ONLY для RobCo сейчас** |
| **DJI Enterprise / 大疆创新** | Shenzhen; private technology group; industrial UAV platform | Dock/Matrice/FlightHub ecosystem | Inspection UAV + autonomous dock | Глобальная Enterprise dealer ecosystem. citeturn19search1turn19search4 | Российские sellers предлагают Enterprise/Dock, но DJI продолжает публиковать собственное заявление о приостановке business activities в России и Украине. citeturn19search0turn19search5 | **Тех. лидер, но SUPPLY_RISK** |

Из этой двадцатки наиболее зрелый **manufacturer shortlist** для текущего этапа RobCo: Geek+, Quicktron, HIKROBOT, HAI Robotics, VisionNav, SEER, PUDU, KEENON, Gausium, ESTUN, JAKA, AUBO и Elite Robots. ForwardX и Multiway технически вполне заслуживают каталогизации, но пока хуже подтверждены именно с точки зрения российского procurement layer. citeturn12search6turn14search2turn23search2turn8search1turn8search0

## Нормализованный каталог моделей и CORE shortlist

Следующая таблица предназначена именно для RobCo matching. `н/д` означает не «у робота нет функции», а **параметр не удалось надёжно подтвердить из использованных публичных материалов**. Это принципиально важно: отсутствие evidence не должно автоматически превращаться в false constraint.

| Manufacturer / model | Class / application | Payload | Speed | Dimensions / aisle / turning | Lift / reach / accuracy | Autonomy / battery / charging | Navigation / safety / environment | API / integration / fleet | RobCo |
|---|---|---:|---:|---|---|---|---|---|---|
| **Geek+ P800R / P-Series** | Shelf-to-person AMR | 600 kg на текущей model page; family до 1200 kg | loaded 2.0 m/s | 950×702×275 mm | lift 60 mm | battery details публично неполны | QR+SLAM поддерживаются RMS; industrial safety ecosystem | RMS/WES/IOP; ERP/WMS/MES; REST API, Webhook, open interfaces, VDA5050; cloud/on-prem. citeturn18search2turn18search5turn18search11 | **CORE** |
| **Quicktron M100** | latent AMR / shelf & material movement | 1000 kg | 1.5 m/s | н/д в используемом current product extract | lift 60 mm | ~7.5 h | QR/inertial family; multi-robot RCS | WES/LES/RCS → WMS, ERP, MES, MIS, OMS, TMS. citeturn0search7turn18search4 | **CORE** |
| **HAI HaiPick A42T** | ACR / tote-to-person high-bay | 30 kg/load unit; до 9 loads simultaneously | н/д | platform geometry требует datasheet/RFQ | pick/storage height up to 12 m | LiFePO4 option; autonomous charging | autonomous nav; obstacle detection, avoidance, alarms, e-stop; Wi-Fi | System integration offered; public protocol-level API detail insufficient. citeturn0search1turn0search4 | **CORE** |
| **VisionNav VNP15** | Autonomous counterbalance forklift | 1500 kg | loaded straight 2.1 m/s; empty 2.5 | turning radius 1490 mm; stacking aisle 3150 mm; turning aisle 2152 mm | lift 3000 mm; load center 500 mm | н/д | vision/autonomous industrial vehicle stack | Fleet/integration available, public API details weaker than SEER/Geek+. citeturn0search0turn0search5 | **CORE** |
| **VisionNav VNQ50** | Autonomous tug | публичная model page подтверждает tug class, но достаточный normalized payload dataset не получен | н/д | н/д | — | н/д | autonomous | н/д | **DO_NOT_USE_YET** для auto-match; допустим как reference candidate. citeturn0search5 |
| **ForwardX Flex 300-L** | MiR-like AMR/platform | 300 kg | н/д в extracted spec | 800×480×295 mm; turning Ø960 mm | lift 60 mm | ~8 h | Laser SLAM + visual + floor/wall QR; 4 lidars, UWA/3D cameras, e-stop, bumper; CE | Wi-Fi, optional 4G/5G; integration layer требует project verification. citeturn10search0 | **OPTIONAL** |
| **ForwardX Max 1500-L** | Heavy latent AMR | 1500 kg | н/д | 1250×800×245 mm; turning Ø1340 | lift 60 mm | ~8 h | Laser SLAM / visual / QR; lidar/cameras/e-stop | Wi-Fi, optional 4G/5G | **OPTIONAL**. citeturn10search3 |
| **ForwardX Max O2500-L** | Heavy-load AMR | 2500 kg | н/д | 2100×1100×310 mm | н/д | ~7 h | same product-family autonomy | project-level integration | **REFERENCE_ONLY/OPTIONAL** pending RF sourcing. citeturn10search3 |
| **SEER AMB-800K** | Latent/lifting AMR | 800 kg | loaded 1.8; empty 2.2 m/s | height 245 mm | positioning ±5 mm; angular ±0.5°; lifting action ~2.5 s | battery details n/d | Laser SLAM; grade ≤5%; step ≤5 mm; gap ≤30 mm | **VDA5050 native via SRC; MQTT/JSON; RDS/M4**, heterogeneous fleets. citeturn10search1turn17search2turn17search4 | **OPTIONAL**, close to CORE technically |
| **HIKROBOT QF Pallet Mover** | pallet mover | 1000 kg | н/д | advertised operation in aisle ~1.8 m | pallet handling | н/д | autonomous industrial navigation | iWMS1000 + RCS2000; standard interfaces to WMS/MES/ERP, PLC/elevator/conveyor. citeturn10search2turn18search0 | **OPTIONAL** until full datasheet normalized |
| **Multiway MW-K16** | robotic VNA/reach truck | 1500 kg | н/д | minimum aisle ~1.75 m | lift 11,000 mm standard; custom to 16,500 mm | н/д | autonomous forklift platform | WMS/RCS/WCS/Horizons/Simulation ecosystem. citeturn14search1turn14search2 | **OPTIONAL** |
| **PUDU BellaBot** | indoor delivery/service | 40 kg total; 10 kg/tray | 0.5–1.2 m/s | 565×537×1290 mm | — | up to 13 h unloaded; charge ~4.5 h | marker or laser positioning | PUDU ecosystem; public industrial API evidence less rich than warehouse AMR vendors. citeturn2search1 | **CORE** |
| **KEENON T10** | indoor delivery | 40 kg | up to 1.0 m/s | 486×555×1399 mm; minimum passage ~590 mm | — | 9–12.5 h; charge ~5.5 h | stereo vision + VSLAM + RGB; slope 5° | KEENON software ecosystem; exact local API/cloud dependency should be RFQ item. citeturn2search2 | **CORE** |
| **Gausium Scrubber 50** | autonomous floor cleaning | cleaning machine, not payload transporter | up to 3.5 km/h (~0.97 m/s) | 810×700×1070 mm; min passage 900 mm; turn width 1200 mm | cleaning width 460 mm | ~3 h scrubbing / ~8 h dust mopping; ~2 h charge; LFP | 2D lidar, 3D/RGB vision, AI obstacle handling; optional automatic workstation | vendor app/cloud/software; automation APIs less publicly transparent than AMR RCS. citeturn15search3turn8search5 | **CORE** |
| **DEEPRobotics X20** | industrial inspection/patrol quadruped | source gives “load/endurance” field 20 kg; configuration must be confirmed | ≥4 m/s | 950×470×700 mm standing | obstacles ≥20 cm; slopes ≥30° | 2–4 h; ~15 km | terrain recognition, dynamic avoidance; IP66 | peripheral interfaces described as extensible, but standardized API details insufficient in public page | **REFERENCE_ONLY**. citeturn20search0 |
| **JAKA Zu12** | cobot; palletizing/tending/handling | 12 kg | TCP speed not normalized here | base Ø188 mm | reach ~1327 mm; repeatability should be frozen from current official datasheet before production import | mains-powered controller | IP54 in Russian product material | wireless programming; industrial integration ecosystem; Russian integrators support palletizing/tending/welding. citeturn9search12turn9search22 | **CORE** |
| **AUBO i10** | UR-class cobot | 10 kg | tool speed ≤3.0 m/s | robot 38.5 kg | reach 1350 mm; repeatability ±0.03 mm | mains/controller | 0…50°C; IP54; ISO Class 5 cleanroom; CE/NRTL/CR; ISO/TS 15066 references | Ethernet; Modbus RTU/TCP documented by Russian supplier; PROFINET optional. citeturn4search1turn15search2 | **CORE** |
| **Elite Robots CS612** | UR-class cobot | 12 kg | TCP up to 3.4 m/s | — | reach 1304 mm; repeatability ±0.05 mm | mains/controller | IP65, optional IP68; −10…50°C | public datasheet/user/service manuals and multiple industrial protocol options. citeturn5search0 | **CORE** |
| **ESTUN ER12B-1510** | industrial 6-axis | 12 kg | cycle/speed requires complete datasheet | — | reach 1510 mm | mains/controller | industrial-arm safety requires cell-level engineering | ESTUN controller/industrial automation ecosystem | **CORE** as arm, not as turnkey cell. citeturn3search0 |
| **DJI Dock 3 + Matrice 4TD** | autonomous inspection UAV + dock | UAV payload is sensor-integrated configuration, not warehouse payload | airborne; use mission limits, not AMR speed | dock closed 640×745×770 mm, 55 kg | operational radius ~10 km; M4D/4TD max flight time 54 min on official specs | Dock 15→95% charge ~27 min | Dock IP56 −30…50°C; aircraft IP55; thermal/visible sensing | **FlightHub 2, FlightHub 2 On-Premises, FlightHub Sync, DJI Cloud API**. citeturn2search0turn19search1 | **REFERENCE_ONLY / SUPPLY_RISK** |

### Аналитические scores

| Selectable solution | Tech | Commercial | Russia | Serviceability | Docs | Recommendation |
|---|---:|---:|---:|---:|---:|---|
| Geek+ P800R | **94** | 60 | **92** | 88 | **95** | **CORE** |
| Quicktron M100 | **91** | 58 | **94** | 88 | 88 | **CORE** |
| HAI A42T | 90 | 52 | 82 | 78 | 88 | **CORE** |
| VisionNav VNP15 | **95** | 45 | 68 | 68 | 91 | **CORE** |
| ForwardX Flex 300-L | 94 | 35 | 20 | 55 | 90 | OPTIONAL |
| ForwardX Max 1500-L | 91 | 35 | 20 | 55 | 87 | OPTIONAL |
| ForwardX Max O2500-L | 78 | 30 | 20 | 50 | 72 | REFERENCE_ONLY |
| SEER AMB-800K | **95** | 40 | 38 | 72 | **96** | OPTIONAL |
| HIKROBOT QF Pallet Mover | 82 | 48 | 86 | 84 | 85 | OPTIONAL |
| Multiway MW-K16 | 79 | 35 | 20 | 58 | 78 | OPTIONAL |
| PUDU BellaBot | 91 | **94** | **98** | **95** | 89 | **CORE** |
| KEENON T10 | 92 | 90 | 87 | 82 | 90 | **CORE** |
| Gausium Scrubber 50 | **96** | **95** | **98** | **96** | 93 | **CORE** |
| DEEPRobotics X20 | 83 | 25 | 10 | 42 | 76 | REFERENCE_ONLY |
| JAKA Zu12 | 92 | 66 | **95** | **92** | 90 | **CORE** |
| AUBO i10 | **97** | **92** | **94** | 91 | **97** | **CORE** |
| Elite CS612 | **97** | 68 | 78 | 82 | **98** | **CORE** |
| ESTUN ER12B-1510 | 88 | 58 | **96** | **93** | 86 | **CORE** |
| VisionNav VNQ50 | 48 | 30 | 62 | 60 | 45 | **DO_NOT_USE_YET** |
| DJI Dock 3 + M4TD | **99** | 72 | 30 | 45 | **99** | **REFERENCE_ONLY** |

С практической точки зрения самый интересный «не-CORE пока» кандидат — **SEER Robotics**. Его SRC controller официально поддерживает VDA5050, MQTT/JSON и heterogeneous fleet scheduling; RDS/M4 прямо предназначены для управления разными типами мобильных роботов. Для vendor-neutral RobCo это очень сильное архитектурное соответствие. Причина не присвоить AMB-800K статус CORE сейчас — не техника, а недостаточно надёжно подтверждённый российский sales/service channel именно для этой product line. citeturn17search0turn17search4

Второй кандидат на повышение — **HIKROBOT**. RCS2000 управляет различными типами mobile robots, а iWMS1000 интегрируется с ERP/MES/OMS/WMS; российский supply channel тоже существует. Но для QF Pallet Mover в текущей публичной странице не хватает geometry/battery/accuracy полей, чтобы RobCo без supplier datasheet автоматически проверял полный набор hard constraints. citeturn18search0turn10search2turn23search14

## Цены, доступность в РФ и procurement resilience

### Price evidence

Главная коммерческая ошибка, которой должен избежать RobCo, — смешивать цену самого робота с turnkey project CAPEX. Для mobile robotics реальный procurement object часто включает не только mobile base, но также зарядки, стеллажи/рабочие станции, Wi-Fi/network engineering, safety integration, RCS/WES/FMS, WMS interface, deployment, acceptance tests, spare batteries и commissioning. Публичные кейсы Geek+/Quicktron прямо показывают system-level architecture, где робот является лишь одним элементом. citeturn18search4turn18search8

| Product | value | price_type | currency | tax_status | incoterm | included_components | Evidence date | confidence |
|---|---:|---|---|---|---|---|---|---|
| **Geek+ P800R** | Quote required | Manufacturer/integrator RFQ | — | — | — | Конфигурация проекта | current | **HIGH** для факта RFQ, **none** для числовой цены. Российский интегратор предлагает запрос КП. citeturn23search2 |
| **Quicktron M100** | Quote required | Official Russian partner RFQ | — | — | — | project-specific | current | **HIGH**: Nissa прямо предлагает коммерческое предложение, но numeric list price отсутствует. citeturn23search2 |
| **HAI A42T** | Quote required | Integrator/project RFQ | — | — | — | ACR system depends on racks/workstations/software | current | **MEDIUM-HIGH**. citeturn23search11turn0search1 |
| **VisionNav VNP15** | Quote required | Distributor/project RFQ | — | — | — | forklift + software/integration configuration | current | **MEDIUM**; японский channel также прямо использует inquiry-for-price. citeturn24search2 |
| **PUDU PuduBot 2** | 640,000 | Russian distributor/reseller list | RUB | не раскрыт в search extract | domestic listing | Robot; charger/software inclusion надо подтвердить | observed 10 Sep 2026 | **MEDIUM**. citeturn15search1 |
| **PUDU BellaBot Basic** | 920,000 | Russian distributor/reseller list | RUB | не раскрыт | domestic listing | robot configuration; extras require confirmation | 10 Sep 2026 | **MEDIUM**. citeturn15search1 |
| **PUDU BellaBot Pro** | 1,040,000 | Russian distributor/reseller list | RUB | не раскрыт | domestic listing | robot configuration | 10 Sep 2026 | **MEDIUM**. citeturn15search1 |
| **KEENON T10** | 1,149,000 | Russian seller list | RUB | не раскрыт | domestic listing | robot; exact accessories/warranty bundle verify in quote | 10 Sep 2026 | **MEDIUM-HIGH**. citeturn8search2turn8search6 |
| **Gausium Scrubber 50MR** | **2,947,118** | Russian distributor/reseller list | RUB | **includes VAT 22% per listing** | domestic | Scrubber 50MR; workstation inclusion not evidenced | **31 Aug 2026** | **HIGH-MEDIUM**. citeturn15search7 |
| **AUBO i10** | **1,995,000** | Russian seller price | RUB | status not explicit in extracted page | domestic, to order | base product; commissioning/training stated separately/on request | 10 Sep 2026 | **HIGH-MEDIUM**. citeturn15search2 |
| **Elite CS612** | 31,400 | US distributor list | USD | local US tax not normalized | domestic US; shipping calculated separately | CS612 listing; accessories require checking | current | **MEDIUM**; useful benchmark, **not a Russia price**. citeturn5search4 |
| **JAKA Zu12** | 14,600–15,800 | Made-in-China seller listing | USD/set | not stated | **FOB** | listing title includes Zu12/gripper configuration; exact BOM unclear | 2026 listing | **LOW**; MOQ 1 set. Do not use as landed/turnkey CAPEX. citeturn24search16 |
| **DJI Dock 3** | 2,033,000 ex tax / 2,236,300 incl tax | Japanese authorized-market retail/list price | JPY | both ex/incl tax published | Japan domestic, not RF | Dock listing; aircraft/package scope must be validated before comparison | current | **MEDIUM-HIGH**, but not Russia price. citeturn19search9 |

Поэтому mobile robotics economic model RobCo лучше хранить не как одно поле `robot_price`, а как набор наблюдений:

`robot_base + battery_option + charger_count + charging_station + rack/top_module + fleet_software + WES/WMS_connector + commissioning + safety_integration + training + initial_spares + warranty_extension + logistics + customs/taxes`.

`FOB`, `EXW`, российская retail price и turnkey integration **никогда не должны попадать в одну price series без отдельного `price_type` и `incoterm`**. Особенно опасны маркетплейсные предложения: например, найденная Made-in-China позиция JAKA имеет FOB semantics и bundle, включающий gripper, поэтому её нельзя сравнивать напрямую с российской ценой bare/base cobot. citeturn24search16

### Russia / CIS availability

| Manufacturer | procurement_status_russia | Office / distributor / integrator evidence | Support / spares / commissioning | Certification evidence | Вывод |
|---|---|---|---|---|---|
| **Geek+** | **CONFIRMED_AVAILABLE** | Nissa Engineering поставляет и интегрирует решения Geek+ в России. citeturn23search2turn6search12 | Nissa — turnkey implementation; есть российский deployment history. citeturn7search1 | Model-specific EAC evidence не найдено | Сильный practical sourcing |
| **Quicktron** | **CONFIRMED_AVAILABLE** | Nissa прямо названа официальным партнёром Quicktron. citeturn23search2 | Внедрение и сервис заявлены там же. citeturn23search2 | Публичное model-specific EAC не найдено | Один из лучших RF channels |
| **HAI Robotics** | **LIKELY_AVAILABLE** | AXELOT публично включает HAI Robotics в портфель AMR/AGV. citeturn23search11 | Российский integrator capability есть; детали warranty/spares нужны в RFQ | EAC evidence не обнаружено | Хороший sourcing lead, но слабее Quicktron |
| **VisionNav** | **LIKELY_AVAILABLE** | Российский коммерческий сайт предлагает VisionNav automated forklifts. citeturn6search14 | Turnkey wording есть, но official manufacturer authorization не доказана | Не обнаружено | Supplier due diligence обязательна |
| **ForwardX** | **UNVERIFIED** | Надёжный RF distributor/integrator не найден | — | — | Не использовать цену/availability автоматически |
| **SEER** | **QUOTE_REQUIRED** | Российские sellers упоминают бренд, но конкретный канал для AMB/SRC/RDS недостаточно подтверждён. citeturn15search9 | Global service infrastructure сильная, в т.ч. Germany warehouse/support. citeturn17search0 | RF evidence нет | Technical optional |
| **HIKROBOT** | **CONFIRMED_AVAILABLE** | Несколько российских distributors; Optimus Drive прямо описывает себя как distributor mobile robots HIKROBOT. citeturn23search14turn23search0 | Русская документация и technical support заявлены поставщиком. citeturn23search14 | Конкретный EAC robot certificate не найден | Strong procurement candidate |
| **Multiway** | **UNVERIFIED** | Подтверждённого RF channel не найдено | — | — | Technical watchlist |
| **SIASUN** | **UNVERIFIED** | Текущий доказательный local channel не обнаружен | — | — | Не auto-match для RF procurement |
| **PUDU** | **CONFIRMED_AVAILABLE** | SPI Robotics заявляет статус официального дистрибьютора PUDU в РФ. citeturn8search1 | 5 years in Russia, 800 robots, spare-parts warehouse, remote support, turnkey integration заявлены distributor. citeturn8search1 | Specific certificate необходимо привязывать к модели | **Очень сильный** |
| **KEENON** | **LIKELY_AVAILABLE** | Активный российский site с моделями/ценами; официальный KEENON RFQ позволяет выбрать Russia. citeturn8search2turn22search0 | Local sales path есть; official authorization seller в собранных источниках не доказана | Не найдено | Хороший, но ниже PUDU |
| **Gausium** | **CONFIRMED_AVAILABLE** | T-Company заявлена official distributor Gausium in Russia. citeturn8search0 | Supply, commissioning, training, service, spares/service center. citeturn8search0turn8search5 | На distributor site опубликовано EAC certificate evidence. citeturn8search0 | **Лучший serviceability evidence** |
| **DEEPRobotics** | **UNVERIFIED** | Проверенного RF industrial channel не найдено | — | — | Reference only |
| **ESTUN** | **CONFIRMED_AVAILABLE** | RobSys — официальный distributor ESTUN в РФ. citeturn9search7 | Local integration/support channel | Требовать certificate по конкретному cell | Strong |
| **JAKA** | **CONFIRMED_AVAILABLE** | RobSys и другие российские integrators указывают official distributor/representative relationship. citeturn9search12turn9search16 | Local integration, palletizing, welding, machine tending capability. citeturn9search12 | Model/cell specific verification required | **Strong** |
| **AUBO** | **CONFIRMED_AVAILABLE** | Lider3D заявляет official dealer in Russia; есть дополнительные Russian sellers. citeturn9search9turn9search1 | Russian integrators/support available. citeturn9search17 | Arm certifications документированы manufacturer manual, local cell conformity separately. citeturn4search1 | **Strong** |
| **Elite Robots** | **LIKELY_AVAILABLE** | Official Russian-language site + Russian resellers. citeturn9search2turn9search25 | Commercial path есть, но local official-distributor status менее убедителен | — | Good secondary cobot |
| **ROKAE** | **UNVERIFIED** | Текущий Russian channel не подтверждён | — | — | Optional only |
| **UBTECH** | **UNVERIFIED** | Нет достаточного RF channel evidence для рассмотренного portfolio | — | — | Reference only |
| **DJI Enterprise** | **SUPPLY_RISK** | Российские websites продолжают предлагать Enterprise equipment/Dock 3. citeturn19search5turn19search8 | Но DJI официально объявила о suspension of all business activities in Russia and Ukraine; опубликованное заявление остаётся на сайте компании. citeturn19search0turn19search3 | Помимо product conformity, для UAV действует отдельный regulatory layer | Нельзя считать локальные listings подтверждением manufacturer-backed supply |

Особенно показателен DJI: наличие российского сайта, называющего себя продавцом Enterprise equipment, **не отменяет официального заявления DJI о приостановке business activities в России**. Поэтому RobCo должен показывать здесь `SUPPLY_RISK`, а не `CONFIRMED_AVAILABLE`; гарантии, activation, firmware, account region и official dealer status должны проверяться непосредственно перед закупкой. citeturn19search0turn19search4turn19search5

### Procurement resilience и software dependency

| Platform | On-prem evidence | Interfaces | Cloud/account dependency | Proprietary dependencies | RF serviceability assessment |
|---|---|---|---|---|---|
| **Geek+** | **Да**, manufacturer прямо заявляет cloud or on-prem deployment. citeturn18search11 | REST API, Webhooks, open APIs, VDA5050; WMS/ERP/MES. citeturn18search5 | Cloud не обязателен по public evidence | Robot controller + RMS/WES remain proprietary | **Высокая** благодаря Nissa |
| **Quicktron** | Public architecture выглядит локальной WES/LES/RCS, но explicit cloud/on-prem declaration в проверенной странице отсутствует | WMS/ERP/MES/MIS/OMS/TMS integration. citeturn18search4 | Не считать cloud mandatory без contract evidence | RCS/LES/WES proprietary | **Высокая** в RF partner projects |
| **HAI** | Не доказано | Enterprise integration заявлена, public API specifics слабые | Требует contract review | ACR controller, lifting mechanism, battery/FMS ecosystem proprietary | **Средняя-высокая** |
| **SEER** | Architecture oriented to industrial local controllers; specific cloud requirement не заявлен | **VDA5050 + MQTT + JSON**; RDS/M4; heterogeneous scheduling. citeturn17search2turn17search4 | Low apparent dependency, но deployment topology нужно закрепить договором | SRC controller proprietary, несмотря на open protocol | **Высокая технически / средняя procurement** |
| **HIKROBOT** | RCS/iWMS industrial deployment; cloud dependency не заявлена | Standard interfaces to WMS/MES/ERP, PLC, elevators, conveyors. citeturn18search0 | Не выявлена обязательная China-cloud dependency | RCS/iWMS + robot controller proprietary | **Высокая** |
| **PUDU** | Public model docs insufficient to guarantee fully disconnected operation | Vendor service ecosystem | Mobile apps/cloud/service functions могут быть relevant; RFQ должен прямо требовать offline/degraded-mode statement | Controllers, battery, navigation software proprietary | **Высокая hardware service**, software-resilience требует проверки |
| **KEENON** | Не доказано | Vendor ecosystem | Current site прямо охватывает connectable products, mobile apps, cloud services и firmware в security policy. citeturn22search5 | Strong vendor stack | **Средняя-высокая** |
| **Gausium** | Private deployment details требуют contract confirmation | Cloud platform + application software входят в product ecosystem. citeturn22search3 | Cloud ecosystem существует; offline autonomy needs acceptance test | Navigation/control and consumables partly proprietary | **Очень высокая local service**, medium software independence |
| **AUBO i10** | Local industrial controller architecture | Ethernet, Modbus RTU/TCP; PROFINET optional. citeturn15search2 | Публичных evidence обязательного cloud для базовой robot operation нет | Controller/servos/joints proprietary | **Очень высокая** |
| **JAKA / Elite / ESTUN** | Типичная local industrial-controller architecture; cloud requirement не выявлен в рассмотренных product materials | Industrial interfaces depend model/controller | Low apparent cloud dependency, verify license/update policy | Drives/reducers/controller proprietary | **Высокая** при российском integrator support |
| **DJI Dock 3** | **Да — FlightHub 2 On-Premises** официально поддерживается. citeturn2search0 | DJI Cloud API, FlightHub Sync | DJI account/firmware/ecosystem остаются существенным dependency layer | Aircraft, batteries, dock, radio, firmware highly proprietary | **Высокий supply/activation risk для РФ** |

Для RobCo стоит сделать отдельные boolean/enum fields:

`on_prem_supported`, `cloud_required_for_core_operation`, `account_region_restriction_verified`, `remote_activation_required`, `offline_degraded_mode`, `public_api_available`, `vda5050_supported`, `standard_fieldbus`, `battery_replaceable_local`, `local_spares_evidence`, `firmware_update_dependency`.

Особенно ценны именно **negative/unknown values**: service robot с отличной механикой, но неизвестным поведением при блокировке vendor cloud, не должен автоматически получать высокий `serviceability_score`.

## Western-reference mapping, supply risks и value positioning

Ни одна из приведённых пар ниже не означает полной interchangeability. Даже при одинаковом payload мобильные платформы могут требовать другие racks, charging topology, fleet server, safety validation, localization maps и WMS connectors; bare cobot не является palletizing cell; inspection drone не является warehouse inventory drone.

| western_reference | chinese_candidate | similarities | important differences | technical_fit | price_difference | documentation_quality | procurement_advantage_russia | risks |
|---|---|---|---|---|---|---|---|---|
| **MiR-like generic AMR** | **ForwardX Flex 300-L** | 300-kg platform, SLAM, dynamic obstacle sensing, top-module style use | Не MiR ecosystem; different FMS/accessories/API maturity | **High** mechanically | Не нормализована: RF price отсутствует | **High** citeturn10search0 | Low today | Russian channel unverified |
| **MiR-like generic AMR** | **SEER AMB-800K** | SLAM AMR, lifting, industrial fleet operation | 800 kg latent format rather than direct MiR250 geometry; stronger VDA5050 controller positioning | **High for intralogistics**, not form-factor equivalent | Quote required | **Very high** | Potentially strong if partner established | Current RF sourcing evidence weak. citeturn10search1turn17search4 |
| **MiR250 / intralogistics AMR reference** | **Geek+ P-series** | Autonomous internal transport, fleet management, enterprise integration | Primarily G2P/rack ecosystem rather than generic top-module AMR | Medium–High depending workflow | Quote required | **Very high** | **Strong** Russian integrator | Requires Geek-specific ecosystem. MiR itself carries up to 250 kg; Geek use case architecture differs. citeturn16search1turn18search8 |
| **Traditional AGV** | **Quicktron M100 / HIKROBOT Q-series** | Deterministic fleet transport, high payload, large-fleet scheduling | More modern hybrid autonomous/QR approaches; fleet stack differs | **High** | Quote required | High | **Strong** | Vendor RCS dependency. citeturn0search7turn18search0 |
| **MiR Hook-like autonomous tug** | **VisionNav VNQ50** | Autonomous towing use case | Insufficient public geometry/tow-rating data to assert equivalence | **Potential**, not selectable | Quote required | **Low for this exact model** | Possible RF commercial path through VisionNav sellers | **Do not automatic-match yet.** citeturn0search5 |
| **Autonomous forklift reference** | **VisionNav VNP15** | Automated pallet pickup/transport/stacking | VisionNav geometry/navigation/software stack differs; 3 m counterbalance format | **Very high** | Quote required | **Very high** | RF sourcing appears possible | Official-local service relationship needs verification. citeturn0search0turn6search14 |
| **Autonomous reach truck** | **Multiway MW-K16** | High rack operations, narrow aisle | 11 m/optional 16.5 m platform needs site-specific rack and pallet tolerances | **High** | Quote required | Medium–High | Low currently | RF service unknown. citeturn14search1 |
| **Heavy-load AMR** | **ForwardX Max O2500-L** | Multi-ton internal transport | Limited public performance dataset vs Flex series | Medium | Quote required | Medium | Low currently | Sourcing/support gap. citeturn10search3 |
| **Indoor delivery robot** | **PUDU BellaBot** | Autonomous indoor delivery, obstacle avoidance, long runtime | Open trays; not secure medical cabinet | **Very high for hospitality/general service** | RF price available | High | **Excellent** | Vendor software/cloud questions. citeturn2search1turn15search1 |
| **Indoor delivery / hospital-service class** | **KEENON T10** | Indoor SLAM delivery, narrow passage, long runtime | T10 is primarily general delivery/marketing; medical samples/medication require appropriate closed-compartment model | High for general service | RF price available | High | High | Do not map to secure medication transport automatically. citeturn2search2turn22search0 |
| **Autonomous cleaning robot** | **Gausium Scrubber 50** | Fully autonomous floor scrubber + workstation option | Gausium software/consumables ecosystem | **Very high** | Russian current price exists | **Very high** | **Excellent** | Proprietary cloud/software and consumables must be contractually addressed. citeturn15search3turn8search5 |
| **UR-class cobot** | **AUBO i10** | 6-axis collaborative arm, ~10 kg payload, ~1.3 m reach, high repeatability | Different programming ecosystem and certified accessory market | **Very high** | Russian price available; like-for-like Δ against UR catalog should be calculated in RobCo | **Very high** | **Excellent** | Local integrator quality matters. UR's current e-Series class similarly covers medium-payload cobots, but accessory ecosystem is substantially mature. citeturn4search1turn16search0 |
| **UR-class cobot** | **JAKA Zu12 / Elite CS612** | 12 kg class, ~1.3 m reach, broad tending/palletizing use | Different software/plugins/safety ecosystem | **Very high** | JAKA marketplace observation exists but not comparable to Russian turnkey; Elite US list exists | High–Very high | JAKA strong; Elite medium-high | Bundle and application-cell cost dominate arm price. citeturn22search1turn5search0 |
| **Industrial 6-axis arm** | **ESTUN ER12B-1510** | Conventional industrial robot for handling/welding/tending | Not collaborative; requires cell safety and application engineering | High | Quote required | High | **Excellent local distributor evidence** | Do not compare bare arm against turnkey western cell. citeturn3search0turn9search7 |
| **Palletizing cell** | **JAKA/AUBO/ESTUN-based cell** | All can be the motion platform for palletizing | **Arm ≠ cell**: gripper, column, vision, conveyor, PLC, guarding and pallet pattern software determine throughput | High only after cell engineering | Must be turnkey-to-turnkey | High arm docs | Good | Biggest risk is false CAPEX equivalence |
| **Inspection drone + dock** | **DJI Dock 3 + Matrice 4TD** | Remote autonomous missions, dock charging, inspection sensors, fleet/cloud software | UAV regulation, airspace, comms and corporate supply situation fundamentally differ | **Technically excellent** | Foreign reference prices available, RF comparable price not normalized | **Exceptional** | Hardware visible in RF retail | **Manufacturer Russia suspension ⇒ SUPPLY_RISK.** citeturn2search0turn19search0 |
| **Warehouse inventory drone** | **No CORE Chinese candidate identified** | — | DJI Dock family is an outdoor/industrial inspection solution, not evidence of autonomous indoor warehouse inventory counting | **Insufficient evidence** | — | — | — | Keep class open rather than forcing a match |

Для `price_difference` RobCo не следует хранить вывод «китайский на X% дешевле» до тех пор, пока обе цены не приведены к одному economic boundary: одна и та же валюта/date, одинаковый tax basis, Incoterm, число chargers, software horizon, commissioning, warranty и integration. В собранной выборке публичных данных недостаточно для добросовестного общего процента экономии, особенно по AMR/forklift systems.

### Supply-risk matrix

| Risk dimension | Lowest observed risk | Medium | Higher risk |
|---|---|---|---|
| **Russian sales channel** | PUDU, Gausium, JAKA, ESTUN, AUBO, Quicktron, Geek+ citeturn8search1turn8search0turn9search12turn9search7turn23search2 | HAI, HIKROBOT, KEENON, VisionNav, Elite | ForwardX, Multiway, DEEPRobotics, DJI |
| **Cloud lock-in** | AUBO/ESTUN/JAKA industrial-controller class; Geek+ supports on-prem. citeturn18search11turn4search1 | Quicktron/HIKROBOT/SEER | Service platforms where offline operation is insufficiently documented; DJI ecosystem |
| **Interoperability** | **SEER VDA5050**, Geek+ VDA5050/REST/Webhook. citeturn17search4turn18search5 | HIKROBOT/Quicktron standard enterprise integration | Closed service-robot stacks |
| **Spare-parts evidence in RF** | PUDU, Gausium explicitly strong. citeturn8search1turn8search0 | Integrator-supported fixed robots and AMRs | Unverified direct channels |
| **Firmware/account dependency** | Traditional industrial arms generally lower | Warehouse AMR fleet software | **DJI and cloud-connected service platforms require strongest contractual check** |
| **Regulatory/certification complexity** | Fixed indoor arm/AMR after normal machine-system conformity assessment | Service robots | **UAV/autonomous drone operations** plus product/supply constraints |
| **Single-vendor software dependence** | SEER architecture can reduce fleet-layer lock-in through VDA5050 | Geek+/Quicktron/HIKROBOT | Highly proprietary service/UAV ecosystems |

### Best value, best documented, easiest to source

**Best documented:** DJI Dock 3/Matrice 4TD, AUBO i10, Elite CS612, Geek+ P-series, SEER AMB/SRC ecosystem и VisionNav VNP15. У DJI есть отдельные installation, flight, safety и maintenance manuals; Elite публикует datasheet/user/service manuals; AUBO manual даёт payload, reach, repeatability, environment и certification data; SEER подробно документирует VDA5050/MQTT/JSON. citeturn19search6turn5search0turn4search1turn17search2

**Easiest to source in Russia по evidence:** PUDU, Gausium, Quicktron, Geek+, ESTUN, JAKA и AUBO. Здесь обнаружены не просто страницы на русском, а distributor/integrator evidence, local service или российские внедрения. citeturn8search1turn8search0turn23search2turn9search7turn9search12turn9search9

**Best value по доказуемым публичным ценам** нельзя объективно определить для AMR/forklift, потому что у сильнейших warehouse OEM цены RFQ-only. Среди cobots наиболее пригоден для value modeling AUBO i10, потому что одновременно имеются хороший technical baseline и российская numeric price. Среди service robots аналогичную роль играют PUDU/KEENON; среди cleaners — Gausium Scrubber 50. citeturn15search2turn15search1turn8search2turn15search7

## Рекомендации по сценариям и решения, которые пока нельзя auto-match

### Warehouse

Для **классического goods-to-person склада** наиболее безопасный первый китайский reference — Geek+ P800R/P-series. Причины: нормализуемые hard constraints, mature RMS/WES stack, REST/Webhook/on-prem/VDA5050 evidence и доказанный российский integrator/deployment layer. Geek+ прямо описывает STP workflow, где RMS отправляет mobile robots за стеллажами, а WMS/WES формирует задания. citeturn18search8turn18search11turn23search2

Для **high-density tote storage** логичнее HAI A42T: возможность обработки bins на высоте до 12 м делает его функционально другим классом, чем floor-only shelf AMR. RobCo должен моделировать его не как «ещё один AMR», а как ACR storage system, где capacity зависит от tote slots, vertical cycle, robot concurrency и workstation queues. citeturn0search1turn0search4

Для **транспортировки тяжёлых load carriers** рационален Quicktron M100, а ForwardX Max 1500-L/2500-L полезен как альтернативный technical reference. Quicktron предпочтительнее в CORE именно из-за российского официального партнёра, а не потому, что ForwardX технически слабее. citeturn0search7turn10search3turn23search2

Для **паллет и автономного stacking** лучший evidence candidate — VisionNav VNP15: payload 1500 кг, lift 3 м, turning radius 1490 мм и stacking aisle 3150 мм позволяют RobCo реально проверять aisle/geometry hard constraints, чего нельзя сделать по одной маркетинговой формулировке «autonomous forklift». citeturn0search0

Для **very-narrow/high-rack operation** интересен Multiway MW-K16 с 1.5 т, 11 м standard lift и заявленным minimum aisle ~1.75 м, но из-за более слабой российской procurement evidence его стоит держать OPTIONAL. citeturn14search1

### Airport / logistics

Для baggage/material logistics первое место я бы отдал **Quicktron M100/HIKROBOT material-handling family**, если задача заключается в перевозке carriers/pallets, а не в буксировке baggage trains. У обеих компаний есть зрелые fleet platforms и интеграция с higher-level systems; у Quicktron сильнее подтверждён российский partner path. citeturn18search4turn18search0turn23search2

Для сценария **MiR Hook-like towing** пока не следует автоматически выдавать VisionNav VNQ50 как interchangeable alternative. Наличие tugger model подтверждено, но публичного набора tow rating, hitch geometry, speed-under-load, turning-envelope и safety fields недостаточно. Для RobCo это именно тот случай, где правильный результат matching — **«кандидат найден, требуется supplier datasheet»**, а не fabricated fit. citeturn0search5

Для heavy industrial logistics ForwardX Max-series технически интересен: Max1500-L несёт 1.5 т, Max O2500-L — 2.5 т. Но без подтверждённого российского partner/support channel им следует дать OPTIONAL/REFERENCE_ONLY, несмотря на хорошую механику. citeturn10search3turn12search6

### Clinic / service

Для **food, linen, documents, non-secure general delivery** наиболее практичен PUDU: BellaBot имеет 40 кг total payload, длительную автономность, а в РФ есть доказанный distributor, spares и support. citeturn2search1turn8search1

KEENON T10 также хорошо подходит для general indoor delivery благодаря 590-мм minimum passage, 40-кг payload и 9–12.5 ч autonomy. Однако его нельзя автоматически считать hospital-medication robot: для лекарств, лабораторных образцов и иных контролируемых грузов нужны закрытые compartments, access control и соответствующий workflow. KEENON имеет отдельную историю hospital robots, включая M1 и более поздние специализированные линии, но T10 — не доказанная замена закрытой hospital courier platform. citeturn2search2turn22search0

Для **clinic/hospital cleaning** Gausium Scrubber 50 имеет наилучшее сочетание доказательств: LFP battery, sensor stack, autonomous spot cleaning, workstation option, российский сервис и EAC evidence. Его public Russian specs достаточно подробны для оценки проходов, turning width, runtime и cleaning productivity. citeturn15search3turn8search5turn8search0

### Fixed robotics

Для **machine tending / pick-and-place / light palletizing** самым сильным procurement/evidence вариантом выглядит AUBO i10. У RobCo есть 10 кг payload, 1350 мм reach, ±0.03 мм repeatability, tool speed, temperature/IP/cleanroom data, Modbus/Ethernet integration и российская numeric price. citeturn4search1turn15search2

JAKA Zu12 лучше рассматривать, когда требуются 12 кг payload и сильная local integrator ecosystem; Elite CS612 — когда критичнее публичная documentation quality. ESTUN нужен отдельным reference как **традиционный industrial 6-axis robot**, потому что RobCo не должен смешивать collaborative и fenced industrial applications. citeturn9search12turn5search0turn3search0

При palletizing/depalletizing RobCo должен отдельно хранить `arm_model` и `cell_configuration`. Ни JAKA Zu12, ни AUBO i10, ни ESTUN ER12 автоматически не являются «palletizing cell»: throughput определяется EOAT, carton mass/geometry, pick/place path, vertical column/7th axis, conveyor interface, vision, pallet dispenser, guarding и application software. Это особенно важно для CAPEX: price bare arm и price turnkey cell принципиально разные economic objects.

### Aerial / inspection

**DJI Dock 3 + Matrice 4TD** — лучший из найденных китайских вариантов по technical evidence для unattended industrial inspection: Dock IP56, −30…50°C, быстрая зарядка, Matrice 4D/4TD, FlightHub 2 и официальный on-premises вариант дают RobCo достаточно полей для hard constraints и infrastructure assessment. citeturn2search0turn19search1turn19search6

Но для российского procurement layer я не рекомендую CORE. DJI официально объявляла о suspension of business activities in Russia, поэтому даже наличие российского предложения Dock 3 не доказывает manufacturer-backed supply, warranty или future account/firmware availability. Это textbook case для статуса `SUPPLY_RISK`. citeturn19search0turn19search5

**Доказательного китайского warehouse inventory drone**, который одновременно имел бы indoor GPS-denied autonomy, inventory/barcode/RFID workflow, public fleet/API information и достаточную commercial maturity для RobCo auto-match, в рассмотренном наборе источников обнаружить не удалось. Это не означает, что таких разработок в Китае нет; это означает, что **ни одна не прошла заданный evidence threshold**. DJI Dock нельзя искусственно использовать для закрытия этой позиции: это другая operational architecture.

### Что не следует пока использовать в автоматическом matching

`DO_NOT_USE_YET` следует присвоить **VisionNav VNQ50 как конкретному tug reference**, пока не получен полный datasheet с tow rating/geometry/safety data.

`REFERENCE_ONLY` — DEEPRobotics X20: продукт явно зрелее research prototype и имеет industrial inspection evidence, однако открытых interface/service/Russia procurement данных мало. citeturn20search0turn20search6

`OPTIONAL` — Multiway MW-K16: очень привлекательные lift/aisle характеристики, но коммерческий и российский слой пока слабее технического. citeturn14search1turn14search2

`OPTIONAL` — ForwardX Max O2500-L: heavy-load payload доказан, но public spec completeness и RF availability недостаточны для fully automatic TCO/matching. citeturn10search3

`OPTIONAL` — HIKROBOT QF Pallet Mover: vendor maturity и Russian procurement сильные, но именно по этой новой модели публичный hard-constraint set пока неполон. citeturn10search2turn12search3

`REFERENCE_ONLY` — DJI Dock 3 для РФ: не из-за технической незрелости, а из-за supply/support inconsistency между российскими retail channels и manufacturer policy. citeturn19search0turn19search5

## JSON-ready dataset и источники

Ниже — компактный production-oriented dataset для первого `CORE` слоя. `null` сознательно сохранён там, где параметр не следует угадывать. Числовая цена не подставляется для quote-only products.

```json
[
  {
    "manufacturer": "Geek+",
    "model": "P800R",
    "robot_class": "shelf_to_person_amr",
    "application": ["goods_to_person", "warehouse_fulfillment"],
    "payload_kg": 600,
    "max_loaded_speed_m_s": 2.0,
    "dimensions_mm": [950, 702, 275],
    "lift_mm": 60,
    "runtime_h": null,
    "minimum_aisle_mm": null,
    "navigation": ["QR", "SLAM"],
    "interfaces": ["REST_API", "Webhook", "VDA5050", "open_API"],
    "upper_system_integration": ["WMS", "ERP", "MES"],
    "fleet_software": ["RMS", "WES", "IOP"],
    "on_prem_supported": true,
    "public_numeric_price": null,
    "price_type": "QUOTE_REQUIRED",
    "procurement_status_russia": "CONFIRMED_AVAILABLE",
    "technical_evidence_score": 94,
    "commercial_evidence_score": 60,
    "russia_availability_score": 92,
    "serviceability_score": 88,
    "documentation_score": 95,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "Quicktron",
    "model": "M100",
    "robot_class": "latent_amr",
    "application": ["material_transport", "warehouse"],
    "payload_kg": 1000,
    "max_speed_m_s": 1.5,
    "lift_mm": 60,
    "runtime_h": 7.5,
    "dimensions_mm": null,
    "navigation": ["QR_inertial_family"],
    "interfaces": ["enterprise_system_integration"],
    "upper_system_integration": ["WMS", "ERP", "MES", "MIS", "OMS", "TMS"],
    "fleet_software": ["RCS", "WES", "LES"],
    "public_numeric_price": null,
    "price_type": "QUOTE_REQUIRED",
    "procurement_status_russia": "CONFIRMED_AVAILABLE",
    "technical_evidence_score": 91,
    "commercial_evidence_score": 58,
    "russia_availability_score": 94,
    "serviceability_score": 88,
    "documentation_score": 88,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "HAI Robotics",
    "model": "HaiPick A42T",
    "robot_class": "autonomous_case_handling_robot",
    "application": ["tote_to_person", "high_bay_storage"],
    "payload_kg_per_load_unit": 30,
    "simultaneous_load_units_max": 9,
    "max_pick_height_mm": 12000,
    "battery_chemistry": "LiFePO4_option",
    "automatic_charging": true,
    "navigation": ["autonomous_navigation"],
    "safety": ["obstacle_detection", "active_avoidance", "alarm", "emergency_stop"],
    "network": ["WiFi"],
    "public_numeric_price": null,
    "price_type": "QUOTE_REQUIRED",
    "procurement_status_russia": "LIKELY_AVAILABLE",
    "technical_evidence_score": 90,
    "commercial_evidence_score": 52,
    "russia_availability_score": 82,
    "serviceability_score": 78,
    "documentation_score": 88,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "VisionNav",
    "model": "VNP15",
    "robot_class": "autonomous_counterbalance_forklift",
    "application": ["pallet_transport", "stacking"],
    "payload_kg": 1500,
    "max_loaded_speed_m_s": 2.1,
    "max_empty_speed_m_s": 2.5,
    "lift_height_mm": 3000,
    "turning_radius_mm": 1490,
    "minimum_stacking_aisle_mm": 3150,
    "minimum_turning_aisle_mm": 2152,
    "load_center_mm": 500,
    "public_numeric_price": null,
    "price_type": "QUOTE_REQUIRED",
    "procurement_status_russia": "LIKELY_AVAILABLE",
    "technical_evidence_score": 95,
    "commercial_evidence_score": 45,
    "russia_availability_score": 68,
    "serviceability_score": 68,
    "documentation_score": 91,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "PUDU Robotics",
    "model": "BellaBot",
    "robot_class": "indoor_delivery_robot",
    "application": ["hospitality", "food_delivery", "general_indoor_delivery"],
    "payload_kg": 40,
    "payload_per_tray_kg": 10,
    "max_speed_m_s": 1.2,
    "dimensions_mm": [565, 537, 1290],
    "runtime_h_unloaded": 13,
    "charging_time_h": 4.5,
    "navigation": ["marker_positioning", "laser_positioning"],
    "public_price_rub_basic": 920000,
    "public_price_rub_pro": 1040000,
    "price_type": "RUSSIAN_RESELLER_LIST",
    "tax_status": "UNKNOWN",
    "procurement_status_russia": "CONFIRMED_AVAILABLE",
    "technical_evidence_score": 91,
    "commercial_evidence_score": 94,
    "russia_availability_score": 98,
    "serviceability_score": 95,
    "documentation_score": 89,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "KEENON Robotics",
    "model": "DINERBOT T10",
    "robot_class": "indoor_delivery_robot",
    "application": ["hospitality", "general_delivery"],
    "payload_kg": 40,
    "max_speed_m_s": 1.0,
    "dimensions_mm": [486, 555, 1399],
    "minimum_passage_mm": 590,
    "runtime_h_min": 9,
    "runtime_h_max": 12.5,
    "charging_time_h": 5.5,
    "max_slope_deg": 5,
    "navigation": ["VSLAM", "stereo_vision", "RGB"],
    "public_price_rub": 1149000,
    "price_type": "RUSSIAN_SELLER_LIST",
    "tax_status": "UNKNOWN",
    "procurement_status_russia": "LIKELY_AVAILABLE",
    "technical_evidence_score": 92,
    "commercial_evidence_score": 90,
    "russia_availability_score": 87,
    "serviceability_score": 82,
    "documentation_score": 90,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "Gausium",
    "model": "Scrubber 50",
    "robot_class": "autonomous_cleaning_robot",
    "application": ["floor_scrubbing", "dust_mopping"],
    "max_speed_m_s": 0.97,
    "dimensions_mm": [810, 700, 1070],
    "cleaning_width_mm": 460,
    "minimum_passage_mm": 900,
    "turning_width_mm": 1200,
    "scrubbing_runtime_h": 3,
    "dust_mopping_runtime_h": 8,
    "charging_time_h": 2,
    "battery_chemistry": "LFP",
    "navigation_sensors": ["2D_LiDAR", "3D_camera", "RGB_camera"],
    "optional_automatic_workstation": true,
    "public_price_rub": 2947118,
    "price_type": "RUSSIAN_RESELLER_LIST",
    "tax_status": "VAT_22_PERCENT_INCLUDED_PER_LISTING",
    "price_observation_date": "2026-08-31",
    "procurement_status_russia": "CONFIRMED_AVAILABLE",
    "technical_evidence_score": 96,
    "commercial_evidence_score": 95,
    "russia_availability_score": 98,
    "serviceability_score": 96,
    "documentation_score": 93,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "JAKA Robotics",
    "model": "Zu12",
    "robot_class": "collaborative_robot_arm",
    "application": ["palletizing", "machine_tending", "handling", "welding"],
    "axes": 6,
    "payload_kg": 12,
    "reach_mm": 1327,
    "ip_rating": "IP54",
    "public_russian_numeric_price": null,
    "price_type": "QUOTE_REQUIRED",
    "procurement_status_russia": "CONFIRMED_AVAILABLE",
    "technical_evidence_score": 92,
    "commercial_evidence_score": 66,
    "russia_availability_score": 95,
    "serviceability_score": 92,
    "documentation_score": 90,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "AUBO Robotics",
    "model": "AUBO-i10",
    "robot_class": "collaborative_robot_arm",
    "application": ["machine_tending", "pick_and_place", "palletizing"],
    "axes": 6,
    "payload_kg": 10,
    "reach_mm": 1350,
    "repeatability_mm": 0.03,
    "max_tool_speed_m_s": 3.0,
    "robot_weight_kg": 38.5,
    "operating_temperature_c_min": 0,
    "operating_temperature_c_max": 50,
    "ip_rating": "IP54",
    "interfaces": ["Ethernet", "Modbus_RTU", "Modbus_TCP", "PROFINET_optional"],
    "public_price_rub": 1995000,
    "price_type": "RUSSIAN_SELLER_LIST",
    "commissioning_included": false,
    "training_included": false,
    "procurement_status_russia": "CONFIRMED_AVAILABLE",
    "technical_evidence_score": 97,
    "commercial_evidence_score": 92,
    "russia_availability_score": 94,
    "serviceability_score": 91,
    "documentation_score": 97,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "Elite Robots",
    "model": "CS612",
    "robot_class": "collaborative_robot_arm",
    "application": ["machine_tending", "handling", "palletizing"],
    "axes": 6,
    "payload_kg": 12,
    "reach_mm": 1304,
    "repeatability_mm": 0.05,
    "max_tcp_speed_m_s": 3.4,
    "ip_rating_standard": "IP65",
    "ip_rating_optional": "IP68",
    "operating_temperature_c_min": -10,
    "operating_temperature_c_max": 50,
    "public_us_distributor_price_usd": 31400,
    "price_type": "US_DISTRIBUTOR_LIST",
    "procurement_status_russia": "LIKELY_AVAILABLE",
    "technical_evidence_score": 97,
    "commercial_evidence_score": 68,
    "russia_availability_score": 78,
    "serviceability_score": 82,
    "documentation_score": 98,
    "robco_catalog_recommendation": "CORE"
  },
  {
    "manufacturer": "ESTUN",
    "model": "ER12B-1510",
    "robot_class": "industrial_6_axis_arm",
    "application": ["handling", "machine_tending", "welding", "palletizing"],
    "axes": 6,
    "payload_kg": 12,
    "reach_mm": 1510,
    "repeatability_mm": null,
    "public_numeric_price": null,
    "price_type": "QUOTE_REQUIRED",
    "procurement_status_russia": "CONFIRMED_AVAILABLE",
    "technical_evidence_score": 88,
    "commercial_evidence_score": 58,
    "russia_availability_score": 96,
    "serviceability_score": 93,
    "documentation_score": 86,
    "robco_catalog_recommendation": "CORE"
  }
]
```

Технические значения Geek+, Quicktron, HAI, VisionNav, PUDU, KEENON, Gausium, AUBO и Elite в dataset соответствуют рассмотренным manufacturer/distributor materials. citeturn18search2turn0search7turn0search1turn0search0turn2search1turn2search2turn8search5turn4search1turn5search0 Российские procurement statuses основаны на evidence Nissa, AXELOT, SPI Robotics, Gausium/T-Company, RobSys, Lider3D и других приведённых российских channels. citeturn23search2turn23search11turn8search1turn8search0turn9search7turn9search12turn9search9

Для production schema RobCo к этим records следует добавить как минимум:

```json
{
  "source_observations": [],
  "spec_revision_date": null,
  "price_observations": [],
  "incoterm": null,
  "tax_status": null,
  "charger_price": null,
  "software_license_model": null,
  "commissioning_price": null,
  "warranty_months": null,
  "spares_package_price": null,
  "eac_evidence": null,
  "on_prem_supported": null,
  "cloud_required_for_core_operation": null,
  "account_region_restriction_verified": null,
  "remote_activation_required": null,
  "firmware_dependency": null,
  "public_api_available": null,
  "vda5050_supported": null,
  "opc_ua_supported": null,
  "mqtt_supported": null,
  "rest_supported": null,
  "local_service_partner": null,
  "supplier_authorization_verified": null,
  "evidence_confidence": null
}
```

Именно эти поля не позволят RobCo превратить наличие китайского робота «в интернете» в ложное утверждение о его полной закупочной готовности в России.

### Sources appendix

| Source group | Что подтверждает |
|---|---|
| **Geek+ official technology / FAQ / solutions** citeturn18search2turn18search5turn18search8turn18search11 | P-series specs, RMS/WES/IOP, REST/Webhook, VDA5050, cloud/on-prem, integration architecture |
| **Geek+ corporate** citeturn1search0turn6search0 | Global footprint, cases, service network, current public-company status |
| **Nissa Engineering** citeturn23search2turn7search1 | Russia sourcing/integration for Geek+/Quicktron and Russian deployment evidence |
| **Quicktron official product/software/cases** citeturn0search7turn18search4turn18search1turn18search10 | M-series specs, WES/RCS/LES, system throughput and integration evidence |
| **HAI Robotics official** citeturn0search1turn0search4turn6search1 | A42T payload, lift height, battery/charging, safety, company maturity |
| **AXELOT Russia** citeturn23search11 | Commercial availability of HAI/HIKROBOT-class AMR solutions in Russia |
| **VisionNav official/partner sources** citeturn0search0turn0search5turn6search3turn6search7 | VNP15 geometry/performance, portfolio, international deployment evidence |
| **ForwardX official** citeturn10search0turn10search3turn12search0turn12search6 | Flex/Max specs, factory and current deployment footprint |
| **SEER Robotics official** citeturn10search1turn14search0turn17search0turn17search4 | AMB specs, listed status, VDA5050, MQTT/JSON, RDS/M4 and mixed fleets |
| **HIKROBOT official** citeturn10search2turn12search1turn12search3turn18search0 | Pallet mover data, company scale, iWMS/RCS integration architecture |
| **Russian HIKROBOT channels** citeturn23search0turn23search14 | Local sales, support and Russian-language documentation evidence |
| **Multiway official** citeturn14search1turn14search2 | Autonomous forklift/reach product matrix, software, manufacturing and international footprint |
| **SIASUN official** citeturn21search0turn21search6 | Listed status, factories, project count, exports |
| **PUDU official + Russia** citeturn22search2turn2search1turn8search1turn15search1 | Company footprint, BellaBot specs, Russian official distributor/service and price observations |
| **KEENON official + Russia** citeturn22search0turn2search2turn8search2 | Company history, international footprint, T10 specs and Russian retail pricing |
| **Gausium official + Russia** citeturn22search3turn15search3turn8search0turn8search5turn15search7 | Company scale, cleaning technology, Russian official distributor/EAC/service and current price |
| **DEEPRobotics official** citeturn20search0turn20search6 | X20 specs, industrial inspection and overseas case evidence |
| **ESTUN official + Russia** citeturn3search0turn9search7 | Robot portfolio/listing status and official RF distributor |
| **JAKA official + Russia** citeturn22search1turn9search12turn9search16 | Company maturity, international deployments, Russian distributors/integrators |
| **AUBO official/manual + Russia** citeturn4search1turn9search9turn15search2 | i10 hard constraints/certification/interfaces and Russian price/sourcing |
| **Elite Robots official + Russia** citeturn5search0turn9search2turn9search25 | CS612 detailed specification/manual quality and Russian commercial presence |
| **ROKAE official** citeturn21search1turn21search4 | Manufacturing footprint, capacity, international presence |
| **UBTECH official** citeturn20search5turn20search2 | Corporate/listed status and service-robot/private-deployment software evidence |
| **DJI Enterprise official** citeturn2search0turn19search1turn19search6 | Dock 3/Matrice specs, FlightHub, on-prem, manuals |
| **DJI Russia-policy / RF commercial evidence** citeturn19search0turn19search5 | Critical discrepancy between manufacturer suspension and continuing Russian reseller availability |
| **Price evidence** citeturn15search1turn8search2turn15search7turn15search2turn5search4turn24search16turn19search9 | PUDU, KEENON, Gausium, AUBO, Elite, JAKA marketplace and DJI Dock observations |

Итоговый procurement-layer следует строить не вокруг утверждения «Chinese alternative = substitute», а вокруг **трёх независимых доказательств**: `technical_fit`, `commercial_observation` и `russia_procurement_evidence`. При таком подходе китайские решения действительно расширяют RobCo: Geek+/Quicktron/HAI/VisionNav дают сильный warehouse layer; PUDU/Gausium — особенно убедительный service layer для РФ; AUBO/JAKA/ESTUN/Elite — viable fixed-robotics layer; SEER/HIKROBOT/ForwardX/Multiway образуют качественную вторую очередь. DJI технически заслуживает catalog reference, но для российского пользователя должен явно показываться как `SUPPLY_RISK`, а не как гарантированно доступный аналог. citeturn23search2turn8search1turn8search0turn9search12turn17search4turn19search0