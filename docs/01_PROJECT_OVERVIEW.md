# RobCo — общее описание проекта v0.2

## 1. Проблема

Заказчик роботизации часто знает процесс и боль, но не знает:

- какой класс роботизации подходит;
- технически осуществима ли задача;
- какие параметры критичны;
- сколько оборудования потребуется;
- сколько стоит не робот, а весь проект;
- какие варианты реально доступны в России;
- насколько результат чувствителен к assumptions;
- что делать следующим шагом.

На практике ранняя стадия проекта распадается между Excel, каталогами производителей, звонками интеграторам, ручным поиском datasheets и экспертными интервью.

## 2. Product vision

RobCo — **платформа предварительного проектирования и технико-экономической оценки роботизации**.

Пользователь описывает объект, процесс и проблему обычным языком. RobCo переводит описание в engineering variables, оценивает readiness, предлагает несколько automation architectures, проверяет реальные решения по hard constraints, учитывает российскую закупочную применимость, рассчитывает capacity/economics, визуализирует сценарий и формирует preliminary ТЭО.

### One-liner

> **От производственного процесса до обоснованного сценария роботизации за несколько минут.**

### Более точный product statement

> **RobCo помогает понять, что автоматизировать, какой класс решения подходит, какие варианты реально рассматривать в России и какой предварительный business case получается.**

## 3. Primary user

**Владелец процесса, у которого есть проблема, но который не обязан знать робототехнику.**

Типовые роли:

- директор/руководитель производства;
- руководитель склада/логистики;
- главный инженер;
- директор по цифровой трансформации;
- руководитель объекта;
- operational excellence / automation specialist.

Secondary:

- интегратор/консультант — ускоряет pre-sale/assessment;
- CFO/инвесткомитет — проверяет assumptions/economics;
- technical reviewer — проверяет feasibility и evidence.

## 4. Core JTBD

Когда у меня есть ручной/дорогой/дефицитный/нестабильный процесс, я хочу быстро понять:

1. имеет ли роботизация смысл;
2. какая архитектура подходит;
3. что блокирует внедрение;
4. какие модели проходят ограничения;
5. какие решения реально доступны в РФ;
6. сколько единиц потребуется;
7. какой TCO/payback/NPV;
8. какие риски и неопределённости остаются;
9. что проверить пилотом/КП/замерами.

## 5. Product principles

### P1. Начинаем от процесса, а не от бренда

Первый вопрос — не «какого робота хотите?», а «что вы хотите автоматизировать?».

### P2. LLM — interface, не truth engine

LLM:

- ведёт интервью;
- извлекает факты;
- нормализует свободный текст;
- задаёт уточнения;
- объясняет вывод;
- собирает report narrative.

Deterministic engines:

- readiness;
- hard constraints;
- capacity;
- economics;
- scenario ranking;
- procurement policy.

### P3. Technical fit ≠ procurement fit

Технически отличный робот может иметь слабый российский канал/сервис. И наоборот, локально доступный робот может уступать по technical fit.

### P4. Архитектура раньше SKU

Сначала RobCo отвечает «какой тип решения нужен», затем «какими продуктами его можно реализовать».

### P5. Неизвестность — first-class data

`unknown/null` означает «не подтверждено», а не «нет».

### P6. Нет ложной точности

Показываются ranges, source, confidence и assumptions. Quote-only данные не превращаются в выдуманную среднюю цену.

### P7. Region-aware, но не geography-driven

Россия фиксирована. Регион уточняет economics/procurement/environment, но не подменяет параметры процесса.

### P8. Visualization and simulation — explanation, не ложная инженерная точность

Для 2D-слоя используются термины `scenario visualization`, `planned flow`, `illustrative playback`. Автономный RobCraft является интерактивной сценарной симуляцией с упрощёнными столкновениями и диспетчеризацией.

Даже для RobCraft нельзя использовать claims `validated throughput`, `engineering-grade collision-free`, `predicted congestion` или `digital twin prediction`, пока модель не откалибрована по реальному объекту.

## 6. Scope MVP

### Object families

1. Склад.
2. Аэропорт / крупный логистический объект.
3. Клиника / сервисный объект.

### Automation families

- AMR / AGV / pallet transport;
- autonomous forklift/stacker/tug;
- service delivery;
- autonomous cleaning;
- inspection robotics / UAV;
- industrial arm / cobot;
- palletizing/pick-and-place cell.

### Calculation profiles

- `MOBILE_TRANSPORT`;
- `MOBILE_SERVICE`;
- `FIXED_MANIPULATION`;
- `AERIAL_INSPECTION`.

## 7. Core outputs

Каждый AnalysisRun выдаёт:

- structured object/process profile;
- assumptions/completeness;
- readiness dimensions + blockers;
- automation architectures;
- technical candidates + hard rejects;
- procurement options RU;
- capacity/fleet/cycle estimate;
- CAPEX/OPEX/TCO/payback/NPV;
- conservative/base/upside sensitivity;
- regional adjustments/warnings;
- evidence/confidence;
- visualization scene;
- next validation steps;
- preliminary ТЭО.

## 8. Что продукт не делает

- не является procurement marketplace;
- не гарантирует наличие товара;
- не даёт юридических гарантий санкционной/экспортной доступности;
- не заменяет safety validation/FAT/SAT;
- не рассчитывает инженерно точную физическую симуляцию и не валидирует safety real-world системы;
- не программирует PLC/robot controller;
- не управляет fleet;
- не выдаёт среднюю зарплату региона за фактическую стоимость FTE клиента;
- не выдаёт региональный planning allowance за тариф перевозчика.

## 9. North-star для хакатона

Жюри должно увидеть **целостность causal chain**:

`боль → параметры → feasibility → architecture → real candidates → procurement reality RU → capacity → money → what-if → visual → report`.

Главная победная фича — не количество данных, а способность объяснить **почему** рекомендация изменилась при изменении process/region/procurement assumptions.
