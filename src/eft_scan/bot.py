from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from eft_scan.client import TarkovClient
from eft_scan.commands import BOT_COMMANDS
from eft_scan.config import INDEX_REFRESH_SECONDS, Settings
from eft_scan.handlers import help_command, mention_or_private, pick_player, player_command, start
from eft_scan.webhook import ALLOWED_UPDATES, register_webhook, run_webhook

logger = logging.getLogger(__name__)


async def _post_init(application: Application) -> None:
    client: TarkovClient = application.bot_data["tarkov"]
    asyncio.create_task(client.warmup(), name="tarkov-warmup")
    try:
        await application.bot.set_my_commands(list(BOT_COMMANDS))
        logger.info("Меню команд обновлено (%s)", len(BOT_COMMANDS))
    except Exception:
        logger.exception("Не удалось установить команды бота")
    me = await application.bot.get_me()
    logger.info("Бот @%s готов", me.username)


async def _post_shutdown(application: Application) -> None:
    client: TarkovClient = application.bot_data.get("tarkov")
    if client:
        await client.aclose()


async def _refresh_indexes(context) -> None:
    client: TarkovClient = context.application.bot_data["tarkov"]
    try:
        await client.refresh_loaded_indexes()
    except Exception:
        logger.exception("Не удалось обновить индекс игроков")


async def _ensure_webhook(context) -> None:
    url = context.application.bot_data.get("webhook_url")
    if not url:
        return
    try:
        info = await context.bot.get_webhook_info()
        if info.url == url:
            return
        logger.warning("Webhook сброшен (%r), ставлю снова %s", info.url, url)
        await register_webhook(context.application, url)
    except Exception:
        logger.exception("Не удалось проверить webhook")


def build_application(settings: Settings) -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.bot_data["tarkov"] = TarkovClient(settings.cache_dir)
    if settings.webhook_url:
        application.bot_data["webhook_url"] = f"{settings.webhook_url}/telegram"
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        CommandHandler(["player", "pvp", "regular", "pve", "season", "arena"], player_command)
    )
    application.add_handler(CallbackQueryHandler(pick_player, pattern=r"^p:"))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, mention_or_private),
    )
    if application.job_queue is not None:
        application.job_queue.run_repeating(
            _refresh_indexes,
            interval=INDEX_REFRESH_SECONDS,
            first=INDEX_REFRESH_SECONDS,
            name="refresh-player-index",
        )
        if settings.use_webhook:
            application.job_queue.run_repeating(
                _ensure_webhook,
                interval=120,
                first=20,
                name="ensure-webhook",
            )
    return application


def run() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    application = build_application(settings)
    if settings.use_webhook:
        logger.info("Запускаю webhook")
        run_webhook(application, settings)
        return
    logger.info("Запускаю long polling")
    application.run_polling(allowed_updates=ALLOWED_UPDATES)
