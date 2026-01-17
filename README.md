# Telegram Userbot Parser (Telethon + SQLAlchemy)

Асинхронный Telegram-парсер (userbot), который анализирует сообщения в заданных чатах
за период и сохраняет активных пользователей в PostgreSQL.

## Возможности

- Поиск чатов по названию
- Анализ сообщений за период (по умолчанию 7 дней)
- Фильтрация ботов, удалённых пользователей и системных сообщений
- Сохранение активных пользователей (только имя и @username)
- Автоматическое создание таблиц при старте
- Логи в stdout

## Переменные окружения

Обязательные:

```
API_ID=
API_HASH=
SESSION_NAME=
TARGET_CHAT_NAMES=chat_one,chat_two
POSTGRES_HOST=
POSTGRES_PORT=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
```

Дополнительные:

```
ANALYSIS_DAYS=7
MIN_MESSAGES=100
```

Для инвайтера:

```
INVITE_TARGET_CHAT=
INVITES_PER_HOUR=2
INVITE_WINDOW_START=12
INVITE_WINDOW_END=19
INVITE_TIMEZONE=UTC
INVITE_IMMEDIATE_ON_START=true
```

## Запуск через Docker Compose

1. Создайте файл `.env` в корне проекта и заполните переменные окружения.
2. Первый запуск требует авторизации Telegram (код из SMS/Telegram).
   Для `docker-compose` обычно используйте `POSTGRES_HOST=postgres` и `POSTGRES_PORT=5432`.

Рекомендуемый поток:

```
docker compose run --rm parser
```

После успешной авторизации будет создана сессия в папке `./sessions`.
Далее запускайте обычным способом:

```
docker compose up --build
```

## Структура проекта

```
.
├── config/
│   ├── __init__.py
│   └── settings.py
├── db/
│   ├── __init__.py
│   ├── base.py
│   ├── models.py
│   └── session.py
├── parser/
│   ├── __init__.py
│   └── service.py
├── main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.inviter.yml
└── docker-compose.yml
```

## Локальные файлы БД

PostgreSQL хранит данные в папке `./postgres_data` (bind‑volume).

## Данные в БД

Таблица: `active_users`

Колонки:

- `username` (формат `@username`)
- `first_name`

Если раньше была таблица `active_user_stats`, её можно удалить вручную.

## Инвайтер

Инвайтер запускается отдельным compose и читает пользователей из таблицы
`active_users`, приглашая их в `INVITE_TARGET_CHAT`.

Перед запуском убедитесь, что основная сеть `telegram_default` создана
(она появляется после `docker compose up -d` основного проекта).

Запуск:

```
docker compose -f docker-compose.inviter.yml up -d --build
```

Логи:

```
docker compose -f docker-compose.inviter.yml logs -f inviter
```
