from __future__ import annotations

import re
from dataclasses import dataclass

NICKNAME_RE = re.compile(r"^(?:[A-Za-z0-9-_]{3,15}|TarkovCitizen\d{1,10})$")
NICKNAME_CHARS_RE = re.compile(r"^[A-Za-z0-9-_]+$")
COMMAND_RE = re.compile(
    r"^/(player|pve|pvp|regular|season|arena)(?:@([A-Za-z0-9_]+))?(?:\s+|$)",
    re.IGNORECASE,
)

GAME_MODE_ALIASES = {
    "pvp": "regular",
    "regular": "regular",
    "pve": "pve",
    "season": "pvp-season",
    "wipe": "pvp-season",
    "arena": "arena",
}

COMMAND_GAME_MODE = {
    "player": "auto",
    "pvp": "regular",
    "regular": "regular",
    "pve": "pve",
    "season": "pvp-season",
    "arena": "arena",
}


@dataclass(frozen=True, slots=True)
class TextEntity:
    type: str
    offset: int
    length: int


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    nickname: str
    game_mode: str
    source: str


def is_valid_nickname(value: str) -> bool:
    return bool(NICKNAME_RE.fullmatch(value))


def nickname_error(value: str) -> str | None:
    if not value:
        return "Укажите ник игрока."
    if not NICKNAME_CHARS_RE.fullmatch(value) and not value.lower().startswith("tarkovcitizen"):
        return "Ник может содержать только латиницу, цифры, дефис и подчёркивание."
    if not is_valid_nickname(value):
        return "Ник должен быть от 3 до 15 символов."
    return None


def _split_mode_and_nick(rest: str) -> tuple[str, str]:
    parts = rest.split()
    if not parts:
        return "auto", ""
    alias = GAME_MODE_ALIASES.get(parts[0].lower())
    if alias and len(parts) > 1:
        return alias, parts[1]
    return "auto", parts[0]


def parse_command(text: str, bot_username: str | None = None) -> ParsedQuery | None:
    raw = (text or "").strip()
    match = COMMAND_RE.match(raw)
    if not match:
        return None
    mentioned_bot = match.group(2)
    if mentioned_bot and bot_username and mentioned_bot.lower() != bot_username.lower():
        return None
    command = match.group(1).lower()
    rest = raw[match.end() :].strip()
    game_mode = COMMAND_GAME_MODE[command]
    if command == "player":
        game_mode, nickname = _split_mode_and_nick(rest)
    else:
        nickname = rest.split()[0] if rest else ""
    return ParsedQuery(nickname=nickname, game_mode=game_mode, source="command")


def parse_mention(text: str, entities: list[TextEntity], bot_username: str) -> ParsedQuery | None:
    if not text or not bot_username:
        return None
    mention_end: int | None = None
    needle = f"@{bot_username.lower()}"
    for entity in entities:
        if entity.type != "mention":
            continue
        fragment = text[entity.offset : entity.offset + entity.length]
        if fragment.lower() == needle:
            mention_end = entity.offset + entity.length
            break
    if mention_end is None:
        # запасной путь, если клиент не прислал entities
        lowered = text.lower()
        idx = lowered.find(needle)
        if idx < 0:
            return None
        mention_end = idx + len(needle)
    rest = text[mention_end:].strip()
    game_mode, nickname = _split_mode_and_nick(rest)
    if not nickname:
        return ParsedQuery(nickname="", game_mode=game_mode, source="mention")
    return ParsedQuery(nickname=nickname, game_mode=game_mode, source="mention")


def parse_private_text(text: str) -> ParsedQuery | None:
    raw = (text or "").strip()
    if not raw or raw.startswith("/"):
        return None
    game_mode, nickname = _split_mode_and_nick(raw)
    if not nickname:
        return None
    return ParsedQuery(nickname=nickname, game_mode=game_mode, source="private")
