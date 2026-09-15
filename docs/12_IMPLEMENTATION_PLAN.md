# План доработки RobCo / «РобоМера» до финала хакатона

Статус: рабочий план команды. Версия: 1.1 от 13 сентября 2026 года.

Обновление 13 сентября: автономный 3D-движок RobCraft реализован отдельным модулем. Пункты первоначального плана про отсутствие simulation/collision больше не описывают фактическое состояние; актуальная граница проходит между демонстрационной сценарной симуляцией и инженерно валидированным digital twin.

Этот документ переводит продуктовую спецификацию и исследовательские выводы в последовательность реализации. Исходный backlog в `07_BACKLOG.md` сохраняется как полный перечень идей, но порядок и приоритеты ниже считаются операционными.

## 1. Цель финальной версии

За 3–5 минут пользователь и жюри должны увидеть доказуемую цепочку:

`описание процесса → качество входных данных → readiness → архитектура роботизации → технические ограничения → реальные варианты получения решения в РФ → требуемая мощность → экономика → what-if → визуализация → предварительное ТЭО`

Финальная версия не обязана быть промышленной SaaS-системой. Она обязана:

- воспроизводимо выполнять warehouse golden path;
- давать объяснимый отрицательный результат, когда роботизация пока не готова;
- не выдавать неизвестные параметры за подтверждённые;
- отделять техническую пригодность, procurement в РФ, экономику и доказательность;
- показывать формулы, источники и допущения;
- работать без внешнего LLM и live-сайтов;
- запускаться одной командой через Docker Compose.

## 2. Правила разработки

1. После каждого этапа сохраняется работающий demo path.
2. Не проводится big-bang rewrite: существующие расчёты переносятся в новые модули постепенно.
3. LLM извлекает и объясняет данные, но не принимает численные решения.
4. Architecture before SKU: сначала способ автоматизации, затем оборудование.
5. Критический `UNKNOWN` не становится `PASS` через скрытый default.
6. Любое число в результате имеет `USER_INPUT`, формулу, источник или маркированное `ASSUMPTION`.
7. Достоверность важнее количества моделей и экранов.
8. 2D-визуализация называется сценарием работы; RobCraft можно называть сценарной симуляцией, но не инженерным цифровым двойником.
9. Числовое ядро должно давать одинаковый результат для одинакового input и версий данных.
10. Новая функция не считается готовой без теста или зафиксированного golden fixture.

## 3. Приоритеты

### P0 — необходимо к защите

- warehouse golden path;
- process-level readiness;
- выбор 1–3 automation architectures;
- `PASS / FAIL / UNKNOWN / ASSUMED` для hard constraints;
- 8–10 вручную проверенных demo-curated записей;
- минимум две правдоподобные procurement alternatives для склада;
- traceable capacity и economics;
- пессимистичный, базовый и оптимистичный сценарии;
- корректная работа плана помещения;
- автономный запуск RobCraft и версионированный контракт будущей интеграции;
- evidence/confidence в UI и PDF;
- отрицательный сценарий;
- автоматические unit/golden/API smoke тесты;
- Docker, demo reset и публичный HTTPS-стенд.

### P1 — после стабильного P0

- отдельный airport/RaaS сценарий;
- clinic cleaning/delivery сценарий;
- сохранение проектов и AnalysisRun в БД;
- PostgreSQL/Alembic;
- расширенный evidence inspector;
- более красивый searchable PDF;
- дополнительные региональные профили;
- админка каталога.

### CUT до защиты

- ROS/Gazebo/Isaac и инженерно точная физика;
- калибровка по CAD/BIM, паспортной кинематике или реальной телеметрии;
- произвольный CAD/BIM import;
- полноценный route optimizer;
- live scraper цен;
- все субъекты РФ;
- управление реальными роботами;
- ERP/WMS-интеграция;
- billing, multitenancy и enterprise IAM.

## 4. Этап 0 — зафиксировать текущую точку

Оценка: 0,5–1 человеко-день. Владелец: V, продуктовая проверка: Z.

### Работы

- Зафиксировать warehouse fixture, на котором был создан текущий PDF.
- Сохранить ожидаемые входы, рекомендации, CAPEX, TCO, NPV и список отказов.
- Добавить минимальный pytest-контур и API smoke test.
- Зафиксировать текущий PDF и несколько скриншотов как baseline.
- Создать одну команду проверки: backend tests + frontend lint/build.
- Проверить, что Docker Compose стартует на чистой машине.
- Зафиксировать версии `rules`, `catalog`, `economics_defaults`, `regional_defaults` и приложения.

### Критерий завершения

Текущий warehouse demo защищён тестом, а последующий рефакторинг не может незаметно изменить его числа.

## 5. Этап 1 — новый контракт анализа и модульное ядро

Оценка: 1–2 человеко-дня. Владелец: V.

### Целевая структура

```text
backend/
  app/
    api/
    domain/
      models.py
      assumptions.py
      readiness.py
      architectures.py
      constraints.py
      capacity.py
      economics.py
      procurement.py
      confidence.py
      scenarios.py
    services/
      analysis.py
      intake.py
      reports.py
    data/
      catalog.json
      procurement.json
      sources.json
      regional_profiles.json
  tests/
    unit/
    golden/
    smoke/
```

Структура является ориентиром: дробить файлы нужно только там, где уже появилась отдельная ответственность.

### Работы

- Ввести `AnalysisInput`, `AnalysisResult` и отдельные DTO для этапов pipeline.
- Добавить `ParameterValue`: value, unit, source type, confidence, assumption/evidence ID.
- Добавить `Assumption`, `ConstraintResult`, `CapacityResult`, `EconomicsResult`, `ConfidenceResult`.
- Добавить `AutomationArchitecture`, `EquipmentModel`, `SolutionConfiguration`, `ProcurementOption`, `PriceEvidence`.
- Создать единый `AnalysisEngine`, оркестрирующий этапы в фиксированном порядке.
- Сохранить старый `/api/calculate` как временный adapter для существующего frontend.
- Добавить новый versioned endpoint `/api/v1/analysis`.
- Возвращать версии правил и данных в каждом результате.

### Критерий завершения

Один warehouse input проходит новый pipeline; существующий UI продолжает работать через adapter; formulas не находятся в API handler.

## 6. Этап 2 — freeze каталога, evidence и procurement

Оценка: 2–3 человеко-дня. Владельцы: Z — данные, V — схема и загрузка, EXT — sanity review.

### Работы с данными

- Выбрать 8–10 demo-curated решений, а не расширять каталог до десятков моделей.
- Для warehouse иметь 2–4 сопоставимых варианта: российский, китайский с каналом в РФ, global reference и при наличии service/RaaS.
- Разделить Manufacturer, EquipmentModel, SolutionConfiguration и ProcurementOption.
- Указать происхождение, OEM/rebrand/localization только там, где это подтверждено.
- Для каждого критического поля записать источник, дату наблюдения и confidence.
- Для цены зафиксировать currency, boundary, tax status, includes/excludes и status.
- Для РФ зафиксировать supplier/channel, service, spares, commissioning, supply risk и last verified date.
- Старые обобщённые записи вида «аналог MiR» оставить только как `DISCOVERY/REFERENCE_ONLY` либо заменить реальными моделями.
- Не использовать бюджетную заглушку как базовую цену рекомендации.

### Проверка источников

Research-отчёты используются для поиска кандидатов и правил, но citation token вида `turn...` сам по себе не является продуктовой ссылкой. Для demo-visible данных нужно повторно открыть первичный источник и сохранить настоящий URL.

### Критерий завершения

Для каждой модели, видимой в warehouse demo, можно ответить: что это, почему технически подходит, откуда взяты характеристики, что означает цена и как решение предполагается получить/обслуживать в России.

## 7. Этап 3 — readiness, architecture и hard constraints

Оценка: 3–4 человеко-дня. V — реализация, Z — правила и тексты.

### 3.1 Readiness Engine

Измерения:

- повторяемость и стандартизация процесса;
- физическая среда и инфраструктура;
- данные и интеграции;
- безопасность и взаимодействие с людьми;
- операционная готовность;
- экономический потенциал;
- качество доказательств и входных данных.

Hard stop хранится отдельно от score. Результат содержит dimension breakdown, blockers, preconditions, confidence и вопросы для проверки.

### 3.2 Architecture Selector

Для warehouse P0 достаточно небольшой taxonomy:

- `PALLET_TRANSPORT_AMR`;
- `GUIDED_AGV`;
- `AUTONOMOUS_FORKLIFT`;
- `TUGGER_TRAIN`;
- `PARTIAL_AUTOMATION`;
- `NOT_RECOMMENDED_YET`.

Selector возвращает 1–3 архитектуры, причины и preconditions до обращения к каталогу SKU.

### 3.3 Constraint Engine

Минимальные проверки warehouse:

- payload и геометрия груза;
- проход, doorway и turning envelope;
- pickup/drop interface;
- поверхность и уклон;
- indoor/outdoor и temperature range;
- рабочее время, charging opportunity и runtime;
- human traffic/safety;
- WMS/Wi-Fi/integration requirement.

Каждая проверка возвращает required, available, status, evidence/assumption и reason code. Критический `FAIL` блокирует рекомендацию. Критический `UNKNOWN` переводит решение в `NEEDS_VALIDATION`, а не в PASS.

### Критерий завершения

Golden warehouse даёт объяснимую архитектуру и кандидатов; узкий проход или неподходящий payload создаёт hard reject; отсутствие критической геометрии создаёт UNKNOWN с вопросом, а не скрытый успех.

## 8. Этап 4 — capacity engine

Оценка: 2–3 человеко-дня. V — реализация, Z/EXT — проверка assumptions.

### Работы

- Выделить strategy interface по calculation profile.
- Сначала довести `MOBILE_TRANSPORT`; остальные профили не должны усложнять его.
- Перестать использовать паспортную максимальную скорость как рабочую.
- Ввести mission cycle:

```text
loaded travel
+ empty travel
+ pickup
+ drop
+ station waiting
+ traffic allowance
+ charging allowance
```

- Учитывать operating window, peak shift share, availability/utilization и reserve units.
- Возвращать low/base/high cycle time и fleet size.
- Добавить formula trace с промежуточными значениями и единицами.
- Проверять результат sanity range из vendor data, но не подменять им формулу.
- Добавить тесты на монотонность: рост объёма/маршрута не уменьшает парк; рост производительности не увеличивает его.

### Критерий завершения

Пользователь может открыть расчёт и понять, почему требуется именно N роботов; эксперт может заменить допущение и получить предсказуемое изменение.

## 9. Этап 5 — economics, scenarios, procurement и region

Оценка: 2–3 человеко-дня. V+Z.

### Economics

- Сохранить существующие CAPEX/OPEX/TCO/NPV/payback формулы как основу.
- Расширить cost stack: logistics, mobilization, training, commissioning, safety, infrastructure и consumables.
- Отделить gross avoided cost, annual OPEX и net annual benefit.
- Передавать диапазоны цены и неопределённость в low/base/high.
- Не рассчитывать достоверный NPV, если цена `QUOTE_REQUIRED` и нет разрешённого allowance.
- Не монетизировать рост throughput без введённой пользователем маржинальной ценности.

### Scenarios

- Разделить architecture scenarios и procurement alternatives.
- Пессимистичный/base/оптимистичный сценарий не должен быть одним непрозрачным набором множителей.
- Возвращать delta к base и список изменённых assumptions.
- Ranking: hard gates → procurement eligibility → confidence → economics; не сортировать только по payback.

### Recurring mode

- Добавить один реальный `RAAS` или `MANAGED_SERVICE` сценарий после стабильного purchase path.
- Отдельно учитывать setup fee, recurring fee и retained internal costs.

### Region

- Добавить три минимальных профиля: Московская область, Магаданская область, Мурманская область.
- Регион влияет на labor fallback, logistics, mobilization, service и confidence.
- Фактическая среда эксплуатации имеет приоритет над климатическим hint.
- Не применять универсальные коэффициенты вида «Дальний Восток × 1,5».

### Критерий завершения

Система показывает технически подходящее решение, реалистичный способ получения в РФ и экономику с понятной границей цены. Смена procurement option или material assumption объяснимо меняет результат.

## 10. Этап 6 — frontend и работа с планом

Оценка: 3–4 человеко-дня. Z — UX/copy, V — реализация.

### Результаты анализа

Над fold:

- объект и процесс;
- readiness band и blockers;
- рекомендуемая архитектура;
- главный scenario outcome;
- installed CAPEX / recurring fee;
- net annual benefit, payback и NPV;
- overall confidence и procurement status.

Далее:

1. почему выбрана архитектура;
2. technical candidates;
3. procurement alternatives;
4. constraint matrix;
5. capacity trace;
6. economics breakdown;
7. assumptions/confidence;
8. what-if;
9. visualization;
10. evidence и next steps.

### Работа с планом

- Исправить передачу `mPerPx`, dimensions, zones и routes из uploader в analysis input.
- Не ожидать `avg_distance_m`, которого uploader не возвращает.
- Дать пользователю отметить pickup/drop или маршрут, а не только площадь зон.
- Рассчитать route distance из масштаба и точек.
- Передавать полученное расстояние в capacity engine.
- Строить visual route из тех же данных, которые использованы в расчёте.
- Если маршрут не размечен, явно показывать `illustrative route`.
- Не обещать распознавание CAD/BIM и автоматическую инженерную трассировку.

### What-if P0

- объём;
- число смен;
- длина маршрута;
- labor cost;
- operating speed/allowance;
- integration cost;
- equipment/system price;
- utilization/availability;
- procurement option.

### Критерий завершения

UI отображает все этапы causal chain, а загруженный план действительно изменяет входы расчёта. Пользователь отличает подтверждённое значение от assumption и UNKNOWN.

## 11. Этап 7 — предварительное ТЭО

Оценка: 1–2 человеко-дня. V — генерация, Z — содержание и язык.

### Структура отчёта

1. Цель и исходный процесс.
2. Входные данные и их происхождение.
3. Readiness, blockers и preconditions.
4. Рассмотренные архитектуры.
5. Constraint matrix выбранного решения.
6. Equipment/configuration.
7. Procurement alternatives в РФ.
8. Capacity formula trace.
9. CAPEX/OPEX/TCO/payback/NPV.
10. Пессимистичный/base/оптимистичный сценарии.
11. Региональные assumptions.
12. Риски и открытые вопросы.
13. План пилота, замеров и получения КП.
14. Sources appendix с URL и датами.

### Улучшения текущего PDF

- заменить `Readiness 95` на обоснованный process readiness;
- показать gross savings, OPEX и net benefit отдельно;
- убрать смешение русского и английского из пользовательских формулировок;
- не называть generic analog закупочной рекомендацией;
- по возможности перейти от image-only PDF к searchable HTML/print PDF;
- включить project/run ID и версии правил/каталога.

### Критерий завершения

Каждый demo-visible вывод отчёта трассируется до input, формулы, assumption или source. PDF не создаёт более сильных обещаний, чем сам движок.

## 12. Этап 8 — качество, deployment и защита

Оценка: 2–3 человеко-дня. V+Z.

### Автоматические проверки

- unit tests readiness rules;
- unit tests constraints;
- unit tests capacity/economics;
- evidence conflict test;
- regional fallback test;
- API contract/smoke;
- frontend happy-path E2E;
- deterministic repeat test;
- Docker healthcheck.

### Golden fixtures

1. Отапливаемый склад, стандартная логистика.
2. Тот же склад после изменения смен/объёма.
3. Узкий проход или недостаточный payload — hard reject.
4. Критический параметр отсутствует — NEEDS_VALIDATION.
5. Удалённый регион — меняются logistics/service/confidence, но не indoor payload fit.
6. Airport RaaS — P1, если P0 стабилен.
7. Clinic cleaning/delivery — P1, если P0 стабилен.

### Demo readiness

- публичный HTTPS URL;
- demo seed/reset;
- warm-up перед защитой;
- отсутствие зависимости от live vendor/Wordstat/weather API;
- backup screenshots;
- backup screen recording;
- заранее созданный PDF;
- локальный Docker fallback;
- прогон выступления на 3–5 минут;
- ответы на вопросы о точности ROI, источниках, simulation и отличии от ChatGPT.

### Критерий завершения

Golden path проходит минимум пять раз подряд на публичном стенде и локально. Отказ LLM не ломает расчёт. Команда может объяснить происхождение любого числа на главном экране.

## 13. Рекомендуемый порядок Pull Request / рабочих итераций

1. `tests/current-baseline`
2. `domain/analysis-contract-v1`
3. `data/demo-curated-catalog`
4. `engine/readiness-and-architecture`
5. `engine/constraint-statuses`
6. `engine/mobile-transport-capacity`
7. `engine/economics-confidence`
8. `engine/procurement-and-region`
9. `frontend/analysis-results`
10. `frontend/floorplan-data-flow`
11. `report/evidence-teo`
12. `qa/golden-e2e-deploy`

Каждая итерация должна быть небольшой, проверяемой и сохранять возможность запустить демо.

## 14. Распределение ответственности

| Область | Владимир | Женя | Внешний reviewer |
|---|---|---|---|
| Contracts/engine/API | Responsible | Consulted | — |
| Readiness/architecture rules | Implementation | Product owner | Sanity check |
| Catalog schema/loader | Responsible | Data owner | Review |
| Procurement evidence | Support | Responsible | Review |
| Economics | Implementation | Assumptions/copy | Domain check |
| Frontend | Implementation | UX/copy | — |
| PDF/pitch | Technical | Content owner | Review |
| Tests/deployment | Responsible | Acceptance | — |

## 15. Research routing

При сомнениях использовать локальные материалы так:

- `research/01_market_catalog.md` — характеристики, hard constraints и catalog records;
- `research/02_economics.md` — cost stack, labor benefit, NPV/TCO и uncertainty;
- `research/03_competitors.md` — позиционирование и отличие от существующих решений;
- `research/04_visualization.md` — граница между visualizer и simulation;
- `research/05_official_case.md` — соответствие официальному кейсу;
- `research/06_readiness.md` — dimensions, weights, hard stops и confidence;
- `research/07_russian_solutions.md` — российские решения, сервис и procurement;
- `research/08_chinese_solutions_ru.md` — китайские кандидаты и доступность в РФ;
- `research/09_search_demand.md` — только качественная терминология; частотности перепроверять;
- `research/10_regional_context_ru.md` — региональные факторы без псевдоточных коэффициентов.

## 16. Сомнительные пункты исходного плана

### Полная БД как P0

PostgreSQL/Alembic полезны, но не усиливают решение жюри сами по себе. До стабильного analysis pipeline достаточно versioned JSON и fixture-based runs. БД переносится в P1, если официальный критерий не требует сохранения проектов.

### Большой каталог

30–40 поверхностных записей слабее 8–10 доказательных. До защиты расширение discovery-каталога не является приоритетом.

### Одинаковая глубина трёх объектов

Warehouse должен быть полноценным. Airport и clinic могут показывать расширяемость на более узких сценариях. Нельзя жертвовать достоверностью склада ради трёх одинаково неглубоких веток.

### Продвинутый AI

Улучшение промпта не важнее deterministic core. Текущий fallback сохраняется; дополнительные LLM-возможности делаются после readiness/constraints/capacity.

### Полная замена генератора PDF

Сначала исправляется содержание отчёта. Технологию генерации можно заменить позже, если текущий image-based PDF остаётся надёжным на защите.

## 17. Общая оценка трудоёмкости

P0 составляет ориентировочно 15–20 человеко-дней. При работе двух участников и разумном параллелизме это примерно 8–12 рабочих дней, но фактический календарь зависит от доступности команды и внешней проверки данных.

Если времени меньше, сокращать в таком порядке:

1. не делать БД;
2. не углублять airport/clinic;
3. не расширять каталог;
4. оставить текущую технологию PDF;
5. сократить регион до двух профилей;
6. не сокращать correctness warehouse engine, evidence и golden tests.

## 18. Финальный Definition of Done

Проект готов к сдаче, когда:

- Docker поднимает систему одной командой;
- warehouse path работает без LLM;
- readiness относится к процессу, а не к выбранному роботу;
- архитектура выбирается раньше SKU;
- hard constraint имеет PASS/FAIL/UNKNOWN/ASSUMED и reason;
- рекомендация не определяется одной окупаемостью;
- fleet size имеет formula trace и не использует max speed как рабочую без allowance;
- минимум две warehouse procurement alternatives подтверждены для РФ;
- assumptions, evidence и confidence видны в UI и PDF;
- план помещения влияет на расстояние/сцену либо честно маркируется illustrative;
- отрицательный сценарий работает;
- golden tests проходят;
- публичный стенд и локальный fallback проверены;
- команда способна защитить каждое главное число и честно назвать границы результата.
