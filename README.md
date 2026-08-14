# EFT_Scan

Telegram-бот для статистики игрока Escape from Tarkov по нику. Данные — [tarkov.dev](https://tarkov.dev/api/).

В группе: `@бот Nikita` или `@бот pve Nikita`. Команды: `/player Nikita`, `/pve Nikita`.

## Токен с телефона — куда класть

Токен от [@BotFather](https://t.me/BotFather) — это пароль бота. Его **нельзя** присылать в GitHub, в Issue, в этот чат и в README.

С телефона:

1. В Telegram откройте [@BotFather](https://t.me/BotFather) → `/mybots` → ваш бот → **API Token** → скопируйте.
2. Вставьте токен **только** в переменную `TELEGRAM_BOT_TOKEN` на хостинге (шаги ниже). Не в код и не в коммит.

Я не могу крутить бота 24/7 на этой облачной машине: она гаснет вместе с задачей. Бесплатный хостинг — это Render.

## Бесплатный запуск на Render (с телефона)

Бесплатный веб-сервис Render: 512 МБ RAM, HTTPS, деплой из GitHub. Раз в 15 минут без запросов сервис засыпает; первое сообщение после сна может идти около минуты (пока Render будит контейнер). Пока ботом пользуются, он отвечает сразу.

1. Зайдите на [render.com](https://render.com) с телефона → **Sign up / Log in** через GitHub и разрешите доступ к репозиторию `Niperx/EFT_Scan`.
2. **New** → **Blueprint** (или **Web Service**).
3. Выберите репозиторий `EFT_Scan`. Ветку — `main` после мержа, либо текущую `cursor/telegram-player-bot-b21b`.
4. Runtime: **Docker**. Команда запуска уже в Dockerfile: `python -m eft_scan`.
5. **Environment** → Add: имя `TELEGRAM_BOT_TOKEN`, значение — токен из BotFather. Вставьте и сохраните.
6. **Create Web Service** / **Apply**.
7. Дождитесь статуса **Live**. Откройте URL вида `https://….onrender.com/health` — должно быть `ok`.
8. В Telegram напишите боту `/start`.

Публичный URL Render подхватится сам (`RENDER_EXTERNAL_URL`), бот включит webhook.

### Чтобы реже засыпал

На [cron-job.org](https://cron-job.org) (бесплатно, с телефона) создайте задачу: раз в 10 минут GET на `https://ваш-сервис.onrender.com/health`. Тогда бот почти не спит. У Render лимит **750 бесплатных часов в месяц** — одного бота хватает на календарный месяц, если держать его включённым.

## Ограничение данных

Живой поиск на tarkov.dev закрыт Turnstile. Бот смотрит индекс профилей, которые уже открывали на [tarkov.dev/players](https://tarkov.dev/players).

## Локальный запуск (компьютер)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m eft_scan
```

Проверка API без Telegram:

```bash
PYTHONPATH=src python -m eft_scan.cli PoeBwo-TTV
```

## Тесты

```bash
pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=src pytest -q
```
