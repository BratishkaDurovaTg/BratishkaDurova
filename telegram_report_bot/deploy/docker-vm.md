# Docker Deploy On VM

Рекомендуемый вариант для `ask 4`: поднять на VM сразу весь стек:

- `postgres`
- `bot`
- `web`
- `caddy`

## 1. Проверить домен

Убедитесь, что субдомен уже указывает на VM:

```bash
ping servtex.duckdns.org
```

IP должен совпадать с VM:

- `188.130.155.158`

## 2. Установить Docker

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

## 3. Открыть порты

Если включён `ufw`:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

## 4. Залить проект на VM

```bash
mkdir -p ~/servicetex-bot
```

Скопируйте содержимое папки `telegram_report_bot` в `~/servicetex-bot`.

## 5. Настроить `.env`

Создайте или отредактируйте `~/servicetex-bot/.env`:

```env
TELEGRAM_BOT_TOKEN=ваш_бот_токен
TELEGRAM_BOT_USERNAME=ваш_username_бота_без_собаки
ADMIN_USER_IDS=
POSTGRES_DB=servicetex
POSTGRES_USER=servicetex
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql://servicetex:change_me@localhost:5432/servicetex
WEB_DOMAIN=servtex.duckdns.org
WEB_BASE_URL=https://servtex.duckdns.org
WEB_SESSION_SECRET=replace_me_with_a_long_random_secret
TELEGRAM_AUTH_MAX_AGE_SECONDS=86400
REPORTS_XLSX_PATH=data/reports.xlsx
REPORT_TIMEZONE=Europe/Moscow
DEFAULT_LANGUAGE=ru
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Важно:

- внутри `docker compose` переменная `DATABASE_URL` для `bot` и `web` будет автоматически переопределена на адрес контейнера `postgres`;
- значение `DATABASE_URL=...localhost...` остаётся удобным reference для локального запуска вне Docker.

## 6. Привязать домен к Telegram-боту

В `@BotFather`:

```text
/setdomain
servtex.duckdns.org
```

Без этого Telegram Login Widget не будет нормально авторизовывать пользователей на сайте.

## 7. Поднять сервисы

Если у вас до этого работал старый `systemd`-бот, сначала остановите его, чтобы не получить `409 Conflict`:

```bash
sudo systemctl stop servicetex-bot
sudo systemctl disable servicetex-bot
```

Потом:

```bash
cd ~/servicetex-bot
docker compose build
docker compose up -d
```

## 8. Проверить работу

```bash
cd ~/servicetex-bot
docker compose ps
docker compose logs -f bot web caddy postgres
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\dt"'
```

Ожидаемо:

- `caddy` раздаёт `https://servtex.duckdns.org`
- `web` отвечает через Caddy
- `bot` подключается к PostgreSQL
- в базе есть таблицы `projects` и `reports`

## 9. Проверить сайт

Откройте:

- [https://servtex.duckdns.org](https://servtex.duckdns.org)

Если всё хорошо:

- виден landing page ServiceTex
- работает Telegram login
- после входа открывается dashboard

## 10. Полезные команды

```bash
cd ~/servicetex-bot
docker compose restart
docker compose down
docker compose up -d
docker compose logs -f web
docker compose logs -f caddy
docker compose logs -f bot
```
