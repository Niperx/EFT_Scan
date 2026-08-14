from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
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
from eft_scan.format import format_mode_missing
from eft_scan.modes import MODE_ORDER, PROFILE_PATH, PVP, PVP_SEASON, lookup_order
from eft_scan.portrait import portrait_url, render_fallback_card, webp_to_jpeg
from eft_scan.stats import (
    PlayerCard,
    PlayerMatch,
    build_player_card,
    load_player_levels,
    pick_single_match,
)

logger = logging.getLogger(__name__)


class TarkovError(RuntimeError):
    pass


class ProfileMissingError(TarkovError):
    def __init__(self, game_mode: str) -> None:
        self.game_mode = game_mode
        super().__init__(format_mode_missing(game_mode))


@dataclass(frozen=True, slots=True)
class LookupResult:
    card: PlayerCard | None = None
    matches: tuple[PlayerMatch, ...] = ()
    game_mode: str = PVP_SEASON
    not_found: bool = False


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
        self._modes_cache: dict[str, tuple[float, tuple[str, ...]]] = {}

    async def aclose(self) -> None:
        if self._owns_http:
            await self.http.aclose()

    async def warmup(self) -> None:
        try:
            await self.ensure_index(PVP_SEASON)
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
        modes = list(self._indexes) or [PVP_SEASON]
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

    async def search(self, query: str, game_mode: str = PVP_SEASON) -> list[PlayerMatch]:
        sqlite_path = await self.ensure_index(game_mode)
        return await asyncio.to_thread(search_sqlite, sqlite_path, query)

    def _profile_url(self, account_id: str, game_mode: str) -> str:
        folder = PROFILE_PATH.get(game_mode, game_mode)
        return f"{PLAYERS_BASE}/{folder}/{account_id}.json"

    def _remember_mode(self, account_id: str, game_mode: str) -> None:
        packed = self._modes_cache.get(account_id)
        if not packed:
            return
        loaded_at, modes = packed
        if game_mode in modes:
            return
        merged = tuple(mode for mode in MODE_ORDER if mode in modes or mode == game_mode)
        self._modes_cache[account_id] = (loaded_at, merged)

    async def profile_exists(self, account_id: str, game_mode: str) -> bool:
        url = self._profile_url(account_id, game_mode)
        try:
            response = await self.http.head(url)
            if response.status_code in (403, 405, 501):
                response = await self.http.get(url, headers={"Range": "bytes=0-0"})
            return response.status_code in (200, 206)
        except httpx.HTTPError:
            logger.debug("Не удалось проверить профиль %s/%s", game_mode, account_id, exc_info=True)
            return False

    async def modes_for_account(self, account_id: str, *, force: bool = False) -> tuple[str, ...]:
        packed = self._modes_cache.get(account_id)
        if not force and packed and (time.time() - packed[0]) < 600:
            return packed[1]
        flags = await asyncio.gather(
            *(self.profile_exists(account_id, mode) for mode in MODE_ORDER)
        )
        modes = tuple(mode for mode, exists in zip(MODE_ORDER, flags, strict=True) if exists)
        self._modes_cache[account_id] = (time.time(), modes)
        return modes

    async def get_profile(self, account_id: str, game_mode: str = PVP_SEASON) -> dict[str, Any]:
        url = self._profile_url(account_id, game_mode)
        response = await self.http.get(url)
        if response.status_code == 404:
            raise ProfileMissingError(game_mode)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("err"):
            raise TarkovError(str(payload.get("errmsg") or payload["err"]))
        self._remember_mode(account_id, game_mode)
        return payload

    async def card_for_account(
        self,
        account_id: str,
        game_mode: str = PVP_SEASON,
        *,
        is_fallback: bool = False,
    ) -> PlayerCard:
        profile = await self.get_profile(account_id, game_mode)
        available = await self.modes_for_account(account_id)
        if game_mode not in available:
            available = (game_mode,) + available
        return build_player_card(
            profile,
            game_mode=game_mode,
            levels=self.levels,
            is_fallback=is_fallback,
            available_modes=available,
        )

    async def card_image(self, card: PlayerCard) -> bytes | None:
        if card.portrait_data:
            url = portrait_url(card.portrait_data)
            try:
                response = await self.http.get(
                    url,
                    headers={"Accept": "image/webp,image/jpeg,image/*,*/*;q=0.8"},
                    timeout=20.0,
                )
                if response.status_code == 200 and response.content:
                    content_type = response.headers.get("content-type", "")
                    if "jpeg" in content_type or "jpg" in content_type:
                        return response.content
                    return await asyncio.to_thread(webp_to_jpeg, response.content)
            except Exception:
                logger.info("Не удалось скачать портрет %s", card.account_id, exc_info=True)
        try:
            return await asyncio.to_thread(render_fallback_card, card)
        except Exception:
            logger.warning("Не удалось нарисовать карточку %s", card.account_id, exc_info=True)
            return None

    async def lookup(self, query: str, game_mode: str = "auto") -> LookupResult:
        modes = lookup_order(game_mode)
        season_missing = False
        for mode in modes:
            matches = await self.search(query, mode)
            if not matches:
                if mode == PVP_SEASON and game_mode == "auto":
                    season_missing = True
                continue
            chosen = pick_single_match(matches)
            if chosen is None:
                return LookupResult(matches=tuple(matches), game_mode=mode)
            try:
                card = await self.card_for_account(
                    chosen.account_id,
                    mode,
                    is_fallback=season_missing and mode == PVP,
                )
                return LookupResult(card=card, game_mode=mode)
            except TarkovError:
                if game_mode == "auto" and mode == PVP_SEASON:
                    season_missing = True
                    continue
                raise
        return LookupResult(not_found=True, game_mode=modes[-1])
