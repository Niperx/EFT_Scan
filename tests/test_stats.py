from __future__ import annotations

import json
from pathlib import Path

from eft_scan.stats import (
    build_player_card,
    load_player_levels,
    player_level,
    search_index,
)

FIXTURE = Path(__file__).parent / "fixtures" / "profile.json"


def _index():
    aid_to_name = {
        "15": "Buhaus",
        "6976458": "PoeBwo-TTV",
        "4598387": "PoeBwottv",
        "1": "Nikita",
        "2": "NikitaTTV",
    }
    name_to_aids: dict[str, list[str]] = {}
    for aid, name in aid_to_name.items():
        name_to_aids.setdefault(name.lower(), []).append(aid)
    return aid_to_name, sorted(name_to_aids), name_to_aids


def test_search_exact_and_prefix() -> None:
    aid_to_name, sorted_names, name_to_aids = _index()
    exact = search_index(aid_to_name, sorted_names, name_to_aids, "PoeBwo-TTV")
    assert len(exact) == 1
    assert exact[0].account_id == "6976458"
    assert exact[0].exact

    by_id = search_index(aid_to_name, sorted_names, name_to_aids, "6976458")
    assert by_id[0].nickname == "PoeBwo-TTV"

    prefix = search_index(aid_to_name, sorted_names, name_to_aids, "Nik")
    names = {item.nickname for item in prefix}
    assert names == {"Nikita", "NikitaTTV"}


def test_search_case_insensitive() -> None:
    aid_to_name, sorted_names, name_to_aids = _index()
    matches = search_index(aid_to_name, sorted_names, name_to_aids, "poebwo-ttv")
    assert matches[0].account_id == "6976458"


def test_player_level_from_bundled_table() -> None:
    levels = load_player_levels()
    level, badge = player_level(0, levels)
    assert level == 1
    level, badge = player_level(1000, levels)
    assert level == 2
    high, _ = player_level(999_999_999, levels)
    assert high == 79


def test_build_player_card() -> None:
    profile = json.loads(FIXTURE.read_text(encoding="utf-8"))
    card = build_player_card(profile, game_mode="regular", levels=load_player_levels())
    assert card.nickname == "PoeBwo-TTV"
    assert card.side == "Bear"
    assert card.prestige == 6
    assert "EOD" in card.editions
    assert "Unheard" in card.editions
    assert card.pmc.raids == 5055
    assert card.pmc.survived == 2003
    assert card.pmc.kills == 26011
    assert card.pmc.kd_label == "9.46"
    assert card.pmc.pmc_kd_label == "2.30"
    assert card.pmc.pmc_kills == 6317
    assert card.level == 71
    assert card.scav.raids == 5
    assert card.achievements == 2
    assert card.hours_played == 14822
    assert card.profile_url.endswith("/regular/6976458")
    assert card.last_active is not None


def test_build_arena_card() -> None:
    profile = json.loads((Path(__file__).parent / "fixtures" / "arena.json").read_text(encoding="utf-8"))
    card = build_player_card(profile, game_mode="arena", levels=load_player_levels())
    assert card.nickname == "PoeBwo-TTV"
    assert card.arena is not None
    assert card.arena.games == 221
    assert card.arena.wins == 113
    assert card.arena.kills == 6058
    assert card.arena.best_arp == 2025
    assert card.arena.kd_label == "1.35"
    names = {line.name for line in card.arena.modes}
    assert "Last Hero" in names
    assert card.hours_played == 652
    assert card.portrait_data is not None
    assert card.profile_url.endswith("/arena/6976458")
