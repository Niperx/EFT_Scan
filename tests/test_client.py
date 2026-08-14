from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from eft_scan.client import TarkovClient

FIXTURE = Path(__file__).parent / "fixtures" / "profile.json"


@pytest.mark.asyncio
async def test_client_search_and_profile(tmp_path: Path) -> None:
    index = {"6976458": "PoeBwo-TTV", "1": "Nikita"}
    profile = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/profile/index.json"):
            return httpx.Response(200, json=index)
        if path.endswith("/profile/6976458.json"):
            return httpx.Response(200, json=profile)
        return httpx.Response(404, json={"err": "not found"})

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    client = TarkovClient(tmp_path, http=http)
    try:
        matches = await client.search("PoeBwo-TTV", "regular")
        assert matches[0].account_id == "6976458"
        card = await client.card_for_account("6976458", "regular")
        assert card.nickname == "PoeBwo-TTV"
        assert card.pmc.raids == 5055
        assert "regular" in card.available_modes
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
async def test_modes_for_account_skips_missing(tmp_path: Path) -> None:
    profile = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/profile/6976458.json") or path.endswith("/arena/6976458.json"):
            return httpx.Response(200, json=profile)
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TarkovClient(tmp_path / "modes", http=http)
    try:
        modes = await client.modes_for_account("6976458")
        assert modes == ("regular", "arena")
        card = await client.card_for_account("6976458", "regular")
        assert card.available_modes == ("regular", "arena")
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
async def test_missing_mode_raises_profile_missing(tmp_path: Path) -> None:
    from eft_scan.client import ProfileMissingError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TarkovClient(tmp_path / "missing", http=http)
    try:
        with pytest.raises(ProfileMissingError) as exc:
            await client.card_for_account("1", "pve")
        assert "PVE" in str(exc.value)
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
async def test_lookup_prefers_season_then_pvp(tmp_path: Path) -> None:
    season_index = {"6976458": "PoeBwo-TTV"}
    pvp_index = {"6976458": "PoeBwo-TTV"}
    profile = json.loads(FIXTURE.read_text(encoding="utf-8"))
    season_profile = json.loads(json.dumps(profile))
    season_profile["info"]["experience"] = 1000

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pvp-season/index.json"):
            return httpx.Response(200, json=season_index)
        if path.endswith("/pvp-season/6976458.json"):
            return httpx.Response(200, json=season_profile)
        if path.endswith("/profile/index.json"):
            return httpx.Response(200, json=pvp_index)
        if path.endswith("/profile/6976458.json"):
            return httpx.Response(200, json=profile)
        return httpx.Response(404, json={"err": "not found"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TarkovClient(tmp_path, http=http)
    try:
        result = await client.lookup("PoeBwo-TTV", "auto")
        assert result.card is not None
        assert result.card.game_mode == "pvp-season"
        assert result.card.is_fallback is False
        assert result.card.level == 2
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
async def test_lookup_falls_back_to_pvp(tmp_path: Path) -> None:
    pvp_index = {"6976458": "PoeBwo-TTV"}
    profile = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pvp-season/index.json"):
            return httpx.Response(200, json={})
        if path.endswith("/profile/index.json"):
            return httpx.Response(200, json=pvp_index)
        if path.endswith("/profile/6976458.json"):
            return httpx.Response(200, json=profile)
        return httpx.Response(404, json={"err": "not found"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TarkovClient(tmp_path / "fallback", http=http)
    try:
        result = await client.lookup("PoeBwo-TTV", "auto")
        assert result.card is not None
        assert result.card.game_mode == "regular"
        assert result.card.is_fallback is True
    finally:
        await client.aclose()
        await http.aclose()
