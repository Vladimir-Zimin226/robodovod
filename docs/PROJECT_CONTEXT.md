# Контекст проекта «РОБОДОВОД»

## Актуальная задача — финальное соответствие ТЗ, 26.09.2026

По присланному CMD-журналу production обновлён до `de2b5bc`, backend healthy,
обе YC-переменные присутствуют в контейнере. Пользователь подтвердил работу
ИИ. Исправлены strict JSON Schema и лимиты генерации Brain/«Робоэксперта»;
живые локальные вызовы прошли. Общая финальная приёмка ТЗ ещё не завершена.

Повторно прочитаны оба PDF организаторов и проверен свежий диагностический
архив от 26.09.2026 01:51:11 UTC: все 30 файлов прошли SHA/row checks,
все четыре сохранённые симуляции связаны с точными ScenarioSpec своих runs.
Выявлены обязательные пробелы веб-управления каталогом, контекстного подбора,
импорта в новый путь, финансовой таблицы и визуального/табличного экспорта.
Brain-запросы в маленькой выборке занимают 11,8–60,1 с; есть fallback модели.

**F1 принят локально:** выбор сохранённых физических сценариев проекта,
видимые входы C11/ScenarioSpec/C23, общая привязка 2D/3D, условная зарядная
точка и отдельный SVG текущего кадра с KPI/digests. Проверены 220/120,
типовой склад, новые версии спроса/плеча/парка, owner isolation и неизменность
прежних snapshots/PDF/C23. Backend targeted 110, frontend 129, RobCraft 83,
lint/build и Chrome 1366×768/390 px прошли. Production не обновлялся.
[Отчёт F1 и свидетельства](planning/final-product-remediation-f1-2026-09-26.md).
**F2 принят локально:** гостевая страница шаблонов, XLSX/CSV `project-workbook-v1`,
внешний интервью-промпт, preview/diff, новая версия импорта/Brain и отдельные
подтверждения формы/экономики. Проверены 220/120 и типовой склад: manual,
форма и Brain дают равный C11; паспорт аэропорта/клиники сохраняется с честной
границей формул. Backend 146, frontend 133, lint/build, Chrome desktop/mobile
и native Excel roundtrip восьми книг прошли. История runs/artifacts/PDF и все
30 файлов архива неизменны. Production не обновлялся.
[Отчёт F2 и свидетельства](planning/final-product-remediation-f2-2026-09-26.md).
**F3 принят локально:** ADMIN web catalog create/edit, источники/ТТХ/цены/НДС,
отдельные предложения, справочники и разрешённые нормы; JSON import/diff,
validate/publish/atomic activation/rollback, owner/CSRF/role/concurrency и audit.
Новые физические профили informational до evidence/rollout; исходный
утверждённый пул сохраняется, формулы/registry не меняются. Backend 102,
frontend 133, lint/build, Chrome desktop/mobile и новый каталог → C11 →
экономика → C23 → 2D/3D → SVG/PDF прошли на 220/120 и типовом складе.
История runs/artifacts/catalog versions, PDF/XLSX и 30 файлов архива неизменны.
Production не обновлялся; для deploy понадобится миграция 0012.
[Отчёт F3 и свидетельства](planning/final-product-remediation-f3-2026-09-26.md).
**F4 принят локально:** каталог фильтруется по объекту/процессу, производителю,
готовности, зрелости, качеству ТТХ, цене и физическим диапазонам с явным unknown;
C05 возвращает объяснимые INCLUDED/EXCLUDED/REQUIRES_CHECK без повышения
непроверенных данных до PASS; новый C11 блокирует известный перегруз и RND.
Ручная форма и Brain используют совместимый
активный capacity-пул, три авторских демо и их источники сохранены.
Backend 125, frontend 134, lint/build, Chrome desktop/mobile для склада,
аэропорта, клиники и информационного сравнения прошли. Повторная физическая
цепочка 220/120 и типового склада прошла; прежние rows runs/artifacts/версий
каталога неизменны. Production не обновлялся.
[Отчёт F4 и свидетельства](planning/final-product-remediation-f4-2026-09-26.md).
**F5 выполнен локально:** новый сохранённый `commercial-scenarios-bundle-v3`
сравнивает baseline, покупку и RaaS на общем горизонте, отделяет ROI на CAPEX
от TCO/NPV и хранит по три параметра чувствительности ±10% для каждого из
семи представленных сценариев. PDF/XLSX/CSV/ZIP читают один immutable snapshot;
выбранный сохранённый C23 связан с PDF и автономным SVG через manifest/SHA.
Проверены 220 паллет/сутки на 120 м и типовой склад, Excel и Chrome desktop/mobile;
исторические runs и artifacts не переписывались. Production не обновлялся.
[Отчёт F5, образец и свидетельства](planning/final-product-remediation-f5-2026-09-26.md).
**F6 выполнен локально:** Brain показывает ожидание, сохраняет сообщение и
черновик, различает успех/локальное действие/fallback/timeout, безопасно
повторяет сохранённый текст и отвергает поздний ответ к новой версии. Лимит
ожидания 59 с; диагностика разделяет время приложения/YC/валидации/записи.
Проверены 181 backend и 135 frontend тестов, lint/build. Три синтетических
диалога измерены без YC; реальный latency и SLA ≤15 с не заявляются.
Production не обновлялся.
[Отчёт F6 и измерения](planning/final-product-remediation-f6-2026-09-26.md).
**F7 выполнен локально:** заменён favicon на контрастный RD с SVG/PNG/ICO,
шаблоны и ADMIN каталог выведены в соответствующие группы меню. Chrome и
Edge на desktop/mobile прошли прямые ссылки, Back/reload, восстановление
выбранного проекта и отказ без роли ADMIN; favicon assets вернули HTTP 200
в production build. Frontend 135 тестов, lint/build прошли. История runs и
simulation artifacts не менялась, production не обновлялся.
[Отчёт F7 и свидетельства](planning/final-product-remediation-f7-2026-09-27.md).
**F8 начат:** подготовлены DOCX/PPTX/OpenAPI/sample package, локальные
PostgreSQL и нагрузочные проверки; [отчёт и открытые gates](planning/final-product-remediation-f8-2026-09-27.md).
[План](planning/final-product-remediation-2026-09-26.md) остаётся критерием
финальной приёмки.
[Полная матрица соответствия и доказательства](planning/final-tz-compliance-audit-2026-09-26.md).
F8 не принят: frontend/browser/production gates, demo-доступы и pinned release
ещё открыты. Исторические runs/снимки/артефакты сохраняются; серверные бекапы
не требовать, серверные команды — Windows CMD. Ниже сохранена история
предыдущих выпусков; её старые release статусы не заменяют этот абзац.

Исходный расчётный аудит baseline — 20 сентября 2026 года,
`f77c32c2fde86cd1450aa96d43dc6273059c57d4`; статус живого выпуска
уточнён 24 сентября 2026 года ниже.

**Продуктовая доработка 25 сентября:** этапы 1–3 обновлённого плана выполнены
локально. Этап 1 устранил тупики ввода единиц за рейс и подтверждения
экономических условий. Этап 2 ввёл общий словарь понятных названий и новое
представление PDF/ZIP. Этап 3 выделил «Помощник по сервису» в отдельную
справочную страницу без расчётного интервью, поиска в интернете и сравнения
роботов. Подробности: [этап 1](planning/product-ux-remediation-stage1-2026-09-25.md),
[этап 2](planning/product-ux-remediation-stage2-2026-09-25.md),
[этап 3](planning/product-ux-remediation-stage3-2026-09-25.md).
Этап 3.1 с Robovod Brain реализован локально: отдельная страница диалога,
версионированный профиль, DeepSeek V4 Flash через серверный адаптер,
подтверждение входов, C03/C11, частичная и полная экономика, PDF/ZIP и пересчёт.
Пилотная приёмка остаётся открытой из-за недоступности Yandex API из среды
проверки и невозможности повторить итоговый frontend/browser gate после последних
правок; подробности: [журнал этапа 3.1](planning/product-ux-remediation-stage3-1-2026-09-25.md).
Production-приёмка также остаётся открытой.
Этап 4 добавлен локально: паллетный маршрут показан как перевозка подготовленной
паллеты, карта складских потоков и ролей версионируется отдельно от runs,
а матрица возможностей опирается на активный каталог. Для этапа 4 пройдены
backend unit/golden проверки; PostgreSQL и итоговые frontend/browser gates
остаются открытыми. [Журнал этапа 4](planning/product-ux-remediation-stage4-2026-09-25.md).
Этап 5 добавлен локально: сравнение нескольких моделей одного расчётного профиля
на сохранённых входах C11, объяснимый технический балл C19, строгая проверка
сопоставимости денежной ветки и явные причины исключения. Исторические runs
не переписывались. Backend golden пройдены; frontend/browser и PostgreSQL gates
остаются открытыми. [Журнал этапа 5](planning/product-ux-remediation-stage5-2026-09-25.md).
Этап 6 реализован локально: модельное начало в понедельник 09:00 с местным
поясом, автоматический запуск сохранённой симуляции, общие 2D/3D вкладки,
версионированный scheduler складской цепочки и повторное открытие её отчёта.
Паллетная экономика изолирована от отбора и упаковки, старые снимки runs не
изменены. Backend и контрактные проверки пройдены; frontend build/browser и
PostgreSQL gate остаются открытыми из-за ограничений текущей среды.
[Журнал этапа 6](planning/product-ux-remediation-stage6-2026-09-26.md).
Этап 7 реализован локально: публичный пакет типового склада связывает C11,
шесть денежных сценариев и сохранённую симуляцию 2D/3D, содержит PDF/ZIP,
manifest с SHA‑256 и явные границы применимости. 20 связанных backend тестов
пройдены; frontend browser gate открыт из-за `EPERM` Node в sandbox. Исторические
runs не изменены. [Журнал этапа 7](planning/product-ux-remediation-stage7-2026-09-26.md).
Этап 8 добавлен локально: самостоятельная страница «Робоэксперт», сравнение
2–3 расчётных позиций одного класса с источниками и пропусками, отдельный
просмотр информационных моделей, рейтинг C19 для сохранённой операции,
ограниченные AI Studio и Yandex Search API. Полный backend suite прошёл;
frontend browser gate и живой пилот Yandex остаются открытыми из-за ограничений
среды. [Журнал этапа 8](planning/product-ux-remediation-stage8-2026-09-26.md).
Этап 9 добавлен локально: самостоятельная страница «Экономика» с поиском по
13 терминам, входными полями и числовыми примерами, воспроизводимыми действующими
C11/C16/C17 движками и golden fixtures. Проверки финансового ядра, frontend
build и browser gate страницы на desktop/390 px пройдены. Исторические runs
не менялись. [Журнал этапа 9](planning/product-ux-remediation-stage9-2026-09-26.md).
Этап 10 добавлен локально: самостоятельная история «Отчёты» группирует
технические, экономические и симуляционные версии по сохранённой операции,
отличает частичный и полный результат, показывает только рассчитанный NPV и
позволяет открыть, сравнить, выгрузить или создать новую версию. Проверки на
одноразовой PostgreSQL, frontend build и browser gate desktop/390 px прошли;
исторические снимки runs не менялись. Production не проверялся.
[Журнал этапа 10](planning/product-ux-remediation-stage10-2026-09-26.md).
Этап 11 принят локально: полный backend suite на одноразовой PostgreSQL
(764 passed), frontend (127), RobCraft (83), lint и build прошли. В Chrome
desktop/mobile проверены помощник, Brain, частичная/полная экономика,
«что если», «Робоэксперт», история, PDF/ZIP и повторное открытие 2D/3D.
Контраст приглушённого текста исправлен, исторические runs не менялись.
Production не опубликован и не проверен; команды Windows CMD после публикации:
[журнал этапа 11](planning/product-ux-remediation-stage11-2026-09-26.md).
Этап 12 подготовил [новое руководство пользователя](USER_GUIDE_2026-09-26.md)
и [PDF](USER_GUIDE_2026-09-26.pdf) для принятого локального интерфейса.
Оба основных маршрута, статусы, источники чисел и границы оценки пояснены;
шесть скриншотов сняты с desktop/mobile на одноразовой БД.
[Журнал этапа 12](planning/product-ux-remediation-stage12-2026-09-26.md).
Старое руководство от 25 сентября сохранено как документ своего выпуска.

**Актуальный release status (24 сентября, после первого запуска):** по
присланному выводу SSH сервер обновлён до `main`/`c89a660`, миграция
`0011_simulation_artifacts` применена, исторические run checksums совпали до и
после неё; `backend`, `frontend` и `caddy` пересозданы и стали healthy. Пользователь
сообщил, что сервис открылся, и выявил проблемы с картинками, отчётом, 2D,
страницей «Процесс», неполными входами и архивом evidence. Локальные
PostgreSQL/backend/frontend/RobCraft gates для этого коммита прошли; полный
пользовательский сценарий на HTTPS после запуска и production release acceptance
не подтверждены. Старое NPV базового PURCHASE 4 857 446 580,85 ₽ воспроизведено
в изоляции; C16 v2 на тех же входах даёт 223 701 942,55 ₽. Это ещё не принятый
бизнес-кейс: C05 `NEEDS_VALIDATION`, закупка `UNVERIFIED`. План следующих этапов:
[доработка после первого запуска](planning/post-deploy-usability-remediation-2026-09-24.md).
История и контракт предыдущего выпуска:
[live calculation remediation](planning/live-calculation-remediation-2026-09-24.md).

**Доработка и второй выпуск (25 сентября):** этапы 1 и 2 выполнены
отдельно. Этап 3 добавил схематичный 2D-склад и синхронизацию зон с RobCraft;
источником KPI остаётся C23. Проверки и ограничения:
[журнал этапа 3](planning/post-deploy-usability-stage3-2d-warehouse.md).
Этап 4 отделил страницу «Процесс» от действующего «Расчёта», убрал старый
бренд из формы и проверил переходы с сохранённым проектом, browser Back и
мобильным меню: [журнал этапа 4](planning/post-deploy-usability-stage4-process-page.md).
Этап 5 добавил помощника с поиском по активной версии каталога, сравнением,
неподтверждённым черновиком intake и отдельным веб-поиском через Yandex Search
API: [журнал этапа 5](planning/post-deploy-usability-stage5-solution-assistant.md).
Этап 6 добавил матрицу входов C03/C11/C13–C21, форму с явными неизвестными,
сохранение частичного экономического run, независимые статусы C14/покупки/RaaS,
структурированные причины пропуска сценариев и обратный путь к недостающим
данным: [журнал этапа 6](planning/post-deploy-usability-stage6-partial-inputs.md).
Старые runs не изменены; полный v1-ввод остаётся воспроизводимым. Этап 7
добавил корневую инструкцию ZIP, русский справочник всех CSV/JSON, читаемый PDF
как главный документ и manifest v2 с контрольными суммами и привязкой к
исходным снимкам: [журнал этапа 7](planning/post-deploy-usability-stage7-evidence-archive.md).
Старый формат экспорта v1 и его golden остались воспроизводимыми.
Этап 8 локально проверен на одноразовой PostgreSQL и в Chrome на desktop/390 px.
Исправлены необязательное имя при регистрации и C23-окно через полночь; полный
маршрут до сохранения, reopen/replay и PDF/ZIP прошёл локально:
[журнал этапа 8](planning/post-deploy-usability-stage8-release.md). Пользователь
подтвердил серверный HEAD `8aaa0e7`, healthy для backend/frontend/caddy и
ответ `/ready` с доступной БД. Полный пользовательский маршрут на production
ещё не принят: диагностический снимок и скачанный отчёт выявили непонятное
представление чисел, пустые финансовые ветки, отсутствие 2D у частичного
результата, два legacy режима в новом расчёте и слабый первый экран.
Следующий порядок работ: [план продуктовой готовности к хакатону](planning/hackathon-product-readiness-2026-09-25.md).
Этапы 1–6 этого плана локально выполнены отдельными коммитами:
[читаемые результаты и PDF](planning/hackathon-product-readiness-stage1.md),
[версионированное демо склада и собственные входы](planning/hackathon-product-readiness-stage2.md),
[2D/C23 для технического и частичного расчёта](planning/hackathon-product-readiness-stage3.md),
[единый расчёт v2 и зоны процесса](planning/hackathon-product-readiness-stage4.md),
[помощник и подтверждаемый черновик](planning/hackathon-product-readiness-stage5.md),
[лендинг и короткий путь к ценности](planning/hackathon-product-readiness-stage6.md).
Этап 7 локально принят на одноразовой PostgreSQL и в Chrome на 1366/390 px:
[журнал и короткий сценарий показа](planning/hackathon-product-readiness-stage7.md).
Исправлено скрытое поле «Единиц/рейс» для собственного паллетного C11.
Production-приёмка ещё открыта: SSH и HTTPS `/ready` 25 сентября завершились
timeout; живые HEAD/Compose и пользовательский маршрут нужно зафиксировать
после восстановления доступа.
Для тестировщиков подготовлено [руководство пользователя текущей версии](USER_GUIDE_CURRENT_2026-09-25.md)
и [PDF для пересылки](USER_GUIDE_CURRENT_2026-09-25.pdf). Описанные в нём
ограничения относятся к выпуску `8aaa0e7`; после продуктовых доработок
руководство нужно обновить.

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

- FastAPI backend с versioned PostgreSQL repository и раздельными
  discovery/runtime/capacity slots;
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

Текущий сервис остаётся модульным монолитом, но storage/runtime foundation уже
реализован: PostgreSQL, SQLAlchemy, Alembic, evidence/procurement/readiness и
раздельные тестовые слои входят в принятый C01–C29 scope. Историческое описание
целевой архитектуры остаётся в `05_TECHNICAL_ARCHITECTURE.md`, а порядок её
ввода — в `17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md`.

Встроенные legacy-модели удалены. Production discovery, capacity и economics
читают только явно активированные PostgreSQL slots/routes; отсутствие нужной
активации даёт fail-closed 503. `organizer-catalog-v4` materialized и принят для
нового C11 → C13–C21 пути, но не содержит безопасной legacy `runtime`
projection, поэтому этот slot намеренно не активируется. Синтетические записи и
golden fixtures production-код не импортирует.

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

Этап **`engine/capacity-formula-trace`** (C07) завершён: реализованы pure
F01–F04/F07 для transport/delivery, exact Decimal/FLOOR/CEIL, K02–K04,
actual selected-fleet coverage и byte-stable `CalculationTrace`. C06 safe-fact
closure и C05 eligibility обязательны; legacy Robot/economics не читаются.
Отчёт: [transport capacity formula trace v1](planning/transport-capacity-formula-trace-v1.md).

Этап **`engine/cleaning-capacity-trace`** (C08) завершён: реализованы pure
F05/F07 для cleaning area, direct/share-of-total area sources, typed
`m2`, `1/day`, `m2/h`, `m2/day`, exact fleet ceil и общий C07 trace runtime.
Проверены все шесть cleaning-ready позиций C06 и airport golden
`85000 × 0.6 = 51000 m2`. Отчёт:
[cleaning capacity trace v1](planning/cleaning-capacity-trace-v1.md).

Этап **`engine/palletizing-capacity-trace`** (C09) завершён: реализованы pure
F06/F07 для fixed palletizing cell с dimension-safe цепочкой
`pick/min → pick/h → box/day → pallet/day`, отдельными efficiency и
availability, output policy 20 box/pallet и synthetic assumption provenance.
Catalog pool не расширен. Отчёт:
[palletizing capacity trace v1](planning/palletizing-capacity-trace-v1.md).

Этап **`contracts/process-profile-coverage-v1`** (C10) завершён: versioned
каталог покрывает ровно 28 K19-процессов и маршрутизирует применимые scopes в
C07–C09; REFERENCE_ONLY и CONSTRAINT_ONLY имеют явные причины/requirements,
а generic USER_CYCLE доступен только как USER/FILE opt-in. Membership 21/24,
production API, frontend и registry v1 не менялись. Отчёт:
[process profile coverage v1](planning/process-profile-coverage-v1.md).

Этап **`api/capacity-analysis-snapshots-v2`** (C11) завершён: добавлен
CSRF/tenant-protected `POST /api/v2/capacity-analyses`, reopen endpoint,
server-owned C05/C06/C10 routing и immutable capacity run с отдельными
input/result/trace/version hashes. Capacity run не требует economics или
ScenarioSpec v1; прежний full run и `/api/calculate` сохранены. Отчёт:
[capacity analysis snapshots v2](planning/capacity-analysis-snapshots-v2.md).

Этап **`frontend/capacity-results-trace`** (C12) завершён: отдельная панель
читает только C11 snapshot, показывает status, units, selected/recommended
fleet, nominal/effective capacity, coverage/overload, blockers и server-owned
trace с источниками. Устаревшие revision отбрасываются, отсутствующая экономика
показана явно, а старые `/api/calculate` runs сохраняют прежнее представление.
Отчёт: [frontend capacity results trace](planning/frontend-capacity-results-trace.md).

Этап **`procurement/commercial-inputs-v1`** (C13) завершён: добавлены strict
`CommercialMoney`, PURCHASE/RAAS terms, K25 cost-basis union, service
responsibilities и evidence-gated procurement resolver/API. Organizer raw price
сохраняется; gross не делится автоматически, `NET_RUB` требует explicit VAT
rate, USER budget не выдаётся за vendor quote, а procurement status не получает
численного score. Отчёт:
[commercial inputs and procurement report v1](planning/commercial-inputs-v1.md).

Этап **`engine/role-labor-baseline-v1`** (C14) завершён: добавлены strict
request/result contracts, pure F08–F15 role baseline, rotation/deficit/surplus,
детерминированный shared-role allocation, единый object pult/tech ledger,
forklift conservation и независимый от salary capacity projection. Missing
salary даёт локальный `INCOMPLETE`, zero требует `ZERO_COST_ROLE`, no-role —
`NO_FOT_BENEFIT`. V2-A закрыт versioned overlay без изменения registry v1 и
K19 mappings. Отчёт: [role labour baseline v1](planning/role-labor-baseline-v1.md).

Этап **`economics/purchase-cost-ledger-v1`** (C15) завершён: добавлены strict
purchase request/ledger contracts, pure F16–F22 capital/operating lines,
раздельные gross/amortizable/cashflow CAPEX bases, warranty/service/energy,
cumulative battery replacements и residual. Missing commercial/technical
inputs дают локальный `INCOMPLETE`, included/excluded cost не считается дважды,
а capacity/labour snapshots остаются immutable. Отчёт:
[purchase cost ledger v1](planning/purchase-cost-ledger-v1.md).

Этап **`economics/full-cashflows-reconciliation-v1`** (C16) завершён: добавлены
strict full base/scenario ledgers F23–F31, primary pretax cashflow, отдельный
illustrative tax supplement, NPV/payback/ROI/TCO и R13-01..49 reconciliation.
C14/C15/capacity snapshots связаны immutable digests; missing finance остаётся
`INCOMPLETE`. V2-C закрыт versioned overlay. Отчёт:
[full cashflows and reconciliation v1](planning/full-cashflows-reconciliation-v1.md).

Этап **`economics/raas-cashflows-v1`** (C17) завершён: добавлены strict F32
RaaS contracts, responsibility-aware zeroing, customer infrastructure CAPEX,
phased/all-fleet payment, full pretax/tax cashflows и RaaS NPV/payback/TCO/ROI.
Unknown responsibility/terms остаются `INCOMPLETE`; C13–C16 snapshots immutable.
Отчёт: [RaaS cashflows v1](planning/raas-cashflows-v1.md).

Этап **`economics/multiprocess-allocation-v1`** (C18) завершён: добавлены
strict SelectedConfiguration/cohort contracts, exact-cent K17 allocation
shared site CAPEX, object-level C14 role/FOT conservation, combined annual
cashflows и project NPV/payback с deterministic trace/replay. Shared roles,
control-post и technical staff учитываются один раз; process projections явно
исключают object-shared статьи. Отчёт:
[multiprocess allocation v1](planning/multiprocess-allocation-v1.md).

Этап **`engine/ranking-v2`** (C19) завершён: eligibility C05/C06 применяется до
score, C18 NPV нормализуется только внутри frozen process cohort, а technical и
financial recommendations разделены. Добавлены explicit K14 curves, R08/K16
data completeness, deterministic ties, full formula/provenance trace и replay
bindings. Hard fail не получает score; incomplete finance не получает full
score; all-negative cohort не выдаёт положительную финансовую рекомендацию.
V2-D закрепил exact versioned C05 rule IDs (29 в текущей rules v2), а
integrations — как advisory applicability component. Отчёт:
[ranking v2](planning/ranking-v2.md).

Этап **`economics/sensitivity-v1`** (C20) завершён: strict immutable bundle
связывает C18 baseline, C19 selection и шесть USER-provenance tornado overrides
price/volume/salary ровно ±10%. Каждый исполняемый вариант повторно вызывает
canonical C18 engine без дублирования финансовой арифметики; blocked variant не
получает синтетический result. Capacity snapshots для price/salary неизменны,
volume может создать traceable fleet/headcount step. Отчёт:
[economics sensitivity v1](planning/sensitivity-v1.md).

Этап **`frontend/commercial-scenarios-v2`** (C21) завершён: добавлен strict
presentation bundle и отдельный UI для PURCHASE/RaaS × трёх uncertainty
profiles, commercial inputs, role monthly gross, procurement/finance statuses,
cashflow/source drilldown и C20 sensitivity. Browser не рассчитывает деньги,
VAT, ranking или deltas; любое изменение input инвалидирует старый result.
Capacity и legacy saved-run viewers сохранены. Отчёт:
[frontend commercial scenarios v2](planning/frontend-commercial-scenarios-v2.md).

Этап **`contracts/scenario-spec-v2`** (C22) завершён: добавлен strict
ScenarioSpec v2 поверх immutable C11 capacity snapshot с typed demand,
operating windows, batch/exchange semantics, fleet/route bindings, полными
calculation version bindings и явным nullable C18 finance binding. Revision
покрывает всё семантическое тело и меняется при изменении version bindings;
capacity-only cleaning fixture не требует payload или экономики. ScenarioSpec
v1, старые runs, catalog membership и production runtime не менялись. Отчёт:
[ScenarioSpec v2](planning/scenario-spec-v2.md).

Этап **`simulation/scheduling-kpi-report-v1`** (C23) завершён: добавлены strict
SimulationRequest/Report v1 и отдельный deterministic microsecond scheduler с
явными calendar/warmup/measurement/grace, queue/wait/utilization/SLA,
capacity-deviation denominator, replay digests, progress/cancel/timeout и
diagnostic limits. Failure rates не выдумываются, availability не применяется
дважды, а отчёт явно не является инженерной сертификацией. C22 и старые runs
неизменны. Отчёт: [simulation scheduling KPI report v1](planning/simulation-scheduling-kpi-report-v1.md).

Этап **`visualization/2d-simulation-report`** (C24) завершён: добавлены
authenticated/CSRF lifecycle API run/progress/cancel поверх неизменного C23
service, strict polling state и обязательный offline SVG consumer ScenarioSpec
v2 + SimulationReport v1. Детерминированный timeline, controls, KPI/SLA/
limitations, >10% warning и visual events связаны с scenario/report revision,
digest, seed и simulation time. Synthetic/provided geometry маркируется явно и
не меняет analytical route; fake failure/charging/SLA и browser business math
не добавлены. Отчёт:
[visualization 2D SimulationReport](planning/visualization-2d-simulation-report.md).

Этап **`robcraft/scenario-v2-reconciliation`** (C25) завершён: RobCraft
принимает ScenarioSpec v1/v2 без downgrade, использует v2 operating windows,
сохраняет analytical route/finance snapshot и возвращает отдельный visual-only
renderer report, связанный с revision и C23 digest. Backend сравнивает его с
C23 только на одинаковой measurement basis и предупреждает строго при >10%;
moving utilization, arbitrary energy, visual faults/charging и SLA
`NOT_EVALUATED` не выдаются за расчётные KPI. Same-origin/source, two-phase и
stale message protections сохранены. Отчёт:
[RobCraft ScenarioSpec v2 reconciliation](planning/robcraft-scenario-v2-reconciliation.md).

Этап **`report/calculation-evidence-exports`** (C26) завершён: успешный
immutable AnalysisRun экспортируется owner-scoped API в deterministic ZIP со
strict manifest, offline searchable PDF, девятью CSV-разделами и полным
`Snapshot.json`. Persisted checksums проверяются до выдачи, archive связан с
manifest digest, missing finance/simulation остаются видимыми как
`NOT_AVAILABLE`, а spreadsheet formulas нейтрализуются без изменения decimal
amounts. Frontend не пересчитывает отчёт и показывает run/revision/digest и
availability разделов. Отчёт:
[calculation evidence exports](planning/calculation-evidence-exports.md).

Этап **`catalog/capacity-runtime-dual-run-rollout`** (C27) завершён: C11 route
читает только отдельный fail-closed capacity slot, утверждённый strict policy и
dual-run report. Policy фиксирует опубликованный content digest, 187/223,
capacity pool 21/24, split 6/15 моделей и отсутствие BAS; unmatched difference
блокирует activation. Policy/report digest и rollback mode/target сохраняются
аддитивной migration 0009. В frontend добавлена только версия capacity source,
без новой арифметики. Текущая и production DB не мигрировались и capacity slot
не активировался. Отчёт:
[capacity runtime dual-run rollout](planning/catalog-capacity-runtime-dual-run-rollout.md).

Этап **`catalog/economics-runtime-migration`** (C28) завершён. Strict policy
фиксирует v2 для новых активированных routes, fail-closed отсутствие active
route, explicit rerun в новый run и snapshot-only historical/legacy replay.
Аддитивная migration 0010 создаёт immutable version mapping и append-only
route activation history; backfill не меняет `analysis_runs` и маркирует
старый `fte_cost_rub` как unknown basis без преобразования в gross. Approved
dual-run golden объясняет различия G06/G07/G12/G21–G32/G34/G36/G39/G47/G48/G52;
для несопоставимых basis числовой delta намеренно отсутствует. Frontend
выбирает legacy/v2 viewer по mapping и показывает migration notice, exports
остаются snapshot-driven. Legacy implementation сохранена. Production DB и
runtime не активировались. Отчёт:
[economics runtime migration](planning/catalog-economics-runtime-migration.md).

Этап **`qa/calculation-migration-acceptance`** (C29) завершён. Pinned release
manifest связывает R00–R13, три object fixtures, exact 28 K19 scopes и ключевые
goldens по SHA-256. Пять повторов warehouse golden path, offline runtime и 50
параллельных economics executions прошли policy limits. Полные backend,
PostgreSQL, frontend, schema/security и backup/restore gates зелёные. Найденные
дефекты capacity policy scope, immutable v2 version binding и cross-version
media verification исправлены без rewrite старых runs, изменения registry v1,
catalog membership или production activation. Отчёт:
[calculation migration acceptance](planning/qa-calculation-migration-acceptance.md).

По завершении исходного C29 следующей итерацией был объявлен
**`ops/production-domain-deployment-v1`** (C30); в рамках самого C29 он не
начинался. Его текущее состояние описано ниже.

C30 начат 2026-09-23 по явной команде владельца; production traffic switch
остаётся на HOLD до переноса проверенного commit в `main` и серверных gates.
Production economics executor теперь подключён в `main.app`: новый путь
создаёт C11 snapshot, принимает явные commercial inputs, исполняет C13–C21 и
сохраняет immutable economics run с reopen/export/exact replay. Fresh organizer
catalog всё ещё не содержит legacy runtime robots и не активируется в
`runtime`; новые поддержанные расчёты используют capacity/economics slots.
Подготовлены internal-only production Compose, pinned Caddy automatic TLS,
secure-cookie/origin settings, root-contract-aware backend image, liveness
endpoint и backup/restore/smoke scripts. Точный runbook:
[production deployment](PRODUCTION_DEPLOYMENT.md).

Аудит локальных материалов организаторов 2026-09-24 уточнил границу C30:
Excel содержит прямо обозначенные demo-значения для типового склада, а
документ с решениями — примеры моделей. Официальные публичные ТТХ MULE/Ronavi
дополняют материалы, но не заменяют паспорт выбранной комплектации, vendor
availability и фактические параметры объекта. Эти данные можно использовать
для предварительного расчёта с раскрытыми допущениями, не для скрытого
`ELIGIBLE`/deployment-ready. Технический разрыв production UI → C11 →
economics v2 закрыт, но это не повышает доказательную готовность C05.
Подробности: [integration gap](planning/production-calculation-integration-gap.md).

По явному разрешению владельца реализован предварительный demo-route:
три авторских [профиля моделей](planning/demo-model-profiles-v1.md) отделяют
публичные ТТХ от допущений; v2-ввод по умолчанию открывает сохранённый C11
capacity run после подтверждения условий. После него сервер требует явные
monthly gross и закупочные/RaaS условия, выполняет C13–C21 и показывает все
неподтверждённые ограничения. Строгий C05 и исторические runs сохранены.
Повторная приёмка: 625 backend/PostgreSQL tests, 73 frontend tests, schema,
lint/build и actual-catalog end-to-end зелёные. Economics approval привязан к
golden projection production orchestrator, не к runtime fixture. C30 traffic
не переключался; legacy route остаётся только для явно маркированной
совместимости и snapshot-only historical viewer/replay.

Все C01–C30 и их acceptance gates обязательны к последовательной реализации.
Ограничение сложности относится только к новой логике сверх принятого плана:
его tax, replacement, allocation, sensitivity, simulation, export и rollout
этапы не упрощаются и не переводятся в optional.

После расчётной приёмки C29 добавлен отдельный C30
**`ops/production-domain-deployment-v1`**: публикация принятого release на
Selectel VDS для `robodovod.ru`/`www.robodovod.ru`, production Compose,
TLS/reverse proxy, secrets, migrations, backup/restore, observability и
rollback. Сервер предварительно подготовлен, но application production
activation до C30 не выполняется. Локальные operational details хранятся в
неотслеживаемом `DEPLOY.md` и не являются частью repository artifacts.

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
