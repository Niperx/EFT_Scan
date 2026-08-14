from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

from eft_scan.config import HTTP_TIMEOUT, INDEX_REFRESH_SECONDS, JSON_API_ITEMS, PLAYERS_BASE, USER_AGENT
from eft_scan.stats import (
    PlayerCard,
    PlayerMatch,
    build_player_card,
    load_player_levels,
    search_index,
)

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

    def _index_cache_path(self, game_mode: str) -> Path:
        return self.cache_dir / f"index-{game_mode}.json"

    def _index_ready(self, game_mode: str) -> bool:
        packed = self._indexes.get(game_mode)
        if not packed:
            return False
        return (time.time() - packed["loaded_at"]) < INDEX_REFRESH_SECONDS

    def _rebuild_index(self, mapping: dict[str, str]) -> dict[str, Any]:
        aid_to_name = {str(aid): str(name) for aid, name in mapping.items()}
        name_to_aids: dict[str, list[str]] = defaultdict(list)
        for aid, name in aid_to_name.items():
            name_to_aids[name.lower()].append(aid)
        sorted_names = sorted(name_to_aids)
        return {
            "aid_to_name": aid_to_name,
            "name_to_aids": dict(name_to_aids),
            "sorted_names": sorted_names,
            "loaded_at": time.time(),
        }

    def invalidate_index(self, game_mode: str | None = None) -> None:
        if game_mode is None:
            for packed in self._indexes.values():
                packed["loaded_at"] = 0
            return
        packed = self._indexes.get(game_mode)
        if packed:
            packed["loaded_at"] = 0

    async def refresh_loaded_indexes(self) -> None:
        modes = list(self._indexes) or ["regular"]
        for mode in modes:
            await self.ensure_index(mode, force=True)

    async def ensure_index(self, game_mode: str = "regular", *, force: bool = False) -> dict[str, Any]:
        if not force and self._index_ready(game_mode):
            return self._indexes[game_mode]
        async with self._locks[game_mode]:
            if not force and self._index_ready(game_mode):
                return self._indexes[game_mode]
            cache_path = self._index_cache_path(game_mode)
            mapping: dict[str, str] | None = None
            cache_fresh = (
                cache_path.exists()
                and (time.time() - cache_path.stat().st_mtime) < INDEX_REFRESH_SECONDS
            )
            if not force and cache_fresh:
                mapping = await asyncio.to_thread(_read_json, cache_path)
            if mapping is None:
                folder = PROFILE_PATH.get(game_mode, game_mode)
                url = f"{PLAYERS_BASE}/{folder}/index.json"
                logger.info("Качаю индекс игроков %s: %s", game_mode, url)
                response = await self.http.get(url)
                response.raise_for_status()
                mapping = response.json()
                await asyncio.to_thread(_write_json, cache_path, mapping)
            packed = await asyncio.to_thread(self._rebuild_index, mapping)
            self._indexes[game_mode] = packed
            logger.info(
                "Индекс %s готов: %s игроков",
                game_mode,
                len(packed["aid_to_name"]),
            )
            return packed

    async def search(self, query: str, game_mode: str = "regular") -> list[PlayerMatch]:
        packed = await self.ensure_index(game_mode)
        return search_index(
            packed["aid_to_name"],
            packed["sorted_names"],
            packed["name_to_aids"],
            query,
        )

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


def _read_json(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
