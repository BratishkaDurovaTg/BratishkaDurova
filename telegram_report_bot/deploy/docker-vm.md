# Docker Deploy On VM

Ниже самый прямой сценарий для Version 2: бот и PostgreSQL поднимаются в Docker Compose на одной VM.

## 1. Установить Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

## 2. Залить проект на VM

```bash
mkdir -p ~/servicetex-bot
```

Скопируйте содержимое папки `telegram_report_bot` в `~/servicetex-bot`.

## 3. Настроить `.env`

Создайте или отредактируйте `~/servicetex-bot/.env`:

```env
TELEGRAM_BOT_TOKEN=ваш_бот_токен
ADMIN_USER_IDS=
POSTGRES_DB=servicetex
POSTGRES_USER=servicetex
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql://servicetex:change_me@localhost:5432/servicetex
REPORTS_XLSX_PATH=data/reports.xlsx
REPORT_TIMEZONE=Europe/Moscow
DEFAULT_LANGUAGE=ru
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

`DATABASE_URL` внутри контейнера будет автоматически переопределён на адрес сервиса `postgres`, так что строку выше можно оставить как понятный reference для локального запуска.

## 4. Поднять сервисы

```bash
cd ~/servicetex-bot
docker compose build
docker compose up -d
```

## 5. Проверить работу

```bash
docker compose ps
docker compose logs -f bot
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\dt"'
```

После первого старта бот сам:

- создаст таблицы `projects` и `reports`;
- импортирует данные из `data/reports.xlsx`, если база пустая;
- импортирует проекты из `data/projects.json`, если база пустая.

## 6. Полезные команды

```bash
cd ~/servicetex-bot
docker compose restart
docker compose down
docker compose up -d
docker compose logs -f bot postgres
```
