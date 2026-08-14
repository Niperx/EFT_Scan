from __future__ import annotations

from eft_scan.commands import BOT_ABOUT, BOT_COMMANDS, BOT_DESCRIPTION, botfather_copy


def test_botfather_limits() -> None:
    assert len(BOT_ABOUT) <= 120
    assert len(BOT_DESCRIPTION) <= 512
    assert "EFT Scan" in BOT_DESCRIPTION
    assert "tarkov.dev" in BOT_DESCRIPTION


def test_bot_commands_menu() -> None:
    names = [command.command for command in BOT_COMMANDS]
    assert names == ["start", "help", "player", "season", "pvp", "pve", "arena"]
    for command in BOT_COMMANDS:
        assert command.description
        assert len(command.description) <= 256


def test_botfather_copy_contains_sections() -> None:
    text = botfather_copy()
    assert "About" in text
    assert "Description" in text
    assert BOT_ABOUT in text
