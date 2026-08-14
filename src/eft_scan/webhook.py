from __future__ import annotations

import asyncio
import json
import logging
import signal

import tornado.web
from telegram import Update
from telegram.ext import Application
from tornado.httpserver import HTTPServer

from eft_scan.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_UPDATES = ["message", "callback_query"]


class HealthHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ("GET", "HEAD")  # type: ignore[assignment]

    def get(self) -> None:
        self.set_header("Content-Type", "text/plain; charset=utf-8")
        self.write("ok")

    def head(self) -> None:
        self.set_status(200)


class RootHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ("GET", "HEAD")  # type: ignore[assignment]

    def get(self) -> None:
        self.set_header("Content-Type", "text/plain; charset=utf-8")
        self.write("EFT_Scan bot is running")

    def head(self) -> None:
        self.set_status(200)


class TelegramHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ("POST",)  # type: ignore[assignment]

    async def post(self) -> None:
        application: Application = self.settings["ptb"]
        try:
            payload = json.loads(self.request.body.decode() or "{}")
            update = Update.de_json(payload, application.bot)
            if update:
                await application.update_queue.put(update)
                logger.info("Webhook update %s", update.update_id)
        except Exception:
            logger.exception("Не удалось разобрать апдейт Telegram")
        self.set_status(200)
        self.write("ok")


def make_tornado_app(application: Application) -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r"/", RootHandler),
            (r"/health", HealthHandler),
            (r"/telegram/?", TelegramHandler),
        ],
        ptb=application,
    )


async def register_webhook(application: Application, webhook_url: str, *, drop_pending: bool = False) -> None:
    await application.bot.set_webhook(
        url=webhook_url,
        allowed_updates=ALLOWED_UPDATES,
        drop_pending_updates=drop_pending,
    )
    logger.info("Webhook зарегистрирован: %s", webhook_url)


def run_webhook(application: Application, settings: Settings) -> None:
    webhook_url = f"{settings.webhook_url}/telegram"
    application.bot_data["webhook_url"] = webhook_url

    async def main() -> None:
        await application.initialize()
        if application.post_init:
            await application.post_init(application)
        await application.start()
        server = HTTPServer(make_tornado_app(application))
        server.listen(settings.port, address="0.0.0.0")
        await register_webhook(application, webhook_url)
        logger.info("Слушаю 0.0.0.0:%s", settings.port)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass
        await stop.wait()
        server.stop()
        # Не вызываем deleteWebhook: при деплое старый контейнер иначе
        # сбрасывает URL, и Telegram перестаёт слать апдейты.
        await application.stop()
        if application.post_shutdown:
            await application.post_shutdown(application)
        await application.shutdown()

    asyncio.run(main())
