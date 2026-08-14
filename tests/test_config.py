from __future__ import annotations

import pytest

from eft_scan.config import Settings


def test_settings_require_token(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env()


def test_settings_detect_render_webhook(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("EFT_SCAN_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://eft-scan.onrender.com")
    settings = Settings.from_env()
    assert settings.use_webhook
    assert settings.port == 10000
    assert settings.webhook_url == "https://eft-scan.onrender.com"
