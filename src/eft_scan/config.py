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


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_token: str
    cache_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Не задан TELEGRAM_BOT_TOKEN. Скопируйте .env.example в .env "
                "и укажите токен от @BotFather."
            )
        cache_dir = Path(os.getenv("EFT_SCAN_CACHE_DIR", ".cache")).resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cls(telegram_token=token, cache_dir=cache_dir)
