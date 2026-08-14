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


class HealthHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "text/plain; charset=utf-8")
        self.write("ok")


class RootHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "text/plain; charset=utf-8")
        self.write("EFT_Scan bot is running")


class TelegramHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ("POST",)  # type: ignore[assignment]

    async def post(self) -> None:
        application: Application = self.settings["ptb"]
        payload = json.loads(self.request.body.decode() or "{}")
        update = Update.de_json(payload, application.bot)
        if update:
            await application.update_queue.put(update)
        self.set_status(200)
        self.write("ok")


def make_tornado_app(application: Application) -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r"/", RootHandler),
            (r"/health", HealthHandler),
            (r"/telegram", TelegramHandler),
        ],
        ptb=application,
    )


def run_webhook(application: Application, settings: Settings) -> None:
    webhook_url = f"{settings.webhook_url}/telegram"

    async def main() -> None:
        await application.initialize()
        if application.post_init:
            await application.post_init(application)
        await application.start()
        server = HTTPServer(make_tornado_app(application))
        server.listen(settings.port, address="0.0.0.0")
        await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
        logger.info("Webhook: %s (port %s)", webhook_url, settings.port)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass
        await stop.wait()
        server.stop()
        try:
            await application.bot.delete_webhook()
        except Exception:
            logger.warning("Не удалось снять webhook", exc_info=True)
        await application.stop()
        if application.post_shutdown:
            await application.post_shutdown(application)
        await application.shutdown()

    asyncio.run(main())
