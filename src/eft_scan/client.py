from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

from eft_scan.config import (
    HTTP_TIMEOUT,
    INDEX_DOWNLOAD_TIMEOUT,
    INDEX_REFRESH_SECONDS,
    JSON_API_ITEMS,
    PLAYERS_BASE,
    USER_AGENT,
)
from eft_scan.index_store import json_to_sqlite, search_sqlite
from eft_scan.stats import PlayerCard, PlayerMatch, build_player_card, load_player_levels

logger = logging.getLogger(__name__)

PROFILE_PATH = {
    "regular": "profile",
    "pve": "pve",
}


class TarkovError(RuntimeError):
    pass


class TarkovClient:
    def __init__(self, cache_dir: Path, http: httpx.AsyncClient | None = None) -> None:
        self.cache_dir = cache_dir
        self._owns_http = http is None
        self.http = http or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
        )
        self.levels = load_player_levels()
        self._indexes: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def aclose(self) -> None:
        if self._owns_http:
            await self.http.aclose()

    async def warmup(self) -> None:
        try:
            await self.ensure_index("regular")
            await self.refresh_levels()
        except Exception:
            logger.exception("Не удалось прогреть индекс игроков")

    async def refresh_levels(self) -> None:
        try:
            response = await self.http.get(JSON_API_ITEMS)
            response.raise_for_status()
            payload = response.json()
            levels = ((payload.get("data") or {}).get("playerLevels")) or []
            if levels:
                self.levels = levels
                logger.info("Обновлена таблица уровней: %s записей", len(levels))
        except Exception:
            logger.warning("Не удалось обновить таблицу уровней, используем локальную", exc_info=True)

    def _sqlite_path(self, game_mode: str) -> Path:
        return self.cache_dir / f"index-{game_mode}.sqlite"

    def _json_path(self, game_mode: str) -> Path:
        return self.cache_dir / f"index-{game_mode}.json"

    def _index_ready(self, game_mode: str) -> bool:
        packed = self._indexes.get(game_mode)
        if not packed:
            return False
        path = Path(packed["sqlite"])
        if not path.exists():
            return False
        return (time.time() - packed["loaded_at"]) < INDEX_REFRESH_SECONDS

    def invalidate_index(self, game_mode: str | None = None) -> None:
        modes = list(self._indexes) if game_mode is None else [game_mode]
        for mode in modes:
            packed = self._indexes.get(mode)
            if packed:
                packed["loaded_at"] = 0

    async def refresh_loaded_indexes(self) -> None:
        modes = list(self._indexes) or ["regular"]
        for mode in modes:
            await self.ensure_index(mode, force=True)

    async def ensure_index(self, game_mode: str = "regular", *, force: bool = False) -> Path:
        if not force and self._index_ready(game_mode):
            return Path(self._indexes[game_mode]["sqlite"])
        async with self._locks[game_mode]:
            if not force and self._index_ready(game_mode):
                return Path(self._indexes[game_mode]["sqlite"])
            sqlite_path = self._sqlite_path(game_mode)
            json_path = self._json_path(game_mode)
            sqlite_fresh = (
                sqlite_path.exists()
                and (time.time() - sqlite_path.stat().st_mtime) < INDEX_REFRESH_SECONDS
            )
            if not force and sqlite_fresh:
                count = -1
            else:
                folder = PROFILE_PATH.get(game_mode, game_mode)
                url = f"{PLAYERS_BASE}/{folder}/index.json"
                logger.info("Качаю индекс игроков %s: %s", game_mode, url)
                await self._download_file(url, json_path)
                count = await asyncio.to_thread(json_to_sqlite, json_path, sqlite_path)
                try:
                    json_path.unlink()
                except OSError:
                    pass
            self._indexes[game_mode] = {
                "sqlite": sqlite_path,
                "loaded_at": time.time(),
            }
            logger.info("Индекс %s готов%s", game_mode, f": {count} игроков" if count >= 0 else "")
            return sqlite_path

    async def _download_file(self, url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = destination.with_suffix(destination.suffix + ".part")
        async with self.http.stream("GET", url, timeout=INDEX_DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            with tmp_path.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    handle.write(chunk)
        tmp_path.replace(destination)

    async def search(self, query: str, game_mode: str = "regular") -> list[PlayerMatch]:
        sqlite_path = await self.ensure_index(game_mode)
        return await asyncio.to_thread(search_sqlite, sqlite_path, query)

    async def get_profile(self, account_id: str, game_mode: str = "regular") -> dict[str, Any]:
        folder = PROFILE_PATH.get(game_mode, game_mode)
        url = f"{PLAYERS_BASE}/{folder}/{account_id}.json"
        response = await self.http.get(url)
        if response.status_code == 404:
            raise TarkovError("Профиль ещё не выгружен на tarkov.dev.")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("err"):
            raise TarkovError(str(payload.get("errmsg") or payload["err"]))
        return payload

    async def card_for_account(self, account_id: str, game_mode: str = "regular") -> PlayerCard:
        profile = await self.get_profile(account_id, game_mode)
        return build_player_card(profile, game_mode=game_mode, levels=self.levels)
