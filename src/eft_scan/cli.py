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
        matches = await client.search(nickname, game_mode)
        if not matches:
            print(f"Игрок {nickname} не найден в индексе {game_mode}.")
            return
        print("Совпадения:")
        for match in matches:
            mark = "exact" if match.exact else "approx"
            print(f"  [{mark}] {match.nickname} ({match.account_id})")
        card = await client.card_for_account(matches[0].account_id, game_mode)
        print()
        print(format_player_card(card).replace("<b>", "").replace("</b>", "").replace("<a href=\"", "").replace("\">", " ").replace("</a>", ""))
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Поиск игрока EFT без Telegram")
    parser.add_argument("nickname")
    parser.add_argument("--mode", default="regular", choices=("regular", "pve"))
    parser.add_argument("--cache", default=".cache")
    args = parser.parse_args()
    asyncio.run(lookup(args.nickname, args.mode, Path(args.cache)))


if __name__ == "__main__":
    main()
