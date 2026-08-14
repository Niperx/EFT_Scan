# EFT_Scan

Telegram-бот для просмотра статистики игрока Escape from Tarkov по нику. Данные берутся из публичных профилей [tarkov.dev](https://tarkov.dev/api/).

## Как пользоваться

В группе упомяните бота и укажите ник:

```
@ваш_бот Nikita
@ваш_бот pve Nikita
```

Команды:

- `/player Nikita` — PVP
- `/pve Nikita` — PVE
- `/start` — справка

В личке достаточно отправить ник.

Бот отвечает уровнем, фракцией, престижем, часами в игре, K/D и выживаемостью PMC/Scav, стриком и ссылкой на профиль.

## Ограничение данных

Живой поиск `player.tarkov.dev` закрыт Cloudflare Turnstile. Бот ищет ник в публичном индексе профилей, которые уже открывали на [tarkov.dev/players](https://tarkov.dev/players). Если игрока нет в индексе — откройте его профиль на сайте и повторите запрос (индекс обновляется примерно раз в сутки).

## Запуск

1. Создайте бота у [@BotFather](https://t.me/BotFather), получите токен.
2. В группе бот видит сообщения с упоминанием и команды — этого достаточно, privacy mode можно не отключать.
3. Скопируйте окружение и установите зависимости:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

В `.env` укажите `TELEGRAM_BOT_TOKEN`.

```bash
python -m eft_scan
```

Поиск без Telegram (проверка API):

```bash
PYTHONPATH=src python -m eft_scan.cli PoeBwo-TTV
```

Docker:

```bash
cp .env.example .env
docker compose up --build
```

## Тесты

```bash
pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=src pytest -q
```
