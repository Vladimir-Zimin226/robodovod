# ChatGPT Deep Research: catalog evidence batch `deep-cleaning-01`

## Результат задачи

Исследуй ровно 7 model identities из приложенного batch и верни ровно 84 field results: по одному для каждого `research_target`. Найди только явно опубликованные model-specific значения и доказательства. Не исследуй модели вне batch, цены, экономику, procurement, capacity formulas или runtime activation.

## Жёсткая блокировка scope

Ниже приведён исчерпывающий roster этого запуска. Это не пример и не рекомендация: разрешены только эти `organizer_id`, модели и target fields.

Scope fingerprint SHA-256: `363b42de85a3204f54e542f4bee4e758967fb1ef98ad710f9425783e5d453a40`

1. `0b9f76be-8213-4938-9661-2bb669dc3d33` — **Депеша-3**
   - targets (13): `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements`
2. `1625ac11-76d0-4994-a86a-e0a540453984` — **Astramis SurfexUnit**
   - targets (13): `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements`
3. `2f46660e-ea20-4845-9620-8c743b03225b` — **Пиксель**
   - targets (13): `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements`
4. `446c5207-a099-45e0-b615-afd60de08589` — **MARK 2 SE**
   - targets (6): `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.connectivity`, `specs.integrations`, `specs.min_aisle_width`, `specs.operating_conditions`
5. `5a5b3599-bd64-4330-9bbb-4f8ce7d780b9` — **Клинботикс 600**
   - targets (13): `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements`
6. `5cecfb84-143b-4af7-89fb-afbf57403792` — **МАРК**
   - targets (13): `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements`
7. `9b20417a-0ac7-4786-985b-f3459a15075d` — **Unit**
   - targets (13): `capacity.cleaning_rate_m2_h`, `capacity.cleaning_width_m`, `specs.autonomy`, `specs.charging_requirements`, `specs.connectivity`, `specs.dimensions`, `specs.integrations`, `specs.max_speed`, `specs.min_aisle_width`, `specs.navigation`, `specs.operating_conditions`, `specs.service_requirements`, `specs.surface_requirements`

До веб-поиска прочитай `01-BATCH-deep-cleaning-01.json` и сравни его с roster выше и с `x-robodovod-scope-lock` в `03-RETURN-SCHEMA-REQUIRED.json`. Они должны дословно совпадать по `batch_id`, каждому UUID, названию и target fields.

Если вложение недоступно или найдено хотя бы одно несовпадение, не подставляй другие модели из памяти, предыдущего чата или поисковой выдачи. Остановись до исследования с единственным сообщением `SCOPE_MISMATCH` и перечисли несовпадение. Любая модель, которой нет в roster выше, запрещена, даже если совпадает количество моделей или полей.

## Входные файлы и доступ к вебу

Файлы `01-BATCH-deep-cleaning-01.json`, `02-RUNTIME-CONTRACT.json` и `03-RETURN-SCHEMA-REQUIRED.json` задают scope, контекст и JSON schema. Они не являются источниками новых ТТХ и не ограничивают источники исследования.

Публичный веб-поиск обязателен для каждой модели. Открывай внешние страницы и документы. `known_source_candidates` — только отправные точки: проверь их содержимое и ищи дополнительные официальные источники. Отсутствие первичных документов среди вложений не является основанием для `NOT_FOUND`.

Если интерфейс сначала показывает proposed research plan, это штатный этап до запуска, но не является итоговым результатом. План должен дословно перечислить все 7 `organizer_id` и названия из roster выше, подтвердить fingerprint `363b42de85a3204f54e542f4bee4e758967fb1ef98ad710f9425783e5d453a40`, публичный веб-поиск и ровно 84 targets. План без полного точного roster нельзя запускать. После запуска доведи исследование до полного отчёта.

## Источники и доказательства

1. Приоритет: точная официальная страница модели, затем официальный datasheet/manual/catalog PDF.
2. Страница авторизованного партнёра допустима только после безуспешного поиска официального источника; evidence должно также доказывать статус партнёра.
3. Маркетплейсы, агрегаторы, SEO-каталоги, форумы, соцсети и неподтверждённые пересказы не являются evidence.
4. Не угадывай URL, модель, ревизию, единицу или значение. Не объединяй разные модели, ревизии и конфигурации.
5. Для каждого verified/conflict/ambiguous field result добавь прямой `source_url`, title, publisher, точный locator/раздел/страницу, `publication_or_update_date` в `YYYY-MM-DD` или `null`, `accessed_at` в `YYYY-MM-DD` и короткий дословный `raw_value` не длиннее 20 слов.
6. Нормализуй только явно опубликованное значение. Не вычисляй производные характеристики и не подставляй типовые значения класса.
7. `known_facts_do_not_silently_overwrite` — контекст для сравнения. Не копируй его как новый факт. Доказанное расхождение возвращай как `CONFLICT` минимум с двумя evidence-записями, показывающими обе стороны.
8. `NOT_FOUND` допустим только после поиска точной модели и конкретного target на официальном сайте и в официальных PDF. Для него `normalized_value=null`, `normalized_unit=null`, `evidence=[]`; в `notes` кратко укажи, что именно было проверено.

## Правила статусов

- `EXACT_MODEL_MATCH`: точная модель/ревизия доказана.
- `EXACT_MODEL_MATCH_WITH_CONFLICTS`: точная identity доказана и есть хотя бы один `CONFLICT`.
- `AMBIGUOUS_MODEL_MATCH`: найдено несколько правдоподобных моделей/ревизий, но применимую нельзя доказать; не выбирай одну из них. Для ambiguous field result значение и unit должны быть `null`, а evidence должно показывать неоднозначность.
- `MODEL_NOT_FOUND`: после веб-поиска точная модель не найдена; target fields возвращаются как `NOT_FOUND`.
- `VERIFIED_OFFICIAL`: значение подтверждено официальным источником.
- `VERIFIED_AUTHORIZED_PARTNER`: официального источника нет, значение подтверждено доказанным авторизованным партнёром.
- `CONFLICT`: применимое единственное значение выбрать нельзя; `normalized_value` и `normalized_unit` должны быть `null`.

## Итоговый Markdown-отчёт

Верни результат непосредственно в теле одного итогового Markdown-отчёта. Не создавай отдельный JSON-файл, не используй `sandbox:/` и не делай полноту результата зависимой от временного файла.

Сначала дай краткую таблицу по 7 моделям: identity status, counts field statuses, conflicts и кликабельные source links. Затем выведи ровно один полный JSON-объект:

1. отдельная строка `CATALOG_RESULT_JSON_BEGIN`;
2. один fenced-блок, начинающийся строкой ```json;
3. полный JSON строго по `03-RETURN-SCHEMA-REQUIRED.json`;
4. закрывающая строка ```;
5. отдельная строка `CATALOG_RESULT_JSON_END`.

Внутри JSON запрещены Markdown-citations, комментарии, сокращения, `...` и дополнительные schema-поля. `batch_id` должен быть `deep-cleaning-01`; `research_completed_at` — валидный RFC 3339 date-time с timezone; каждый `organizer_id` должен присутствовать ровно один раз и без изменения.

## Completion gate

Не завершай итоговый отчёт, пока одновременно не выполнены все условия:

- публичный веб-поиск выполнен для каждой из 7 моделей;
- JSON синтаксически валиден и содержит ровно 7 model results и 84 field results;
- `batch_id`, все UUID, названия и targets сверены с жёстким roster выше; никаких других моделей в отчёте нет;
- результат проверен по batch-specific ограничениям `03-RETURN-SCHEMA-REQUIRED.json`, включая `const organizer_id` и exact per-model targets;
- состав `organizer_id` и `field_path` точно совпадает с batch;
- каждый verified/conflict/ambiguous result имеет требуемое evidence, каждый `NOT_FOUND` имеет пустое evidence;
- ни один факт не перенесён из known facts без нового допустимого evidence;
- итоговый JSON полностью находится между двумя маркерами в этом отчёте.
