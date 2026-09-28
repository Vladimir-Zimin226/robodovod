# Быстрый запуск

Команды выполняются из корня репозитория. Нужен Docker Desktop с запущенным Docker Engine. Подробности о компонентах — в [архитектуре](ARCHITECTURE.md), о работе в интерфейсе — в [руководстве](USER_GUIDE.md).

1. Создайте локальный `.env` из [шаблона](../.env.example) и замените все значения `<...>`. Для полного Compose `DATABASE_URL` должен указывать на host `db`. Пароль в URL кодируется; `POSTGRES_ADMIN_USER` и `APP_DB_USER` должны быть разными пользователями.
2. Поднимите сервисы и дождитесь готовности БД и миграций:

   ```cmd
   copy .env.example .env
   docker compose up --build -d
   docker compose ps
   curl.exe -f http://localhost:8000/ready
   ```

3. Откройте интерфейс на <http://localhost:5173>. API доступен на <http://localhost:8000>, интерактивная схема — на <http://localhost:8000/docs>. Первый запуск на пустой БД требует подготовки и активации runtime-каталога; порядок и команды описаны в [корневом README](../README.md#catalog-validatorimporter).

`docker compose down` останавливает сервисы и сохраняет named volume PostgreSQL. Команда с `-v` удаляет volume с данными. Секреты в `.env` не коммитьте.

Без Docker нужны Python 3.12+, Node.js 22.12+ и PostgreSQL 16. Пошаговые команды для Git Bash и PowerShell приведены в [корневом README](../README.md#локальный-запуск-без-docker). Production-окружение описано отдельно в [runbook](PRODUCTION_DEPLOYMENT.md).
