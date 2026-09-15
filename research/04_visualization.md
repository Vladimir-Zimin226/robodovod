# Visualization MVP для RobCo: UX-паттерны layout planning, warehouse flow, fleet planning и digital twin

## Главный вывод для RobCo

Лучший двухнедельный результат для RobCo — **не пытаться клонировать AnyLogic/FlexSim/Visual Components как simulation product**, а собрать убедительный **interactive scenario visualizer**: план помещения → зоны и маршруты → движущиеся агенты → heatmap → KPI → переключение Base/Scenario → playback. Именно эта комбинация визуально считывается пользователем как «мы понимаем будущий поток», при этом не требует discrete-event simulation, физики, диспетчеризации, collision avoidance или статистического моделирования.

Исследованные продукты почти всегда разделяют две сущности: **геометрию сцены** и **операционную семантику**. Autodesk Factory Design Utilities накладывает Stations, Products и Routings поверх layout; Azure Digital Twins связывает 3D-elements с twins и behaviors; AWS TwinMaker связывает элементы сцены и точки пространства с данными; OTTO Fleet Manager накладывает points of interest и traffic rules на карту помещения. Это наиболее важный архитектурный паттерн для RobCo. citeturn19view1turn19view14turn19view16turn19view17

Второй общий паттерн — **canvas является главным носителем истории**, а таблицы и KPI вторичны. Visual Components строит опыт вокруг 3D-layout и process flow, RoboDK — вокруг 3D station с деревом объектов, AnyLogic/FlexSim — вокруг анимированной модели и результатов, OTTO/MiR — вокруг карты движения fleet. citeturn19view4turn19view13turn19view9turn19view17turn20search4

Третий паттерн — наиболее эффектные аналитические слои на самом деле можно сделать **без simulation engine**. Autodesk FDU, например, визуализирует направления routing, transportation indicators, интенсивность связей и показатели стоимости/расстояния; Siemens использует Sankey-представление material flow; AnyLogic и FlexSim показывают density/heat-map поверх геометрии. Для RobCo можно построить аналогичные слои из **заданных маршрутов, nominal speed, trips/hour и статических весов**, ясно называя их planned flow / traffic load, а не предсказанием congestion. citeturn19view2turn19view3turn19view7turn19view11

**Моя рекомендация по “wow-effect / dev hour”:**

| Паттерн | Wow | Стоимость | Для MVP |
|---|---:|---:|---|
| Animated AMR/люди вдоль маршрутов + trails | 5/5 | 2/5 | **Да** |
| Heatmap planned movement density | 5/5 | 2/5 | **Да** |
| Base ↔ Scenario с мгновенными KPI delta | 5/5 | 2/5 | **Да** |
| Толщина/цвет маршрута по flow + бегущие direction pulses | 4/5 | 1/5 | **Да** |
| Floating KPI chips прямо над зонами | 4/5 | 1/5 | **Да** |
| Zones: restricted / slow / pickup / drop-off | 4/5 | 1–2/5 | **Да** |
| Красивые top-down/isometric sprites + мягкие shadows | 4/5 | 2/5 | **Да** |
| Timeline со scrubber и x0.5/x1/x2/x4 | 4/5 | 2/5 | **Да** |
| Настоящий 3D editor | 5/5 | 5/5 | Нет |
| Реальная fleet dispatch optimization | 5/5 | 5/5+ | Нет |
| DES/agent simulation | 5/5 | 5/5+ | Нет |

Иными словами, **RobCo должен выглядеть скорее как “AnyLogic/FlexSim result view + OTTO map editor + Azure Digital Twin viewer”, чем как настоящий simulation IDE**. Это существенно лучше соответствует двухнедельному горизонту.

## Benchmark продуктов и UX-паттернов

Ниже `before/after` означает не обязательно встроенную одноимённую функцию продукта, а то, насколько UX поддерживает сравнение альтернативных configurations/runs. Там, где продукт действительно пересчитывает динамическую модель, я отдельно отмечаю это как **real simulation**, чтобы не смешивать это с тем, что разумно реализовать в RobCo.

| Референс | Input | Canvas model | Zones / routes / agents | Before / after и what-if | KPI overlay и heatmaps | Playback / timeline | Screenshot / video / source |
|---|---|---|---|---|---|---|---|
| **Autodesk Factory Design Utilities — layout/material flow** | 2D factory layout, factory assets; Material Flow задаётся через **Stations, Products, Routings**. Есть импорт material-flow данных; отдельные route properties включают processing/setup/transport parameters. citeturn19view0turn19view1 | AutoCAD-план служит основой; рядом Asset Browser, Material Flow и Factory Properties. Layout можно продолжить в связанных factory-design инструментах Autodesk. citeturn19view0 | Station — семантическая точка/область процесса; Routing соединяет stations направленными линиями. Особенно важно: Autodesk прямо описывает routes как линии между connectors с оценочным distance, **а не как фактическую геометрию транспортного lane/path**. Это отличный precedent для RobCo lightweight flow visualization. citeturn19view1 | Material-flow analysis позволяет сравнивать варианты через вычисляемые transportation indicators без необходимости делать из каждой линии физически точную траекторию. citeturn19view1turn19view2 | Gauges/indicators для transportation metrics; travel distance/time; визуальные флаги для высокой station intensity, а connections могут сигнализировать интенсивность flow. citeturn19view2 | Это прежде всего layout/analysis workflow, а не cinematic simulation timeline. Для RobCo отсюда стоит брать **overlay**, не playback. citeturn19view0turn19view1 | Официальные Autodesk Help-страницы **Finding Your Way Around AutoCAD Factory**, **Creating and Analyzing Material Flow** и **Transportation Indicators** содержат UI/screenshots и являются лучшими визуальными референсами. citeturn19view0turn19view1turn19view2 |
| **Siemens Tecnomatix Plant Simulation — material-flow visualization** | Производственная структура, process/material-flow logic, resources и CAD geometry используются для построения динамической модели. citeturn19view3 | 2D/3D представление производственной системы; Siemens отдельно подчёркивает 3D-enabled material-flow visualization на реальной CAD geometry. citeturn19view3 | Потоки идут между производственными ресурсами; 3D-модели robots, warehouses, conveyors и другого оборудования дают физический контекст. citeturn19view3 | Это **real simulation**: layout, control logic и dimensioning можно менять и исследовать поведение системы. citeturn19view3 | Особенно полезный паттерн — **Sankey Diagram** для быстрого понимания material flows плюс bottleneck analyzer/statistics. citeturn19view3 | Динамическое поведение является частью simulation model; это значительно глубже, чем предлагаемый RobCo playback. citeturn19view3 | Официальная Siemens-страница **Introduction to Plant Simulation** содержит embedded introduction video и объяснение Sankey/bottleneck analysis — хороший референс именно для визуального языка. citeturn19view3 |
| **Visual Components** | CAD/2D drawings и готовые manufacturing components; layout собирается визуально, process modeling задаёт взаимодействие ресурсов, людей и robots. citeturn19view4turn18search5 | Главная метафора — **editable 3D factory layout** с drag-and-drop assets; process workflow и statistics существуют вокруг этого spatial canvas. citeturn19view4 | Conveyors, machines, warehouse components, robot/human transports и process routing превращаются в визуальную производственную сцену. Academy отдельно обучает routing/process-modeling workflow. citeturn18search5turn18search1 | Продукт организует story как **Design → Model → Simulate → Analyze → Optimize → Share**; таким образом альтернативы должны быть не просто геометрическими версиями, а проверяемыми simulation scenarios. citeturn18search1 | Statistics Dashboard поддерживает charts/series, sampling interval, hover inspection, zoom/pan/focus range и экспорт данных. Это хороший источник для RobCo KPI side panel, но сам numerical output в VC основан на simulation. citeturn19view5 | Simulation run является частью основного продукта; Visual Components также ориентирован на визуальное presentation/share результатов. citeturn18search1turn19view4 | **Visual Components Manufacturing Simulation** даёт product screenshots; официальный video **Setting up a manufacturing simulation workflow step-by-step** показывает всю цепочку от design до share; Academy — компоненты warehouse/layout. citeturn19view4turn18search1turn18search5 |
| **AnyLogic** | Process parameters, material-handling networks, transporters/AGV, conveyors, pedestrians и другие model objects; what-if задаётся параметрами simulation experiments. citeturn20search0turn20search1 | Модель объединяет spatial canvas с animation и аналитическими widgets. Density Map может быть привязан к пространству/paths и динамически перекрашиваться во время run. citeturn19view7 | Для spatial movement AnyLogic моделирует агентов/transporters, а density layer может работать как по пространству, так и вдоль network paths. citeturn19view7 | Один из сильнейших what-if UX: **Parameter Variation** запускает серию runs с различными model parameters; Compare Runs позволяет сохранять outputs разных runs на charts. Это настоящий simulation comparison, а не UI-only diff. citeturn20search0turn20search5 | Density Map умеет `Maximum`/`Mean`, complete-run/sliding-window представления, threshold/legend/transparency. Это почти готовая UX-спецификация RobCo heatmap, хотя значения RobCo должны рассчитываться иначе. citeturn19view7 | В AnyLogic animation синхронизирована с simulation time; experiments повторно запускают модель. citeturn20search0turn20search1 | Официальный **AnyLogic Help: Density Map** содержит screenshots и настройки heatmap; **Parameter Variation** и **Compare Runs** — source для scenario UX. citeturn19view7turn20search0turn20search5 |
| **Autodesk FlexSim** | Objects/resources, arrival/process logic, AGV networks, scenario parameters; Autodesk описывает factory simulation как data-driven discrete-event modeling с scenario/experiment management. citeturn19view9 | Центральная 3D simulation scene + dashboards/results. Готовые object libraries позволяют собирать system визуально. citeturn19view9 | AGV network включает paths/control logic; tutorial рассматривает layouts, dispatching, load balancing и capacity. A* navigation дополнительно предоставляет grid/navigation layer. citeturn19view10turn19view11 | **Scenario/Experiment Manager** и side-by-side what-if comparison — один из наиболее прямых референсов для RobCo Scenario A/B UI, но FlexSim действительно перезапускает DES. citeturn19view9 | Results dashboards показывают simulation outputs; A* tooling также имеет heat-map visualization по выбранному criterion. citeturn19view9turn19view11 | Time/event behavior — часть DES; AGV model включает более реалистичную динамику движения и traffic interactions, чем допустимо имитировать в MVP. citeturn19view10 | Официальная Autodesk **Factory Simulation / FlexSim** page содержит product imagery/video; официальный **AGV tutorial** и **A* Navigation** — screenshots конкретных fleet/network/heat-map mechanisms. citeturn19view9turn19view10turn19view11 |
| **RoboDK** | Robot station: robots, objects/CAD, tools, reference frames, targets и programs; поддерживаются типичные 3D CAD/mesh inputs, объекты можно загружать в station. citeturn19view13 | Классический engineering UX: **Station Tree слева + large 3D viewport + toolbar**; viewport поддерживает pan/rotate/zoom. citeturn19view13 | Семантика строится вокруг robot, frame, tool, target и motion instructions, а не warehouse zones. citeturn19view13 | Изменение targets/layout даёт возможность проверять robotic alternatives, но смысл продукта — real robot simulation/offline programming. citeturn19view13 | Warehouse heatmap/KPI overlay — не его центральный UX. Зато **tree + viewport + selected-object properties** — сильный шаблон для RobCo object inspector. citeturn19view13 | Programs запускаются как robot simulation; station можно экспортировать/share как web/3D representations. citeturn19view13 | RoboDK **Basic Guide** очень полезен как screenshot/video source: документ показывает window, Station Tree, 3D navigation, building station, targets/programs и содержит официальные video tutorials. citeturn19view13 |
| **Azure Digital Twins 3D Scenes Studio + AWS IoT TwinMaker — digital twin dashboards** | Azure: `.gltf/.glb` scene + mappings к digital twins; AWS: 3D scene/models + entity/property bindings и operational data. citeturn19view14turn19view15turn19view16 | **Scene Viewer/Builder** вместо simulation editor: spatial geometry является “холстом”, поверх которого добавляется business context. Azure разделяет Build/View modes. AWS Scene Composer связывает visualization с twin data. citeturn19view14turn19view15turn19view16 | Azure elements соответствуют 3D meshes/twins; behaviors задают visual rules, badges/widgets; layers дают различные operational views. AWS tags/scene bindings закрепляют operational information в точке/объекте пространства. citeturn19view14turn19view15turn19view16 | Не simulation what-if по умолчанию. Ключевой UX — **live/current state vs historical data/context**, что для RobCo важнее как future telemetry mode. citeturn19view14turn19view15turn19view16 | Azure visual rules могут менять mesh appearance и badges; widgets показывают свойства/history. AWS интегрируется с Grafana-style operational dashboards. citeturn19view15turn19view16 | Azure поддерживает анимацию из 3D asset и historical widgets, но timeline здесь относится к data/state, а не DES. citeturn19view15 | Microsoft Learn **3D Scenes Studio concepts/use** содержит screenshots Builder/Viewer и rules; AWS **What is IoT TwinMaker?** показывает Scene Composer architecture. citeturn19view14turn19view15turn19view16 |
| **OTTO Fleet Manager + MiR Fleet — AGV/AMR fleet planning/operations** | OTTO workflow начинается с mapping facility, затем пользователь добавляет points of interest и traffic rules/workflows. MiR централизует missions, robot status и traffic. citeturn19view17turn20search4 | **Facility map как главный canvas**. Это самый близкий к предлагаемому RobCo UX из всех референсов. citeturn19view17turn20search4 | OTTO показывает chargers/drop-off/parking и “rules of the road”: one-way, speed-limit и stop-related semantics; более новые tooling concepts группируют map elements/zones/lanes и endpoints. MiR Fleet управляет traffic flow fleet. citeturn19view17turn19view19turn20search4 | Fleet software оптимизирует actual assignments/operations. Для RobCo безопасно копировать **scenario map editing**, но не обещать идентичную fleet optimization. citeturn19view18turn20search4 | OTTO описывает dashboards для live production/bottleneck trends; MiR Insights позиционируется как visualize/analyze/optimize слой fleet data. citeturn19view18turn20search7 | В operation mode состояние robots обновляется во времени; это live fleet monitoring, а не обязательно offline simulation. citeturn19view18turn20search4 | **OTTO: Introduction to Fleet Manager** — особенно ценный официальный пяти-минутный video walkthrough map → POIs → traffic rules → workflow. OTTO product/blog и MiR Fleet pages содержат дополнительные screenshots. citeturn19view17turn19view19turn20search4 |

Самые полезные референсы для непосредственного копирования UX — **OTTO для map semantics**, **AnyLogic для heatmap controls**, **FlexSim для scenarios/KPI comparison**, **Visual Components для “живой” presentation**, **Azure Digital Twins для inspector/layers/status overlays**, **RoboDK для object tree + viewport**, а **Autodesk FDU и Siemens Sankey** показывают, как сделать flow визуально убедительным даже при относительно простой network representation. citeturn19view17turn19view7turn19view9turn19view4turn19view14turn19view13turn19view2turn19view3

## Паттерны с максимальным wow-effect на час разработки

**Паттерн “geometry underneath, semantics above”.** Floor plan/racks/rooms должны быть почти пассивным background layer. Отдельно существуют `zones`, `nodes`, `routes`, `agents`, `metrics`. Это очень близко к Autodesk Station/Routing, Azure element/behavior и OTTO POI/traffic-rule подходам. Пользователь понимает визуализацию даже тогда, когда underlying floor plan — обычная картинка. citeturn19view1turn19view14turn19view17

Это позволяет сделать практически бесплатный input workflow:

**Upload floorplan → Set scale → Place zones/endpoints → Draw routes → Select agent profile → Enter flow → Play.**

CAD/DXF/BIM ingestion в первые две недели не нужен. Достаточно PNG/JPEG/SVG background и калибровки масштаба двумя кликами: «эта линия = 10 m». С точки зрения perceived sophistication семантические overlays дают гораздо больше, чем сложный CAD importer.

**Паттерн “route carries data”.** Линия должна показывать одновременно topology и operational meaning:

`width ∝ trips/hour`  
`moving chevrons = direction`  
`opacity/color class = load index`  
`hover = from → to, distance, nominal time, trips/h`

Именно Sankey в Plant Simulation делает flow визуально мгновенно понятным, а Autodesk FDU уже использует connection lines и transportation indicators как аналитическую надстройку над layout. citeturn19view3turn19view2

Для RobCo это может быть простой derived metric:

\[
\text{routeLoad}=
\frac{\text{trips/hour}\times \text{nominal traverse time}}
{3600\times \max(1,\text{lane capacity proxy})}
\]

Но UI следует называть его **Traffic load index** или **Planned route load**, а не «вероятность пробки».

**Паттерн “heatmap makes planning look intelligent”.** AnyLogic Density Map поддерживает legend, thresholds, transparency и разные временные modes; FlexSim также применяет heat-map layer в navigation analysis. Именно такой overlay моментально переводит статическую карту в категорию «аналитический инструмент». citeturn19view7turn19view11

В RobCo heatmap можно получить вообще без моделирования. Для каждого route discretize polyline в точки/grid cells и добавить вес:

\[
w_{cell} +=
\text{tripsPerHour} \times
\frac{\text{segmentLength}}{\text{speed}}
\]

После normalization и небольшого Gaussian blur получится **planned movement density**. Если два route проходят через один corridor, он естественно загорится сильнее. Это выглядит очень похоже на traffic simulation output, но математически остаётся честным aggregate visualization.

**Паттерн “moving agents prove the story”.** Пользователь значительно легче понимает flow, если по маршрутам едут AMR, baggage cart или hospital delivery robot. Но эти агенты не обязаны принимать решения. Достаточно равномерного path-following с dwell в pickup/drop-off points. Настоящие AGV tools моделируют значительно более сложное поведение — FlexSim рассматривает dispatching, speed dynamics и traffic interactions, а fleet managers действительно выбирают robots и управляют traffic. citeturn19view10turn19view18turn20search4

Следовательно, RobCo animation может быть **deterministic storyboard**:

`spawn → travel → dwell → travel → loop`

На экране пользователь увидит fleet, но под капотом это контролируемое воспроизведение scenario assumptions.

**Паттерн “what-if = one click, not configuration wizard”.** AnyLogic и FlexSim дают мощные experiment managers, однако для двухнедельного продукта пользователю достаточно `Base | Scenario A | Scenario B` и нескольких sliders/fields: Fleet size, trips/hour, nominal speed, route enabled, dwell time. Настоящие продукты пересчитывают simulation runs; RobCo должен пересчитывать только deterministic planning metrics и visualization. citeturn20search0turn20search5turn19view9

Самый выгодный visual trick — **не split screen**, а мгновенный morph:

> `Base` → нажать `Scenario B` → маршруты/agents плавно перестраиваются за 300–500 ms → KPI chips пересчитываются и показывают `↓ 18% distance`, `↑ 24% nominal capacity`, `2 high-load crossings`.

Дешевле side-by-side renderer, но в презентации воспринимается как сильный what-if engine.

**Паттерн “digital twin status grammar”.** Azure 3D Scenes Studio использует elements + behaviors, visual rules, mesh coloring, badges, widgets и layers; AWS TwinMaker также накладывает operational information на spatial scene. Именно этот визуальный язык стоит использовать для RobCo, даже если сначала данные не live. citeturn19view14turn19view15turn19view16

Например:

`AMR-04  ● Moving  67%`  
`Packing 2  ● High load`  
`Route R7  ▲ 82% planned load`  
`Zone Z3  ⚠ Restricted`

При подключении реальной telemetry позже renderer не меняется — меняется только источник данных.

## Visualization MVP для двух недель

При рабочем допущении **один сильный React/frontend engineer, частичная помощь дизайнера и уже существующий RobCo application shell**, я бы намеренно ограничил core MVP следующим набором.

**Обязательный canvas.** Full-screen 2D floor-plan editor с pan/zoom, grid, fit-to-view, selection, drag-and-drop и object inspector. Input первого релиза: prebuilt scene template или PNG/JPEG/SVG floorplan; scale calibration; ручная расстановка объектов. Это воспроизводит центральную spatial metaphor всех ключевых референсов, не затягивая команду в CAD/BIM ingestion. citeturn19view0turn19view4turn19view13turn19view17

**Обязательные primitives:** `asset`, `zone`, `endpoint`, `route`, `agent`. Этого достаточно почти для всех трёх demo verticals.

| Primitive | Что пользователь делает | Что видит |
|---|---|---|
| Asset | drag/drop rack, station, gate, bed | physical context |
| Zone | draw rect/polygon | fill + border + label |
| Endpoint | click/place Pickup, Drop-off, Charger | pin/status badge |
| Route | polyline между endpoints | arrows, flow width, tooltip |
| Agent | выбрать AMR/person/cart profile | moving sprite + trail |

Такое разделение повторяет общую идею Station/Routing у Autodesk, element/behavior у Azure и POI/traffic semantics у OTTO. citeturn19view1turn19view14turn19view17

**Обязательные zone types:** normal operational zone, restricted/no-go, slow-speed, pickup/drop-off, charging/parking и high-priority corridor. OTTO уже использует one-way/speed-related spatial rules и operational POIs, поэтому пользователи robotics software знакомы с этой ментальной моделью. citeturn19view17turn19view19

**Обязательный flow layer:** arrows, moving dashes/chevrons, variable line width и traffic-load state. Hover/selection открывает:

> Receiving → Packing  
> 42.3 m  
> 32 planned trips/h  
> 1.2 m/s nominal speed  
> 35 s nominal travel time  
> High shared-corridor load

Это даёт большой analytical wow почти исключительно силами renderer и geometry utilities; сам принцип visual flow emphasis подтверждается Autodesk transportation overlays и Siemens Sankey. citeturn19view2turn19view3

**Обязательная agent animation:** 3–30 видимых AMR/robots/people/carts с deterministic movement по predefined routes. Выбранный agent получает glow/outline, label и короткий tail. В endpoint он может остановиться на `dwellSec`, после чего продолжить следующий leg.

**Обязательный heatmap:** toggle `Traffic heatmap`. UI должен иметь небольшую legend `Low → High`, opacity slider и tooltip **“Planned movement density — derived from configured routes and flows”**. Эта framing особенно важна, потому что AnyLogic heatmap является результатом динамической model data, тогда как RobCo MVP будет visualization from assumptions. citeturn19view7

**Обязательный KPI HUD** лучше разместить прямо над canvas, а не уводить пользователя на отдельный Analytics screen:

| KPI для MVP | Как считать без simulation |
|---|---|
| Total route length | сумма geometry длины active routes |
| Weighted travel distance | `Σ distance × trips/h` |
| Nominal travel time | `distance / configured speed + dwell` |
| Planned moves/hour | сумма configured flows |
| Fleet load proxy | workload time / available fleet time |
| Shared-corridor load | overlap weighted by configured flow |
| High-load segments | count segments above derived threshold |
| Coverage / serviced endpoints | active endpoints reachable by routes |

Это должны быть **derived planning KPIs**, а не заявленные throughput/queue predictions. Contrast здесь принципиален: FlexSim/AnyLogic действительно получают показатели из simulation experiments, Visual Components выводит simulation statistics, а RobCo на этом этапе должен показывать прозрачные deterministic formulas. citeturn19view5turn19view9turn20search0

**Обязательное A/B.** Пользователь нажимает `Duplicate scenario`, меняет fleet count/routes/speed/flow и получает delta chips:

`Weighted distance  12.4 km/h  ↓ 16%`  
`High-load segments  5  →  2`  
`Fleet load proxy  74%  ↓ 9 pp`

Именно pattern comparison стоит позаимствовать у AnyLogic Compare Runs/FlexSim scenarios, не заимствуя претензию на simulation. citeturn20search5turn19view9

**Обязательный playback bar:**

`|◀  ▶|  00:34 / 02:00 ━━━━━●━━━━  0.5×  1×  2×  4×  Loop`

Scrubbing должен воспроизводить заранее определённое состояние agents в выбранный `t`; никаких event queues для этого не требуется.

**Optional polish — только после core:** isometric asset sprites, shadow under agents, trail fade, animated route pulses, zone glow on alert, floating labels, mini sparklines, cinematic auto-pan для demo, screenshot export, `Presentation mode` без editor chrome и optional 3D preview. В качестве visual reference именно presentation/share часть Visual Components и digital-twin scene viewer показывают, насколько большую ценность даёт чистый view mode. citeturn19view4turn19view14turn19view15

Я бы распределил реализацию примерно так:

| Период | Цель |
|---|---|
| Первые два дня | scene schema, viewport, background, pan/zoom/selection |
| Следующие два | assets, zones, endpoints, route editor |
| Следующие два | animated agents, playback clock |
| Следующие два | flow styling, heatmap, KPI derivation |
| Следующий день | scenarios A/B + delta UX |
| Последний день | three polished demo scenes, presentation mode, bugs/polish |

Если drag/edit infrastructure RobCo уже имеет, освободившееся время лучше потратить **не на simulation**, а на visual polish: pre-authored scenes, cinematic transitions и качественные assets дадут больше perceived product maturity.

## Где проходит граница: что нельзя называть simulation

Это самый важный product-marketing guardrail.

FlexSim позиционируется как **discrete-event factory simulation** и имеет scenario experiments; AnyLogic Parameter Variation запускает модель многократно с разными параметрами; FlexSim AGV tooling моделирует traffic/network behavior; RoboDK действительно симулирует robot programs и motion относительно robot station. citeturn19view9turn20search0turn19view10turn19view13

Поэтому в RobCo MVP **нельзя обещать**:

| Нельзя обещать | Почему |
|---|---|
| “Predicted throughput: 428 units/h” | без process/resource/queue model это декоративная точность |
| “Average waiting time: 31 s” | требует queueing/event semantics |
| “No congestion” | анимация по линиям не моделирует mutual exclusion |
| “No deadlocks” | нужен routing/traffic-control model |
| “Optimal fleet size = 7” | нужен objective + scheduler + validated workload model |
| “Optimal routes” | если routes задаёт пользователь, они не оптимизируются |
| “Collision-free AMR operation” | 2D overlap visualization не эквивалентна planner/collision avoidance |
| “Battery utilization / required chargers” | без mission/charge/battery state dynamics это не simulation |
| “Accurate human flow” | density drawing не равно pedestrian model |
| “Accurate cycle time” робота | требуется kinematics, program semantics и реальные speed/acceleration limits |
| “Digital twin” в строгом operational смысле | пока virtual scene не связана с authoritative live/operational state |

AnyLogic density visualization, например, находится внутри настоящей model environment, FlexSim AGV tutorial исследует layouts/dispatch/capacity с динамической моделью, RoboDK строит simulation вокруг actual robot station/program concepts. Именно эти возможности создают ту границу, за которую RobCo MVP не должен заходить в claims. citeturn19view7turn19view10turn19view13

Безопасная терминология:

**Хорошо:**  
`Scenario visualization`  
`Layout comparison`  
`Planned material flow`  
`Nominal travel time`  
`Estimated route distance`  
`Traffic load index`  
`Derived KPI`  
`Illustrative playback`  
`Configured fleet capacity`  
`Operational visualization`

**Плохо до появления engine:**  
`Simulation result`  
`Predicted congestion`  
`Optimized fleet`  
`Calculated wait time`  
`Collision-free`  
`Validated throughput`  
`Digital twin prediction`

Особенно удачный precedent здесь — Autodesk FDU: route может выражать material movement и estimated distance, не являясь буквально физическим транспортным path. RobCo может честно делать то же: **network visualization + deterministic analytics**. citeturn19view1

При этом архитектуру стоит сделать такой, чтобы позже один и тот же viewer принимал:

`source: "configured"` → сегодняшний visualization MVP  
`source: "recorded"` → uploaded telemetry/logs  
`source: "live"` → real fleet telemetry  
`source: "simulation"` → будущий simulation backend

Тогда UI не придётся переписывать, когда появится настоящий engine.

## React-архитектура, scene JSON и animation

**Выбор для двух недель: React + react-konva/Konva как основной renderer.**

React-Konva предоставляет declarative React bindings для Canvas objects, events и shapes; официальные Konva examples/use cases включают editor-like canvases, annotations, floor-plan style interactions и node-style editors. Konva также делит canvas на layers, позволяя обновлять динамический слой независимо от статического, хотя документация рекомендует не раздувать количество layers из-за memory/performance costs. citeturn19view20turn19view21

Сравнение:

| Вариант | Сильные стороны | Цена для RobCo | Решение |
|---|---|---|---|
| **SVG** | DOM-native, простые shapes/text, CSS, accessibility, очень быстро разрабатывать маленькие diagrams | сотни moving agents, trails, heatmap tiles и route animation начинают создавать лишнюю DOM-нагрузку; менее удобно для graphics-heavy viewport | Использовать для icons/mini charts, **не main canvas** |
| **Konva / Canvas** | React-friendly scene objects; hit-testing/events; layers; достаточно производителен для десятков/сотен interactive entities; отлично подходит для editor | не GPU-first; HTML labels лучше держать отдельно | **Основной MVP choice**. citeturn19view20turn19view21 |
| **PixiJS** | GPU-oriented scene graph и renderer; WebGL хорошо подходит для большого количества sprites; актуальная документация также развивает WebGPU | больше low-level graphics work для form/editor interaction; WebGPU support сам Pixi пока оговаривает как менее зрелый/зависящий от browser implementation | Только когда scene станет массовой по количеству sprites/particles. citeturn19view22 |
| **Three.js / React Three Fiber** | настоящий 3D; GLTFLoader поддерживает glTF 2.0; Three WebGLRenderer использует WebGL2 | camera, picking, lighting, asset pipeline, dimensions, gizmos и 3D editing съедят значительную часть двух недель | **Optional presentation layer**, не MVP editor. citeturn20search3turn20search8 |

Архитектурно я бы сделал четыре visual layers в Konva:

```text
StaticLayer
  floorplan
  walls
  racks / rooms / furniture

SemanticLayer
  zones
  endpoints
  routes
  labels

AnalyticsLayer
  heatmap
  route load
  KPI callouts

DynamicLayer
  agents
  trails
  pulses
  selections
```

Разделение статического и часто обновляемого content соответствует самой модели Konva layers: layer имеет собственный canvas, благодаря чему динамический layer можно перерисовывать без полного redraw статической сцены. citeturn19view21

HTML/React DOM при этом лучше оставить для `TopBar`, `AssetPalette`, `Inspector`, `KPI cards`, `Timeline`, menus/tooltips. Не стоит рисовать весь application chrome внутрь Canvas.

**Scene JSON следует отделить от playback.** Это позволит одним и тем же scene definitions пользоваться в editor, viewer, telemetry mode и будущем simulator.

```json
{
  "schemaVersion": "0.1",
  "scene": {
    "id": "warehouse-berlin",
    "name": "Distribution Center",
    "kind": "warehouse",
    "units": "m",
    "width": 72,
    "height": 44,
    "background": {
      "assetId": "floor-warehouse-01",
      "metersPerPixel": 0.05
    }
  },

  "assets": [
    {
      "id": "rack-01",
      "type": "rack",
      "x": 18.0,
      "y": 11.2,
      "width": 8.0,
      "height": 1.2,
      "rotation": 0,
      "visual": {
        "sprite": "rack-top.svg"
      }
    }
  ],

  "zones": [
    {
      "id": "zone-receiving",
      "type": "operational",
      "label": "Receiving",
      "polygon": [[2, 4], [14, 4], [14, 16], [2, 16]]
    },
    {
      "id": "zone-slow-01",
      "type": "speed-limit",
      "polygon": [[31, 6], [40, 6], [40, 18], [31, 18]],
      "rules": {
        "nominalSpeedMps": 0.6
      }
    }
  ],

  "endpoints": [
    {
      "id": "receiving-a",
      "type": "pickup",
      "x": 8,
      "y": 10,
      "label": "Receiving A"
    },
    {
      "id": "packing-a",
      "type": "dropoff",
      "x": 61,
      "y": 30,
      "label": "Packing A"
    }
  ],

  "routes": [
    {
      "id": "route-01",
      "from": "receiving-a",
      "to": "packing-a",
      "direction": "one-way",
      "points": [[8, 10], [20, 10], [20, 24], [47, 24], [61, 30]],
      "assumptions": {
        "tripsPerHour": 24,
        "nominalSpeedMps": 1.2,
        "dwellSec": 8
      }
    }
  ],

  "agentProfiles": [
    {
      "id": "amr-medium",
      "type": "amr",
      "widthM": 0.7,
      "lengthM": 0.9,
      "nominalSpeedMps": 1.2,
      "sprite": "amr-top.svg"
    }
  ],

  "agents": [
    {
      "id": "amr-01",
      "profileId": "amr-medium",
      "routeId": "route-01",
      "phase": 0.0
    },
    {
      "id": "amr-02",
      "profileId": "amr-medium",
      "routeId": "route-01",
      "phase": 0.5
    }
  ],

  "scenarios": [
    {
      "id": "base",
      "label": "Current layout",
      "overrides": {}
    },
    {
      "id": "scenario-b",
      "label": "6 AMRs + express route",
      "overrides": {
        "fleetCount": 6,
        "route-01.tripsPerHour": 36
      }
    }
  ],

  "analytics": {
    "heatmap": {
      "source": "plannedMovementDensity",
      "gridSizeM": 1.0
    },
    "kpis": [
      "weightedTravelDistance",
      "nominalTravelTime",
      "plannedMovesPerHour",
      "fleetLoadProxy",
      "highLoadSegments"
    ]
  },

  "playback": {
    "durationSec": 120,
    "loop": true,
    "defaultSpeed": 1
  }
}
```

Ключевой design decision здесь — не записывать в scene JSON придуманные «results». Scene содержит **inputs/assumptions**, а derived KPI вычисляются отдельным analytics layer. Это предотвращает постепенное превращение fake visualization в псевдосимуляцию.

**Animation engine** может быть очень маленьким. Для каждого polyline один раз считаются segment lengths и cumulative distance:

```text
route:
A -------- B ---- C ------------- D

cumulative:
0m         12m    18m             43m
```

В каждом visual frame:

```ts
distance =
  ((playbackTime * speedMps) + phaseOffsetMeters) % routeLength

position = pointAtDistance(route, distance)
heading  = tangentAtDistance(route, distance)
```

React state не нужно обновлять 60 раз в секунду: selected scene/scenario/playback state остаётся declarative, а текущие sprite transforms обновляются в animation layer через refs/render loop. Это особенно хорошо сочетается с Konva layer separation. citeturn19view21

Чтобы timeline был scrubbable, position должна быть **чистой функцией от time**, а не результатом цепочки incremental `x += velocity`. Тогда прыжок с `00:15` на `01:04` мгновенно воспроизводим.

Для более «настоящего» поведения без simulation engine можно добавить компактный deterministic trace:

```json
{
  "agentId": "amr-01",
  "events": [
    { "t": 0,  "state": "moving",  "routeId": "route-01" },
    { "t": 31, "state": "loading", "endpointId": "packing-a", "duration": 8 },
    { "t": 39, "state": "moving",  "routeId": "route-02" },
    { "t": 74, "state": "idle",    "endpointId": "charger-01", "duration": 12 }
  ]
}
```

Это уже даёт rich playback, status badges и timeline markers, но остаётся **storyboard trace**, а не event simulation.

Если позже понадобится настоящий 3D wow mode, тот же JSON можно projection-mapping преобразовать в Three.js/R3F scene и загрузить `.glb` assets через GLTFLoader. Three.js официально поддерживает glTF 2.0 через GLTFLoader, поэтому это естественная вторая renderer implementation поверх того же semantic schema. citeturn20search8turn20search3

## Demo-сцены, assets и wireframe

Три сцены должны демонстрировать не три разных продукта, а **один универсальный spatial-flow engine**. Это очень важно для sales effect RobCo: после warehouse пользователь должен увидеть airport и clinic и понять, что platform abstraction шире AMR warehouse planning.

**Warehouse demo — главный hero case.**

```text
Receiving
   ↓
Buffer → Storage aisles → Picking
             ↓               ↓
          Charger         Packing → Shipping
```

Семантика: receiving/storage/picking/packing/shipping zones; AMR lanes; forklift crossing; chargers; no-go zone; slow corridor; pickup/drop-off endpoints. Animate 6–12 AMRs и 1–2 forklifts. Heatmap должен сразу подсвечивать центральный shared corridor. Это визуально наиболее близко к OTTO/MiR fleet map и warehouse/material-flow tooling. citeturn19view17turn20search4turn18search5

Hero what-if:

> **Current:** два независимых длинных routes через центральный corridor  
> **Scenario B:** добавить cross-aisle + перенести packing station  
> **Visual result:** часть agents плавно меняет route, central heatmap охлаждается, weighted distance падает, KPI delta становится зелёным.

Важно: фраза на UI — `Planned traffic load ↓`, не `Congestion reduced by 31%`.

**Airport demo** использует ту же модель:

```text
Entry → Check-in → Security → Gates
                    ↓
               Transfer flow

Baggage intake → Sortation → Gate makeup
```

Assets/agents: passenger silhouettes, baggage carts, autonomous tug, security lanes, check-in desks, seating, baggage belts, gates. AnyLogic действительно используется для spatial/pedestrian-style analysis и density visualization, поэтому airport context естественно воспринимается рядом с heatmaps, но RobCo должен называть свой слой **planned passenger movement** или **configured flow**, если human behavior не моделируется. citeturn19view7

Hero what-if: закрывается security lane или меняется gate assignment → alternative route highlights → heat intensity смещается → walking-distance KPI меняется.

**Clinic demo:**

```text
Entrance → Reception → Waiting → Exam rooms
                         ↓
                      Imaging
                         ↓
Lab ← Supply robot → Pharmacy
```

Assets/agents: patient, nurse, hospital AMR/cart, wheelchair, bed, exam room, waiting chairs, nurse station, pharmacy/lab/supply room. В этом vertical лучше сделать акцент не на «patient simulation», а на **logistics visualization**: transport requests, walking route length, supply robot coverage и corridor traffic.

Hero what-if: перенести supply hub из края клиники в центр → animated supply routes сокращаются → planned logistics distance меняется мгновенно.

**Минимальный 2D asset pack** должен быть стилистически единым, top-down и не слишком детальным. Для warehouse достаточно rack module, pallet, pallet stack, dock door, conveyor straight/corner, worktable/packing station, charger, AMR, forklift и worker. Для airport — belt, check-in desk, security gate, seating row, gate desk, baggage cart/tug и passenger. Для clinic — bed, chair, reception/nurse desk, examination station, supply cart/AMR, wheelchair и patient/staff.

Не стоит создавать отдельную анимацию для каждого asset. Достаточно:

`static top-down SVG`  
`selected state`  
`status badge anchor`  
`optional isometric PNG/WebP`

Agent sprites требуют только orientation; renderer сам вращает их вдоль tangent route.

Для visually rich 2.5D лучше заказать **один согласованный asset kit**, а не смешивать Material Symbols, CAD top views и случайные Blender renders.

Если Blender-ресурс доступен, optional набор `.glb` стоит ограничить примерно десятью modular hero assets: floor/wall module, rack, conveyor, pallet, AMR, forklift, workstation, robot arm/cell, airport baggage module, hospital bed/cart. GLB/glTF здесь особенно практичен, поскольку это стандартный формат для loaders в Three.js, а Azure 3D Scenes Studio тоже использует glTF/GLB scene content, что делает pipeline пригодным и для будущего digital-twin view. citeturn20search8turn19view15

Для Blender assets нужны строгие production conventions:

```text
1 Blender unit = 1 meter
Z-up inside authoring → normalize on export/import
pivot/origin = logical placement point
+Y or +X = agreed forward direction for vehicles
low-poly/simple materials
no baked environment lighting
separate semantic objects only where interaction is needed
consistent naming:
  warehouse_rack_01
  vehicle_amr_01
  airport_belt_straight_01
  clinic_bed_01
```

Для двухнедельного MVP **2D assets важнее Blender**. Трёхмерный AMR не спасёт продукт, если пользователь не может быстро нарисовать route, увидеть flow и переключить scenario.

Рекомендуемый desktop wireframe:

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ RobCo Visualizer   Warehouse DC-01   [Base ▾] [+ Scenario]    BUILD | ▶ PLAY   92% │
├───────────────┬───────────────────────────────────────────────────────┬─────────────┤
│ ASSETS        │  KPI  Distance     Moves/h     Fleet load   Hotspots │ INSPECTOR   │
│               │       12.4 km/h      184          72%          2     │             │
│ ▣ Rack        │                                                       │ Route R-12  │
│ ▣ Station     │             RECEIVING                                 │             │
│ ◉ Endpoint    │                ●──────→───────┐                       │ From: A     │
│ ▱ Zone        │          AMR ▸                │                       │ To: Packing │
│ ─ Route       │                               │                       │ Distance 42m│
│               │     ░░░░ HEATMAP ░░░░        ▼                       │ Flow 32/h   │
│ LAYERS        │                           ┌───────────┐                │ Speed 1.2   │
│ ☑ Assets      │        ▸ AMR              │ PACKING   │                │             │
│ ☑ Routes      │                           └───────────┘                │ [Disable]   │
│ ☑ Agents      │                    ⚠ high load                         │             │
│ ☑ Heatmap     │                                                       │             │
│ ☐ Base ghost  │                                                       │             │
├───────────────┴───────────────────────────────────────────────────────┴─────────────┤
│  ◀   ▶   00:34 / 02:00     ━━━━━━━━━━━●━━━━━━━━━━━━     1× ▾    Loop   Heatmap ▾   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

Здесь одновременно объединены наиболее доказанные UX conventions: object hierarchy/viewport из RoboDK, canvas-centric factory model Visual Components, layers/inspector digital twin viewers, facility-map workflow OTTO и simulation-style timeline/KPI language AnyLogic/FlexSim. citeturn19view13turn19view4turn19view14turn19view17turn19view7turn19view9

В **Build mode** bottom timeline можно свернуть, а left panel показать `Assets | Flows | Layers`. В **Play mode** editor handles исчезают, timeline разворачивается, KPI cards становятся крупнее, а selected object показывает live-looking status. Разделение Build/View уже используется Azure 3D Scenes Studio и хорошо предотвращает визуальный конфликт между CAD-like editing и executive presentation. citeturn19view15

`Before/After` я бы реализовал в три уровня сложности:

| Уровень | UX | Решение |
|---|---|---|
| MVP | `Base / Scenario B` tabs + animated transition + KPI delta | **Сделать** |
| Хороший polish | `Show base ghost` — предыдущие assets/routes полупрозрачным контуром | **Сделать при времени** |
| Later | side-by-side synchronized canvases / swipe divider | Отложить |

Самый сильный demo sequence должен занимать меньше минуты:

> Открывается warehouse → agents уже движутся → включить Heatmap → выбрать glowing hotspot → `Duplicate scenario` → перетащить один station / переключить alternative route → KPI пересчитываются → нажать Play → flow перенаправляется, heatmap меняется → включить `Base ghost`.

Это даёт почти все визуальные сигналы серьёзного simulation/digital-twin продукта — **spatial context, flow, agents, time, analytics и what-if** — но остаётся технически честным visualization layer.

Именно поэтому оптимальный scope RobCo можно свести к формуле:

> **Floorplan + semantic graph + deterministic animation + derived analytics + scenario diff + excellent visual polish.**

Не нужно строить discrete-event engine, чтобы пользователь получил большую часть визуального и decision-support эффекта, который делают привлекательными Autodesk material-flow overlays, Siemens Sankey, Visual Components 3D factory scenes, AnyLogic heatmaps, FlexSim scenarios, RoboDK spatial station model, Azure/AWS digital-twin overlays и OTTO/MiR fleet maps. Но numerical claims RobCo должны оставаться в классе **configured/derived/planned**, пока за viewer не появится валидированный simulation или real operational-data backend. citeturn19view2turn19view3turn19view4turn19view7turn19view9turn19view13turn19view14turn19view16turn19view17turn20search4