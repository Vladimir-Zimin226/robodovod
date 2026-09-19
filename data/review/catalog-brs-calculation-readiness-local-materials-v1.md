# БРС: проверка локальных материалов и готовности к расчётам

Дата среза: 2026-09-19. Проверка выполнена только по локальным материалам
кейсодателя, импортированным base/overlay/evidence и принятому official-source
staging. БАС исключены.

## Ответ

В accepted staging есть факты для 26 identities, но `SmartCube` не имеет
поддержанного capacity profile. В текущем фокусе остаются 25 моделей БРС:
15 `MOBILE_TRANSPORT` и 10 `CLEANING`.

У них остаётся 156 незаполненных contract fields и два conflict records. Это не
означает, что все 156 полей нужны непосредственно арифметике расчёта:

- 40 — capacity inputs: 15 `units_per_trip`, 15 `exchange_time_s`, 6
  `cleaning_width_m`, 4 `cleaning_rate_m2_h`;
- 37 — технические ограничения/идентификаторы: payload, speed, aisle,
  autonomy, dimensions;
- 79 — deployment/engineering readiness: surface, service, connectivity,
  operating conditions, integrations, charging и navigation.

Текущий backend уже трактует `units_per_trip` как scenario input с приоритетом
над catalog profile, а при отсутствии catalog `exchange_time_s` использует
явную глобальную расчётную константу. Поэтому отсутствие этих 30 значений у
вендора не должно само по себе запрещать предварительный расчёт, если в
результате видны источник и допущение.

## Что действительно было у кейсодателя

Оригиналы найдены локально, их hashes совпадают с зарегистрированными:

- `catalog_export_v4.csv` — 223 позиции / 187 identities;
- `Примеры_решений_типы_объектов.docx` — примеры ТТХ восьми решений;
- 91-страничный каталог внедрений и две его полные текстовые версии;
- XLSX профилей склада, аэропорта и медучреждения;
- основное ТЗ и дополнения.

Материалы кейсодателя уже дают 20 contract-required model facts для девяти из
26 identities. Это payload из названий/CSV, а также часть autonomy,
dimensions, speed, navigation, operating conditions и aisle data из DOCX.

Найден один безопасный недоразбор: у Ronavi H1500 исходный DOCX дословно
содержит `ровный промышленный пол` внутри `operating_conditions`. Этот фрагмент
можно тем же evidence отдельно адаптировать в `specs.surface_requirements`.

Остальные числовые фразы в карточках не закрывают missing model fields:

- 8 тысяч отгрузок за смену относятся к комплексу из 48 Ronavi H1500;
- 2 тыс. м² для Клинботикс 400 PRO не содержат времени уборки;
- сокращение уборки с 1,5 часа до 35 минут для двух Клинботикс 600 не содержит
  площади;
- для DMR 1200 сказано, что автономность подтверждена испытаниями, но числовое
  значение не опубликовано;
- сведения о количестве внедрённых роботов, процентах улучшения и сроке
  окупаемости являются case metrics, а не паспортной capacity одной модели.

## Уже пригодны для арифметики предварительного расчёта

Если отделить formula inputs от полного deployment gate и явно разрешить
scenario assumptions для cycle operations, минимальное расчётное ядро уже есть
у 19 моделей.

### Transport — 13

- Робот для транспортировки деталей и инструментов
- Беспилотный тягач (Когнитив Пилот)
- Робот-штабелёр RoboCV
- Ronavi SR
- Ronavi H1500
- Ronavi SD
- Ronavi H2000
- AMR 1500
- Робот-тягач RoboCV
- DMR 600
- DMR 1200
- Ronavi M
- MULE

Для них подтверждены как минимум model payload и speed. `units_per_trip` и
`exchange_time_s` должны приходить из сценария/операционного допущения с явной
provenance, а не выдаваться за паспортную характеристику.

### Cleaning — 6

- MARK 2 SE
- Клинботикс 600
- АК-SC80
- РУБИ-С-03
- БРО 3.0
- Клинботикс 400 PRO

Для них есть model-specific `cleaning_rate_m2_h`, непосредственно используемый
текущей формулой. Ширина уборки остаётся обязательной для трассировки покрытия,
но текущая арифметика fleet sizing её пока не использует.

## Формульно заблокированы — 6

- Беспилотный погрузчик — нет payload и speed;
- L5 — нет payload и speed;
- Astramis SurfexUnit — нет cleaning rate;
- Пиксель — нет cleaning rate;
- БРО 2.1 — нет cleaning rate;
- Веном Саранча — нет cleaning rate.

## Реализованный практический шаг

Не следует пытаться любой ценой заполнить все 156 полей. Реализован contract v2
с двумя независимыми gates:

1. `CALCULATION_READY` — факты, непосредственно входящие в формулу, плюс явно
   версионированные scenario assumptions;
2. `DEPLOYMENT_REVIEW_REQUIRED` — aisle, surface, charging, integrations,
   connectivity, service и прочие параметры обследования/внедрения.

Контракт даёт расчётный пул 19 реальных БРС внутри accepted research cohort и
21 модель / 24 позиции по всему каталогу. Ни одна модель не получила
`DEPLOYMENT_READY`; assumptions не стали vendor facts.
