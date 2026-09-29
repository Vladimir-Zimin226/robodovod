# Исправление сборки frontend при выпуске продуктовой цепочки, 29.09.2026

Операторский лог для `7e4b5c72a4dcd8df7fd8bef40346476e67630552`
показал успешные push и checkout, затем ошибку `docker compose build backend frontend`:
Vite не нашёл `contracts/user-presentation-v3.json` и
`contracts/investor-presentation-versions-v1.json`. Команда завершилась до
`docker compose up`; в логе оба работающих контейнера ещё имели прежний возраст.

Причина: `frontend/Dockerfile` копировал в build stage только два конкретных
JSON-файла из `contracts/`, а новые импорты frontend требуют ещё два. Теперь
build stage копирует весь каталог `contracts/`; в финальный nginx-образ по-прежнему
попадает только собранный `dist`. Backend, методики расчётов, snapshots и данные
не менялись.

Регрессионный тест `frontend/tests/docker-build-context.test.mjs` сверяет внешние
относительные импорты frontend с `COPY` build stage. На старом Dockerfile он
падал на `investor-presentation-versions-v1.json`; после исправления проходит.
Также прошли 177 frontend-тестов, `eslint src tests` и локальная production-сборка
Vite (116 модулей). Docker Engine локально недоступен, поэтому реальная сборка
Docker-образа и production smoke остаются проверками оператора после push.
