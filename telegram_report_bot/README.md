# ServiceTex Control Center

Мини-система для ежедневных отчётов команды: Telegram-бот принимает голосовые отчёты, а веб-приложение показывает dashboard, проекты и админ-сводку.

Проект теперь состоит из:

- Telegram bot для отправки отчётов;
- web app с авторизацией через Telegram Login Widget;
- PostgreSQL как основного хранилища;
- Docker Compose для `bot + web + postgres + caddy`;
- публичного HTTPS-деплоя на VM.

## Что умеет система

- сотрудник выбирает проект в Telegram;
- отправляет голосовое сообщение;
- бот расшифровывает аудио через `faster-whisper`;
- пытается выделить `Факт за сегодня` и `План на завтра`;
- сохраняет результат в PostgreSQL;
- web app показывает:
  - dashboard с проектами;
  - личные последние отчёты;
  - страницу проекта;
  - admin view с глобальной сводкой.

## Web App

Веб-интерфейс сделан в тёмной стилистике, вдохновлённой `belfort.app`, но адаптирован под ServiceTex.

Внутри web app есть:

- landing page;
- login через Telegram;
- dashboard;
- project pages;
- admin screen.

Брендинг:

- `ServiceTex`
- `project by @BratishkaDurova`

## Технологии

- Python 3.11+
- `python-telegram-bot`
- `FastAPI`
- `Jinja2`
- `PostgreSQL`
- `Caddy`
- `Docker Compose`

## Быстрый старт локально

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Минимальные переменные:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_USERNAME=your_bot_username
DATABASE_URL=postgresql://servicetex:change_me@localhost:5432/servicetex
WEB_DOMAIN=servtex.duckdns.org
WEB_BASE_URL=https://servtex.duckdns.org
WEB_SESSION_SECRET=replace_me_with_a_long_random_secret
ADMIN_USER_IDS=
```

Если `ADMIN_USER_IDS` пустой, админ-доступ открыт любому аккаунту, который знает `/admin` и авторизуется в web app.

## Запуск локально

Бот:

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
source .venv/bin/activate
python main.py
```

Web app:

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
source .venv/bin/activate
uvicorn employee_report_bot.web:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

Или через `Makefile`:

```bash
make run-web
```

## Telegram Login

Для входа в web app используется официальный `Telegram Login Widget`.

Нужно:

1. Указать `TELEGRAM_BOT_USERNAME`.
2. Поднять публичный `HTTPS` URL.
3. Привязать домен к боту через `@BotFather`:

```text
/setdomain
servtex.duckdns.org
```

После этого landing page сможет логинить пользователя через Telegram и создавать web session.

## Docker Compose

В `docker-compose.yml` поднимаются четыре сервиса:

- `postgres`
- `bot`
- `web`
- `caddy`

Запуск:

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
docker compose build
docker compose up -d
```

Проверка:

```bash
docker compose ps
docker compose logs -f bot web caddy postgres
```

## Public Deploy

Текущий публичный домен в конфиге:

- `servtex.duckdns.org`

Для production-деплоя нужно:

- чтобы `servtex.duckdns.org` указывал на IP VM;
- чтобы были открыты порты `80` и `443`;
- чтобы `Caddy` смог получить сертификат.

Подробный сценарий:

- [docker-vm.md](/Users/nikita/BratishkaDurova/telegram_report_bot/deploy/docker-vm.md)

## Хранилище данных

Основной источник данных:

- PostgreSQL

Дополнительные зеркала на диске:

- [reports.xlsx](/Users/nikita/BratishkaDurova/telegram_report_bot/data/reports.xlsx)
- [projects.json](/Users/nikita/BratishkaDurova/telegram_report_bot/data/projects.json)

## Полезные команды

Тесты:

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
python3 -m unittest discover -s tests -v
```

Проверка синтаксиса:

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
python3 -m py_compile main.py employee_report_bot/*.py
```

Compose config:

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
docker compose config
```

## Структура

- [main.py](/Users/nikita/BratishkaDurova/telegram_report_bot/main.py) — запуск Telegram-бота
- [web.py](/Users/nikita/BratishkaDurova/telegram_report_bot/employee_report_bot/web.py) — FastAPI web app
- [telegram_auth.py](/Users/nikita/BratishkaDurova/telegram_report_bot/employee_report_bot/telegram_auth.py) — проверка Telegram login hash
- [postgres_store.py](/Users/nikita/BratishkaDurova/telegram_report_bot/employee_report_bot/postgres_store.py) — PostgreSQL storage
- [docker-compose.yml](/Users/nikita/BratishkaDurova/telegram_report_bot/docker-compose.yml) — bot/web/db/caddy
- [Caddyfile](/Users/nikita/BratishkaDurova/telegram_report_bot/Caddyfile) — публичный HTTPS reverse proxy
