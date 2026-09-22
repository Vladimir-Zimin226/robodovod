# Контекст проекта «РОБОДОВОД»

Актуально на 20 сентября 2026 года; расчётный аудит baseline
`f77c32c2fde86cd1450aa96d43dc6273059c57d4`.

## Коротко

РОБОДОВОД (репозиторий `robodovod`, ранее RobCo / «РобоМера» / Prism) — хакатонный проект для кейса ЛЦТ‑2026 «Платформа подбора роботизированных решений с расчётом экономического эффекта и визуализацией работы роботов на объекте».

Продукт помогает владельцу процесса, не обязанному разбираться в робототехнике, пройти путь от описания проблемы до предварительно обоснованного сценария роботизации:

`объект → процесс → готовность → архитектура автоматизации → техническая пригодность → доступность в РФ → мощность → экономика → сценарии → визуализация → предварительное ТЭО`

One-liner: **от производственного процесса до обоснованного сценария роботизации за несколько минут**.

## Проблема и ценность

На ранней стадии заказчик обычно не знает, какой класс решения ему нужен, сколько единиц потребуется и во что обойдётся весь проект. Ответ собирается вручную из Excel, каталогов, консультаций интеграторов и неполных коммерческих данных.

РОБОДОВОД объединяет этот pre-feasibility этап и разделяет четыре независимых вопроса:

1. Может ли решение выполнить процесс технически?
2. Реалистично ли его приобрести, внедрить и обслуживать в России?
3. Получается ли приемлемая экономика с учётом всей стоимости проекта?
4. На каких источниках и предположениях основан вывод?

## Пользователь и демонстрационный сценарий

Основной пользователь — руководитель склада, производства, объекта, главный инженер или руководитель автоматизации. Golden path — склад в России: описание паллетных перемещений, уточнение параметров, подбор нескольких вариантов, жёсткий отсев несовместимых моделей, расчёт парка и экономики, what-if и интерактивный сценарий работы.

Дополнительные ветки прототипа: аэропорт/крупная логистика и клиника/сервис. Россия фиксирована как рынок MVP; регион должен влиять прежде всего на труд, логистику, сервис и риски, а на технический подбор — только через фактическую среду эксплуатации.

## Состояние реализации

Репозиторий содержит прототип и PostgreSQL control-plane/catalog/persistence.
Ниже перечислены реализованные подсистемы; это не утверждение, что нынешний
capacity pool уже подключён к полному end-to-end расчёту:

- FastAPI backend с versioned PostgreSQL repository и раздельными discovery/runtime slots;
- React 19 + Vite frontend;
- интервью на YandexGPT при наличии ключей и regex/fallback без них;
- пресеты для склада, аэропорта и клиники;
- hard-constraint filtering и список отклонённых решений;
- детерминированные расчёты fleet size, CAPEX, OPEX, TCO, payback, NPV и сценариев;
- расчёт единого процесса или нескольких независимых функциональных зон с общей
  экономической сводкой и зональным what-if;
- полный discovery-каталог 187 моделей / 223 позиции и materialized capacity
  pool 21 модель / 24 позиции; прежние 13 встроенных решений удалены;
- встроенную 3D-визуализацию поддержанного складского сценария и генерацию PDF в браузере.
- тёмный visualization-first dashboard с единой оболочкой, command input,
  readiness, реальными KPI, baseline/target, сценарным сравнением и responsive drawer;
- presentation-adapter, который выбирает рекомендацию только по `is_best` и
  формирует `NO_ACCEPTABLE_ECONOMICS` без ложной звезды или PDF; технически
  допустимый парк передаётся только для явно маркированной 3D-визуализации.

Автономный 3D-движок `robcraft/` («РобКрафт») также встроен в основной
React/FastAPI-сервис через same-origin iframe. Он поддерживает representative
multi-zone scenes, но не единую физическую модель всего здания:

- процедурная генерация склада, аэропорта и больницы по seed и нормализованной конфигурации;
- локальный разбор текстового описания объекта без сетевых запросов;
- вид от первого лица и свободная летающая камера;
- семь визуально и функционально разных типов мобильных роботов;
- детерминированные задания, погрузка, выгрузка, зарядка, отказы и KPI;
- упрощённая физика корпусов, препятствий, роботов и людей;
- динамический локальный A* вокруг препятствий, управление приоритетом и ограничение числа AMR в рабочей зоне;
- раздельные встречные полосы и ротация складских заданий между рядами и ячейками стеллажей;
- стационарные ролевые зоны людей вне транспортных коридоров;
- самостоятельный запуск на Node.js без runtime-зависимостей и контейнеров;
- отдельный творческий редактор сцены с 3D-выбором, строительством, трансформациями, роботами и Undo/Redo;
- версионированный ScenePatch поверх неизменяемой процедурной базы, импорт/экспорт JSON и обновляемые коллизии;
- безопасные ролевые зоны людей: контролёр склада, персонал терминала и пациенты/врачи в палатах без пешеходов в роботных коридорах;
- same-origin embedded-режим с непрерывным автопоказом, необязательным ручным
  осмотром, pointer lock, инспектором `E`, привязанным к ревизии ScenePatch и явным
  статусом изменённой геометрии без пересчёта экономики;
- немедленное стартовое задание, динамичный CameraDirector и доступный в embedded
  переключатель скорости ×1/×2/×4;
- многозонный embedded RobCraft: отдельные концептуальные сцены транспорта,
  клинической доставки, coverage-уборки и стационарной паллетизации, автоматическая
  ротация и ручной выбор зоны с явным fallback;
- 77 автоматических тестов генерации, навигации, поведения, физики, отчётности,
  редактора, расчётного ScenarioSpec, режиссёра камеры и iframe-протокола.

Подробный технический контекст движка: `13_ROBCRAFT_ENGINE.md`.

Текущий код — компактный демонстрационный монолит. Описанная в
`05_TECHNICAL_ARCHITECTURE.md` архитектура с PostgreSQL, SQLAlchemy, Alembic,
полноценными evidence/procurement/readiness-модулями и тестовыми слоями является
целевой: считать её уже реализованной нельзя. Принятый порядок следующей
итерации зафиксирован в `17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md`: сначала
границы хранения и фундамент БД, затем импорт проверенного каталога через
отдельный overlay и только после dual-run проверки — переключение backend.

Встроенные legacy-модели удалены. Production runtime и discovery читают только
явно активированные PostgreSQL slots; отсутствие безопасной runtime projection
даёт 503. Тесты расчётного ядра используют отдельные синтетические записи,
которые production-код не импортирует. До materialization официального
расчётного пула работоспособного runtime-каталога намеренно нет.

## Принципы, которые нельзя потерять

- Начинать с процесса и боли, а не с бренда робота.
- Сначала выбирать архитектуру решения, затем конкретные модели.
- LLM извлекает и объясняет данные, но не определяет численные итоги.
- Не смешивать technical fit, procurement fit и economics.
- `UNKNOWN` означает отсутствие подтверждения, а не ноль или отрицание.
- Цена робота не равна установленной стоимости проекта.
- Показывать диапазоны, assumptions, confidence и происхождение данных.
- Называть RobCraft интерактивной сценарной симуляцией, но не инженерным цифровым двойником и не источником подтверждённой пропускной способности.

## Исследовательская база

Проведены десять исследований: мировой каталог, экономика, конкуренты, визуализация, официальный кейс, readiness процесса, российские и китайские решения, поисковый спрос и региональный контекст РФ. Навигация находится в `research/README.md`, а принятые выводы и пробелы — в `04_RESEARCH_REGISTER_AND_GAPS.md`.

Критические незакрытые места перед финальной защитой:

- вручную перепроверить demo-curated модели, характеристики, свежесть цен и канал обслуживания в РФ;
- повторно проверить обновления официального кейса и Q&A;
- не использовать примерные Wordstat-частотности без реального замера;
- зафиксировать прозрачные readiness/procurement rules;
- использовать уже связанные с `zone.id` полигоны для единой физической модели,
  общих коридоров и межзональных потоков вместо справочного контурного слоя;
- не связывать frame loop режиссёра с расчётной экономикой.

Материалы организаторов импортированы в versioned production bundle:
сохранены 187 model identities, 223 отдельные catalog positions с
применимостью/ценой, официальные профили объектов, изображения,
описания и field-level provenance. Для 11 P0-решений выполнено
внешнее enrichment. Структурный QA пройден; неполные,
конфликтующие и неоднозначные сведения сохранены явными статусами и не
должны становиться расчётной истиной. Исходный `data/staging/` остаётся
исключённым из Git и не является runtime-источником.

## Совместная работа через архивные снимки

Женя работает с собственной локальной копией без Git-веток и Docker и передаёт
Владимиру проект архивом. Распакованные поставки находятся только в
`Разобрать/Версии проекта от Жени/`, а весь `Разобрать/` исключён из Git. Это
входящие снимки для сравнения, а не второй authoritative repository и не source
для копирования поверх текущего дерева.

При каждой новой поставке применяется один и тот же intake-процесс:

1. Зафиксировать текущий `git status`, дату и корень входящего снимка.
2. Не читать и не переносить реальные `.env`; исключить БД, `venv`,
   `node_modules`, caches, `dist` и иные generated artifacts.
3. Запустить доступные тесты/build самого снимка, затем выполнить semantic diff
   формул, тест-кейсов, API, UI и данных относительно текущего проекта.
4. Классифицировать изменения как `ADOPT`, `ADAPT`, `DEFER` или `REJECT` с
   причиной. Предпочитать сильную сторону Жени — предметную логику, формулы,
   граничные примеры и UX; архитектуру, security, persistence и contracts
   сверять с актуальными docs и кодом.
5. Переносить только минимальные самостоятельные изменения с новыми тестами.
   Golden fixtures не переписывать: при изменении формулы создавать следующую
   immutable-версию и сохранять предыдущую.
6. После интеграции прогонять основной regression suite; входящий снимок не
   становится runtime dependency и не коммитится.

Снимок от 16 сентября 2026 года (`projects/robomera`) прошёл 236 backend-тестов
и frontend build. Из него адаптированы три подтверждаемые корректировки текущей
экономики: отдельная индексация ФОТ и расходов на ричтраки, единый first-year
ramp OPEX для cash flow/TCO и статус `mixed` при частичном покрытии пульта.
SQLite/auth/catalog-admin, RaaS, XLSX import/export и дополнительные fleet rows
сохранены как референс для соответствующих плановых итераций, но напрямую не
перенесены. Недоказанные нормы, автоматические fallback-ТТХ и генерация fleet
stub с фиктивными характеристиками отвергнуты.

## Границы обещания

РОБОДОВОД выдаёт предварительную оценку. Он не заменяет обследование объекта, integrator engineering, safety validation, FAT/SAT и коммерческое предложение. Прототип не управляет реальными роботами и не гарантирует наличие оборудования. RobCraft моделирует диспетчеризацию, движение и столкновения на уровне демонстрационного сценария; его кинематика, геометрия и KPI пока не прошли инженерную валидацию.

## Ближайший приоритет команды

Встроенный warehouse golden path, PostgreSQL persistence, immutable
AnalysisRun, официальный discovery-каталог, XLSX/CSV intake, readiness,
architecture selection и hard constraints являются рабочей базой.
Встроенный legacy fleet удалён. Production runtime может читать только явно
активированную PostgreSQL-версию каталога; 223 official positions не становятся
расчётными без evidence-backed runtime facts.

`catalog/runtime-eligibility-contract-gap-audit-223` реализован только по
локальным данным. Contract v1 фиксирует четыре поддержанных equipment class и
capacity profile без формул; отчёт детерминированно покрывает 223 positions и
187 model identities. Распределение моделей: 0 `RUNTIME_READY`, 36
`NEEDS_FACTS`, 5 `CONFLICT_REVIEW`, 142 `UNSUPPORTED_CAPACITY_PROFILE`, 4
`NOT_EQUIPMENT`. Этот общий eligibility-аудит сохранён как исторический срез;
он не является текущим calculation-readiness решением.

`catalog/official-source-enrichment` исследован и сведён в review-only staging;
итерация materialization перенесла принятый срез в versioned ENRICHMENT bundle:
131 field fact и 154 evidence records для 26 моделей, 129 facts matching-safe, 2 review-only,
7 отложены и 318 остаются missing. Проекция после staging сохраняет 0
`RUNTIME_READY`; распределение моделей — 37 `NEEDS_FACTS`, 3
`CONFLICT_REVIEW`, 143 `UNSUPPORTED_CAPACITY_PROFILE`, 4 `NOT_EQUIPMENT`.
Staging не читается runtime-кодом: importer использует только его проверенную
коммитнутую проекцию. Эти результаты стали входом materialized capacity runtime; они не разрешают
автоматически активировать deployment runtime.

Для предварительных расчётов deployment readiness отделён от calculation
readiness versioned contract v2. По всему organizer catalog ядро
предварительного capacity-расчёта есть у 21 модели / 24 позиций; 15 моделей
требуют явных scenario assumptions, 6 готовы без них. В accepted research
cohort расчётно пригодны 19 из 26 identities. Итерация
`catalog/runtime-pool-materialization-ui-21` материализовала этот пул без БАС,
сохранила полный каталог из 223 позиций и добавила в каталог заметный тег
`Участвует в расчёте`, уточнение `С допущениями` и фильтр `Все / Участвуют /
Требуют данных`. Capacity DTO повторно проверяет evidence-gated facts и не
требует фиктивного legacy Robot DTO. Для end-to-end расчёта ещё нужны formula
trace и отдельная economics policy. Deployment-ready моделей по-прежнему 0; это не
разрешает закупочные claims. Полный контракт этапа находится в
`18_RUNTIME_POOL_AND_CATALOG_UI.md`.

Локальный end-to-end smoke после materialization подтвердил BASE/ENRICHMENT,
публикацию и discovery-активацию с 187 моделями / 223 позициями и capacity pool
21 / 24. Media rehydration отдельно зарегистрировала 189 content-addressed
assets для 223 позиций. Профильные Compose tools-сервисы следует запускать с
`--build` после обновления checkout: обычный `docker compose up --build` их не
собирает. При пересоздании PostgreSQL media metadata и position links нужно
восстановить повторным идемпотентным `catalog-media`, даже если одноимённый
binary volume сохранился.

Аудит 2026-09-19 полностью покрыл 14 файлов reference версии 3.2. Они являются
основой предметных формул; редакция1.1 разрешает конфликты по ТЗ/дополнениям; архитектура,
evidence gates, tenant isolation и воспроизводимые snapshots сохраняются.
Подробный [план 19](19_ZHENYA_CALCULATION_IMPLEMENTATION_PLAN.md) и
[inventory](planning/zhenya-source-inventory.md) фиксируют формулы,
расхождения, решения, вопросы и последовательность внедрения.

Новая поставка Жени `Референсы/reference v2` изучена 2026-09-22. Она сильно
расширяет labour/intake/finance/reconciliation, но содержит и внутренние
неоднозначности. Принятые K01–K29 остаются исполнимой основой; все новые идеи,
конфликты и source hashes сохранены в
[reference v2 delta-register](planning/zhenya-reference-v2-delta.md). Они
рассматриваются versioned на gates V2-A–V2-D и не переписывают registry v1 или
старые runs.

Этап **`contracts/calculation-semantics-v1`** (C01) завершён: добавлены строгие
units/quantity/process/role DTO, независимые capacity/finance statuses,
versioned `CalculationTrace`, replay digests, schema fixtures и proposed
registry contract без подключения к production API. Контрактный отчёт:
[calculation semantics v1](planning/calculation-semantics-contract-v1.md).

Этап **`data/calculation-parameter-registry-v1`** (C02) завершён: добавлены
immutable snapshot из 228 параметров, strict schemas, manifest с hashes
источников, coverage/supersession ledger и runtime-независимый loader. Таблица
трёх сценариев полна, unsafe salary/vendor defaults исключены. Отчёт:
[calculation parameter registry v1](planning/calculation-parameter-registry-v1.md).

Этап **`intake/process-role-normalization-v2`** (C03) завершён: добавлены
strict versioned intake/normalization contracts, exact K19 projection 28 блоков,
typed units, USER/FILE/LLM raw provenance, monthly gross salary без default
и compatibility adapter из существующего file import v1. Отчёт:
[calculation intake normalization v2](planning/calculation-intake-normalization-v2.md).

Этап **`frontend/process-role-intake-v2`** (C04) завершён: новый frontend
flow показывает object→process blocks→roles, сериализует только
raw C03 inputs, хранит input revision/override events, отклоняет
stale responses и показывает server-derived provenance. Legacy v1 forms
и runs сохранены. Отчёт:
[frontend process-role intake v2](planning/frontend-process-role-intake-v2.md).

Этап **`engine/applicability-constraints-v2`** (C05) завершён: добавлены
versioned strict request/report/rules contracts, scoped evidence-gated
PASS/FAIL/UNKNOWN/ASSUMED/N_A checks и единый v2 eligibility report для
readiness/execution. Legacy v1 runtime сохранён. Отчёт:
[applicability constraints v2](planning/applicability-constraints-v2.md).

Этап **`catalog/formula-executability-audit-v3`** (C06) завершён: добавлены
versioned dependency profiles F01–F07, evidence/unit/domain resolver,
раздельные catalog/run statuses, golden full-audit 187/223 и exact pool diff.
Membership остался 21/24, БАС не допущены. Отчёт:
[formula executability audit v3](planning/formula-executability-audit-v3.md).

Следующая малая итерация — **`engine/capacity-formula-trace`** (C07).
C07 использует завершённые registry, normalization, constraints и
executability audit. Нынешний `/api/calculate` требует legacy
Robot/economics; materialized CapacityRuntimeDTO ещё не образует независимый
расчётный endpoint. Calculation readiness не гарантирует исполнимость каждой
формулы при конкретном input и не означает deployment readiness.

Все C01–C29 и их acceptance gates обязательны к последовательной реализации.
Ограничение сложности относится только к новой логике сверх принятого плана:
его tax, replacement, allocation, sensitivity, simulation, export и rollout
этапы не упрощаются и не переводятся в optional.

Главные изменения целевого канона: полный exchange учитывается один раз,
peak×reserve отделён от availability; роли и USER gross salary вместо единого
fte_cost; full baseline/scenario cashflows с отдельным tax mode; purchase/RaaS
как независимая ось; server-owned trace и ScenarioSpec v2. Scheduling/SLA, scoring curves, pult allocation, annual ramp и НДС
определены в [policy v1](planning/calculation-policy-decisions-v1.md).
Все29конфликтов и12групп вопросов приняты к реализации без ожидания Жени.
Основная денежная база gross, по дополнениям организаторов; warehouse —
полный обязательный сценарий, все28process blocks имеют конечный scope. План не разрешает добавлять недоказанные vendor facts.
21/24 сохраняется как baseline до отдельного доказанного и согласованного
изменения membership; 187/223 discovery и отсутствие БАС в pool проверяются.

Реализованы аддитивные этапы C01–C06 и их целевые schema/serialization/data
tests. Формулы, production API/UI, versioned catalog и runtime slots не
менялись.

Команда: Владимир — технический лидер и интегратор authoritative tree; Женя —
продуктовая логика, формулы, граничные случаи и опыт пользователя. Замороженные
решения и владельцы открытых вопросов перечислены в
`11_DECISIONS_AND_OPEN_QUESTIONS.md`. Текущее задание Жене и заполняемый формат
возврата находятся в `ZHENYA_WORK_PACKAGE.md`.
