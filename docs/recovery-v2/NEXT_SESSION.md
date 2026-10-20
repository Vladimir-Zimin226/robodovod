# RECOVERY V2 — точка возобновления, 20.10.2026

Ветка `integration/evgeny-transfer-2026-10-19`; коммиты предыдущего прохода `529bc12`, `d28412b`, `46b9681`, `2e3940f`, `4534a65`. Текущий HEAD сверять `git log -1` после тематического коммита политики. Feature freeze. Не повторять большой аудит и уже успешно пройденные длительные E2E без изменения их кода.

## Что завершено в последнем проходе

- `529bc12`: 3 локальных PDF ×8 страниц на активированном опубликованном bundle; 24 рендера просмотрены, числа/статусы локализованы, графики не рвутся; 21/21 профильных тестов, совпадение вывода UI/PDF.
- `d28412b`: 60-секундный трейлер из 6 глав со встроенной музыкой заказчика AAC в web/master MP4; немой 18-секундный loop. Заказчик подтвердил права на музыку в чате. FFprobe, SHA manifest, desktop 1280 и mobile 390 browser Play со звуком/Mute/Unmute/seek PASS. `docs/recovery-v2/mux_trailer_music.py` воспроизводит монтаж после рендера; исходный WAV остаётся в `Разобрать/`.
- `46b9681`: убраны сырые технические статусы сцены. 3 локальных browser проверки на 360 px: склад/аэропорт/клиника, 3D/2D движение, пауза, без горизонтального overflow; `evidence/local-catalog-mobile-rc-360.json` и кадры.
- На отдельной локальной PostgreSQL БД `robodovod_rc_auth_20261020`: 4/4 теста регистрации, согласия, входа/выхода, CSRF и прав. Локальный каталог в `robodovod_recovery` активен в `capacity` и `discovery`, Alembic `0014_picking_project_runs`. Композиция WAV не включена в web-ассеты. Frontend build/ESLint PASS.
- Новые критерии заказчика: R4 `ACCEPTED_FOR_RC`; полный фотореализм больше не является релизным блокером. Не делать Blender-итерации без конкретного критического дефекта.
- В ответе заказчик предоставил реквизиты оператора ИП Зимин Владимир Андреевич и поручил использовать политику другого сервиса как основу. Обновлены `frontend/public/privacy-policy.html`, версия согласия в frontend/backend и профильные тесты; сделаны `docs/recovery-v2/SELF_DEPLOY_RC.md`, локальные auth/browser evidence. После изменения: 4/4 PostgreSQL auth tests, 2/2 privacy tests, frontend build/ESLint, браузер 390 и реальный локальный FastAPI register/consent/logout/login PASS. Заказчик сообщил, что деплой выполнит сам по инструкции.

## Развёртывание пока не выполнено

`docs/recovery-v2/RELEASE_CANDIDATE_REPORT.md` содержит точный статус и rollback. `docker compose --env-file .env.production.example -f compose.yaml -f compose.production.yaml config --quiet` PASS; Docker daemon локально не запущен. В среде нет `.env.production`, проверенной SSH-цели и сведений о действующей версии сервера. Запрос `https://robodovod.ru/health` отсюда завершился тайм-аутом. Производственные backup/restore, migration, deploy и smoke не проводились. Политика РОБОДОВОДА с реквизитами оператора подготовлена; применимость сообщённого номера уведомления Роскомнадзора 100293352 к этому сервису и фактическое размещение данных на production оператор должен проверить перед публикацией. Инструкция самостоятельного деплоя: `docs/recovery-v2/SELF_DEPLOY_RC.md`.

## Следующее конкретное действие

1. Зафиксировать тематический коммит политики/тестов/инструкции. Если remote доступен и разрешает обычный push, опубликовать ветку без force; сообщить точный SHA оператору.
2. Заказчик выполняет `SELF_DEPLOY_RC.md`: read-only inventory сервера, backup PostgreSQL+uploads и restore drill, затем build/migrate/обновление только при совместимости и production smoke. Перед запуском проверить сведения уведомления Роскомнадзора и размещение персональных данных. Не активировать runtime без подтверждённых паспортов.
3. После получения фактических результатов оператора записать deployed SHA, URL, каталог, миграцию, production smoke и rollback статус в `RELEASE_CANDIDATE_REPORT.md`. Пока ответа нет, оставлять production `BLOCKED`, не утверждать, что RC находится на сервере.

## Рабочее дерево / службы

Перед следующим коммитом проверить `git status`. Существующие посторонние изменения не включать: `docs/recovery-v2/evidence/mobile-{390,768}-robcraft-build.png`, `docs/recovery-v2/evidence/trailer-player-clinic.png`, `docs/visual-polish/screenshots/07-robcraft-390.png`, `.tmp*`, `docs/handoff/*`, `docs/planning/*`, `reference-view/*`, `robcraft-motion-390-frame-{1,2}.png`. Также незакоммичены локально переснятые `local-catalog-1440-*-simulation.png` и `local-catalog-examples.json`; сохранять, не включать в релиз без отдельной проверки.

На момент записи локальный FastAPI 8001 использует только изолированную PostgreSQL 55432; Vite 4177 проксирует 8001; Edge CDP 9225. Эти процессы могут остановиться между сессиями. Ничего в production они не меняют.
