from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

USER_AGENT = "EFT_Scan/1.0 (+https://github.com/Niperx/EFT_Scan)"
PLAYERS_BASE = "https://players.tarkov.dev"
JSON_API_ITEMS = "https://json.tarkov.dev/regular/items"
INDEX_REFRESH_SECONDS = 6 * 60 * 60
HTTP_TIMEOUT = 30.0
INDEX_DOWNLOAD_TIMEOUT = 120.0


def _public_base_url() -> str:
    for key in ("WEBHOOK_URL", "RENDER_EXTERNAL_URL"):
        value = os.getenv(key, "").strip().rstrip("/")
        if value:
            return value
    railway = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
    if railway:
        return railway if "://" in railway else f"https://{railway}"
    koyeb = os.getenv("KOYEB_PUBLIC_DOMAIN", "").strip().rstrip("/")
    if koyeb:
        return koyeb if "://" in koyeb else f"https://{koyeb}"
    return ""


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_token: str
    cache_dir: Path
    port: int
    webhook_url: str

    @property
    def use_webhook(self) -> bool:
        return bool(self.port and self.webhook_url)

    @classmethod
    def from_env(cls) -> Settings:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Не задан TELEGRAM_BOT_TOKEN. На хостинге добавьте переменную окружения, "
                "локально скопируйте .env.example в .env."
            )
        cache_dir = Path(os.getenv("EFT_SCAN_CACHE_DIR", ".cache")).resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        port_raw = os.getenv("PORT", "").strip()
        port = int(port_raw) if port_raw else 0
        return cls(
            telegram_token=token,
            cache_dir=cache_dir,
            port=port,
            webhook_url=_public_base_url(),
        )
