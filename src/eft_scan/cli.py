from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from eft_scan.client import TarkovClient
from eft_scan.format import format_player_card


async def lookup(nickname: str, game_mode: str, cache_dir: Path) -> None:
    client = TarkovClient(cache_dir)
    try:
        result = await client.lookup(nickname, game_mode)
        if result.not_found:
            print(f"Игрок {nickname} не найден в индексе {result.game_mode}.")
            return
        if result.matches:
            print("Совпадения:")
            for match in result.matches:
                mark = "exact" if match.exact else "approx"
                print(f"  [{mark}] {match.nickname} ({match.account_id})")
            return
        assert result.card is not None
        print(
            format_player_card(result.card)
            .replace("<b>", "")
            .replace("</b>", "")
            .replace("<i>", "")
            .replace("</i>", "")
            .replace('<a href="', "")
            .replace('">', " ")
            .replace("</a>", "")
        )
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Поиск игрока EFT без Telegram")
    parser.add_argument("nickname")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=("auto", "pvp-season", "regular", "pve", "arena"),
    )
    parser.add_argument("--cache", default=".cache")
    args = parser.parse_args()
    asyncio.run(lookup(args.nickname, args.mode, Path(args.cache)))


if __name__ == "__main__":
    main()
