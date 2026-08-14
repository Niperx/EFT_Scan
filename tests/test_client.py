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
        matches = await client.search("PoeBwo-TTV")
        assert matches[0].account_id == "6976458"
        card = await client.card_for_account("6976458")
        assert card.nickname == "PoeBwo-TTV"
        assert card.pmc.raids == 5055
    finally:
        await client.aclose()
        await http.aclose()
