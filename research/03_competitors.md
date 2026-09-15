# Конкурентное исследование RobCo: robotics feasibility, matching, economics и preliminary ТЭО

## Ключевой вывод

На сентябрь 2026 года рынок уже хорошо закрывает **отдельные куски** цепочки RobCo, но я не нашёл коммерческого продукта, который в одном vendor-neutral self-service workflow убедительно соединяет всю последовательность:

**объект / операция → описание процесса → automation readiness → cross-brand robot/EOAT matching → проверка hard constraints → cycle time / требуемое число роботов → CAPEX/OPEX/TCO → сравнение сценариев → понятная визуализация → предварительное ТЭО.**

Это важный вывод именно как результат конкурентного анализа, а не утверждение, что такого продукта физически нигде не существует. Ближайшие конкуренты распадаются на несколько кластеров. **HowToRobot** ближе всего к бизнес-слою RobCo: от идеи и требований до supplier-ready brief, market matching, бюджетных предложений, ROI и сравнения поставщиков. В 2026 году продукт уже использует AI-интервью, показывает число подходящих suppliers/products и даёт стартовать бесплатно. Но feasibility в нём в значительной мере валидируется **рынком и людьми-поставщиками**, а не встроенным инженерным движком, рассчитывающим reach, payload, EOAT, collision, cycle time и fleet size. citeturn13search5turn13search4turn13search7

**Vention MachineBuilder** — наиболее сильный UX-референс для следующего слоя: browser-based 3D-design, более 3 000 modular components, AI-assisted part recommendation, design checker, real-time BOM/цена/assembly time и digital-twin programming. Это уже очень близко к ощущению «конфигуратора промышленной автоматизации», однако пользователь в основном приходит с уже выбранной задачей и проектирует решение внутри коммерческой экосистемы Vention, а не начинает с диагностики процесса и vendor-neutral ТЭО. citeturn21search0turn13search0

**Realtime Robotics Resolver** — самый важный конкурент для технической части `capacity`: платформа автоматически генерирует collision-free paths, interlocks, task allocation, оптимизирует cycle time и позволяет работать с произвольным числом роботов; input начинается с уже подготовленных workcell/simulation data. То есть Resolver очень силён там, где RobCo уже перешёл от «стоит ли автоматизировать?» к «как оптимально спроектировать эту robotic cell?». citeturn13search1turn13search3turn19search4turn19search17

**Siemens Process Simulate, ABB RobotStudio, DELMIA и Visual Components** гораздо глубже RobCo по fidelity симуляции, collision/reach/cycle/virtual commissioning, но гораздо дальше от раннего business-feasibility UX. Process Simulate, например, рассчитывает collision-free robot motion, cycle time и energy use, а virtual commissioning может работать с реальным или виртуальным PLC; ABB использует Virtual Controller, повторяющий production controller; Visual Components 5.0 объединяет factory layout, process simulation, OLP и virtual commissioning. citeturn16search0turn16search16turn17search8turn17search13

**Именно между HowToRobot и инженерными симуляторами находится наиболее интересная белая зона RobCo:** быстрый, объяснимый, достаточно инженерно-строгий **pre-simulation feasibility layer**, который не пытается заменить Siemens/ABB/Visual Components, но до затрат на detailed engineering отвечает: *что автоматизировать, каким классом решения, какими конкретными роботами, сколько их нужно, какие ограничения критичны, сколько это ориентировочно стоит и какой сценарий экономически лучше*.

По конкурентной карте я бы формулировал RobCo не как **«AI для выбора робота»** и не как **«симулятор роботизации»**, а как:

> **Vendor-neutral automation feasibility & investment decision platform — от производственного процесса до предварительного ТЭО.**

Или ещё жёстче:

> **The decision layer before robot simulation and integrator RFQ.**

## Карта рынка и категории конкурентов

В таблице ниже `hard constraints` означает прежде всего payload с учётом EOAT/workpiece, reach/work envelope, mounting, геометрию и коллизии, требования к среде/процессу и совместимость компонентов. `Fleet/cycle` — не просто скорость робота из datasheet, а попытку вывести cycle time, throughput, загрузку и необходимое количество роботов/ячеек. Под `report` я отличаю инженерные outputs/BOM от именно **management-ready preliminary ТЭО**.

Цены указаны только там, где есть публичная информация; `quote` означает непубличную enterprise/solution pricing.

| Кат. | Компания / продукт / страна / URL | Target user и исходные данные | Catalog, matching и hard constraints | Fleet / cycle, economics, AI | Visualization, simulation, report | Бизнес-модель, сильные и слабые стороны |
|---|---|---|---|---|---|---|
| **A/E** | **HowToRobot** — Дания / международный. [howtorobot.com](https://howtorobot.com/) | Manufacturers, automation managers, engineering/procurement. Пользователь описывает operation, volumes и pain points обычным языком; AI задаёт уточнения и превращает разговор в project brief. citeturn13search5 | Не классический robot-SKU configurator: платформа показывает количество соответствующих suppliers и ready-made products и отправляет структурированный RFI matched/vetted suppliers. Реальная hard feasibility в значительной степени приходит через supplier concepts/quotes. citeturn13search5turn13search9 | Отдельный Investment Calculator считает текущую стоимость процесса, savings, ROI и разные automation scenarios. AI является front-end для requirements gathering и market match. citeturn13search4turn13search5 | Side-by-side standardized quotes; Investment Calculator экспортирует PDF management report. Собственной публично описанной physics/3D-cell simulation не найдено. citeturn13search4turn13search5 | Buyer начинает бесплатно; sourcing — subscription. Supplier Premium публично указан как $150/мес. или $1,200/год, плюс 5% commission при выданном PO. **Сильная сторона:** самый близкий к RobCo business workflow и независимое sourcing-positioning. **Слабость:** market validation вместо автоматизированного engineering validation. citeturn13search7turn13search11 |
| **B/D** | **Vention MachineBuilder** — Канада. [vention.io/machine-builder](https://vention.io/machine-builder) | Manufacturing/automation engineers, integrators и предприятия, уже представляющие cell/machine. Input — 3D geometry и сборка из modular components. | 3 000+ компонентов; AI-driven part recommendation, smart placement, configuration assistant, design checker. Robot-agnostic cells могут строиться вокруг нескольких известных брендов, но commerce завязан на Vention ecosystem. citeturn21search0turn13search0 | Real-time BOM, assembly time и price. Программирование связано с digital-twin simulation; у Vention также есть отдельные ROI tools/content, но публичные материалы не показывают единого neutral TCO optimizer внутри matching. citeturn21search0turn13search0 | Один из лучших browser 3D UX: design → digital twin → BOM/price → assembly. Автоматические assembly instructions. citeturn21search0 | MachineBuilder используется как low-friction/free design environment; monetization — hardware/cells, software/deployment/services. **Сильная сторона:** практически эталон «configure visually and see the cost immediately». **Слабость для RobCo:** начинается после выбора automation concept и не является независимым market-wide feasibility layer. citeturn21search0 |
| **B/D** | **RoboDK** — Канада. [robodk.com](https://robodk.com/) | Robotics engineers/integrators; CAD, robot model, TCP/targets/path/process. | Очень широкий multi-brand robot library: фильтры по типу, axes, reach, payload, weight, repeatability и application; в библиотеке, например, более тысячи 6-axis models. Matching — преимущественно filter/search, а не автоматический `process → best robot`. citeturn15search16 | Simulation/OLP позволяет инженерно проверить выбранного робота; business ROI/TCO layer публично не является ядром. | Сильные 3D simulation и offline programming; поддерживаются многие типы роботов и CAD/CAM. citeturn15search9 | Professional perpetual license публично €3,995, maintenance после первого года — €1,500/год. **Сила:** зрелый, недорогой относительно enterprise OLP, multi-vendor. **Слабость:** инструмент инженера, а не decision tool для операционного/финансового пользователя. citeturn15search1turn15search9 |
| **B** | **FANUC Robot Range / Robot Finder** — Япония. [fanuc.eu/eu-en/robot-range](https://www.fanuc.eu/eu-en/robot-range) | Engineers/buyers, уже знающие application и основные технические требования. | Собственный FANUC catalog: payload от субкилограммового уровня до heavy-duty моделей; модели группируются по applications/series. Это классический OEM selector, то есть matching ограничен продукцией одного производителя. citeturn20search3turn20search7turn20search23 | Не evidence-based fleet/TCO engine. | Product/spec visualization, но не whole-cell feasibility simulation и не management ТЭО. | Бесплатный presales selector, монетизация через hardware. **Сильная сторона:** точные OEM specs. **Слабость:** vendor lock-in и практически отсутствующий business-case layer. |
| **B** | **Yaskawa Motoman Spec Finder** — Япония. [motoman.com/.../industrial](https://www.motoman.com/en-us/products/robots/industrial) | Robotics engineers; application + требуемые robot specs. | Spec Finder помогает выбрать arm по application и техническим параметрам внутри Motoman range. citeturn20search15 | Публичного cross-vendor cycle/fleet или TCO matching нет. | Каталог/spec pages; detailed engineering уходит в другие инструменты. | Бесплатный OEM sales funnel. Те же ограничения, что у FANUC: хороший datasheet selection, слабая early-stage feasibility. citeturn20search15 |
| **B/E** | **OnRobot D:PLOY** — Дания. [onrobot.com/en/dploy](https://onrobot.com/en/dploy) | SMEs, end users и integrators для palletizing, transferring, packaging, CNC tending. Input: автоматически обнаруженное cell hardware, workspace boundaries/obstacles, workpiece attributes и pick positions. citeturn14search0turn21search23 | Поддерживает ABB, Denso, Doosan, FANUC, Kawasaki, KUKA, Omron, UR, Yaskawa и др. D:PLOY автоматически строит collision-free paths и program logic. Но он в основном **конфигурирует уже выбранное hardware**, а не решает market-wide robot selection. citeturn21search2turn14search0 | Оптимизирует application под throughput и даёт runtime KPI monitoring. Отдельного neutral CAPEX/TCO decision engine в изученных материалах нет. Автоматизация алгоритмическая, но продукт не позиционируется прежде всего как generative-AI planner. citeturn14search0 | Очень сильный guided UI; намеренно может обходиться **без отдельной simulation phase** — palletizing позиционируется как zero programming/zero simulations. citeturn14search9turn21search14 | Quote/hardware+software. **Сила:** отличный reference для «задай несколько параметров — получи работающую application». **Слабость:** ограниченные application families и поздняя стадия относительно RobCo. |
| **C** | **A3 ROI Robot System Value Calculator** — США. [automate.org/robotics-roi-calculator](https://www.automate.org/robotics-roi-calculator) | Manufacturers и managers, которым уже известен ориентировочный robot-system cost. | Нет robot catalog/matching/hard-constraint analysis. | Сравнивает manual labor с владением robot system на горизонте 20 лет; учитывает purchase price, electricity, scaling по workforce и предполагает annual maintenance в размере 5%. citeturn15search0 | Финансовая projection/value output; engineering sim нет. | Бесплатно. **Сила:** простой и прозрачный economic reference. **Слабость:** экономика отделена от вопроса «какой робот физически выполнит процесс?», а часть assumptions фиксирована. citeturn15search0 |
| **C** | **Universal Robots Justification / ROI Calculator** — Дания. [universal-robots.com/.../roi-calculator...](https://www.universal-robots.com/2024q1/roi-calculator-business-case-organic-social-sequence/) | Cobot buyers. Input связан с economics существующего manual process и ожидаемым эффектом automation. | UR/cobot-centric; нет market-wide matching. | Учитывает не только labor, но rework savings, scrap savings, inventory reduction, capacity gains и customer retention. citeturn14search2 | Worksheet/business-case UX, не cell simulation. | Бесплатный lead-generation tool. **Хороший reference:** RobCo стоит считать benefits шире labour replacement. **Слабость:** экономика заранее привязана к классу cobot solution. citeturn14search2 |
| **C/A** | **Robotiq Lean Robotics ROI Calculator / IQ Fit Check** — Канада. [robotiq.com](https://robotiq.com/solutions/palletizing) | В первую очередь end-of-line palletizing customers. | Matching ограничен Robotiq solution family. Новый self-service `IQ` включает 5-minute Fit Check для конкретного проекта. citeturn15search15 | ROI Calculator учитывает production rate, staff costs и risks; IQ обещает detailed ROI, price range и payback period. citeturn15search2turn15search15 | Это скорее guided commercial assessment/reporting, чем general robotic simulation. | Бесплатный presales funnel → sale of Robotiq system. **Сила:** очень близкий к RobCo micro-UX для конкретного use case. **Слабость:** application/vendor specific. |
| **D** | **Visual Components 5.x** — Финляндия. [visualcomponents.com](https://www.visualcomponents.com/) | Manufacturing/process/automation engineers, integrators, OEMs. Input — factory/cell layouts, equipment, flows, processes и robots. | Богатая manufacturing-component ecosystem и multi-brand robotics/OLP; не business-language `process → robot` matcher. | Сильные throughput/cycle/process what-if models; встроенного preliminary-investment TCO/matching layer уровня RobCo в публичном positioning нет. | 5.0 объединяет factory layout planning, process simulation, robot OLP и virtual commissioning. Это один из лучших visual references для RobCo. citeturn17search13turn17search1 | HQ Espoo, Finland. Visual Components сама указывает Premium simulation около €13,000/год; Premium OLP продаётся отдельно и выше по цене. **Сила:** доступнее и визуальнее многих enterprise digital-twin suites. **Слабость:** требует существенно больше инженерных input/data, чем RobCo должен требовать на feasibility stage. citeturn17search2turn17search5 |
| **D** | **Siemens Tecnomatix Process Simulate** — Германия. [siemens.com/.../process-simulate-software](https://www.siemens.com/en-us/products/tecnomatix/process-simulate-software/) | Automotive/industrial engineering, line builders, integrators. CAD/layout, robot models, processes, PLC/logics. | Robot Library + CAD, reachability/collision/path validation. Это engineering selection/validation, не автоматическая market matching system. citeturn16search4turn16search10 | Robot operation cycle time и energy use входят в анализ; можно test variants. В 2026 Siemens также продвигает AI Copilot для Process Simulate, включая reachability/diagnostics. citeturn16search0turn16search22 | Очень глубокий dynamic 3D, SiL/HiL virtual commissioning с PLC, sequence validation. citeturn16search16 | Enterprise quote/licensing. **Сила:** высокая engineering credibility. **Слабость:** overkill для пользователя, которому ещё нужно понять, имеет ли проект business sense. |
| **D** | **ABB RobotStudio Suite** — Швейцария. [abb.com/.../robotstudio-suite](https://www.abb.com/global/en/areas/robotics/products/software/robotstudio-suite) | ABB robot engineers, integrators, commissioning teams. | ABB-specific robot ecosystem; Virtual Controller повторяет real controller software, Automatic Path Planning входит в набор функций. citeturn17search8 | Accurate robot behavior/cycle engineering; AI Assistant помогает работе с RobotStudio и документацией, но не является инвестиционным AI matcher. citeturn17search0turn17search16 | Desktop + Cloud; 3D simulation, virtual commissioning, real-time collaboration; AR viewer может визуализировать cell на shop floor. citeturn17search0turn17search4 | Trial/free Cloud access + commercial licenses. **Сила:** ABB controller fidelity. **Слабость:** сильный OEM lock-in; нет process-readiness/TCO-first UX. |
| **D** | **Dassault Systèmes DELMIA Robotics** — Франция. [3ds.com/.../robotics](https://www.3ds.com/products/delmia/industrial-engineering/robotics) | Large manufacturers, automotive/aerospace, integrators, 3DEXPERIENCE users. | Генерирует collision-free paths, может идентифицировать эффективные robot configurations; engineering context берётся из seams, fasteners и process geometry. citeturn16search2 | AI применяется для automatic collision-free path generation и robot recognition; новая DELMIA AI-agent direction использует routing, labor, machine, process и performance data. citeturn16search6turn16search12 | Full 3D virtual twin, process simulation/programming/virtual commissioning. | Enterprise subscription/quote. **Сила:** широкий manufacturing context и digital continuity. **Слабость:** сложность/стоимость и поздний lifecycle stage по отношению к RobCo. |
| **D/F** | **NVIDIA Isaac Sim** — США. [developer.nvidia.com/isaac/sim](https://developer.nvidia.com/isaac/sim) | Robotics developers, AI teams, robot OEMs/startups. CAD/robot descriptions, world/sensors, policies. | Не коммерческий robot selector: framework для импорта/моделирования и validation. | Сильнейшая основа для Physical AI, testing и synthetic data; нет business ROI/TCO logic. | Open-source reference framework на Omniverse для physically based robot simulation, testing и synthetic-data generation. citeturn16search3 | Open-source ecosystem + NVIDIA infrastructure. **Сила:** мощная technology foundation, которую RobCo потенциально может использовать на позднем fidelity layer. **Слабость:** слишком developer-oriented для preliminary ТЭО. |
| **E** | **Qviro** — Бельгия. [qviro.com](https://qviro.com/) | Buyers/engineers ищут robots, components и integrators. | Marketplace: 23 product categories, datasheets/specs, vetted integrators; позиционируется как compare/connect/get best deal. citeturn20search0 | Public evidence полноценного cycle/fleet/TCO simulator не найдено. | Comparison/reviews/product discovery, не physics simulation. | Marketplace + SaaS/data model для vendors; Qviro — Belgium-based startup. **Сила:** discovery, reviews и supplier layer. **Слабость:** ответ на «где купить/с кем интегрировать», а не на «доказать feasibility». citeturn20search4turn20search28 |
| **E/G** | **Formic Full Service Automation** — США. [formic.co/full-service-automation](https://formic.co/full-service-automation) | US manufacturers, особенно компании, которым сложно самостоятельно купить, интегрировать и обслуживать robotics. | Formic сам scope/deploy/operate solution; matching выполняется внутри managed-service process, а не независимым публичным configurator. | Economics радикально упрощена через **zero CapEx / fixed monthly price**; production-intelligence software включён в service. citeturn20search1 | Клиенту важнее operating system/service outcome, чем standalone simulation UX. | RaaS / Full Service Automation. **Сила:** убирает CapEx, maintenance и expertise barriers. **Слабость относительно RobCo:** assessment — часть продажи собственной service solution, а не neutral ТЭО. citeturn20search1turn20search25 |
| **E/F** | **ReshapeX** — США. [reshapex.com](https://www.reshapex.com/en) | Automation OEMs, distributors, integrators и industrial sales/application-engineering teams. | AI работает поверх catalog, compatibility rules, approved substitutes, datasheets, proposal archive и pricing tiers; workflows включают RFP→BOM, Quote и Substitute agents. citeturn20search2 | Сильный AI product/configuration/quoting layer, но не factory throughput/TCO engine. | BOM/quote/workflow outputs; не robot-physics digital twin. | Enterprise / forward-deployed AI + product platform. **Сила:** показывает, как AI может быть grounded в industrial catalog и constraint rules. **Слабость для RobCo:** в 2026 positioning — seller-side sales/applications engineering, а не manufacturer-side automation feasibility. citeturn20search2turn20search6 |
| **F** | **Realtime Robotics Resolver** — США. [rtr.ai/resolver](https://rtr.ai/resolver/) | Proposal/design engineers, system integrators, automotive manufacturers. Input — workcell data из simulation tool. citeturn13search1 | Не является catalog recommender. Зато после выбора robots автоматически генерирует collision-free motion, interlocks и task assignment. | **Очень сильный:** automatic task allocation, target sequencing, arbitrary number of robots, cycle-time optimization и throughput. Это наиболее близкий competitor к `matching → capacity`, но task-to-robot allocation ≠ market robot selection. citeturn13search3turn19search4turn19search17 | Интегрируется с simulation workflow; рассчитан на rapid what-if engineering и reachability validation. | Cloud product, есть Try Resolver Free. **Сила:** technical feasibility/optimization на proposal stage. **Слабость:** пользователь должен принести workcell model; readiness и financial business case находятся вне продукта. citeturn19search0turn19search8 |
| **F** | **Wandelbots NOVA** — Германия. [wandelbots.com](https://www.wandelbots.com/product-description-wandelbots-nova) | Robot developers, integrators, manufacturers с heterogeneous robot fleet. | NOVA OS даёт hardware-agnostic abstraction для ABB, FANUC, KUKA, UR, Yaskawa и др.; это унификация control stack, не автоматический robot recommendation engine. citeturn19search1turn19search34 | Architecture включает motion planning, virtualization, data pipelines, AI models и digital twins. ROI/TCO matching не является core product layer. citeturn19search34 | Может связываться с physically accurate simulation, включая Isaac Sim; хороший reference robot-agnostic architecture. citeturn19search26 | Commercial platform; cloud имеет consumption-based features. **Сила:** vendor-independent software abstraction. **Слабость:** отвечает «как написать и выполнить robotic app», а не «какую automation investment выбрать». citeturn19search1 |
| **F** | **Jacobi Robotics** — США. [jacobirobotics.com](https://jacobirobotics.com/) | Robotics developers/integrators; особенно dynamic palletizing и motion-intensive applications. | Hardware-agnostic platform; robot selection не core. | Совмещает high-fidelity simulation, ultrafast motion planning и reinforcement-learning agents, принимающие решения в dynamic environment. citeturn19search9 | Strong technical simulation/motion layer; нет preliminary ТЭО/reporting focus. | Software/platform + application solutions, commercial quote. **Сила:** AI действительно влияет на motion/task execution, а не просто разговаривает с пользователем. **Слабость:** downstream execution technology, а не feasibility planning. citeturn19search9 |
| **F** | **Trener Robotics Acteris** — США / Норвегия. [trener.ai](https://trener.ai/) | Manufacturers/integrators для high-mix, high-variability operations. | Совместим в 2026 с ABB, Universal Robots и FANUC, новые brands планируются. Использует существующие или новые cells. citeturn19search28 | Physical AI делает industrial robots более adaptive; направление — pre-trained robotic skills вместо жёсткой point-to-point programming. citeturn19search3 | Execution/adaptation platform, не standalone feasibility simulator/report generator. | Enterprise/startup model. HQ указаны San Jose и Trondheim. **Сила:** compelling Physical-AI differentiation. **Слабость:** почти не конкурирует с RobCo в economics/readiness, но конкурирует за слово «AI robotics». citeturn19search7turn19search3 |
| **G** | **Excel + internal engineering model** | Automation engineer, operations manager или integrator вручную собирает process times, labor, robot datasheets и цены. | Catalog обычно PDF/Excel/browser tabs; matching экспертное. | ROI/cycle легко моделируются, но assumptions и formulas становятся person-dependent; multidimensional scenario comparison быстро разрастается. | Excel graphs + PowerPoint/Word proposal; 3D — отдельный CAD/simulation package. | Почти нулевая software cost, максимальная гибкость. **Это главный реальный substitute RobCo:** не отдельный SaaS, а связка spreadsheet + engineer judgement + звонки integrators. То, что даже специализированные vendors продолжают выпускать spreadsheet-style cycle/ROI tools, показывает устойчивость этого workflow. |
| **G** | **Consultant / integrator presales** | Клиент отдаёт задачу automation consultant, OEM или integrator. | Human expert выполняет readiness, technology selection и constraints assessment. | Cycle, price и ROI появляются в concept/proposal/RFQ; качество сильно зависит от конкретной команды и от коммерческой мотивации продавца. | CAD concept, simulation по необходимости, PDF/PPT proposal. | Hourly/project consulting либо presales, окупаемый выигранным hardware/integration deal. HowToRobot сам комбинирует platform с independent expert support, Vention — digital design с supported/turnkey delivery, а Formic вообще принимает scope/deploy/operate на себя. Это показывает, что главный incumbent workflow — **software + human expert**, а не software alone. citeturn13search9turn20search1 |

Особенно важна эволюция **HowToRobot**: это уже не просто supplier directory. Текущая главная страница 2026 года формулирует продукт как *automation planning & sourcing platform* с цепочкой `Describe → Gather ideas → Publish & get quotes → Compare & choose`; AI преобразует rough operations в draft briefs, а каждому draft показывает доступность suppliers и ready-made products. То есть для RobCo это уже прямой конкурент по нескольким верхним блокам proposed workflow. citeturn13search5

С другой стороны, **Robotiq IQ Fit Check** показывает, что даже hardware vendors двигаются вверх по funnel: клиент за пять минут получает project-specific ROI, price range и payback estimate для palletizing. Это подтверждает, что `assessment → economics` становится частью modern robotics UX, пусть пока и в vendor/application-specific виде. citeturn15search15

## Feature matrix

Обозначения: **●** — сильная native capability подтверждена публичными материалами; **◐** — partial, manual, adjacent или отдельный модуль/инструмент; **○** — в изученных актуальных публичных материалах такой функции не найдено. `○` не означает гарантированного отсутствия во внутренних enterprise workflows.

| Product | Process / readiness | Robot catalog | Auto matching | Hard constraints | Cycle / fleet | ROI / TCO | AI | Visual / 3D | Simulation | Scenario compare | Preliminary ТЭО / decision report |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **HowToRobot** | **●** | ◐ | **●** supplier/product | ◐ human/supplier | ○ | **●** | **●** | ○ | ○ | **●** economics/quotes | **●** |
| **Vention MachineBuilder** | ◐ | **●** ecosystem | **●** components | **●** | ◐ | ◐ | **●** | **●** | **●** digital twin | **●** design | ◐ BOM/docs |
| **RoboDK** | ○ | **●** multi-brand | ◐ filters | **●** via sim | ◐/● | ○ | ○ | **●** | **●** | **●** engineering | ◐ technical |
| **FANUC Finder** | ○ | **●** FANUC | ◐ filter | ◐ datasheet | ○ | ○ | ○ | ◐ | ○ | ○ | ○ |
| **Yaskawa Finder** | ○ | **●** Motoman | ◐ filter | ◐ datasheet | ○ | ○ | ○ | ◐ | ○ | ○ | ○ |
| **OnRobot D:PLOY** | ◐ application wizard | ◐ compatible HW | ◐ | **●** workspace/collision | **●** throughput | ○ | ◐ automation | **●** GUI | ◐ / intentionally minimized | ◐ | ◐ runtime KPI |
| **A3 ROI Calculator** | ○ | ○ | ○ | ○ | ◐ scaling | **●** | ○ | ◐ charts | ○ | ◐ | **●** financial case |
| **UR ROI Calculator** | ○ | ○ | ○ | ○ | ◐ capacity benefit | **●** | ○ | ◐ | ○ | ◐ | ◐ |
| **Robotiq IQ / ROI** | **●** narrow use case | ◐ | **●** own solution | ◐ | ◐ | **●** | ◐ | ◐ | ○ | ◐ | **●** commercial assessment |
| **Visual Components** | ○ | ◐/● | ○ | **●** | **●** | ○ | ◐ | **●** | **●** | **●** | ◐ engineering |
| **Siemens Process Simulate** | ○ | **●** robot library | ○ | **●** | **●** | ○ | **●/◐** | **●** | **●** | **●** | ◐ engineering |
| **ABB RobotStudio** | ○ | **●** ABB | ○ | **●** | **●** | ○ | **●** assistant | **●** | **●** | **●** | ◐ |
| **DELMIA Robotics** | ○ | ◐/● | ◐ configuration | **●** | **●** | ○ | **●** | **●** | **●** | **●** | ◐ |
| **NVIDIA Isaac Sim** | ○ | ◐ import/ecosystem | ○ | **●** physics | **●** technical | ○ | **●** foundation | **●** | **●** | **●** technical | ○ |
| **Realtime Resolver** | ○ | ○ | ◐ task allocation | **●** | **●** | ○ | **●** | ◐ via simulation stack | **●/◐** | **●** | **●** engineering outputs |
| **Wandelbots NOVA** | ○ | ◐ brand abstraction | ○ | ◐ | ◐ | ○ | **●** | **●** digital twin | **●/◐** | ◐ | ○ |
| **Jacobi Robotics** | ○ | ◐ hardware-agnostic | ○ | **●** motion | **●** motion | ○ | **●** RL | **●** | **●** | ◐ | ○ |
| **Trener Acteris** | ○ | ◐ compatible brands | ○ | ◐ | ◐ | ○ | **●** Physical AI | ◐ | ◐ | ○ | ○ |
| **Qviro** | ○ | **●** marketplace | ◐ discovery | ◐ specs | ○ | ○ | ○/◐ | ◐ | ○ | ◐ products | ○ |
| **Formic** | **●** human service | ◐ internal | **●** human/internal | **●** engineering | **●** service | **●** RaaS economics | ◐ | ◐ | ◐ internal | ◐ | **●** proposal |
| **ReshapeX** | ○ factory / ● sales process | **●** supplier catalog | **●** parts/BOM | **●** compatibility rules | ○ | ○ factory / ● pricing | **●** | ◐ configurator | ○ | ◐ quote variants | **●** BOM/quote |
| **Excel + integrator** | **●** manual | ◐ | **●** expert | **●** expert | **●** manual | **●** | ◐ if added | ◐ | ◐ external | **●** | **●** manual |

Эта матрица хорошо показывает архитектурную проблему рынка. Самый насыщенный верхний левый участок — **HowToRobot**, самый насыщенный engineering участок — **Siemens/DELMIA/Visual Components/ABB**, самый сильный optimization участок — **Realtime Resolver**, а лучший связующий 3D/configuration UX — **Vention**. Но ни одна строка не становится `●` практически во всей цепочке. Это и есть пространство RobCo. Вывод основан на сопоставлении актуальных публичных product workflows и поэтому является аналитической интерпретацией источников. citeturn13search5turn21search0turn19search17turn16search0turn17search13

## Table stakes и реальный market gap

### Что уже является table stakes

Для продукта, который обещает **robotics feasibility assessment**, я бы считал обязательными не три декоративные AI-функции, а пять фундаментальных capabilities.

**Structured process intake + readiness assessment.** Пользователь не должен начинать с dropdown `ABB / FANUC / UR`. Правильная точка входа — операция: что за объект, откуда/куда он движется, масса и размеры, takt/throughput, variability, требуемая точность, process time, shifts, staffing, space, environment и pain points. HowToRobot уже установил высокую планку: можно описывать operation обычным языком, после чего AI задаёт уточняющие вопросы и формирует supplier-ready project brief. Robotiq для palletizing уже показывает, что даже vendor-specific Fit Check должен занимать минуты, а не engineering workshop. citeturn13search5turn15search15

**Constraint-based matching с объяснимыми reject reasons.** Обычного фильтра `payload > 10 kg` недостаточно. RoboDK показывает, насколько большой уже может быть search space — библиотека фильтруется по reach, payload, repeatability, axes и application. Vention добавляет smart component placement, recommendations и design checker. Следующий логичный UX-уровень для RobCo — не просто «вот пять роботов», а **«почему эти три проходят, а эти семь отклонены»**: payload+EOAT margin, reach, wrist moment/inertia, mounting, protection/environment, application fit и требуемая precision. citeturn15search16turn21search0

**Cycle/capacity/fleet model.** Без него robot selection не превращается в feasibility. Realtime Resolver уже делает cycle-time optimization, task allocation и работу с несколькими роботами central value proposition; Siemens также рассматривает cycle time как базовую engineering metric. Поэтому ответ RobCo «этот robot подходит по payload и reach» будет слабым. Нужен хотя бы low-fidelity ответ: **estimated cycle = X–Y sec, one cell capacity = N units/h, target requires K robots/cells**, с явными assumptions. citeturn19search0turn13search3turn16search0

**Economics, связанная именно с техническим сценарием.** ROI calculator сам по себе commodity: A3, UR, Robotiq и HowToRobot уже предлагают такую функциональность. Differentiation возникает, когда economics автоматически питается из engineering model: количество роботов → robot/EOAT/peripherals/integration CAPEX → service/energy/maintenance OPEX → throughput/labor/scrap effects → payback/TCO/NPV. A3 уже показывает expected baseline — purchase, maintenance, electricity и long-horizon comparison; UR напоминает, что benefits должны учитывать scrap, rework, inventory и capacity, а не только заменённые FTE. citeturn15search0turn14search2turn13search4

**Scenario comparison + exportable decision artifact.** В industrial automation недостаточно результата `ROI = 28%`. Менеджеру нужны параллельные варианты: manual baseline, cobot, industrial robot, два robots, high-speed cell, RaaS и, иногда, «не автоматизировать». HowToRobot уже стандартизирует side-by-side supplier quotes и умеет выгружать investment report; Vention мгновенно связывает design с BOM/price; Visual Components продвигает what-if digital comparison. Поэтому RobCo должен заканчивать не chatbot answer, а **auditable preliminary ТЭО**. citeturn13search4turn13search5turn21search0turn17search9

### Где именно находится market gap

Главный gap — не «на рынке нет robot configurators». Их много. Gap — **нет хорошо представленного self-service decision system между spreadsheet/business assessment и full engineering simulation**.

Сегодня типичный путь фактически выглядит так:

`Excel / consultant / HowToRobot → integrator RFQ → ручной robot shortlist → CAD/Visual Components/RoboDK/Process Simulate → несколько итераций engineering → quote → ROI spreadsheet → management approval`.

RobCo может сжать первые несколько этапов до:

`process data → feasibility score → explainable shortlist → low-fidelity capacity → economic scenarios → preliminary TEО → только затем detailed simulation/RFQ`.

Наиболее заметны шесть незакрытых ниш.

**Vendor-neutral `process → SKU` matching.** OEM finders хорошо выбирают внутри FANUC или Yaskawa; RoboDK хорошо даёт cross-brand catalog; HowToRobot хорошо matches project с suppliers/products. Но публичного workflow, который из process requirements автоматически строит **cross-brand ranked robot + EOAT combinations с инженерно объяснимой совместимостью**, я не нашёл. citeturn20search7turn20search15turn15search16turn13search5

**Early hard-constraint checking без полного CAD project.** Сейчас либо слишком легко — datasheet filters, либо слишком тяжело — Process Simulate/RobotStudio/DELMIA/Visual Components. Vention частично закрывает середину своим design checker, но внутри собственного configure-and-buy workflow. Это очень хорошее место для RobCo. citeturn21search0turn16search0turn17search8

**Low-fidelity engineering с uncertainty.** Enterprise simulation стремится к fidelity; ROI calculator часто создаёт иллюзию одной точной цифры. Preliminary ТЭО лучше должно сказать `cycle 8.5–11 s`, `CAPEX €170–230k`, `payback 17–25 months`, показать, какие assumptions создают диапазон, и объяснить, какие данные уменьшат неопределённость. Ни один из исследованных продуктов не демонстрирует это как центральное cross-vendor UX-positioning; это вывод из рассмотренных workflows. citeturn13search4turn15search0turn16search0turn21search0

**Engineering + economics в одном causal model.** Сегодня экономические tools считают business case, а simulators — robot physics. Даже очень сильный Resolver фокусируется на path/task/cycle optimization, а HowToRobot Investment Calculator — на process cost/savings. Самая ценная связь для RobCo — сделать так, чтобы изменение `robot`, `gripper`, `cycle`, `fleet size` или `shift pattern` автоматически пересчитывало TCO и payback. citeturn19search17turn13search4

**Automation vs alternative automation.** Почти все vendor tools оптимизируют уже выбранный тип решения. Neutral RobCo может честно выдать: `robotic automation not recommended`, `semi-automatic fixture has better economics`, `cobot cannot hit takt`, `two low-cost robots beat one high-payload unit`, `RaaS preferable because demand uncertainty is high`. Именно последняя возможность отличает *feasibility tool* от *robot-sales configurator*.

**Traceability/provenance.** ReshapeX даёт важный UX-сигнал для industrial AI: AI должен быть grounded в catalog, compatibility rules, datasheets, approved substitutes и pricing data, а не «знать роботов» из языковой модели. Для RobCo это особенно критично: recommendation должен ссылаться на исходный datasheet/constraint и показывать формулу. citeturn20search2

Из этого следует важный продуктовый принцип: **LLM не должен быть инженерным truth engine RobCo**. Его сильное место — превратить свободное описание процесса в structured variables, выявить missing information и объяснить результат. Payload/reach eligibility, capacity и economics должны рассчитываться deterministic rules/model code; detailed geometry при необходимости передаётся simulator. Это не только уменьшает hallucination risk, но и создаёт намного более сильную демонстрацию для industrial audience.

## Какие позиционирования уже заняты

Рынок уже достаточно насыщен, поэтому несколько очевидных pitch lines для RobCo я бы сознательно не использовал.

| Занятое positioning | Кто уже занимает | Почему RobCo не стоит идти лоб в лоб |
|---|---|---|
| **“Find what to automate, define it, get suppliers and quotes”** | **HowToRobot** | Практически буквальное совпадение с верхней частью RobCo. Текущий продукт уже имеет AI intake, supplier/product matching, budgetary quotes, comparison и investment calculator. citeturn13search5turn13search4 |
| **“Design your automation cell online and buy it”** | **Vention** | Очень сильный 3D/configure/BOM/price/order UX и огромная modular-component library. citeturn21search0 |
| **“Multi-brand robot simulation / offline programming”** | **RoboDK, Visual Components** | Зрелые products с robot libraries и значительно более глубокой simulation capability, чем разумно строить на hackathon. citeturn15search16turn17search13 |
| **“Enterprise digital twin / virtual commissioning”** | **Siemens, DELMIA, ABB** | Это десятилетия engineering capability, controller/PLC integration и enterprise workflows. citeturn16search16turn16search2turn17search8 |
| **“No-code/zero-programming robotic applications”** | **OnRobot D:PLOY** | Сильный guided workflow для конкретных applications с auto path/program generation. citeturn14search0turn14search9 |
| **“AI robot path/cycle optimization”** | **Realtime Robotics Resolver** | Уже очень убедительное industrial-AI proposition вокруг cycle time, task allocation, interlocks и path generation. citeturn19search0turn19search17 |
| **“Robot-agnostic software operating system”** | **Wandelbots NOVA** | Hardware abstraction across major robot brands уже является explicit core positioning. citeturn19search34 |
| **“Physical AI that makes industrial robots adaptive”** | **Trener / Jacobi** | Здесь конкурентная битва идёт за adaptive execution, RL, vision/action and skills, а не за investment planning. citeturn19search3turn19search9 |
| **“AI application engineer / AI quoting for industrial automation”** | **ReshapeX** | RFP→BOM, Quote, Substitute и compatibility-grounded AI уже заняты seller-side productом. citeturn20search2 |
| **“Robotics-as-a-Service, no CapEx”** | **Formic** | Full-service automation + fixed monthly cost + operations/maintenance уже является мощным, хорошо сформулированным business model. citeturn20search1 |
| **“Robot marketplace / compare suppliers”** | **HowToRobot, Qviro** | Discovery и procurement сами по себе не дадут RobCo defensible differentiation. citeturn13search5turn20search0 |
| **“Robot ROI calculator”** | **A3, UR, Robotiq и др.** | Это уже table-stakes utility и часто бесплатный lead magnet. citeturn15search0turn14search2turn15search2 |

Поэтому наиболее свободное positioning звучит не как перечисление технологий, а как **job-to-be-done**:

> **RobCo tells a manufacturer whether a process is robot-ready, which realistic robot-cell options fit, how many are needed, and whether the investment makes sense — before paying for detailed engineering.**

Ещё более дифференцированная версия:

> **From process description to an evidence-backed preliminary automation feasibility study in minutes.**

И очень сильная B2B формулировка для integrators/OEMs:

> **Turn an unqualified automation lead into an engineering-ready opportunity.**

Последняя версия потенциально превращает HowToRobot и integrators не только в конкурентов, но и в channel/customer: RobCo может быть **pre-sales qualification engine**, выдающим structured constraints, shortlist, cycle model и economics до дорогостоящей application-engineering работы. То, что HowToRobot уже прямо продаёт suppliers сокращение early qualification/scoping effort, подтверждает наличие этого pain point на стороне поставщика. citeturn13search7

## Как RobCo лучше показать на хакатоне

Для хакатона стратегическая ошибка — пытаться сделать miniature Visual Components или Isaac Sim. У этих платформ преимущество в simulation fidelity, которое невозможно правдоподобно догнать за короткий срок. Намного сильнее показать **полный decision loop**, который существующие tools заставляют пользователя собирать из четырёх-пяти продуктов.

Оптимальный demo-flow я бы сделал таким:

**Процесс.** Пользователь пишет или диктует: «Оператор берёт 8-килограммовые коробки 600×400×300 мм с конвейера, поворачивает на 90°, укладывает на паллету; 14 коробок/мин, две смены, пространство 2.5×2.5 м, зарплата оператора X». Можно разрешить загрузить фото layout или простой sketch. AI превращает это в structured process model и подсвечивает missing information. UX-референс здесь — HowToRobot: natural-language operation description + intelligent follow-up questions. citeturn13search5

**Readiness.** RobCo выдаёт не бинарное `yes/no`, а несколько блоков: repetitiveness, part variability, presentation consistency, cycle pressure, safety/environment, space, integration complexity. Например: `Automation readiness 78/100; main uncertainty: box presentation and pallet changeover`. Это слой, который симуляторы обычно считают уже решённым.

**Matching.** Даже для hackathon достаточно качественного curated catalog из, например, 20–50 arm models и нескольких grippers. Важно не количество, а демонстрация **hard filter → scoring**. RoboDK показывает, какие базовые fields ожидаются от серьезного robot catalog: reach, payload, repeatability, robot type/application. citeturn15search16

Экран должен показывать примерно такой reasoning:

`FANUC X — rejected: effective payload requirement 13.2 kg > allowable payload with safety margin.`

`UR Y — technically feasible, but estimated cycle misses takt by 18%.`

`ABB Z — feasible; 24% reach margin; one-cell throughput 890 units/shift.`

То есть главный visual trick — **не “AI recommends ABB”**, а **“constraints eliminated 37 of 42 configurations; here is why”**.

**Capacity.** Затем RobCo строит low-fidelity cycle decomposition:

`approach 0.8s + grip 0.35s + loaded move 1.6s + place 0.5s + return 1.3s + allowance = 5.1–5.8s`.

После этого становится возможен действительно полезный output:

`required takt = 4.29 s → one cell cannot meet target → either two robots or faster layout/gripper.`

Realtime Robotics демонстрирует, насколько значим именно cycle/task-allocation layer в реальном industrial design. RobCo не нужно повторять его path optimizer; достаточно сделать early estimate и честно показать confidence. citeturn13search3turn19search4

**Economics.** Для каждого технически валидного варианта автоматически формируется один economic model. В отличие от обычного ROI calculator, пользователь **не вводит CAPEX и robot count повторно**: они уже получены из chosen configuration/capacity.

Например:

| | Scenario A | Scenario B | Scenario C |
|---|---:|---:|---:|
| Architecture | 1 high-speed industrial robot | 2 cobots | manual baseline |
| Feasibility | 91% | 86% | baseline |
| Capacity | 15.2 boxes/min | 14.7 boxes/min | 14 boxes/min |
| Estimated CAPEX | €190–225k | €145–185k | €0 |
| Annual OPEX | €X | €Y | €labor |
| Payback | 19–23 mo | 24–31 mo | — |
| Five-year TCO | €… | €… | €… |
| Main risk | guarding/layout | two-cell coordination | labor availability |
| Confidence | medium-high | medium | high |

Это принципиально сильнее standalone ROI calculators, поскольку **engineering choice причинно связан с economics**. В качестве financial design references разумно взять A3 для lifecycle ownership costs, UR для scrap/rework/capacity benefits и HowToRobot для management-oriented scenario report. citeturn15search0turn14search2turn13search4

**Visualization.** Не надо делать photorealistic physics. Хакатонному productу достаточно автоматически построить схематичный 2D/top-down или простой WebGL/Three.js layout: robot base, reach envelope, pickup/drop zones, obstacles и pallet/conveyor. Важнее показать красным unreachable/collision-risk geometry и зелёным feasible area. Vention — лучший референс ощущения «из параметров сразу появился понятный spatial solution», а Visual Components — референс того, как хорошо manufacturing stakeholders реагируют на visual factory model. citeturn21search0turn17search13

**Preliminary ТЭО.** Финальный экран должен быть главным wow-moment: одна кнопка **Generate preliminary feasibility study**.

Не generic LLM essay, а структурированный документ:

`Objective → current process → assumptions → readiness → recommended architectures → constraint check → robot/EOAT shortlist → capacity calculation → economics → scenario comparison → risks/open questions → recommended next validation → sources/datasheets`.

Каждая важная цифра кликабельна: пользователь видит источник или формулу. HowToRobot уже задаёт expectation, что assessment должен заканчиваться structured management report; RobCo может отличиться тем, что добавит к этому **engineering evidence chain**. citeturn13search4

Самая выигрышная hackathon-функция, на мой взгляд, — **live scenario slider**. Пользователь меняет required throughput с 14 до 18 units/min, зарплату с €25 до €35/h или shifts с одной до трёх, и RobCo в реальном времени:

`recalculates capacity → invalidates one robot → changes fleet size → updates CAPEX/TCO → changes recommendation → regenerates ТЭО`.

Это буквально визуализирует цепочку, ради которой RobCo существует.

Архитектурно demo лучше разделить на три truth layers:

`LLM = extraction + clarification + explanation`

`Rule/calculation engine = constraints + cycle + economics`

`Catalog/evidence layer = robot specs + EOAT compatibility + pricing ranges`

Так RobCo выглядит не как очередной «ChatGPT wrapper for robotics», а как **AI interface over a deterministic techno-economic decision engine**. В этом смысле ReshapeX — особенно полезный reference: его current industrial-AI proposition специально опирается на catalog, compatibility rules, datasheets и controlled pricing knowledge, а не на общие знания LLM. citeturn20search2

## Лучшие UX и reference products

Если команде RobCo нужно выбрать всего пять-шесть продуктов для разбора экран-за-экраном, я бы расставил приоритет так.

**Vention MachineBuilder — лучший общий UX reference.** Это самый убедительный пример того, как industrial engineering можно сделать похожим на современный consumer-grade configurator: drag-and-drop, smart placement, AI recommendations, immediate design checking, real-time BOM, assembly time, pricing и digital twin в браузере. RobCo стоит копировать не функциональную глубину Vention, а принцип **instant feedback after every user decision**. citeturn21search0turn13search0

**HowToRobot — лучший reference для входа от бизнес-проблемы.** Именно он ближе всего к началу RobCo. Пользователь не обязан знать robotics terminology; система начинает с operation, volumes и pain points, задаёт follow-ups, создаёт project brief, оценивает market availability, а затем ведёт через supplier quotes и comparison. Особенно важно изучить текущий 2026 UX, а не старые обзоры: продукт заметно эволюционировал в сторону AI-driven automation planning. citeturn13search5

**OnRobot D:PLOY — лучший reference для guided application setup.** Очень хороший lesson: от пользователя запрашивается только то, что действительно необходимо на текущем шаге. Hardware auto-discovery → workspace/obstacles → workpiece/pick position → automatically generated path/program → operate/monitor. RobCo нужен похожий progressive disclosure: сначала десять business/process variables, затем только те engineering questions, которые реально меняют feasibility. citeturn14search0

**Realtime Robotics Resolver — лучший reference для технического scenario engine.** Для RobCo особенно интересна не graphics, а product concept: automation engine берёт сложную optimization problem и возвращает cycle-target-driven answer, automatically reallocating tasks across robots. Именно такое ощущение «система действительно посчитала, а не просто подсказала» нужно воспроизвести на меньшей fidelity. citeturn13search1turn19search4

**Visual Components — лучший visual/digital-factory reference.** В 2026 году продукт напрямую объединяет factory layout planning, process simulation, OLP и virtual commissioning. RobCo не должен копировать complexity, но должен заимствовать визуальный язык: equipment in spatial context, flow, operating envelope, state/scenario comparison. citeturn17search13

**A3 Calculator — лучший reference для прозрачной экономики.** Не самый эффектный UI, зато логика понятна: manual versus robotic system, purchase, maintenance, electricity, 20-year ownership. RobCo может сделать значительно красивее и глубже, но нельзя потерять такую же прозрачность assumptions. citeturn15search0

Если свести это к одной продуктовой формуле, идеальный RobCo UX выглядел бы как:

**HowToRobot intake  
+ Vention immediacy  
+ RoboDK catalog breadth  
+ Realtime Resolver capacity reasoning  
+ A3 economics transparency  
+ Visual Components spatial clarity  
− enterprise simulation complexity.**

Именно такая комбинация пока выглядит наиболее слабо занятой.

Самый важный стратегический вывод исследования: **не пытаться выиграть “больше AI”, “больше robots” или “лучше simulation”.** Рынок уже имеет очень сильных специализированных игроков по каждому из этих направлений. У RobCo есть шанс выиграть за счёт **последовательности решения** и **связности данных**: однажды введённые process parameters проходят через readiness, matching, constraints, cycle, fleet и economics без ручного переноса между Excel, selector, simulator и proposal. HowToRobot доказал ценность раннего structured planning, Vention — ценность instant configurable engineering, Realtime — ценность automated cycle optimization, а классические digital-twin platforms — ценность engineering validation. RobCo может стать недостающим **decision layer, который связывает эти миры до начала дорогого detailed engineering**. citeturn13search5turn21search0turn19search0turn16search0turn17search13