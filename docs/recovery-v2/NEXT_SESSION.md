# RECOVERY V2 — точка возобновления, 20.10.2026

Ветка `integration/evgeny-transfer-2026-10-19`, HEAD `46b9681`. Feature freeze. Не повторять большой аудит и уже успешно пройденные длительные E2E без изменения их кода.

## Что завершено в последнем проходе

- `529bc12`: 3 локальных PDF ×8 страниц на активированном опубликованном bundle; 24 рендера просмотрены, числа/статусы локализованы, графики не рвутся; 21/21 профильных тестов, совпадение вывода UI/PDF.
- `d28412b`: 60-секундный трейлер из 6 глав со встроенной музыкой заказчика AAC в web/master MP4; немой 18-секундный loop. Заказчик подтвердил права на музыку в чате. FFprobe, SHA manifest, desktop 1280 и mobile 390 browser Play со звуком/Mute/Unmute/seek PASS. `docs/recovery-v2/mux_trailer_music.py` воспроизводит монтаж после рендера; исходный WAV остаётся в `Разобрать/`.
- `46b9681`: убраны сырые технические статусы сцены. 3 локальных browser проверки на 360 px: склад/аэропорт/клиника, 3D/2D движение, пауза, без горизонтального overflow; `evidence/local-catalog-mobile-rc-360.json` и кадры.
- На отдельной локальной PostgreSQL БД `robodovod_rc_auth_20261020`: 4/4 теста регистрации, согласия, входа/выхода, CSRF и прав. Локальный каталог в `robodovod_recovery` активен в `capacity` и `discovery`, Alembic `0014_picking_project_runs`. Композиция WAV не включена в web-ассеты. Frontend build/ESLint PASS.
- Новые критерии заказчика: R4 `ACCEPTED_FOR_RC`; полный фотореализм больше не является релизным блокером. Не делать Blender-итерации без конкретного критического дефекта.

## Развёртывание пока не выполнено

`docs/recovery-v2/RELEASE_CANDIDATE_REPORT.md` содержит точный статус и rollback. `docker compose --env-file .env.production.example -f compose.yaml -f compose.production.yaml config --quiet` PASS; Docker daemon локально не запущен. В среде нет `.env.production`, проверенной SSH-цели и сведений о действующей версии сервера. Запрос `https://robodovod.ru/health` отсюда завершился тайм-аутом. Производственные backup/restore, migration, deploy и smoke не проводились. Кроме того, `frontend/public/privacy-policy.html` помечен проектом без реквизитов оператора; публичная регистрация требует утверждённого документа. У пользователя запрошены утверждённая политика/реквизиты и безопасный доступ к серверу либо решение выпустить без регистрации. Не трактовать отсутствие ответа как согласие.

## Следующее конкретное действие

1. Принять ответ пользователя по политике и серверу. Если предоставлен утверждённый текст — обновить документ и версию согласия, проверить auth и собрать frontend; если пользователь выбрал выпуск без регистрации — реализовать явное закрытие публичной регистрации с сохранением входа, проверить UX и API. Без этого не выпускать публичную регистрацию.
2. Если предоставлен доступ к серверу — выполнить read-only inventory по `docs/PRODUCTION_DEPLOYMENT.md`: commit, `docker compose ps`, Alembic, активные слоты каталога, env permissions без вывода секретов. Затем backup PostgreSQL+uploads, SHA и restore drill на отдельной БД. Только после совместимости выполнить build/migrate/traffic switch и production smoke. Не активировать runtime без подтверждённых паспортов.
3. Если доступ так и не предоставлен, оставить деплой BLOCKED; обновить `RELEASE_CANDIDATE_REPORT.md` и финальный статус. Не заявлять, что релиз находится на сервере.

## Рабочее дерево / службы

Перед следующим коммитом проверить `git status`. Существующие посторонние изменения не включать: `docs/recovery-v2/evidence/mobile-{390,768}-robcraft-build.png`, `docs/recovery-v2/evidence/trailer-player-clinic.png`, `docs/visual-polish/screenshots/07-robcraft-390.png`, `.tmp*`, `docs/handoff/*`, `docs/planning/*`, `reference-view/*`, `robcraft-motion-390-frame-{1,2}.png`. Также незакоммичены локально переснятые `local-catalog-1440-*-simulation.png` и `local-catalog-examples.json`; сохранять, не включать в релиз без отдельной проверки.

На момент записи локальный FastAPI 8001 использует только изолированную PostgreSQL 55432; Vite 4177 проксирует 8001; Edge CDP 9225. Эти процессы могут остановиться между сессиями. Ничего в production они не меняют.
