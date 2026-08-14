from __future__ import annotations

from eft_scan.parse import (
    TextEntity,
    is_valid_nickname,
    nickname_error,
    parse_command,
    parse_mention,
    parse_private_text,
)


def test_valid_nicknames() -> None:
    assert is_valid_nickname("Nikita")
    assert is_valid_nickname("PoeBwo-TTV")
    assert is_valid_nickname("TarkovCitizen12")
    assert not is_valid_nickname("ab")
    assert not is_valid_nickname("ник")
    assert nickname_error("аб") is not None


def test_parse_command_player() -> None:
    parsed = parse_command("/player PoeBwo-TTV", "eft_scan_bot")
    assert parsed is not None
    assert parsed.nickname == "PoeBwo-TTV"
    assert parsed.game_mode == "auto"


def test_parse_command_player_pve() -> None:
    parsed = parse_command("/player@eft_scan_bot pve Nikita")
    assert parsed is not None
    assert parsed.nickname == "Nikita"
    assert parsed.game_mode == "pve"


def test_parse_command_pve() -> None:
    parsed = parse_command("/pve Nikita")
    assert parsed is not None
    assert parsed.game_mode == "pve"
    assert parsed.nickname == "Nikita"


def test_parse_command_season() -> None:
    parsed = parse_command("/season Nikita")
    assert parsed is not None
    assert parsed.game_mode == "pvp-season"
    assert parsed.nickname == "Nikita"


def test_parse_command_pvp() -> None:
    parsed = parse_command("/pvp Nikita")
    assert parsed is not None
    assert parsed.game_mode == "regular"


def test_parse_command_ignores_other_bot() -> None:
    parsed = parse_command("/player@otherbot Nikita", "eft_scan_bot")
    assert parsed is None


def test_parse_mention() -> None:
    text = "эй @eft_scan_bot PoeBwo-TTV глянь"
    entities = [TextEntity(type="mention", offset=3, length=len("@eft_scan_bot"))]
    parsed = parse_mention(text, entities, "eft_scan_bot")
    assert parsed is not None
    assert parsed.nickname == "PoeBwo-TTV"
    assert parsed.game_mode == "auto"
    assert parsed.source == "mention"


def test_parse_mention_pve() -> None:
    text = "@eft_scan_bot pve Nikita"
    entities = [TextEntity(type="mention", offset=0, length=len("@eft_scan_bot"))]
    parsed = parse_mention(text, entities, "eft_scan_bot")
    assert parsed is not None
    assert parsed.nickname == "Nikita"
    assert parsed.game_mode == "pve"


def test_parse_mention_season() -> None:
    text = "@eft_scan_bot season Nikita"
    entities = [TextEntity(type="mention", offset=0, length=len("@eft_scan_bot"))]
    parsed = parse_mention(text, entities, "eft_scan_bot")
    assert parsed is not None
    assert parsed.nickname == "Nikita"
    assert parsed.game_mode == "pvp-season"


def test_parse_mention_without_nick() -> None:
    text = "@eft_scan_bot"
    entities = [TextEntity(type="mention", offset=0, length=len("@eft_scan_bot"))]
    parsed = parse_mention(text, entities, "eft_scan_bot")
    assert parsed is not None
    assert parsed.nickname == ""


def test_parse_private_text() -> None:
    parsed = parse_private_text("pve Nikita")
    assert parsed is not None
    assert parsed.game_mode == "pve"
    assert parsed.nickname == "Nikita"
    assert parse_private_text("/player x") is None
