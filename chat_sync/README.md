# Chat Sync

Django-приложение для синхронизации чатов Telegram Business с внешним API. Поддерживает два режима работы: пакетная синхронизация через Celery и real-time обновления через Telegram Webhook + WebSocket.

## Стек

- **Django 5** + Django REST Framework
- **Daphne** (ASGI) + Django Channels (WebSocket)
- **Celery** + Redis (фоновые задачи)
- **PostgreSQL** (основная БД)
- **DynamoDB** (хранение сообщений)
- **S3** (аватарки контактов)

## Структура проекта

```
chat_sync/
├── config/             # Настройки Django, Celery, ASGI
├── apps/
│   ├── chats/          # Модели (Deal, Customer), сериализаторы, WebSocket consumer
│   ├── sync/           # Пакетная синхронизация чатов (Celery-таски, сервисы)
│   └── telegram/       # Telegram webhook, обработчики, Celery-таски
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── manage.py
```

## API-эндпоинты

### Deals (чаты)

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/v1/deals/` | Список сделок (cursor-пагинация). Только полностью синхронизированные (customer + message сохранены) |
| GET | `/api/v1/deals/{id}/` | Детали сделки с сообщениями из DynamoDB |

### Sync (синхронизация)

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/v1/sync/start/` | Запустить Celery-задачу синхронизации. Тело: `{"max_date": "2025-01-01"}` (опционально) |
| GET | `/api/v1/sync/status/{task_id}/` | Статус задачи синхронизации |

### Telegram

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/telegram/webhook/` | Webhook для Telegram Bot API. Обрабатывает: `business_connection`, `business_message`, `edited_business_message`, `deleted_business_messages` |

### WebSocket

| URL | Описание |
|-----|----------|
| `ws/chats/{user_id}/` | Real-time обновления чатов |

### Admin

| URL | Описание |
|-----|----------|
| `/admin/` | Django Admin |

## Celery-задачи

| Задача | Описание |
|--------|----------|
| `sync_chats_task` | Пакетная синхронизация чатов из внешнего API. Распределённая блокировка, поддержка resume |
| `sync_read_status_to_telegram` | Отправка статуса прочтения в Telegram |
| `download_contact_avatar` | Загрузка аватарки контакта из Telegram в S3 |

## Запуск

### Docker (все сервисы)

```bash
docker-compose up --build
```

Будут запущены: PostgreSQL, Redis, Django (Daphne, порт 8000), Celery worker.

После запуска выполнить миграции:

```bash
docker-compose exec web python manage.py migrate
```

### Локальная разработка

1. Поднять инфраструктуру:

```bash
docker-compose up -d postgres redis
```

2. Установить зависимости:

```bash
pip install -r requirements.txt
```

3. Применить миграции:

```bash
python manage.py migrate
```

4. Запустить Django:

```bash
python manage.py runserver
```

5. Запустить Celery worker (отдельный терминал):

```bash
celery -A config worker -l info
```

6. (Опционально) Telegram polling:

```bash
python manage.py run_polling
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `POSTGRES_HOST` | `localhost` | Хост PostgreSQL |
| `POSTGRES_PORT` | `5432` | Порт PostgreSQL |
| `POSTGRES_DB` | `chat_sync` | Имя БД |
| `POSTGRES_USER` | `postgres` | Пользователь БД |
| `POSTGRES_PASSWORD` | `postgres` | Пароль БД |
| `REDIS_HOST` | `localhost` | Хост Redis |
| `REDIS_PORT` | `6379` | Порт Redis |
| `DEBUG` | `True` | Режим отладки |
| `USE_MOCK_SERVICES` | `True` | Моки для DynamoDB/S3 в dev-режиме |
| `TELEGRAM_BOT_TOKEN` | | Токен Telegram-бота |
| `TELEGRAM_WEBHOOK_SECRET` | | Секрет для валидации webhook |
| `TELEGRAM_WEBHOOK_URL` | | URL webhook для Telegram |
