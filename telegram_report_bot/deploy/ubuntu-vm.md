# VM Deploy

Ниже старый вариант деплоя только для Telegram-бота через `systemd`.

Для `ask 4` и официального требования с web app используйте:

- [docker-vm.md](/Users/nikita/BratishkaDurova/telegram_report_bot/deploy/docker-vm.md)

Именно там описан рекомендуемый production-сценарий для:

- `bot`
- `web app`
- `postgres`
- `public HTTPS domain`

## 1. Подготовить VM

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg postgresql postgresql-contrib
```

## 2. Поднять PostgreSQL

Ниже пример с локальной базой на той же VM:

```bash
sudo -u postgres psql -c "CREATE USER servicetex WITH PASSWORD 'change_me';"
sudo -u postgres psql -c "CREATE DATABASE servicetex OWNER servicetex;"
```

Если пользователь или база уже существуют, просто пропустите этот шаг.

## 3. Залить проект на VM

В этом примере проект будет лежать в `/opt/servicetex-bot`.

```bash
sudo mkdir -p /opt/servicetex-bot
sudo chown -R $USER:$USER /opt/servicetex-bot
```

Скопируйте содержимое папки `telegram_report_bot` в `/opt/servicetex-bot`.

Через `scp` это может выглядеть так:

```bash
scp -r /Users/nikita/BratishkaDurova/telegram_report_bot/* user@your-vm:/opt/servicetex-bot/
```

Если деплоите из `git`, просто сделайте `git clone` в эту папку.

## 4. Создать окружение и установить зависимости

```bash
cd /opt/servicetex-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Настроить `.env`

Создайте файл `/opt/servicetex-bot/.env`:

```env
TELEGRAM_BOT_TOKEN=ваш_бот_токен
DATABASE_URL=postgresql://servicetex:change_me@localhost:5432/servicetex
ADMIN_USER_IDS=ваш_telegram_user_id
REPORTS_XLSX_PATH=data/reports.xlsx
REPORT_TIMEZONE=Europe/Moscow
DEFAULT_LANGUAGE=ru
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Если оставить `ADMIN_USER_IDS=` пустым, `/admin` будет открываться на любом аккаунте, который знает команду.

При первом запуске бот автоматически:

- создаст таблицы в PostgreSQL;
- импортирует старые данные из `data/reports.xlsx`, если база пока пустая;
- импортирует проекты из `data/projects.json`, если база пока пустая;
- продолжит поддерживать `reports.xlsx` и `projects.json` как зеркала данных на диске.

## 6. Проверить ручной запуск

```bash
cd /opt/servicetex-bot
source .venv/bin/activate
python main.py
```

Если в логах видите `Application started`, значит бот запускается нормально. Остановить можно через `Ctrl+C`.

## 7. Поднять через `systemd`

Скопируйте сервис:

```bash
sudo cp /opt/servicetex-bot/deploy/servicetex-bot.service /etc/systemd/system/servicetex-bot.service
```

Откройте сервис и проверьте два поля:

```bash
sudo nano /etc/systemd/system/servicetex-bot.service
```

Нужно заменить при необходимости:

- `User=ubuntu` на вашего пользователя VM
- `/opt/servicetex-bot` если выбрали другой путь

После этого:

```bash
sudo systemctl daemon-reload
sudo systemctl enable servicetex-bot
sudo systemctl start servicetex-bot
```

## 8. Проверить статус и логи

```bash
sudo systemctl status servicetex-bot
sudo journalctl -u servicetex-bot -f
```

## Что хранится на VM

- база данных PostgreSQL: основное хранилище
- отчёты: `/opt/servicetex-bot/data/reports.xlsx`
- список проектов: `/opt/servicetex-bot/data/projects.json`
- временные загрузки: `/opt/servicetex-bot/data/downloads/`

## Как обновлять код

Если вы обновили проект:

```bash
cd /opt/servicetex-bot
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart servicetex-bot
```

## Нюанс по распознаванию

При первом запуске модель `Whisper` может скачиваться дольше обычного. Это нормально.
