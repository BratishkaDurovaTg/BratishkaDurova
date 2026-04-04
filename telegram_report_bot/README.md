# Telegram Report Bot

Минимальный бесплатный Telegram-бот для учёта работы сотрудников через голосовые сообщения.

Что он делает:

- показывает меню-клавиатуру прямо в Telegram;
- даёт выбрать проект из общего списка;
- принимает голосовое сообщение или аудиофайл;
- расшифровывает речь локально через `faster-whisper`;
- пытается выделить `Факт за сегодня` и `План на завтра`;
- сохраняет результат в PostgreSQL или в Excel-файл `data/reports.xlsx` вместе с проектом;
- обновляет строку сотрудника за текущую дату, если он отправил отчёт повторно;
- даёт скрытую админ-панель через `/admin` с выбором проекта, добавлением нового проекта, сводкой, списком отчётов и Excel.

Version 2 уже включает:

- Telegram-админку вместо внешней панели;
- PostgreSQL как классическую БД;
- Docker Compose для бота и БД;
- CI-проверку для тестов и синтаксиса;
- деплой на VM.

## Как это работает

Рекомендуемый шаблон голосового отчёта:

```text
Факт за сегодня: закрыл задачу по сайту, созвонился с клиентом, отправил макеты.
План на завтра: доделать правки, проверить тестовый сервер, подготовить отчёт.
```

Если человек просто наговорит текст без явных маркеров, бот всё равно сохранит расшифровку, но точность разбиения на `Факт` и `План` будет ниже.

Перед отправкой отчёта сотрудник выбирает проект в меню бота.

## Что нужно для запуска

- Python 3.11+
- токен Telegram-бота от `@BotFather`
- интернет для первого запуска модели `Whisper`

`OpenAI API key` здесь не нужен.

## Установка

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

После этого откройте `.env` и вставьте токен бота:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
DATABASE_URL=postgresql://servicetex:change_me@localhost:5432/servicetex
ADMIN_USER_IDS=ваш_telegram_user_id
```

`ADMIN_USER_IDS` это числовой `user_id` администратора в Telegram. Если админов несколько, перечислите их через запятую. Если оставить значение пустым, `/admin` будет доступен любому аккаунту, который знает эту команду.

`DATABASE_URL` включает PostgreSQL-режим. Если переменную не задавать, бот продолжит работать по старому файловому сценарию через `data/reports.xlsx` и `data/projects.json`.

## Запуск

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
source .venv/bin/activate
python main.py
```

После первого запуска модель может немного скачиваться и инициализироваться.

## Быстрый Quality Check

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
python3 -m unittest discover -s tests -v
```

## Запуск на VM

Для деплоя на Ubuntu/Linux VM есть готовые файлы:

- [run_bot.sh](/Users/nikita/BratishkaDurova/telegram_report_bot/deploy/run_bot.sh)
- [servicetex-bot.service](/Users/nikita/BratishkaDurova/telegram_report_bot/deploy/servicetex-bot.service)
- [ubuntu-vm.md](/Users/nikita/BratishkaDurova/telegram_report_bot/deploy/ubuntu-vm.md)
- [docker-vm.md](/Users/nikita/BratishkaDurova/telegram_report_bot/deploy/docker-vm.md)

Рекомендуемый путь на сервере: `/opt/servicetex-bot` с запуском через `systemd`.

Для Version 2 рекомендованный вариант деплоя: `Docker Compose` с двумя сервисами:

- `bot`
- `postgres`

Локально это выглядит так:

```bash
cd /Users/nikita/BratishkaDurova/telegram_report_bot
docker compose up -d --build
```

## Что есть в меню бота

После `/start` бот показывает клавиатуру с действиями:

- `📁 Выбрать проект`
- `🎤 Отправить отчёт`
- `📌 Мой проект`
- `ℹ️ Помощь`

После выбора проекта бот ждёт голосовое сообщение и сохраняет:

- что сделано сегодня;
- что планируется завтра;
- к какому проекту относится отчёт.

## Что есть в админ-панели

Команда `/admin` открывает простую панель прямо в Telegram. В ней доступны:

- `Выбрать проект`
- `Добавить проект`
- `Сводка за сегодня`
- `Список отчётов`
- `Скачать Excel по выбранному проекту`

Добавление проекта сделано максимально просто: админ нажимает кнопку добавления, отправляет код проекта обычным сообщением, и проект сразу появляется в пользовательском меню и в админке.

Команда не рекламируется обычным пользователям, но админ по-прежнему может открыть её вручную.

То есть TA можно показать именно Telegram-админку. Если включён PostgreSQL, Excel и JSON остаются зеркалом данных на диске для экспорта и удобной проверки.

## Где лежат данные

- PostgreSQL: данные отчётов и проектов, если задан `DATABASE_URL`
- Excel-файл: `/Users/nikita/BratishkaDurova/telegram_report_bot/data/reports.xlsx`
- список проектов: `/Users/nikita/BratishkaDurova/telegram_report_bot/data/projects.json`
- временные аудиофайлы: `/Users/nikita/BratishkaDurova/telegram_report_bot/data/downloads/`

## Полезные настройки

Файл `.env` поддерживает такие параметры:

```env
POSTGRES_DB=servicetex
POSTGRES_USER=servicetex
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql://servicetex:change_me@localhost:5432/servicetex
ADMIN_USER_IDS=
REPORTS_XLSX_PATH=data/reports.xlsx
REPORT_TIMEZONE=Europe/Moscow
DEFAULT_LANGUAGE=ru
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Практичные значения:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` для Docker Compose и VM
- `DATABASE_URL=...` если хотите классическую серверную БД на PostgreSQL
- `WHISPER_MODEL=small` для лучшего качества
- `WHISPER_MODEL=base` если нужен более быстрый запуск на слабом ноутбуке
- `REPORT_TIMEZONE=Europe/Moscow` чтобы дата отчёта совпадала с вашим рабочим днём

## Ограничения

- Бот должен где-то постоянно работать, если нужен режим `24/7`.
- Расшифровка полностью локальная, поэтому скорость зависит от вашего компьютера.
- Боты Telegram не работают с `secret chats`.

## Структура Version 2

- [Dockerfile](/Users/nikita/BratishkaDurova/telegram_report_bot/Dockerfile) для контейнера бота
- [docker-compose.yml](/Users/nikita/BratishkaDurova/telegram_report_bot/docker-compose.yml) для бота и PostgreSQL
- [postgres_store.py](/Users/nikita/BratishkaDurova/telegram_report_bot/employee_report_bot/postgres_store.py) для хранения в БД
- [tests](/Users/nikita/BratishkaDurova/telegram_report_bot/tests) для базовой автоматической проверки
