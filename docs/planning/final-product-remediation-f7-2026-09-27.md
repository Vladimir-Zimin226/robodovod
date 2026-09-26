# F7 — иконка RD и навигация

**Выполнено локально 27.09.2026; production не обновлялся.**

Прежний фиолетовый знак заменён на простой контрастный `RD` в
[SVG](../../frontend/public/favicon.svg). Подготовлены [PNG 32 px](../../frontend/public/favicon-32.png)
и [ICO 16/32/48/64 px](../../frontend/public/favicon.ico), собираемые
воспроизводимым [скриптом](../../scripts/build_f7_favicon.py). При просмотре
16/32 px буквы читаются ([образец на светлом и тёмном фоне](assets/f7/icon-16-32-light-dark.png)); тёмная подложка с белыми буквами и светлой рамкой
различима на светлой и тёмной вкладке. `frontend/index.html` указывает все
три формата, сохраняет заголовок и `theme-color=#0a1217`. Production Vite
сборка содержит файлы по корневым путям; `frontend/nginx.conf` раздаёт их
из `/usr/share/nginx/html`, Dockerfile копирует туда `dist`.

Страницы «Шаблоны и загрузка данных» и «Библиотека решений» сгруппированы
в меню проекта; «Каталог и источники» и «Пользователи» — в отдельном меню,
которое видит только ADMIN. Активные пункты отмечены и доступны с клавиатуры;
мобильное меню прокручивается, а название приложения не перекрывает кнопку
закрытия. Прямой `#admin-catalog` без прав показывает объяснение и путь к
учётной записи. Выбранный проект восстанавливается из принадлежащего
пользователю списка через прежний scoped sessionStorage; смена hash, Back
и reload его не сбрасывают.

[Браузерное свидетельство](assets/f7/report.json) получено на production Vite
build с синтетическими ответами read-only API: Chrome и Edge, 1366×768 и
390×844. Оба браузера прошли прямую ссылку на шаблоны, переход через меню
на админский каталог, Back, reload, восстановление выбранного проекта и
объяснение отказа для USER. SVG/PNG/ICO вернули HTTP 200 с типом не `text/html`;
проверены title и theme color. Снимки:
[Chrome desktop](assets/f7/chrome-admin.png),
[Chrome mobile](assets/f7/chrome-mobile-menu.png),
[Edge desktop](assets/f7/edge-admin.png),
[Edge mobile](assets/f7/edge-mobile-menu.png).
Frontend: **135 passed**, lint и production build прошли. Серверные модели,
формулы, исторические immutable runs, их снимки/checksums и simulation
artifacts не изменялись.

Локальное воспроизведение из Windows CMD:

```cmd
python scripts\build_f7_favicon.py
cd frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 5177
```

В другом окне CMD из корня проекта:

```cmd
python scripts\browser_f7_navigation.py
```

Следующий этап F8 — только после новой команды пользователя.
