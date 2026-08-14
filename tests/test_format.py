from __future__ import annotations

import json
from pathlib import Path

from eft_scan.format import format_help, format_not_found, format_player_card
from eft_scan.stats import build_player_card, load_player_levels

FIXTURE = Path(__file__).parent / "fixtures" / "profile.json"


def test_format_player_card_contains_core_stats() -> None:
    profile = json.loads(FIXTURE.read_text(encoding="utf-8"))
    card = build_player_card(profile, game_mode="regular", levels=load_player_levels())
    text = format_player_card(card)
    assert "PoeBwo-TTV" in text
    assert "ур." in text
    assert "престиж 6" in text
    assert "Unheard" in text
    assert "K/D: 9.46" in text
    assert "tarkov.dev" in text
    assert "<b>" in text


def test_format_not_found_and_help() -> None:
    missing = format_not_found("NoSuchPlayer", "pve")
    assert "NoSuchPlayer" in missing
    assert "PVE" in missing
    help_text = format_help("eft_scan_bot")
    assert "@eft_scan_bot Nikita" in help_text
    assert "/player" in help_text
