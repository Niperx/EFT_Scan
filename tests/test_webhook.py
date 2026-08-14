from __future__ import annotations

from unittest.mock import MagicMock

from eft_scan.webhook import HealthHandler, RootHandler, TelegramHandler, make_tornado_app


def test_webhook_handlers_support_expected_methods() -> None:
    application = MagicMock()
    tornado_app = make_tornado_app(application)
    assert tornado_app.settings["ptb"] is application
    assert "HEAD" in HealthHandler.SUPPORTED_METHODS
    assert "HEAD" in RootHandler.SUPPORTED_METHODS
    assert "POST" in TelegramHandler.SUPPORTED_METHODS
