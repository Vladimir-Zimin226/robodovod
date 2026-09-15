# Российские роботизированные решения для RobCo: доказательный procurement-каталог

## Executive summary и методика

Российский рынок робототехники к 2026 году уже нельзя описывать как рынок, где есть только интеграторы импортного оборудования. В нем сформировались несколько разных по глубине локализации слоев: серийные российские производители промышленной робототехники; российские разработчики автономии и программного обеспечения, устанавливающие свой стек на стороннее шасси; производители робототехнических комплексов, происхождение отдельных мехатронных узлов которых публично не раскрывается; локальные интеграторы китайских OEM; и российские дистрибьюторы, которые вообще не являются производителями. Масштаб локализованного сегмента быстро растет: по данным Центра развития базовых отраслей промышленности Минпромторга, в 2025 году в РФ выпустили 414 локализованных промышленных роботов на 2,33 млрд руб.; к концу 2025 года в реестре российской промышленной продукции было 16 моделей пяти производителей, тогда как в 2024 году — одна модель одного производителя. citeturn21search0

Для RobCo главное следствие этого исследования — **поле `manufacturer_country = RU` недостаточно**. Даже для решений, которые российский поставщик называет отечественными, необходимо независимо хранить происхождение робототехнической платформы, ПО, сборки, управляющей электроники и critical components. Особенно это видно на примерах RoboCV, где российской является прежде всего технология автономизации сторонней складской техники; Automacon, где заявляется российское производство и собственный WCS, но как минимум для AK-L3 обнаруживается существенное совпадение опубликованных характеристик с китайской платформой HIKROBOT Q3-600C; и TECHNORED, где российская инженерия роботизированной системы хорошо подтверждается, а происхождение каждого мехатронного узла робота REDS публичной документацией доказано хуже. citeturn1search1turn4search0turn6search1turn19search0

На другом конце шкалы есть существенно более сильные доказательства локализации. RusRobot RR 120-2900 разработан ООО «Русский Робот», серийно производится в Челябинске ООО «Завод Роботов» и с 10 апреля 2025 года имеет реестровый номер 10625128 в реестре российской промышленной продукции по ПП №719. Promobot M13 также заявлен производителем как включенный в реестр российской промышленной продукции, производится в Перми и имеет российскую техническую поддержку. «Берилл» компании «Валдай Роботы» серийно изготавливается в Московской области, имеет российский управляющий стек и прошел ПП №719; для него также найдена действующая декларация соответствия ТР ТС 010/2011 и 020/2011. citeturn21search4turn20search1turn25search0turn25search2turn25search4

Для складских и крупных логистических объектов наиболее зрелый российский procurement-layer обнаружен в AMR/FMR, автономных паллетных перевозках, автономизации складской техники и инвентаризации. Ronavi публикует характеристики и даже цену H1500; Automacon имеет крупные действующие внедрения, включая десятки роботов; RoboCV показывает исторические и действующие проекты с роботизированными тягачами, штабелерами и ричтраками; Neurus предлагает отдельный робот-инвентаризатор с WMS/API-интеграцией. citeturn0search0turn5search0turn5search2turn1search1turn14search8

Для аэропортов особенно важен Evocargo: компания предлагает коммерческую беспилотную грузовую услугу на базе электрических автономных машин собственного производства, а аэропорт Жуковский использовался как площадка для отработки перевозки грузов между терминалом и воздушным судном. У Evocargo есть десятки внедрений, российская инженерная и сервисная команда и модель Robots-as-a-Service. Для уборки крупных терминалов российский рынок также хорошо подтвержден: Waybot указывает эксплуатацию своих Cleanbotics в Пулково и публикует цены, характеристики, сервисные условия и варианты аренды. citeturn0search1turn13search2turn13search4

Для клиники ситуация неоднородна. Хорошо подтверждена роботизированная уборка: Waybot сообщает о применении в НИИ скорой помощи им. Склифосовского и других московских медучреждениях. В апреле 2026 года Яндекс начал пилот роботов-доставщиков в Первой Градской больнице и ГКБ №15 для перевозки лекарств, расходных материалов и биоматериалов. Но это прежде всего **сервис и автономная экосистема Яндекса**, а не procurement-ready SKU внутреннего больничного AMR, который клиент может приобрести и самостоятельно эксплуатировать on-premise. Именно класс полностью российского indoor hospital delivery robot остается одной из самых заметных дыр каталога. citeturn12search0turn11search0turn11search5

По коммерческой прозрачности рынок намного слабее технической части. Публичную цену удалось подтвердить лишь для ограниченного числа решений. Ronavi H1500 публикует ориентир 2,16–2,70 млн руб. и цену от 2,16 млн руб. при партии 100 машин; Waybot публикует 1,5 млн руб. для Cleanbotics 400 PRO и 2,3 млн руб. для Cleanbotics 600, а также тарифы аренды и сервиса. Большинство промышленных роботов, погрузчиков, паллетайзеров и автономных платформ работают по модели `QUOTE_REQUIRED`. citeturn0search0turn12search0turn13search2turn13search4

В исследовании используется следующий консервативный принцип классификации:

| Статус | Интерпретация для RobCo |
|---|---|
| `CONFIRMED_AVAILABLE` | Есть актуальная российская продажа/услуга, форма заказа или коммерческий контакт и дополнительные признаки реальной эксплуатации |
| `LIKELY_AVAILABLE` | Товар представлен российскому рынку, но текущая поставка конкретной модели подтверждена слабее |
| `QUOTE_REQUIRED` | Продукт явно действующий и доступен для проектного заказа, но цена и конкретная конфигурация определяются КП |
| `SUPPLY_RISK` | Поставку предлагают, но критическая зависимость от внешнего OEM/компонента делает procurement нестабильным |
| `DISCONTINUED` | Есть доказательство прекращения модели |
| `UNVERIFIED` | Недостаточно доказательств, чтобы делать вывод об актуальной коммерческой поставке |

`procurement_confidence` — авторская оценка силы доказательств, а не вероятность исполнения будущего договора. `1.0` означало бы практически исчерпывающую доказательную базу; 0.9–0.99 — текущая официальная продажа плюс сервис/кейсы; 0.7–0.89 — действующий продукт, но есть пробелы по происхождению или поставке; ниже 0.7 — решение следует держать в research layer, а не автоматически выдавать пользователю как selectable procurement option.

`source_quality` в каталоге обозначена как `A` — текущая официальная продуктовая документация плюс сильные дополнительные свидетельства; `A-` — качественная официальная страница при отдельных пробелах; `B` — преимущественно заявления производителя или неполная документация; `C` — вторичные/дистрибьюторские источники.

## Карта рынка и производители

**Карта по классам.** Знак «●» означает наличие убедительно подтвержденного российского решения или российского engineering layer; «◐» — решение есть, но происхождение hardware, зрелость SKU либо текущая поставка подтверждены не полностью; «○» — российский procurement в основном закрывается иностранным OEM или найденные отечественные варианты недостаточно доказаны.

| Класс | Покрытие РФ | Наиболее доказательные игроки | Вывод для RobCo |
|---|---:|---|---|
| AMR | ● | Ronavi, Automacon/RIX | Хорошо закрыт; у Automacon обязательно хранить OEM-provenance отдельно. citeturn0search0turn4search0 |
| AGV | ●/◐ | ОМП, ТПА/3D Technologies, Automacon | Российские поставщики и производство заявлены, но документация слабее Ronavi. citeturn4search2turn4search8 |
| Автономные транспортные платформы | ● | Evocargo, «Валдай Роботы» | Сильный сегмент для закрытых промышленных/логистических территорий. citeturn0search1turn25search1 |
| Автономные тягачи | ●/◐ | RoboCV, Evocargo | У RoboCV российская автономизация, но не обязательно российское базовое транспортное средство. citeturn1search1 |
| Роботизированные погрузчики / штабелёры | ●/◐ | Automacon, RoboCV | Реальные крупные внедрения есть; hardware provenance необходимо проверять по модели. citeturn5search2turn1search1 |
| Промышленные манипуляторы | ● | RusRobot, «Валдай Роботы», TECHNORED | Один из наиболее быстро локализующихся классов; есть ПП №719. citeturn21search4turn25search4turn19search0 |
| Cobot | ● | Promobot M13, REDS/TECHNORED | M13 особенно хорошо подтвержден как российский продукт с реестровым статусом. citeturn20search1turn2search1 |
| Palletizing | ● | TECHNORED REDCARGO, Promobot M13-based cells, Aripix | Есть серийные типовые ячейки и российская интеграция. citeturn26search1turn26search2 |
| Depalletizing | ◐ | системные интеграторы | Отдельных стандартизированных российских SKU с такой же открытой документацией найдено значительно меньше. citeturn26search2 |
| Pick-and-place / sorting | ●/◐ | Aripix, TECHNORED | Российская инженерия сильна; рынок часто проектный, а не SKU-based. citeturn9search0turn9search1 |
| Indoor service delivery | ○/◐ | Яндекс — hospital/campus service; Promobot — сервис, но не грузовой courier AMR | Полноценный российский аналог Pudu/Keenon hospital delivery как покупаемого SKU с сильным datasheet не подтвержден. citeturn11search0turn1search6 |
| Автономная уборка | ● | Waybot, Yacu.ai | Один из наиболее procurement-ready сервисных классов. citeturn12search0turn13search3 |
| Промышленные/inspection БПЛА | ●/◐ | Aeromax, Geoscan | Производители есть; модельная коммерческая прозрачность неодинакова. citeturn14search4turn16search1 |
| Складская инвентаризация | ● | Neurus/Automacon | Хорошо подтвержден специализированный российский robot SKU. citeturn14search8 |
| Наземная inspection robotics | ● | SMP Robotics, «Электромотив» | SMP — особенно сильная документация; у «Электромотива» продукт новее и procurement пока менее доказан. citeturn15search0turn14search2 |

**Отдельная таблица российских производителей и разработчиков.**

| Компания | Что доказано как российское | Производство/сборка | Что остается неизвестным |
|---|---|---|---|
| **Ronavi Robotics** | Российский производитель AMR, собственная интеграция и поддержка. citeturn0search0turn4search6 | Производство в РФ заявлено производителем. citeturn4search6 | BOM, происхождение lidar/drive/controller/battery |
| **Evocargo** | Разработка автономной грузовой системы и транспортные средства собственного производства. citeturn0search1 | Собственное производство заявлено. citeturn0search1 | Детальная доля локализации и происхождение sensor/compute stack |
| **ООО «Русский Робот» + ООО «Завод Роботов»** | Разработка RusRobot; отечественное ПО; RR120-2900 в ПП №719. citeturn23view0turn21search4 | Серийное производство, Челябинск. citeturn21search4 | Полный country-of-origin каждого сервопривода/редуктора публично не раскрыт |
| **Promobot** | Российская разработка, ПО, M13 в реестре российской продукции. citeturn20search1 | Производство, Пермь. citeturn20search1 | Происхождение всех critical components |
| **Валдай Роботы** | Beryl разработан в СПб; собственное ПО; российское серийное производство; ПП №719. citeturn25search0turn25search4 | Московская область. citeturn25search0 | BOM приводов/датчиков опубликован не полностью |
| **SMP Robotics** | Полный цикл разработки шасси, электроники, вычислителей, ПО; серийное производство РФ. citeturn15search0turn15search2 | Россия, engineering center — Зеленоград. citeturn15search0 | В некоторых конфигурациях есть явно импортный NVIDIA Jetson |
| **Waybot Robotics** | Российские алгоритмы SLAM/CV, системная разработка, локальное производство корпуса. citeturn12search0 | РФ заявлена как производственная база. citeturn12search0 | Происхождение lidar/camera/battery/cleaning modules |
| **Yacu.ai** | Собственное ПО и шасси заявлены российскими. citeturn13search3 | Российское производство заявлено. citeturn13search3 | Cleaning hardware обозначен как узлы известных марок без раскрытия стран |
| **Automacon / RIX** | Российский WCS, R&D, интеграция; с 2025 г. заявлено производство полного цикла в РФ. citeturn4search0turn5search1 | РФ по заявлению группы. citeturn4search0 | Происхождение части robot bases; для AK-L3 есть OEM-risk evidence |
| **Neurus / Automacon** | Собственное ПО robot inventory и российская разработка. citeturn14search1turn14search8 | Hardware manufacturing site отдельно не доказан | Шасси, камеры, вычислитель |
| **RoboCV** | Российский autonomy stack X-MOTION NG, WMS/ERP integration. citeturn1search1 | Российская разработка/интеграция | Базовый тягач/штабелер/ричтрак может быть сторонним OEM |
| **TECHNORED** | Российская разработка робототехнических систем, ПО, интеграция; REDEDUCATION PRO в реестре по ПП №719. citeturn19search0 | Производство систем в Москве заявлено. citeturn19search0 | ПП №719 для REDEDUCATION не доказывает происхождение всех REDS и REDCARGO components |
| **Aripix Robotics** | Российская разработка RTK, контроллеров и собственной электроники, интеграция. citeturn9search0turn9search2 | Российская сборка/разработка | Компания публично использует в том числе закупаемые китайские компоненты; BOM зависит от проекта. citeturn9search6 |
| **ОМП** | Российское производство AGV заявлено самим поставщиком. citeturn4search2 | РФ заявлена | Недостаточно независимой product-level localization документации |
| **ТПА / 3D Technologies** | Заявлен полный цикл производства AGV и сервиса в РФ. citeturn4search8 | Санкт-Петербург/РФ заявлены | Слабая открытая модельная спецификация |
| **Aeromax** | Российский разработчик, производитель и эксплуатант БАС, собственное производство БВС. citeturn14search4turn14search0 | РФ | Detailed BOM и часть актуальных model-level specs |
| **Электромотив** | По сообщению Сколково, роботы спроектированы и произведены в РФ; заявлена локализация свыше 75%. citeturn14search2 | РФ | Модель, datasheet, коммерческая поставка и сервис публично подтверждены недостаточно |

**Rebrand/OEM/integrator layer — то, что RobCo нельзя автоматически маркировать `Russian robot`.**

| Поставщик/бренд в РФ | Реальный статус | Почему это важно |
|---|---|---|
| **Cobot.ru / Elfin, Elfin-Pro, S** | Фактически продуктовая линейка **Huayan Robotics**; русскоязычный сайт прямо публикует новости Huayan Robotics и ее листинга HKEX. Это не доказательство российского производителя. citeturn21search6turn21search2 | `manufacturer_country` должен отражать иностранного OEM, а не домен `.ru`. |
| **QRobotics / Gausium** | Российский официальный дистрибьютор Gausium; Gausium — иностранный OEM. citeturn12search6 | Российские sale/service/integration ≠ российское происхождение оборудования. |
| **VIGGO Russia** | Сайт позиционирует организацию как официального представителя и аккредитованный сервисный центр в РФ. citeturn12search4 | `localization_status = FOREIGN_OEM_RU_REPRESENTATIVE`, пока не доказано обратное. |
| **RoboCV X-MOTION NG** | Российский разработчик автономии и интегратор сторонней складской техники. citeturn1search1 | «Российским» корректно называть autonomy/software layer, а не обязательно весь forklift. |
| **Automacon AK-L3** | Производитель заявляет российский manufacturing layer, но опубликованные параметры AK-L3 — 940×650×250 мм, 600 кг, 2 м/с, ±10 мм и ≥8 ч — очень близко/совпадают с китайской HIKROBOT Q3-600C. Это **индикатор**, но не окончательное доказательство rebrand. citeturn5search1turn6search1 | RobCo: `oem_rebrand_status = SUSPECTED_FOREIGN_OEM_BASE`; запросить декларацию производителя/BOM/country of origin до присвоения RU-hardware. |
| **TECHNORED REDCARGO/REDS** | Российский производитель и интегратор робототехнической системы подтвержден; происхождение всех embedded robot components публично не прослеживается. citeturn19search0turn26search1 | Не следует автоматически переносить ПП №719 одной учебной ячейки на всю линейку REDS/REDCARGO. |

## Нормализованный каталог

Ниже `null / н/д` означает именно **«публично не подтверждено»**, а не отсутствие функции.

**Identity, application и procurement.**

| ID | Manufacturer / model | Robot class / typical process | manufacturer_country | manufacturing_country | localization_status | procurement_status_russia | confidence | service_in_russia | price_status | supply_risk | source_quality |
|---|---|---|---|---|---|---|---:|---|---|---|---|
| RU-01 | **Ronavi H1500** | AMR; подъем/перевозка паллет и грузов | RU | RU, заявлено | RU design + production; components undisclosed | `CONFIRMED_AVAILABLE` | **0.96** | YES | PUBLIC_RANGE | MEDIUM | A citeturn0search0 |
| RU-02 | **Ronavi M** | FMR/AMR, Goods-to-Person, стеллажи/паллеты | RU | RU, заявлено | RU development/production; BOM undisclosed | `QUOTE_REQUIRED` | **0.91** | YES | QUOTE | MEDIUM | A- citeturn4search6 |
| RU-03 | **Automacon/RIX AK-L3** | AMR/FMR, shelf transport | RU system supplier; underlying OEM uncertain | RU assembly claimed / base origin disputed | RU WCS + integration; suspected foreign OEM base | `CONFIRMED_AVAILABLE` | **0.86** | YES | QUOTE | **HIGH** | B citeturn4search0turn5search1turn6search1 |
| RU-04 | **Automacon/RIX AK-2000-2** | Autonomous forklift/pallet mover | RU system supplier | RU production claimed; chassis provenance unverified | RU WCS/integration + hardware provenance incomplete | `CONFIRMED_AVAILABLE` | **0.94** | YES | QUOTE | MEDIUM | A- citeturn5search1turn5search2 |
| RU-05 | **ОМП AGV 300 platform** | AGV, carts/material transport | RU | RU claimed | Russian manufacture claimed; components unknown | `QUOTE_REQUIRED` | **0.78** | YES | QUOTE | MEDIUM | B citeturn4search2 |
| RU-06 | **ТПА / 3D Technologies AGV family** | AGV, forklift/stacker/tug/cart | RU | RU claimed | full-cycle RU production claimed | `QUOTE_REQUIRED` | **0.74** | YES | QUOTE | MEDIUM | B citeturn4search8 |
| RU-07 | **Evocargo N1** | Autonomous electric cargo platform | RU | RU / own production claimed | RU autonomy + own vehicle production; component BOM undisclosed | `CONFIRMED_AVAILABLE` | **0.98** | YES | RaaS/QUOTE | MEDIUM | A citeturn0search1 |
| RU-08 | **Valdai Granit** | Autonomous industrial transport platform | RU | RU | Russian-developed/manufactured platform; imported compute disclosed | `QUOTE_REQUIRED` | **0.91** | YES | QUOTE | MEDIUM | A- citeturn25search1turn25search8 |
| RU-09 | **RoboCV X-MOTION NG tug/stacker/reachtruck** | Autonomous tug, stacker, reachtruck | RU for autonomy layer | Depends on base OEM | RU software/autonomy on third-party electric vehicle | `QUOTE_REQUIRED` | **0.91** | YES | QUOTE | HIGH | A- citeturn1search1 |
| RU-10 | **RusRobot RR 120-2900** | 6-axis industrial manipulator | RU | RU, Chelyabinsk | **PP719 registered**, RU software | `QUOTE_REQUIRED` | **0.98** | YES | QUOTE | MEDIUM | A citeturn21search4turn24view0 |
| RU-11 | **Promobot M13** | Cobot; palletizing, welding, machine tending | RU | RU, Perm | **PP719 registered**, RU production/software | `QUOTE_REQUIRED` | **0.98** | YES | QUOTE | MEDIUM | A citeturn20search1turn2search1 |
| RU-12 | **Valdai Beryl RP25.22ShS** | Industrial 6-axis manipulator | RU | RU, Moscow region | **PP719 registered**, own RU software/control stack | `QUOTE_REQUIRED` | **0.98** | YES | QUOTE | MEDIUM | A citeturn25search0turn25search4 |
| RU-13 | **TECHNORED REDCARGO BASIC 10 cobot** | Palletizing cell | RU system manufacturer | RU system production; arm BOM unverified | RU cell/integration/software; embedded hardware provenance incomplete | `QUOTE_REQUIRED` | **0.96** | YES | QUOTE | MEDIUM | A- citeturn26search1 |
| RU-14 | **Aripix custom pick/sort/packing RTK** | Pick-and-place, sorting, packaging | RU | RU system assembly | RU engineering/controllers/electronics; some imported components | `QUOTE_REQUIRED` | **0.87** | YES | QUOTE | MEDIUM | B+ citeturn9search0turn9search1turn9search6 |
| RU-15 | **Promobot V.4** | Indoor service/reception/guide robot | RU | RU, Perm | RU product/software/assembly; component BOM incomplete | `QUOTE_REQUIRED` | **0.95** | YES | QUOTE | MEDIUM | A- citeturn1search6turn1search2 |
| RU-16 | **Yandex Rover Gen4 / robotic delivery service** | Autonomous courier, hospital/campus delivery | RU developer/operator | **UNVERIFIED** for hardware factory | RU autonomy/software; hardware manufacturing origin not publicly established here | `CONFIRMED_AVAILABLE` **as service** | **0.96** | YES, vendor-operated | SERVICE/QUOTE | MEDIUM | A citeturn11search0turn11search1turn11search5 |
| RU-17 | **Waybot Cleanbotics 400 PRO** | Autonomous cleaning | RU | RU claimed | RU software/system/body; key sensors/battery origins undisclosed | `CONFIRMED_AVAILABLE` | **0.99** | YES | PUBLIC | MEDIUM | A citeturn12search0turn13search2 |
| RU-18 | **Waybot Cleanbotics 600** | Autonomous cleaning | RU | RU claimed | RU software/system; components incompletely disclosed | `CONFIRMED_AVAILABLE` | **0.99** | YES | PUBLIC | MEDIUM | A citeturn13search4 |
| RU-19 | **Yacu.ai Unit** | Autonomous cleaning/platform | RU | RU claimed | Own RU software/chassis; cleaning modules partly third-party | `QUOTE_REQUIRED` | **0.86** | YES/dealer | QUOTE | MEDIUM | A- citeturn13search3 |
| RU-20 | **Aeromax BAS family A-5/B-120/B-200** | Industrial UAV; monitoring, inspection, logistics | RU | RU / own production claimed | RU aircraft development/production; BOM undisclosed | `QUOTE_REQUIRED` | **0.91** | YES/operator service | QUOTE | MEDIUM | A- citeturn14search4turn14search9 |
| RU-21 | **Geoscan 701** | Fixed-wing survey/inspection UAV | RU | RU likely, model-level proof weaker in reviewed material | Russian developer; current model provenance insufficiently documented here | `LIKELY_AVAILABLE` | **0.70** | LIKELY | QUOTE | UNKNOWN | C+ citeturn16search1turn16search2 |
| RU-22 | **SMP Robotics Inspector T5.5/T7.5** | Outdoor autonomous inspection robot | RU | RU | Full-cycle RU design/manufacturing; NVIDIA edge compute used | `QUOTE_REQUIRED` | **0.96** | YES | QUOTE / financing | HIGH | A citeturn15search0turn15search1 |
| RU-23 | **Neurus AI Stock Counter 12M / AUSC12** | Warehouse inventory robot | RU | UNVERIFIED for complete hardware | RU software/system; hardware component provenance incomplete | `QUOTE_REQUIRED` | **0.94** | YES, Automacon group | QUOTE | MEDIUM | A citeturn14search8turn14search5 |
| RU-24 | **Electromotiv autonomous inspector** | Outdoor inspection/security | RU | RU per Skolkovo | RU design/manufacture; **>75% localization claimed by Skolkovo** | `UNVERIFIED` | **0.55** | UNVERIFIED | UNVERIFIED | UNKNOWN | B- citeturn14search2 |

**Technical normalized fields.**

| ID | Payload / working load | Dimensions | Speed | Runtime/range | Navigation/localization | Lift/reach/repeatability/cycle | Environment | Integration / fleet |
|---|---|---|---|---|---|---|---|---|
| RU-01 H1500 | 1500 kg | 1044×654×380 mm | 1.5 m/s | up to 10 h, operating 80→20% SOC | QR + SLAM | min aisle 750 mm | Indoor | Open API, WMS/MES; Wi-Fi 5 GHz. **S1** citeturn0search0 |
| RU-02 Ronavi M | configurations up to 1200 kg | н/д | н/д | н/д | SLAM | н/д | Indoor | Open API/WMS. **S2** citeturn4search6 |
| RU-03 AK-L3 | 600 kg | 940×650×250 mm | up to 2 m/s | ≥8 h; charge ≤1.5 h | QR / laser SLAM / visual SLAM family | turning radius 995 mm; positioning ±10 mm | Indoor | WCS/fleet. **S3** citeturn5search1 |
| RU-04 AK-2000-2 | 2000 kg | 1980×1065×2285 mm | published catalog value up to ~2.6 m/s | 6–8 h; charge ~2 h | 3D Laser SLAM | fork lift ~175 mm; turning radius 1555 mm; positioning ±30 mm | Indoor warehouse | Automacon WCS; safety lidar. **S3** citeturn5search1 |
| RU-05 OMP AGV | up to 300 kg | 890×650×297 mm | 1.5 m/s | battery data not sufficiently specified | inductive / magnetic / machine vision options | н/д | Configurations advertised down to −40 °C | ASUTP integration. **S4** citeturn4search2 |
| RU-06 TPA AGV | н/д | н/д | н/д | н/д | embedded wire / magnetic tape / inertial / laser depending solution | н/д | Industrial | custom integration. **S5** citeturn4search8 |
| RU-07 Evocargo N1 | 2000 kg public figure | н/д | public reports differ around 20–25 km/h | public range up to ~200 km | autonomous sensor stack | up to six Euro pallets cited in current industry source | Outdoor/industrial territories; Russian winter operations demonstrated | Customer IT integration as part of RaaS. **S6** citeturn0search1 |
| RU-08 Granit | 3000 kg | 1500×800×415 mm | 5 km/h | up to 9 h | autonomous industrial platform; detailed localization method н/д | mecanum drive | Industrial indoor | Wi-Fi; LattePanda compute. **S7** citeturn25search1 |
| RU-09 RoboCV | Depends on converted tug/stacker/reachtruck | Depends on OEM base | н/д | Depends on vehicle | X-MOTION NG autonomous navigation | lift etc. depends on vehicle | Warehouse/industrial | WMS/ERP integration, fleet layer. **S8** citeturn1search1 |
| RU-10 RR120-2900 | 120 kg | 1700×950×1950 mm transport | н/д | mains powered industrial robot | fixed industrial manipulator | reach 2900 mm; 6 axes | Industrial | industrial network protocols. **S9** citeturn24view0 |
| RU-11 M13 | 13 kg | 1550×492×240 mm | nominal TCP 1 m/s | mains powered | fixed 6-axis cobot | reach 150–1300 mm; repeatability 0.05 mm | +5…+50 °C; IP54 | controller + teach pendant; external tooling. **S10** citeturn2search1 |
| RU-12 Beryl | 25 kg | full envelope n/д; mass 265±10 kg | linear 2 m/s; axes up to 150–180°/s | mains powered | fixed 6-axis | reach 2200 mm; positioning ±0.1 mm; repeatability published 0.02–0.2 mm | 0…45 °C | PROFINET via gateway, EtherCAT Master, Modbus TCP, VALDAi API. **S11** citeturn25search0 |
| RU-13 REDCARGO 10 | 10 kg package | work area 1450×1450 mm | arm ≤4 m/s | mains; avg ~500 W, max 2000 W | fixed cobot cell | reach 1350 mm; 6–12 cycles/min; repeatability ±0.1 mm; stack 1100 mm | Industrial | REDS C10 controller, cell I/O; pallet 1200×800. **S12** citeturn26search1 |
| RU-14 Aripix | project-dependent | project-dependent | н/д | n/a | vision/project-dependent | published case: up to 42,000 items/h / ~700 kg/h for a specific confectionery application; not generic robot rating | Production | custom MES/line integration. **S13** citeturn9search1 |
| RU-15 Promobot V4 | n/a; service robot | н/д in reviewed current source | autonomous indoor movement | autonomous charging stated | mapping/autonomous movement; 16 sensors + 3D camera | n/a | Indoor | SDK; external databases, web services, security systems. **S14** citeturn1search6turn1search4 |
| RU-16 Yandex Rover Gen4 | payload not publicly established in reviewed current sources | н/д | н/д | н/д | proprietary autonomous-driving stack, lidar/vision | n/a | Urban/campus, year-round | Yandex delivery platform; partner service rather than on-prem fleet product. **S15** citeturn11search1turn11search5 |
| RU-17 Cleanbotics 400 PRO | cleaning payload not applicable | 1064×560×744 mm; 50 kg | n/д | ~3 h; charge ~1 h | Waybot autonomous SLAM/CV | 40 cm cleaning width; 700–1200 m²/h | Indoor | Waybot Control; can operate without Internet. **S16** citeturn13search2turn12search0 |
| RU-18 Cleanbotics 600 | n/a | 700×600×1000 mm; 140 kg | n/д | ~4 h; full charge ~1 h | 2D lidar + four 3D lidar + four HD cameras listed | 60 cm width; up to ~1600 m²/h | Indoor large areas | fleet monitoring/control. **S17** citeturn13search4 |
| RU-19 Yacu Unit | n/a | 900×560×800 mm; filled mass 130 kg | н/д | up to 5 h | lidar 360°, radar, stereo camera, RTLS | ~7200 m²/cycle; water 50+50 L | Indoor | RTLS/fleet system; automatic dock available. **S18** citeturn13search3 |
| RU-20 Aeromax | depends on aircraft | model-dependent | model-dependent | historical/current service documentation cites D-20 up to 10 h; MK-series up to 80 min with 2 kg payload, but current SKU mapping requires quote | GNSS/autonomous BAS | model-dependent | Outdoor | GIS/customer-system integration. **S19** citeturn14search0turn14search4 |
| RU-21 Geoscan 701 | exact usable payload n/д in reviewed source | wingspan ~3.3 m | н/д | up to ~10 h | airborne navigation | MTOW ~22 kg per distributor | Outdoor | survey workflow; current software configuration quote-dependent. **S20** citeturn16search2 |
| RU-22 SMP Inspector | application sensors rather than cargo | 1520×860×1620 mm; 142 kg without batteries | 3–5 km/h typical | up to 6 h; 20 km range; charge 2–4 h | GNSS GLONASS/GPS/BDS/Galileo + visual fallback | turning radius 1.7 m; lane 1.3 m; grade up to 30% | **−45…+45 °C, IP65** | Navigator, Remote Control; 3G/4G/5G; API/ONVIF/MQTT ecosystem. **S21** citeturn15search1turn15search2 |
| RU-23 Neurus AUSC12 | n/a | mast up to 12 m | max 0.6 m/s current page | ~2 h; automatic charging | autonomous route/patrol, cameras | scan range up to 2 m | Warehouse | WMS, ERP, 1C via API. **S22** citeturn14search8turn14search5 |
| RU-24 Electromotiv inspector | н/д | н/д | н/д | н/д | autonomous | n/a | off-road surfaces; demonstrated gradients up to 30° for platform family | н/д. **S23** citeturn14search2 |

Есть несколько явных случаев, где данные производителя следует хранить с `data_quality_flag`. Например, на разных страницах Waybot для Cleanbotics 900 обнаруживаются внутренне противоречивые значения емкости баков и массы; поэтому 900 не включен в recommended set до получения актуального datasheet. Аналогично, у Neurus одна текущая маркетинговая страница показывает крайне маловероятную формулировку «до 500 паллет в минуту», тогда как более ранняя официальная страница указывала 12 600 ячеек/ч; я не использовал ни одно из этих значений как selectable capacity parameter и оставил только однозначные скорость движения, дальность сканирования и runtime. citeturn13search1turn13search5turn14search1turn14search5

## Коммерция, сервис и supply risk

**Публичные цены и коммерческие условия.**

| Решение | Публичная цена / evidence | VAT | Charger / dock / SW | Commissioning / integration | Warranty / service / training | Lead time / finance | price_status |
|---|---|---|---|---|---|---|---|
| **Ronavi H1500** | ориентир **2,16–2,70 млн RUB**; от **2,16 млн RUB при 100 шт.**; конечная стоимость зависит от комплектации. **S1** citeturn0search0 | Not stated | exact inclusion not stated | проектная интеграция/WMS/API предлагается | warranty **1 year**; local service/spares claimed | pilot/rental possibilities mentioned; delivery РФ | `PUBLIC_RANGE` |
| **Ronavi M** | н/д; индивидуальный расчет. citeturn4search6 | Not stated | Quote | WMS/API | Russian support | Quote | `QUOTE_REQUIRED` |
| **Automacon robots** | н/д | Not stated | project | WCS/fleet, commissioning | 24/7 service, RF spare-parts warehouse claimed | Project | `QUOTE_REQUIRED` citeturn4search0 |
| **Evocargo N1** | публичной purchase price не найдено; основная коммерческая модель — **Robots-as-a-Service**. citeturn0search1 | n/a | Included as service configuration | site audit, routes/digital twin, IT integration | operation/maintenance by provider | Contract/project | `RAAS_QUOTE` |
| **RusRobot RR120** | цена по запросу | Not stated | controller/product configuration through quote | integration partner available | training center + support | order/project | `QUOTE_REQUIRED` citeturn24view0turn23view0 |
| **Promobot M13** | цена по запросу | Not stated | controller + teaching pendant + manipulator listed | integration/tooling project | technical support in Perm/Russia | Quote | `QUOTE_REQUIRED` citeturn20search1turn2search1 |
| **Valdai Beryl** | цена по запросу | Not stated | own control/software stack | integration by Valdai | training, technical support; software updates stated free over robot life | in-stock robots: **~1 month**; made-to-order: **4–7 months**. **S11/S24** citeturn25search0turn25search4 | `QUOTE_REQUIRED` |
| **TECHNORED REDCARGO BASIC 10** | цена по запросу | Not stated | robot, stand, gripper, electric cabinet, pneumatics, pallet positioner, sensors listed in standard kit | turnkey integration available | training/service; finance tools | leasing/installment/support options visible | `QUOTE_REQUIRED` citeturn26search1turn26search4 |
| **Waybot Cleanbotics 400 PRO** | **1.5 млн RUB purchase**; rental first month about **200k**, then **75k/month**; annual plan figures also published. **S16** citeturn12search0turn13search2 | Not stated | charging infrastructure configuration available | deployment/support | warranty **2 years**; monthly service published at **30k RUB** for purchased robot | rental available | `PUBLIC` |
| **Waybot Cleanbotics 600** | **2.3 млн RUB purchase**; rental first month about **300k**, then **90k/month**. **S17** citeturn12search0turn13search4 | Not stated | dock offered/in system | deployment/support | 2-year warranty according to product family offer; service network | rental available | `PUBLIC` |
| **Yacu Unit** | exact public price not found | Not stated | Robot + dock + RTLS anchors form project price | pilot/commissioning stated | warranty **1 year**, dealer/service network | **50% advance**, manufacturing about **2 months**; leasing mentioned | `QUOTE_REQUIRED` citeturn13search3 |
| **SMP Inspector** | exact price not public | Not stated | ACS automatic charger/options | manufacturer commissioning/routes/site deployment | remote monitoring, field service, parts | partial-initial-payment/monthly-payment model offered | `QUOTE_REQUIRED` citeturn15search0turn15search1 |
| **Yandex Rover** | hardware purchase price not applicable/confirmed; B2B robotic-delivery service | Service contract | managed ecosystem | vendor integration | vendor-operated service | Commercial partner connection available | `SERVICE_QUOTE` citeturn11search5 |

**Российский сервис и реальная доступность.**

| Solution | Можно запросить КП / подключение | Российские внедрения | Российский service | Spares evidence | Public customer cases | Итог |
|---|---|---|---|---|---|---|
| Ronavi H1500/M | Yes | публичные product-sales evidence; точные кейсы по каждому SKU менее подробно раскрыты | Да, manufacturer claims local support | Да, локальные parts/support заявлены | Limited on reviewed model pages | Сильный procurement candidate. citeturn0search0turn4search6 |
| Automacon AK-2000-2 | Yes | **X5: 67 robots**; VkusVill project includes **70 FMR**, inventory and cleaning robots | Да, 24/7 | Склад запчастей РФ заявлен | X5, VkusVill | Очень сильная эксплуатационная доказательность, но проверять OEM provenance. citeturn5search0turn5search2 |
| Evocargo N1 | Yes/service contract | более 50 deployments по России по текущему сайту | Да | maintenance included within service model | Wildberries, Sportmaster, Baltika, Severstal, SIBUR, Russian Post and others listed | Один из наиболее доказательных large-logistics candidates. citeturn0search1 |
| RoboCV | Yes | VW, KAMAZ, Pyaterochka, Knauf и др. | Да | зависит также от base vehicle OEM | Да | Сильный autonomy/integration layer. citeturn1search1 |
| RusRobot | Yes | серийные поставки заявлены; промышленное применение | Российский manufacturer/integration network | manufacturer/production base | Есть отраслевые evidence | Высокая локализационная уверенность. citeturn21search3turn21search4 |
| Promobot M13 | Yes | current industrial product and support | Да | Russian support | current public industrial references on corporate ecosystem | Сильный Russian cobot reference. citeturn20search1 |
| Beryl | Yes | МЦСТ / exhibitions and industrial projects | Да | support@supplier + serial production | МЦСТ case, public demos | Поставка прямо подтверждена; clear lead time. citeturn25search10turn25search4 |
| REDCARGO | Yes | 2026 confectionery case plus earlier projects | Да | components in supplier stock claimed for standard complexes | Да | Сильный palletizing reference. citeturn19search0turn26search3 |
| Waybot | Yes / direct purchase | Sklifosovsky, Pulkovo, industry/business facilities listed | сервисные точки/contractors | service network claimed | Да | Очень procurement-friendly. citeturn12search0 |
| Yacu Unit | Yes | public deployment detail weaker than Waybot | dealer/24×7 support claimed | common-market parts claimed | limited | Suitable secondary cleaning reference. citeturn13search3 |
| Yandex Rover | Partner connection | Moscow/SPb/Kazan etc.; hospital pilot | Fully vendor-operated | vendor fleet | >1m deliveries / >1000 fleet by 2026; hospital pilot | Excellent operational evidence, **but not hardware procurement SKU**. citeturn11search0turn11search4turn11search5 |
| SMP Inspector | Yes | serial T5 fleet >100 by early 2023, long outdoor operation; Russian deployments offered | manufacturer remote + onsite service | supplier states parts stock | operational evidence strong, customer identities less complete | Strong inspection candidate. citeturn15search0turn15search2 |
| Neurus AUSC12 | Yes | Automacon group deployments include inventory robots | Automacon service | group service infrastructure | VkusVill project indicates inventory robots | Strong warehouse inventory candidate. citeturn14search5turn5search0 |
| Aeromax | Yes | commercial BAS work in **57 regions** reported for aviation group | Operator/manufacturer service | fleet operator | industry monitoring/logistics projects | Procurement may be service-based rather than simple airframe sale. citeturn14search12 |
| Electromotiv inspector | Not enough evidence | prototype/demo evidence | Unverified | Unverified | innovation-show evidence | Keep as `UNVERIFIED`, not reject. citeturn14search2 |

**Supply-risk matrix.** Это оценка устойчивости **легальной коммерческой поставки**, а не анализ способов обхода ограничений.

| Solution | supply_risk | Причина |
|---|---|---|
| **Ronavi H1500/M** | `MEDIUM` | Российский производитель, сервис и производство заявлены; однако происхождение приводов, lidar, battery cells и compute публично не раскрыто. Отсутствие такого раскрытия не означает импортность, но не позволяет поставить LOW. citeturn0search0turn4search6 |
| **Automacon AK-L3** | `HIGH` | Российский WCS/service сильны, но имеется существенное совпадение характеристик с китайским HIKROBOT Q3-600C; до получения BOM/country-of-origin сохраняется OEM dependency risk. citeturn5search1turn6search1 |
| **Automacon AK-2000-2** | `MEDIUM` | Крупный локальный fleet/service/spares подтверждены, но происхождение key vehicle hardware публично неполно. citeturn4search0turn5search2 |
| **Evocargo N1** | `MEDIUM` | Собственная разработка/производство и российский managed service снижают риск, но sensor/compute/BMS component origin не раскрыт. citeturn0search1 |
| **RoboCV autonomous forklifts** | `HIGH` | Российский autonomy software сохраняется, но доступность всего решения напрямую зависит от конкретного OEM electric truck и его spares. citeturn1search1 |
| **RusRobot RR120** | `MEDIUM` | ПП №719, российское серийное производство и ПО существенно снижают риск. Но ПП №719 не означает автоматически 100% отечественный BOM, поэтому без component declaration LOW было бы слишком сильным выводом. citeturn21search4turn23view0 |
| **Promobot M13** | `MEDIUM` | Реестр ПП №719, производство и support РФ подтверждены; exact origin reducer/servo/sensor stack в открытой документации не полностью описан. citeturn20search1 |
| **Valdai Beryl** | `MEDIUM` | Очень сильная software sovereignty: собственный stack, российское ПО, заявлены российские процессоры и отсутствие third-party software licensing; ПП №719. Но полный BOM приводов публично не показан. citeturn25search0turn25search4 |
| **Valdai Granit** | `MEDIUM` | Российская разработка/изготовление, однако страница прямо указывает LattePanda как вычислительное ядро — импортная зависимость существует. citeturn25search1 |
| **REDCARGO** | `MEDIUM` | Российская system engineering и сервис хорошо подтверждены; страна происхождения каждой embedded robotic component не установлена. citeturn26search1turn19search0 |
| **Aripix** | `MEDIUM` | Российские controllers/electronics/software, но публично сообщалось о закупке части компонентов в Китае. citeturn9search2turn9search6 |
| **Waybot** | `MEDIUM` | Российское ПО и возможность работы **без интернета** уменьшают cloud/vendor-lockout risk; hardware sensor/battery origin не раскрыт полностью. citeturn12search0 |
| **Yacu Unit** | `MEDIUM` | Собственное software/chassis, но cleaning components обозначены как сторонние «известные марки». citeturn13search3 |
| **Yandex Rover** | `MEDIUM` | Российский proprietary autonomy stack и серийный fleet уменьшают operational risk; однако клиент приобретает vendor-managed service и остается зависим от платформы Яндекса, а BOM не раскрыт. citeturn14search6turn11search5 |
| **SMP Inspector** | `HIGH` | Российское шасси/электроника/ПО развиты глубоко, однако спецификация прямо указывает **NVIDIA Jetson TX2 / Orin NX** как вычислительную платформу видеоаналитики; публичного отечественного substitute path на product page не указано. citeturn15search1turn15search0 |
| **Neurus AUSC12** | `MEDIUM` | Российское ПО и local integration сильны; происхождение мобильного шасси, камер и compute публично не раскрыто. citeturn14search8 |
| **Aeromax BAS** | `MEDIUM` | Собственное производство БВС и российская эксплуатация подтверждены, но electronics/engine/sensor BOM недостаточно прозрачен для LOW. citeturn14search4turn14search0 |
| **Geoscan 701** | `UNKNOWN` | Недостаточно актуальной официальной model-level procurement и component evidence в собранной выборке; нельзя интерпретировать это как недоступность. citeturn16search1turn16search2 |
| **Electromotiv inspector** | `UNKNOWN` | >75% локализации заявлено Сколково, но нет достаточного datasheet/service/procurement trail. citeturn14search2 |

Очень важный для архитектуры RobCo вывод: **supply risk и localization — ортогональные параметры**. Российское ПО на китайском шасси может давать низкий риск software lockout, но высокий hardware OEM risk. И наоборот, глубоко локализованный робот может использовать один критический иностранный compute module, который превращает этот модуль в single point of supply failure. Это особенно ясно на RoboCV, Granit и SMP Inspector. citeturn1search1turn25search1turn15search1

## Рекомендации RobCo и demo-cases

Для production-версии RobCo я бы не пытался представить все найденные 24 позиции как равноправные. Нужен небольшой **selectable reference set**, где технические параметры, procurement и российский сервис доказаны достаточно хорошо, а более спорные решения остаются в discovery catalog.

**Рекомендованные десять selectable solutions.**

| Priority | Solution | Почему включить в RobCo | Demo-case | Главный caveat |
|---|---|---|---|---|
| **A** | **Ronavi H1500** | Чистый и хорошо документированный AMR reference: 1500 кг, aisle 750 мм, до 10 ч, SLAM/QR, API/WMS; есть публичный price anchor. citeturn0search0 | Склад | Critical-components localization не раскрыта |
| **A** | **Automacon AK-2000-2** | Реальный pallet/forklift fleet и крупные российские внедрения; 2 т payload, 3D SLAM, service/spares РФ. citeturn5search1turn5search2 | Склад / large logistics | Не маркировать hardware как полностью российский без BOM |
| **A** | **Evocargo N1** | Очень сильный reference для outdoor/yard autonomous transport; 2 т, RaaS, десятки deployments и аэропортовый сценарий. citeturn0search1 | **Аэропорт**, логистический парк | Purchase CAPEX может быть неприменим — считать RaaS/TCO |
| **A** | **Neurus AUSC12** | Специализированная inventory robotics: 12-м мачта, 0.6 м/с, 2 ч, autocharge, WMS/API. citeturn14search8 | **Склад** | Hardware provenance требует supplier questionnaire |
| **A** | **Promobot M13** | Российский PP719 cobot с качественной technical spec; 13 кг, 1.3 м, ±0.05 мм. citeturn20search1turn2search1 | Manufacturing / back-of-house | Не AMR; нужен отдельный process template |
| **A** | **RusRobot RR120-2900** | Сильный reference отечественного тяжелого industrial manipulator: 120 кг, 2.9 м, PP719, serial production in Chelyabinsk. citeturn21search4turn24view0 | Manufacturing / pallet handling | Повторяемость и cycle data не опубликованы на текущей product page |
| **A** | **TECHNORED REDCARGO BASIC 10** | Очень хороший RobCo reference для готовой паллетизирующей ячейки: payload 10 кг, 6–12 cycles/min, footprint 1.45×1.45 м, explicit kit. citeturn26search1 | Склад / упаковочная зона | Localization cell ≠ доказанная локализация всех robot components |
| **A** | **Waybot Cleanbotics 600** | Отличная комбинация technical + commercial + service evidence; применимо к большим терминалам и клиникам. citeturn13search4turn12search0 | **Аэропорт / клиника** | Sensors/battery component origin incomplete |
| **A-** | **Yandex Rover Gen4 service** | Редкий российский доказанный healthcare delivery scenario: лекарства, расходники, биоматериалы; масштабный реальный fleet. citeturn11search0turn11search4 | **Клиника / campus** | Представлять как `robotic_delivery_service`, а не стандартный hardware purchase |
| **A-** | **SMP Inspector T5.5/T7.5** | Один из лучших открытых российских datasheet для autonomous inspection: −45…+45°C, IP65, 20 км, до 6 ч, GNSS+vision. citeturn15search1 | Аэропорт perimeter / logistics yard / industrial site | NVIDIA compute dependency → `HIGH` supply risk |

Для промышленной робототехники **Valdai Beryl** достоин статуса первого alternate к RusRobot: техническая документация, российское ПО, ПП №719, действующая декларация и explicit lead time делают его почти идеальным procurement reference. При расширении каталога industrial arms я бы хранил оба — Beryl как 25-kg general-purpose arm и RR120 как 120-kg heavy arm. citeturn25search0turn25search2turn25search4

**Что российский рынок закрывает хорошо.** На основании собранных данных наиболее убедительно закрыты: AMR/FMR для перемещения паллет и стеллажей; автономная перевозка грузов по закрытым промышленным территориям; автономизация погрузчиков/тягачей на уровне российского software stack; промышленные манипуляторы и cobots; паллетизация; автономная уборка больших помещений; outdoor inspection; складская robot inventory. Здесь есть не только демонстрационные проекты, но и серийные продукты, сервис, интеграция и российские customer cases. citeturn0search0turn5search2turn0search1turn20search1turn26search1turn12search0turn15search0turn14search8

**Где российские аналоги слабо подтверждены.** В исследованных открытых источниках не найден столь же хорошо документированный российский покупаемый SKU для классического indoor hospital delivery AMR с лифтовой интеграцией, автоматическими дверями и hospital fleet manager; для этого сценария наиболее доказан Яндекс, но как управляемый delivery service. Также слабее задокументированы серийные российские depalletizing cells, полностью отечественные high-bay reach-trucks с прозрачным BOM, стандартизированные high-speed sorting SKUs и отдельные inventory drones для полетов внутри склада. Наличие интеграторов или прототипов в этих классах не следует трактовать как отсутствие продукта — RobCo должен возвращать `UNVERIFIED`, пока evidence layer не станет сильнее. citeturn11search0turn26search2turn14search8

**Склад.** Базовый reference stack RobCo может строиться как Ronavi H1500 для горизонтального pallet movement; Automacon AK-2000-2 для автономного pallet handling; Neurus AUSC12 для инвентаризации; REDCARGO для end-of-line palletizing. Для участков с высокими требованиями к throughput Automacon особенно интересен благодаря реальным внедрениям десятков машин, однако его OEM provenance должен отображаться пользователю отдельным warning badge. citeturn0search0turn5search1turn5search2turn14search8turn26search1

**Аэропорт / крупный логистический объект.** Evocargo является наиболее прямым российским reference: отдельный кейс Жуковского подтверждает applicability к apron cargo movement, а коммерческая RaaS-модель позволяет RobCo считать OPEX-сценарий наряду с CAPEX. Для терминала Cleanbotics 600 подходит как cleaning benchmark; Waybot указывает Пулково среди внедрений. Для perimeter/technical inspection SMP Inspector дает сильный outdoor reference с IP65 и диапазоном −45…+45°C. citeturn0search1turn12search0turn15search1

**Клиника / сервисный объект.** Наиболее доказательная комбинация сегодня — Waybot для уборки и Yandex Rover для внутренней/межкорпусной логистики в тех сценариях, где service model допустима. Promobot V4 может закрывать front-of-house функции — навигацию посетителей, коммуникацию и сервисное взаимодействие, но его нельзя подменять термином `delivery robot`, поскольку основной публично описанный сценарий V4 — сервис/консультация, а не автономная перевозка медицинских грузов. citeturn12search0turn11search0turn1search6

## Модель данных RobCo и JSON-ready dataset

Существующей модели `RobotModel`, ориентированной преимущественно на `payload / dimensions / speed / price`, для российского procurement layer недостаточно. Российский кейс показывает, что RobCo должен хранить **provenance graph**, а не одно поле «страна производителя».

Я рекомендую добавить как минимум следующие группы полей:

| Field | Type | Зачем |
|---|---|---|
| `manufacturer_country` | ISO country / nullable | Страна юридического производителя |
| `legal_manufacturer_name` | string | Не смешивать brand и юридическое лицо |
| `brand_owner_country` | ISO country | Важен при rebrand |
| `manufacturing_country` | ISO country / `"UNVERIFIED"` | Где реально производится/собирается SKU |
| `development_country` | ISO country[] | Где разработано hardware/software |
| `localization_status` | enum | Например `RU_PP719_REGISTERED`, `RU_DESIGNED_ASSEMBLED_COMPONENTS_UNDISCLOSED`, `RU_SOFTWARE_ON_FOREIGN_BASE`, `FOREIGN_OEM_RU_DISTRIBUTOR` |
| `localization_percent` | number/null | **Только из доказательного источника** |
| `localization_percent_source_id` | source/null | Запрещает вычислять процент самим |
| `russian_industrial_registry_status` | enum | `CONFIRMED`, `NOT_FOUND`, `UNVERIFIED`, `NOT_APPLICABLE` |
| `russian_industrial_registry_number` | string/null | Реестровый номер |
| `russian_software_registry_status` | enum | Отдельно для ПО |
| `oem_rebrand_status` | enum | `ORIGINAL_MAKER`, `LOCALIZED_OEM`, `SUSPECTED_FOREIGN_OEM_BASE`, `FOREIGN_OEM`, `UNVERIFIED` |
| `underlying_oem` | object/null | Реальный OEM, если установлен |
| `oem_match_confidence` | 0–1 | Позволяет хранить именно подозрение, а не факт |
| `critical_import_components` | array | Lidar, servo, reducer, compute, battery, safety PLC и т.д. |
| `component_origin_confidence` | 0–1 | Качество BOM evidence |
| `procurement_status_russia` | required enum | Запрошенное пользователем поле |
| `procurement_confidence` | 0–1 | Evidence confidence |
| `procurement_mode` | enum[] | `CAPEX_PURCHASE`, `LEASE`, `RENTAL`, `RAAS`, `MANAGED_SERVICE` |
| `quote_available` | boolean/null | Можно ли получить КП |
| `current_sales_evidence_date` | date/null | Защита от устаревших каталогов |
| `service_in_russia` | enum | `MANUFACTURER`, `AUTHORIZED_PARTNER`, `DISTRIBUTOR`, `NONE_CONFIRMED`, `UNVERIFIED` |
| `spare_parts_in_russia` | enum | Не смешивать service и склад запчастей |
| `commissioning_in_russia` | boolean/null | Procurement readiness |
| `training_in_russia` | boolean/null | Procurement readiness |
| `public_russian_deployments` | array | Сustomer evidence |
| `deployment_count_evidence` | object/null | Число + дата + source |
| `supply_risk` | required enum | `LOW/MEDIUM/HIGH/UNKNOWN` |
| `supply_risk_reasons` | array | Машиночитаемое обоснование |
| `cloud_dependency` | enum | `NONE`, `OPTIONAL`, `REQUIRED`, `UNVERIFIED` |
| `offline_operation` | boolean/null | Critical для sanctions/vendor-lockout |
| `foreign_activation_required` | boolean/null | Очень важное procurement field |
| `update_dependency` | enum | `LOCAL_VENDOR`, `FOREIGN_OEM`, `CLOUD_VENDOR`, `UNVERIFIED` |
| `vendor_lockout_risk` | enum | `LOW/MEDIUM/HIGH/UNKNOWN` |
| `price_status` | required enum | `PUBLIC`, `PUBLIC_RANGE`, `QUOTE_REQUIRED`, `RAAS_QUOTE`, `UNVERIFIED` |
| `vat_status` | enum | `INCLUDED`, `EXCLUDED`, `NOT_STATED` |
| `price_evidence_date` | date/null | Цена быстро устаревает |
| `lead_time_value` | number/null | Вместо текста |
| `lead_time_unit` | enum | days/weeks/months |
| `lead_time_basis` | enum | `IN_STOCK`, `BUILD_TO_ORDER`, `PROJECT`, `UNVERIFIED` |
| `source_quality` | required enum | A/A-/B/C или numeric |
| `field_evidence` | map | На **каждое значение** → source/date/confidence |
| `data_conflict_flags` | array | Для конфликтующих цифр разных страниц |
| `last_verified_at` | datetime | Ключевой operational field |

Кроме того, RobCo стоит отказаться от единственного `payload` для всех классов. Для манипулятора это `rated_payload_kg`; для AMR — `transport_payload_kg`; для БПЛА — `useful_payload_kg`; для уборщика эта величина вообще малоинформативна. Аналогично `autonomy` необходимо разложить на `runtime_h`, `range_km`, `battery_capacity`, `charge_time_h`, `opportunity_charging`, а `navigation` — на `localization_methods[]`, `infrastructure_required[]` и `gnss_dependency`. Собранные российские продукты наглядно показывают, почему единое строковое поле не работает. citeturn0search0turn15search1turn13search3

**JSON-ready core dataset.** Это нормализованный procurement layer; `null` означает «не подтверждено», а не «нет».

```json
{
  "dataset_version": "2026-09-10",
  "market": "RU",
  "solutions": [
    {
      "id": "RU-01",
      "manufacturer": "Ronavi Robotics",
      "brand": "Ronavi",
      "model": "H1500",
      "robot_class": ["AMR", "pallet_transport"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "localization_status": "RU_DESIGNED_PRODUCED_COMPONENTS_UNDISCLOSED",
      "oem_rebrand_status": "ORIGINAL_MAKER_CLAIMED",
      "payload_kg": 1500,
      "dimensions_mm": [1044, 654, 380],
      "max_speed_m_s": 1.5,
      "runtime_h": 10,
      "runtime_basis": "80_to_20_percent_SOC",
      "minimum_aisle_mm": 750,
      "navigation": ["QR", "SLAM"],
      "integration": ["Open API", "WMS", "MES"],
      "procurement_status_russia": "CONFIRMED_AVAILABLE",
      "procurement_confidence": 0.96,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "price_status": "PUBLIC_RANGE",
      "price_rub_min": 2160000,
      "price_rub_max": 2700000,
      "vat_status": "NOT_STATED",
      "source_quality": "A",
      "source_refs": ["S1"]
    },
    {
      "id": "RU-02",
      "manufacturer": "Ronavi Robotics",
      "brand": "Ronavi",
      "model": "M",
      "robot_class": ["AMR", "FMR", "goods_to_person"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "localization_status": "RU_DESIGNED_PRODUCED_COMPONENTS_UNDISCLOSED",
      "oem_rebrand_status": "ORIGINAL_MAKER_CLAIMED",
      "payload_kg_max": 1200,
      "navigation": ["SLAM"],
      "integration": ["Open API", "WMS"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.91,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S2"]
    },
    {
      "id": "RU-03",
      "manufacturer": "Automacon",
      "brand": "RIX",
      "model": "AK-L3",
      "robot_class": ["AMR", "FMR"],
      "manufacturer_country": "RU_SYSTEM_SUPPLIER",
      "manufacturing_country": "RU_ASSEMBLY_CLAIMED",
      "localization_status": "RU_WCS_INTEGRATION_SUSPECTED_FOREIGN_OEM_BASE",
      "oem_rebrand_status": "SUSPECTED_FOREIGN_OEM_BASE",
      "underlying_oem_candidate": "HIKROBOT Q3-600C",
      "oem_match_confidence": 0.75,
      "payload_kg": 600,
      "dimensions_mm": [940, 650, 250],
      "max_speed_m_s": 2.0,
      "runtime_h_min": 8,
      "charge_time_h_max": 1.5,
      "turning_radius_mm": 995,
      "positioning_accuracy_mm": 10,
      "navigation": ["QR", "Laser SLAM", "Visual SLAM"],
      "procurement_status_russia": "CONFIRMED_AVAILABLE",
      "procurement_confidence": 0.86,
      "supply_risk": "HIGH",
      "service_in_russia": "MANUFACTURER_GROUP",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "B",
      "source_refs": ["S3", "S25"]
    },
    {
      "id": "RU-04",
      "manufacturer": "Automacon",
      "brand": "RIX",
      "model": "AK-2000-2",
      "robot_class": ["robotic_forklift", "pallet_transport"],
      "manufacturer_country": "RU_SYSTEM_SUPPLIER",
      "manufacturing_country": "RU_PRODUCTION_CLAIMED",
      "localization_status": "RU_WCS_INTEGRATION_HARDWARE_PROVENANCE_INCOMPLETE",
      "oem_rebrand_status": "UNVERIFIED",
      "payload_kg": 2000,
      "dimensions_mm": [1980, 1065, 2285],
      "runtime_h_min": 6,
      "runtime_h_max": 8,
      "charge_time_h": 2,
      "turning_radius_mm": 1555,
      "lift_mm": 175,
      "navigation": ["3D Laser SLAM"],
      "procurement_status_russia": "CONFIRMED_AVAILABLE",
      "procurement_confidence": 0.94,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_GROUP",
      "spare_parts_in_russia": "CONFIRMED_BY_VENDOR",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S3"]
    },
    {
      "id": "RU-05",
      "manufacturer": "OMP",
      "brand": "OMP",
      "model": "AGV 300",
      "robot_class": ["AGV"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_CLAIMED",
      "localization_status": "RU_MANUFACTURE_CLAIMED_COMPONENTS_UNDISCLOSED",
      "oem_rebrand_status": "UNVERIFIED",
      "payload_kg_max": 300,
      "dimensions_mm": [890, 650, 297],
      "max_speed_m_s": 1.5,
      "navigation": ["inductive", "magnetic", "machine_vision_optional"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.78,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "B",
      "source_refs": ["S4"]
    },
    {
      "id": "RU-06",
      "manufacturer": "Technologies of Industrial Automation / 3D Technologies",
      "brand": "TPA",
      "model": "AGV family",
      "robot_class": ["AGV", "autonomous_tug", "robotic_stacker"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_CLAIMED",
      "localization_status": "RU_FULL_CYCLE_CLAIMED",
      "oem_rebrand_status": "UNVERIFIED",
      "navigation": ["embedded_wire", "magnetic_tape", "inertial", "laser"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.74,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "B",
      "source_refs": ["S5"]
    },
    {
      "id": "RU-07",
      "manufacturer": "Evocargo",
      "brand": "Evocargo",
      "model": "N1",
      "robot_class": ["autonomous_transport_platform", "autonomous_cargo_vehicle"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_OWN_PRODUCTION_CLAIMED",
      "localization_status": "RU_AUTONOMY_OWN_VEHICLE_PRODUCTION_COMPONENT_BOM_UNDISCLOSED",
      "oem_rebrand_status": "ORIGINAL_MAKER_CLAIMED",
      "payload_kg": 2000,
      "range_km_max_public": 200,
      "procurement_mode": ["RAAS"],
      "procurement_status_russia": "CONFIRMED_AVAILABLE",
      "procurement_confidence": 0.98,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_MANAGED_SERVICE",
      "price_status": "RAAS_QUOTE",
      "source_quality": "A",
      "source_refs": ["S6"]
    },
    {
      "id": "RU-08",
      "manufacturer": "Valdai Robots",
      "brand": "Valdai",
      "model": "Granit",
      "robot_class": ["autonomous_transport_platform"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "localization_status": "RU_DESIGNED_MANUFACTURED_WITH_DISCLOSED_IMPORTED_COMPUTE",
      "oem_rebrand_status": "ORIGINAL_MAKER",
      "payload_kg": 3000,
      "dimensions_mm": [1500, 800, 415],
      "max_speed_km_h": 5,
      "runtime_h_max": 9,
      "battery": "LiFePO4 48V 105Ah",
      "compute": "LattePanda",
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.91,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S7"]
    },
    {
      "id": "RU-09",
      "manufacturer": "RoboCV",
      "brand": "X-MOTION NG",
      "model": "tug/stacker/reachtruck autonomy family",
      "robot_class": ["autonomous_tug", "robotic_stacker", "robotic_reachtruck"],
      "manufacturer_country": "RU_AUTONOMY_DEVELOPER",
      "manufacturing_country": "DEPENDS_ON_BASE_OEM",
      "localization_status": "RU_SOFTWARE_AUTONOMY_ON_THIRD_PARTY_BASE",
      "oem_rebrand_status": "AUTONOMY_RETROFIT_NOT_FULL_HARDWARE_OEM",
      "integration": ["WMS", "ERP"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.91,
      "supply_risk": "HIGH",
      "service_in_russia": "DEVELOPER_INTEGRATOR",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S8"]
    },
    {
      "id": "RU-10",
      "manufacturer": "Russian Robot / Robot Factory",
      "brand": "RusRobot",
      "model": "RR 120-2900",
      "robot_class": ["industrial_manipulator"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "development_location": "Russia",
      "manufacturing_location": "Chelyabinsk",
      "localization_status": "RU_PP719_REGISTERED",
      "russian_industrial_registry_status": "CONFIRMED",
      "russian_industrial_registry_number": "10625128",
      "oem_rebrand_status": "ORIGINAL_MAKER",
      "payload_kg": 120,
      "reach_mm": 2900,
      "axes": 6,
      "transport_dimensions_mm": [1700, 950, 1950],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.98,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_PARTNER_NETWORK",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A",
      "source_refs": ["S9", "S26"]
    },
    {
      "id": "RU-11",
      "manufacturer": "Promobot",
      "brand": "Promobot M",
      "model": "M13",
      "robot_class": ["cobot"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "manufacturing_location": "Perm",
      "localization_status": "RU_PP719_REGISTERED",
      "russian_industrial_registry_status": "CONFIRMED",
      "oem_rebrand_status": "ORIGINAL_MAKER",
      "payload_kg": 13,
      "reach_mm_max": 1300,
      "tcp_speed_m_s_nominal": 1.0,
      "repeatability_mm": 0.05,
      "ip_rating": "IP54",
      "operating_temperature_c": [5, 50],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.98,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A",
      "source_refs": ["S10", "S27"]
    },
    {
      "id": "RU-12",
      "manufacturer": "Valdai Robots",
      "brand": "Valdai",
      "model": "RP25.22ShS Beryl",
      "robot_class": ["industrial_manipulator"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "development_location": "Saint Petersburg",
      "manufacturing_location": "Moscow Region",
      "localization_status": "RU_PP719_REGISTERED_RU_SOFTWARE",
      "russian_industrial_registry_status": "CONFIRMED",
      "oem_rebrand_status": "ORIGINAL_MAKER",
      "payload_kg": 25,
      "reach_mm": 2200,
      "axes": 6,
      "linear_speed_m_s": 2,
      "positioning_accuracy_mm": 0.1,
      "repeatability_mm_range": [0.02, 0.2],
      "integration": ["PROFINET", "EtherCAT", "Modbus TCP", "VALDAi API"],
      "certifications": ["TR CU 010/2011", "TR CU 020/2011"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.98,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "lead_time_in_stock_months": 1,
      "lead_time_build_to_order_months": [4, 7],
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A",
      "source_refs": ["S11", "S28"]
    },
    {
      "id": "RU-13",
      "manufacturer": "TECHNORED",
      "brand": "REDCARGO",
      "model": "BASIC 10 cobot",
      "robot_class": ["palletizing_cell"],
      "manufacturer_country": "RU_SYSTEM_MANUFACTURER",
      "manufacturing_country": "RU_SYSTEM_PRODUCTION",
      "localization_status": "RU_CELL_SOFTWARE_INTEGRATION_EMBEDDED_ARM_PROVENANCE_UNVERIFIED",
      "oem_rebrand_status": "SYSTEM_INTEGRATOR_OEM_PROVENANCE_UNVERIFIED",
      "payload_kg": 10,
      "reach_mm": 1350,
      "cycle_rate_per_min_min": 6,
      "cycle_rate_per_min_max": 12,
      "repeatability_mm": 0.1,
      "footprint_mm": [1450, 1450],
      "max_pallet_mm": [1200, 800],
      "max_stack_height_mm": 1100,
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.96,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_INTEGRATOR",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S12"]
    },
    {
      "id": "RU-14",
      "manufacturer": "Aripix Robotics",
      "brand": "Aripix",
      "model": "custom pick/sort/packing RTK",
      "robot_class": ["pick_and_place_cell", "sorting_cell", "packaging_cell"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_SYSTEM_ASSEMBLY",
      "localization_status": "RU_ENGINEERING_CONTROLLERS_WITH_IMPORTED_COMPONENTS",
      "oem_rebrand_status": "CUSTOM_SYSTEM",
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.87,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_INTEGRATOR",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "B+",
      "source_refs": ["S13"]
    },
    {
      "id": "RU-15",
      "manufacturer": "Promobot",
      "brand": "Promobot",
      "model": "V.4",
      "robot_class": ["indoor_service_robot", "reception_robot", "guide_robot"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "manufacturing_location": "Perm",
      "localization_status": "RU_SOFTWARE_ASSEMBLY_COMPONENT_BOM_INCOMPLETE",
      "oem_rebrand_status": "ORIGINAL_MAKER",
      "navigation": ["autonomous_indoor_mapping"],
      "sensors": ["16 sensors", "3D camera"],
      "integration": ["SDK", "external databases", "web services"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.95,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S14"]
    },
    {
      "id": "RU-16",
      "manufacturer": "Yandex",
      "brand": "Yandex Rover",
      "model": "Generation 4",
      "robot_class": ["robotic_delivery_service", "campus_delivery_robot"],
      "manufacturer_country": "RU_DEVELOPER_OPERATOR",
      "manufacturing_country": "UNVERIFIED",
      "localization_status": "RU_AUTONOMY_SOFTWARE_HARDWARE_MANUFACTURING_UNVERIFIED",
      "oem_rebrand_status": "ORIGINAL_PLATFORM_DEVELOPER_HARDWARE_FACTORY_UNVERIFIED",
      "procurement_mode": ["MANAGED_SERVICE"],
      "offline_operation": null,
      "procurement_status_russia": "CONFIRMED_AVAILABLE",
      "procurement_confidence": 0.96,
      "supply_risk": "MEDIUM",
      "service_in_russia": "VENDOR_MANAGED_SERVICE",
      "price_status": "SERVICE_QUOTE",
      "source_quality": "A",
      "source_refs": ["S15"]
    },
    {
      "id": "RU-17",
      "manufacturer": "Waybot Robotics",
      "brand": "Cleanbotics",
      "model": "400 PRO",
      "robot_class": ["autonomous_cleaning_robot"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_CLAIMED",
      "localization_status": "RU_SOFTWARE_SYSTEM_BODY_COMPONENTS_PARTLY_UNDISCLOSED",
      "oem_rebrand_status": "ORIGINAL_SYSTEM_CLAIMED",
      "dimensions_mm": [1064, 560, 744],
      "mass_kg": 50,
      "runtime_h": 3,
      "charge_time_h": 1,
      "cleaning_width_mm": 400,
      "productivity_m2_h_min": 700,
      "productivity_m2_h_max": 1200,
      "offline_operation": true,
      "procurement_status_russia": "CONFIRMED_AVAILABLE",
      "procurement_confidence": 0.99,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_CONTRACTOR_NETWORK",
      "price_status": "PUBLIC",
      "price_rub": 1500000,
      "monthly_service_rub": 30000,
      "vat_status": "NOT_STATED",
      "source_quality": "A",
      "source_refs": ["S16"]
    },
    {
      "id": "RU-18",
      "manufacturer": "Waybot Robotics",
      "brand": "Cleanbotics",
      "model": "600",
      "robot_class": ["autonomous_cleaning_robot"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_CLAIMED",
      "localization_status": "RU_SOFTWARE_SYSTEM_COMPONENTS_PARTLY_UNDISCLOSED",
      "oem_rebrand_status": "ORIGINAL_SYSTEM_CLAIMED",
      "dimensions_mm": [700, 600, 1000],
      "mass_kg": 140,
      "runtime_h": 4,
      "charge_time_h": 1,
      "cleaning_width_mm": 600,
      "productivity_m2_h_max": 1600,
      "procurement_status_russia": "CONFIRMED_AVAILABLE",
      "procurement_confidence": 0.99,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_CONTRACTOR_NETWORK",
      "price_status": "PUBLIC",
      "price_rub": 2300000,
      "vat_status": "NOT_STATED",
      "source_quality": "A",
      "source_refs": ["S17"]
    },
    {
      "id": "RU-19",
      "manufacturer": "Yacu.ai",
      "brand": "Yacu",
      "model": "Unit",
      "robot_class": ["autonomous_cleaning_robot"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_CLAIMED",
      "localization_status": "RU_SOFTWARE_CHASSIS_THIRD_PARTY_CLEANING_MODULES",
      "oem_rebrand_status": "ORIGINAL_SYSTEM_CLAIMED",
      "dimensions_mm": [900, 560, 800],
      "filled_mass_kg": 130,
      "runtime_h": 5,
      "clean_water_l": 50,
      "dirty_water_l": 50,
      "coverage_per_cycle_m2": 7200,
      "navigation": ["360_lidar", "radar", "stereo_camera", "RTLS"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.86,
      "supply_risk": "MEDIUM",
      "service_in_russia": "DEALER_NETWORK",
      "manufacturing_lead_time_months": 2,
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S18"]
    },
    {
      "id": "RU-20",
      "manufacturer": "Aeromax",
      "brand": "Aeromax",
      "model": "A-5/B-120/B-200 family",
      "robot_class": ["industrial_UAV", "inspection_UAV"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU_OWN_PRODUCTION_CLAIMED",
      "localization_status": "RU_AIRCRAFT_DEVELOPMENT_PRODUCTION_BOM_UNDISCLOSED",
      "oem_rebrand_status": "ORIGINAL_MAKER_CLAIMED",
      "procurement_mode": ["PROJECT", "MANAGED_SERVICE"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.91,
      "supply_risk": "MEDIUM",
      "service_in_russia": "MANUFACTURER_OPERATOR",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A-",
      "source_refs": ["S19"]
    },
    {
      "id": "RU-21",
      "manufacturer": "Geoscan",
      "brand": "Geoscan",
      "model": "701",
      "robot_class": ["industrial_UAV", "survey_UAV"],
      "manufacturer_country": "RU",
      "manufacturing_country": "UNVERIFIED_IN_CURRENT_RESEARCH",
      "localization_status": "RU_DEVELOPER_MODEL_LEVEL_PROVENANCE_INCOMPLETE",
      "oem_rebrand_status": "UNVERIFIED",
      "flight_time_h_max": 10,
      "wingspan_m": 3.3,
      "mtow_kg": 22,
      "procurement_status_russia": "LIKELY_AVAILABLE",
      "procurement_confidence": 0.70,
      "supply_risk": "UNKNOWN",
      "service_in_russia": "LIKELY",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "C+",
      "source_refs": ["S20"]
    },
    {
      "id": "RU-22",
      "manufacturer": "SMP Robotics",
      "brand": "Inspector",
      "model": "T5.5/T7.5",
      "robot_class": ["inspection_robot", "outdoor_AMR"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "localization_status": "RU_FULL_CYCLE_WITH_IMPORTED_NVIDIA_COMPUTE",
      "oem_rebrand_status": "ORIGINAL_MAKER",
      "dimensions_mm": [1520, 860, 1620],
      "mass_without_batteries_kg": 142,
      "runtime_h_max": 6,
      "range_km": 20,
      "typical_speed_km_h_min": 3,
      "typical_speed_km_h_max": 5,
      "turning_radius_m": 1.7,
      "recommended_lane_width_m": 1.3,
      "operating_temperature_c": [-45, 45],
      "ip_rating": "IP65",
      "navigation": ["GLONASS", "GPS", "BDS", "Galileo", "visual_fallback"],
      "critical_import_components": ["NVIDIA Jetson TX2", "NVIDIA Jetson Orin NX"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.96,
      "supply_risk": "HIGH",
      "service_in_russia": "MANUFACTURER",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A",
      "source_refs": ["S21"]
    },
    {
      "id": "RU-23",
      "manufacturer": "Neurus / Automacon",
      "brand": "Neurus",
      "model": "AI Stock Counter 12M AUSC12",
      "robot_class": ["warehouse_inventory_robot"],
      "manufacturer_country": "RU",
      "manufacturing_country": "UNVERIFIED_FOR_COMPLETE_HARDWARE",
      "localization_status": "RU_SOFTWARE_SYSTEM_HARDWARE_PROVENANCE_INCOMPLETE",
      "oem_rebrand_status": "UNVERIFIED",
      "mast_height_m": 12,
      "max_speed_m_s": 0.6,
      "runtime_h": 2,
      "scan_range_m": 2,
      "charging": "automatic",
      "integration": ["WMS", "ERP", "1C", "API"],
      "procurement_status_russia": "QUOTE_REQUIRED",
      "procurement_confidence": 0.94,
      "supply_risk": "MEDIUM",
      "service_in_russia": "AUTOMACON_GROUP",
      "price_status": "QUOTE_REQUIRED",
      "source_quality": "A",
      "source_refs": ["S22"]
    },
    {
      "id": "RU-24",
      "manufacturer": "Electromotiv",
      "brand": null,
      "model": "autonomous inspector",
      "robot_class": ["inspection_robot", "security_robot"],
      "manufacturer_country": "RU",
      "manufacturing_country": "RU",
      "localization_status": "RU_DESIGNED_MANUFACTURED_LOCALIZATION_OVER_75_PERCENT_REPORTED",
      "localization_percent_min": 75,
      "localization_percent_basis": "external official innovation ecosystem report",
      "oem_rebrand_status": "ORIGINAL_MAKER_REPORTED",
      "procurement_status_russia": "UNVERIFIED",
      "procurement_confidence": 0.55,
      "supply_risk": "UNKNOWN",
      "service_in_russia": "UNVERIFIED",
      "price_status": "UNVERIFIED",
      "source_quality": "B-",
      "source_refs": ["S23"]
    }
  ]
}
```

## Sources appendix

Все источники ниже проверялись в рамках исследования **10 сентября 2026 года**. Там, где сама продуктовая страница не содержит даты публикации/обновления, дата обозначена как `n/d`; это намеренно, чтобы не выдавать дату crawling за дату технической ревизии документа. `confidence` относится к достоверности **того, что прямо заявлено источником**, а не к полноте BOM или будущей доступности товара.

| Ref | URL | source_type | Publication/update date | accessed_at | confidence / use |
|---|---|---|---|---|---|
| **S1** | `https://ronavi-robotics.ru/catalogue/h1500` | Official manufacturer product page | n/d, current | 2026-09-10 | **0.98** — H1500 specs, price, API, warranty, service. citeturn0search0 |
| **S2** | `https://ronavi-robotics.ru/catalogue/m` | Official manufacturer product page | n/d, current | 2026-09-10 | **0.95** — Ronavi M payload/use/navigation/procurement. citeturn4search6 |
| **S3** | Automacon/RIX product catalog, `https://agv.automacon.ru/` | Official manufacturer/integrator catalog | current 2026 | 2026-09-10 | **0.92** — AK-L/AK-2000 specifications; manufacturing claims. citeturn4search0turn5search1 |
| **S4** | `https://transport.o-m-p.ru/agvrobot` | Official manufacturer page | n/d | 2026-09-10 | **0.82** — OMP AGV dimensions/payload/speed/options. citeturn4search2 |
| **S5** | `https://www.agvrobot.ru/` | Official supplier/manufacturer page | n/d | 2026-09-10 | **0.78** — TPA/3D-Tech production and AGV types. citeturn4search8 |
| **S6** | `https://evocargo.com/` | Official manufacturer/operator | current 2026 | 2026-09-10 | **0.98** for current sales/service/cases; **0.8** for figures sourced via linked/secondary product coverage. citeturn0search1 |
| **S7** | `https://vald.ai/granit` | Official manufacturer product page | current 2026 | 2026-09-10 | **0.97** — Granit payload, dimensions, runtime, battery, compute. citeturn25search1 |
| **S8** | `https://robocv.ru/` | Official developer/integrator | current 2026 | 2026-09-10 | **0.96** — X-MOTION NG classes, WMS/ERP, customer cases. citeturn1search1 |
| **S9** | `https://rusrobot.ru/catalog/universalnyy-promyshlennyyrobot-rr-120-2900/` | Official product page | current 2026 | 2026-09-10 | **0.99** — RR120 payload/reach/dimensions/order. citeturn24view0 |
| **S10** | `https://promobot-m.ru/docs/m13-technical-specifications/` | Official technical specifications | current | 2026-09-10 | **0.99** — M13 numeric technical fields. citeturn2search1 |
| **S11** | `https://vald.ai/beryl` | Official manufacturer product/datasheet page | current 2026 | 2026-09-10 | **0.99** — Beryl technical data, manufacturing, software, API. citeturn25search0 |
| **S12** | `https://technored.ru/catalog/oborudovanie-dlya-peremesheniya-i-ukladki/zagruzochnye_pogruzochnye_resheniya/robototehnicheskij-kompleks-redcargo-10-cobot.html` | Official product catalog | current, crawled Aug 2026 | 2026-09-10 | **0.99** — REDCARGO BASIC 10 dimensions/cycle/payload/kit. citeturn26search1 |
| **S13** | `https://aripix.ru/` and current portfolio | Official developer/integrator | current 2026 | 2026-09-10 | **0.9** — system production/current cases; lower confidence for standardized model specs because projects are custom. citeturn9search0turn9search1 |
| **S14** | `https://promo-bot.ru/production/promobot-v4/` | Official manufacturer product page | current | 2026-09-10 | **0.95** — V4 function/navigation/integration/current sales. citeturn1search6 |
| **S15** | `https://yandex.ru/company/news/07-04-2026-04` plus current Yandex autonomy pages | Official developer/operator news | **2026-04-07** and current 2026 | 2026-09-10 | **0.99** — hospital deployment; **0.98** current service/fleet. citeturn11search0turn14search6 |
| **S16** | `https://www.waybotrobot.ru/cleanbotic-400` | Official product page | current 2026 | 2026-09-10 | **0.98** — Cleanbotics 400 PRO technical values; prices cross-checked against current Waybot site. citeturn13search2turn12search0 |
| **S17** | `https://waybotrobot.ru/cleanbotics-model-600` | Official product page | current 2026 | 2026-09-10 | **0.98** — Cleanbotics 600 specs. citeturn13search4 |
| **S18** | `https://yacuai.com/ru/unit/` | Official manufacturer product page | current | 2026-09-10 | **0.96** — Unit specs, commercial terms, service. citeturn13search3 |
| **S19** | `https://www.aeromax-group.ru/` and `https://www.aeromax-group.ru/services/monitoring/` | Official manufacturer/operator | current company page; monitoring page older/undated | 2026-09-10 | **0.97** company/current lineup; **0.75** older individual-aircraft performance values. citeturn14search4turn14search0 |
| **S20** | `https://www.rusgeocom.ru/` Geoscan 701 product listing | Russian specialist distributor | current listing; product technical data | 2026-09-10 | **0.7** — weak compared with manufacturer datasheet; therefore solution not top-tier selectable. citeturn16search2 |
| **S21** | `https://www.smprobotics.ru/robot-infrakrasnoy-diagnostiki-inspektor-t5-5` | Official manufacturer product/datasheet page | current 2026 | 2026-09-10 | **0.99** — Inspector numerical data, environment, battery, navigation, NVIDIA components. citeturn15search1 |
| **S22** | `https://automacon.ru/inventarizator/` | Official product page | current 2026 | 2026-09-10 | **0.99** — AUSC12 12 m, 2 h, 0.6 m/s, scan range, automatic charging. citeturn14search8 |
| **S23** | `https://sk.ru/news/na-territorii-innovacij-roboty-vyshli-na-sushu/` | Skolkovo official ecosystem news | **2026-06-23** | 2026-09-10 | **0.85** — Electromotiv RU development/production and >75% localization; weak for procurement because not vendor catalog. citeturn14search2 |
| **S24** | `https://vald.ai/news/gisp` | Official manufacturer registry/procurement news | **2025-05-14** | 2026-09-10 | **0.98** — Beryl PP719, serial availability, 1 / 4–7 month lead times. citeturn25search4 |
| **S25** | `https://www.zhineng518.com/page109?product_id=5311` | Chinese equipment listing/comparison evidence | n/d | 2026-09-10 | **0.70** — only for AK-L3/HIKROBOT similarity analysis; **not sufficient to prove OEM identity alone**. citeturn6search1 |
| **S26** | `https://rusrobot.ru/press-center/news/rusrobot-rr-120-2900-v-reestre-rossiyskoy-promyshlennoy-produktsii/` | Official manufacturer registry announcement | **2025-04-10** registry date | 2026-09-10 | **0.99** — PP719 register no. 10625128, Chelyabinsk production. citeturn21search4 |
| **S27** | `https://promobot-m.ru/` | Official manufacturer/current sales page | current 2026 | 2026-09-10 | **0.99** — Russian production, Perm address, PP719 claim, support/sales. citeturn20search1 |
| **S28** | Federal-accreditation-derived declaration page for Beryl | Conformity-registry evidence | registered **2025-02-18**, valid to **2030-02-13** | 2026-09-10 | **0.95** — manufacturer Russia; TR CU 010/2011 and 020/2011. citeturn25search2 |
| **S29** | `https://technored.ru/` | Official manufacturer/integrator | current 2026 | 2026-09-10 | **0.97** — Russian system production, service, cases; REDEDUCATION PRO PP719 dated 2026-07-16. citeturn19search0 |
| **S30** | `https://www.smprobotics.ru/o-kompanii-smp-robotics` | Official manufacturer company/production page | current 2026 | 2026-09-10 | **0.98** — full-cycle Russian engineering/production, >100 T5 robots by early 2023, service and finance model. citeturn15search0 |
| **S31** | `https://www.neurus.ru/projects/inventory` | Official developer product/project page | current 2026 | 2026-09-10 | **0.94** — inventory concept, software, 12 m mast and earlier technical evidence; conflicting scan-rate marketing data intentionally excluded from final capacity matching. citeturn14search1 |
| **S32** | `https://www.aeromax-group.ru/group-aeromax-avia/` | Official BAS operator group page | current | 2026-09-10 | **0.95** — commercial BAS operation in 57 Russian regions and monitoring/logistics services. citeturn14search12 |
| **S33** | `https://cobot.ru/` | Russian-language OEM sales site | current 2026 | 2026-09-10 | **0.98** for identifying Huayan Robotics product origin; demonstrates why `.ru` presence cannot define Russian manufacturing. citeturn21search6 |
| **S34** | `https://qrobotics.ru/` | Official Russian distributor | current | 2026-09-10 | **0.98** — explicit Gausium distributor evidence. citeturn12search6 |
| **S35** | `https://viggorobot.ru/` | Official Russian representative/service site | current | 2026-09-10 | **0.95** — Russian representation/service only; no basis to label hardware Russian. citeturn12search4 |

Итоговая procurement-логика для RobCo должна быть асимметричной: **сильное утверждение «российский производитель» разрешается только при сильном evidence, тогда как слабое evidence никогда не должно автоматически превращаться в «недоступно» или «иностранное»**. Для спорных случаев правильные значения — `UNVERIFIED`, `OEM_PROVENANCE_UNVERIFIED` или `SUSPECTED_FOREIGN_OEM_BASE`. Именно такой подход позволяет одновременно не завышать российскую локализацию и не исключать реальные российские решения только из-за того, что их производители пока публикуют документацию хуже глобальных OEM. citeturn21search0turn5search1turn6search1turn14search2