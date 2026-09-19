# ChatGPT Deep Research handoff — runtime eligibility v1

Пакет предназначен для ручного запуска в веб-версии ChatGPT. Один batch — один отдельный Deep Research chat.

## Что загружать

Для каждого запуска откройте готовую папку `upload/<batch-id>/` и приложите из неё ровно три файла:

1. `01-BATCH-<batch-id>.json`;
2. `02-RUNTIME-CONTRACT.json`;
3. `03-RETURN-SCHEMA-REQUIRED.json`.

Не загружайте `contracts/runtime-eligibility-contract-v1.schema.json`: это schema runtime-контракта, а не schema результата исследования. Нужный третий файл всегда имеет имя `03-RETURN-SCHEMA-REQUIRED.json` и уже лежит в готовой upload-папке.

Полный 424-KB audit report, исходные restricted PDF/XLSX/DOCX и локальный `.env` загружать не нужно. Batch уже содержит необходимый локальный контекст, stable IDs, known facts, conflicts и ранее известные URL.

## Порядок запуска

1. Откройте новый chat в ChatGPT и выберите **Deep Research** в меню инструментов.
2. Загрузите три JSON-файла из `upload/<batch-id>/`.
3. Откройте `upload/<batch-id>/COPY-PASTE-PROMPT.md` и целиком скопируйте его в chat. Batch ID уже подставлен.
4. В источниках оставьте public web и загруженные файлы; подключать Apps не требуется. Не ограничивайте поиск одним доменом: prompt уже требует приоритет официальных источников.
5. Запустите исследование. Prompt требует выполнить весь batch сразу и запрещает останавливаться ради подтверждения плана. Не объединяйте batch-файлы в один chat.
6. Скачайте итоговый отчёт в Markdown и положите без ручного редактирования в `returns/`. Имя скачанного `.md` не важно: batch определяется из встроенного JSON.
7. После всех запусков извлеките JSON локально или передайте каталог `returns/` обратно Codex с запросом: «Извлеки и провалидируй Deep Research returns, построй evidence review и не импортируй ничего без явного подтверждения».

Веб-интерфейс ChatGPT может независимо от текста prompt показать системный proposed research plan до начала поиска. Это штатный этап интерфейса. Сверьте не только количество: план обязан перечислять все UUID и названия из раздела «Жёсткая блокировка scope» и тот же scope fingerprint. Если хотя бы одна модель заменена, не запускайте исследование. При полном совпадении нажмите запуск/подтверждение в том же chat.

Локальная строгая проверка полного комплекта перед передачей:

```powershell
./.venv/Scripts/python.exe -m scripts.extract_catalog_deep_research_reports --reports-dir data/research/catalog-runtime-eligibility-v1/returns --require-complete
```

Extractor требует полный JSON-блок между маркерами `CATALOG_RESULT_JSON_BEGIN/END`, создаёт `<batch-id>.result.json` и сразу выполняет schema/coverage-проверку.

После extraction постройте только staging/review-отчёт (без импорта в catalog/runtime):

```powershell
./.venv/Scripts/python.exe -m scripts.review_catalog_deep_research_returns --returns-dir data/research/catalog-runtime-eligibility-v1/returns --require-complete
```

Проверить целостность всех шести исходных пакетов независимо от результатов:

```powershell
./.venv/Scripts/python.exe -m scripts.audit_catalog_deep_research_packets
```

Если ChatGPT остановился на плане, не создавайте новый chat. Убедитесь, что приложен `03-RETURN-SCHEMA-REQUIRED.json`, затем отправьте в том же chat содержимое `upload/<batch-id>/RECOVERY-CURRENT-CHAT.md`.

## Batch-порядок

1. `deep-mobile-01` — 10 transport моделей.
2. `deep-mobile-02` — 10 transport моделей.
3. `deep-cleaning-01` — 7 cleaning моделей.
4. `deep-cleaning-02` — 6 cleaning моделей.
5. `deep-other-01` — 2 palletizing + 1 delivery модель.
6. `hybrid-conflicts-01` — 5 конфликтных моделей.

Итого: 36 `DEEP_RESEARCH` + 5 `HYBRID` model identities. Позиции не склеиваются: каждый batch содержит связанные `position_ids`.
