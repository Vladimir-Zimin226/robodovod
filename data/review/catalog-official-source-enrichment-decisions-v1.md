# Очередь ручных решений по обогащению каталога

> Review-only: решения в этом файле сами по себе не изменяют catalog, runtime или backend/fleet.

## Как работать

Разбираем по одному пункту в порядке ID. Для каждого пункта допустимы решения: `ACCEPT`, `REJECT` или `DEFER/VERIFY`. При `ACCEPT` фиксируется конкретное значение и evidence; конфликт целиком без выбора применимой ревизии принимать нельзя.

- Конфликты/identity всего: 22.
- Уже зафиксировано ручных решений: 22.
- Требуют проверки конфликта/identity: 0.
- Кандидаты на принятие всего: 116.
- Уже рассмотрено обычных кандидатов: 116.
- Ожидают решения: 0.
- Остаются без фактов: 318.

## Сначала: конфликты и identity

### R001 — Пиксель — `specs.operating_conditions`

- Batch: `deep-cleaning-01`; organizer ID: `2f46660e-ea20-4845-9620-8c743b03225b`.
- Catalog positions: `catalog-v4-row-0107`.
- Производитель: ООО "Автономика"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Пиксель.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Текущая model page и паспорт 01.V1 дают разные нижние температурные пределы.
- Evidence:
  - «температура окружающей среды: от –10 ˚С до +40 ˚С» — [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf), ООО «Автономика», PDF page 5/9, §3.2 «Нормальные условия эксплуатации».
  - «от −30°C до +40 °C» — [Пиксель](https://www.avtonomika.ru/products/pixel/), ООО «Автономика», Раздел «Превосходная производительность и универсальность».
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_PASSPORT_CONSERVATIVE** — {"max": 40, "min": -10} °C. По решению пользователя принято более безопасное значение из паспорта точной ревизии 01.V1; более широкий диапазон текущей страницы сохранён как альтернативное evidence.

### R002 — Клинботикс 600 — `capacity.cleaning_rate_m2_h`

- Batch: `deep-cleaning-01`; organizer ID: `5a5b3599-bd64-4330-9bbb-4f8ce7d780b9`.
- Catalog positions: `catalog-v4-row-0025`.
- Производитель: ООО "Вейбот Автомакон Роботикс"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Клинботикс 600.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Две официальные страницы производителя публикуют разные диапазоны.
- Evidence:
  - «скорость уборки 1000-1500 м²/ час» — [Cleanbotics — робот поломойщик для профессиональной уборки](https://waybotrobotics.com/), Waybot Robotics / ООО «Вейбот Автомакон Роботикс», Раздел «Модели», карточка «Клинботикс 600».
  - «Скорость уборки составляет 1000-2300 м²/ час!» — [Модель Cleanbotics 600](https://waybotrobotics.com/models/600), Waybot Robotics / ООО «Вейбот Автомакон Роботикс», Вводный раздел «Инструмент для безупречного клининга».
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — {"max": 1500, "min": 1000} m²/h. По решению пользователя принят меньший официальный диапазон, чтобы не завышать будущую расчётную производительность; более широкий диапазон сохранён как альтернативное evidence.

### R003 — Клинботикс 600 — `specs.autonomy`

- Batch: `deep-cleaning-01`; organizer ID: `5a5b3599-bd64-4330-9bbb-4f8ce7d780b9`.
- Catalog positions: `catalog-v4-row-0025`.
- Производитель: ООО "Вейбот Автомакон Роботикс"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Клинботикс 600.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Одна официальная model page содержит несовместимые значения 5 h, 4 h и 3 h.
- Evidence:
  - «5 часов работы в режиме мойки» — [Модель Cleanbotics 600](https://waybotrobotics.com/models/600), Waybot Robotics / ООО «Вейбот Автомакон Роботикс», Раздел «Ключевые особенности».
  - «3 часа» — [Модель Cleanbotics 600](https://waybotrobotics.com/models/600), Waybot Robotics / ООО «Вейбот Автомакон Роботикс», Раздел «Технические характеристики», «Время работы без подзарядки».
  - «Время работы на одном заряде (режим влажной уборки) — 4 часа» — [Модель Cleanbotics 600](https://waybotrobotics.com/models/600), Waybot Robotics / ООО «Вейбот Автомакон Роботикс», Таблица «Сравнение с конкурентами», колонка Cleanbotics 600.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — 3 h. По разрешённой пользователем консервативной политике принято минимальное явно опубликованное время работы; заявления 4 и 5 часов сохранены как альтернативные evidence.

### R004 — Клинботикс 600 — `specs.dimensions`

- Batch: `deep-cleaning-01`; organizer ID: `5a5b3599-bd64-4330-9bbb-4f8ce7d780b9`.
- Catalog positions: `catalog-v4-row-0025`.
- Производитель: ООО "Вейбот Автомакон Роботикс"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Клинботикс 600.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Официальная model page и официальный каталог публикуют разные габариты.
- Evidence:
  - «размер 700 x 600 х 1000 мм» — [Cleanbotics — робот поломойщик для профессиональной уборки](https://waybotrobotics.com/), Waybot Robotics / ООО «Вейбот Автомакон Роботикс», Раздел «Модели», карточка «Клинботикс 600».
  - «750 x 700 x 1000 мм» — [Модель Cleanbotics 600](https://waybotrobotics.com/models/600), Waybot Robotics / ООО «Вейбот Автомакон Роботикс», Таблица «Сравнение с конкурентами», строка «Габариты», колонка Cleanbotics 600.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE_PLANNING_ENVELOPE** — [750, 700, 1000] mm. Для проверки пространства принят больший из двух целиком опубликованных габаритных контуров; меньший контур сохранён как альтернативное evidence.

### R005 — Веном Саранча — `specs.operating_conditions`

- Batch: `deep-cleaning-02`; organizer ID: `d4b39362-518a-4cf2-8770-b69bc03585a0`.
- Catalog positions: `catalog-v4-row-0108`.
- Производитель: ООО "Робком"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Веном Саранча.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Две официальные страницы точной модели публикуют несовместимые верхние границы температуры: 32 °C и 42 °C.
- Evidence:
  - «Температура эксплуатации: от -30 до 42 С» — [Робот косилка Venom САРАНЧА - купить с доставкой по России](https://rob-com.ru/robot-kosilka-venom-sarancha), РОБКОМ, ТЕХ. ХАРАКТЕРИСТИКИ → Веном Саранча.
  - «Температура эксплуатации: до 32 С» — [Веном Саранча](https://rob-com.ru/tproduct/480874550-266559644532-venom-sarancha), РОБКОМ, Тех. характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE_PARTIAL** — {"max": 32} °C. По разрешённой пользователем консервативной политике принята только явно опубликованная верхняя граница +32 °C. Нижняя граница не перенесена из конфликтующего источника и остаётся неизвестной; полный диапазон −30…+42 °C сохранён как альтернативное evidence.

### R006 — Клинботикс 400 PRO — `capacity.cleaning_rate_m2_h`

- Batch: `deep-cleaning-02`; organizer ID: `f31223c1-44c8-4410-8381-6356e2158b61`.
- Catalog positions: `catalog-v4-row-0024`.
- Производитель: ООО "Вейбот Автомакон Роботикс"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Cleanbotics 400 PRO.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Русская и английская официальные версии страницы точной модели расходятся по верхней границе: 1200 и 1500 м²/ч.
- Evidence:
  - «Cleaning speed 700–1500 m²/hour» — [Cleanbotics 400 PRO](https://waybotrobotics.com/en/models/400pro), ООО «ВЕЙБОТ АВТОМАКОН РОБОТИКС», Competitive Comparison → Cleanbotics 400 PRO.
  - «Скорость уборки 700-1200 м²/час» — [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro), ООО «ВЕЙБОТ АВТОМАКОН РОБОТИКС», Сравнение с конкурентами → Cleanbotics 400 PRO.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — {"max": 1200, "min": 700} m²/h. Принят меньший официальный диапазон русской страницы, чтобы не завышать расчётную производительность.

### R007 — Клинботикс 400 PRO — `specs.dimensions`

- Batch: `deep-cleaning-02`; organizer ID: `f31223c1-44c8-4410-8381-6356e2158b61`.
- Catalog positions: `catalog-v4-row-0024`.
- Производитель: ООО "Вейбот Автомакон Роботикс"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Cleanbotics 400 PRO.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Две официальные страницы точной модели публикуют разные габариты; даты ревизий не указаны.
- Evidence:
  - «размер 561 x 744 х 611,5 мм» — [Cleanbotics — робот поломойщик для профессиональной уборки](https://waybotrobotics.com/), ООО «ВЕЙБОТ АВТОМАКОН РОБОТИКС», Модели → Клинботикс 400 ПРО.
  - «Габариты 676 x 560 x 744 мм» — [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro), ООО «ВЕЙБОТ АВТОМАКОН РОБОТИКС», Ключевые особенности → Компактность и маневренность.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **DEFER** — —. По решению пользователя выбор отложен: ни один опубликованный габарит не больше другого по всем осям, порядок осей первой записи не определён, а составной максимальный контур был бы недопустимым вычисленным фактом.

### R008 — Клинботикс 400 PRO — `specs.min_aisle_width`

- Batch: `deep-cleaning-02`; organizer ID: `f31223c1-44c8-4410-8381-6356e2158b61`.
- Catalog positions: `catalog-v4-row-0024`.
- Производитель: ООО "Вейбот Автомакон Роботикс"; класс: `CLEANING`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Cleanbotics 400 PRO.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: На одной официальной странице точной модели 40 см для влажного режима несовместимы с общим минимумом 700 мм.
- Evidence:
  - «Ширина проходов 75 см в режиме пылесоса и 40 см в режиме влажной уборки» — [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro), ООО «ВЕЙБОТ АВТОМАКОН РОБОТИКС», Области применения и условия эксплуатации.
  - «Минимальная ширина прохода — 700 мм» — [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro), ООО «ВЕЙБОТ АВТОМАКОН РОБОТИКС», Сравнение с конкурентами → Cleanbotics 400 PRO.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — 750 mm. Для общего требования к проходу принято наибольшее явно опубликованное значение 750 мм; меньшие значения сохранены с контекстом режима.

### R009 — Ronavi M (грузоподъемность до 1200 кг) — `specs.min_aisle_width`

- Batch: `deep-mobile-02`; organizer ID: `dcfd9975-81eb-49b5-a422-827a720ba582`.
- Catalog positions: `catalog-v4-row-0006`.
- Производитель: ООО "Ронави Роботикс"; класс: `MOBILE_TRANSPORT`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Ronavi M.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: На одной официальной странице опубликованы 760 мм в таблице ТТХ и 800 мм в требованиях подготовки склада; применимое единственное значение не выбрано.
- Evidence:
  - «минимальную ширину проезда 800 мм» — [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m), Ронави Роботикс, FAQ «Какая подготовка склада требуется для внедрения?».
  - «Минимальная ширина проезда \| 760 мм» — [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m), Ронави Роботикс, Раздел «Технические характеристики Ronavi M».
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — 800 mm. Для подготовки склада принято большее требование 800 мм; табличный минимум 760 мм сохранён как альтернативное evidence.

### R010 — SmartCube — `specs.max_speed`

- Batch: `hybrid-conflicts-01`; organizer ID: `0ece582a-084c-4a8b-99f4-576f0e01b7c8`.
- Catalog positions: `catalog-v4-row-0018`.
- Производитель: ООО "АРС"; класс: `None`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: CR-02 / SmartCube.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `[2.1, 2.7] m/s` — source указан в batch
- Пояснение: Обе стороны сохранены; применимая revision/configuration документально не доказана.
- Evidence:
  - «Максимальная скорость движения составляет 2,1 м/с» — [CR-02 — Новое поколение мобильного робота для кубической системы хранения](https://arobosys.ru/robot), ООО «АРС Смарт Роботикс», Страница «CR-02».
  - «Линейная скорость 2,7 м/с» — [CR-02 — Новое поколение мобильного робота для кубической системы хранения](https://arobosys.ru/robot), ООО «АРС Смарт Роботикс», Технические характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — 2.1 m/s. Принята меньшая официально заявленная максимальная скорость, чтобы не завышать будущую пропускную способность.

### R011 — Робот-штабелёр RoboCV — `specs.aisle_requirements`

- Batch: `hybrid-conflicts-01`; organizer ID: `2ffc706d-fe43-4c2b-baad-a624a95ad3ce`.
- Catalog positions: `catalog-v4-row-0016`.
- Производитель: ООО "Робосиви"; класс: `MOBILE_TRANSPORT`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Робот-штабелёр RoboCV.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `{"full_speed_aisle_mm": [1900, 1800], "turning_aisle_mm": 2900} mm` — source указан в batch
- Пояснение: Обе стороны сохранены; применимая revision/configuration документально не доказана.
- Evidence:
  - «Для объезда препятствий необходим проезд шириной не менее 1,6 м» — [Робот-штабелёр](https://robocv.ru/robot-shtabelyor), ООО «РобоСиВи», Объезд препятствий.
  - «Мин. ширина проезда для набора полной скорости 1800мм» — [Спецификация робота-штабелёра RoboCV](https://robocv.ru/wp-content/uploads/2021/05/robot-shtabelyor-robocv-specifikaciya.pdf), ООО «РобоСиВи», Мин. ширина проезда для набора полной скорости.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONDITIONAL_CONSERVATIVE** — {"full_speed_min_mm": 1900, "obstacle_bypass_min_mm": 1600, "turning_min_mm": 2900} mm. По решению пользователя разные условия сохранены отдельно. Для полной скорости принято более осторожное официальное требование 1900 мм; 1800 мм из PDF сохранено как альтернатива. Требования 1600 мм для объезда и 2900 мм для разворота не смешиваются с full-speed aisle.

### R012 — Робот-штабелёр RoboCV — `specs.max_speed`

- Batch: `hybrid-conflicts-01`; organizer ID: `2ffc706d-fe43-4c2b-baad-a624a95ad3ce`.
- Catalog positions: `catalog-v4-row-0016`.
- Производитель: ООО "Робосиви"; класс: `MOBILE_TRANSPORT`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Робот-штабелёр RoboCV.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `[2.0, 1.67] m/s` — source указан в batch
- Пояснение: Обе стороны сохранены; применимая revision/configuration документально не доказана.
- Evidence:
  - «Максимальная скорость, м/с: 2» — [Робот-штабелёр](https://robocv.ru/robot-shtabelyor), ООО «РобоСиВи», Технические характеристики.
  - «Скорость 1,67 м/с» — [Спецификация робота-штабелёра RoboCV](https://robocv.ru/wp-content/uploads/2021/05/robot-shtabelyor-robocv-specifikaciya.pdf), ООО «РобоСиВи», Макс. скорость.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — 1.67 m/s. Принята меньшая скорость из официальной спецификации, чтобы не завышать будущую пропускную способность.

### R013 — Ronavi H1500 (грузоподъемность до 1 500 кг) — `specs.min_aisle_width`

- Batch: `hybrid-conflicts-01`; organizer ID: `5760e938-9a43-45a7-b8e8-f4f2e6383930`.
- Catalog positions: `catalog-v4-row-0002`, `catalog-v4-row-0067`.
- Производитель: ООО "Ронави Роботикс"; класс: `MOBILE_TRANSPORT`.
- Identity: `AMBIGUOUS_MODEL_MATCH`; найдено: —.
- Требуется: `IDENTITY_REVIEW`; evidence status: `AMBIGUOUS_MODEL_MATCH`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NO_KNOWN_FACT`.
- Пояснение: Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.
- Evidence:
  - «Минимальная ширина проезда;750 мм» — [Ronavi H1500](https://ronavi-robotics.ru/catalogue/h1500), ООО «Ронави Роботикс», Технические характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CURRENT_OFFICIAL_REVISION_ONLY** — 750 mm. По решению пользователя 750 мм принято только для текущей официальной ревизии точной модели Ronavi H1500. Это не разрешает отдельный конфликт автономности 6/10 часов и не доказывает ревизию organizer positions.

### R014 — AMR 100 (грузоподъемность до 100 кг) — `specs.autonomy`

- Batch: `hybrid-conflicts-01`; organizer ID: `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff`.
- Catalog positions: `catalog-v4-row-0008`.
- Производитель: ООО "Морос"; класс: `MOBILE_TRANSPORT`.
- Identity: `AMBIGUOUS_MODEL_MATCH`; найдено: —.
- Требуется: `IDENTITY_REVIEW`; evidence status: `AMBIGUOUS_MODEL_MATCH`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `{"average_load": 20, "maximum_load": 10} h` — source указан в batch
- Пояснение: Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.
- Evidence:
  - «Время работы — 20 часов (при средних нагрузках)» — [AMR100 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-100/), ООО «Морос», Технические характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **DEFER_IDENTITY** — —. Текущая официальная страница относится к AMR100 до 150 кг, а organizer position — к варианту до 100 кг; применимость характеристики отложена до доказательства identity/revision.

### R015 — AMR 100 (грузоподъемность до 100 кг) — `specs.charging_requirements`

- Batch: `hybrid-conflicts-01`; organizer ID: `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff`.
- Catalog positions: `catalog-v4-row-0008`.
- Производитель: ООО "Морос"; класс: `MOBILE_TRANSPORT`.
- Identity: `AMBIGUOUS_MODEL_MATCH`; найдено: —.
- Требуется: `IDENTITY_REVIEW`; evidence status: `AMBIGUOUS_MODEL_MATCH`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `["automatic_dock", "manual charging"]` — source указан в batch
- Пояснение: Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.
- Evidence:
  - «Способ зарядки — Автоматическая док-станция / ручная зарядка» — [AMR100 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-100/), ООО «Морос», Технические характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **DEFER_IDENTITY** — —. Текущая официальная страница относится к AMR100 до 150 кг, а organizer position — к варианту до 100 кг; применимость характеристики отложена до доказательства identity/revision.

### R016 — AMR 100 (грузоподъемность до 100 кг) — `specs.dimensions`

- Batch: `hybrid-conflicts-01`; organizer ID: `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff`.
- Catalog positions: `catalog-v4-row-0008`.
- Производитель: ООО "Морос"; класс: `MOBILE_TRANSPORT`.
- Identity: `AMBIGUOUS_MODEL_MATCH`; найдено: —.
- Требуется: `IDENTITY_REVIEW`; evidence status: `AMBIGUOUS_MODEL_MATCH`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `[600, 400, 220] mm` — source указан в batch
- Пояснение: Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.
- Evidence:
  - «Габаритные размеры (Д×Ш×В) — 600 × 400 × 220 мм» — [AMR100 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-100/), ООО «Морос», Технические характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **DEFER_IDENTITY** — —. Текущая официальная страница относится к AMR100 до 150 кг, а organizer position — к варианту до 100 кг; применимость характеристики отложена до доказательства identity/revision.

### R017 — AMR 100 (грузоподъемность до 100 кг) — `specs.integrations`

- Batch: `hybrid-conflicts-01`; organizer ID: `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff`.
- Catalog positions: `catalog-v4-row-0008`.
- Производитель: ООО "Морос"; класс: `MOBILE_TRANSPORT`.
- Identity: `AMBIGUOUS_MODEL_MATCH`; найдено: —.
- Требуется: `IDENTITY_REVIEW`; evidence status: `AMBIGUOUS_MODEL_MATCH`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `["MES", "API"]` — source указан в batch
- Пояснение: Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.
- Evidence:
  - «Возможность интеграции с конвейерами, подъемниками, манипуляторами.» — [AMR100 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-100/), ООО «Морос», Ключевые функциональные возможности.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **DEFER_IDENTITY** — —. Текущая официальная страница относится к AMR100 до 150 кг, а organizer position — к варианту до 100 кг; применимость характеристики отложена до доказательства identity/revision.

### R018 — AMR 100 (грузоподъемность до 100 кг) — `specs.max_speed`

- Batch: `hybrid-conflicts-01`; organizer ID: `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff`.
- Catalog positions: `catalog-v4-row-0008`.
- Производитель: ООО "Морос"; класс: `MOBILE_TRANSPORT`.
- Identity: `AMBIGUOUS_MODEL_MATCH`; найдено: —.
- Требуется: `IDENTITY_REVIEW`; evidence status: `AMBIGUOUS_MODEL_MATCH`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `3.0 m/s` — source указан в batch
- Пояснение: Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.
- Evidence:
  - «Скорость перемещения — 3 м/с» — [AMR100 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-100/), ООО «Морос», Технические характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **DEFER_IDENTITY** — —. Текущая официальная страница относится к AMR100 до 150 кг, а organizer position — к варианту до 100 кг; применимость характеристики отложена до доказательства identity/revision.

### R019 — AMR 100 (грузоподъемность до 100 кг) — `specs.positioning_accuracy`

- Batch: `hybrid-conflicts-01`; organizer ID: `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff`.
- Catalog positions: `catalog-v4-row-0008`.
- Производитель: ООО "Морос"; класс: `MOBILE_TRANSPORT`.
- Identity: `AMBIGUOUS_MODEL_MATCH`; найдено: —.
- Требуется: `IDENTITY_REVIEW`; evidence status: `AMBIGUOUS_MODEL_MATCH`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `10.0 mm` — source указан в batch
- Пояснение: Источник относится к текущей модели/ревизии, но применимость к organizer identity документально не доказана.
- Evidence:
  - «Точность позиционирования — ±10 мм» — [AMR100 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-100/), ООО «Морос», Технические характеристики.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **DEFER_IDENTITY** — —. Текущая официальная страница относится к AMR100 до 150 кг, а organizer position — к варианту до 100 кг; применимость характеристики отложена до доказательства identity/revision.

### R020 — Робот-тягач RoboCV — `specs.max_speed`

- Batch: `hybrid-conflicts-01`; organizer ID: `b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1`.
- Catalog positions: `catalog-v4-row-0017`.
- Производитель: ООО "Робосиви"; класс: `MOBILE_TRANSPORT`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Робот-тягач RoboCV.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `{"html_unspecified_load_m_s": 2.2, "pdf_loaded_m_s": 2.0833, "pdf_unloaded_m_s": 3.3333} m/s` — source указан в batch
- Пояснение: Обе стороны сохранены; применимая revision/configuration документально не доказана.
- Evidence:
  - «Максимальная скорость, м/с: 2,2» — [Робот-тягач](https://robocv.ru/robot-tyagach), ООО «РобоСиВи», Технические характеристики.
  - «Макс. скорость без груза 12 км/ч» — [Спецификация робота-тягача RoboCV](https://robocv.ru/wp-content/uploads/2021/05/robot-tyagach-robocv-specifikaciya.pdf), ООО «РобоСиВи», Макс. скорость без груза.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_CONSERVATIVE** — 2.2 m/s. 2,2 м/с ниже опубликованных 12 км/ч без груза и не привязаны к оптимальному режиму без нагрузки; принято более осторожное значение без пересчёта единиц в resolved fact.

### R021 — Робот-тягач RoboCV — `specs.payload`

- Batch: `hybrid-conflicts-01`; organizer ID: `b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1`.
- Catalog positions: `catalog-v4-row-0017`.
- Производитель: ООО "Робосиви"; класс: `MOBILE_TRANSPORT`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Робот-тягач RoboCV.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `[5000, 4000] kg` — source указан в batch
- Пояснение: Обе стороны сохранены; применимая revision/configuration документально не доказана.
- Evidence:
  - «Грузоподъемность, кг: до 5000» — [Робот-тягач](https://robocv.ru/robot-tyagach), ООО «РобоСиВи», Технические характеристики.
  - «Сила тяги 4000кг» — [Спецификация робота-тягача RoboCV](https://robocv.ru/wp-content/uploads/2021/05/robot-tyagach-robocv-specifikaciya.pdf), ООО «РобоСиВи», Сила тяги.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_PAYLOAD_RECLASSIFY_TRACTION** — 5000 kg. По решению пользователя для payload принято единственное семантически соответствующее значение грузоподъёмности 5000 кг. Сила тяги 4000 кг является другой характеристикой, сохранена отдельно и не используется в runtime без контракта поля.

### R022 — Робот-тягач RoboCV — `specs.positioning_accuracy`

- Batch: `hybrid-conflicts-01`; organizer ID: `b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1`.
- Catalog positions: `catalog-v4-row-0017`.
- Производитель: ООО "Робосиви"; класс: `MOBILE_TRANSPORT`.
- Identity: `EXACT_MODEL_MATCH_WITH_CONFLICTS`; найдено: Робот-тягач RoboCV.
- Требуется: `CONFLICT_REVIEW`; evidence status: `CONFLICT`.
- Кандидат: `—`.
- Сравнение с локальным fact: `NOT_COMPARABLE`.
- Локальные facts:
  - `[50, 70] mm` — source указан в batch
- Пояснение: Обе стороны сохранены; применимая revision/configuration документально не доказана.
- Evidence:
  - «Точность навигации, см: 5» — [Робот-тягач](https://robocv.ru/robot-tyagach), ООО «РобоСиВи», Технические характеристики.
  - «Точность позиционирования 70мм» — [Спецификация робота-тягача RoboCV](https://robocv.ru/wp-content/uploads/2021/05/robot-tyagach-robocv-specifikaciya.pdf), ООО «РобоСиВи», Точность позиционирования.
- Рекомендуемое действие: проверить identity/revision/configuration и выбрать только доказанную сторону; иначе `DEFER`.
- Решение: **ACCEPT_POSITIONING_RECLASSIFY_NAVIGATION** — 70 mm. По решению пользователя для positioning accuracy принято семантически точное и более осторожное значение 70 мм из официального PDF. Точность навигации 50 мм сохранена отдельно и не используется в runtime без контракта поля.

## Затем: кандидаты на принятие

### Astramis SurfexUnit

`1625ac11-76d0-4994-a86a-e0a540453984` · positions: `catalog-v4-row-0111` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A001` | `specs.charging_requirements` | {"battery_replenishment": "automatic battery replacement"} | `NO_KNOWN_FACT` | [Astramis SurfexUnit – робот для автономной промышленной уборки складов и производств](https://astramis.com/SurfexUnit) | Опубликована автоматическая замена аккумуляторов; электрические параметры зарядки не указаны. | `ACCEPT` |
| `A002` | `specs.navigation` | {"sensors": ["Lidar", "machine-vision camera"]} | `NO_KNOWN_FACT` | [Astramis SurfexUnit – робот для автономной промышленной уборки складов и производств](https://astramis.com/SurfexUnit) | Навигационный стек указан явно на официальной странице модели. | `ACCEPT_EXACT_CANDIDATE` |
### Пиксель

`2f46660e-ea20-4845-9620-8c743b03225b` · positions: `catalog-v4-row-0107` · identity `EXACT_MODEL_MATCH_WITH_CONFLICTS`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A003` | `specs.autonomy` | 16 h | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | 16 h относится к работе за сутки при четырёх циклах зарядки, не к одному непрерывному заряду. | `ACCEPT_EXACT_CANDIDATE` |
| `A004` | `specs.charging_requirements` | {"charging_station": "Пиксель Поинт 22", "connector": "3P+PE", "current_A": 32, "supply_voltage_V": [230, 380]} | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | Нормализованы только опубликованные параметры комплекта зарядки и название станции. | `ACCEPT_EXACT_CANDIDATE` |
| `A005` | `specs.connectivity` | {"LTE_bands": [1, 2, 3, 7, 8, 20, 38, 40], "Wi-Fi": ["2.4 GHz 802.11b/g/n", "5 GHz 802.11a/n/ac"], "remote_control_radio": "2.4 GHz"} | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | Паспорт явно перечисляет LTE и Wi-Fi; частота радиопульта опубликована в том же разделе. | `ACCEPT_EXACT_CANDIDATE` |
| `A006` | `specs.dimensions` | [2460, 1500, 1680] mm | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | Порядок: Д × Ш × В; платформа без навесного оборудования. | `ACCEPT_EXACT_CANDIDATE` |
| `A007` | `specs.integrations` | {"attachment_bus": "CAN"} | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | Опубликовано подключение и управление навесным оборудованием через CAN. | `ACCEPT_EXACT_CANDIDATE` |
| `A008` | `specs.max_speed` | 10 km/h | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | Максимальная скорость движения опубликована прямо в паспорте. | `ACCEPT_EXACT_CANDIDATE` |
| `A009` | `specs.navigation` | {"inertial_system": true, "lidar": true, "satellite": ["GLONASS", "GPS"], "triangulation": true} | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | Объединены только явно перечисленные компоненты навигации одной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A010` | `specs.service_requirements` | {"service_schedule": "determined by operating and storage conditions"} | `NO_KNOWN_FACT` | [Паспорт. Многофункциональная роботизированная платформа для коммунального хозяйства «Пиксель». Модель 01.V1](https://storage.yandexcloud.net/web-fies/automatika/docs/01_%D0%9F%D0%B8%D0%BA%D1%81%D0%B5%D0%BB%D1%8C_%D0%9F%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82_V03_PixV1.pdf) | Паспорт прямо задаёт принцип определения графика сервисного обслуживания. | `ACCEPT_EXACT_CANDIDATE` |
### MARK 2 SE

`446c5207-a099-45e0-b615-afd60de08589` · positions: `catalog-v4-row-0022` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A011` | `capacity.cleaning_rate_m2_h` | [600, 700] m2/h | `NO_KNOWN_FACT` | [MARK 2 SE](https://r2b.company/mark2se) | Единица m²/h задана непосредственно вопросом официального FAQ; диапазон ответа не пересчитывался. | `ACCEPT_EXACT_CANDIDATE` |
| `A012` | `capacity.cleaning_width_m` | 0.45 m | `NO_KNOWN_FACT` | [MARK 2 SE](https://r2b.company/mark2se) | 450 mm нормализованы в 0.45 m без расчёта производной характеристики. | `ACCEPT_EXACT_CANDIDATE` |
| `A013` | `specs.min_aisle_width` | 1.3 m | `NO_KNOWN_FACT` | [Аренда робота-уборщика Mark 2 SE](https://r2b.company/rent) | Минимальная ширина прохода опубликована для Mark 2 SE. | `ACCEPT_EXACT_CANDIDATE` |
| `A014` | `specs.operating_conditions` | {"adapted_conditions": ["грязь весной", "грязь осенью", "грязь зимой"]} | `NO_COMPARABLE_KNOWN_VALUE` | [MARK 2 SE](https://r2b.company/mark2se) | Источник даёт качественное, не числовое описание условий эксплуатации. | `ACCEPT_EXACT_CANDIDATE` |
### Клинботикс 600

`5a5b3599-bd64-4330-9bbb-4f8ce7d780b9` · positions: `catalog-v4-row-0025` · identity `EXACT_MODEL_MATCH_WITH_CONFLICTS`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A015` | `capacity.cleaning_width_m` | 0.6 m | `NO_KNOWN_FACT` | [Модель Cleanbotics 600](https://waybotrobotics.com/models/600) | 60 cm нормализованы в 0.6 m. | `ACCEPT_EXACT_CANDIDATE` |
| `A016` | `specs.charging_requirements` | {"fast_full_charge_h": 1, "normal_full_charge_h": 2} | `NO_KNOWN_FACT` | [Модель Cleanbotics 600](https://waybotrobotics.com/models/600) | Производитель явно различает быстрый и обычный режимы зарядки. | `ACCEPT_EXACT_CANDIDATE` |
| `A017` | `specs.integrations` | ["лифты", "турникеты"] | `NO_KNOWN_FACT` | [Модель Cleanbotics 600](https://waybotrobotics.com/models/600) | Интеграции названы прямо на точной странице модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A018` | `specs.min_aisle_width` | 0.75 m | `NO_KNOWN_FACT` | [Модель Cleanbotics 600](https://waybotrobotics.com/models/600) | 750 mm нормализованы в 0.75 m. | `ACCEPT_EXACT_CANDIDATE` |
| `A019` | `specs.navigation` | {"algorithm": "SLAM", "lidar": {"additional_count": 3, "main_3D_fov_deg": 360}} | `NO_KNOWN_FACT` | [Модель Cleanbotics 600](https://waybotrobotics.com/models/600) | Нормализованы только явно опубликованные SLAM и параметры лидаров. | `ACCEPT_EXACT_CANDIDATE` |
| `A020` | `specs.operating_conditions` | {"active_traffic_supported": true, "max_threshold_cm": 5} | `NO_KNOWN_FACT` | [Модель Cleanbotics 600](https://waybotrobotics.com/models/600) | Страница модели прямо относит параметры к условиям эксплуатации. | `ACCEPT_EXACT_CANDIDATE` |
| `A021` | `specs.surface_requirements` | ["керамическая плитка", "керамогранит", "натуральный камень", "ПВХ и винил", "наливной пол", "дерево твердых пород"] | `NO_KNOWN_FACT` | [Модель Cleanbotics 600](https://waybotrobotics.com/models/600) | Типы поверхностей перечислены на точной странице модели. | `ACCEPT_EXACT_CANDIDATE` |
### БРО 2.1

`ba5d2051-3036-439f-8b2e-e05e26581fe6` · positions: `catalog-v4-row-0105` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A022` | `specs.autonomy` | {"continuous_cleaning": 6, "patrol": 10} h | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Оба режима автономной работы опубликованы для точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A023` | `specs.charging_requirements` | 4 h | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Опубликовано как время зарядки АКБ. | `ACCEPT_EXACT_CANDIDATE` |
| `A024` | `specs.dimensions` | {"height": 1120, "length": 1721, "width": 803} mm | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Габариты точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A025` | `specs.max_speed` | 5 km/h | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Нормализован опубликованный верхний предел рабочей скорости. | `ACCEPT_EXACT_CANDIDATE` |
| `A026` | `specs.operating_conditions` | {"max": 30, "min": -10} °C | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Опубликованный диапазон рабочих температур. | `ACCEPT_EXACT_CANDIDATE` |
| `A027` | `specs.surface_requirements` | {"max_slope_deg": 8, "max_step_m": 0.05} | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Сохранены две явно опубликованные характеристики проходимости без пересчёта. | `ACCEPT_EXACT_CANDIDATE` |
### Веном Саранча

`d4b39362-518a-4cf2-8770-b69bc03585a0` · positions: `catalog-v4-row-0108` · identity `EXACT_MODEL_MATCH_WITH_CONFLICTS`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A028` | `capacity.cleaning_width_m` | 0.95 m | `NO_KNOWN_FACT` | [Веном Саранча](https://rob-com.ru/tproduct/480874550-266559644532-venom-sarancha) | Ширина относится к шнекоротору точной модели; ширина самого ротора 1000 мм не подменяет ширину захвата. | `ACCEPT_EXACT_CANDIDATE` |
| `A029` | `specs.autonomy` | {"single_battery": 5, "with_spare_battery": 10} h | `NO_KNOWN_FACT` | [Робот косилка Venom САРАНЧА - купить с доставкой по России](https://rob-com.ru/robot-kosilka-venom-sarancha) | Режимы сохранены раздельно: один аккумулятор и запасной аккумулятор. | `ACCEPT_EXACT_CANDIDATE` |
| `A030` | `specs.connectivity` | пульт ДУ; до 200 м прямой видимости | `NO_KNOWN_FACT` | [Веном Саранча](https://rob-com.ru/tproduct/480874550-266559644532-venom-sarancha) | Зафиксирована явно опубликованная дистанционная связь управления и её дальность. | `ACCEPT_EXACT_CANDIDATE` |
| `A031` | `specs.dimensions` | {"height": 750, "length": 1800, "width": 1230} mm | `NO_KNOWN_FACT` | [Веном Саранча](https://rob-com.ru/tproduct/480874550-266559644532-venom-sarancha) | Габариты точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A032` | `specs.max_speed` | 5 km/h | `NO_KNOWN_FACT` | [Веном Саранча](https://rob-com.ru/tproduct/480874550-266559644532-venom-sarancha) | Поле — максимальная скорость; взят опубликованный верхний предел диапазона 3–5 км/ч. | `ACCEPT_EXACT_CANDIDATE` |
| `A033` | `specs.surface_requirements` | 30 deg | `NO_KNOWN_FACT` | [Робот косилка Venom САРАНЧА - купить с доставкой по России](https://rob-com.ru/robot-kosilka-venom-sarancha) | Опубликован предел уклона для точной модели. | `ACCEPT_EXACT_CANDIDATE` |
### АК-SC80

`e2095cfe-3ce4-404e-a4bb-2f378480d7ca` · positions: `catalog-v4-row-0023` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A034` | `capacity.cleaning_rate_m2_h` | 3000 m2/h | `NO_KNOWN_FACT` | [Автономный робот-уборщик АК-SC80](https://robot.automacon.ru/ak-sc80) | Производительность опубликована на странице точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A035` | `specs.autonomy` | 8 h | `NO_KNOWN_FACT` | [Автономные роботы-уборщики Автомакон](https://robot.automacon.ru/waybotrobot) | Официальный каталог связывает 8 часов непосредственно с АК-SC80. | `ACCEPT_EXACT_CANDIDATE` |
| `A036` | `specs.charging_requirements` | автоматическая зарядка | `NO_KNOWN_FACT` | [Автономный робот-уборщик АК-SC80](https://robot.automacon.ru/ak-sc80) | Опубликован автоматический режим зарядки; время зарядки не заявлено. | `ACCEPT_EXACT_CANDIDATE` |
| `A037` | `specs.connectivity` | автоматическая загрузка отчётов на сервер | `NO_KNOWN_FACT` | [Автономный робот-уборщик АК-SC80](https://robot.automacon.ru/ak-sc80) | Зафиксирована явно опубликованная серверная передача данных. | `ACCEPT_EXACT_CANDIDATE` |
| `A038` | `specs.integrations` | ["системы доступа", "лифты", "автоматические ворота"] | `NO_KNOWN_FACT` | [Автономный робот-уборщик АК-SC80](https://robot.automacon.ru/ak-sc80) | Интеграции перечислены прямо на странице точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A039` | `specs.navigation` | запатентованная навигация по контурам; интеллектуальное картографирование; автономный обход препятствий | `NO_KNOWN_FACT` | [Автономный робот-уборщик АК-SC80](https://robot.automacon.ru/ak-sc80) | Сохранены только прямо названные навигационные возможности. | `ACCEPT_EXACT_CANDIDATE` |
| `A040` | `specs.operating_conditions` | средние и крупные крытые и открытые площади | `NO_KNOWN_FACT` | [Автономный робот-уборщик АК-SC80](https://robot.automacon.ru/ak-sc80) | Опубликован тип среды эксплуатации. | `ACCEPT_EXACT_CANDIDATE` |
| `A041` | `specs.surface_requirements` | ["керамическая плитка", "гравий", "мрамор", "бетонный пол", "карбид кремния", "мелкая плитка", "терраццо", "эпоксидный пол"] | `NO_KNOWN_FACT` | [Автономный робот-уборщик АК-SC80](https://robot.automacon.ru/ak-sc80) | Список поверхностей опубликован на странице точной модели. | `ACCEPT_EXACT_CANDIDATE` |
### РУБИ-С-03

`e8960183-1828-4fdb-8c39-91f5a3523a96` · positions: `catalog-v4-row-0021` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A042` | `capacity.cleaning_rate_m2_h` | 790 m2/h | `NO_KNOWN_FACT` | [Prime Park](https://robo.ooo/prime-park) | Показатель опубликован производителем для внедрения именно РУБИ-С-03. | `ACCEPT_EXACT_CANDIDATE` |
| `A043` | `specs.charging_requirements` | автономная подзарядка | `NO_KNOWN_FACT` | [Prime Park](https://robo.ooo/prime-park) | Функция опубликована в официальном кейсе точной ревизии. | `ACCEPT_EXACT_CANDIDATE` |
| `A044` | `specs.connectivity` | ROBO FMS; контроль парка в реальном времени | `NO_KNOWN_FACT` | [Prime Park](https://robo.ooo/prime-park) | Зафиксировано model-specific подключение к платформе управления; сетевой протокол не заявлен. | `ACCEPT_EXACT_CANDIDATE` |
| `A045` | `specs.integrations` | ROBO FMS | `NO_KNOWN_FACT` | [Prime Park](https://robo.ooo/prime-park) | Официальный кейс прямо связывает точную ревизию с ROBO FMS. | `ACCEPT_EXACT_CANDIDATE` |
### БРО 3.0

`ef375ca1-8de1-4a8d-9262-c1a6b71f0333` · positions: `catalog-v4-row-0106` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A046` | `capacity.cleaning_rate_m2_h` | {"max": 6000, "min": 2400} m2/h | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Диапазон переведён из явно опубликованных тысяч м²/ч в м²/ч. | `ACCEPT_EXACT_CANDIDATE` |
| `A047` | `specs.autonomy` | {"continuous_cleaning_min": 5.5, "patrol": 15} h | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Сохранены опубликованные режимы и нижняя граница для сплошной уборки. | `ACCEPT_EXACT_CANDIDATE` |
| `A048` | `specs.charging_requirements` | 2.5 h | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Опубликован верхний предел времени зарядки. | `ACCEPT_EXACT_CANDIDATE` |
| `A049` | `specs.dimensions` | {"height": 1276, "length": 1994, "width": 1252} mm | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Габариты точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A050` | `specs.max_speed` | 5 km/h | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Нормализован опубликованный верхний предел рабочей скорости. | `ACCEPT_EXACT_CANDIDATE` |
| `A051` | `specs.operating_conditions` | {"max": 30, "min": -10} °C | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Опубликованный диапазон рабочих температур. | `ACCEPT_EXACT_CANDIDATE` |
| `A052` | `specs.surface_requirements` | {"max_slope_deg": 8, "max_step_m": 0.05} | `NO_KNOWN_FACT` | [168robotics Робоуборка](https://168robotics.com/robots) | Сохранены две явно опубликованные характеристики проходимости без пересчёта. | `ACCEPT_EXACT_CANDIDATE` |
### Клинботикс 400 PRO

`f31223c1-44c8-4410-8381-6356e2158b61` · positions: `catalog-v4-row-0024` · identity `EXACT_MODEL_MATCH_WITH_CONFLICTS`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A053` | `capacity.cleaning_width_m` | {"vacuum": 0.5, "wet": 0.4} m | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Ширина опубликована отдельно по режимам; значения не объединялись. | `ACCEPT_EXACT_CANDIDATE` |
| `A054` | `specs.autonomy` | 3 h | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Опубликовано для влажной уборки на одном заряде. | `ACCEPT_EXACT_CANDIDATE` |
| `A055` | `specs.charging_requirements` | 1 h | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Опубликовано как время зарядки. | `ACCEPT_EXACT_CANDIDATE` |
| `A056` | `specs.connectivity` | Waybot Control; удалённый запуск | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Зафиксированы model-specific удалённое управление и фирменный интерфейс; сетевой протокол не заявлен. | `ACCEPT_EXACT_CANDIDATE` |
| `A057` | `specs.integrations` | ["лифты", "турникеты"] | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Интеграции указаны прямо на странице точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A058` | `specs.navigation` | SLAM; 3D-лидар 360°; 5 дополнительных лидаров; 4 HD-камеры | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Навигационный алгоритм и сенсоры опубликованы для точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A059` | `specs.operating_conditions` | {"high_traffic": true, "max_area_m2": 2000, "max_threshold_cm": 1.5} | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Сохранены три явно опубликованных условия без вывода дополнительных ограничений. | `ACCEPT_EXACT_CANDIDATE` |
| `A060` | `specs.service_requirements` | модульная конструкция; лёгкий доступ к узлам; простое обслуживание | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Опубликована качественная характеристика обслуживания, без придуманной периодичности. | `ACCEPT_EXACT_CANDIDATE` |
| `A061` | `specs.surface_requirements` | ["керамическая плитка", "керамогранит", "натуральный камень", "ПВХ и винил", "наливной пол", "ковровые покрытия с низким ворсом", "дерево твердых пород"] | `NO_KNOWN_FACT` | [Модель Cleanbotics 400 PRO](https://waybotrobotics.com/models/400pro) | Список поверхностей опубликован на странице точной модели. | `ACCEPT_EXACT_CANDIDATE` |
### Робот для транспортировки деталей и инструментов

`0265d700-534e-417e-8fde-47de88fc3ebb` · positions: `catalog-v4-row-0071` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A062` | `specs.max_speed` | 1.5 m/s | `NO_KNOWN_FACT` | [В ОДК-СТАР создают робота для транспортировки деталей и инструмента](https://www.uecrus.com/press/v-odk-star-sozdayut-robota-dlya-transportirovki-detaley-i-instrumenta/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A063` | `specs.navigation` | навигация по карте | `NO_KNOWN_FACT` | [В ОДК-СТАР создают робота для транспортировки деталей и инструмента](https://www.uecrus.com/press/v-odk-star-sozdayut-robota-dlya-transportirovki-detaley-i-instrumenta/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A064` | `specs.payload` | 100 kg | `NO_KNOWN_FACT` | [В ОДК-СТАР создают робота для транспортировки деталей и инструмента](https://www.uecrus.com/press/v-odk-star-sozdayut-robota-dlya-transportirovki-detaley-i-instrumenta/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
### Беспилотный погрузчик

`19a68304-56f7-432f-afd8-b97b2b8466ba` · positions: `catalog-v4-row-0019` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A065` | `specs.navigation` | потолочные оптические метки в видимом диапазоне | `NO_KNOWN_FACT` | [Автономный склад: инженеры МФТИ разработали робота-кладовщика](https://ai.mipt.ru/news/tpost/n0tcjtjoy1-avtonomnii-sklad-inzheneri-mfti-razrabot) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
### Беспилотный тягач (Когнитив Пилот)

`28a5afa8-0473-4f80-99a9-b2922b76810f` · positions: `catalog-v4-row-0189` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A066` | `specs.connectivity` | взаимодействие роботов в реальном времени | `NO_KNOWN_FACT` | [До конца года в Пулково внедрят флот беспилотных тягачей под управлением ИИ](https://cognitivepilot.com/cognitive-news/news/do-kontsa-goda-v-pulkovo-vnedryat-flot-bespilotnykh-tyagachey-pod-upravleniem-ii/) | Значение явно опубликовано для применимого проекта. | `ACCEPT_EXACT_CANDIDATE` |
| `A067` | `specs.integrations` | ["система управления аэропортом"] | `NO_KNOWN_FACT` | [До конца года в Пулково внедрят флот беспилотных тягачей под управлением ИИ](https://cognitivepilot.com/cognitive-news/news/do-kontsa-goda-v-pulkovo-vnedryat-flot-bespilotnykh-tyagachey-pod-upravleniem-ii/) | Значение явно опубликовано для применимого проекта. | `ACCEPT_EXACT_CANDIDATE` |
| `A068` | `specs.max_speed` | 15 km/h | `NO_KNOWN_FACT` | [В аэропорту Пулково появятся беспилотные роботы-грузчики](https://cognitivepilot.com/cognitive-news/news/v-aeroportu-pulkovo-poyavyatsya-bespilotnye-roboty-gruzchiki/) | Значение явно опубликовано для применимого проекта. | `ACCEPT_EXACT_CANDIDATE` |
| `A069` | `specs.navigation` | {"control": "нейросети", "sensors": ["4 видеокамеры", "лидары", "радары"]} | `NO_KNOWN_FACT` | [До конца года в Пулково внедрят флот беспилотных тягачей под управлением ИИ](https://cognitivepilot.com/cognitive-news/news/do-kontsa-goda-v-pulkovo-vnedryat-flot-bespilotnykh-tyagachey-pod-upravleniem-ii/) | Значение явно опубликовано для применимого проекта. | `ACCEPT_EXACT_CANDIDATE` |
| `A070` | `specs.operating_conditions` | сложные метеоусловия Санкт-Петербурга | `NO_KNOWN_FACT` | [До конца года в Пулково внедрят флот беспилотных тягачей под управлением ИИ](https://cognitivepilot.com/cognitive-news/news/do-kontsa-goda-v-pulkovo-vnedryat-flot-bespilotnykh-tyagachey-pod-upravleniem-ii/) | Значение явно опубликовано для применимого проекта. | `ACCEPT_EXACT_CANDIDATE` |
| `A071` | `specs.payload` | 3 t | `NO_KNOWN_FACT` | [Пулково встречает будущее!](https://cognitivepilot.com/cognitive-news/blog/pulkovo-vstrechaet-budushchee/) | Значение явно опубликовано для применимого проекта. | `ACCEPT_EXACT_CANDIDATE` |
### Ronavi SR (грузоподъемность до 50 кг)

`3f2aaa1b-2237-4d7b-b215-1ac5ec789ed5` · positions: `catalog-v4-row-0003` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A072` | `specs.autonomy` | 16 h | `NO_KNOWN_FACT` | [Ronavi SR — робот-сортировщик для склада \| Автоматическая сортировка грузов до 50 кг](https://ronavi-robotics.ru/catalogue/sr) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A073` | `specs.connectivity` | Wi-Fi 5 ГГц 802.11 a/c/n | `NO_KNOWN_FACT` | [Ronavi SR — робот-сортировщик для склада \| Автоматическая сортировка грузов до 50 кг](https://ronavi-robotics.ru/catalogue/sr) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A074` | `specs.integrations` | ["WMS", "система управления складом и производством", "открытый API"] | `NO_KNOWN_FACT` | [Ronavi SR — робот-сортировщик для склада \| Автоматическая сортировка грузов до 50 кг](https://ronavi-robotics.ru/catalogue/sr) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A075` | `specs.max_speed` | 3 m/s | `NO_KNOWN_FACT` | [Ronavi SR — робот-сортировщик для склада \| Автоматическая сортировка грузов до 50 кг](https://ronavi-robotics.ru/catalogue/sr) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A076` | `specs.min_aisle_width` | 690 mm | `NO_KNOWN_FACT` | [Ronavi SR — робот-сортировщик для склада \| Автоматическая сортировка грузов до 50 кг](https://ronavi-robotics.ru/catalogue/sr) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A077` | `specs.navigation` | ["QR-метки"] | `NO_KNOWN_FACT` | [Ronavi SR — робот-сортировщик для склада \| Автоматическая сортировка грузов до 50 кг](https://ronavi-robotics.ru/catalogue/sr) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A078` | `specs.service_requirements` | полная сервисная поддержка в РФ | `NO_KNOWN_FACT` | [Ronavi SR — робот-сортировщик для склада \| Автоматическая сортировка грузов до 50 кг](https://ronavi-robotics.ru/catalogue/sr) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
### Ronavi SD (грузоподъемность до 10 кг)

`66d8e7ad-cdcd-4287-afb0-e2afa9ef5217` · positions: `catalog-v4-row-0005` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A079` | `specs.connectivity` | Wi-Fi 5 ГГц 802.11 a/c/n | `NO_KNOWN_FACT` | [Ronavi SD — робот для сортировки посылок и писем до 10 кг \| Купить AMR для почтовой логистики](https://ronavi-robotics.ru/catalogue/sd) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A080` | `specs.integrations` | ["ТСД", "система управления складом", "почтовые системы"] | `NO_KNOWN_FACT` | [Ronavi SD — робот для сортировки посылок и писем до 10 кг \| Купить AMR для почтовой логистики](https://ronavi-robotics.ru/catalogue/sd) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A081` | `specs.service_requirements` | полная сервисная поддержка | `NO_KNOWN_FACT` | [Ronavi SD — робот для сортировки посылок и писем до 10 кг \| Купить AMR для почтовой логистики](https://ronavi-robotics.ru/catalogue/sd) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
### Ronavi H2000 (грузоподъемность до 2 000 кг)

`6f3da854-41da-4363-8496-5487f37c845a` · positions: `catalog-v4-row-0004`, `catalog-v4-row-0068` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A082` | `specs.min_aisle_width` | 1190 mm | `NO_KNOWN_FACT` | [Ronavi H2000 — робот для гибкого конвейера до 2000 кг \| Компенсация конвейерных разрывов](https://ronavi-robotics.ru/catalogue/h2000) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A083` | `specs.operating_conditions` | {"context": "цех", "environment": "внутри помещений"} | `NO_COMPARABLE_KNOWN_VALUE` | [Ronavi H2000 — робот для гибкого конвейера до 2000 кг \| Компенсация конвейерных разрывов](https://ronavi-robotics.ru/catalogue/h2000) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
### AMR 1500 (грузоподъемность до 1 500 кг)

`7d5a76d2-7bf3-4a40-b6f7-64590d4d9273` · positions: `catalog-v4-row-0010` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A084` | `specs.autonomy` | 22 h | `NO_KNOWN_FACT` | [AMR1500 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-1500/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A085` | `specs.charging_requirements` | ["автоматическая док-станция", "ручная зарядка"] | `NO_KNOWN_FACT` | [AMR1500 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-1500/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A086` | `specs.integrations` | ["MES", "WMS", "API для промышленных систем"] | `NO_KNOWN_FACT` | [AMR1500 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-1500/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A087` | `specs.max_speed` | 1.5 m/s | `NO_KNOWN_FACT` | [AMR1500 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-1500/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A088` | `specs.navigation` | ["QR-метки", "SLAM"] | `NO_KNOWN_FACT` | [AMR1500 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-1500/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A089` | `specs.operating_conditions` | {"optional_ip_rating": "IP54+", "temperature_degC": [5, 40]} | `NO_KNOWN_FACT` | [AMR1500 — Автономный мобильный робот от МОРОС](https://xn--l1aeahg.xn--p1ai/amr-1500/) | Значение явно опубликовано для применимой модели. | `ACCEPT_EXACT_CANDIDATE` |
### L5

`a834aa03-136e-4f61-a1d6-b5563d798f68` · positions: `catalog-v4-row-0198` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A090` | `specs.autonomy` | 23 h | `NO_KNOWN_FACT` | [Создан автономным](https://truck.navio.auto/) | Это опубликованное время нахождения в движении, а не заявленная ёмкость батареи или запас хода. | `ACCEPT_EXACT_CANDIDATE` |
| `A091` | `specs.connectivity` | V2X (vehicle-to-everything) | `NO_KNOWN_FACT` | [Создан автономным: Navio представляет магистральный тягач L5](https://navio.auto/news/technology-11) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A092` | `specs.navigation` | ["лидары", "радары", "камеры"] | `NO_KNOWN_FACT` | [Создан автономным: Navio представляет магистральный тягач L5](https://navio.auto/news/technology-11) | Нормализован только явно перечисленный сенсорный контур автономного вождения. | `ACCEPT_EXACT_CANDIDATE` |
| `A093` | `specs.operating_conditions` | круглосуточный контроль удалённых операторов | `NO_KNOWN_FACT` | [Создан автономным](https://truck.navio.auto/) | Зафиксировано как явно опубликованный режим эксплуатации/надзора. | `ACCEPT_EXACT_CANDIDATE` |
### DMR 600 (грузоподъемность до 600 кг)

`be814758-3616-4b94-befa-9848be2ac604` · positions: `catalog-v4-row-0012`, `catalog-v4-row-0065` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A094` | `specs.autonomy` | 8 h | `NO_KNOWN_FACT` | [Автономный мобильный робот-тележка ДиКом DMR 600 (AMR)](https://dikom-a.ru/product/dmr-600) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A095` | `specs.charging_requirements` | 2 h | `NO_KNOWN_FACT` | [Автономный мобильный робот-тележка ДиКом DMR 600 (AMR)](https://dikom-a.ru/product/dmr-600) | Опубликовано именно время зарядки; тип/электропараметры станции не нормализовались. | `ACCEPT_EXACT_CANDIDATE` |
| `A096` | `specs.integrations` | Яндекс Роботикс | `NO_KNOWN_FACT` | [Автономный мобильный робот-тележка ДиКом DMR 600 (AMR)](https://dikom-a.ru/product/dmr-600) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A097` | `specs.max_speed` | 2 m/s | `NO_KNOWN_FACT` | [Автономный мобильный робот-тележка ДиКом DMR 600 (AMR)](https://dikom-a.ru/product/dmr-600) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A098` | `specs.navigation` | SLAM | `NO_KNOWN_FACT` | [Автономный мобильный робот-тележка ДиКом DMR 600 (AMR)](https://dikom-a.ru/product/dmr-600) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A099` | `specs.service_requirements` | ["доставка и монтаж", "настройка программного обеспечения", "гарантийное сервисное обслуживание", "техническая поддержка"] | `NO_KNOWN_FACT` | [Автономный мобильный робот-тележка ДиКом DMR 600 (AMR)](https://dikom-a.ru/product/dmr-600) | Нормализованы только явно перечисленные элементы сопровождения DMR 600. | `ACCEPT_EXACT_CANDIDATE` |
### DMR 1200 (грузоподъемность до 1 200 кг)

`cccd0c0d-8ae7-435d-a171-45f5d82886e6` · positions: `catalog-v4-row-0011` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A100` | `specs.max_speed` | 2 m/s | `NO_KNOWN_FACT` | [Автоматизация и роботизация производств и складов от завода "ДиКом"](https://dikom-a.ru/) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
### Ronavi M (грузоподъемность до 1200 кг)

`dcfd9975-81eb-49b5-a422-827a720ba582` · positions: `catalog-v4-row-0006` · identity `EXACT_MODEL_MATCH_WITH_CONFLICTS`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A101` | `specs.autonomy` | 8 h | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A102` | `specs.charging_requirements` | зоны для подзарядки | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A103` | `specs.connectivity` | Wi-Fi 5 ГГц 802.11 a/c/n | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A104` | `specs.integrations` | ["Open API", "WMS: 1С, SAP, Oracle", "RMS"] | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A105` | `specs.max_speed` | 2.5 m/s | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A106` | `specs.navigation` | ["QR-метки", "SLAM"] | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A107` | `specs.operating_conditions` | ровное твердое покрытие (бетон, асфальт); минимальная ширина проезда 800 мм; зоны для подзарядки | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Сохранён опубликованный набор «стандартных условий» без вычислений. | `ACCEPT_EXACT_CANDIDATE` |
| `A108` | `specs.service_requirements` | 1 year | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Зафиксирован опубликованный model-specific срок гарантии как сервисное условие. | `ACCEPT_EXACT_CANDIDATE` |
| `A109` | `specs.surface_requirements` | ровное твердое покрытие (бетон, асфальт); допустимы неровности до 10 мм | `NO_KNOWN_FACT` | [Ronavi M — напольный логистический робот-тележка для комплектации «товар к человеку»](https://ronavi-robotics.ru/catalogue/m) | Нормализованы два явно опубликованных требования/допуска к покрытию. | `ACCEPT_EXACT_CANDIDATE` |
### MULE

`ecd7d582-b342-449a-b43b-66288d159a32` · positions: `catalog-v4-row-0020` · identity `EXACT_MODEL_MATCH`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A110` | `specs.charging_requirements` | автоматическая | `NO_KNOWN_FACT` | [SM ROBOTICS — автономный палетоперевозчик MULE](https://sm-robotics.ru/) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A111` | `specs.integrations` | ["M-CONTROL", "WMS"] | `NO_KNOWN_FACT` | [SM ROBOTICS — автономный палетоперевозчик MULE](https://sm-robotics.ru/) | M-CONTROL опубликован на той же официальной странице как система управления флотом роботов SM ROBOTICS. | `ACCEPT_EXACT_CANDIDATE` |
| `A112` | `specs.max_speed` | 1.3 m/s | `NO_KNOWN_FACT` | [SM ROBOTICS — автономный палетоперевозчик MULE](https://sm-robotics.ru/) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A113` | `specs.navigation` | SLAM | `NO_KNOWN_FACT` | [SM ROBOTICS — автономный палетоперевозчик MULE](https://sm-robotics.ru/) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
| `A114` | `specs.payload` | 1500 kg | `NO_KNOWN_FACT` | [SM ROBOTICS — автономный палетоперевозчик MULE](https://sm-robotics.ru/) | Проверить применимость к точной модели. | `ACCEPT_EXACT_CANDIDATE` |
### Робот-штабелёр RoboCV

`2ffc706d-fe43-4c2b-baad-a624a95ad3ce` · positions: `catalog-v4-row-0016` · identity `EXACT_MODEL_MATCH_WITH_CONFLICTS`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A115` | `specs.min_aisle_width` | 2.9 m | `NO_KNOWN_FACT` | [Робот-штабелёр](https://robocv.ru/robot-shtabelyor) | Evidence URL восстановлен детерминированным join с локальным known_source_candidate. | `ACCEPT_EXACT_CANDIDATE` |
### Робот-тягач RoboCV

`b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1` · positions: `catalog-v4-row-0017` · identity `EXACT_MODEL_MATCH_WITH_CONFLICTS`

| ID | Поле | Кандидат | Сравнение | Источник | Что проверить | Решение |
|---|---|---|---|---|---|---|
| `A116` | `specs.min_aisle_width` | 2.9 m | `NO_KNOWN_FACT` | [Робот-тягач](https://robocv.ru/robot-tyagach) | Evidence URL восстановлен детерминированным join с локальным known_source_candidate. | `ACCEPT_EXACT_CANDIDATE` |

## Ненайденные поля

Эти поля не являются кандидатами на принятие. Они остаются `NEEDS_FACTS`; запрещено заменять их типовыми значениями класса.

| Робот | Organizer ID | Количество | Поля |
|---|---|---:|---|
| AK-2000-2 | `5a36611d-033e-4893-bd49-5d4f776f57dd` | 8 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.connectivity`, `specs.integrations`, `specs.min_aisle_width`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| AMR 100 (грузоподъемность до 100 кг) | `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff` | 8 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.connectivity`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| AMR 1500 (грузоподъемность до 1 500 кг) | `7d5a76d2-7bf3-4a40-b6f7-64590d4d9273` | 6 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.connectivity`, `specs.min_aisle_width`, `specs.service_requirements`, `specs.surface_requirements` |
| AMR 800 (грузоподъемность до 800 кг) | `5ec66969-8fcc-47b3-b517-a9c29372fffe` | 6 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.connectivity`, `specs.min_aisle_width`, `specs.service_requirements`, `specs.surface_requirements` |
| ARIPIX А1 | `d55f507b-b3f2-4666-b3f4-dd3d48813e9d` | 7 | `specs.dimensions`, `specs.integrations`, `specs.operating_conditions`, `specs.payload`, `specs.positioning_accuracy`, `specs.service_requirements`, `specs.throughput` |
| Astramis SurfexUnit | `1625ac11-76d0-4994-a86a-e0a540453984` | 11 | `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| DMR 1200 (грузоподъемность до 1 200 кг) | `cccd0c0d-8ae7-435d-a171-45f5d82886e6` | 11 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| DMR 300 Carrier B | `a83abbfd-78ee-43dc-9111-f51db4938001` | 13 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.payload`, `specs.service_requirements`, `specs.surface_requirements` |
| DMR 600 (грузоподъемность до 600 кг) | `be814758-3616-4b94-befa-9848be2ac604` | 6 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.connectivity`, `specs.min_aisle_width`, `specs.operating_conditions`, `specs.surface_requirements` |
| L5 | `a834aa03-136e-4f61-a1d6-b5563d798f68` | 9 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.charging_requirements`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.payload`, `specs.service_requirements`, `specs.surface_requirements` |
| MARK 2 SE | `446c5207-a099-45e0-b615-afd60de08589` | 2 | `specs.connectivity`, `specs.integrations` |
| MULE | `ecd7d582-b342-449a-b43b-66288d159a32` | 8 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.connectivity`, `specs.min_aisle_width`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Ronavi H1500 (грузоподъемность до 1 500 кг) | `5760e938-9a43-45a7-b8e8-f4f2e6383930` | 3 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.surface_requirements` |
| Ronavi H2000 (грузоподъемность до 2 000 кг) | `6f3da854-41da-4363-8496-5487f37c845a` | 3 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.surface_requirements` |
| Ronavi M (грузоподъемность до 1200 кг) | `dcfd9975-81eb-49b5-a422-827a720ba582` | 2 | `capacity.exchange_time_s`, `capacity.units_per_trip` |
| Ronavi RCM (грузоподъемность до 350 кг) | `4d347e47-38f9-415b-aae1-7a6d3759a75c` | 12 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Ronavi SD (грузоподъемность до 10 кг) | `66d8e7ad-cdcd-4287-afb0-e2afa9ef5217` | 5 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.charging_requirements`, `specs.operating_conditions`, `specs.surface_requirements` |
| Ronavi SR (грузоподъемность до 50 кг) | `3f2aaa1b-2237-4d7b-b215-1ac5ec789ed5` | 5 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.charging_requirements`, `specs.operating_conditions`, `specs.surface_requirements` |
| Tagarka (грузоподъемность до 6 000 кг) | `c9e9517c-18f0-47b4-aa05-4344566aa885` | 12 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Unit | `9b20417a-0ac7-4786-985b-f3459a15075d` | 13 | `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| АК-SC80 | `e2095cfe-3ce4-404e-a4bb-2f378480d7ca` | 5 | `capacity.cleaning_width_m`, `specs.dimensions`, `specs.max_speed`, `specs.min_aisle_width`, `specs.service_requirements` |
| БРО 2.1 | `ba5d2051-3036-439f-8b2e-e05e26581fe6` | 7 | `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.connectivity`, `specs.integrations`, `specs.min_aisle_width`, `specs.navigation`, `specs.service_requirements` |
| БРО 3.0 | `ef375ca1-8de1-4a8d-9262-c1a6b71f0333` | 6 | `capacity.cleaning_width_m`, `specs.connectivity`, `specs.integrations`, `specs.min_aisle_width`, `specs.navigation`, `specs.service_requirements` |
| Белка | `cdf80f5b-c60a-447b-af30-2c8a44480f98` | 14 | `capacity.elevator_compatibility`, `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.payload`, `specs.service_requirements`, `specs.surface_requirements` |
| Беспилотный погрузчик | `19a68304-56f7-432f-afd8-b97b2b8466ba` | 12 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.operating_conditions`, `specs.payload`, `specs.service_requirements`, `specs.surface_requirements` |
| Беспилотный тягач (Когнитив Пилот) | `28a5afa8-0473-4f80-99a9-b2922b76810f` | 7 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.min_aisle_width`, `specs.service_requirements`, `specs.surface_requirements` |
| Веном Саранча | `d4b39362-518a-4cf2-8770-b69bc03585a0` | 6 | `capacity.cleaning_rate_m2_h`, `specs.charging_requirements`, `specs.integrations`, `specs.min_aisle_width`, `specs.navigation`, `specs.service_requirements` |
| Депеша-3 | `0b9f76be-8213-4938-9661-2bb669dc3d33` | 13 | `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Клинботикс 400 PRO | `f31223c1-44c8-4410-8381-6356e2158b61` | 1 | `specs.max_speed` |
| Клинботикс 600 | `5a5b3599-bd64-4330-9bbb-4f8ce7d780b9` | 3 | `specs.connectivity`, `specs.max_speed`, `specs.service_requirements` |
| МАРК | `5cecfb84-143b-4af7-89fb-afbf57403792` | 13 | `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Пиксель | `2f46660e-ea20-4845-9620-8c743b03225b` | 4 | `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.min_aisle_width`, `specs.surface_requirements` |
| РУБИ-С-03 | `e8960183-1828-4fdb-8c39-91f5a3523a96` | 9 | `capacity.cleaning_width_m`, `specs.autonomy`, `specs.dimensions`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Робот для транспортировки деталей и инструментов | `0265d700-534e-417e-8fde-47de88fc3ebb` | 10 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.min_aisle_width`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Робот-комплектовщик | `c3d39a80-5fb9-42d3-82ae-0696fb647128` | 13 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.payload`, `specs.service_requirements`, `specs.surface_requirements` |
| Робот-тягач RoboCV | `b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1` | 6 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Робот-штабелёр RoboCV | `2ffc706d-fe43-4c2b-baad-a624a95ad3ce` | 7 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.connectivity`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |
| Роботизированный комплекс по обследованию грунта | `b86f4613-789b-4cee-9f75-5d010da90b61` | 13 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.payload`, `specs.service_requirements`, `specs.surface_requirements` |
| Роботизированный комплекс по укладке заготовок | `22b5ba99-bc4f-46a7-9a9b-e4475ecd9fc7` | 7 | `specs.dimensions`, `specs.integrations`, `specs.operating_conditions`, `specs.payload`, `specs.positioning_accuracy`, `specs.service_requirements`, `specs.throughput` |
| Сёмабот (грузоподъемность до 1 500 кг) | `993d980e-8b91-45e0-9c98-50ffab6e11e4` | 12 | `capacity.exchange_time_s`, `capacity.units_per_trip`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements` |

## Статус

Все пункты изначально имеют статус **не принято**. Решения фиксируются следующими итерациями по одному ID.
